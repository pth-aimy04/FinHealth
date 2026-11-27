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
