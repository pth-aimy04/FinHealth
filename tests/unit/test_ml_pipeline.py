"""Deterministic synthetic panel experiments with real estimators, SHAP, and artifact I/O."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit
from sklearn.metrics import fbeta_score

from finhealth.core.exceptions import ModelPipelineError
from finhealth.etl.feature_engineering import compute_temporal_features
from finhealth.etl.financial_ratios import compute_statement_ratios
from finhealth.etl.pipeline import FinancialEtlPipeline
from finhealth.ml.distress_classifier import (
    BaselineComparisonSuite,
    DistressClassifier,
    classify_risk_level,
)
from finhealth.ml.evaluator import evaluate_binary_classification, evaluate_multitarget_regression
from finhealth.ml.explainer import ShapExplainer
from finhealth.ml.forecaster import NextPeriodForecaster
from finhealth.ml.pca_clustering import FinancialHealthClusterer
from finhealth.ml.registry import (
    ModelArtifactBundle,
    load_bundle,
    predict_for_company_records,
    save_bundle,
    train_and_evaluate_pipeline,
)
from finhealth.ml.splitter import (
    FORECAST_TARGET_COLUMNS,
    ML_FEATURE_COLUMNS,
    TemporalSplitter,
    build_next_period_panel,
    derive_distress_label,
    training_horizon_rows,
)


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    """Generate accounting-consistent synthetic companies, never presented as real issuer data."""
    rng = np.random.default_rng(42)
    rows: list[dict[str, Any]] = []
    for company in range(24):
        kind = company // 6
        debt = [0.25, 0.45, 0.72, 0.92][kind]
        roa = [0.18, 0.08, 0.015, -0.20][kind]
        ocf_ratio = [0.35, 0.16, 0.035, -0.15][kind]
        for year in range(2019, 2024):
            assets = (100 + company * 5) * 1e6 * (1.03 ** (year - 2019))
            liabilities = assets * (debt + rng.normal(0, 0.004))
            profit = assets * (roa + (year - 2019) * 0.001 + rng.normal(0, 0.002))
            row = {
                "company_id": company,
                "form_type": "10-K",
                "fiscal_year": year,
                "fiscal_period": "FY",
                "period_end_date": date(year, 12, 31),
                "total_assets": assets,
                "total_liabilities": liabilities,
                "stockholders_equity": assets - liabilities,
                "net_income": profit,
                "current_assets": 0.4 * assets,
                "current_liabilities": 0.4 * assets / [2.5, 1.5, 1, 0.6][kind],
                "operating_income": profit * 1.2,
                "revenues": assets * (1.2 - 0.15 * kind),
                "retained_earnings": assets * [0.4, 0.2, 0.04, -0.3][kind],
                "operating_cash_flow": liabilities * ocf_ratio,
                "eps_diluted": profit / 1e7,
                "eps_basic": profit / 9.9e6,
                "is_distressed": int(kind == 3),
            }
            row.update(compute_statement_ratios(row))
            rows.append(row)
    return pd.DataFrame(compute_temporal_features(rows))


@pytest.fixture(scope="module")
def splits(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Construct real sequential targets before a deterministic out-of-time partition."""
    return TemporalSplitter().split(build_next_period_panel(panel), 2021)


@pytest.fixture(scope="module")
def bundle(panel: pd.DataFrame) -> ModelArtifactBundle:
    """Train a real end-to-end bundle once for artifact and explainability verification."""
    return train_and_evaluate_pipeline(panel, 2021, "test-v1")


def test_temporal_splitter_and_next_period_alignment(
    panel: pd.DataFrame, splits: dict[str, pd.DataFrame]
) -> None:
    """Verify group ownership, yearly gaps, quarterly gaps, and train-target boundary purging."""
    assert splits["train"]["fiscal_year"].max() == 2021
    assert splits["test"]["fiscal_year"].min() == 2022
    full = build_next_period_panel(panel)
    first = full.loc[(full["company_id"] == 0) & (full["fiscal_year"] == 2019)].iloc[0]
    actual_next = panel.loc[(panel["company_id"] == 0) & (panel["fiscal_year"] == 2020)].iloc[0]
    assert first["next_roa"] == actual_next["roa"]
    assert full.loc[full["fiscal_year"] == 2023, "next_roa"].isna().all()
    gapped = panel.loc[~((panel["company_id"] == 0) & panel["fiscal_year"].eq(2021))]
    result = build_next_period_panel(gapped)
    assert (
        result.loc[(result["company_id"] == 0) & result["fiscal_year"].eq(2020), "next_roa"]
        .isna()
        .all()
    )
    purged = training_horizon_rows(splits["train"])
    assert len(purged) == 48
    assert purged["next_fiscal_year"].max() == 2021
    assert training_horizon_rows(purged).index.equals(purged.index)
    with pytest.raises(ModelPipelineError):
        TemporalSplitter().split(panel, 2018)
    with pytest.raises(ModelPipelineError):
        TemporalSplitter().split(panel, 2023)
    with pytest.raises(ModelPipelineError):
        TemporalSplitter().split(panel, 2021, 2020)
    validation = TemporalSplitter().split(panel, 2020, 2021)
    assert set(validation["val"]["fiscal_year"]) == {2021}
    quarters = panel.iloc[:3].copy()
    quarters["company_id"] = 99
    quarters["form_type"] = "10-Q"
    quarters["fiscal_year"] = [2020, 2020, 2021]
    quarters["fiscal_period"] = ["Q1", "Q3", "Q1"]
    quarters["period_end_date"] = [date(2020, 3, 31), date(2020, 9, 30), date(2021, 3, 31)]
    assert build_next_period_panel(quarters)["next_roa"].isna().all()


def test_pca_clustering_deterministic_health_ranking(splits: dict[str, pd.DataFrame]) -> None:
    """Verify ordered economic meaning, real variance/silhouette, and immutable train bounds."""
    train, test = splits["train"], splits["test"]
    clusterer = FinancialHealthClusterer().fit(train)
    transformed = clusterer.transform(test)
    assert transformed.index.equals(test.index)
    assert set(transformed.loc[test["company_id"] < 6, "cluster_id"]) == {0}
    assert set(transformed.loc[test["company_id"] >= 18, "cluster_id"]) == {3}
    assert set(transformed.loc[test["company_id"] >= 18, "cluster_label"]) == {
        "Financial Distress / High Risk"
    }
    diagnostics = clusterer.diagnostics_
    assert 0 < diagnostics["cumulative_variance_ratio"] <= 1.000001
    assert -1 <= diagnostics["silhouette_score"] <= 1
    assert diagnostics["silhouette_score"] > 0.5
    scores = [diagnostics["cluster_profiles"][i]["health_score"] for i in range(4)]
    assert scores == sorted(scores, reverse=True)
    again = FinancialHealthClusterer().fit(train).transform(test)
    pd.testing.assert_frame_equal(transformed, again)
    statistics = clusterer.preprocessor.imputer.statistics_.copy()
    clusterer.transform(test.assign(roa=1000))
    np.testing.assert_array_equal(statistics, clusterer.preprocessor.imputer.statistics_)


def test_next_period_forecaster_and_metrics(splits: dict[str, pd.DataFrame]) -> None:
    """Fit actual regressors and verify paired metrics, including a known independent example."""
    forecaster = NextPeriodForecaster().fit(splits["train"])
    prediction = forecaster.predict(splits["test"])
    assert list(prediction) == [f"pred_{column}" for column in FORECAST_TARGET_COLUMNS]
    assert np.isfinite(prediction.to_numpy()).all()
    report = evaluate_multitarget_regression(splits["test"], prediction)
    for target in FORECAST_TARGET_COLUMNS:
        assert report[target]["n_samples"] == 24
        assert report[target]["mae"] >= 0
        assert report[target]["rmse"] >= report[target]["mae"] - 1e-9
        assert np.isfinite(report[target]["r2"])
    truth = pd.DataFrame({"next_roa": [1.0, 2.0, 3.0]}, index=[0, 1, 2])
    pred = pd.DataFrame({"pred_roa": [4.0, 2.0, 1.0]}, index=[2, 1, 0])
    exact = evaluate_multitarget_regression(truth, pred, ["roa"])["roa"]
    assert exact["mae"] == pytest.approx(1 / 3)
    assert exact["rmse"] == pytest.approx(np.sqrt(1 / 3))
    assert exact["r2"] == pytest.approx(0.5)
    with pytest.raises(ModelPipelineError):
        NextPeriodForecaster().fit(splits["train"].assign(next_roa=np.nan))


def test_non_forward_publications_invalidate_all_targets(panel: pd.DataFrame) -> None:
    """Discard same-day and backwards comparisons even for consecutive economic periods."""
    rows = panel.loc[panel["company_id"].eq(0)].iloc[:4].copy()
    rows["filed_date"] = pd.to_datetime(["2022-02-01", "2022-02-01", "2022-01-15", "2023-02-01"])
    shifted = build_next_period_panel(rows)
    targets = [f"next_{name}" for name in (*FORECAST_TARGET_COLUMNS, "is_distressed")]
    assert shifted.iloc[:2][targets].isna().all().all()
    assert shifted.iloc[2][targets].notna().all()
    rows = rows.assign(next_fiscal_year=2022, next_filed_date=pd.Timestamp("2022-02-01"))
    rows.attrs["train_end_year"] = 2022
    assert training_horizon_rows(rows).index.tolist() == [rows.index[2]]


def test_altman_baseline_uses_each_rows_strict_cutoff(splits: dict[str, pd.DataFrame]) -> None:
    """Apply the variant-specific rule to identical scores and neutralize missing scores."""
    baseline = BaselineComparisonSuite().fit(splits["train"])
    rows = (
        splits["test"]
        .iloc[:6]
        .assign(
            sic_code=["3571", "5411", "3571", "5411", "5411", "3571"],
            altman_z_score=[1.5, 1.5, 1.81, 1.10, np.nextafter(1.10, 0), np.nan],
        )
    )
    scores = baseline.predict_probabilities(rows)["altman_z_baseline"]
    assert (scores >= np.nextafter(0.5, 1)).tolist() == [True, False, False, False, True, False]
    assert scores[-1] == 0.5


def test_distress_classifier_vs_baselines_and_f2_threshold(splits: dict[str, pd.DataFrame]) -> None:
    """All benchmarks use identical labels; validation-only search returns maximal real F2."""
    train = splits["train"]
    test = splits["test"].dropna(subset=["next_is_distressed"])
    labels = test["next_is_distressed"].astype(int)
    classifier = DistressClassifier().fit(train)
    baselines = BaselineComparisonSuite().fit(train)
    probabilities = classifier.predict_proba(test)
    assert np.all((probabilities >= 0) & (probabilities <= 1))
    validation = train.loc[train["fiscal_year"] == 2021]
    threshold = classifier.optimize_threshold(
        validation, validation["next_is_distressed"].astype(int)
    )
    validation_probabilities = classifier.predict_proba(validation)
    scores = [
        fbeta_score(
            validation["next_is_distressed"],
            validation_probabilities >= cutoff,
            beta=2,
            zero_division=0,
        )
        for cutoff in np.linspace(0.15, 0.85, 71)
    ]
    assert 0.15 <= threshold <= 0.85
    assert (
        fbeta_score(
            validation["next_is_distressed"],
            validation_probabilities >= threshold,
            beta=2,
            zero_division=0,
        )
        >= max(scores) - 0.02
    )
    report = baselines.evaluate(test, labels) | {
        "xgboost": evaluate_binary_classification(labels, probabilities, threshold)
    }
    for metrics in report.values():
        assert set(metrics["confusion_matrix"]) == {"tn", "fp", "fn", "tp"}
        assert sum(metrics["confusion_matrix"].values()) == len(test)
        assert all(0 <= metrics[key] <= 1 for key in ("roc_auc", "pr_auc", "f1_score", "f2_score"))
    assert classifier.scale_pos_weight_ == 3
    assert [classify_risk_level(p) for p in [0, 0.2, 0.5, 0.75, 1]] == [
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        "CRITICAL",
    ]
    for invalid in (-0.1, 1.1, np.nan, np.inf):
        with pytest.raises(ValueError):
            classify_risk_level(invalid)
    with pytest.raises(ModelPipelineError):
        classifier.fit(train.assign(next_is_distressed=1))


def test_tree_shap_explainer_instance_and_global(
    bundle: ModelArtifactBundle, splits: dict[str, pd.DataFrame]
) -> None:
    """Real TreeSHAP contributions reconstruct the fitted model's raw output."""
    test = splits["test"]
    row = test.loc[test["company_id"] == 23].iloc[[0]]
    xgb_classifier = (bundle.candidates or {}).get("xgboost", bundle.classifier)
    explainer = ShapExplainer(xgb_classifier)
    explanation = explainer.explain_instance(row)
    json.dumps(explanation, allow_nan=False)
    assert set(explanation["contributions"]) == set(ML_FEATURE_COLUMNS)
    margin = xgb_classifier.raw_margin_from_features(xgb_classifier.preprocessor.transform(row))[0]
    reconstructed = explanation["base_value"] + sum(explanation["contributions"].values())
    assert reconstructed == pytest.approx(float(margin), abs=1e-5)
    assert expit(reconstructed) == pytest.approx(explanation["distress_probability"], abs=1e-6)
    assert len(explanation["top_drivers"]) == 10
    strengths = [abs(driver["shap_value"]) for driver in explanation["top_drivers"]]
    assert strengths == sorted(strengths, reverse=True)
    global_importance = explainer.compute_global_importance(test)
    assert set(global_importance) == set(ML_FEATURE_COLUMNS)
    assert all(np.isfinite(value) and value >= 0 for value in global_importance.values())


def test_full_pipeline_registry_save_load_and_company_inference(
    bundle: ModelArtifactBundle, splits: dict[str, pd.DataFrame], tmp_path: Path
) -> None:
    """Publish/reload the actual estimators and reproduce forecasts, probabilities, and SHAP."""
    destination = save_bundle(bundle, tmp_path)
    assert (destination / "evaluation_report.json").is_file()
    report = json.loads((destination / "evaluation_report.json").read_text())
    assert report["split_summary"]["max_train_target_year"] <= 2021
    assert report["split_summary"]["train_supervised_rows"] == 48
    restored = load_bundle(destination)
    np.testing.assert_array_equal(
        bundle.classifier.predict_proba(splits["test"]),
        restored.classifier.predict_proba(splits["test"]),
    )
    np.testing.assert_array_equal(
        bundle.forecaster.predict(splits["test"]), restored.forecaster.predict(splits["test"])
    )
    pd.testing.assert_frame_equal(
        bundle.clusterer.transform(splits["test"]), restored.clusterer.transform(splits["test"])
    )
    fixture = (
        Path(__file__).resolve().parents[1] / "fixtures/sec_companyfacts_0000320193_sample.json"
    )
    records = FinancialEtlPipeline().process_company_facts_payload(
        "320193", json.loads(fixture.read_text()), "3571"
    )
    prediction = predict_for_company_records(restored, records)
    json.dumps(prediction, allow_nan=False)
    assert 0 <= prediction["distress_probability"] <= 1
    assert set(prediction["shap_explanations"]["contributions"]) == set(ML_FEATURE_COLUMNS)
    with pytest.raises(ModelPipelineError, match="already exists"):
        save_bundle(bundle, tmp_path)
    model_path = destination / "models.joblib"
    model_path.write_bytes(model_path.read_bytes() + b"corruption")
    with pytest.raises(ModelPipelineError, match="checksum"):
        load_bundle(destination)


def test_labels_metric_edges_and_degenerate_clusters(panel: pd.DataFrame) -> None:
    """Cover observed-label precedence, missingness, one-class AUC, and tiny real PCA fits."""
    signals = pd.DataFrame(
        {
            "is_distressed": [0, np.nan, np.nan],
            "is_bankrupt": [1, 1, np.nan],
            "altman_z_score": [0, 4, 4],
            "roa": [0, 0, -0.1],
            "debt_ratio": [0.2, 0.2, 0.9],
        }
    )
    assert derive_distress_label(signals).tolist() == [0, 1, 1]
    metrics = evaluate_binary_classification([0, 0], [0.1, 0.9])
    assert metrics["roc_auc"] is None
    assert metrics["confusion_matrix"] == {"tn": 1, "fp": 1, "fn": 0, "tp": 0}
    with pytest.raises(ModelPipelineError):
        evaluate_binary_classification([0, 1], [np.nan, 0.9])
    with pytest.raises(ModelPipelineError):
        derive_distress_label(pd.DataFrame({"is_distressed": [0.5]}))
    tiny = FinancialHealthClusterer().fit(panel.iloc[[0]])
    transformed = tiny.transform(panel.iloc[[0]])
    assert transformed["cluster_id"].iloc[0] == 0
    assert transformed["pca_comp_2"].iloc[0] == transformed["pca_comp_3"].iloc[0] == 0
    assert tiny.diagnostics_["silhouette_score"] == 0


def test_publication_cutoff_and_train_only_preprocessing(panel: pd.DataFrame) -> None:
    """Purge targets published after cutoff and reject any held-out influence on learned bounds."""
    dated = panel.copy()
    dated["filed_date"] = pd.to_datetime(dated["fiscal_year"].astype(str) + "-12-31")
    dated.loc[dated["fiscal_year"] == 2021, "filed_date"] = pd.Timestamp("2022-02-01")
    train = TemporalSplitter().split(build_next_period_panel(dated), 2021)["train"]
    purged = training_horizon_rows(train)
    assert purged["next_fiscal_year"].max() == 2020
    assert purged["next_filed_date"].max() <= pd.Timestamp("2021-12-31")
    model = NextPeriodForecaster(n_estimators=5).fit(train)
    bounds = dict(model.preprocessor.winsorizer.bounds_)
    expected = purged["roa"].quantile([0.025, 0.975]).tolist()
    assert bounds["roa"] == pytest.approx(expected)
    model.predict(panel.assign(roa=1e6))
    assert model.preprocessor.winsorizer.bounds_ == bounds


def test_lightgbm_and_random_forest_candidates_and_selection(
    splits: dict[str, pd.DataFrame],
) -> None:
    """Fit LightGBM and Random Forest candidates, explain instances, and select best."""
    from finhealth.ml.distress_classifier import select_best_classifier

    train, test = splits["train"], splits["test"]
    labeled_test = test.dropna(subset=["next_is_distressed"])
    y_test = labeled_test["next_is_distressed"].astype(int)
    candidates = {
        name: DistressClassifier(random_seed=42, model_type=name).fit(train)
        for name in ("xgboost", "lightgbm", "random_forest")
    }
    for name, clf in candidates.items():
        probs = clf.predict_proba(labeled_test)
        assert probs.shape == (len(labeled_test),)
        assert np.all((probs >= 0.0) & (probs <= 1.0))
        explanation = ShapExplainer(clf).explain_instance(labeled_test.iloc[[0]])
        assert set(explanation["contributions"]) == set(ML_FEATURE_COLUMNS)
        if name == "lightgbm":
            margin = clf.raw_margin_from_features(
                clf.preprocessor.transform(labeled_test.iloc[[0]])
            )[0]
            assert explanation["base_value"] + sum(
                explanation["contributions"].values()
            ) == pytest.approx(float(margin), abs=1e-4)
    best_name, best_clf, metrics = select_best_classifier(candidates, labeled_test, y_test)
    assert best_name in candidates
    assert best_clf is candidates[best_name]
    assert set(metrics) == {"xgboost", "lightgbm", "random_forest"}


def test_kaggle_bankruptcy_loader_and_out_of_time_panel(tmp_path: Path) -> None:
    """Load Kaggle schema, guard zero denominators, and align next-period targets."""
    from finhealth.ml.kaggle_loader import load_kaggle_bankruptcy_panel

    csv_path = tmp_path / "kaggle_sample.csv"
    pd.DataFrame(
        [
            {
                "company_name": "C_1",
                "status_label": "alive",
                "year": 2015,
                "X1": 500.0,
                "X6": 40.0,
                "X8": 800.0,
                "X10": 1000.0,
                "X12": 60.0,
                "X14": 250.0,
                "X15": 200.0,
                "X16": 900.0,
                "X17": 400.0,
            },
            {
                "company_name": "C_1",
                "status_label": "alive",
                "year": 2016,
                "X1": 520.0,
                "X6": 50.0,
                "X8": 850.0,
                "X10": 1100.0,
                "X12": 70.0,
                "X14": 260.0,
                "X15": 230.0,
                "X16": 950.0,
                "X17": 420.0,
            },
            {
                "company_name": "C_2",
                "status_label": "failed",
                "year": 2015,
                "X1": 100.0,
                "X6": -30.0,
                "X8": 50.0,
                "X10": 0.0,  # Zero denominator must produce NaN, never inf.
                "X12": -20.0,
                "X14": 0.0,
                "X15": -50.0,
                "X16": 0.0,
                "X17": 0.0,
            },
        ]
    ).to_csv(csv_path, index=False)

    panel = load_kaggle_bankruptcy_panel(csv_path)
    assert len(panel) == 3
    c1_2015 = panel.loc[(panel["cik"] == "C_1") & (panel["fiscal_year"] == 2015)].iloc[0]
    assert c1_2015["roa"] == pytest.approx(0.04)
    assert c1_2015["current_ratio"] == pytest.approx(2.0)
    assert np.isfinite(c1_2015["altman_z_score"])
    assert c1_2015["is_distressed"] == 0

    c2_2015 = panel.loc[panel["cik"] == "C_2"].iloc[0]
    assert pd.isna(c2_2015["roa"])
    assert pd.isna(c2_2015["current_ratio"])
    assert pd.isna(c2_2015["altman_z_score"])
    assert c2_2015["is_distressed"] == 1

    shifted = build_next_period_panel(panel)
    c1_shifted = shifted.loc[(shifted["cik"] == "C_1") & (shifted["fiscal_year"] == 2015)].iloc[0]
    assert c1_shifted["next_fiscal_year"] == 2016
    assert c1_shifted["next_is_distressed"] == 0


@pytest.mark.parametrize("model_type", ["xgboost", "lightgbm", "random_forest"])
def test_smote_balances_training_only_and_is_deterministic(
    splits: dict[str, pd.DataFrame], model_type: str
) -> None:
    """SMOTE must balance training counts without double-weighting or touching held-out data."""
    train, test = splits["train"], splits["test"]
    clf_a = DistressClassifier(
        model_type=model_type,  # type: ignore[arg-type]
        imbalance_strategy="smote",
        random_seed=42,
    ).fit(train)
    clf_b = DistressClassifier(
        model_type=model_type,  # type: ignore[arg-type]
        imbalance_strategy="smote",
        random_seed=42,
    ).fit(train)

    assert clf_a.train_class_counts_before_ is not None
    assert clf_a.train_class_counts_after_ is not None
    assert clf_a.train_class_counts_before_[0] > clf_a.train_class_counts_before_[1]
    assert clf_a.train_class_counts_after_[0] == clf_a.train_class_counts_after_[1]
    assert clf_a.scale_pos_weight_ == pytest.approx(1.0)
    if model_type == "random_forest":
        assert clf_a.params["class_weight"] is None

    labeled_test = test.loc[test["next_is_distressed"].notna()]
    probs_a = clf_a.predict_proba(labeled_test)
    probs_b = clf_b.predict_proba(labeled_test)
    np.testing.assert_allclose(probs_a, probs_b)

    test_labels = labeled_test["next_is_distressed"].astype(int)
    clf_a.fit_calibration(labeled_test, test_labels)
    threshold = clf_a.optimize_threshold(labeled_test, test_labels)
    assert 0.0 < threshold < 1.0


def test_smote_pipeline_end_to_end_and_baseline(panel: pd.DataFrame) -> None:
    """End-to-end pipeline with SMOTE should preserve TreeSHAP and report resampling counts."""
    smote_bundle = train_and_evaluate_pipeline(
        panel, 2021, "test-smote-v1", imbalance_strategy="smote"
    )
    report = smote_bundle.evaluation_report
    assert report["imbalance_strategy"] == "smote"
    assert report["train_class_counts_before"][0] > report["train_class_counts_before"][1]
    assert report["train_class_counts_after"][0] == report["train_class_counts_after"][1]
    assert report["classifier_scale_pos_weight"] == pytest.approx(1.0)
    assert smote_bundle.baselines.imbalance_strategy == "smote"
    assert smote_bundle.baselines.logistic_regression.named_steps["clf"].class_weight is None


def test_smote_edge_cases_and_validation(splits: dict[str, pd.DataFrame]) -> None:
    """Validate error handling for invalid SMOTE config and small minority counts."""
    with pytest.raises(ModelPipelineError, match="Unsupported imbalance_strategy"):
        DistressClassifier(imbalance_strategy="oversample")  # type: ignore[arg-type]

    with pytest.raises(ModelPipelineError, match="smote_k_neighbors must be >= 1"):
        DistressClassifier(imbalance_strategy="smote", smote_k_neighbors=0)

    train = training_horizon_rows(splits["train"])
    negatives = train.loc[train["next_is_distressed"] == 0]
    positives = train.loc[train["next_is_distressed"] == 1]

    single_pos = pd.concat([negatives, positives.iloc[:1]], ignore_index=True)
    with pytest.raises(ModelPipelineError, match="at least 2 samples"):
        DistressClassifier(imbalance_strategy="smote").fit(single_pos)

    small_pos = pd.concat([negatives, positives.iloc[:2]], ignore_index=True)
    clf = DistressClassifier(
        model_type="random_forest", imbalance_strategy="smote", smote_k_neighbors=5
    ).fit(small_pos)
    assert clf.train_class_counts_after_ is not None
    assert clf.train_class_counts_after_[0] == clf.train_class_counts_after_[1]
