"""Deterministic annual accounting analytics independent of the fitted ML bundle."""

from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from itertools import permutations
from math import fsum, isfinite, prod
from typing import Any

from finhealth.etl.financial_ratios import _finite, _safe_div

COMPOSITE_METRICS = ("roa", "ocf_ratio", "current_ratio", "debt_ratio")
RESEARCH_GRADE_LABEL = "Internal Research Grade (Not an Agency Credit Rating)"
COMPOSITE_VERSION = "internal_composite_v1.2"
DUPONT_BASIS = (
    "Unclipped net income / average book equity, using opening and closing annual balances. "
    "Both book equity balances must be at least 5% of their respective assets. "
    "ML ROE uses ending equity and is capped at ±300%."
)
CHECKLIST_BASIS = (
    "Eight Piotroski-inspired checks on reported FinHealth ratios. Leverage uses total "
    "liabilities and margin uses operating income. Counts use observed checks only."
)
ACCRUALS_BASIS = (
    "Net income minus operating cash flow. Cash-flow accruals are a screening signal "
    "and do not establish earnings manipulation."
)
_COMPARATIVE_CHECKS = (
    ("improving_roa", "roa", True),
    ("declining_leverage", "debt_ratio", False),
    ("improving_liquidity", "current_ratio", True),
    ("improving_operating_margin", "operating_margin", True),
    ("improving_asset_turnover", "asset_turnover", True),
)
Record = Mapping[str, Any]
Factors = tuple[float, float, float]


def _pair_reason(current: Record, prior: Record | None) -> str | None:
    """Validate a comparable fiscal and publication sequence for a company's statements."""
    if prior is None:
        return "missing_prior_annual"
    if current.get("form_type") != "10-K" or prior.get("form_type") != "10-K":
        return "annual_filings_required"
    if current["fiscal_year"] != prior["fiscal_year"] + 1:
        return "nonconsecutive_fiscal_year"
    current_date, prior_date = current.get("filed_date"), prior.get("filed_date")
    if not isinstance(current_date, date) or not isinstance(prior_date, date):
        return "missing_filing_date"
    if current_date <= prior_date:
        return "non_forward_publication"
    return None


def _average_assets(current: Record, prior: Record) -> float | None:
    """Average two positive reported asset balances."""
    end, start = _finite(current.get("total_assets")), _finite(prior.get("total_assets"))
    if end is None or start is None or min(end, start) <= 0:
        return None
    return end / 2 + start / 2


def _dupont_factors(current: Record, prior: Record | None) -> tuple[Factors | None, str | None]:
    """Compute net margin, turnover and multiplier from a compatible annual pair."""
    reason = _pair_reason(current, prior)
    if reason:
        return None, reason
    assert prior is not None
    assets = _average_assets(current, prior)
    if assets is None:
        return None, "missing_or_nonpositive_assets"
    end_equity = _finite(current.get("stockholders_equity"))
    start_equity = _finite(prior.get("stockholders_equity"))
    if (
        end_equity is None
        or start_equity is None
        or min(end_equity, start_equity) <= 0
        or end_equity < 0.05 * current["total_assets"]
        or start_equity < 0.05 * prior["total_assets"]
    ):
        return None, "missing_or_insufficient_equity"
    equity = end_equity / 2 + start_equity / 2
    revenue = _finite(current.get("revenues"))
    income = _finite(current.get("net_income"))
    if revenue is None or revenue <= 0 or income is None:
        return None, "missing_income_or_nonpositive_revenue"
    factors = (income / revenue, revenue / assets, assets / equity)
    if not all(map(isfinite, factors)) or not isfinite(prod(factors)):
        return None, "nonfinite_dupont"
    return factors, None


def dupont_bridge(prior: Factors, current: Factors) -> dict[str, float]:
    """Average marginal ROE changes across all six factor replacement orders."""
    changes: list[list[float]] = [[], [], []]
    for order in permutations(range(3)):
        values = list(prior)
        for index in order:
            before = prod(values)
            values[index] = current[index]
            changes[index].append(prod(values) - before)
    return {
        "margin_contribution": fsum(changes[0]) / 6,
        "turnover_contribution": fsum(changes[1]) / 6,
        "leverage_contribution": fsum(changes[2]) / 6,
        "delta_roe_dupont_avg": prod(current) - prod(prior),
    }


def compute_dupont(history: Sequence[Record]) -> dict[str, Any]:
    """Return latest annual DuPont factors and, for three valid years, the ROE bridge."""
    current = history[-1]
    prior = history[-2] if len(history) >= 2 else None
    earlier = history[-3] if len(history) >= 3 else None
    factors, reason = _dupont_factors(current, prior)
    prior_factors, prior_reason = _dupont_factors(prior, earlier) if prior else (None, None)
    return {
        "net_profit_margin": factors[0] if factors else None,
        "asset_turnover_avg": factors[1] if factors else None,
        "equity_multiplier_avg": factors[2] if factors else None,
        "roe_dupont_avg": prod(factors) if factors else None,
        "roe_ending_equity": _finite(current.get("roe")),
        "prior_roe_dupont_avg": prod(prior_factors) if prior_factors and factors else None,
        "bridge": dupont_bridge(prior_factors, factors) if prior_factors and factors else None,
        "reason": reason,
        "bridge_reason": reason or prior_reason,
        "basis_note": DUPONT_BASIS,
    }


def compute_quality_of_earnings(current: Record, prior: Record | None) -> dict[str, Any]:
    """Measure conversion and accruals, falling back to explicitly tagged ending assets."""
    income, ocf = _finite(current.get("net_income")), _finite(current.get("operating_cash_flow"))
    gap = _finite(income - ocf) if income is not None and ocf is not None else None
    conversion = _safe_div(ocf, income, True)
    reason = (
        "non_positive_net_income"
        if income is not None and income <= 0
        else "missing_net_income"
        if income is None
        else "missing_operating_cash_flow"
        if ocf is None
        else "unusable_conversion_ratio"
        if conversion is None
        else None
    )
    average = (
        _average_assets(current, prior) if prior and _pair_reason(current, prior) is None else None
    )
    ending = _finite(current.get("total_assets"))
    assets = average if average is not None else ending
    basis = (
        "average_assets"
        if average is not None
        else "ending_assets"
        if ending and ending > 0
        else None
    )
    accrual = _safe_div(gap, assets, True)
    flag = None
    if accrual is not None:
        if accrual > 0.08:
            flag = "EARNINGS_AHEAD_OF_CASH_WARNING"
        elif accrual <= 0 and ocf is not None and ocf > 0:
            flag = "CASH_BACKED_EARNINGS"
    return {
        "cash_conversion_qoe": conversion,
        "cash_conversion_reason": reason,
        "accrual_gap_usd": gap,
        "cash_flow_accruals_ratio": accrual,
        "accruals_basis": basis,
        "accruals_flag": flag,
        "basis_note": ACCRUALS_BASIS,
    }


def _signal(
    value: float | None, reference: float | None, increasing: bool, reason: str | None = None
) -> dict[str, Any]:
    """Compare finite quantities and preserve absent evidence."""
    if value is None or reference is None or reason:
        return {
            "status": "UNAVAILABLE",
            "current_value": value,
            "prior_value": reference,
            "reason": reason or "missing_accounting_input",
        }
    passed = value > reference if increasing else value < reference
    return {
        "status": "PASS" if passed else "FAIL",
        "current_value": value,
        "prior_value": reference,
        "reason": ("current_gt_reference" if increasing else "current_lt_reference")
        if passed
        else "strict_improvement_not_met",
    }


def compute_accounting_checklist(current: Record, prior: Record | None) -> dict[str, Any]:
    """Evaluate eight signals using observed accounting values and valid annual pairs."""
    roa = _finite(current.get("roa"))
    ocf = _finite(current.get("operating_cash_flow"))
    income = _finite(current.get("net_income"))
    signals = {
        "positive_roa": _signal(roa, 0.0, True),
        "positive_ocf": _signal(ocf, 0.0, True),
        "cash_exceeds_net_income": _signal(ocf, income, True),
    }
    reason = _pair_reason(current, prior)
    for name, metric, increasing in _COMPARATIVE_CHECKS:
        signals[name] = _signal(
            _finite(current.get(metric)),
            _finite(prior.get(metric)) if prior and reason is None else None,
            increasing,
            reason,
        )
    observed = sum(signal["status"] != "UNAVAILABLE" for signal in signals.values())
    passes = sum(signal["status"] == "PASS" for signal in signals.values())
    return {
        "signals": signals,
        "observed_passes": passes,
        "observed_checks": observed,
        "pass_ratio": passes / observed if observed else None,
        "basis_note": CHECKLIST_BASIS,
    }


def _composite_values(row: Record) -> tuple[float, ...] | None:
    """Require complete finite evidence for all four composite dimensions."""
    values = tuple(_finite(row.get(key)) for key in COMPOSITE_METRICS)
    return None if None in values else tuple(value for value in values if value is not None)


def _sorted_columns(rows: list[tuple[float, ...]]) -> tuple[list[float], ...]:
    """Prepare one sorted column per metric from the same complete-case cohort."""
    return tuple(sorted(column) for column in zip(*rows, strict=True)) if rows else ()


@dataclass(frozen=True)
class CompositeBenchmark:
    """One fixed peer cohort per scope for all companies in a response."""

    universe: tuple[list[float], ...]
    by_sector: dict[str, tuple[list[float], ...]]

    @classmethod
    def from_rows(cls, rows: Sequence[Record]) -> "CompositeBenchmark":
        """Construct complete-case industry benchmarks from annual snapshots."""
        universe = []
        sectors: dict[str, list[tuple[float, ...]]] = {}
        for row in rows:
            values = _composite_values(row)
            if values is not None:
                universe.append(values)
                if row.get("sector") not in (None, "", "Unknown"):
                    sectors.setdefault(row["sector"], []).append(values)
        return cls(
            _sorted_columns(universe),
            {
                sector: _sorted_columns(group)
                for sector, group in sectors.items()
                if len(group) >= 10
            },
        )

    def score(self, current: Record, sector: str | None) -> dict[str, Any]:
        """Evaluate empirical midranks against a single fixed benchmark cohort."""
        local = self.by_sector.get(sector) if sector else None
        columns = local or self.universe
        size = len(columns[0]) if columns else 0
        values = _composite_values(current)
        ranks = {}
        score = None
        if values is not None and size:
            ranks = {
                key: 50 * (bisect_left(column, value) + bisect_right(column, value)) / size
                for key, column, value in zip(COMPOSITE_METRICS, columns, values, strict=True)
            }
            score = (
                ranks["roa"]
                + ranks["ocf_ratio"]
                + ranks["current_ratio"]
                + 100
                - ranks["debt_ratio"]
            ) / 4
        grade = (
            "UNSCORED"
            if score is None
            else next(
                band
                for minimum, band in (
                    (85, "AAA"),
                    (75, "AA"),
                    (65, "A"),
                    (55, "BBB"),
                    (45, "BB"),
                    (35, "B"),
                    (0, "CCC"),
                )
                if score >= minimum
            )
        )
        return {
            "composite_health_score": score,
            "internal_research_grade": grade,
            "internal_research_grade_label": RESEARCH_GRADE_LABEL,
            "cohort_scope": "sector" if local else "universe",
            "cohort_size": size,
            "methodology_version": COMPOSITE_VERSION,
            "component_percentiles": ranks,
        }


_PILLAR_BOUNDS: dict[str, tuple[tuple[str, float, float, bool], ...]] = {
    "profitability": (
        ("roa", -0.15, 0.20, False),
        ("roe", -0.30, 0.35, False),
        ("operating_margin", -0.15, 0.25, False),
        ("ebit_to_assets", -0.15, 0.20, False),
    ),
    "liquidity": (
        ("current_ratio", 0.50, 2.50, False),
        ("cash_ratio", 0.05, 1.00, False),
        ("working_capital_ratio", -0.20, 0.35, False),
    ),
    "solvency": (
        ("debt_ratio", 0.20, 0.95, True),
        ("debt_to_equity", 0.20, 4.00, True),
        ("retained_earnings_ratio", -0.40, 0.40, False),
        ("interest_coverage", -2.0, 10.0, False),
    ),
    "cash_flow_efficiency": (
        ("ocf_ratio", -0.15, 0.35, False),
        ("fcf_to_liabilities", -0.20, 0.25, False),
        ("asset_turnover", 0.15, 1.50, False),
    ),
}

_PILLAR_LABELS: dict[str, str] = {
    "profitability": "Khả năng sinh lời",
    "liquidity": "Khả năng thanh khoản",
    "solvency": "Cấu trúc vốn & Khả năng trả nợ",
    "cash_flow_efficiency": "Dòng tiền & Hiệu quả hoạt động",
}


def _score_metric(
    value: float | None, low: float, high: float, invert: bool, key: str
) -> float | None:
    """Map an observed finite financial ratio onto [0, 100] without imputing missing values."""
    val = _finite(value)
    if val is None:
        return None
    if key == "debt_to_equity" and val < 0:
        return 0.0
    clamped = min(max(val, low), high)
    norm = (clamped - low) / (high - low)
    return 100.0 * (1.0 - norm if invert else norm)


def _pillar_status(score: float | None) -> str:
    """Assign a discrete qualitative status to a 0-100 pillar score."""
    if score is None:
        return "UNAVAILABLE"
    if score >= 70.0:
        return "STRONG"
    if score >= 50.0:
        return "ADEQUATE"
    if score >= 30.0:
        return "WEAK"
    return "CRITICAL"


def compute_health_pillars(record: Record) -> dict[str, Any]:
    """Compute 0-100 scores across the four fundamental financial health pillars."""
    pillars: dict[str, dict[str, Any]] = {}
    available_scores: list[float] = []
    for pillar_key, specs in _PILLAR_BOUNDS.items():
        scores = [
            s
            for metric_key, low, high, invert in specs
            if (s := _score_metric(record.get(metric_key), low, high, invert, metric_key))
            is not None
        ]
        pillar_score = fsum(scores) / len(scores) if scores else None
        if pillar_score is not None:
            available_scores.append(pillar_score)
        pillars[pillar_key] = {
            "name": pillar_key,
            "label_vi": _PILLAR_LABELS[pillar_key],
            "score": pillar_score,
            "status": _pillar_status(pillar_score),
            "observed_metrics": len(scores),
            "total_metrics": len(specs),
        }
    overall = fsum(available_scores) / len(available_scores) if available_scores else None
    grade = (
        "UNSCORED"
        if overall is None
        else next(
            band
            for minimum, band in (
                (85, "AAA"),
                (75, "AA"),
                (65, "A"),
                (55, "BBB"),
                (45, "BB"),
                (35, "B"),
                (0, "CCC"),
            )
            if overall >= minimum
        )
    )
    return {
        "overall_score": overall,
        "overall_grade": grade,
        "pillars": pillars,
    }


_RECOMMENDATION_RULES: dict[str, tuple[str, str, str]] = {
    "debt_ratio": (
        "SOLVENCY",
        "<= 60%",
        "Giảm tỷ lệ nợ phải trả trên tổng tài sản qua tái cơ cấu nợ vay hoặc tăng vốn chủ sở hữu.",
    ),
    "debt_to_equity": (
        "SOLVENCY",
        "<= 1.5x",
        "Hạ đòn bẩy nợ/vốn chủ sở hữu và hạn chế vay nợ mới có lãi suất cao.",
    ),
    "retained_earnings_ratio": (
        "SOLVENCY",
        ">= 10%",
        "Củng cố lợi nhuận giữ lại tích lũy, hạn chế chia cổ tức tiền mặt khi đệm vốn mỏng.",
    ),
    "current_ratio": (
        "LIQUIDITY",
        ">= 1.20x",
        "Bổ sung vốn lưu động ròng, giãn kỳ hạn nợ ngắn hạn và thu hồi công nợ phải thu.",
    ),
    "working_capital_ratio": (
        "LIQUIDITY",
        ">= 10%",
        (
            "Cải thiện tỷ trọng vốn lưu động trên tổng tài sản "
            "để phòng ngừa áp lực thanh khoản ngắn hạn."
        ),
    ),
    "ocf_ratio": (
        "CASH_FLOW",
        ">= 15%",
        (
            "Tăng dòng tiền thuần từ hoạt động kinh doanh (OCF) trên tổng nợ "
            "thông qua tối ưu tồn kho và thu tiền."
        ),
    ),
    "ocf_ratio_yoy_delta": (
        "CASH_FLOW",
        ">= 0%",
        "Ngăn chặn đà suy giảm dòng tiền hoạt động so với cùng kỳ năm trước.",
    ),
    "negative_ocf_streak": (
        "CASH_FLOW",
        "0 năm âm liên tiếp",
        "Chấm dứt chuỗi năm dòng tiền hoạt động âm để tránh mất khả năng thanh toán.",
    ),
    "roa": (
        "PROFITABILITY",
        ">= 5%",
        "Nâng cao tỷ suất sinh lời trên tổng tài sản (ROA) và thanh lý tài sản kém hiệu quả.",
    ),
    "roa_yoy_delta": (
        "PROFITABILITY",
        ">= 0%",
        "Khắc phục sự suy giảm hiệu suất sinh lời ROA so với năm trước.",
    ),
    "roe": (
        "PROFITABILITY",
        ">= 10%",
        "Cải thiện hiệu quả sinh lời trên vốn chủ sở hữu (ROE) từ hoạt động cốt lõi.",
    ),
    "roe_yoy_delta": (
        "PROFITABILITY",
        ">= 0%",
        "Ổn định biên lợi nhuận và ROE trước biến động chi phí.",
    ),
    "operating_margin": (
        "PROFITABILITY",
        ">= 8%",
        (
            "Kiểm soát giá vốn và chi phí quản lý/bán hàng "
            "để nâng biên lợi nhuận hoạt động (EBIT margin)."
        ),
    ),
    "ebit_to_assets": (
        "PROFITABILITY",
        ">= 6%",
        "Tăng năng suất tạo lợi nhuận trước lãi vay và thuế (EBIT) trên mỗi đồng tài sản.",
    ),
    "asset_turnover": (
        "CASH_FLOW",
        ">= 0.60x",
        "Đẩy nhanh vòng quay tổng tài sản và hiệu suất khai thác công suất.",
    ),
    "debt_ratio_yoy_delta": (
        "SOLVENCY",
        "<= 0%",
        "Kiểm soát tốc độ gia tăng tỷ lệ nợ so với năm trước.",
    ),
    "eps": (
        "PROFITABILITY",
        "> 0",
        "Phục hồi thu nhập trên mỗi cổ phần (EPS) dương bền vững.",
    ),
}


def generate_actionable_recommendations(
    record: Record,
    top_drivers: Sequence[Mapping[str, Any]] | None = None,
    risk_level: str | None = None,
) -> list[dict[str, Any]]:
    """Derive concrete risk-mitigation recommendations from TreeSHAP drivers and ratios."""
    recommendations: list[dict[str, Any]] = []
    seen_features: set[str] = set()
    if top_drivers:
        for driver in top_drivers:
            feature = str(driver.get("feature") or "")
            shap_val = _finite(driver.get("shap_value"))
            direction = str(driver.get("direction") or "")
            if (
                not feature
                or feature in seen_features
                or feature not in _RECOMMENDATION_RULES
                or (shap_val is not None and shap_val <= 0)
                or (shap_val is None and direction != "INCREASES_RISK")
            ):
                continue
            category, benchmark, action_vi = _RECOMMENDATION_RULES[feature]
            priority = (
                "HIGH"
                if (shap_val is not None and shap_val >= 0.25)
                or risk_level in ("HIGH", "CRITICAL")
                else "MEDIUM"
            )
            recommendations.append(
                {
                    "priority": priority,
                    "category": category,
                    "feature": feature,
                    "current_value": _finite(record.get(feature)),
                    "shap_impact": shap_val,
                    "target_benchmark": benchmark,
                    "action_vi": action_vi,
                }
            )
            seen_features.add(feature)
            if len(recommendations) >= 4:
                break
    if not recommendations:
        debt = _finite(record.get("debt_ratio"))
        curr = _finite(record.get("current_ratio"))
        ocf = _finite(record.get("ocf_ratio"))
        if debt is not None and debt > 0.70:
            cat, bench, act = _RECOMMENDATION_RULES["debt_ratio"]
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": cat,
                    "feature": "debt_ratio",
                    "current_value": debt,
                    "shap_impact": None,
                    "target_benchmark": bench,
                    "action_vi": act,
                }
            )
        if curr is not None and curr < 1.0:
            cat, bench, act = _RECOMMENDATION_RULES["current_ratio"]
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": cat,
                    "feature": "current_ratio",
                    "current_value": curr,
                    "shap_impact": None,
                    "target_benchmark": bench,
                    "action_vi": act,
                }
            )
        if ocf is not None and ocf < 0:
            cat, bench, act = _RECOMMENDATION_RULES["ocf_ratio"]
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": cat,
                    "feature": "ocf_ratio",
                    "current_value": ocf,
                    "shap_impact": None,
                    "target_benchmark": bench,
                    "action_vi": act,
                }
            )
    if not recommendations:
        recommendations.append(
            {
                "priority": "LOW",
                "category": "SOLVENCY",
                "feature": "overall_health",
                "current_value": None,
                "shap_impact": None,
                "target_benchmark": "Duy trì cấu trúc hiện tại",
                "action_vi": (
                    "Các chỉ số tài chính và đóng góp TreeSHAP hiện ở vùng an toàn; "
                    "tiếp tục duy trì kỷ luật dòng tiền hoạt động và thanh khoản."
                ),
            }
        )
    return recommendations
