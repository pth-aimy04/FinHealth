"""Strict Pydantic v2 schemas for organization-scoped companies and VN financial statements."""

import math
import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BusinessType = Literal["manufacturing", "trade_service", "financial_institution"]
ListingStatus = Literal["listed", "unlisted"]
RelationshipTag = Literal[
    "own_company", "customer", "supplier", "competitor", "portfolio", "other"
]
AccountingStandardLiteral = Literal["TT99_2025", "TT200_2014", "TT133_2016", "IFRS_USGAAP"]
CurrencyLiteral = Literal["VND", "USD"]
UnitScaleLiteral = Literal[1, 1_000, 1_000_000, 1_000_000_000]
AuditStatusLiteral = Literal[
    "audited_unqualified",
    "audited_qualified",
    "audited_adverse_disclaimer",
    "unaudited",
]
StatementStatusLiteral = Literal["draft", "finalized"]
SourceChannelLiteral = Literal["web_form", "excel_upload", "htkk_xml", "sample"]

FI_EXCLUSION_MESSAGE = (
    "Tổ chức tài chính (Ngân hàng, Bảo hiểm, Chứng khoán, Quỹ) không thuộc phạm vi "
    "chấm điểm của mô hình Altman Z và mô hình ML phi tài chính."
)

_MST_PATTERN = re.compile(r"^\d{10}(?:-\d{3})?$")


class StrictOrgInput(BaseModel):
    """Reject unexpected fields so clients cannot inject organization_id or server flags."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


def _normalize_optional_text(value: str | None) -> str | None:
    """Trim whitespace and normalize empty strings to None."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _validate_tax_code(value: str | None) -> str | None:
    """Validate Vietnamese 10-digit or 13-digit (10-3) tax code (MST) when provided."""
    cleaned = _normalize_optional_text(value)
    if cleaned is None:
        return None
    if not _MST_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "Mã số thuế (MST) phải gồm 10 chữ số hoặc 13 chữ số dạng 0123456789-001."
        )
    return cleaned


def _validate_finite_number(value: float | None) -> float | None:
    """Reject NaN and infinite numeric inputs in financial statement payloads."""
    if value is None:
        return None
    if not math.isfinite(value):
        raise ValueError("Giá trị tài chính phải là số hữu hạn (không chấp nhận NaN/Inf).")
    return float(value)


class OrgCompanyCreateInput(StrictOrgInput):
    """Validated payload to create a private company inside the active organization."""

    name: str = Field(min_length=1, max_length=255)
    tax_code: str | None = Field(default=None, max_length=20)
    ticker: str | None = Field(default=None, max_length=20)
    sector_code: str | None = Field(default=None, max_length=20)
    sector_name: str | None = Field(default=None, max_length=120)
    business_type: BusinessType = "trade_service"
    listing_status: ListingStatus = "unlisted"
    relationship_tag: RelationshipTag = "other"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        """Require a non-blank company name."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Tên doanh nghiệp không được để trống.")
        return cleaned

    @field_validator("tax_code")
    @classmethod
    def check_tax_code(cls, value: str | None) -> str | None:
        """Validate MST format."""
        return _validate_tax_code(value)

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, value: str | None) -> str | None:
        """Normalize ticker symbol to uppercase when provided."""
        cleaned = _normalize_optional_text(value)
        return cleaned.upper() if cleaned is not None else None

    @field_validator("sector_code", "sector_name")
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        """Normalize optional sector metadata."""
        return _normalize_optional_text(value)


class OrgCompanyUpdateInput(StrictOrgInput):
    """Partial update payload for an organization company (including soft-archive)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    tax_code: str | None = Field(default=None, max_length=20)
    ticker: str | None = Field(default=None, max_length=20)
    sector_code: str | None = Field(default=None, max_length=20)
    sector_name: str | None = Field(default=None, max_length=120)
    business_type: BusinessType | None = None
    listing_status: ListingStatus | None = None
    relationship_tag: RelationshipTag | None = None
    archived: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        """Reject blank names on update."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Tên doanh nghiệp không được để trống.")
        return cleaned

    @field_validator("tax_code")
    @classmethod
    def check_tax_code(cls, value: str | None) -> str | None:
        """Validate MST format."""
        return _validate_tax_code(value)

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, value: str | None) -> str | None:
        """Normalize ticker symbol to uppercase when provided."""
        cleaned = _normalize_optional_text(value)
        return cleaned.upper() if cleaned is not None else None

    @field_validator("sector_code", "sector_name")
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        """Normalize optional sector metadata."""
        return _normalize_optional_text(value)


class OrgCompanyResponse(BaseModel):
    """Serialized organization company profile with explicit FI scoring-eligibility flag."""

    id: int
    organization_id: int
    name: str
    tax_code: str | None
    ticker: str | None
    sector_code: str | None
    sector_name: str | None
    business_type: BusinessType
    listing_status: ListingStatus
    relationship_tag: RelationshipTag
    archived: bool
    is_sample: bool
    scoring_eligible: bool
    scoring_exclusion_reason: str | None
    latest_health_score: float | None = None
    latest_risk_tier: str | None = None
    created_at: str
    updated_at: str


class FieldCheckIssueSchema(BaseModel):
    """Single balance-sheet validation error or business warning."""

    code: str
    severity: Literal["error", "warning"]
    field: str
    message: str
    related_fields: list[str] = Field(default_factory=list)
    expected: float | None = None
    actual: float | None = None
    discrepancy: float | None = None


class ValidationReportSchema(BaseModel):
    """Structured balance-sheet validation summary."""

    is_balanced: bool
    errors: list[FieldCheckIssueSchema] = Field(default_factory=list)
    warnings: list[FieldCheckIssueSchema] = Field(default_factory=list)


class OrgStatementInput(StrictOrgInput):
    """Create or upsert a financial statement in draft or finalized status.

    Monetary amounts are provided in ``unit_scale`` units (e.g. 1=VND, 1_000_000=Million VND)
    and normalized internally to base currency units before persistence.
    """

    fiscal_year: int = Field(ge=1990, le=2100)
    fiscal_period: str = Field(default="FY", pattern=r"^(FY|Q[1-4]|H[1-2])$")
    period_end_date: date | None = None
    accounting_standard: AccountingStandardLiteral = "TT99_2025"
    currency: CurrencyLiteral = "VND"
    unit_scale: UnitScaleLiteral = 1
    display_unit: str | None = Field(default=None, max_length=16)
    audit_status: AuditStatusLiteral = "unaudited"
    status: StatementStatusLiteral = "draft"

    total_assets: float | None = None
    current_assets: float | None = None
    cash_and_equivalents: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    total_liabilities: float | None = None
    current_liabilities: float | None = None
    short_term_debt: float | None = None
    long_term_debt: float | None = None
    accounts_payable: float | None = None
    stockholders_equity: float | None = None
    retained_earnings: float | None = None

    revenues: float | None = None
    cost_of_goods_sold: float | None = None
    gross_profit: float | None = None
    operating_expenses: float | None = None
    operating_income: float | None = None
    depreciation_amortization: float | None = None
    ebitda: float | None = None
    interest_expense: float | None = None
    net_income: float | None = None

    operating_cash_flow: float | None = None
    capex: float | None = None
    market_value_equity: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None

    @field_validator(
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
        "eps_basic",
        "eps_diluted",
    )
    @classmethod
    def check_finite(cls, value: float | None) -> float | None:
        """Ensure every provided numeric fact is finite."""
        return _validate_finite_number(value)


class OrgStatementUpdateInput(StrictOrgInput):
    """Partial update for an existing organization financial statement."""

    period_end_date: date | None = None
    accounting_standard: AccountingStandardLiteral | None = None
    currency: CurrencyLiteral | None = None
    unit_scale: UnitScaleLiteral | None = None
    display_unit: str | None = Field(default=None, max_length=16)
    audit_status: AuditStatusLiteral | None = None
    status: StatementStatusLiteral | None = None

    total_assets: float | None = None
    current_assets: float | None = None
    cash_and_equivalents: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    total_liabilities: float | None = None
    current_liabilities: float | None = None
    short_term_debt: float | None = None
    long_term_debt: float | None = None
    accounts_payable: float | None = None
    stockholders_equity: float | None = None
    retained_earnings: float | None = None

    revenues: float | None = None
    cost_of_goods_sold: float | None = None
    gross_profit: float | None = None
    operating_expenses: float | None = None
    operating_income: float | None = None
    depreciation_amortization: float | None = None
    ebitda: float | None = None
    interest_expense: float | None = None
    net_income: float | None = None

    operating_cash_flow: float | None = None
    capex: float | None = None
    market_value_equity: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None

    @field_validator(
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
        "eps_basic",
        "eps_diluted",
    )
    @classmethod
    def check_finite(cls, value: float | None) -> float | None:
        """Ensure every provided numeric fact is finite."""
        return _validate_finite_number(value)


class OrgStatementResponse(BaseModel):
    """Serialized financial statement with normalized base-currency values and validation."""

    id: int
    organization_id: int
    org_company_id: int
    fiscal_year: int
    fiscal_period: str
    period_end_date: date | None
    accounting_standard: str
    currency: str
    unit_scale: int
    display_unit: str
    audit_status: str
    status: str
    source_channel: str

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

    validation: ValidationReportSchema
    ratios: dict[str, Any]
    raw_source_meta: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class SampleCompanySummary(BaseModel):
    """Summary of one seeded Vietnamese sample company."""

    id: int
    name: str
    tax_code: str | None
    business_type: str
    is_sample: bool


class SampleSeedResponse(BaseModel):
    """Idempotent result of seeding the 3 Vietnamese sample companies."""

    created_companies: int
    existing_companies: int
    created_statements: int
    companies: list[SampleCompanySummary]
