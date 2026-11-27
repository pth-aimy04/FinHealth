"""Out-of-time model orchestration, v2 scale-free scoring, and multi-worker safe registry."""

import hashlib
import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.core.constants import EXCLUDED_INDUSTRIAL_CIKS
from finhealth.core.exceptions import ModelPipelineError
from finhealth.db.lineage import archive_forecast, archive_statement
from finhealth.db.models import Company, FinancialMetric, FinancialStatement
from finhealth.db.repositories import PredictionRepository
from finhealth.ingestion.schemas import is_financial_institution_sic
from finhealth.ml.confidence import (
    BankruptcyAssessmentResult,
    apply_cash_flow_overlay,
    assess_confidence,
    classify_bankruptcy_tier,
    map_pd_to_health_score,
)
from finhealth.ml.distress_classifier import (
    ALL_MODEL_TYPES,
    CANDIDATE_MODEL_TYPES,
    BaselineComparisonSuite,
    DistressClassifier,
    ImbalanceStrategy,
    classify_risk_level,
    compute_ensemble_weights,
    predict_ensemble_probabilities,
    select_best_classifier,
)
from finhealth.ml.evaluator import (
    evaluate_binary_classification,
    evaluate_multitarget_regression,
    reliability_bins,
)
from finhealth.ml.explainer import ShapExplainer
from finhealth.ml.feature_contracts import (
    CORE_BANKRUPTCY_FEATURES,
    MULTI_PERIOD_FEATURES,
    YOY_DELTA_FEATURES,
    ScoringMode,
    assert_scale_free_features,
)
from finhealth.ml.forecaster import NextPeriodForecaster
from finhealth.ml.kaggle_loader import compute_scale_free_features_from_statements
from finhealth.ml.pca_clustering import FinancialHealthClusterer
from finhealth.ml.splitter import (
    FORECAST_TARGET_COLUMNS,
    ML_FEATURE_COLUMNS,
    TemporalSplitter,
    build_next_period_panel,
    prepare_validation_test,
    training_horizon_rows,
)

logger = logging.getLogger(__name__)


@dataclass
class ModelArtifactBundle:
    """Fitted estimators and their evaluation context, suitable only for trusted joblib storage."""

    model_version: str
    clusterer: FinancialHealthClusterer
    forecaster: NextPeriodForecaster
    classifier: DistressClassifier
    baselines: BaselineComparisonSuite
    evaluation_report: dict[str, Any]
    created_at: str
    candidates: dict[str, DistressClassifier] | None = None
    single_period_classifier: DistressClassifier | None = None
    single_period_candidates: dict[str, DistressClassifier] | None = None
    multi_period_classifier: DistressClassifier | None = None
    multi_period_candidates: dict[str, DistressClassifier] | None = None
    ensemble_weights_single: dict[str, float] | None = None
    ensemble_weights_multi: dict[str, float] | None = None
    scoring_contract: str = "legacy_v1"


def industrial_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Exclude unsupported institutions and the known ticker collision by registrant identity."""
    eligible = pd.Series(True, index=panel.index)
    if "cik" in panel:
        eligible &= ~panel["cik"].astype(str).str.zfill(10).isin(EXCLUDED_INDUSTRIAL_CIKS)
    if "sic_code" in panel:
        eligible &= ~panel["sic_code"].map(is_financial_institution_sic)
    return panel.loc[eligible]


def _paired_forecast_scores(test: pd.DataFrame, predictions: pd.DataFrame) -> dict[str, Any]:
    """Compare to unmodified persistence on the same finite current/target row pairs."""
    current = test[list(FORECAST_TARGET_COLUMNS)].replace([np.inf, -np.inf], np.nan)
    persistence = current.rename(columns=lambda name: f"pred_{name}")
    return {
        "persistence": evaluate_multitarget_regression(test, persistence),
        "model": evaluate_multitarget_regression(test, predictions.where(persistence.notna())),
    }


def _train_four_model_suite(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    target_col: str,
    random_seed: int,
    imbalance_strategy: ImbalanceStrategy,
) -> dict[str, Any]:
    """Fit and Platt-calibrate all 4 models (LR/RF/XGB/LGBM) on identical splits."""
    assert_scale_free_features(feature_columns)
    val_labels = val_df[target_col].astype(int)
    test_labels = test_df[target_col].astype(int)

    candidates: dict[str, DistressClassifier] = {}
    for model_name in ALL_MODEL_TYPES:
        clf = DistressClassifier(
            feature_columns=feature_columns,
            random_seed=random_seed,
            model_type=model_name,
            imbalance_strategy=imbalance_strategy,
        ).fit(train_df, target_col=target_col)
        clf.fit_calibration(val_df, val_labels)
        clf.optimize_threshold(val_df, val_labels)
        candidates[model_name] = clf

    best_tree_name, best_tree, val_metrics = select_best_classifier(
        candidates, val_df, val_labels, boosted_tree_only=True
    )
    weights = compute_ensemble_weights(val_metrics)

    explainer = ShapExplainer(best_tree)
    contributions, bases = explainer._explanation(test_df)
    expected_out = (
        best_tree.predict_raw_proba(test_df)
        if explainer.output_space == "probability"
        else best_tree.predict_raw_margin(test_df)
    )
    shap_error = float(np.max(np.abs(bases + contributions.sum(axis=1) - expected_out)))
    if shap_error >= 1e-5:
        raise ModelPipelineError(
            f"TreeSHAP reconstruction error {shap_error:.3e} exceeds 1e-5 for {best_tree_name}"
        )
    importance_raw = dict(
        zip(best_tree.feature_columns, np.abs(contributions).mean(axis=0), strict=True)
    )
    global_shap_importance = {
        key: float(value)
        for key, value in sorted(importance_raw.items(), key=lambda item: (-item[1], item[0]))
    }

    test_metrics: dict[str, dict[str, Any]] = {
        name: evaluate_binary_classification(
            test_labels, clf.predict_proba(test_df), clf.optimal_threshold_
        )
        for name, clf in candidates.items()
    }
    ensemble_val_probs, _ = predict_ensemble_probabilities(candidates, val_df, weights)
    ensemble_test_probs, _ = predict_ensemble_probabilities(candidates, test_df, weights)
    ensemble_test_metrics = evaluate_binary_classification(
        test_labels, ensemble_test_probs, threshold=0.08
    )
    ensemble_val_metrics = evaluate_binary_classification(
        val_labels, ensemble_val_probs, threshold=0.08
    )
    return {
        "candidates": candidates,
        "best_tree_name": best_tree_name,
        "best_tree": best_tree,
        "weights": weights,
        "val_metrics": {**val_metrics, "calibrated_ensemble": ensemble_val_metrics},
        "test_metrics": {**test_metrics, "calibrated_ensemble": ensemble_test_metrics},
        "shap_error": shap_error,
        "shap_output_space": explainer.output_space,
        "global_shap_importance": global_shap_importance,
        "calibrations": {name: clf.calibration_ for name, clf in candidates.items()},
    }


def train_and_evaluate_kaggle_v2_pipeline(
    df_panel: pd.DataFrame,
    train_end_year: int = 2014,
    model_version: str = "v2.0.0-kaggle",
    random_seed: int = 42,
    *,
    validation_end_year: int = 2016,
    imbalance_strategy: ImbalanceStrategy = "class_weight",
) -> ModelArtifactBundle:
    """Train leakage-free v2 Kaggle bankruptcy engine (single_period + multi_period, 4 models)."""
    if not df_panel.index.is_unique:
        raise ModelPipelineError("Training panels require unique row indices")
    if "next_is_bankrupt" not in df_panel.columns:
        raise ModelPipelineError("Kaggle v2 pipeline requires next_is_bankrupt column")

    panel = industrial_panel(df_panel).copy()
    split = TemporalSplitter().split(panel, train_end_year, validation_end_year)
    train = split["train"].copy()
    validation = split["val"].copy()
    test = split["test"].copy()

    # Enforce 0% entity overlap of positive-labeled companies across Train/Val vs Test.
    train_pos_ciks = set(train.loc[train["next_is_bankrupt"] == 1, "cik"].astype(str))
    val_pos_ciks = set(validation.loc[validation["next_is_bankrupt"] == 1, "cik"].astype(str))
    test_pos_ciks = set(test.loc[test["next_is_bankrupt"] == 1, "cik"].astype(str))
    overlap_pos = (train_pos_ciks | val_pos_ciks) & test_pos_ciks
    if overlap_pos:
        raise ModelPipelineError(
            f"Entity leakage detected: {len(overlap_pos)} bankrupt companies appear in both "
            "Train/Val and Test"
        )

    single_suite = _train_four_model_suite(
        train,
        validation,
        test,
        feature_columns=CORE_BANKRUPTCY_FEATURES,
        target_col="next_is_bankrupt",
        random_seed=random_seed,
        imbalance_strategy=imbalance_strategy,
    )
    multi_suite = _train_four_model_suite(
        train,
        validation,
        test,
        feature_columns=MULTI_PERIOD_FEATURES,
        target_col="next_is_bankrupt",
        random_seed=random_seed,
        imbalance_strategy=imbalance_strategy,
    )

    # Fit auxiliary clustering, forecasting, and Altman/LR baselines for complete reporting.
    cluster_train = (
        train.sample(n=8_000, random_state=random_seed) if len(train) > 8_000 else train
    )
    clusterer = FinancialHealthClusterer(random_seed=random_seed).fit(cluster_train)
    shifted = build_next_period_panel(panel)
    shifted_split = TemporalSplitter().split(shifted, train_end_year, validation_end_year)
    shifted_train = shifted_split["train"]
    shifted_train.attrs["train_end_year"] = train_end_year
    shifted_supervised = training_horizon_rows(shifted_train)
    allow_missing = any(
        col not in panel or panel[col].isna().all() for col in FORECAST_TARGET_COLUMNS
    )
    forecaster = NextPeriodForecaster(
        random_seed=random_seed, allow_missing_targets=allow_missing
    ).fit(shifted_supervised)
    target_winsorizer = forecaster.target_winsorizer_
    assert target_winsorizer is not None
    forecaster.tune_shrinkage(shifted_split["val"])
    forecast_preds = forecaster.predict(shifted_split["test"])

    baselines = BaselineComparisonSuite(
        feature_columns=CORE_BANKRUPTCY_FEATURES,
        random_seed=random_seed,
        imbalance_strategy=imbalance_strategy,
    ).fit(train, target_col="next_is_bankrupt")
    baselines.fit_calibration(validation, validation["next_is_bankrupt"].astype(int))
    baseline_test_metrics = baselines.evaluate(test, test["next_is_bankrupt"].astype(int))

    # Primary classifier is the best multi-period tree model; single-period stored alongside it.
    primary_tree: DistressClassifier = multi_suite["best_tree"]
    primary_name: str = multi_suite["best_tree_name"]
    primary_candidates: dict[str, DistressClassifier] = multi_suite["candidates"]
    test_labels = test["next_is_bankrupt"].astype(int)
    raw_probabilities = primary_tree.predict_raw_proba(test)
    calibrated_probabilities = primary_tree.predict_proba(test)

    xgb_clf = primary_candidates["xgboost"]
    xgb_raw_probs = xgb_clf.predict_raw_proba(test)
    xgb_cal_probs = xgb_clf.predict_proba(test)

    # Training-only [1%, 99%] OOD bounds across all 24 scale-free features.
    train_frame = primary_tree.preprocessor.frame(train)
    quantiles = train_frame.quantile([0.01, 0.99])
    ood_bounds = {
        column: [float(v) for v in quantiles[column].tolist()]
        for column in quantiles
        if np.isfinite(quantiles[column]).all()
    }

    all_model_metrics: dict[str, dict[str, Any]] = {
        **multi_suite["test_metrics"],
        "altman_z_baseline": baseline_test_metrics["altman_z_baseline"],
    }

    report: dict[str, Any] = {
        "scoring_contract": "scale_free_v2",
        "feature_columns_single_period": list(CORE_BANKRUPTCY_FEATURES),
        "feature_columns_multi_period": list(MULTI_PERIOD_FEATURES),
        "clustering": clusterer.diagnostics_,
        "forecasting": evaluate_multitarget_regression(shifted_split["test"], forecast_preds),
        "forecasting_winsorized": evaluate_multitarget_regression(
            shifted_split["test"], forecast_preds, target_winsorizer=target_winsorizer
        ),
        "forecast_target_bounds": target_winsorizer.bounds_,
        "forecast_shrinkage": forecaster.blends_,
        "forecasting_paired": _paired_forecast_scores(shifted_split["test"], forecast_preds),
        "feature_ood_bounds": ood_bounds,
        "probability_calibration": primary_tree.calibration_,
        "calibration_all_models_single": single_suite["calibrations"],
        "calibration_all_models_multi": multi_suite["calibrations"],
        "ensemble_weights_single": single_suite["weights"],
        "ensemble_weights_multi": multi_suite["weights"],
        "imbalance_strategy": imbalance_strategy,
        "train_class_counts_before": primary_tree.train_class_counts_before_,
        "train_class_counts_after": primary_tree.train_class_counts_after_,
        "classifier_scale_pos_weight": primary_tree.scale_pos_weight_,
        "test_reliability_bins": reliability_bins(
            test_labels, raw_probabilities, calibrated_probabilities
        ),
        "selected_model_name": primary_name,
        "selected_model_single_period": single_suite["best_tree_name"],
        "selected_model_multi_period": primary_name,
        "classification_selected": multi_suite["test_metrics"][primary_name],
        "classification_xgboost": evaluate_binary_classification(
            test_labels, xgb_cal_probs, xgb_clf.optimal_threshold_
        ),
        "classification_xgboost_raw": evaluate_binary_classification(test_labels, xgb_raw_probs),
        "classification_baselines": baseline_test_metrics,
        "classification_candidates": all_model_metrics,
        "classification_single_period": single_suite["test_metrics"],
        "classification_multi_period": multi_suite["test_metrics"],
        "validation_candidates": multi_suite["val_metrics"],
        "validation_single_period": single_suite["val_metrics"],
        "global_shap_importance": multi_suite["global_shap_importance"],
        "shap_margin_max_abs_error": multi_suite["shap_error"],
        "shap_single_period_max_abs_error": single_suite["shap_error"],
        "shap_output_space": multi_suite["shap_output_space"],
        "shap_model_name": primary_name,
        "split_summary": {
            "train_end_year": train_end_year,
            "train_feature_rows": len(train),
            "train_supervised_rows": len(train),
            "train_positive_rows": int(train["next_is_bankrupt"].sum()),
            "non_forward_supervised_rows": 0,
            "entity_leakage_positive_overlap": 0,
            "total_positive_rows": int(panel["next_is_bankrupt"].sum()),
            "test_rows": len(test),
            "test_rows_before_publication_embargo": len(test),
            "threshold_calibration_asof": f"{validation_end_year}-12-31",
            "test_classification_rows": len(test),
            "test_positive_rows": int(test["next_is_bankrupt"].sum()),
            "max_train_target_year": int(train["fiscal_year"].max()),
            "min_test_feature_year": int(test["fiscal_year"].min()),
            "threshold_source": (
                f"validation_fiscal_years_{train_end_year + 1}_{validation_end_year}"
            ),
            "validation_rows": len(validation),
            "validation_positive_rows": int(validation["next_is_bankrupt"].sum()),
            "label_kind": "observed_1y_bankruptcy_year_eq_max_year",
        },
    }
    return ModelArtifactBundle(
        model_version=model_version,
        clusterer=clusterer,
        forecaster=forecaster,
        classifier=primary_tree,
        baselines=baselines,
        evaluation_report=report,
        created_at=datetime.now(timezone.utc).isoformat(),
        candidates=primary_candidates,
        single_period_classifier=single_suite["best_tree"],
        single_period_candidates=single_suite["candidates"],
        multi_period_classifier=multi_suite["best_tree"],
        multi_period_candidates=multi_suite["candidates"],
        ensemble_weights_single=single_suite["weights"],
        ensemble_weights_multi=multi_suite["weights"],
        scoring_contract="scale_free_v2",
    )


def train_and_evaluate_pipeline(
    df_panel: pd.DataFrame,
    train_end_year: int,
    model_version: str = "v1.0.0",
    random_seed: int = 42,
    *,
    validation_end_year: int | None = None,
    imbalance_strategy: ImbalanceStrategy = "class_weight",
) -> ModelArtifactBundle:
    """Train within the feature/target cutoff and benchmark on the same out-of-time rows."""
    if not df_panel.index.is_unique:
        raise ModelPipelineError("Training panels require unique row indices")
    split = TemporalSplitter().split(
        build_next_period_panel(industrial_panel(df_panel)), train_end_year, validation_end_year
    )
    train, test = split["train"], split["test"]
    train.attrs["train_end_year"] = train_end_year
    if "filed_date" in train:
        cutoff = pd.Timestamp(year=train_end_year, month=12, day=31)
        train = train.loc[pd.to_datetime(train["filed_date"]) <= cutoff].copy()
    supervised = training_horizon_rows(train)
    clusterer = FinancialHealthClusterer(random_seed=random_seed).fit(train)
    allow_missing = any(
        col not in df_panel or df_panel[col].isna().all() for col in FORECAST_TARGET_COLUMNS
    )
    forecaster = NextPeriodForecaster(
        random_seed=random_seed, allow_missing_targets=allow_missing
    ).fit(supervised)
    target_winsorizer = forecaster.target_winsorizer_
    assert target_winsorizer is not None
    candidates: dict[str, DistressClassifier] = {
        model_name: DistressClassifier(
            random_seed=random_seed,
            model_type=model_name,
            imbalance_strategy=imbalance_strategy,
        ).fit(supervised)
        for model_name in CANDIDATE_MODEL_TYPES
    }
    baselines = BaselineComparisonSuite(
        random_seed=random_seed, imbalance_strategy=imbalance_strategy
    ).fit(supervised)
    threshold_source = "fixed_0.5_no_validation_set"
    validation_rows = 0
    validation_positives = 0
    calibration_asof = None
    raw_test_rows = len(test)
    validation_scores: dict[str, dict[str, Any]] | None = None
    if validation_end_year is not None:
        validation, test, calibration_asof = prepare_validation_test(
            split["val"], test, validation_end_year
        )
        if validation.empty:
            raise ModelPipelineError(
                "No observable sequential validation targets for threshold tuning"
            )
        validation_labels = validation["next_is_distressed"].astype(int)
        for candidate in candidates.values():
            candidate.fit_calibration(validation, validation_labels)
            candidate.optimize_threshold(validation, validation_labels)
        baselines.fit_calibration(validation, validation_labels)
        forecaster.tune_shrinkage(validation)
        validation_rows = len(validation)
        validation_positives = int(validation_labels.sum())
        threshold_source = f"validation_fiscal_years_{train_end_year + 1}_{validation_end_year}"
        selected_name, classifier, validation_scores = select_best_classifier(
            candidates, validation, validation_labels, tree_only=True
        )
    labeled_test = test.loc[test["next_is_distressed"].notna()]
    if labeled_test.empty:
        raise ModelPipelineError(
            "Out-of-time test split has no observed sequential distress targets"
        )
    labels = labeled_test["next_is_distressed"].astype(int)
    if validation_end_year is None:
        selected_name, classifier, _ = select_best_classifier(
            candidates, labeled_test, labels, tree_only=True
        )
    predictions = forecaster.predict(test)
    explainer = ShapExplainer(classifier)
    raw_probabilities = classifier.predict_raw_proba(labeled_test)
    calibrated_probabilities = classifier.predict_proba(labeled_test)
    shap_error = explainer.verify_reconstruction_error(labeled_test)
    if shap_error >= 1e-5:
        raise ModelPipelineError(f"TreeSHAP raw-margin reconstruction error: {shap_error}")
    xgb_clf = candidates["xgboost"]
    xgb_raw_probs = xgb_clf.predict_raw_proba(labeled_test)
    xgb_cal_probs = xgb_clf.predict_proba(labeled_test)
    baseline_metrics = baselines.evaluate(labeled_test, labels)
    candidate_test_metrics: dict[str, dict[str, Any]] = {
        name: evaluate_binary_classification(
            labels, cand.predict_proba(labeled_test), cand.optimal_threshold_
        )
        for name, cand in candidates.items()
    }
    all_model_metrics: dict[str, dict[str, Any]] = {**candidate_test_metrics, **baseline_metrics}
    quantiles = classifier.preprocessor.frame(
        supervised.dropna(subset=["next_is_distressed"])
    ).quantile([0.01, 0.99])
    bounds = {
        column: quantiles[column].tolist()
        for column in quantiles
        if np.isfinite(quantiles[column]).all()
    }
    non_forward = (
        int((supervised["next_filed_date"] <= supervised["filed_date"]).sum())
        if "filed_date" in supervised
        else 0
    )
    report = {
        "clustering": clusterer.diagnostics_,
        "forecasting": evaluate_multitarget_regression(test, predictions),
        "forecasting_winsorized": evaluate_multitarget_regression(
            test, predictions, target_winsorizer=target_winsorizer
        ),
        "forecast_target_bounds": target_winsorizer.bounds_,
        "forecast_shrinkage": forecaster.blends_,
        "forecasting_paired": _paired_forecast_scores(test, predictions),
        "feature_ood_bounds": bounds,
        "probability_calibration": classifier.calibration_,
        "imbalance_strategy": imbalance_strategy,
        "train_class_counts_before": classifier.train_class_counts_before_,
        "train_class_counts_after": classifier.train_class_counts_after_,
        "classifier_scale_pos_weight": classifier.scale_pos_weight_,
        "test_reliability_bins": reliability_bins(
            labels, raw_probabilities, calibrated_probabilities
        ),
        "selected_model_name": selected_name,
        "classification_selected": candidate_test_metrics[selected_name],
        "classification_xgboost": evaluate_binary_classification(
            labels, xgb_cal_probs, xgb_clf.optimal_threshold_
        ),
        "classification_xgboost_raw": evaluate_binary_classification(labels, xgb_raw_probs),
        "classification_baselines": baseline_metrics,
        "classification_candidates": all_model_metrics,
        "validation_candidates": validation_scores,
        "global_shap_importance": explainer.compute_global_importance(labeled_test),
        "shap_margin_max_abs_error": shap_error,
        "shap_output_space": explainer.output_space,
        "shap_model_name": explainer.model_name,
        "split_summary": {
            "train_end_year": train_end_year,
            "train_feature_rows": len(train),
            "train_supervised_rows": len(supervised),
            "non_forward_supervised_rows": non_forward,
            "test_rows": len(test),
            "test_rows_before_publication_embargo": raw_test_rows,
            "threshold_calibration_asof": calibration_asof,
            "test_classification_rows": len(labeled_test),
            "max_train_target_year": int(supervised["next_fiscal_year"].max()),
            "min_test_feature_year": int(test["fiscal_year"].min()),
            "threshold_source": threshold_source,
            "validation_rows": validation_rows,
            "validation_positive_rows": validation_positives,
            "label_kind": "observed_when_supplied_otherwise_fundamental_distress_v1",
        },
    }
    return ModelArtifactBundle(
        model_version,
        clusterer,
        forecaster,
        classifier,
        baselines,
        report,
        datetime.now(timezone.utc).isoformat(),
        candidates=candidates,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Durably write strict JSON into an unpublished staging directory."""
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def save_bundle(
    bundle: ModelArtifactBundle, artifacts_dir: Path, *, pending: bool = False
) -> Path:
    """Stage and atomically publish a complete immutable version; never overwrite prior bundles."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", bundle.model_version):
        raise ModelPipelineError(
            "Model version must be a safe directory name of at most 64 characters"
        )
    destination = artifacts_dir / bundle.model_version
    if destination.exists():
        raise ModelPipelineError(f"Artifact version already exists: {bundle.model_version}")
    try:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".finhealth-", dir=artifacts_dir) as temporary:
            staging = Path(temporary) / "bundle"
            staging.mkdir()
            model_path = staging / "models.joblib"
            if pending:
                (staging / ".unpublished").touch()
            joblib.dump(bundle, model_path, compress=3)
            _write_json(staging / "evaluation_report.json", bundle.evaluation_report)
            _write_json(
                staging / "metadata.json",
                {
                    "model_version": bundle.model_version,
                    "created_at": bundle.created_at,
                    "scoring_contract": getattr(bundle, "scoring_contract", "legacy_v1"),
                    "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                    "dependencies": {
                        name: version(name)
                        for name in (
                            "scikit-learn",
                            "xgboost",
                            "lightgbm",
                            "shap",
                            "numpy",
                            "pandas",
                            "joblib",
                        )
                    },
                },
            )
            staging.replace(destination)
    except (OSError, TypeError, ValueError) as error:
        raise ModelPipelineError("Cannot atomically save model bundle") from error
    return destination


def load_bundle(bundle_dir: Path) -> ModelArtifactBundle:
    """Load a trusted local bundle after verifying integrity and matching JSON metadata."""
    try:
        metadata = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
        path = bundle_dir / "models.joblib"
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ModelPipelineError("Model artifact checksum mismatch")
        bundle = joblib.load(path)
        report = json.loads((bundle_dir / "evaluation_report.json").read_text(encoding="utf-8"))
        if (
            not isinstance(bundle, ModelArtifactBundle)
            or bundle.model_version != metadata["model_version"]
        ):
            raise ModelPipelineError("Model bundle type/version does not match metadata")
        if json.loads(json.dumps(bundle.evaluation_report)) != report:
            raise ModelPipelineError("Evaluation JSON does not match the model bundle")
        return bundle
    except (OSError, ValueError, KeyError, EOFError) as error:
        raise ModelPipelineError("Cannot load model bundle") from error


def _prepare_scoring_frame(records: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Normalize statement records and compute scale-free ratios if raw items are supplied."""
    df = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(list(records))
    if df.empty:
        raise ModelPipelineError("Company scoring requires at least one financial statement record")
    if "fiscal_year" in df.columns:
        df = df.sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)
    elif "period_end_date" in df.columns:
        df["period_end_date"] = pd.to_datetime(df["period_end_date"])
        df = df.sort_values("period_end_date", kind="mergesort").reset_index(drop=True)

    missing_core = [col for col in CORE_BANKRUPTCY_FEATURES if col not in df.columns]
    if missing_core and any(
        raw in df.columns for raw in ("total_assets", "revenues", "total_liabilities", "net_income")
    ):
        computed = compute_scale_free_features_from_statements(df)
        for col in MULTI_PERIOD_FEATURES:
            if col not in df.columns:
                df[col] = computed[col]
            else:
                df[col] = df[col].where(df[col].notna(), computed[col])
    else:
        for col in MULTI_PERIOD_FEATURES:
            if col not in df.columns:
                df[col] = np.nan
    return df


def score_company_bankruptcy(
    bundle: ModelArtifactBundle,
    records: Sequence[Mapping[str, Any]] | pd.DataFrame,
    *,
    audit_status: str = "audited_unqualified",
    negative_ocf_streak: int | None = None,
    interest_coverage: float | None = None,
    operating_cash_flow: float | None = None,
) -> BankruptcyAssessmentResult:
    """Score one company using single_period or multi_period calibrated 4-model ensemble."""
    df = _prepare_scoring_frame(records)
    latest = df.iloc[[-1]]
    latest_row = latest.iloc[0]

    has_multi_models = (
        getattr(bundle, "multi_period_candidates", None) is not None
        and getattr(bundle, "multi_period_classifier", None) is not None
    )
    has_single_models = (
        getattr(bundle, "single_period_candidates", None) is not None
        and getattr(bundle, "single_period_classifier", None) is not None
    )
    has_valid_yoy = len(df) >= 2 and any(
        (val := latest_row.get(col)) is not None
        and pd.notna(val)
        and np.isfinite(float(val))
        for col in YOY_DELTA_FEATURES
    )

    if has_multi_models and has_valid_yoy:
        scoring_mode: ScoringMode = "multi_period"
        candidates = bundle.multi_period_candidates
        primary_tree = bundle.multi_period_classifier
        weights = bundle.ensemble_weights_multi
    elif has_single_models:
        scoring_mode = "single_period"
        candidates = bundle.single_period_candidates
        primary_tree = bundle.single_period_classifier
        weights = bundle.ensemble_weights_single
    else:
        scoring_mode = "single_period"
        candidates = bundle.candidates or {
            getattr(bundle.classifier, "model_type", "xgboost"): bundle.classifier
        }
        primary_tree = bundle.classifier
        weights = None

    assert candidates is not None and primary_tree is not None
    ensemble_probs, per_model_arrays = predict_ensemble_probabilities(candidates, latest, weights)
    pd_12m = float(ensemble_probs[0])
    model_probabilities = {name: float(arr[0]) for name, arr in per_model_arrays.items()}

    base_tier = classify_bankruptcy_tier(pd_12m)
    eff_streak = (
        negative_ocf_streak
        if negative_ocf_streak is not None
        else int(latest_row["negative_ocf_streak"])
        if "negative_ocf_streak" in latest_row and pd.notna(latest_row["negative_ocf_streak"])
        else 0
    )
    eff_ic = (
        interest_coverage
        if interest_coverage is not None
        else float(latest_row["interest_coverage"])
        if "interest_coverage" in latest_row and pd.notna(latest_row["interest_coverage"])
        else None
    )
    eff_ocf = (
        operating_cash_flow
        if operating_cash_flow is not None
        else float(latest_row["operating_cash_flow"])
        if "operating_cash_flow" in latest_row and pd.notna(latest_row["operating_cash_flow"])
        else None
    )
    overlay = apply_cash_flow_overlay(
        base_tier,
        negative_ocf_streak=eff_streak,
        interest_coverage=eff_ic,
        operating_cash_flow=eff_ocf,
        audit_status=audit_status,
    )
    health_score = map_pd_to_health_score(pd_12m)
    confidence = assess_confidence(
        {str(k): v for k, v in latest_row.to_dict().items()},
        feature_ood_bounds=bundle.evaluation_report.get("feature_ood_bounds"),
        model_probabilities=model_probabilities,
        audit_status=audit_status,
        core_features=CORE_BANKRUPTCY_FEATURES,
    )
    shap_explanation = ShapExplainer(primary_tree).explain_instance(latest)
    return BankruptcyAssessmentResult(
        model_version=bundle.model_version,
        scoring_mode=scoring_mode,
        pd_12m=pd_12m,
        risk_tier=overlay.adjusted_tier,
        health_score=health_score,
        confidence=confidence,
        cash_flow_overlay=overlay,
        shap_explanation=shap_explanation,
        model_probabilities=model_probabilities,
    )


def predict_for_company_records(
    bundle: ModelArtifactBundle, records: list[dict[str, Any]] | pd.DataFrame
) -> dict[str, Any]:
    """Predict the latest observed period for one company, retaining all real SHAP drivers."""
    df = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(records)
    if df.empty or "period_end_date" not in df:
        raise ModelPipelineError("Company inference requires dated records")
    key = "company_id" if "company_id" in df else "cik"
    if key not in df or df[key].isna().any() or df[key].nunique() != 1:
        raise ModelPipelineError("Company inference requires exactly one company")
    df["period_end_date"] = pd.to_datetime(df["period_end_date"])
    sort_cols = ["period_end_date", "form_type"] if "form_type" in df.columns else [
        "period_end_date"
    ]
    latest = df.sort_values(sort_cols).iloc[[-1]]
    cluster_dict = {
        str(k): v for k, v in bundle.clusterer.transform(latest).iloc[0].to_dict().items()
    }
    forecast_dict = {
        str(k): v for k, v in bundle.forecaster.predict(latest).iloc[0].to_dict().items()
    }
    if getattr(bundle, "scoring_contract", "legacy_v1") == "scale_free_v2":
        assessment = score_company_bankruptcy(bundle, df)
        probability = assessment.pd_12m
        result: dict[str, Any] = {
            **cluster_dict,
            **forecast_dict,
            "distress_probability": probability,
            "pd_12m": probability,
            "predicted_label": int(probability >= bundle.classifier.optimal_threshold_),
            "risk_level": classify_risk_level(probability),
            "risk_tier": assessment.risk_tier,
            "health_score": assessment.health_score,
            "scoring_mode": assessment.scoring_mode,
            "confidence": assessment.confidence.to_dict(),
            "cash_flow_overlay": assessment.cash_flow_overlay.to_dict(),
            "model_probabilities": assessment.model_probabilities,
            "model_version": bundle.model_version,
            "shap_explanations": assessment.shap_explanation,
        }
        return result

    explanation = ShapExplainer(bundle.classifier).explain_instance(latest)
    probability = explanation["distress_probability"]
    result = {
        **cluster_dict,
        **forecast_dict,
        "distress_probability": probability,
        "predicted_label": int(probability >= bundle.classifier.optimal_threshold_),
        "risk_level": classify_risk_level(probability),
        "model_version": bundle.model_version,
        "shap_explanations": explanation,
    }
    return result


def sync_company_prediction(session: Session, company_id: int, bundle: ModelArtifactBundle) -> bool:
    """Update annual cluster assignments and the latest forecast in the caller's transaction."""
    rows = session.execute(
        select(FinancialStatement, FinancialMetric)
        .outerjoin(FinancialMetric, FinancialMetric.statement_id == FinancialStatement.id)
        .where(FinancialStatement.company_id == company_id, FinancialStatement.form_type == "10-K")
        .order_by(FinancialStatement.period_end_date, FinancialStatement.id)
    ).all()
    if not rows:
        return False
    if any(metric is None for _, metric in rows):
        raise ModelPipelineError("Annual statement has no engineered metrics")
    frame = pd.DataFrame(
        [
            {
                "company_id": company_id,
                "period_end_date": statement.period_end_date,
                "form_type": statement.form_type,
                **{name: getattr(metric, name) for name in ML_FEATURE_COLUMNS},
            }
            for statement, metric in rows
        ]
    )
    inferred = predict_for_company_records(bundle, frame)
    for (_, metric), coords in zip(
        rows, bundle.clusterer.transform(frame).to_dict("records"), strict=True
    ):
        for key, value in coords.items():
            setattr(metric, str(key), value)
    latest = rows[-1][0]
    keys = (
        *(f"pred_{name}" for name in bundle.forecaster.target_columns),
        "distress_probability",
        "risk_level",
        "shap_explanations",
    )
    prediction = PredictionRepository(session).upsert_prediction(
        company_id,
        latest.id,
        bundle.model_version,
        latest.fiscal_year + 1,
        "FY",
        {key: inferred[key] for key in keys},
    )
    company = session.get(Company, company_id)
    assert company is not None
    version_row = archive_statement(session, company.cik, latest, "normalized")
    reported = {
        str(name): float(value) if pd.notna(value) else None
        for name, value in frame.iloc[-1][list(ML_FEATURE_COLUMNS)].items()
    }
    archive_forecast(
        session,
        version_row,
        prediction,
        reported,
        inferred["shap_explanations"]["fitted_inputs"],
    )
    return True


class ModelRegistryState:
    """Multi-worker safe model registry tracking latest.json mtime_ns and sha256 manifest."""

    def __init__(self) -> None:
        """Initialize empty activation state without filesystem or model loading side effects."""
        self._lock = RLock()
        self.training_lock = RLock()
        self._bundle: ModelArtifactBundle | None = None
        self._v2_bundle: ModelArtifactBundle | None = None
        self._v2_checked = False
        self._initialized = False
        self._directory: Path | None = None
        self._pointer_mtime_ns: int | None = None
        self._pointer_sha256: str | None = None

    def get(self) -> ModelArtifactBundle | None:
        """Return the currently active complete bundle, reloading if latest.json changed."""
        with self._lock:
            if self._directory is not None:
                self._reload_if_pointer_changed(self._directory)
            return self._bundle

    def get_scale_free_v2(self) -> ModelArtifactBundle | None:
        """Return the active scale_free_v2 bundle, loading v2.0.0-kaggle beside legacy latest."""
        with self._lock:
            active = self.get()
            if (
                active is not None
                and getattr(active, "scoring_contract", "legacy_v1") == "scale_free_v2"
            ):
                return active
            if self._v2_checked:
                return self._v2_bundle
            self._v2_checked = True
            if self._directory is not None:
                candidate_dir = self._directory / "v2.0.0-kaggle"
                if candidate_dir.is_dir():
                    try:
                        loaded = load_bundle(candidate_dir)
                        if getattr(loaded, "scoring_contract", "legacy_v1") == "scale_free_v2":
                            self._v2_bundle = loaded
                    except ModelPipelineError as error:
                        logger.warning("Cannot load v2.0.0-kaggle bundle: %s", error)
            return self._v2_bundle

    def set(self, bundle: ModelArtifactBundle | None) -> None:
        """Explicitly publish or clear the active model in memory."""
        with self._lock:
            self._bundle = bundle
            self._v2_bundle = None
            self._v2_checked = False
            self._initialized = True
            self._directory = None
            self._pointer_mtime_ns = None
            self._pointer_sha256 = None

    def _load_from_pointer_bytes(
        self, resolved: Path, raw_bytes: bytes, mtime_ns: int, digest: str
    ) -> None:
        """Parse latest.json bytes and atomically swap the active bundle on success."""
        target = json.loads(raw_bytes.decode("utf-8"))
        name = target["bundle_dir"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name)
            or target["model_version"] != name
        ):
            raise ValueError("Invalid published bundle name")
        bundle = load_bundle(resolved / name)
        if bundle.model_version != name:
            raise ValueError("Published bundle version mismatch")
        self._bundle = bundle
        self._pointer_mtime_ns = mtime_ns
        self._pointer_sha256 = digest
        self._initialized = True

    def _reload_if_pointer_changed(self, resolved: Path) -> bool:
        """Check latest.json mtime_ns and sha256; reload bundle atomically if updated."""
        pointer = resolved / "latest.json"
        if not pointer.is_file():
            return False
        try:
            stat = pointer.stat()
            if self._pointer_mtime_ns == stat.st_mtime_ns and self._bundle is not None:
                return False
            raw_bytes = pointer.read_bytes()
            digest = hashlib.sha256(raw_bytes).hexdigest()
            if self._pointer_sha256 == digest and self._bundle is not None:
                self._pointer_mtime_ns = stat.st_mtime_ns
                return False
            self._load_from_pointer_bytes(resolved, raw_bytes, stat.st_mtime_ns, digest)
            return True
        except (OSError, KeyError, TypeError, ValueError, ModelPipelineError) as error:
            logger.warning("Cannot reload published model from latest.json: %s", error)
            return False

    def initialize(self, directory: Path) -> None:
        """Load the published pointer and auto-reload whenever latest.json mtime/sha256 changes."""
        resolved = directory.resolve()
        with self._lock:
            if self._initialized and self._directory == resolved:
                self._reload_if_pointer_changed(resolved)
                return
            if self._initialized and self._directory is None:
                return
            self._bundle = None
            self._v2_bundle = None
            self._v2_checked = False
            self._directory = resolved
            self._pointer_mtime_ns = None
            self._pointer_sha256 = None
            pointer = resolved / "latest.json"
            if pointer.is_file():
                try:
                    stat = pointer.stat()
                    raw_bytes = pointer.read_bytes()
                    digest = hashlib.sha256(raw_bytes).hexdigest()
                    self._load_from_pointer_bytes(resolved, raw_bytes, stat.st_mtime_ns, digest)
                    return
                except (OSError, KeyError, TypeError, ValueError, ModelPipelineError) as error:
                    logger.warning("Cannot load published model: %s", error)
                    self._initialized = True
                    return
            candidates: list[ModelArtifactBundle] = []
            if resolved.is_dir():
                for child in sorted(resolved.iterdir()):
                    if (
                        child.is_dir()
                        and not child.name.startswith(".")
                        and not (child / ".unpublished").exists()
                    ):
                        try:
                            candidates.append(load_bundle(child))
                        except ModelPipelineError as error:
                            logger.warning(
                                "Skipping invalid model artifact %s: %s", child.name, error
                            )
            if candidates:
                self._bundle = max(
                    candidates, key=lambda item: (item.created_at, item.model_version)
                )
            self._initialized = True
