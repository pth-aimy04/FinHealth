"""Translate model feature attributions into plain-Vietnamese Strengths and Bottlenecks."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import fsum
from typing import Any, Literal

from finhealth.etl.financial_ratios import _finite
from finhealth.etl.metric_catalog import (
    METRIC_CATALOG,
    PillarKey,
    evaluate_metric_status,
    format_metric_value_vi,
)

ImpactStrength = Literal["VERY_HIGH", "HIGH", "MODERATE", "LOW"]
DriverSide = Literal["STRENGTH", "BOTTLENECK"]


@dataclass(frozen=True)
class _FeatureNarrativeMeta:
    """Plain-Vietnamese financial description for one model feature."""

    display_code: str
    label_vi: str
    pillar: PillarKey
    unit: Literal["ratio", "percent", "times", "days", "flag", "count"]
    reference_range_vi: str


_FEATURE_META: dict[str, _FeatureNarrativeMeta] = {
    "roa": _FeatureNarrativeMeta(
        "roa", "Tỷ suất sinh lời trên tài sản (ROA)", "profitability", "percent", ">= 5%"
    ),
    "roe": _FeatureNarrativeMeta(
        "roe", "Tỷ suất sinh lời trên vốn chủ sở hữu (ROE)", "profitability", "percent", ">= 12%"
    ),
    "ebit_to_assets": _FeatureNarrativeMeta(
        "ebit_to_assets", "Lợi nhuận hoạt động / Tổng tài sản", "profitability", "percent", ">= 6%"
    ),
    "ebitda_to_assets": _FeatureNarrativeMeta(
        "ebitda_to_assets",
        "Khả năng tạo dòng tiền hoạt động trước khấu hao / Tổng tài sản",
        "profitability",
        "percent",
        ">= 10%",
    ),
    "gross_margin": _FeatureNarrativeMeta(
        "gross_margin", "Biên lợi nhuận gộp", "profitability", "percent", ">= 20%"
    ),
    "operating_margin": _FeatureNarrativeMeta(
        "operating_margin", "Biên lợi nhuận hoạt động", "profitability", "percent", ">= 8%"
    ),
    "ebitda_margin": _FeatureNarrativeMeta(
        "ebitda_margin",
        "Biên lợi nhuận trước khấu hao (EBITDA)",
        "profitability",
        "percent",
        ">= 12%",
    ),
    "opex_to_revenue": _FeatureNarrativeMeta(
        "opex_to_revenue",
        "Tổng chi phí hoạt động / Doanh thu",
        "efficiency",
        "percent",
        "<= 85%",
    ),
    "asset_turnover": _FeatureNarrativeMeta(
        "asset_turnover", "Vòng quay tổng tài sản", "efficiency", "times", ">= 0,70x"
    ),
    "current_ratio": _FeatureNarrativeMeta(
        "current_ratio", "Hệ số thanh toán hiện hành", "liquidity", "times", ">= 1,50x"
    ),
    "quick_ratio": _FeatureNarrativeMeta(
        "quick_ratio", "Hệ số thanh toán nhanh", "liquidity", "times", ">= 1,00x"
    ),
    "cash_ratio": _FeatureNarrativeMeta(
        "cash_ratio", "Hệ số thanh toán tiền mặt", "liquidity", "times", ">= 0,30x"
    ),
    "working_capital_ratio": _FeatureNarrativeMeta(
        "working_capital_ratio",
        "Vốn lưu động ròng / Tổng tài sản",
        "liquidity",
        "percent",
        ">= 10%",
    ),
    "debt_ratio": _FeatureNarrativeMeta(
        "debt_ratio", "Nợ phải trả / Tổng tài sản", "solvency", "percent", "<= 60%"
    ),
    "debt_to_equity": _FeatureNarrativeMeta(
        "debt_to_equity", "Nợ phải trả / Vốn chủ sở hữu", "solvency", "times", "<= 1,50x"
    ),
    "short_term_debt_share": _FeatureNarrativeMeta(
        "short_term_debt_share",
        "Tỷ trọng nợ ngắn hạn trong tổng nợ",
        "solvency",
        "percent",
        "<= 60%",
    ),
    "long_term_debt_to_assets": _FeatureNarrativeMeta(
        "long_term_debt_to_assets", "Nợ dài hạn / Tổng tài sản", "solvency", "percent", "<= 35%"
    ),
    "retained_earnings_ratio": _FeatureNarrativeMeta(
        "retained_earnings_ratio",
        "Lợi nhuận giữ lại / Tổng tài sản",
        "solvency",
        "percent",
        ">= 15%",
    ),
    "equity_to_assets": _FeatureNarrativeMeta(
        "equity_to_assets", "Vốn chủ sở hữu / Tổng tài sản", "solvency", "percent", ">= 40%"
    ),
    "is_negative_equity": _FeatureNarrativeMeta(
        "negative_equity", "Tình trạng âm vốn chủ sở hữu", "solvency", "flag", "VCSH dương"
    ),
    "interest_coverage": _FeatureNarrativeMeta(
        "interest_coverage", "Khả năng thanh toán lãi vay", "solvency", "times", ">= 3,00x"
    ),
    "inventory_to_assets": _FeatureNarrativeMeta(
        "inventory_to_assets", "Hàng tồn kho / Tổng tài sản", "efficiency", "percent", "<= 25%"
    ),
    "receivables_to_revenue": _FeatureNarrativeMeta(
        "receivables_to_revenue", "Phải thu ngắn hạn / Doanh thu", "efficiency", "percent", "<= 18%"
    ),
    "depreciation_to_assets": _FeatureNarrativeMeta(
        "depreciation_to_assets", "Khấu hao / Tổng tài sản", "efficiency", "percent", "2% – 8%"
    ),
    "ocf_ratio": _FeatureNarrativeMeta(
        "ocf_ratio", "Dòng tiền hoạt động / Tổng nợ", "cash_flow", "percent", ">= 15%"
    ),
    "fcf_to_liabilities": _FeatureNarrativeMeta(
        "fcf_to_liabilities", "Dòng tiền tự do / Tổng nợ", "cash_flow", "percent", ">= 5%"
    ),
    "roa_yoy_delta": _FeatureNarrativeMeta(
        "roa_trend", "Xu hướng ROA so với năm trước", "profitability", "percent", ">= 0%"
    ),
    "roe_yoy_delta": _FeatureNarrativeMeta(
        "roe_trend", "Xu hướng ROE so với năm trước", "profitability", "percent", ">= 0%"
    ),
    "gross_margin_yoy_delta": _FeatureNarrativeMeta(
        "gross_margin_trend",
        "Biến động biên lợi nhuận gộp so với năm trước",
        "profitability",
        "percent",
        ">= 0%",
    ),
    "debt_ratio_yoy_delta": _FeatureNarrativeMeta(
        "debt_ratio_trend",
        "Biến động tỷ lệ nợ so với năm trước",
        "solvency",
        "percent",
        "<= 0%",
    ),
    "working_capital_yoy_delta": _FeatureNarrativeMeta(
        "working_capital_trend",
        "Biến động vốn lưu động ròng so với năm trước",
        "liquidity",
        "percent",
        ">= 0%",
    ),
    "ocf_ratio_yoy_delta": _FeatureNarrativeMeta(
        "ocf_trend",
        "Biến động dòng tiền hoạt động so với năm trước",
        "cash_flow",
        "percent",
        ">= 0%",
    ),
    "revenue_growth_yoy": _FeatureNarrativeMeta(
        "revenue_growth", "Tăng trưởng doanh thu so với năm trước", "efficiency", "percent", ">= 5%"
    ),
    "negative_ocf_streak": _FeatureNarrativeMeta(
        "negative_ocf_streak",
        "Số năm liên tiếp có dòng tiền hoạt động âm",
        "cash_flow",
        "count",
        "0 năm",
    ),
}

_STRENGTH_LABELS_VI: dict[ImpactStrength, str] = {
    "VERY_HIGH": "Rất mạnh",
    "HIGH": "Mạnh",
    "MODERATE": "Trung bình",
    "LOW": "Nhẹ",
}


def _classify_impact_strength(impact_share_pct: float) -> ImpactStrength:
    """Bucket relative contribution percentage into four plain-language intensity tiers."""
    if impact_share_pct >= 25.0:
        return "VERY_HIGH"
    if impact_share_pct >= 15.0:
        return "HIGH"
    if impact_share_pct >= 7.0:
        return "MODERATE"
    return "LOW"


def _format_feature_value(feature: str, value: float | None, meta: _FeatureNarrativeMeta) -> str:
    """Format an observed feature value in Vietnamese financial phrasing."""
    finite_val = _finite(value)
    if finite_val is None:
        return "Chưa ghi nhận"
    if feature in METRIC_CATALOG:
        return format_metric_value_vi(feature, finite_val)
    if meta.unit == "percent":
        return f"{finite_val * 100:.1f}%".replace(".", ",")
    if meta.unit == "times":
        return f"{finite_val:.2f}x".replace(".", ",")
    if meta.unit == "days":
        return f"{round(finite_val):d} ngày"
    if meta.unit == "flag":
        return "Đang âm VCSH" if finite_val >= 0.5 else "VCSH dương"
    if meta.unit == "count":
        return f"{int(round(finite_val))} năm"
    return f"{finite_val:.2f}".replace(".", ",")


def _lookup_meta(feature: str) -> _FeatureNarrativeMeta:
    """Resolve narrative metadata for any known or future scale-free feature."""
    if feature in _FEATURE_META:
        return _FEATURE_META[feature]
    clean_code = feature.replace("_yoy_delta", "_trend").replace("shap_", "")
    return _FeatureNarrativeMeta(
        display_code=clean_code,
        label_vi="Chỉ tiêu tài chính bổ trợ",
        pillar="solvency",
        unit="ratio",
        reference_range_vi="Theo chuẩn ngành",
    )


def _build_copy_vi(
    *,
    side: DriverSide,
    meta: _FeatureNarrativeMeta,
    formatted_value: str,
    impact_share_pct: float,
    strength: ImpactStrength,
) -> tuple[str, str]:
    """Generate concise Vietnamese headline and detail without ML jargon or score subtraction."""
    share_str = f"{impact_share_pct:.1f}%".replace(".", ",")
    if side == "BOTTLENECK":
        headline = (
            f"{meta.label_vi} ở mức {formatted_value} "
            f"(ngưỡng tham chiếu {meta.reference_range_vi})"
        )
        intensity_phrase = (
            "là yếu tố đẩy rủi ro tăng rất mạnh"
            if strength == "VERY_HIGH"
            else "đang tạo áp lực đẩy rủi ro tăng đáng kể"
            if strength == "HIGH"
            else "góp phần làm tăng rủi ro tài chính"
        )
        detail = (
            f"{meta.label_vi} hiện đạt {formatted_value} so với ngưỡng an toàn tham chiếu "
            f"{meta.reference_range_vi}, {intensity_phrase} — "
            f"chiếm {share_str} tổng mức tác động rủi ro."
        )
    else:
        headline = (
            f"{meta.label_vi} đạt {formatted_value} "
            f"(ngưỡng tham chiếu {meta.reference_range_vi})"
        )
        intensity_phrase = (
            "là điểm tựa giảm rủi ro nổi bật nhất"
            if strength == "VERY_HIGH"
            else "đóng vai trò điểm tựa giúp giảm rủi ro đáng kể"
            if strength == "HIGH"
            else "hỗ trợ củng cố độ an toàn tài chính"
        )
        detail = (
            f"{meta.label_vi} đạt {formatted_value} (tham chiếu {meta.reference_range_vi}), "
            f"{intensity_phrase} — chiếm {share_str} tổng mức tác động đánh giá."
        )
    return headline, detail


def _is_semantically_adverse(feature: str, observed_val: float, is_neg_eq: bool) -> bool:
    """Return True when an observed ratio is economically weak and must not appear as a Strength."""
    if feature in METRIC_CATALOG:
        return (
            evaluate_metric_status(feature, observed_val, is_negative_equity=is_neg_eq)
            in ("WARNING", "CRITICAL")
        )
    if feature == "receivables_to_revenue":
        return observed_val > 0.25
    if feature == "inventory_to_assets":
        return observed_val > 0.35
    if feature == "opex_to_revenue":
        return observed_val > 0.92
    if feature == "long_term_debt_to_assets":
        return observed_val > 0.50
    if feature == "is_negative_equity":
        return observed_val >= 0.5
    if feature == "negative_ocf_streak":
        return observed_val >= 2.0
    if feature == "ebit_to_assets":
        return observed_val < 0.0
    if feature == "ebitda_to_assets":
        return observed_val < 0.03
    if feature == "debt_ratio_yoy_delta":
        return observed_val > 0.05
    if feature in (
        "roa_yoy_delta",
        "roe_yoy_delta",
        "gross_margin_yoy_delta",
        "working_capital_yoy_delta",
        "ocf_ratio_yoy_delta",
        "revenue_growth_yoy",
    ):
        return observed_val < -0.05
    return False


def translate_drivers_to_business(
    shap_explanation: Mapping[str, Any] | None,
    record: Mapping[str, Any],
    *,
    max_per_side: int = 5,
) -> dict[str, Any]:
    """Split local feature attributions into <=5 Strengths and <=5 Bottlenecks in plain Vietnamese.

    Relative impact shares (`impact_share_pct`) sum to 100% across all non-zero contributions.
    Health score points are NEVER linearly subtracted from log-odds attributions.
    """
    if not shap_explanation:
        return {
            "strengths": [],
            "bottlenecks": [],
            "total_impact_share_pct": 0.0,
            "technical_attribution": None,
        }

    raw_contribs = shap_explanation.get("contributions")
    if not isinstance(raw_contribs, Mapping) or not raw_contribs:
        return {
            "strengths": [],
            "bottlenecks": [],
            "total_impact_share_pct": 0.0,
            "technical_attribution": {
                "output_space": shap_explanation.get("output_space"),
                "base_value": _finite(shap_explanation.get("base_value")),
                "model_name": shap_explanation.get("model_name"),
                "features": [],
            },
        }

    finite_items: list[tuple[str, float]] = []
    for feature, raw_val in raw_contribs.items():
        val = _finite(raw_val)
        if val is not None and abs(val) > 0.0:
            finite_items.append((str(feature), val))

    total_abs = fsum(abs(val) for _, val in finite_items)
    if total_abs <= 0.0:
        return {
            "strengths": [],
            "bottlenecks": [],
            "total_impact_share_pct": 0.0,
            "technical_attribution": {
                "output_space": shap_explanation.get("output_space"),
                "base_value": _finite(shap_explanation.get("base_value")),
                "model_name": shap_explanation.get("model_name"),
                "features": [],
            },
        }

    strengths: list[dict[str, Any]] = []
    bottlenecks: list[dict[str, Any]] = []
    tech_features: list[dict[str, Any]] = []
    is_neg_eq = bool(record.get("is_negative_equity"))

    ordered_items = sorted(finite_items, key=lambda item: (-abs(item[1]), item[0]))
    for feature, attribution in ordered_items:
        share_pct = round((abs(attribution) / total_abs) * 100.0, 2)
        side: DriverSide = "BOTTLENECK" if attribution > 0.0 else "STRENGTH"
        meta = _lookup_meta(feature)
        # Never substitute training medians for missing company facts in user-facing copy.
        observed_val = _finite(record.get(feature))

        tech_features.append(
            {
                "feature": feature,
                "shap_value": round(attribution, 6),
                "impact_share_pct": share_pct,
                "direction": "INCREASES_RISK" if side == "BOTTLENECK" else "DECREASES_RISK",
                "observed_value": observed_val,
            }
        )

        if observed_val is None:
            continue
        if side == "STRENGTH" and _is_semantically_adverse(feature, observed_val, is_neg_eq):
            continue

        formatted = _format_feature_value(feature, observed_val, meta)
        impact_strength = _classify_impact_strength(share_pct)
        headline_vi, detail_vi = _build_copy_vi(
            side=side,
            meta=meta,
            formatted_value=formatted,
            impact_share_pct=share_pct,
            strength=impact_strength,
        )

        driver_card = {
            "factor_code": meta.display_code,
            "label_vi": meta.label_vi,
            "pillar": meta.pillar,
            "side": side,
            "observed_value": observed_val,
            "formatted_value_vi": formatted,
            "reference_range_vi": meta.reference_range_vi,
            "impact_share_pct": share_pct,
            "impact_strength": impact_strength,
            "impact_strength_label_vi": _STRENGTH_LABELS_VI[impact_strength],
            "headline_vi": headline_vi,
            "detail_vi": detail_vi,
        }
        if side == "BOTTLENECK":
            if len(bottlenecks) < max_per_side:
                bottlenecks.append(driver_card)
        else:
            if len(strengths) < max_per_side:
                strengths.append(driver_card)

    total_share_pct = round(fsum(item["impact_share_pct"] for item in tech_features), 2)
    return {
        "strengths": strengths,
        "bottlenecks": bottlenecks,
        "total_impact_share_pct": total_share_pct,
        "technical_attribution": {
            "output_space": shap_explanation.get("output_space"),
            "base_value": _finite(shap_explanation.get("base_value")),
            "model_name": shap_explanation.get("model_name"),
            "features": tech_features,
        },
    }
