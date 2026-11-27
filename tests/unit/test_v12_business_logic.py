"""Independent accounting checks for the Stage 9 analytical layer."""

from datetime import date
from math import fsum
from typing import Any

import pytest

from finhealth.etl.corporate_finance import (
    COMPOSITE_METRICS,
    CompositeBenchmark,
    compute_accounting_checklist,
    compute_dupont,
    compute_health_pillars,
    compute_quality_of_earnings,
    generate_actionable_recommendations,
)
from finhealth.etl.financial_ratios import compute_statement_ratios


@pytest.fixture
def apple() -> list[dict[str, Any]]:
    """Use the selected annual Apple facts from the audited FY2023–FY2025 panel."""
    rows = []
    for year, end, filed, assets, equity, sales, income, cash in (
        (2023, 30, date(2023, 11, 3), 352583, 62146, 383285, 96995, 110543),
        (2024, 28, date(2024, 11, 1), 364980, 56950, 391035, 93736, 118254),
        (2025, 27, date(2025, 10, 31), 359241, 73733, 416161, 112010, 111482),
    ):
        row = {
            "form_type": "10-K",
            "fiscal_year": year,
            "filed_date": filed,
            "period_end_date": date(year, 9, end),
            "total_assets": assets * 1e6,
            "stockholders_equity": equity * 1e6,
            "revenues": sales * 1e6,
            "net_income": income * 1e6,
            "operating_cash_flow": cash * 1e6,
        }
        rows.append(row | compute_statement_ratios(row))
    return rows


def test_dupont_identity_and_shapley_bridge_exact_reconciliation(
    apple: list[dict[str, Any]],
) -> None:
    """Reconcile actual Apple ROE and compare symmetric effects to a closed-form calculation."""
    result = compute_dupont(apple)
    prior = compute_dupont(apple[:2])
    factors = ("net_profit_margin", "asset_turnover_avg", "equity_multiplier_avg")
    a, b, c = (prior[key] for key in factors)
    x, y, z = (result[key] for key in factors)
    expected = 112010 / ((56950 + 73733) / 2)
    assert abs(expected - result["roe_dupont_avg"]) < 1e-12
    assert abs(x * y * z - result["roe_dupont_avg"]) < 1e-12
    assert result["roe_ending_equity"] < prior["roe_ending_equity"]
    assert result["roe_dupont_avg"] > prior["roe_dupont_avg"]
    bridge = result["bridge"]
    estimates = {
        "margin_contribution": (x - a) * (b * c / 3 + (b * z + y * c) / 6 + y * z / 3),
        "turnover_contribution": (y - b) * (a * c / 3 + (a * z + x * c) / 6 + x * z / 3),
        "leverage_contribution": (z - c) * (a * b / 3 + (a * y + x * b) / 6 + x * y / 3),
    }
    for key, value in estimates.items():
        assert abs(bridge[key] - value) < 1e-12
    assert abs(fsum(bridge[key] for key in estimates) - bridge["delta_roe_dupont_avg"]) < 1e-12


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"stockholders_equity": -1}, "missing_or_insufficient_equity"),
        ({"stockholders_equity": 1}, "missing_or_insufficient_equity"),
        ({"fiscal_year": 2026}, "nonconsecutive_fiscal_year"),
        ({"filed_date": date(2024, 11, 1)}, "non_forward_publication"),
    ],
)
def test_dupont_rejects_invalid_comparatives(
    apple: list[dict[str, Any]], change: dict[str, Any], reason: str
) -> None:
    """A broken comparative pair should withhold average-asset DuPont and the bridge."""
    result = compute_dupont([*apple[:-1], apple[-1] | change])
    assert result["roe_dupont_avg"] is None and result["bridge"] is None
    assert result["reason"] == reason


def test_quality_of_earnings_accruals_and_evidence_gated_checklist(
    apple: list[dict[str, Any]],
) -> None:
    """Check the cash-flow arithmetic, a real loss, and unavailable year-over-year inputs."""
    current, prior = apple[-1], apple[-2]
    quality = compute_quality_of_earnings(current, prior)
    assert quality["cash_conversion_qoe"] == pytest.approx(111482 / 112010)
    assert quality["accrual_gap_usd"] == 528e6
    assert quality["cash_flow_accruals_ratio"] == pytest.approx(528 / ((364980 + 359241) / 2))
    assert quality["accruals_basis"] == "average_assets"
    loss = current | {"net_income": -10e9}
    quality = compute_quality_of_earnings(loss, None)
    assert quality["cash_conversion_qoe"] is None
    assert quality["cash_conversion_reason"] == "non_positive_net_income"
    assert quality["accruals_basis"] == "ending_assets"
    assert quality["accruals_flag"] == "CASH_BACKED_EARNINGS"
    warning = compute_quality_of_earnings(current | {"operating_cash_flow": 0}, prior)
    assert warning["accruals_flag"] == "EARNINGS_AHEAD_OF_CASH_WARNING"
    loss_dupont = compute_dupont([*apple[:-1], loss])
    assert loss_dupont["roe_dupont_avg"] == pytest.approx(-10000 / ((56950 + 73733) / 2))
    bridge = loss_dupont["bridge"]
    assert (
        abs(
            fsum(
                bridge[name]
                for name in (
                    "margin_contribution",
                    "turnover_contribution",
                    "leverage_contribution",
                )
            )
            - bridge["delta_roe_dupont_avg"]
        )
        < 1e-12
    )
    checklist = compute_accounting_checklist(current, None)
    assert len(checklist["signals"]) == 8
    assert (checklist["observed_passes"], checklist["observed_checks"]) == (2, 3)
    assert checklist["pass_ratio"] == pytest.approx(2 / 3)
    assert checklist["signals"]["cash_exceeds_net_income"]["status"] == "FAIL"
    assert checklist["signals"]["improving_roa"]["status"] == "UNAVAILABLE"
    assert checklist["signals"]["improving_roa"]["reason"] == "missing_prior_annual"


def test_composite_health_score_monotonicity_and_cohort_consistency() -> None:
    """Rank one complete cohort with midpoint ties and no per-metric imputation."""
    rows = [
        {"sector": "Manufacturing", **dict.fromkeys(COMPOSITE_METRICS, index / 10)}
        for index in range(10)
    ]
    incomplete = rows[0] | {"roa": 100, "ocf_ratio": None}
    benchmark = CompositeBenchmark.from_rows([*rows, incomplete, rows[0] | {"sector": "Mining"}])
    current = rows[5]
    result = benchmark.score(current, current["sector"])
    assert result["cohort_scope"] == "sector" and result["cohort_size"] == 10
    assert result["component_percentiles"] == dict.fromkeys(COMPOSITE_METRICS, 55.0)
    assert result["composite_health_score"] == 52.5
    assert result["internal_research_grade"] == "BB"
    for key in COMPOSITE_METRICS:
        changed = current | {key: 0.1 if key == "debt_ratio" else 0.9}
        assert 52.5 < benchmark.score(changed, current["sector"])["composite_health_score"] <= 100
    assert benchmark.score(incomplete, "Manufacturing")["internal_research_grade"] == "UNSCORED"
    fallback = benchmark.score(current, "Mining")
    assert (fallback["cohort_scope"], fallback["cohort_size"]) == ("universe", 11)


def test_health_pillars_and_actionable_recommendations(apple: list[dict[str, Any]]) -> None:
    """Verify four-pillar 0-100 scoring, missing-data handling, and SHAP recommendations."""
    strong = apple[-1]
    pillars_res = compute_health_pillars(strong)
    assert pillars_res["overall_score"] is not None
    assert 0.0 <= pillars_res["overall_score"] <= 100.0
    assert pillars_res["overall_grade"] in ("AAA", "AA", "A", "BBB", "BB", "B", "CCC")
    assert pillars_res["pillars"]["profitability"]["status"] == "STRONG"
    assert pillars_res["pillars"]["cash_flow_efficiency"]["status"] == "STRONG"

    empty_res = compute_health_pillars({})
    assert empty_res["overall_score"] is None
    assert empty_res["overall_grade"] == "UNSCORED"
    for item in empty_res["pillars"].values():
        assert item["score"] is None
        assert item["status"] == "UNAVAILABLE"
        assert item["observed_metrics"] == 0

    distressed = {
        "roa": -0.18,
        "roe": -0.45,
        "debt_ratio": 0.96,
        "debt_to_equity": -2.5,
        "current_ratio": 0.45,
        "ocf_ratio": -0.16,
    }
    distressed_pillars = compute_health_pillars(distressed)
    assert distressed_pillars["overall_score"] is not None
    assert distressed_pillars["overall_score"] < 30.0
    assert distressed_pillars["pillars"]["solvency"]["status"] == "CRITICAL"

    shap_drivers = [
        {"feature": "debt_ratio", "shap_value": 0.85, "direction": "INCREASES_RISK"},
        {"feature": "ocf_ratio", "shap_value": 0.42, "direction": "INCREASES_RISK"},
        {"feature": "roa", "shap_value": -0.30, "direction": "DECREASES_RISK"},
    ]
    recs = generate_actionable_recommendations(distressed, shap_drivers, "CRITICAL")
    assert len(recs) == 2
    assert recs[0]["feature"] == "debt_ratio"
    assert recs[0]["priority"] == "HIGH"
    assert recs[0]["category"] == "SOLVENCY"
    assert recs[1]["feature"] == "ocf_ratio"

    safe_recs = generate_actionable_recommendations(strong, [], "LOW")
    assert len(safe_recs) == 1
    assert safe_recs[0]["priority"] == "LOW"
    assert safe_recs[0]["feature"] == "overall_health"
