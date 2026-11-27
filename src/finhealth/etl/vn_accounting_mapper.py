"""Vietnamese accounting standard (TT99/2025, TT200/2014, TT133/2016) code mapper."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from finhealth.core.exceptions import EtlProcessingError
from finhealth.etl.financial_ratios import _finite

AccountingStandard = Literal["TT99_2025", "TT200_2014", "TT133_2016", "IFRS_USGAAP"]
VasRegime = Literal["TT99_2025", "TT200_2014", "TT133_2016"]
StatementSection = Literal["bs", "is", "cf"]
SignPolicy = Literal["as_is", "abs_outflow"]

SUPPORTED_VAS_REGIMES: tuple[VasRegime, ...] = ("TT99_2025", "TT200_2014", "TT133_2016")

MONETARY_STATEMENT_FIELDS: tuple[str, ...] = (
    "total_assets",
    "current_assets",
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "total_liabilities",
    "current_liabilities",
    "short_term_debt",
    "long_term_debt",
    "accounts_payable",
    "stockholders_equity",
    "retained_earnings",
    "revenues",
    "cost_of_goods_sold",
    "gross_profit",
    "operating_expenses",
    "operating_income",
    "depreciation_amortization",
    "ebitda",
    "interest_expense",
    "net_income",
    "operating_cash_flow",
    "capex",
    "market_value_equity",
)

PER_SHARE_FIELDS: tuple[str, ...] = ("eps_basic", "eps_diluted")
ALL_STATEMENT_NUMERIC_FIELDS: tuple[str, ...] = MONETARY_STATEMENT_FIELDS + PER_SHARE_FIELDS


class NormalizedStatementRecord(TypedDict, total=False):
    """Shared normalized statement contract across Org, SEC EDGAR, and Kaggle inputs."""

    total_assets: float | None
    current_assets: float | None
    cash_and_equivalents: float | None
    accounts_receivable: float | None
    inventory: float | None
    total_liabilities: float | None
    current_liabilities: float | None
    short_term_debt: float | None
    long_term_debt: float | None
    accounts_payable: float | None
    stockholders_equity: float | None
    retained_earnings: float | None
    revenues: float | None
    cost_of_goods_sold: float | None
    gross_profit: float | None
    operating_expenses: float | None
    operating_income: float | None
    depreciation_amortization: float | None
    ebitda: float | None
    interest_expense: float | None
    net_income: float | None
    operating_cash_flow: float | None
    capex: float | None
    market_value_equity: float | None
    eps_basic: float | None
    eps_diluted: float | None
    is_manufacturing: bool
    is_financial_institution: bool
    listing_status: str
    audit_status: str
    accounting_standard: str
    currency: str


@dataclass(frozen=True)
class VasLineItemSpec:
    """Metadata linking an official Vietnamese accounting line code to a normalized field."""

    section: StatementSection
    code: str
    field_name: str
    label_vi: str
    sign_policy: SignPolicy = "as_is"
    is_per_share: bool = False


_TT200_AND_TT99_BS_ITEMS: tuple[VasLineItemSpec, ...] = (
    VasLineItemSpec("bs", "100", "current_assets", "Tài sản ngắn hạn"),
    VasLineItemSpec("bs", "110", "cash_and_equivalents", "Tiền và các khoản tương đương tiền"),
    VasLineItemSpec("bs", "130", "accounts_receivable", "Các khoản phải thu ngắn hạn"),
    VasLineItemSpec("bs", "140", "inventory", "Hàng tồn kho"),
    VasLineItemSpec("bs", "270", "total_assets", "Tổng cộng tài sản"),
    VasLineItemSpec("bs", "300", "total_liabilities", "Nợ phải trả"),
    VasLineItemSpec("bs", "310", "current_liabilities", "Nợ ngắn hạn"),
    VasLineItemSpec("bs", "311", "accounts_payable", "Phải trả người bán ngắn hạn"),
    VasLineItemSpec("bs", "320", "short_term_debt", "Vay và nợ thuê tài chính ngắn hạn"),
    VasLineItemSpec("bs", "338", "long_term_debt", "Vay và nợ thuê tài chính dài hạn"),
    VasLineItemSpec("bs", "400", "stockholders_equity", "Vốn chủ sở hữu"),
    VasLineItemSpec("bs", "421", "retained_earnings", "Lợi nhuận sau thuế chưa phân phối"),
)

_TT200_AND_TT99_IS_ITEMS: tuple[VasLineItemSpec, ...] = (
    VasLineItemSpec("is", "10", "revenues", "Doanh thu thuần về bán hàng và cung cấp dịch vụ"),
    VasLineItemSpec("is", "11", "cost_of_goods_sold", "Giá vốn hàng bán"),
    VasLineItemSpec("is", "20", "gross_profit", "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ"),
    VasLineItemSpec("is", "23", "interest_expense", "Trong đó: Chi phí lãi vay"),
    VasLineItemSpec("is", "25", "selling_expenses", "Chi phí bán hàng"),
    VasLineItemSpec("is", "26", "admin_expenses", "Chi phí quản lý doanh nghiệp"),
    VasLineItemSpec("is", "30", "operating_income", "Lợi nhuận thuần từ hoạt động kinh doanh"),
    VasLineItemSpec("is", "60", "net_income", "Lợi nhuận sau thuế thu nhập doanh nghiệp"),
    VasLineItemSpec("is", "70", "eps_basic", "Lãi cơ bản trên cổ phiếu", is_per_share=True),
    VasLineItemSpec("is", "71", "eps_diluted", "Lãi suy giảm trên cổ phiếu", is_per_share=True),
)

_COMMON_CF_ITEMS: tuple[VasLineItemSpec, ...] = (
    VasLineItemSpec(
        "cf",
        "02",
        "depreciation_amortization",
        "Khấu hao TSCĐ và bất động sản đầu tư",
    ),
    VasLineItemSpec(
        "cf",
        "20",
        "operating_cash_flow",
        "Lưu chuyển tiền thuần từ hoạt động kinh doanh",
    ),
    VasLineItemSpec(
        "cf",
        "21",
        "capex",
        "Tiền chi để mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác",
        sign_policy="abs_outflow",
    ),
)

_TT133_BS_ITEMS: tuple[VasLineItemSpec, ...] = (
    VasLineItemSpec("bs", "100", "current_assets", "Tài sản ngắn hạn"),
    VasLineItemSpec("bs", "110", "cash_and_equivalents", "Tiền và các khoản tương đương tiền"),
    VasLineItemSpec("bs", "130", "accounts_receivable", "Các khoản phải thu ngắn hạn"),
    VasLineItemSpec("bs", "140", "inventory", "Hàng tồn kho"),
    VasLineItemSpec("bs", "270", "total_assets", "Tổng cộng tài sản"),
    VasLineItemSpec("bs", "300", "total_liabilities", "Nợ phải trả"),
    VasLineItemSpec("bs", "310", "current_liabilities", "Nợ ngắn hạn"),
    VasLineItemSpec("bs", "311", "accounts_payable", "Phải trả người bán ngắn hạn"),
    VasLineItemSpec("bs", "316", "short_term_debt", "Vay và nợ thuê tài chính ngắn hạn"),
    VasLineItemSpec("bs", "336", "long_term_debt", "Vay và nợ thuê tài chính dài hạn"),
    VasLineItemSpec("bs", "400", "stockholders_equity", "Vốn chủ sở hữu"),
    VasLineItemSpec("bs", "417", "retained_earnings", "Lợi nhuận sau thuế chưa phân phối"),
)

_TT133_IS_ITEMS: tuple[VasLineItemSpec, ...] = (
    VasLineItemSpec("is", "10", "revenues", "Doanh thu thuần về bán hàng và cung cấp dịch vụ"),
    VasLineItemSpec("is", "11", "cost_of_goods_sold", "Giá vốn hàng bán"),
    VasLineItemSpec("is", "20", "gross_profit", "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ"),
    VasLineItemSpec("is", "23", "interest_expense", "Trong đó: Chi phí lãi vay"),
    VasLineItemSpec("is", "24", "operating_expenses", "Chi phí quản lý kinh doanh"),
    VasLineItemSpec("is", "30", "operating_income", "Lợi nhuận thuần từ hoạt động kinh doanh"),
    VasLineItemSpec("is", "60", "net_income", "Lợi nhuận sau thuế thu nhập doanh nghiệp"),
)

REGIME_SPECS: dict[VasRegime, tuple[VasLineItemSpec, ...]] = {
    "TT99_2025": _TT200_AND_TT99_BS_ITEMS + _TT200_AND_TT99_IS_ITEMS + _COMMON_CF_ITEMS,
    "TT200_2014": _TT200_AND_TT99_BS_ITEMS + _TT200_AND_TT99_IS_ITEMS + _COMMON_CF_ITEMS,
    "TT133_2016": _TT133_BS_ITEMS + _TT133_IS_ITEMS + _COMMON_CF_ITEMS,
}

REGIME_METADATA: dict[VasRegime, dict[str, str]] = {
    "TT99_2025": {
        "title_vi": "Thông tư 99/2025/TT-BTC (Báo cáo tình hình tài chính)",
        "bs_name_vi": "Báo cáo tình hình tài chính (B01-DN)",
        "is_name_vi": "Báo cáo kết quả hoạt động kinh doanh (B02-DN)",
        "cf_name_vi": "Báo cáo lưu chuyển tiền tệ (B03-DN)",
    },
    "TT200_2014": {
        "title_vi": "Thông tư 200/2014/TT-BTC (Doanh nghiệp lớn)",
        "bs_name_vi": "Bảng cân đối kế toán (B01-DN)",
        "is_name_vi": "Báo cáo kết quả hoạt động kinh doanh (B02-DN)",
        "cf_name_vi": "Báo cáo lưu chuyển tiền tệ (B03-DN)",
    },
    "TT133_2016": {
        "title_vi": "Thông tư 133/2016/TT-BTC (Doanh nghiệp nhỏ và vừa)",
        "bs_name_vi": "Báo cáo tình hình tài chính (B01b-DNN)",
        "is_name_vi": "Báo cáo kết quả hoạt động kinh doanh (B02-DNN)",
        "cf_name_vi": "Báo cáo lưu chuyển tiền tệ (B03-DNN)",
    },
}


def normalize_vas_regime(standard: str) -> VasRegime:
    """Validate and normalize a Vietnamese accounting standard identifier."""
    cleaned = standard.strip().upper().replace("-", "_").replace("/", "_")
    aliases: dict[str, VasRegime] = {
        "TT99": "TT99_2025",
        "TT99_2025": "TT99_2025",
        "TT99_2025_TT_BTC": "TT99_2025",
        "TT200": "TT200_2014",
        "TT200_2014": "TT200_2014",
        "TT200_2014_TT_BTC": "TT200_2014",
        "TT133": "TT133_2016",
        "TT133_2016": "TT133_2016",
        "TT133_2016_TT_BTC": "TT133_2016",
    }
    if cleaned in aliases:
        return aliases[cleaned]
    raise EtlProcessingError(
        f"Chế độ kế toán không được hỗ trợ: {standard!r}. "
        "Chỉ hỗ trợ TT99_2025, TT200_2014, TT133_2016."
    )


def get_regime_spec(standard: str) -> tuple[VasLineItemSpec, ...]:
    """Return the official line-item mapping table for one Vietnamese accounting regime."""
    return REGIME_SPECS[normalize_vas_regime(standard)]


def _normalize_code_key(code: str) -> str:
    """Normalize a numeric VAS indicator code string while preserving leading zeros."""
    cleaned = str(code).strip()
    if cleaned.endswith(".0") and cleaned[:-2].isdigit():
        cleaned = cleaned[:-2]
    if len(cleaned) == 1 and cleaned.isdigit():
        return f"0{cleaned}"
    return cleaned


def _normalize_section_map(raw: Mapping[str, Any] | None) -> dict[str, float | None]:
    """Convert raw indicator mappings into canonical code -> finite float or None."""
    if not raw:
        return {}
    normalized: dict[str, float | None] = {}
    for key, value in raw.items():
        code = _normalize_code_key(key)
        normalized[code] = _finite(value)
    return normalized


def map_vas_codes_to_normalized(
    standard: str,
    *,
    bs_codes: Mapping[str, Any] | None = None,
    is_codes: Mapping[str, Any] | None = None,
    cf_codes: Mapping[str, Any] | None = None,
    unit_scale: int = 1,
) -> dict[str, float | None]:
    """Map TT99/TT200/TT133 indicator codes into the unified normalized statement schema.

    Missing codes remain ``None`` (never implicitly coerced to zero).
    """
    if unit_scale <= 0:
        raise EtlProcessingError(f"Hệ số đơn vị phải là số dương, nhận được {unit_scale}.")

    regime = normalize_vas_regime(standard)
    specs = REGIME_SPECS[regime]
    sections: dict[StatementSection, dict[str, float | None]] = {
        "bs": _normalize_section_map(bs_codes),
        "is": _normalize_section_map(is_codes),
        "cf": _normalize_section_map(cf_codes),
    }

    result: dict[str, float | None] = dict.fromkeys(ALL_STATEMENT_NUMERIC_FIELDS, None)
    selling_exp: float | None = None
    admin_exp: float | None = None

    for item in specs:
        raw_val = sections[item.section].get(item.code)
        if raw_val is None:
            continue
        scaled = raw_val if item.is_per_share else raw_val * float(unit_scale)
        if item.sign_policy == "abs_outflow":
            scaled = abs(scaled)
        if item.field_name == "selling_expenses":
            selling_exp = scaled
        elif item.field_name == "admin_expenses":
            admin_exp = scaled
        else:
            result[item.field_name] = scaled

    # Fallback: if net revenue (10) is absent, accept gross revenue (01) only when present.
    if result["revenues"] is None:
        gross_rev = sections["is"].get("01")
        if gross_rev is not None:
            result["revenues"] = gross_rev * float(unit_scale)

    # Combine selling (25) + G&A (26) into operating_expenses for TT200/TT99.
    if result["operating_expenses"] is None and (selling_exp is not None or admin_exp is not None):
        result["operating_expenses"] = (selling_exp or 0.0) + (admin_exp or 0.0)

    # Derive gross_profit when omitted and both revenues and COGS exist.
    if (
        result["gross_profit"] is None
        and result["revenues"] is not None
        and result["cost_of_goods_sold"] is not None
    ):
        result["gross_profit"] = result["revenues"] - result["cost_of_goods_sold"]

    # Derive EBITDA when omitted and both operating_income and D&A exist.
    if (
        result["ebitda"] is None
        and result["operating_income"] is not None
        and result["depreciation_amortization"] is not None
    ):
        result["ebitda"] = result["operating_income"] + result["depreciation_amortization"]

    return result


def map_normalized_to_vas_codes(
    standard: str,
    statement: Mapping[str, Any],
    *,
    unit_scale: int = 1,
) -> dict[StatementSection, dict[str, float | None]]:
    """Project normalized statement fields back onto official VAS codes for templates."""
    if unit_scale <= 0:
        raise EtlProcessingError(f"Hệ số đơn vị phải là số dương, nhận được {unit_scale}.")
    regime = normalize_vas_regime(standard)
    specs = REGIME_SPECS[regime]
    projected: dict[StatementSection, dict[str, float | None]] = {"bs": {}, "is": {}, "cf": {}}

    opex = _finite(statement.get("operating_expenses"))
    for item in specs:
        if item.field_name == "selling_expenses":
            # When projecting combined operating_expenses into TT200/TT99, place in code 26 (G&A)
            # unless explicit selling_expenses was provided.
            raw = _finite(statement.get("selling_expenses"))
        elif item.field_name == "admin_expenses":
            raw = _finite(statement.get("admin_expenses"))
            if raw is None and _finite(statement.get("selling_expenses")) is None:
                raw = opex
        else:
            raw = _finite(statement.get(item.field_name))

        if raw is None:
            projected[item.section][item.code] = None
        else:
            projected[item.section][item.code] = (
                raw if item.is_per_share else raw / float(unit_scale)
            )
    return projected
