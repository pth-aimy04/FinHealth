"""Unit tests for V1.0 Altman Z/Z'/Z'', 5 health pillars, metric catalog, and driver narratives."""

import json
import re

import pytest

from finhealth.api.services_org import classify_bankruptcy_tier, map_pd_to_health_score
from finhealth.etl.altman import (
    FI_UNAVAILABLE_REASON_VI,
    compute_altman_assessment,
    select_altman_variant,
)
from finhealth.etl.corporate_finance import compute_health_pillars, compute_health_pillars_v2
from finhealth.etl.driver_narrative import translate_drivers_to_business
from finhealth.etl.metric_catalog import (
    METRIC_CATALOG,
    METRIC_SPECS,
    PILLAR_SPECS,
    evaluate_metric_status,
)


def _sample_statement() -> dict[str, float]:
    """Balanced manufacturing statement for exact deterministic Altman verification."""
    return {
        "total_assets": 1000.0,
        "current_assets": 450.0,
        "cash_and_equivalents": 150.0,
        "accounts_receivable": 120.0,
        "inventory": 130.0,
        "total_liabilities": 500.0,
        "current_liabilities": 250.0,
        "stockholders_equity": 500.0,
        "retained_earnings": 220.0,
        "revenues": 900.0,
        "cost_of_goods_sold": 600.0,
        "gross_profit": 300.0,
        "operating_income": 120.0,
        "depreciation_amortization": 40.0,
        "ebitda": 160.0,
        "interest_expense": 20.0,
        "net_income": 85.0,
        "operating_cash_flow": 110.0,
        "capex": 30.0,
        "market_value_equity": 1200.0,
    }


def test_altman_all_three_variants_cutoffs_and_fallback() -> None:
    """Verify exact formulas and cutoffs for Z, Z', Z'', listed->Z' fallback, and FI blocking."""
    stmt = _sample_statement()
    # X1 = (450 - 250)/1000 = 0.20
    # X2 = 220/1000 = 0.22
    # X3 = 120/1000 = 0.12
    # X4_mve = 1200/500 = 2.40; X4_bve = 500/500 = 1.00
    # X5 = 900/1000 = 0.90

    z_res = compute_altman_assessment(
        stmt, business_type="manufacturing", listing_status="listed"
    )
    expected_z = 1.2 * 0.20 + 1.4 * 0.22 + 3.3 * 0.12 + 0.6 * 2.40 + 1.0 * 0.90
    assert z_res["applicable"] is True
    assert z_res["variant"] == "Z"
    assert z_res["cutoff_low"] == 1.81
    assert z_res["cutoff_high"] == 2.99
    assert z_res["score"] == pytest.approx(expected_z, abs=1e-4)
    assert z_res["zone"] == "SAFE"
    assert z_res["fallback_note_vi"] is None

    # Fallback Z -> Z' when listed manufacturer lacks market_value_equity
    stmt_no_mve = {k: v for k, v in stmt.items() if k != "market_value_equity"}
    z_prime_fallback = compute_altman_assessment(
        stmt_no_mve, business_type="manufacturing", listing_status="listed"
    )
    expected_z_prime = 0.717 * 0.20 + 0.847 * 0.22 + 3.107 * 0.12 + 0.420 * 1.00 + 0.998 * 0.90
    assert z_prime_fallback["applicable"] is True
    assert z_prime_fallback["variant"] == "Z'"
    assert z_prime_fallback["cutoff_low"] == 1.23
    assert z_prime_fallback["cutoff_high"] == 2.90
    assert z_prime_fallback["score"] == pytest.approx(expected_z_prime, abs=1e-4)
    assert z_prime_fallback["zone"] == "GREY"
    assert z_prime_fallback["fallback_note_vi"] is not None

    # Unlisted manufacturing -> Z' without fallback note
    z_prime_unlisted = compute_altman_assessment(
        stmt, business_type="manufacturing", listing_status="unlisted"
    )
    assert z_prime_unlisted["variant"] == "Z'"
    assert z_prime_unlisted["cutoff_low"] == 1.23
    assert z_prime_unlisted["cutoff_high"] == 2.90
    assert z_prime_unlisted["score"] == pytest.approx(expected_z_prime, abs=1e-4)
    assert z_prime_unlisted["fallback_note_vi"] is None

    # Non-manufacturing -> Z''
    z_double = compute_altman_assessment(
        stmt, business_type="trade_service", listing_status="unlisted"
    )
    expected_z_double = 6.56 * 0.20 + 3.26 * 0.22 + 6.72 * 0.12 + 1.05 * 1.00
    assert z_double["applicable"] is True
    assert z_double["variant"] == "Z''"
    assert z_double["cutoff_low"] == 1.10
    assert z_double["cutoff_high"] == 2.60
    assert z_double["score"] == pytest.approx(expected_z_double, abs=1e-4)
    assert z_double["zone"] == "SAFE"

    # Financial institution -> blocked
    fi_res = compute_altman_assessment(
        stmt, business_type="financial_institution", listing_status="listed"
    )
    assert fi_res["applicable"] is False
    assert fi_res["variant"] is None
    assert fi_res["score"] is None
    assert fi_res["cutoff_low"] is None
    assert fi_res["cutoff_high"] is None
    assert fi_res["unavailable_reason_vi"] == FI_UNAVAILABLE_REASON_VI
    assert select_altman_variant(
        business_type="financial_institution", listing_status="listed", has_market_value=True
    ) == (None, None, None)


def test_metric_catalog_and_five_pillars_negative_equity_penalty() -> None:
    """Confirm 5 pillars, 20 metrics with Vietnamese tooltips, no AAA..CCC, and 0.0 penalty."""
    assert len(PILLAR_SPECS) == 5
    assert len(METRIC_SPECS) == 20
    assert len(METRIC_CATALOG) == 20
    for spec in METRIC_SPECS:
        assert spec.label_vi.strip()
        assert spec.tooltip_vi.strip()
        assert spec.reference_range_vi.strip()

    # Negative equity case: roe and debt_to_equity are None due to equity<=0, must score 0.0
    neg_eq_record = {
        "total_assets": 1000.0,
        "current_assets": 300.0,
        "current_liabilities": 400.0,
        "total_liabilities": 1100.0,
        "stockholders_equity": -100.0,
        "is_negative_equity": True,
        "equity_to_assets": -0.10,
        "debt_ratio": 1.10,
        "debt_to_equity": None,
        "roe": None,
        "roa": -0.08,
        "current_ratio": 0.75,
        "working_capital_ratio": -0.10,
        "retained_earnings_ratio": -0.35,
        "operating_margin": -0.05,
        "ocf_ratio": -0.12,
    }

    v2 = compute_health_pillars_v2(neg_eq_record)
    assert len(v2["pillars"]) == 5
    assert len(v2["metrics"]) == 20
    assert v2["is_negative_equity"] is True
    assert "overall_grade" not in v2
    assert v2["overall_status"] in ("STRONG", "ADEQUATE", "WEAK", "CRITICAL", "UNAVAILABLE")

    metrics_by_key = {item["key"]: item for item in v2["metrics"]}
    assert metrics_by_key["roe"]["score"] == 0.0
    assert metrics_by_key["roe"]["status"] == "CRITICAL"
    assert metrics_by_key["equity_to_assets"]["score"] == 0.0
    assert metrics_by_key["equity_to_assets"]["status"] == "CRITICAL"
    assert evaluate_metric_status("roe", None, is_negative_equity=True) == "CRITICAL"

    # Legacy 4-pillar function must also penalize None debt_to_equity & roe to 0.0 when neg equity
    legacy = compute_health_pillars(neg_eq_record)
    assert legacy["pillars"]["solvency"]["observed_metrics"] >= 3
    assert legacy["pillars"]["profitability"]["observed_metrics"] >= 3
    assert legacy["pillars"]["solvency"]["status"] == "CRITICAL"


def test_driver_narrative_limits_share_sum_and_zero_ml_jargon() -> None:
    """Ensure <=5 Strengths & <=5 Bottlenecks, 100% impact share sum, and zero ML jargon."""
    contributions = {
        "debt_ratio": 0.85,
        "short_term_debt_share": 0.42,
        "debt_ratio_yoy_delta": 0.31,
        "is_negative_equity": 0.25,
        "opex_to_revenue": 0.18,
        "receivables_to_revenue": 0.11,
        "roa": -0.60,
        "gross_margin": -0.45,
        "current_ratio": -0.33,
        "working_capital_ratio": -0.22,
        "ocf_ratio_yoy_delta": -0.14,
        "asset_turnover": -0.09,
    }
    record = {
        "debt_ratio": 0.84,
        "short_term_debt_share": 0.78,
        "debt_ratio_yoy_delta": 0.09,
        "is_negative_equity": 1.0,
        "opex_to_revenue": 0.34,
        "receivables_to_revenue": 0.29,
        "roa": 0.07,
        "gross_margin": 0.28,
        "current_ratio": 1.65,
        "working_capital_ratio": 0.18,
        "ocf_ratio_yoy_delta": 0.04,
        "asset_turnover": 0.95,
    }
    shap_payload = {
        "output_space": "log_odds",
        "base_value": -4.2,
        "model_name": "xgboost",
        "contributions": contributions,
        "fitted_inputs": record,
    }

    result = translate_drivers_to_business(shap_payload, record)
    assert len(result["strengths"]) == 5
    assert len(result["bottlenecks"]) == 5
    assert result["total_impact_share_pct"] == pytest.approx(100.0, abs=0.1)

    tech_sum = sum(
        item["impact_share_pct"] for item in result["technical_attribution"]["features"]
    )
    assert tech_sum == pytest.approx(100.0, abs=0.1)

    customer_blob = json.dumps(
        {"strengths": result["strengths"], "bottlenecks": result["bottlenecks"]},
        ensure_ascii=False,
    )
    forbidden_patterns = (
        r"\bSHAP\b",
        r"shap_value",
        r"log[-_]odds",
        r"XGBoost",
        r"Random Forest",
        r"LightGBM",
        r"_yoy_delta",
        r"\bAAA\b",
        r"\bCCC\b",
        r"giảm\s+\d+[\.,]?\d*\s+điểm\s+sức\s+khỏe",
    )
    for pattern in forbidden_patterns:
        assert re.search(pattern, customer_blob, flags=re.IGNORECASE) is None, (
            f"Forbidden jargon matched: {pattern}"
        )


def test_pd_to_health_score_monotonic_and_tier_aligned() -> None:
    """Verify strict monotonicity of map_pd_to_health_score and 1-1 risk tier boundaries."""
    grid = [0.0, 0.002, 0.0099, 0.01, 0.02, 0.0299, 0.03, 0.05, 0.0799, 0.08, 0.20, 0.50, 1.0]
    scores = [map_pd_to_health_score(p) for p in grid]
    for left, right in zip(scores, scores[1:], strict=False):
        assert left > right

    assert classify_bankruptcy_tier(0.005) == "STRONG"
    assert map_pd_to_health_score(0.005) >= 80.0
    assert classify_bankruptcy_tier(0.02) == "STABLE"
    assert 60.0 <= map_pd_to_health_score(0.02) < 80.0
    assert classify_bankruptcy_tier(0.05) == "WATCH"
    assert 35.0 <= map_pd_to_health_score(0.05) < 60.0
    assert classify_bankruptcy_tier(0.15) == "CRITICAL"
    assert 0.0 <= map_pd_to_health_score(0.15) < 35.0
