"""Comprehensive tests for the V1.0 leakage-free ML bankruptcy engine (T08, T09, T10)."""

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from finhealth.core.exceptions import ModelPipelineError
from finhealth.ml.confidence import (
    apply_cash_flow_overlay,
    assess_confidence,
    classify_bankruptcy_tier,
    map_pd_to_health_score,
)
from finhealth.ml.distress_classifier import ALL_MODEL_TYPES
from finhealth.ml.explainer import ShapExplainer
from finhealth.ml.feature_contracts import (
    CORE_BANKRUPTCY_FEATURES,
    MULTI_PERIOD_FEATURES,
    YOY_DELTA_FEATURES,
    assert_scale_free_features,
)
from finhealth.ml.kaggle_loader import (
    compute_scale_free_features_from_statements,
    load_kaggle_bankruptcy_panel,
)
from finhealth.ml.registry import (
    ModelArtifactBundle,
    ModelRegistryState,
    load_bundle,
    save_bundle,
    score_company_bankruptcy,
    train_and_evaluate_kaggle_v2_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
KAGGLE_CSV = REPO_ROOT / "data" / "raw" / "kaggle" / "american_bankruptcy.csv"
V2_BUNDLE_DIR = REPO_ROOT / "data" / "artifacts" / "models" / "v2.0.0-kaggle"


def _make_synthetic_bankruptcy_panel(n_companies: int = 80) -> pd.DataFrame:
    """Build a deterministic synthetic Kaggle-like panel spanning 2012-2018 for fast unit tests."""
    rng = np.random.default_rng(42)
    rows: list[dict[str, Any]] = []
    for idx in range(n_companies):
        cik = f"SYN_{idx:03d}"
        # Assign some companies to fail in Train (<=2014), Val (2015-2016), and Test (2017-2018).
        if idx < 10:
            status = "failed"
            end_year = 2014
        elif idx < 16:
            status = "failed"
            end_year = 2015 if idx % 2 == 0 else 2016
        elif idx < 22:
            status = "failed"
            end_year = 2017 if idx % 2 == 0 else 2018
        else:
            status = "alive"
            end_year = 2018
        for year in range(2012, end_year + 1):
            distress = status == "failed" and year == end_year
            scale = 1_000.0 * (1.0 + 0.05 * (year - 2012)) * (1.0 + 0.02 * idx)
            assets = scale
            liab_ratio = (0.92 if distress else 0.42) + float(rng.normal(0, 0.03))
            liab = max(0.05 * assets, assets * liab_ratio)
            curr_assets = assets * (0.20 if distress else 0.48)
            curr_liab = liab * (0.65 if distress else 0.35)
            revenues = assets * (0.55 if distress else 1.15)
            cogs = revenues * (0.85 if distress else 0.62)
            gross_profit = revenues - cogs
            opex = revenues * (0.98 if distress else 0.80)
            depreciation = assets * 0.04
            ebit = revenues * (-0.12 if distress else 0.14)
            ebitda = ebit + depreciation
            net_income = assets * (-0.15 if distress else 0.09)
            inventory = curr_assets * 0.30
            receivables = revenues * 0.12
            retained = assets * (-0.25 if distress else 0.25)
            lt_debt = max(0.0, liab - curr_liab)
            rows.append(
                {
                    "company_name": cik,
                    "status_label": status,
                    "year": year,
                    "X1": curr_assets,
                    "X2": cogs,
                    "X3": depreciation,
                    "X4": ebitda,
                    "X5": inventory,
                    "X6": net_income,
                    "X7": receivables,
                    "X8": max(1.0, (assets - liab) * 1.5),
                    "X9": revenues,
                    "X10": assets,
                    "X11": lt_debt,
                    "X12": ebit,
                    "X13": gross_profit,
                    "X14": curr_liab,
                    "X15": retained,
                    "X16": revenues,
                    "X17": liab,
                    "X18": opex,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def synthetic_v2_bundle(tmp_path_factory: pytest.TempPathFactory) -> ModelArtifactBundle:
    """Train a fast v2 bundle on synthetic Kaggle-format data for deterministic unit tests."""
    tmp_dir = tmp_path_factory.mktemp("kaggle_v2_syn")
    csv_path = tmp_dir / "synthetic_kaggle.csv"
    _make_synthetic_bankruptcy_panel().to_csv(csv_path, index=False)
    panel = load_kaggle_bankruptcy_panel(csv_path)
    return train_and_evaluate_kaggle_v2_pipeline(
        panel,
        train_end_year=2014,
        model_version="v2.0.0-syn",
        random_seed=42,
        validation_end_year=2016,
    )


def test_kaggle_loader_zero_leakage_and_exact_splits_on_real_csv() -> None:
    """Prove 0% look-ahead and 0% entity leakage on american_bankruptcy.csv."""
    if not KAGGLE_CSV.exists():
        pytest.skip("american_bankruptcy.csv not present")
    panel = load_kaggle_bankruptcy_panel(KAGGLE_CSV)

    assert len(panel) == 78_682
    assert int(panel["next_is_bankrupt"].sum()) == 609

    # Every failed company must have exactly 1 positive row at year == max_year.
    failed = panel.loc[panel["status_label"].str.lower() == "failed"]
    assert failed["cik"].nunique() == 609
    per_company_pos = failed.groupby("cik")["next_is_bankrupt"].sum()
    assert (per_company_pos == 1).all()

    max_years = failed.groupby("cik")["fiscal_year"].transform("max")
    assert (failed.loc[failed["fiscal_year"] < max_years, "next_is_bankrupt"] == 0).all()
    assert (failed.loc[failed["fiscal_year"] == max_years, "next_is_bankrupt"] == 1).all()

    alive = panel.loc[panel["status_label"].str.lower() == "alive"]
    assert (alive["next_is_bankrupt"] == 0).all()

    # Exact out-of-time positive counts and 0% positive-company entity overlap.
    train = panel.loc[panel["fiscal_year"] <= 2014]
    val = panel.loc[panel["fiscal_year"].between(2015, 2016)]
    test = panel.loc[panel["fiscal_year"] >= 2017]
    assert int(train["next_is_bankrupt"].sum()) == 490
    assert int(val["next_is_bankrupt"].sum()) == 62
    assert int(test["next_is_bankrupt"].sum()) == 57

    train_val_pos = set(train.loc[train["next_is_bankrupt"] == 1, "cik"]) | set(
        val.loc[val["next_is_bankrupt"] == 1, "cik"]
    )
    test_pos = set(test.loc[test["next_is_bankrupt"] == 1, "cik"])
    assert train_val_pos.isdisjoint(test_pos)

    # All 19 core + 5 YoY features present, scale-free contract verified.
    assert len(CORE_BANKRUPTCY_FEATURES) == 19
    assert len(YOY_DELTA_FEATURES) == 5
    assert all(col in panel.columns for col in MULTI_PERIOD_FEATURES)
    assert "eps" not in MULTI_PERIOD_FEATURES
    assert "X8" not in MULTI_PERIOD_FEATURES
    assert "market_value_equity" not in MULTI_PERIOD_FEATURES


def test_scale_free_feature_contract_and_negative_equity(tmp_path: Path) -> None:
    """Reject currency-dependent features and preserve finite ratios under negative equity."""
    assert_scale_free_features(CORE_BANKRUPTCY_FEATURES)
    assert_scale_free_features(MULTI_PERIOD_FEATURES)
    for forbidden in ("eps", "X8", "market_value_equity", "total_assets", "revenues"):
        with pytest.raises(ValueError, match="Scale-dependent"):
            assert_scale_free_features([*CORE_BANKRUPTCY_FEATURES, forbidden])

    neg_eq = pd.DataFrame(
        [
            {
                "cik": "NEG_1",
                "fiscal_year": 2023,
                "total_assets": 100.0,
                "total_liabilities": 130.0,
                "stockholders_equity": -30.0,
                "current_assets": 30.0,
                "current_liabilities": 60.0,
                "inventory": 10.0,
                "accounts_receivable": 10.0,
                "long_term_debt": 70.0,
                "retained_earnings": -50.0,
                "revenues": 80.0,
                "gross_profit": 20.0,
                "operating_expenses": 75.0,
                "operating_income": -10.0,
                "depreciation_amortization": 5.0,
                "ebitda": -5.0,
                "net_income": -18.0,
            }
        ]
    )
    feats = compute_scale_free_features_from_statements(neg_eq).iloc[0]
    assert feats["is_negative_equity"] == 1.0
    assert feats["equity_to_assets"] == pytest.approx(-0.30)
    assert np.isfinite(feats["equity_to_assets"])
    assert feats["debt_ratio"] == pytest.approx(1.30)
    assert feats["short_term_debt_share"] == pytest.approx(60.0 / 130.0)


def test_pd_tier_and_health_score_strict_monotonicity() -> None:
    """Health score must decrease strictly monotonically on [0, 1] and align 1-to-1 with tiers."""
    grid = np.linspace(0.0, 1.0, 1001)
    scores = [map_pd_to_health_score(float(p)) for p in grid]
    assert scores[0] == 100.0
    assert scores[-1] == 0.0
    for idx in range(len(scores) - 1):
        assert scores[idx] > scores[idx + 1], (
            f"Non-monotonic at pd={grid[idx]:.4f}->{grid[idx + 1]:.4f}: "
            f"{scores[idx]} -> {scores[idx + 1]}"
        )

    # Verify exact tier thresholds and score band alignment.
    assert classify_bankruptcy_tier(0.0) == "STRONG"
    assert classify_bankruptcy_tier(0.0099) == "STRONG"
    assert map_pd_to_health_score(0.0099) > 80.0

    assert classify_bankruptcy_tier(0.01) == "STABLE"
    assert map_pd_to_health_score(0.01) == 80.0
    assert classify_bankruptcy_tier(0.0299) == "STABLE"
    assert 60.0 < map_pd_to_health_score(0.0299) < 80.0

    assert classify_bankruptcy_tier(0.03) == "WATCH"
    assert map_pd_to_health_score(0.03) == 60.0
    assert classify_bankruptcy_tier(0.0799) == "WATCH"
    assert 35.0 < map_pd_to_health_score(0.0799) < 60.0

    assert classify_bankruptcy_tier(0.08) == "CRITICAL"
    assert map_pd_to_health_score(0.08) == 35.0
    assert classify_bankruptcy_tier(1.0) == "CRITICAL"

    for invalid in (-0.001, 1.001, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            classify_bankruptcy_tier(invalid)
        with pytest.raises(ValueError):
            map_pd_to_health_score(invalid)


def test_four_model_platt_calibration_and_dual_mode_scoring(
    synthetic_v2_bundle: ModelArtifactBundle,
) -> None:
    """All 4 models must be Platt-calibrated for both single_period and multi_period modes."""
    assert synthetic_v2_bundle.scoring_contract == "scale_free_v2"
    assert synthetic_v2_bundle.single_period_candidates is not None
    assert synthetic_v2_bundle.multi_period_candidates is not None

    for mode_candidates in (
        synthetic_v2_bundle.single_period_candidates,
        synthetic_v2_bundle.multi_period_candidates,
    ):
        assert set(mode_candidates) == set(ALL_MODEL_TYPES)
        for name, clf in mode_candidates.items():
            assert clf.calibration_ is not None, f"{name} missing Platt calibration"
            slope, intercept = clf.calibration_
            assert np.isfinite(slope) and np.isfinite(intercept) and slope > 0

    # Verify automatic single_period vs multi_period mode selection.
    one_year = [
        {
            "cik": "CO_1",
            "fiscal_year": 2023,
            "total_assets": 1000.0,
            "current_assets": 450.0,
            "total_liabilities": 400.0,
            "current_liabilities": 150.0,
            "stockholders_equity": 600.0,
            "retained_earnings": 250.0,
            "revenues": 1100.0,
            "gross_profit": 420.0,
            "operating_expenses": 880.0,
            "operating_income": 150.0,
            "depreciation_amortization": 40.0,
            "ebitda": 190.0,
            "net_income": 95.0,
            "inventory": 120.0,
            "accounts_receivable": 130.0,
            "long_term_debt": 250.0,
        }
    ]
    two_years = [
        {**one_year[0], "fiscal_year": 2022, "revenues": 1000.0, "net_income": 85.0},
        one_year[0],
    ]
    single_res = score_company_bankruptcy(synthetic_v2_bundle, one_year)
    multi_res = score_company_bankruptcy(synthetic_v2_bundle, two_years)
    assert single_res.scoring_mode == "single_period"
    assert multi_res.scoring_mode == "multi_period"
    assert set(single_res.model_probabilities) == set(ALL_MODEL_TYPES)
    assert set(multi_res.model_probabilities) == set(ALL_MODEL_TYPES)
    assert single_res.shap_explanation["output_space"] in {"log_odds", "probability"}
    assert single_res.shap_explanation["model_name"] in {"xgboost", "lightgbm", "random_forest"}


def test_currency_scale_invariance_usd_vs_vnd(
    synthetic_v2_bundle: ModelArtifactBundle,
) -> None:
    """Multiplying all financial statement items by 25,000 or 1,000,000 must not change outputs."""
    monetary_fields = (
        "total_assets",
        "current_assets",
        "total_liabilities",
        "current_liabilities",
        "stockholders_equity",
        "retained_earnings",
        "revenues",
        "gross_profit",
        "operating_expenses",
        "operating_income",
        "depreciation_amortization",
        "ebitda",
        "net_income",
        "inventory",
        "accounts_receivable",
        "long_term_debt",
    )
    base_records = [
        {
            "cik": "CUR_1",
            "fiscal_year": 2022,
            "total_assets": 900.0,
            "current_assets": 400.0,
            "total_liabilities": 380.0,
            "current_liabilities": 140.0,
            "stockholders_equity": 520.0,
            "retained_earnings": 210.0,
            "revenues": 980.0,
            "gross_profit": 370.0,
            "operating_expenses": 790.0,
            "operating_income": 130.0,
            "depreciation_amortization": 36.0,
            "ebitda": 166.0,
            "net_income": 80.0,
            "inventory": 110.0,
            "accounts_receivable": 115.0,
            "long_term_debt": 240.0,
        },
        {
            "cik": "CUR_1",
            "fiscal_year": 2023,
            "total_assets": 1000.0,
            "current_assets": 450.0,
            "total_liabilities": 410.0,
            "current_liabilities": 155.0,
            "stockholders_equity": 590.0,
            "retained_earnings": 260.0,
            "revenues": 1120.0,
            "gross_profit": 430.0,
            "operating_expenses": 890.0,
            "operating_income": 155.0,
            "depreciation_amortization": 40.0,
            "ebitda": 195.0,
            "net_income": 98.0,
            "inventory": 125.0,
            "accounts_receivable": 135.0,
            "long_term_debt": 255.0,
        },
    ]
    base_result = score_company_bankruptcy(synthetic_v2_bundle, base_records)
    for multiplier in (25_000.0, 1_000_000.0):
        scaled = [
            {
                k: (v * multiplier if k in monetary_fields else v)
                for k, v in row.items()
            }
            for row in base_records
        ]
        scaled_result = score_company_bankruptcy(synthetic_v2_bundle, scaled)
        assert scaled_result.scoring_mode == base_result.scoring_mode == "multi_period"
        assert abs(scaled_result.pd_12m - base_result.pd_12m) < 1e-9
        assert abs(scaled_result.health_score - base_result.health_score) < 1e-9
        assert scaled_result.risk_tier == base_result.risk_tier
        assert [d["feature"] for d in scaled_result.shap_explanation["top_drivers"]] == [
            d["feature"] for d in base_result.shap_explanation["top_drivers"]
        ]


def test_four_layer_confidence_and_cash_flow_overlay() -> None:
    """Verify all 4 confidence layers and Cash-Flow Overlay escalation rules."""
    full_features = {col: 0.2 for col in CORE_BANKRUPTCY_FEATURES}
    bounds = {col: [0.0, 1.0] for col in CORE_BANKRUPTCY_FEATURES}
    tight_probs = {
        "logistic_regression": 0.015,
        "random_forest": 0.018,
        "xgboost": 0.016,
        "lightgbm": 0.017,
    }

    # Clean case -> HIGH confidence.
    high = assess_confidence(
        full_features,
        feature_ood_bounds=bounds,
        model_probabilities=tight_probs,
        audit_status="audited_unqualified",
    )
    assert high.level == "HIGH"
    assert high.input_completeness == 1.0
    assert not high.is_ood

    # Layer 1: <70% completeness -> LOW.
    sparse = {col: 0.2 for col in CORE_BANKRUPTCY_FEATURES[:10]}
    low_comp = assess_confidence(sparse, feature_ood_bounds=bounds, model_probabilities=tight_probs)
    assert low_comp.level == "LOW"
    assert low_comp.input_completeness < 0.70

    # Layer 1: 70%-90% completeness -> MODERATE.
    partial = {col: 0.2 for col in CORE_BANKRUPTCY_FEATURES[:15]}
    mod_comp = assess_confidence(
        partial, feature_ood_bounds=bounds, model_probabilities=tight_probs
    )
    assert mod_comp.level == "MODERATE"

    # Layer 2: >=3 OOD features -> downgrade from HIGH to MODERATE.
    ood_feats = {**full_features, "roa": 5.0, "debt_ratio": 9.0, "current_ratio": 50.0}
    ood_res = assess_confidence(
        ood_feats, feature_ood_bounds=bounds, model_probabilities=tight_probs
    )
    assert ood_res.is_ood
    assert len(ood_res.ood_features) == 3
    assert ood_res.level == "MODERATE"

    # Layer 3: high ensemble spread (>0.08) -> downgrade.
    spread_probs = {
        "logistic_regression": 0.01,
        "random_forest": 0.14,
        "xgboost": 0.02,
        "lightgbm": 0.03,
    }
    spread_res = assess_confidence(
        full_features, feature_ood_bounds=bounds, model_probabilities=spread_probs
    )
    assert spread_res.ensemble_spread == pytest.approx(0.13)
    assert spread_res.level == "MODERATE"

    # Layer 4: unaudited -> max MODERATE; adverse/disclaimer -> LOW.
    unaudited = assess_confidence(
        full_features,
        feature_ood_bounds=bounds,
        model_probabilities=tight_probs,
        audit_status="unaudited",
    )
    assert unaudited.level == "MODERATE"
    adverse = assess_confidence(
        full_features,
        feature_ood_bounds=bounds,
        model_probabilities=tight_probs,
        audit_status="audited_adverse_disclaimer",
    )
    assert adverse.level == "LOW"

    # Cash-Flow Overlay: escalates STRONG/STABLE to WATCH without altering CRITICAL.
    no_trigger = apply_cash_flow_overlay(
        "STRONG",
        negative_ocf_streak=1,
        interest_coverage=3.0,
        operating_cash_flow=10.0,
    )
    assert not no_trigger.triggered
    assert no_trigger.adjusted_tier == "STRONG"

    streak_trigger = apply_cash_flow_overlay("STRONG", negative_ocf_streak=2)
    assert streak_trigger.triggered
    assert "NEGATIVE_OCF_STREAK" in streak_trigger.flags
    assert streak_trigger.adjusted_tier == "WATCH"

    ic_trigger = apply_cash_flow_overlay(
        "STABLE", interest_coverage=0.5, operating_cash_flow=-100.0
    )
    assert ic_trigger.triggered
    assert "WEAK_INTEREST_COVERAGE_NEGATIVE_OCF" in ic_trigger.flags
    assert ic_trigger.adjusted_tier == "WATCH"

    crit_keep = apply_cash_flow_overlay("CRITICAL", negative_ocf_streak=3)
    assert crit_keep.triggered
    assert crit_keep.adjusted_tier == "CRITICAL"


def test_tree_shap_reconstruction_and_output_space(
    synthetic_v2_bundle: ModelArtifactBundle,
) -> None:
    """TreeSHAP reconstruction error must be < 1e-5 and output_space accurate per model."""
    assert synthetic_v2_bundle.single_period_candidates is not None
    df_row = pd.DataFrame([{col: 0.15 for col in CORE_BANKRUPTCY_FEATURES}])
    for model_name, expected_space in (
        ("xgboost", "log_odds"),
        ("lightgbm", "log_odds"),
        ("random_forest", "probability"),
    ):
        clf = synthetic_v2_bundle.single_period_candidates[model_name]
        explainer = ShapExplainer(clf)
        assert explainer.output_space == expected_space
        assert explainer.verify_reconstruction_error(df_row) < 1e-5
        exp = explainer.explain_instance(df_row)
        assert exp["output_space"] == expected_space
        assert exp["model_name"] == model_name

    lr_clf = synthetic_v2_bundle.single_period_candidates["logistic_regression"]
    with pytest.raises(ModelPipelineError, match="TreeSHAP requires a fitted tree classifier"):
        ShapExplainer(lr_clf)


def test_multi_worker_registry_reloads_on_latest_json_change(
    synthetic_v2_bundle: ModelArtifactBundle, tmp_path: Path
) -> None:
    """ModelRegistryState must reload automatically when latest.json mtime/sha256 changes."""
    bundle_a = ModelArtifactBundle(
        **{**synthetic_v2_bundle.__dict__, "model_version": "v2.0.0-a"}
    )
    bundle_b = ModelArtifactBundle(
        **{**synthetic_v2_bundle.__dict__, "model_version": "v2.0.0-b"}
    )
    save_bundle(bundle_a, tmp_path)
    save_bundle(bundle_b, tmp_path)

    pointer = tmp_path / "latest.json"
    pointer.write_text(
        json.dumps({"model_version": "v2.0.0-a", "bundle_dir": "v2.0.0-a"}),
        encoding="utf-8",
    )
    state = ModelRegistryState()
    state.initialize(tmp_path)
    active_a = state.get()
    assert active_a is not None and active_a.model_version == "v2.0.0-a"

    # Simulate another worker publishing v2.0.0-b atomically.
    time.sleep(0.02)
    pointer.write_text(
        json.dumps({"model_version": "v2.0.0-b", "bundle_dir": "v2.0.0-b"}),
        encoding="utf-8",
    )
    active_b = state.get()
    assert active_b is not None and active_b.model_version == "v2.0.0-b"


def test_published_v2_kaggle_artifact_provenance_and_invariance() -> None:
    """Verify the real published v2.0.0-kaggle artifact bundle meets all T10 criteria."""
    if not V2_BUNDLE_DIR.exists():
        pytest.skip("v2.0.0-kaggle artifact not yet published")

    report = json.loads((V2_BUNDLE_DIR / "evaluation_report.json").read_text(encoding="utf-8"))
    report_text = json.dumps(report)
    assert "synthetic stochastic outcomes" not in report_text.lower()
    assert report["scoring_contract"] == "scale_free_v2"
    assert report["split_summary"]["non_forward_supervised_rows"] == 0
    assert report["split_summary"]["entity_leakage_positive_overlap"] == 0
    assert report["split_summary"]["total_positive_rows"] == 609
    assert report["split_summary"]["train_positive_rows"] == 490
    assert report["split_summary"]["validation_positive_rows"] == 62
    assert report["split_summary"]["test_positive_rows"] == 57
    assert report["shap_margin_max_abs_error"] < 1e-5
    assert report["shap_single_period_max_abs_error"] < 1e-5

    # All 4 models calibrated with realistic Brier scores (< 0.05 on ~1% base rate).
    for mode_key in ("classification_single_period", "classification_multi_period"):
        for model_name in ALL_MODEL_TYPES:
            metrics = report[mode_key][model_name]
            assert metrics["brier_score"] < 0.05, f"{mode_key}/{model_name} uncalibrated Brier"
            assert metrics["mean_probability"] < 0.10, f"{mode_key}/{model_name} uncalibrated mean"

    benchmark_md = (V2_BUNDLE_DIR / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")
    assert "synthetic stochastic outcomes" not in benchmark_md.lower()
    assert "Kaggle US Company Bankruptcy dataset" in benchmark_md

    # Load real bundle and prove currency invariance (< 1e-9).
    bundle = load_bundle(V2_BUNDLE_DIR)
    sample = [
        {
            "cik": "REAL_INV",
            "fiscal_year": 2023,
            "total_assets": 500.0,
            "current_assets": 220.0,
            "total_liabilities": 210.0,
            "current_liabilities": 85.0,
            "stockholders_equity": 290.0,
            "retained_earnings": 120.0,
            "revenues": 610.0,
            "gross_profit": 230.0,
            "operating_expenses": 490.0,
            "operating_income": 85.0,
            "depreciation_amortization": 22.0,
            "ebitda": 107.0,
            "net_income": 52.0,
            "inventory": 60.0,
            "accounts_receivable": 75.0,
            "long_term_debt": 125.0,
        }
    ]
    res_usd = score_company_bankruptcy(bundle, sample)
    res_vnd = score_company_bankruptcy(
        bundle,
        [
            {
                k: (v * 25_000.0 if isinstance(v, float) else v)
                for k, v in sample[0].items()
            }
        ],
    )
    assert abs(res_usd.pd_12m - res_vnd.pd_12m) < 1e-9
    assert abs(res_usd.health_score - res_vnd.health_score) < 1e-9
    assert res_usd.risk_tier == res_vnd.risk_tier
