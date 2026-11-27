/** Bộ định dạng số liệu và từ điển chuẩn tài chính tiếng Việt (bảo toàn null/NaN -> '—'). */

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (!isFiniteNumber(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatRatio(value: number | null | undefined, digits = 2): string {
  if (!isFiniteNumber(value)) return '—';
  return value.toFixed(digits);
}

export function formatSigned(value: number | null | undefined, digits = 3): string {
  if (!isFiniteNumber(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}`;
}

export function formatScore(value: number | null | undefined, digits = 1): string {
  if (!isFiniteNumber(value)) return '—';
  return value.toFixed(digits);
}

export function formatCompactUsd(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function formatCompactVnd(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)} nghìn tỷ ₫`;
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)} tỷ ₫`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(1)} triệu ₫`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(0)} nghìn ₫`;
  return `${sign}${Math.round(abs).toLocaleString('vi-VN')} ₫`;
}

export function formatMoney(
  value: number | null | undefined,
  currency: 'VND' | 'USD' | string = 'VND',
  unitScale: number = 1,
): string {
  if (!isFiniteNumber(value)) return '—';
  const baseValue = value * unitScale;
  if (currency.toUpperCase() === 'USD') {
    return formatCompactUsd(baseValue);
  }
  return formatCompactVnd(baseValue);
}

export function formatScaledVnd(
  valueInBaseVnd: number | null | undefined,
  unitScale: 1 | 1_000 | 1_000_000 | 1_000_000_000 = 1_000_000,
): string {
  if (!isFiniteNumber(valueInBaseVnd)) return '—';
  const scaled = valueInBaseVnd / unitScale;
  const unitLabels: Record<number, string> = {
    1: 'đồng',
    1_000: 'nghìn đồng',
    1_000_000: 'triệu đồng',
    1_000_000_000: 'tỷ đồng',
  };
  const digits = unitScale >= 1_000_000_000 ? 2 : unitScale >= 1_000_000 ? 1 : 0;
  return `${scaled.toLocaleString('vi-VN', { maximumFractionDigits: digits })} ${unitLabels[unitScale] ?? 'đồng'}`;
}

export const RISK_TIER_META = {
  STRONG: {
    label: 'Vững mạnh',
    tone: 'low',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
    description: 'Nền tảng tài chính vững chắc, khả năng chịu đựng biến động tốt.',
  },
  STABLE: {
    label: 'Ổn định',
    tone: 'info',
    fg: 'var(--accent-primary)',
    bg: 'var(--accent-soft)',
    description: 'Hoạt động tài chính ổn định, rủi ro mất cân đối trong 12 tháng ở mức kiểm soát.',
  },
  WATCH: {
    label: 'Cần theo dõi sát',
    tone: 'medium',
    fg: 'var(--risk-medium-fg)',
    bg: 'var(--risk-medium-bg)',
    description: 'Xuất hiện dấu hiệu áp lực dòng tiền hoặc đòn bẩy, cần rà soát định kỳ.',
  },
  CRITICAL: {
    label: 'Nguy cơ khủng hoảng cao',
    tone: 'critical',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
    description: 'Rủi ro mất khả năng thanh toán cao trong 12 tháng tới, cần hành động ngay.',
  },
} as const;

export type RiskTierKey = keyof typeof RISK_TIER_META;

export function getRiskTierMeta(tier: string | null | undefined) {
  if (!tier) return null;
  const key = tier.toUpperCase() as RiskTierKey;
  return RISK_TIER_META[key] ?? null;
}

export const CONFIDENCE_LEVEL_META = {
  HIGH: {
    label: 'Độ tin cậy Cao',
    shortLabel: 'Cao',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
  },
  MODERATE: {
    label: 'Độ tin cậy Khá',
    shortLabel: 'Khá',
    fg: 'var(--risk-medium-fg)',
    bg: 'var(--risk-medium-bg)',
  },
  LOW: {
    label: 'Cần lưu ý dữ liệu',
    shortLabel: 'Cần lưu ý',
    fg: 'var(--risk-high-fg)',
    bg: 'var(--risk-high-bg)',
  },
} as const;

export const ORG_ROLE_LABELS: Record<'org_admin' | 'analyst' | 'viewer', string> = {
  org_admin: 'Quản trị tổ chức',
  analyst: 'Chuyên viên phân tích',
  viewer: 'Người xem',
};

export const RELATIONSHIP_TAG_LABELS: Record<string, string> = {
  own_company: 'Doanh nghiệp của tôi',
  customer: 'Khách hàng',
  supplier: 'Nhà cung cấp',
  competitor: 'Đối thủ cạnh tranh',
  portfolio: 'Danh mục đầu tư / Tín dụng',
  other: 'Khác',
};

export const BUSINESS_TYPE_LABELS: Record<string, string> = {
  manufacturing: 'Sản xuất & Công nghiệp',
  trade_service: 'Thương mại & Dịch vụ',
  financial_institution: 'Tổ chức tài chính (Loại trừ chấm điểm)',
};

export const ACCOUNTING_STANDARD_LABELS: Record<string, string> = {
  TT99_2025: 'TT99/2025/TT-BTC',
  TT200_2014: 'TT200/2014/TT-BTC',
  TT133_2016: 'TT133/2016/TT-BTC',
  IFRS_USGAAP: 'IFRS / US GAAP',
};

export const AUDIT_STATUS_LABELS: Record<string, string> = {
  audited_unqualified: 'Kiểm toán — Chấp nhận toàn phần',
  audited_qualified: 'Kiểm toán — Ý kiến ngoại trừ',
  audited_adverse_disclaimer: 'Kiểm toán — Từ chối / Trái ngược',
  unaudited: 'Chưa kiểm toán (Tự lập)',
};

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('vi-VN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

const FEATURE_LABELS: Record<string, string> = {
  roa: 'Tỷ suất sinh lời tài sản (ROA)',
  roe: 'Tỷ suất sinh lời vốn CSH (ROE)',
  eps: 'Lợi nhuận trên cổ phiếu (EPS)',
  debt_ratio: 'Tỷ lệ Nợ / Tổng tài sản',
  debt_to_equity: 'Tỷ lệ Nợ / Vốn chủ sở hữu',
  current_ratio: 'Hệ số thanh toán hiện hành',
  operating_margin: 'Biên lợi nhuận hoạt động',
  ocf_ratio: 'Tỷ lệ Dòng tiền hoạt động (OCF)',
  working_capital_ratio: 'Vốn lưu động / Tổng tài sản',
  retained_earnings_ratio: 'Lợi nhuận giữ lại / Tổng tài sản',
  ebit_to_assets: 'EBIT / Tổng tài sản',
  asset_turnover: 'Vòng quay tổng tài sản',
  cash_ratio: 'Hệ số thanh toán tiền mặt',
  interest_coverage: 'Khả năng trả lãi vay',
  fcf_to_liabilities: 'Dòng tiền tự do / Tổng nợ',
  altman_z_score: 'Chỉ số Altman Z-Score',
  roa_yoy_delta: 'Biến động ROA cùng kỳ (YoY)',
  roe_yoy_delta: 'Biến động ROE cùng kỳ (YoY)',
  debt_ratio_yoy_delta: 'Biến động Tỷ lệ nợ (YoY)',
  ocf_ratio_yoy_delta: 'Biến động Tỷ lệ OCF (YoY)',
  negative_ocf_streak: 'Số năm liên tiếp OCF âm',
  positive_roa: 'ROA dương trong kỳ',
  positive_ocf: 'Dòng tiền hoạt động (OCF) dương',
  cash_exceeds_net_income: 'Dòng tiền OCF vượt lợi nhuận ròng',
  improving_roa: 'ROA cải thiện so với năm trước',
  declining_leverage: 'Tỷ lệ đòn bẩy nợ giảm so với năm trước',
  improving_liquidity: 'Hệ số thanh toán hiện hành cải thiện',
  improving_operating_margin: 'Biên lợi nhuận hoạt động cải thiện',
  improving_asset_turnover: 'Vòng quay tổng tài sản tăng',
  roa_improving: 'ROA cải thiện so với năm trước',
  ocf_exceeds_net_income: 'Dòng tiền OCF vượt lợi nhuận ròng',
  ocf_gt_net_income: 'Dòng tiền OCF vượt lợi nhuận ròng',
  lower_leverage: 'Tỷ lệ nợ vay giảm so với kỳ trước',
  debt_ratio_decreasing: 'Tỷ lệ đòn bẩy nợ giảm',
  higher_liquidity: 'Thanh khoản hiện hành cải thiện',
  current_ratio_improving: 'Hệ số thanh toán hiện hành tăng',
  higher_margin: 'Biên lợi nhuận hoạt động cải thiện',
  operating_margin_improving: 'Biên hoạt động tăng so với năm trước',
  higher_turnover: 'Vòng quay tài sản cải thiện',
  asset_turnover_improving: 'Vòng quay tổng tài sản tăng',
};

export function humanizeFeature(feature: string): string {
  return (
    FEATURE_LABELS[feature] ??
    feature
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (ch) => ch.toUpperCase())
  );
}

const SECTOR_MAP: Record<string, string> = {
  Manufacturing: 'Sản xuất & Công nghiệp',
  Services: 'Dịch vụ & Công nghệ',
  'Retail Trade': 'Bán lẻ & Tiêu dùng',
  'Wholesale Trade': 'Thương mại bán buôn',
  Mining: 'Khai khoáng & Năng lượng',
  Construction: 'Xây dựng & Hạ tầng',
  'Transportation, Communications, Electric, Gas, and Sanitary Services': 'Vận tải, Viễn thông & Tiện ích',
  'Transportation, Communications and Utilities': 'Vận tải, Viễn thông & Tiện ích',
  'Transportation & Utilities': 'Vận tải & Tiện ích',
  'Finance, Insurance, and Real Estate': 'Tài chính, Bảo hiểm & BĐS',
  'Agriculture, Forestry, and Fishing': 'Nông, Lâm & Ngư nghiệp',
  'Public Administration': 'Hành chính công',
};

export function translateSector(sector: string | null | undefined): string {
  if (!sector) return 'Chưa phân ngành';
  return SECTOR_MAP[sector] ?? sector;
}

export function translateAltmanZone(zone: string | null | undefined): string {
  if (!zone) return 'Chưa xác định';
  const key = zone.toUpperCase();
  if (key === 'SAFE') return 'Vùng an toàn';
  if (key === 'GREY' || key === 'GRAY') return 'Vùng xám (Thận trọng)';
  if (key === 'DISTRESS') return 'Vùng kiệt quệ';
  return zone;
}

const CLUSTER_MAP: Record<string, string> = {
  'Healthy Growth / Low Risk': 'Tăng trưởng lành mạnh · Rủi ro thấp',
  'Stable Core / Moderate Leverage': 'Ổn định cốt lõi · Đòn bẩy vừa phải',
  'Elevated Leverage / Watchlist': 'Đòn bẩy cao · Cần theo dõi',
  'Acute Distress / High Risk': 'Kiệt quệ tài chính · Rủi ro cao',
  'Cash-Rich / Conservative': 'Dồi dào tiền mặt · An toàn',
};

export function translateClusterLabel(label: string | null | undefined): string {
  if (!label) return '—';
  return CLUSTER_MAP[label] ?? label;
}

export function translateSignalReason(reason: string): string {
  const map: Record<string, string> = {
    current_gt_reference: 'Đạt tiêu chuẩn dương / vượt ngưỡng tham chiếu',
    current_le_reference: 'Chưa vượt ngưỡng tham chiếu an toàn',
    current_lt_reference: 'Thấp hơn ngưỡng tham chiếu an toàn',
    current_gt_prior: 'Cải thiện tích cực so với năm tài chính trước',
    current_lt_prior: 'Giảm so với năm tài chính trước',
    current_le_prior: 'Không tăng hoặc giảm so với kỳ trước',
    current_ge_prior: 'Duy trì hoặc tăng so với kỳ trước',
    missing_inputs: 'Thiếu dữ liệu kế toán gốc để đối chiếu',
    missing_prior_period: 'Chưa có kỳ báo cáo trước liền kề để so sánh',
  };
  return map[reason] ?? reason;
}
