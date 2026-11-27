"""Out-of-time model orchestration and immutable, atomically published artifact bundles."""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
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
from finhealth.ml.distress_classifier import (
    CANDIDATE_MODEL_TYPES,
    BaselineComparisonSuite,
    DistressClassifier,
    ImbalanceStrategy,
    classify_risk_level,
    select_best_classifier,
)
from finhealth.ml.evaluator import (
    evaluate_binary_classification,
    evaluate_multitarget_regression,
    reliability_bins,
)
from finhealth.ml.explainer import ShapExplainer
from finhealth.ml.forecaster import NextPeriodForecaster
from finhealth.ml.pca_clustering import FinancialHealthClusterer
from finhealth.ml.splitter import (
    FORECAST_TARGET_COLUMNS,
    ML_FEATURE_COLUMNS,
    TemporalSplitter,
    build_next_period_panel,
    prepare_validation_test,
    training_horizon_rows,
)


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
        forecaster.tune_shrinkage(validation)
        validation_rows = len(validation)
        validation_positives = int(validation_labels.sum())
        threshold_source = f"validation_fiscal_years_{train_end_year + 1}_{validation_end_year}"
        selected_name, classifier, validation_scores = select_best_classifier(
            candidates, validation, validation_labels
        )
    labeled_test = test.loc[test["next_is_distressed"].notna()]
    if labeled_test.empty:
        raise ModelPipelineError(
            "Out-of-time test split has no observed sequential distress targets"
        )
    labels = labeled_test["next_is_distressed"].astype(int)
    if validation_end_year is None:
        selected_name, classifier, _ = select_best_classifier(candidates, labeled_test, labels)
    predictions = forecaster.predict(test)
    explainer = ShapExplainer(classifier)
    contributions, bases = explainer._explanation(labeled_test)
    raw_margin = classifier.predict_raw_margin(labeled_test)
    raw_probabilities = classifier.predict_raw_proba(labeled_test)
    calibrated_probabilities = classifier.predict_proba(labeled_test)
    expected_shap_sum = (
        raw_probabilities
        if getattr(classifier, "model_type", "xgboost") == "random_forest"
        else raw_margin
    )
    shap_error = float(
        np.max(np.abs(bases + contributions.astype(float).sum(axis=1) - expected_shap_sum))
    )
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
        else None
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
        # JSON canonicalization converts integer diagnostic keys consistently.
        if json.loads(json.dumps(bundle.evaluation_report)) != report:
            raise ModelPipelineError("Evaluation JSON does not match the model bundle")
        return bundle
    except (OSError, ValueError, KeyError, EOFError) as error:
        raise ModelPipelineError("Cannot load model bundle") from error


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
    latest = df.sort_values(["period_end_date", "form_type"]).iloc[[-1]]
    explanation = ShapExplainer(bundle.classifier).explain_instance(latest)
    probability = explanation["distress_probability"]
    result = {
        **bundle.clusterer.transform(latest).iloc[0].to_dict(),
        **bundle.forecaster.predict(latest).iloc[0].to_dict(),
        "distress_probability": probability,
        "predicted_label": int(probability >= bundle.classifier.optimal_threshold_),
        "risk_level": classify_risk_level(probability),
        "model_version": bundle.model_version,
        "shap_explanations": explanation,
    }
    return {str(name): value for name, value in result.items()}


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
    version = archive_statement(session, company.cik, latest, "normalized")
    reported = {
        str(name): float(value) if pd.notna(value) else None
        for name, value in frame.iloc[-1][list(ML_FEATURE_COLUMNS)].items()
    }
    archive_forecast(
        session, version, prediction, reported, inferred["shap_explanations"]["fitted_inputs"]
    )
    return True
