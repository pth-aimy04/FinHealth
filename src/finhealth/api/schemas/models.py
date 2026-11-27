"""Explicit API contracts with recursive nonfinite-to-null normalization."""

import math
from datetime import date
from numbers import Real
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from finhealth.etl.corporate_finance import RESEARCH_GRADE_LABEL


def sanitize_nonfinite(value: Any) -> Any:
    """Replace nonfinite real numbers recursively while preserving ordinary domain values."""
    if type(value) is float:
        return value if math.isfinite(value) else None
    if value is None or type(value) in (str, int, bool, date):
        return value
    if isinstance(value, dict):
        return {key: sanitize_nonfinite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_nonfinite(item) for item in value]
    if isinstance(value, Real) and not isinstance(value, int):
        return float(value) if math.isfinite(value) else None
    return value


class ApiSchema(BaseModel):
    """Read ORM attributes and normalize every incoming scalar or nested JSON field."""

    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)

    @field_validator("*", mode="before")
    @classmethod
    def finite_values(cls, value: Any) -> Any:
        """Keep nullable financial fields and arbitrary evaluation JSON safe for strict JSON."""
        return sanitize_nonfinite(value)


class CompositeHealthSchema(ApiSchema):
    """A complete-case, cohort-relative internal research score."""

    composite_health_score: float | None = Field(None, ge=0, le=100)
    internal_research_grade: str = "UNSCORED"
    internal_research_grade_label: str = RESEARCH_GRADE_LABEL
    methodology_version: str = "internal_composite_v1.2"
    cohort_scope: Literal["sector", "universe"] = "universe"
    cohort_size: int = 0
    component_percentiles: dict[str, float] = Field(default_factory=dict)


class CompanySummarySchema(CompositeHealthSchema):
    """Identity plus the latest observed metric and prediction snapshot."""

    cik: str
    ticker: str | None = None
    name: str
    sic_code: str | None = None
    sector: str | None = None
    latest_fiscal_year: int | None = None
    latest_period_end_date: date | None = None
    filed_date: date | None = None
    accession_number: str | None = None
    model_version: str | None = None
    roa: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None
    ocf_ratio: float | None = None
    eps: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    operating_margin: float | None = None
    working_capital_ratio: float | None = None
    retained_earnings_ratio: float | None = None
    ebit_to_assets: float | None = None
    asset_turnover: float | None = None
    cash_ratio: float | None = None
    interest_coverage: float | None = None
    fcf_to_liabilities: float | None = None
    altman_z_score: float | None = None
    altman_zone: str | None = None
    cluster_id: int | None = None
    cluster_label: str | None = None
    distress_probability: float | None = None
    risk_level: str | None = None


class HistoricalMetricPointSchema(ApiSchema):
    """A statement period joined to its engineered ratios and optional cluster assignments."""

    fiscal_year: int
    fiscal_period: str
    form_type: str
    period_end_date: date
    accession_number: str | None = None
    filed_date: date | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    stockholders_equity: float | None = None
    revenues: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    retained_earnings: float | None = None
    cash_and_equivalents: float | None = None
    interest_expense: float | None = None
    capex: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None
    cash_ratio: float | None = None
    interest_coverage: float | None = None
    fcf_to_liabilities: float | None = None
    field_provenance: dict[str, dict[str, Any]] | None = None
    roa: float | None = None
    roe: float | None = None
    eps: float | None = None
    debt_ratio: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    operating_margin: float | None = None
    ocf_ratio: float | None = None
    working_capital_ratio: float | None = None
    retained_earnings_ratio: float | None = None
    ebit_to_assets: float | None = None
    asset_turnover: float | None = None
    altman_z_score: float | None = None
    altman_zone: str | None = None
    roa_yoy_delta: float | None = None
    roe_yoy_delta: float | None = None
    debt_ratio_yoy_delta: float | None = None
    ocf_ratio_yoy_delta: float | None = None
    negative_ocf_streak: int = 0
    pca_comp_1: float | None = None
    pca_comp_2: float | None = None
    pca_comp_3: float | None = None
    cluster_id: int | None = None
    cluster_label: str | None = None


class ShapDriverSchema(ApiSchema):
    """One TreeSHAP driver; invalid numeric values are represented as JSON null."""

    feature: str
    feature_value: float | None = None
    shap_value: float | None
    direction: str


class PredictionDetailSchema(ApiSchema):
    """Persisted next-period forecasts and complete raw-margin SHAP attributions."""

    model_version: str
    target_fiscal_year: int
    target_fiscal_period: str
    pred_roa: float | None = None
    pred_roe: float | None = None
    pred_eps: float | None = None
    pred_debt_ratio: float | None = None
    pred_ocf_ratio: float | None = None
    distress_probability: float | None = None
    risk_level: str | None = None
    base_value: float | None = None
    top_drivers: list[ShapDriverSchema] = Field(default_factory=list)
    contributions: dict[str, float | None] = Field(default_factory=dict)
    feature_values: dict[str, float | None] = Field(default_factory=dict)
    output_space: str = "log_odds"
    raw_margin: float | None = None
    raw_probability: float | None = None


class PeerMetricSchema(ApiSchema):
    """Median and empirical midrank percentile of the reported metric."""

    median: float | None
    percentile: float | None = Field(ge=0, le=100)
    n_observed: int


class SectorPeerContextSchema(ApiSchema):
    """Comparison cohort and metric-specific denominators of latest annual snapshots."""

    sector: str | None
    cohort: str
    cohort_size: int
    metrics: dict[str, PeerMetricSchema]


class DupontBridgeSchema(ApiSchema):
    """Shapley contributions to the change in average equity ROE."""

    margin_contribution: float
    turnover_contribution: float
    leverage_contribution: float
    delta_roe_dupont_avg: float


class DupontSchema(ApiSchema):
    """Three-factor characterization of unclipped average equity ROE."""

    net_profit_margin: float | None
    asset_turnover_avg: float | None
    equity_multiplier_avg: float | None
    roe_dupont_avg: float | None
    roe_ending_equity: float | None
    prior_roe_dupont_avg: float | None
    bridge: DupontBridgeSchema | None
    reason: str | None
    bridge_reason: str | None
    basis_note: str


class QualityOfEarningsSchema(ApiSchema):
    """Cash conversion and cash-flow accruals on the disclosed asset basis."""

    cash_conversion_qoe: float | None
    cash_conversion_reason: str | None
    accrual_gap_usd: float | None
    cash_flow_accruals_ratio: float | None
    accruals_basis: Literal["average_assets", "ending_assets"] | None
    accruals_flag: Literal["EARNINGS_AHEAD_OF_CASH_WARNING", "CASH_BACKED_EARNINGS"] | None
    basis_note: str


class AccountingSignalSchema(ApiSchema):
    """A strict comparison with a reported value or a disclosed comparator."""

    status: Literal["PASS", "FAIL", "UNAVAILABLE"]
    current_value: float | None
    prior_value: float | None
    reason: str


class AccountingChecklistSchema(ApiSchema):
    """Observed evidence for the eight accounting signals."""

    signals: dict[str, AccountingSignalSchema]
    observed_passes: int
    observed_checks: int
    pass_ratio: float | None
    basis_note: str


class HealthPillarItemSchema(ApiSchema):
    """One 0-100 fundamental financial health pillar score and status."""

    name: str
    label_vi: str
    score: float | None = None
    status: Literal["STRONG", "ADEQUATE", "WEAK", "CRITICAL", "UNAVAILABLE"] = "UNAVAILABLE"
    observed_metrics: int = 0
    total_metrics: int = 0


class HealthPillarsSchema(ApiSchema):
    """Four-pillar fundamental health breakdown and overall score."""

    overall_score: float | None = None
    overall_grade: str = "UNSCORED"
    pillars: dict[str, HealthPillarItemSchema] = Field(default_factory=dict)


class ActionableRecommendationSchema(ApiSchema):
    """Concrete financial management recommendation derived from SHAP drivers and ratios."""

    priority: Literal["HIGH", "MEDIUM", "LOW"]
    category: Literal["PROFITABILITY", "LIQUIDITY", "SOLVENCY", "CASH_FLOW"]
    feature: str
    current_value: float | None = None
    shap_impact: float | None = None
    target_benchmark: str
    action_vi: str


class CompanyFullAnalysisSchema(ApiSchema):
    """Company identity, chronological history, and latest forecast for the requested form."""

    company: CompanySummarySchema
    history: list[HistoricalMetricPointSchema]
    latest_prediction: PredictionDetailSchema | None = None
    altman_components: dict[str, float | None] = Field(default_factory=dict)
    sector_peer_context: SectorPeerContextSchema | None = None
    dupont: DupontSchema | None = None
    quality_of_earnings: QualityOfEarningsSchema | None = None
    accounting_checklist: AccountingChecklistSchema | None = None
    health_pillars: HealthPillarsSchema | None = None
    recommendations: list[ActionableRecommendationSchema] = Field(default_factory=list)


class CompanyComparisonItemSchema(HistoricalMetricPointSchema, CompositeHealthSchema):
    """An aligned annual comparison column with forecasts matched to the origin."""

    cik: str
    ticker: str | None
    name: str
    sector: str | None
    altman_model_variant: str
    model_version: str | None
    target_fiscal_year: int | None
    distress_probability: float | None
    pred_roa: float | None
    pred_roe: float | None
    pred_eps: float | None
    pred_debt_ratio: float | None
    pred_ocf_ratio: float | None
    dupont: DupontSchema
    quality_of_earnings: QualityOfEarningsSchema


class CompanyComparisonResponseSchema(ApiSchema):
    """Selected issuers, their per-period observations, and descriptive cohort medians."""

    requested_identifiers: list[str]
    period_policy: Literal["latest_annual", "common_fiscal_year"]
    common_fiscal_year: int | None
    active_model_version: str | None
    companies: list[CompanyComparisonItemSchema]
    cohort_medians: dict[str, float | None]
    historical_series: dict[str, list[HistoricalMetricPointSchema]]


class StressScenarioRequestSchema(ApiSchema):
    """Bounded fractional shocks to the selected annual statement."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    revenue_shock_pct: float = Field(0.0, ge=-0.50, le=0.50)
    operating_margin_delta_pct: float = Field(0.0, ge=-0.30, le=0.30)
    debt_change_pct: float = Field(0.0, ge=-0.50, le=1.00)
    ocf_shock_pct: float = Field(0.0, ge=-0.80, le=0.80)


class StressSnapshotSchema(ApiSchema):
    """A single statement, its computed metrics and the resulting model inference."""

    metrics: HistoricalMetricPointSchema
    prediction: PredictionDetailSchema


class ShapShiftSchema(ApiSchema):
    """Scenario minus baseline attribution in raw XGBoost margin units."""

    feature: str
    baseline: float
    stressed: float
    delta: float


class StressSimulationResponseSchema(ApiSchema):
    """Read-only sensitivity comparison and explicit assumptions."""

    cik: str
    baseline: StressSnapshotSchema
    stressed: StressSnapshotSchema
    probability_delta: float
    altman_z_delta: float | None
    cluster_shift: bool
    is_ood_scenario: bool | None
    ood_features: list[str]
    top_shifted_shap_drivers: list[ShapShiftSchema]
    assumptions: tuple[str, ...]


class ClusterPointSchema(ApiSchema):
    """Latest available assigned cluster position for a registrant."""

    cik: str
    ticker: str | None = None
    name: str
    fiscal_year: int
    pca_comp_1: float | None
    pca_comp_2: float | None
    pca_comp_3: float | None
    cluster_id: int
    cluster_label: str
    distress_probability: float | None = None
    altman_z_score: float | None = None


class CompanyScreeningFilters(BaseModel):
    """Validated optional filters applied before snapshot pagination."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    q: str | None = Field(None, max_length=120)
    sector: str | None = Field(None, max_length=120)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    cluster_id: int | None = Field(None, ge=0)
    fiscal_year: int | None = Field(None, ge=1990, le=2100)
    min_roa: float | None = Field(None, allow_inf_nan=False)
    max_debt_ratio: float | None = Field(None, allow_inf_nan=False)
    min_current_ratio: float | None = Field(None, ge=0, allow_inf_nan=False)


class HealthCheckSchema(ApiSchema):
    """Live SQL connectivity and active model state."""

    status: str
    environment: str
    database_connected: bool
    active_model_version: str | None = None
    ingestion_queue_enabled: bool = False


class ModelEvaluationResponseSchema(ApiSchema):
    """Stored evaluation results from a real fitted artifact bundle."""

    model_version: str
    created_at: str
    evaluation_report: dict[str, Any]


class TrainModelRequest(ApiSchema):
    """Train on persisted panel data only, with an explicit time boundary and immutable version."""

    model_config = ConfigDict(extra="forbid")
    train_end_year: int = Field(ge=1990, le=2100)
    model_version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    validation_end_year: int | None = Field(None, ge=1991, le=2100)
    imbalance_strategy: Literal["class_weight", "smote"] = "class_weight"

    @model_validator(mode="after")
    def validate_year_order(self) -> "TrainModelRequest":
        """An explicit validation window must start after the training cutoff."""
        if self.validation_end_year is not None and self.validation_end_year <= self.train_end_year:
            raise ValueError("validation_end_year must be after train_end_year")
        return self


class ModelVersionSummarySchema(ApiSchema):
    """Metadata summary for one persisted model artifact bundle."""

    model_version: str
    created_at: str
    is_active: bool
    dataset: str
    selected_model_name: str | None = None
    imbalance_strategy: str | None = None


class ManualStatementInputSchema(BaseModel):
    """User-supplied financial statement figures for stateless distress scoring and TreeSHAP."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    model_version: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    )
    company_name: str = Field(default="Doanh nghiệp tự nhập", min_length=1, max_length=120)
    fiscal_year: int = Field(default=2025, ge=1990, le=2100)
    is_manufacturing: bool = True
    total_assets: float = Field(..., gt=0)
    current_assets: float | None = Field(default=None, ge=0)
    total_liabilities: float = Field(..., ge=0)
    current_liabilities: float | None = Field(default=None, ge=0)
    stockholders_equity: float | None = None
    retained_earnings: float | None = None
    revenues: float | None = Field(default=None, ge=0)
    operating_income: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    cash_and_equivalents: float | None = Field(default=None, ge=0)
    interest_expense: float | None = Field(default=None, ge=0)
    capex: float | None = Field(default=None, ge=0)
    eps_diluted: float | None = None
    prior_total_assets: float | None = Field(default=None, gt=0)
    prior_current_assets: float | None = Field(default=None, ge=0)
    prior_total_liabilities: float | None = Field(default=None, ge=0)
    prior_current_liabilities: float | None = Field(default=None, ge=0)
    prior_stockholders_equity: float | None = None
    prior_revenues: float | None = Field(default=None, ge=0)
    prior_operating_income: float | None = None
    prior_net_income: float | None = None
    prior_operating_cash_flow: float | None = None


class ManualPredictionResponseSchema(ApiSchema):
    """Stateless manual-input prediction, Altman breakdown, PCA regime and TreeSHAP output."""

    company_name: str
    fiscal_year: int
    is_manufacturing: bool
    ratios: dict[str, float | None]
    altman_z_score: float | None = None
    altman_zone: str | None = None
    altman_components: dict[str, float | None] = Field(default_factory=dict)
    cluster_id: int | None = None
    cluster_label: str | None = None
    prediction: PredictionDetailSchema
    classification_threshold: float | None = None
    is_ood_scenario: bool | None = None
    ood_features: list[str] = Field(default_factory=list)
    health_pillars: HealthPillarsSchema | None = None
    dupont: DupontSchema | None = None
    quality_of_earnings: QualityOfEarningsSchema | None = None
    accounting_checklist: AccountingChecklistSchema | None = None
    recommendations: list[ActionableRecommendationSchema] = Field(default_factory=list)


class BatchPredictionRequestSchema(BaseModel):
    """Batch portfolio prediction request for up to 200 corporate financial statements."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    model_version: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    )
    items: list[ManualStatementInputSchema] = Field(..., min_length=1, max_length=200)


class BatchPredictionItemSchema(ApiSchema):
    """Per-company summary row in a batch portfolio risk assessment."""

    company_name: str
    fiscal_year: int
    is_manufacturing: bool
    distress_probability: float | None = None
    risk_level: str | None = None
    overall_health_score: float | None = None
    overall_health_grade: str = "UNSCORED"
    altman_z_score: float | None = None
    altman_zone: str | None = None
    cluster_id: int | None = None
    cluster_label: str | None = None
    roa: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None
    current_ratio: float | None = None
    ocf_ratio: float | None = None
    top_risk_driver: str | None = None
    top_recommendation_vi: str | None = None


class BatchPredictionResponseSchema(ApiSchema):
    """Aggregated portfolio risk distribution and per-company scoring results."""

    model_version: str
    classification_threshold: float | None = None
    total_companies: int
    risk_counts: dict[str, int] = Field(default_factory=dict)
    average_distress_probability: float | None = None
    average_health_score: float | None = None
    results: list[BatchPredictionItemSchema] = Field(default_factory=list)
