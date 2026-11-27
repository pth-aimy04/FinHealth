/** TypeScript contracts matching FastAPI Pydantic schemas under /api/v1. */

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface HealthCheck {
  status: string;
  environment: string;
  database_connected: boolean;
  active_model_version?: string | null;
  ingestion_queue_enabled?: boolean;
}

export interface DashboardOverview {
  company_count: number;
  annual_statement_count: number;
}

export interface DataQuality {
  report_count: number;
  observed: Record<string, number>;
}

export interface CompositeHealth {
  composite_health_score: number | null;
  internal_research_grade: string;
  internal_research_grade_label: string;
  methodology_version: string;
  cohort_scope: 'sector' | 'universe';
  cohort_size: number;
  component_percentiles: Record<string, number>;
}

export interface CompanySummary extends CompositeHealth {
  cik: string;
  ticker: string | null;
  name: string;
  sic_code: string | null;
  sector: string | null;
  latest_fiscal_year: number | null;
  latest_period_end_date: string | null;
  filed_date: string | null;
  accession_number: string | null;
  model_version: string | null;
  roa: number | null;
  roe: number | null;
  debt_ratio: number | null;
  ocf_ratio: number | null;
  eps: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  operating_margin: number | null;
  working_capital_ratio: number | null;
  retained_earnings_ratio: number | null;
  ebit_to_assets: number | null;
  asset_turnover: number | null;
  cash_ratio: number | null;
  interest_coverage: number | null;
  fcf_to_liabilities: number | null;
  altman_z_score: number | null;
  altman_zone: string | null;
  cluster_id: number | null;
  cluster_label: string | null;
  distress_probability: number | null;
  risk_level: string | null;
}

export interface HistoricalMetricPoint {
  fiscal_year: number;
  fiscal_period: string;
  form_type: string;
  period_end_date: string;
  accession_number: string | null;
  filed_date: string | null;
  total_assets: number | null;
  total_liabilities: number | null;
  stockholders_equity: number | null;
  revenues: number | null;
  operating_income: number | null;
  net_income: number | null;
  operating_cash_flow: number | null;
  current_assets: number | null;
  current_liabilities: number | null;
  retained_earnings: number | null;
  cash_and_equivalents: number | null;
  interest_expense: number | null;
  capex: number | null;
  eps_basic: number | null;
  eps_diluted: number | null;
  cash_ratio: number | null;
  interest_coverage: number | null;
  fcf_to_liabilities: number | null;
  field_provenance?: Record<string, Record<string, unknown>> | null;
  roa: number | null;
  roe: number | null;
  eps: number | null;
  debt_ratio: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  operating_margin: number | null;
  ocf_ratio: number | null;
  working_capital_ratio: number | null;
  retained_earnings_ratio: number | null;
  ebit_to_assets: number | null;
  asset_turnover: number | null;
  altman_z_score: number | null;
  altman_zone: string | null;
  roa_yoy_delta: number | null;
  roe_yoy_delta: number | null;
  debt_ratio_yoy_delta: number | null;
  ocf_ratio_yoy_delta: number | null;
  negative_ocf_streak: number;
  pca_comp_1: number | null;
  pca_comp_2: number | null;
  pca_comp_3: number | null;
  cluster_id: number | null;
  cluster_label: string | null;
}

export interface ShapDriver {
  feature: string;
  feature_value: number | null;
  shap_value: number | null;
  direction: string;
}

export interface PredictionDetail {
  model_version: string;
  target_fiscal_year: number;
  target_fiscal_period: string;
  pred_roa: number | null;
  pred_roe: number | null;
  pred_eps: number | null;
  pred_debt_ratio: number | null;
  pred_ocf_ratio: number | null;
  distress_probability: number | null;
  risk_level: string | null;
  base_value: number | null;
  top_drivers: ShapDriver[];
  contributions: Record<string, number | null>;
  feature_values: Record<string, number | null>;
  output_space: string;
  raw_margin: number | null;
  raw_probability: number | null;
}

export interface PeerMetric {
  median: number | null;
  percentile: number | null;
  n_observed: number;
}

export interface SectorPeerContext {
  sector: string | null;
  cohort: string;
  cohort_size: number;
  metrics: Record<string, PeerMetric>;
}

export interface DupontBridge {
  margin_contribution: number;
  turnover_contribution: number;
  leverage_contribution: number;
  delta_roe_dupont_avg: number;
}

export interface Dupont {
  net_profit_margin: number | null;
  asset_turnover_avg: number | null;
  equity_multiplier_avg: number | null;
  roe_dupont_avg: number | null;
  roe_ending_equity: number | null;
  prior_roe_dupont_avg: number | null;
  bridge: DupontBridge | null;
  reason: string | null;
  bridge_reason: string | null;
  basis_note: string;
}

export interface QualityOfEarnings {
  cash_conversion_qoe: number | null;
  cash_conversion_reason: string | null;
  accrual_gap_usd: number | null;
  cash_flow_accruals_ratio: number | null;
  accruals_basis: 'average_assets' | 'ending_assets' | null;
  accruals_flag: 'EARNINGS_AHEAD_OF_CASH_WARNING' | 'CASH_BACKED_EARNINGS' | null;
  basis_note: string;
}

export interface AccountingSignal {
  status: 'PASS' | 'FAIL' | 'UNAVAILABLE';
  current_value: number | null;
  prior_value: number | null;
  reason: string;
}

export interface AccountingChecklist {
  signals: Record<string, AccountingSignal>;
  observed_passes: number;
  observed_checks: number;
  pass_ratio: number | null;
  basis_note: string;
}

export interface HealthPillarItem {
  name: string;
  label_vi: string;
  score: number | null;
  status: 'STRONG' | 'ADEQUATE' | 'WEAK' | 'CRITICAL' | 'UNAVAILABLE';
  observed_metrics: number;
  total_metrics: number;
}

export interface HealthPillars {
  overall_score: number | null;
  overall_grade: string;
  pillars: Record<string, HealthPillarItem>;
}

export interface ActionableRecommendation {
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  category: 'PROFITABILITY' | 'LIQUIDITY' | 'SOLVENCY' | 'CASH_FLOW';
  feature: string;
  current_value: number | null;
  shap_impact: number | null;
  target_benchmark: string;
  action_vi: string;
}

export interface CompanyFullAnalysis {
  company: CompanySummary;
  history: HistoricalMetricPoint[];
  latest_prediction: PredictionDetail | null;
  altman_components: Record<string, number | null>;
  sector_peer_context: SectorPeerContext | null;
  dupont: Dupont | null;
  quality_of_earnings: QualityOfEarnings | null;
  accounting_checklist: AccountingChecklist | null;
  health_pillars: HealthPillars | null;
  recommendations: ActionableRecommendation[];
}

export interface CompanyComparisonItem extends HistoricalMetricPoint, CompositeHealth {
  cik: string;
  ticker: string | null;
  name: string;
  sector: string | null;
  altman_model_variant: string;
  model_version: string | null;
  target_fiscal_year: number | null;
  distress_probability: number | null;
  pred_roa: number | null;
  pred_roe: number | null;
  pred_eps: number | null;
  pred_debt_ratio: number | null;
  pred_ocf_ratio: number | null;
  dupont: Dupont;
  quality_of_earnings: QualityOfEarnings;
}

export interface CompanyComparisonResponse {
  requested_identifiers: string[];
  period_policy: 'latest_annual' | 'common_fiscal_year';
  common_fiscal_year: number | null;
  active_model_version: string | null;
  companies: CompanyComparisonItem[];
  cohort_medians: Record<string, number | null>;
  historical_series: Record<string, HistoricalMetricPoint[]>;
}

export interface ClusterPoint {
  cik: string;
  ticker: string | null;
  name: string;
  fiscal_year: number;
  pca_comp_1: number | null;
  pca_comp_2: number | null;
  pca_comp_3: number | null;
  cluster_id: number;
  cluster_label: string;
  distress_probability: number | null;
  altman_z_score: number | null;
}

export interface StressScenarioRequest {
  revenue_shock_pct: number;
  operating_margin_delta_pct: number;
  debt_change_pct: number;
  ocf_shock_pct: number;
}

export interface StressSnapshot {
  metrics: HistoricalMetricPoint;
  prediction: PredictionDetail;
}

export interface ShapShift {
  feature: string;
  baseline: number;
  stressed: number;
  delta: number;
}

export interface StressSimulationResponse {
  cik: string;
  baseline: StressSnapshot;
  stressed: StressSnapshot;
  probability_delta: number;
  altman_z_delta: number | null;
  cluster_shift: boolean;
  is_ood_scenario: boolean | null;
  ood_features: string[];
  top_shifted_shap_drivers: ShapShift[];
  assumptions: string[];
}

export interface ModelVersionSummary {
  model_version: string;
  created_at: string;
  is_active: boolean;
  dataset: string;
  selected_model_name: string | null;
  imbalance_strategy: string | null;
}

export interface ModelEvaluationResponse {
  model_version: string;
  created_at: string;
  evaluation_report: Record<string, unknown>;
}

export interface ManualStatementInput {
  model_version?: string | null;
  company_name: string;
  fiscal_year: number;
  is_manufacturing: boolean;
  total_assets: number;
  current_assets?: number | null;
  total_liabilities: number;
  current_liabilities?: number | null;
  stockholders_equity?: number | null;
  retained_earnings?: number | null;
  revenues?: number | null;
  operating_income?: number | null;
  net_income?: number | null;
  operating_cash_flow?: number | null;
  cash_and_equivalents?: number | null;
  interest_expense?: number | null;
  capex?: number | null;
  eps_diluted?: number | null;
}

export interface ManualPredictionResponse {
  company_name: string;
  fiscal_year: number;
  is_manufacturing: boolean;
  ratios: Record<string, number | null>;
  altman_z_score: number | null;
  altman_zone: string | null;
  altman_components: Record<string, number | null>;
  cluster_id: number | null;
  cluster_label: string | null;
  prediction: PredictionDetail;
  classification_threshold: number | null;
  is_ood_scenario: boolean | null;
  ood_features: string[];
  health_pillars: HealthPillars | null;
  dupont: Dupont | null;
  quality_of_earnings: QualityOfEarnings | null;
  accounting_checklist: AccountingChecklist | null;
  recommendations: ActionableRecommendation[];
}

export interface BatchPredictionItem {
  company_name: string;
  fiscal_year: number;
  is_manufacturing: boolean;
  distress_probability: number | null;
  risk_level: string | null;
  overall_health_score: number | null;
  overall_health_grade: string;
  altman_z_score: number | null;
  altman_zone: string | null;
  cluster_id: number | null;
  cluster_label: string | null;
  roa: number | null;
  roe: number | null;
  debt_ratio: number | null;
  current_ratio: number | null;
  ocf_ratio: number | null;
  top_risk_driver: string | null;
  top_recommendation_vi: string | null;
}

export interface BatchPredictionResponse {
  model_version: string;
  classification_threshold: number | null;
  total_companies: number;
  risk_counts: Record<string, number>;
  average_distress_probability: number | null;
  average_health_score: number | null;
  results: BatchPredictionItem[];
}

export interface FilingVersion {
  id: number;
  issuer_key: string;
  accession: string;
  form_type: string;
  scope: string;
  fiscal_year: number;
  fiscal_period: string;
  period_end: string;
  published_on: string;
  captured_at: string;
  capture_kind: string;
  source_url: string | null;
  fingerprint: string;
  values: Record<string, number | null>;
  provenance: Record<string, Record<string, unknown>>;
  missing_reasons: Record<string, string>;
  ratios: Record<string, number | null>;
  accounting_framework?: string | null;
  audit_status?: string | null;
  issuer_name?: string | null;
}

export interface ReportResponse {
  issuer_key: string;
  as_of: string | null;
  versions: FilingVersion[];
  quarterly_series: Array<{
    fiscal_year: number;
    fiscal_period: 'Q1' | 'Q2' | 'Q3' | 'Q4';
    period_end: string;
    flows: Record<string, { value: number | null; yoy_growth: number | null; ttm: number | null }>;
  }>;
}

export interface ReportAlert {
  rule: string;
  rule_version: number;
  previous_filing_id: number;
  filing_id: number;
  published_on: string;
  changed_fields: string[];
  source_url: string | null;
}

export interface ForecastEvidence {
  id: number;
  filing_version_id: number;
  model_version: string;
  input_status: 'verified_inputs' | 'legacy_unverified';
  reported_inputs: Record<string, number | null> | null;
  fitted_inputs: Record<string, number> | null;
  outputs: Record<string, unknown>;
  fingerprint: string;
}

export interface PublicUser {
  id: number;
  email: string;
  display_name: string;
  job_title?: string | null;
  role: 'user' | 'admin' | string;
  active: boolean;
  email_verified: boolean;
}

export type OrgRole = 'viewer' | 'analyst' | 'org_admin';

export interface OrganizationSummary {
  id: number;
  name: string;
  slug: string;
  is_personal: boolean;
  role: OrgRole;
  member_count: number;
  is_active_workspace: boolean;
  created_at: string;
}

export interface OrganizationDetail {
  id: number;
  name: string;
  slug: string;
  is_personal: boolean;
  role: OrgRole;
  member_count: number;
  created_at: string;
}

export interface OrganizationSwitchResponse {
  active_org_id: number;
  organization: {
    id: number;
    name: string;
    slug: string;
    is_personal: boolean;
    role: OrgRole;
  };
}

export interface OrganizationMember {
  user_id: number;
  email: string;
  display_name: string;
  job_title: string | null;
  role: OrgRole;
  joined_at: string;
}

export interface OrganizationInvite {
  id: number;
  organization_id: number;
  email: string;
  role: OrgRole;
  invited_by: number | null;
  expires_at: string;
  created_at: string;
}

export interface OrganizationInviteCreated {
  id: number;
  organization_id: number;
  email: string;
  role: OrgRole;
  token: string;
  email_sent: boolean;
  expires_at: string;
}

export interface OrganizationInviteAcceptResponse {
  organization_id: number;
  organization_name: string;
  role: OrgRole;
}

export interface OrganizationAuditEntry {
  id: number;
  organization_id: number;
  actor_id: number | null;
  action: string;
  target: string;
  outcome: string;
  created_at: string;
}

export interface UserDataExport {
  exported_at: string;
  profile: PublicUser & { created_at: string; updated_at: string };
  organizations: Array<{
    organization_id: number;
    name: string;
    slug: string;
    is_personal: boolean;
    role: OrgRole;
    joined_at: string;
  }>;
  sessions: Array<{
    id: number;
    active_org_id: number | null;
    created_at: string;
    expires_at: string;
    revoked_at: string | null;
  }>;
  workspace: {
    watchlist: Array<{
      id: number;
      organization_id: number;
      company_id: number;
      created_at: string;
    }>;
    screeners: Array<{
      id: number;
      organization_id: number;
      name: string;
      filters: Record<string, unknown>;
    }>;
    analyses: Array<{
      id: number;
      organization_id: number;
      name: string;
      model_version: string;
      created_at: string;
    }>;
  };
  activity_logs: {
    organization_audit_logs: Array<{
      id: number;
      organization_id: number;
      action: string;
      target: string;
      outcome: string;
      created_at: string;
    }>;
    admin_audit_logs: Array<{
      id: number;
      action: string;
      target: string;
      outcome: string;
      created_at: string;
    }>;
  };
}

// =============================================================================
// V1.0 Organization Companies & Multi-Standard VN Financial Statements
// =============================================================================

export type BusinessType = 'manufacturing' | 'trade_service' | 'financial_institution';
export type ListingStatus = 'listed' | 'unlisted';
export type RelationshipTag =
  | 'own_company'
  | 'customer'
  | 'supplier'
  | 'competitor'
  | 'portfolio'
  | 'other';
export type AccountingStandard = 'TT99_2025' | 'TT200_2014' | 'TT133_2016' | 'IFRS_USGAAP';
export type CurrencyCode = 'VND' | 'USD';
export type UnitScale = 1 | 1_000 | 1_000_000 | 1_000_000_000;
export type AuditStatus =
  | 'audited_unqualified'
  | 'audited_qualified'
  | 'audited_adverse_disclaimer'
  | 'unaudited';
export type StatementStatus = 'draft' | 'finalized';
export type SourceChannel = 'web_form' | 'excel_upload' | 'htkk_xml' | 'sample';

export interface OrgCompany {
  id: number;
  organization_id: number;
  name: string;
  tax_code: string | null;
  ticker: string | null;
  sector_code: string | null;
  sector_name: string | null;
  business_type: BusinessType;
  listing_status: ListingStatus;
  relationship_tag: RelationshipTag;
  archived: boolean;
  is_sample: boolean;
  scoring_eligible: boolean;
  scoring_exclusion_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrgCompanyCreateInput {
  name: string;
  tax_code?: string | null;
  ticker?: string | null;
  sector_code?: string | null;
  sector_name?: string | null;
  business_type?: BusinessType;
  listing_status?: ListingStatus;
  relationship_tag?: RelationshipTag;
}

export interface OrgCompanyUpdateInput {
  name?: string | null;
  tax_code?: string | null;
  ticker?: string | null;
  sector_code?: string | null;
  sector_name?: string | null;
  business_type?: BusinessType | null;
  listing_status?: ListingStatus | null;
  relationship_tag?: RelationshipTag | null;
  archived?: boolean | null;
}

export interface FieldCheckIssue {
  code: string;
  severity: 'error' | 'warning';
  field: string;
  message: string;
  related_fields: string[];
  expected?: number | null;
  actual?: number | null;
  discrepancy?: number | null;
}

export interface ValidationReport {
  is_balanced: boolean;
  errors: FieldCheckIssue[];
  warnings: FieldCheckIssue[];
}

export interface OrgStatementNumericFields {
  total_assets?: number | null;
  current_assets?: number | null;
  cash_and_equivalents?: number | null;
  accounts_receivable?: number | null;
  inventory?: number | null;
  total_liabilities?: number | null;
  current_liabilities?: number | null;
  short_term_debt?: number | null;
  long_term_debt?: number | null;
  accounts_payable?: number | null;
  stockholders_equity?: number | null;
  retained_earnings?: number | null;
  revenues?: number | null;
  cost_of_goods_sold?: number | null;
  gross_profit?: number | null;
  operating_expenses?: number | null;
  operating_income?: number | null;
  depreciation_amortization?: number | null;
  ebitda?: number | null;
  interest_expense?: number | null;
  net_income?: number | null;
  operating_cash_flow?: number | null;
  capex?: number | null;
  market_value_equity?: number | null;
  eps_basic?: number | null;
  eps_diluted?: number | null;
}

export interface OrgStatementInput extends OrgStatementNumericFields {
  fiscal_year: number;
  fiscal_period?: string;
  period_end_date?: string | null;
  accounting_standard?: AccountingStandard;
  currency?: CurrencyCode;
  unit_scale?: UnitScale;
  display_unit?: string | null;
  audit_status?: AuditStatus;
  status?: StatementStatus;
}

export interface OrgStatementUpdateInput extends OrgStatementNumericFields {
  period_end_date?: string | null;
  accounting_standard?: AccountingStandard | null;
  currency?: CurrencyCode | null;
  unit_scale?: UnitScale | null;
  display_unit?: string | null;
  audit_status?: AuditStatus | null;
  status?: StatementStatus | null;
}

export interface OrgStatement extends Required<{ [K in keyof OrgStatementNumericFields]: number | null }> {
  id: number;
  organization_id: number;
  org_company_id: number;
  fiscal_year: number;
  fiscal_period: string;
  period_end_date: string | null;
  accounting_standard: AccountingStandard | string;
  currency: CurrencyCode | string;
  unit_scale: UnitScale | number;
  display_unit: string;
  audit_status: AuditStatus | string;
  status: StatementStatus | string;
  source_channel: SourceChannel | string;
  validation: ValidationReport;
  ratios: Record<string, number | boolean | null>;
  raw_source_meta?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface SampleCompanySummary {
  id: number;
  name: string;
  tax_code: string | null;
  business_type: string;
  is_sample: boolean;
}

export interface SampleSeedResponse {
  created_companies: number;
  existing_companies: number;
  created_statements: number;
  companies: SampleCompanySummary[];
}

// =============================================================================
// V1.0 Corporate Risk Analytics, 5 Pillars, Drivers & Org Comparison
// =============================================================================

export type RiskTier = 'STRONG' | 'STABLE' | 'WATCH' | 'CRITICAL';
export type ConfidenceLevel = 'HIGH' | 'MODERATE' | 'LOW';
export type AltmanVariant = 'Z' | 'Z_PRIME' | 'Z_DOUBLE_PRIME';
export type AltmanZone = 'SAFE' | 'GREY' | 'DISTRESS';
export type PillarKey = 'liquidity' | 'solvency' | 'profitability' | 'cash_flow' | 'efficiency';
export type PillarStatus = 'STRONG' | 'ADEQUATE' | 'WEAK' | 'CRITICAL' | 'UNAVAILABLE';
export type MetricStatus = 'GOOD' | 'WARNING' | 'CRITICAL' | 'UNAVAILABLE';
export type MetricUnit = 'percent' | 'ratio' | 'days' | 'multiple';
export type GoodDirection = 'higher' | 'lower';
export type DriverSide = 'strength' | 'bottleneck';
export type ImpactStrength = 'high' | 'medium' | 'low';
export type BenchmarkScope = 'sector' | 'universe' | 'unavailable';

export interface ConfidenceView {
  level: ConfidenceLevel;
  input_completeness: number;
  is_ood: boolean;
  ood_features: string[];
  ensemble_spread: number | null;
  audit_status: string;
  reasons_vi: string[];
}

export interface CashFlowOverlayView {
  triggered: boolean;
  flags: string[];
  reasons_vi: string[];
  original_tier: RiskTier | null;
  adjusted_tier: RiskTier | null;
}

export interface AssessmentSummaryView {
  scoring_eligible: boolean;
  scoring_mode: 'single_period' | 'multi_period' | 'excluded';
  model_version: string;
  health_score: number | null;
  risk_tier: RiskTier | null;
  risk_label_vi: string;
  pd_12m: number | null;
  confidence: ConfidenceView | null;
  cash_flow_overlay: CashFlowOverlayView | null;
  top_3_takeaways_vi: string[];
  unavailable_reason_vi: string | null;
  legal_disclaimer_vi: string;
}

export interface AltmanView {
  applicable: boolean;
  variant: AltmanVariant | null;
  score: number | null;
  zone: AltmanZone | null;
  zone_label_vi: string | null;
  cutoff_low: number | null;
  cutoff_high: number | null;
  components: Record<string, number | null>;
  fallback_note_vi: string | null;
  unavailable_reason_vi: string | null;
}

export interface PeerMetricPositionView {
  metric_key: string;
  peer_median: number | null;
  percentile: number | null;
  n_observed: number;
  benchmark_scope: BenchmarkScope;
  position_label_vi: string;
}

export interface ContextualMetricView {
  key: string;
  pillar: PillarKey;
  label_vi: string;
  value: number | null;
  formatted_value_vi: string;
  unit: MetricUnit;
  good_direction: GoodDirection;
  reference_range_vi: string;
  tooltip_vi: string;
  status: MetricStatus;
  score: number | null;
  yoy_change: number | null;
  peer_position: PeerMetricPositionView | null;
}

export interface PillarView {
  key: PillarKey;
  label_vi: string;
  description_vi: string;
  weight: number;
  score: number | null;
  status: PillarStatus;
  observed_metrics: number;
  total_metrics: number;
  metrics: ContextualMetricView[];
}

export interface PillarsOverviewView {
  overall_score: number | null;
  overall_status: PillarStatus;
  is_negative_equity: boolean;
  pillars: PillarView[];
}

export interface BusinessDriverView {
  factor_code: string;
  label_vi: string;
  pillar: PillarKey;
  side: DriverSide;
  observed_value: number | null;
  formatted_value_vi: string;
  reference_range_vi: string;
  impact_share_pct: number;
  impact_strength: ImpactStrength;
  impact_strength_label_vi: string;
  headline_vi: string;
  detail_vi: string;
}

export interface DriversSplitView {
  strengths: BusinessDriverView[];
  bottlenecks: BusinessDriverView[];
  total_impact_share_pct: number;
}

export interface DiagnosticsView {
  dupont: Record<string, unknown>;
  quality_of_earnings: Record<string, unknown>;
  accounting_checklist: Record<string, unknown>;
}

export interface MultiPeriodHistoryPointView {
  statement_id: number;
  fiscal_year: number;
  fiscal_period: string;
  accounting_standard: string;
  currency: string;
  audit_status: string;
  revenues: number | null;
  net_income: number | null;
  operating_cash_flow: number | null;
  total_assets: number | null;
  total_liabilities: number | null;
  stockholders_equity: number | null;
  debt_ratio: number | null;
  roa: number | null;
  current_ratio: number | null;
  altman_variant: AltmanVariant | null;
  altman_z_score: number | null;
  altman_zone: AltmanZone | null;
  health_score: number | null;
  pd_12m: number | null;
  risk_tier: RiskTier | null;
}

export interface PeerContextView {
  benchmark_scope: BenchmarkScope;
  mapped_sector: string | null;
  cohort_size: number;
  summary_label_vi: string;
  metrics: Record<string, PeerMetricPositionView>;
}

export interface OrgCompanyMetaView {
  id: number;
  organization_id: number;
  name: string;
  tax_code: string | null;
  ticker: string | null;
  sector_code: string | null;
  sector_name: string | null;
  business_type: string;
  listing_status: string;
  relationship_tag: string;
  is_sample: boolean;
  fiscal_year: number | null;
  accounting_standard: string | null;
  currency: string | null;
}

export interface CompanyAssessmentView {
  company: OrgCompanyMetaView;
  summary: AssessmentSummaryView;
  altman: AltmanView;
  pillars: PillarsOverviewView;
  drivers: DriversSplitView;
  diagnostics: DiagnosticsView;
  history: MultiPeriodHistoryPointView[];
  peer_context: PeerContextView;
  legal_disclaimer_vi: string;
}

export interface OrgCompareCompanyItemView {
  company: OrgCompanyMetaView;
  fiscal_year: number;
  accounting_standard: string;
  health_score: number | null;
  risk_tier: RiskTier | null;
  risk_label_vi: string;
  pd_12m: number | null;
  altman: AltmanView;
  pillar_scores: Record<string, number | null>;
  core_metrics: Record<string, number | null>;
}

export interface OrgCompareResponseView {
  organization_id: number;
  requested_ids: number[];
  period_policy: 'latest_finalized' | 'common_fiscal_year';
  common_fiscal_year: number | null;
  active_model_version: string;
  companies: OrgCompareCompanyItemView[];
  historical_series: Record<string, MultiPeriodHistoryPointView[]>;
  cohort_medians: Record<string, number | null>;
  legal_disclaimer_vi: string;
}

// =============================================================================
// V1.0 Asynchronous Batch Excel Jobs (S03)
// =============================================================================

export type BatchJobStatus = 'queued' | 'running' | 'completed' | 'failed';
export type BatchRowStatus = 'pending' | 'succeeded' | 'failed' | 'excluded';

export interface BatchJobSummary {
  id: number;
  organization_id: number;
  created_by?: number | null;
  filename: string;
  status: BatchJobStatus;
  model_version: string | null;
  total_rows: number;
  processed_rows: number;
  succeeded_rows: number;
  failed_rows: number;
  error_message: string | null;
  summary: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface BatchJobRowResult {
  id: number;
  row_index: number;
  risk_rank?: number | null;
  company_name: string;
  tax_code: string | null;
  fiscal_year: number | null;
  status: BatchRowStatus;
  pd_12m: number | null;
  health_score: number | null;
  risk_tier: RiskTier | null;
  confidence_level: ConfidenceLevel | null;
  top_bottleneck_vi: string | null;
  error_message: string | null;
  result_meta?: Record<string, unknown> | null;
}

export interface BatchJobDetail extends BatchJobSummary {
  rows: BatchJobRowResult[];
  legal_disclaimer_vi?: string;
}

export interface WatchlistEntry {
  id: number;
  cik: string;
  ticker: string | null;
  name: string;
}

export interface SavedScreenerEntry {
  id: number;
  name: string;
  filters: Record<string, string | number | null>;
}

export interface SavedAnalysisSummary {
  id: number;
  name: string;
  model_version: string;
  created_at: string;
}

export interface AdminOverview {
  database_connected: boolean;
  worker_enabled: boolean;
  counts: Record<string, number>;
  last_success: string | null;
  email_configured: boolean;
}

export interface IngestionJob {
  id: number;
  identifier: string;
  status: string;
  stage: string;
  error_message?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  requested_by_name?: string | null;
  requested_by_email?: string | null;
}

export interface IngestionEvent {
  stage: string;
  message: string;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  actor_id: number;
  action: string;
  target: string;
  outcome: string;
  created_at: string;
}
