"""Pydantic v2 response contracts for V1.0 corporate risk analytics and org comparison."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from finhealth.etl.altman import AltmanVariant, AltmanZone
from finhealth.etl.driver_narrative import DriverSide, ImpactStrength
from finhealth.etl.metric_catalog import GoodDirection, MetricStatus, MetricUnit, PillarKey
from finhealth.ml.feature_contracts import ConfidenceLevel, RiskTier

LEGAL_DISCLAIMER_VI = (
    "Kết quả đánh giá sức khỏe tài chính và xác suất rủi ro 12 tháng là phân tích định lượng "
    "nội bộ dựa trên mô hình học máy từ dữ liệu lịch sử, không phải dịch vụ xếp hạng tín nhiệm "
    "theo Nghị định 88/2014/NĐ-CP và không thay thế quyết định cấp tín dụng, đầu tư hay "
    "kiểm toán độc lập."
)

PillarStatus = Literal["STRONG", "ADEQUATE", "WEAK", "CRITICAL", "UNAVAILABLE"]
BenchmarkScope = Literal["sector", "universe", "unavailable"]


class ConfidenceView(BaseModel):
    """Four-layer assessment reliability contract."""

    model_config = ConfigDict(from_attributes=True)

    level: ConfidenceLevel
    input_completeness: float = Field(ge=0.0, le=1.0)
    is_ood: bool
    ood_features: list[str] = Field(default_factory=list)
    ensemble_spread: float | None = None
    audit_status: str = "unaudited"
    reasons_vi: list[str] = Field(default_factory=list)


class CashFlowOverlayView(BaseModel):
    """Supplementary cash-flow and audit stress overlay result."""

    model_config = ConfigDict(from_attributes=True)

    triggered: bool = False
    flags: list[str] = Field(default_factory=list)
    reasons_vi: list[str] = Field(default_factory=list)
    original_tier: RiskTier | None = None
    adjusted_tier: RiskTier | None = None


class AssessmentSummaryView(BaseModel):
    """Top-level 3-second executive summary for any evaluated company."""

    model_config = ConfigDict(from_attributes=True)

    scoring_eligible: bool
    scoring_mode: Literal["single_period", "multi_period", "excluded"]
    model_version: str
    health_score: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_tier: RiskTier | None = None
    risk_label_vi: str
    pd_12m: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: ConfidenceView | None = None
    cash_flow_overlay: CashFlowOverlayView | None = None
    top_3_takeaways_vi: list[str] = Field(default_factory=list, max_length=3)
    unavailable_reason_vi: str | None = None
    legal_disclaimer_vi: str = LEGAL_DISCLAIMER_VI


class AltmanView(BaseModel):
    """Altman Z / Z' / Z'' result with explicit dynamic cutoffs."""

    model_config = ConfigDict(from_attributes=True)

    applicable: bool
    variant: AltmanVariant | None = None
    score: float | None = None
    zone: AltmanZone | None = None
    zone_label_vi: str | None = None
    cutoff_low: float | None = None
    cutoff_high: float | None = None
    components: dict[str, float | None] = Field(default_factory=dict)
    fallback_note_vi: str | None = None
    unavailable_reason_vi: str | None = None


class PeerMetricPositionView(BaseModel):
    """Industry benchmark percentile position for one metric (S01)."""

    model_config = ConfigDict(from_attributes=True)

    metric_key: str
    peer_median: float | None = None
    percentile: float | None = None
    n_observed: int = 0
    benchmark_scope: BenchmarkScope = "unavailable"
    position_label_vi: str


class ContextualMetricView(BaseModel):
    """One financial ratio enriched with Vietnamese tooltip, status, YoY, and peer rank."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    pillar: PillarKey
    label_vi: str
    value: float | None = None
    formatted_value_vi: str
    unit: MetricUnit
    good_direction: GoodDirection
    reference_range_vi: str
    tooltip_vi: str
    status: MetricStatus
    score: float | None = None
    yoy_change: float | None = None
    peer_position: PeerMetricPositionView | None = None


class PillarView(BaseModel):
    """One of the five fundamental financial health pillars."""

    model_config = ConfigDict(from_attributes=True)

    key: PillarKey
    label_vi: str
    description_vi: str
    weight: float
    score: float | None = None
    status: PillarStatus
    observed_metrics: int
    total_metrics: int
    metrics: list[ContextualMetricView] = Field(default_factory=list)


class PillarsOverviewView(BaseModel):
    """Five-pillar overview without AAA..CCC agency rating labels."""

    model_config = ConfigDict(from_attributes=True)

    overall_score: float | None = None
    overall_status: PillarStatus
    is_negative_equity: bool = False
    pillars: list[PillarView] = Field(default_factory=list)


class BusinessDriverView(BaseModel):
    """Plain-Vietnamese Strength or Bottleneck card without ML jargon."""

    model_config = ConfigDict(from_attributes=True)

    factor_code: str
    label_vi: str
    pillar: PillarKey
    side: DriverSide
    observed_value: float | None = None
    formatted_value_vi: str
    reference_range_vi: str
    impact_share_pct: float = Field(ge=0.0, le=100.0)
    impact_strength: ImpactStrength
    impact_strength_label_vi: str
    headline_vi: str
    detail_vi: str


class DriversSplitView(BaseModel):
    """Balanced Strengths vs Bottlenecks panel (up to 5 per side)."""

    model_config = ConfigDict(from_attributes=True)

    strengths: list[BusinessDriverView] = Field(default_factory=list, max_length=5)
    bottlenecks: list[BusinessDriverView] = Field(default_factory=list, max_length=5)
    total_impact_share_pct: float = Field(default=0.0, ge=0.0, le=100.5)


class DiagnosticsView(BaseModel):
    """Deterministic accounting diagnostics: DuPont, QoE (C02), and checklist."""

    model_config = ConfigDict(from_attributes=True)

    dupont: dict[str, Any] = Field(default_factory=dict)
    quality_of_earnings: dict[str, Any] = Field(default_factory=dict)
    accounting_checklist: dict[str, Any] = Field(default_factory=dict)


class MultiPeriodHistoryPointView(BaseModel):
    """One annual point in the 3-5 year trajectory seamlessly bridging TT200 -> TT99 (M11)."""

    model_config = ConfigDict(from_attributes=True)

    statement_id: int
    fiscal_year: int
    fiscal_period: str = "FY"
    accounting_standard: str
    currency: str
    audit_status: str
    revenues: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    stockholders_equity: float | None = None
    debt_ratio: float | None = None
    roa: float | None = None
    current_ratio: float | None = None
    altman_variant: AltmanVariant | None = None
    altman_z_score: float | None = None
    altman_zone: AltmanZone | None = None
    health_score: float | None = None
    pd_12m: float | None = None
    risk_tier: RiskTier | None = None


class PeerContextView(BaseModel):
    """Industry cohort positioning summary for S01."""

    model_config = ConfigDict(from_attributes=True)

    benchmark_scope: BenchmarkScope = "unavailable"
    mapped_sector: str | None = None
    cohort_size: int = 0
    summary_label_vi: str
    metrics: dict[str, PeerMetricPositionView] = Field(default_factory=dict)


class OrgCompanyMetaView(BaseModel):
    """Identity header for an organization-scoped company assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    tax_code: str | None = None
    ticker: str | None = None
    sector_code: str | None = None
    sector_name: str | None = None
    business_type: str
    listing_status: str
    relationship_tag: str
    is_sample: bool = False
    fiscal_year: int | None = None
    accounting_standard: str | None = None
    currency: str | None = None


class CompanyAssessmentView(BaseModel):
    """Unified V1.0 assessment contract shared with reporting and UI consumers."""

    model_config = ConfigDict(from_attributes=True)

    company: OrgCompanyMetaView
    summary: AssessmentSummaryView
    altman: AltmanView
    pillars: PillarsOverviewView
    drivers: DriversSplitView
    diagnostics: DiagnosticsView
    history: list[MultiPeriodHistoryPointView] = Field(default_factory=list)
    peer_context: PeerContextView
    legal_disclaimer_vi: str = LEGAL_DISCLAIMER_VI


class OrgCompareCompanyItemView(BaseModel):
    """One company column inside the 2-4 company head-to-head comparison (C03)."""

    model_config = ConfigDict(from_attributes=True)

    company: OrgCompanyMetaView
    fiscal_year: int
    accounting_standard: str
    health_score: float | None = None
    risk_tier: RiskTier | None = None
    risk_label_vi: str
    pd_12m: float | None = None
    altman: AltmanView
    pillar_scores: dict[str, float | None] = Field(default_factory=dict)
    core_metrics: dict[str, float | None] = Field(default_factory=dict)


class OrgCompareResponseView(BaseModel):
    """Head-to-head comparison response for 2-4 companies within one organization workspace."""

    model_config = ConfigDict(from_attributes=True)

    organization_id: int
    requested_ids: list[int]
    period_policy: Literal["latest_finalized", "common_fiscal_year"]
    common_fiscal_year: int | None = None
    active_model_version: str
    companies: list[OrgCompareCompanyItemView] = Field(default_factory=list)
    historical_series: dict[int, list[MultiPeriodHistoryPointView]] = Field(default_factory=dict)
    cohort_medians: dict[str, float | None] = Field(default_factory=dict)
    legal_disclaimer_vi: str = LEGAL_DISCLAIMER_VI
