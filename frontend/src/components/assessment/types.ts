/**
 * Assessment presentation contracts matching `src/finhealth/api/schemas/analytics.py`.
 * Pure TypeScript types for T18 presentational components.
 */

export type RiskTier = 'STRONG' | 'STABLE' | 'WATCH' | 'CRITICAL';
export type ConfidenceLevel = 'HIGH' | 'MODERATE' | 'LOW';
export type AltmanVariant = 'Z' | "Z'" | "Z''";
export type AltmanZone = 'SAFE' | 'GREY' | 'DISTRESS';
export type PillarKey =
  | 'liquidity'
  | 'solvency'
  | 'profitability'
  | 'efficiency'
  | 'cash_flow';
export type PillarStatus = 'STRONG' | 'ADEQUATE' | 'WEAK' | 'CRITICAL' | 'UNAVAILABLE';
export type MetricUnit = 'ratio' | 'percent' | 'times' | 'days';
export type GoodDirection = 'higher' | 'lower';
export type MetricStatus = 'GOOD' | 'NEUTRAL' | 'WARNING' | 'CRITICAL' | 'UNAVAILABLE';
export type BenchmarkScope = 'sector' | 'universe' | 'unavailable';
export type DriverSide = 'STRENGTH' | 'BOTTLENECK';
export type ImpactStrength = 'VERY_HIGH' | 'HIGH' | 'MODERATE' | 'LOW';

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

export const RISK_TIER_STYLE: Record<
  RiskTier,
  {
    label: string;
    fg: string;
    bg: string;
    ring: string;
    border: string;
  }
> = {
  STRONG: {
    label: 'Vững mạnh',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
    ring: '#0D7A68',
    border: 'rgba(13, 122, 104, 0.28)',
  },
  STABLE: {
    label: 'Ổn định',
    fg: '#1D4ED8',
    bg: 'rgba(37, 99, 235, 0.12)',
    ring: '#2563EB',
    border: 'rgba(37, 99, 235, 0.28)',
  },
  WATCH: {
    label: 'Cần theo dõi sát',
    fg: 'var(--risk-high-fg)',
    bg: 'var(--risk-high-bg)',
    ring: '#D97706',
    border: 'rgba(217, 119, 6, 0.30)',
  },
  CRITICAL: {
    label: 'Nguy cơ khủng hoảng cao',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
    ring: '#BE123C',
    border: 'rgba(190, 18, 60, 0.32)',
  },
};

export const PILLAR_SHORT_LABELS_VI: Record<PillarKey, string> = {
  liquidity: 'Thanh khoản',
  solvency: 'Cơ cấu vốn',
  profitability: 'Sinh lời',
  efficiency: 'Hiệu quả vốn',
  cash_flow: 'Dòng tiền thực',
};

export const CONFIDENCE_META_VI: Record<
  ConfidenceLevel,
  { label: string; fg: string; bg: string }
> = {
  HIGH: {
    label: 'Cao',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
  },
  MODERATE: {
    label: 'Khá',
    fg: 'var(--risk-medium-fg)',
    bg: 'var(--risk-medium-bg)',
  },
  LOW: {
    label: 'Cần lưu ý',
    fg: 'var(--risk-high-fg)',
    bg: 'var(--risk-high-bg)',
  },
};

export function formatAuditStatusVi(status: string | null | undefined): string {
  const key = (status ?? '').toLowerCase();
  switch (key) {
    case 'audited_unqualified':
    case 'audited':
      return 'Đã kiểm toán (Chấp nhận toàn phần)';
    case 'audited_qualified':
      return 'Đã kiểm toán (Ngoại trừ)';
    case 'audited_adverse':
      return 'Đã kiểm toán (Trái ngược / Từ chối)';
    case 'reviewed':
      return 'Đã soát xét';
    case 'unaudited':
      return 'Chưa kiểm toán';
    default:
      return 'Chưa xác định';
  }
}

export function formatStandardShortVi(standard: string | null | undefined): string {
  if (!standard) return '—';
  const normalized = standard.toUpperCase();
  if (normalized.includes('TT99')) return 'TT99/2025';
  if (normalized.includes('TT200')) return 'TT200/2014';
  if (normalized.includes('TT133')) return 'TT133/2016';
  if (normalized.includes('US_GAAP') || normalized.includes('GAAP')) return 'US GAAP';
  if (normalized.includes('IFRS')) return 'IFRS';
  return standard;
}

export function formatScoreVi(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return value.toLocaleString('vi-VN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPctVi(
  ratio: number | null | undefined,
  digits = 2,
  alreadyPercent = false,
): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return '—';
  const pct = alreadyPercent ? ratio : ratio * 100;
  return `${pct.toLocaleString('vi-VN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`;
}

export function formatCompactCurrencyVi(
  value: number | null | undefined,
  currency = 'VND',
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  const cur = currency.toUpperCase();
  if (cur === 'VND') {
    if (abs >= 1e12) {
      return `${sign}${(abs / 1e12).toLocaleString('vi-VN', { maximumFractionDigits: 2 })} nghìn tỷ`;
    }
    if (abs >= 1e9) {
      return `${sign}${(abs / 1e9).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} tỷ`;
    }
    if (abs >= 1e6) {
      return `${sign}${(abs / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} tr`;
    }
    return `${sign}${abs.toLocaleString('vi-VN', { maximumFractionDigits: 0 })} đ`;
  }
  if (abs >= 1e9) {
    return `${sign}$${(abs / 1e9).toLocaleString('en-US', { maximumFractionDigits: 2 })}B`;
  }
  if (abs >= 1e6) {
    return `${sign}$${(abs / 1e6).toLocaleString('en-US', { maximumFractionDigits: 1 })}M`;
  }
  if (abs >= 1e3) {
    return `${sign}$${(abs / 1e3).toLocaleString('en-US', { maximumFractionDigits: 1 })}K`;
  }
  return `${sign}$${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}
