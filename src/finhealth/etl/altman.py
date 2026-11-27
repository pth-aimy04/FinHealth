"""International Altman Z, Z', and Z'' scoring with dynamic cutoffs and FI exclusion."""

from collections.abc import Mapping
from math import isfinite
from typing import Any, Literal

from finhealth.etl.financial_ratios import _finite, _safe_div

AltmanVariant = Literal["Z", "Z'", "Z''"]
AltmanZone = Literal["SAFE", "GREY", "DISTRESS"]

FI_UNAVAILABLE_REASON_VI = (
    "Chỉ số Altman Z-Score không áp dụng cho Ngân hàng, Bảo hiểm và Tổ chức tài chính."
)
LISTED_FALLBACK_NOTE_VI = (
    "Thiếu vốn hóa thị trường (Market Value of Equity); hệ thống tự động chuyển sang "
    "biến thể Z' sử dụng vốn chủ sở hữu sổ sách với ngưỡng 1,23 / 2,90."
)
ZONE_LABELS_VI: dict[AltmanZone, str] = {
    "SAFE": "Vùng an toàn",
    "GREY": "Vùng xám (cần theo dõi)",
    "DISTRESS": "Vùng nguy hiểm",
}


def select_altman_variant(
    *,
    business_type: str,
    listing_status: str = "unlisted",
    has_market_value: bool = False,
) -> tuple[AltmanVariant | None, float | None, float | None]:
    """Select the economically valid Altman formula and zone cutoffs by firm type."""
    normalized_type = business_type.strip().lower()
    normalized_listing = listing_status.strip().lower()
    if normalized_type == "financial_institution":
        return None, None, None
    if normalized_type == "manufacturing":
        if normalized_listing == "listed" and has_market_value:
            return "Z", 1.81, 2.99
        return "Z'", 1.23, 2.90
    return "Z''", 1.10, 2.60


def compute_altman_assessment(
    statement: Mapping[str, Any],
    *,
    business_type: str = "trade_service",
    listing_status: str = "unlisted",
) -> dict[str, Any]:
    """Compute Altman Z, Z', or Z'' with explicit cutoffs and financial-institution blocking."""
    normalized_type = business_type.strip().lower()
    normalized_listing = listing_status.strip().lower()
    if normalized_type == "financial_institution":
        return {
            "applicable": False,
            "variant": None,
            "score": None,
            "zone": None,
            "zone_label_vi": None,
            "cutoff_low": None,
            "cutoff_high": None,
            "components": {},
            "fallback_note_vi": None,
            "unavailable_reason_vi": FI_UNAVAILABLE_REASON_VI,
        }

    market_value = _finite(statement.get("market_value_equity"))
    has_market_value = market_value is not None and market_value > 0.0
    variant, cutoff_low, cutoff_high = select_altman_variant(
        business_type=normalized_type,
        listing_status=normalized_listing,
        has_market_value=has_market_value,
    )
    assert variant is not None and cutoff_low is not None and cutoff_high is not None

    fallback_note_vi = (
        LISTED_FALLBACK_NOTE_VI
        if normalized_type == "manufacturing"
        and normalized_listing == "listed"
        and not has_market_value
        else None
    )

    current_assets = _finite(statement.get("current_assets"))
    current_liabilities = _finite(statement.get("current_liabilities"))
    working_capital = (
        current_assets - current_liabilities
        if current_assets is not None and current_liabilities is not None
        else None
    )
    total_assets = _finite(statement.get("total_assets"))
    total_liabilities = _finite(statement.get("total_liabilities"))

    x1 = _safe_div(working_capital, total_assets, require_positive_den=True)
    x2 = _safe_div(statement.get("retained_earnings"), total_assets, require_positive_den=True)
    x3 = _safe_div(statement.get("operating_income"), total_assets, require_positive_den=True)

    weights: tuple[float, ...]
    ordered: tuple[float | None, ...]
    if variant == "Z":
        x4 = _safe_div(market_value, total_liabilities, require_positive_den=True)
        x5 = _safe_div(statement.get("revenues"), total_assets, require_positive_den=True)
        components: dict[str, float | None] = {
            "x1_wc_to_ta": x1,
            "x2_re_to_ta": x2,
            "x3_ebit_to_ta": x3,
            "x4_mve_to_tl": x4,
            "x5_sales_to_ta": x5,
        }
        weights = (1.2, 1.4, 3.3, 0.6, 1.0)
        ordered = (x1, x2, x3, x4, x5)
    elif variant == "Z'":
        x4 = _safe_div(
            statement.get("stockholders_equity"), total_liabilities, require_positive_den=True
        )
        x5 = _safe_div(statement.get("revenues"), total_assets, require_positive_den=True)
        components = {
            "x1_wc_to_ta": x1,
            "x2_re_to_ta": x2,
            "x3_ebit_to_ta": x3,
            "x4_bve_to_tl": x4,
            "x5_sales_to_ta": x5,
        }
        weights = (0.717, 0.847, 3.107, 0.420, 0.998)
        ordered = (x1, x2, x3, x4, x5)
    else:
        x4 = _safe_div(
            statement.get("stockholders_equity"), total_liabilities, require_positive_den=True
        )
        components = {
            "x1_wc_to_ta": x1,
            "x2_re_to_ta": x2,
            "x3_ebit_to_ta": x3,
            "x4_bve_to_tl": x4,
        }
        weights = (6.56, 3.26, 6.72, 1.05)
        ordered = (x1, x2, x3, x4)

    if any(value is None for value in ordered):
        return {
            "applicable": True,
            "variant": variant,
            "score": None,
            "zone": None,
            "zone_label_vi": None,
            "cutoff_low": cutoff_low,
            "cutoff_high": cutoff_high,
            "components": components,
            "fallback_note_vi": fallback_note_vi,
            "unavailable_reason_vi": (
                f"Chưa đủ khoản mục kế toán bắt buộc để tính chỉ số Altman {variant}."
            ),
        }

    raw_score = sum(
        weight * value
        for weight, value in zip(weights, ordered, strict=True)
        if value is not None
    )
    if not isfinite(raw_score):
        return {
            "applicable": True,
            "variant": variant,
            "score": None,
            "zone": None,
            "zone_label_vi": None,
            "cutoff_low": cutoff_low,
            "cutoff_high": cutoff_high,
            "components": components,
            "fallback_note_vi": fallback_note_vi,
            "unavailable_reason_vi": f"Giá trị Altman {variant} không hữu hạn.",
        }

    score = round(raw_score, 4)
    zone: AltmanZone = (
        "SAFE" if score > cutoff_high else "GREY" if score >= cutoff_low else "DISTRESS"
    )
    return {
        "applicable": True,
        "variant": variant,
        "score": score,
        "zone": zone,
        "zone_label_vi": ZONE_LABELS_VI[zone],
        "cutoff_low": cutoff_low,
        "cutoff_high": cutoff_high,
        "components": components,
        "fallback_note_vi": fallback_note_vi,
        "unavailable_reason_vi": None,
    }
