/** Format numbers, preserving missingness. */
export function number(value: unknown, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits }).format(
        value,
      )
    : "—";
}
/** Format a fractional ratio. */
export function percent(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${number(value * 100, 1)}%`
    : "—";
}
/** Format dates without shifting date-only fiscal observations. */
export function date(value: unknown): string {
  if (typeof value !== "string" || !value) return "—";
  const parsed = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(parsed.getTime())
    ? "—"
    : new Intl.DateTimeFormat("vi-VN").format(parsed);
}
export const labels: Record<string, string> = {
  overall_score: "Điểm tổng hợp nền tảng",
  overall_grade: "Nhóm sức khỏe nội bộ",
  pillars: "Các trụ cột tài chính",
  score: "Điểm",
  status: "Trạng thái",
  observed_metrics: "Chỉ tiêu đã quan sát",
  total_metrics: "Tổng chỉ tiêu",
  retained_earnings_ratio: "Lợi nhuận giữ lại / tài sản",
  working_capital_ratio: "Vốn lưu động / tài sản",
  ebit_to_assets: "EBIT / tài sản",
  asset_turnover: "Vòng quay tài sản",
  roa_yoy_delta: "Thay đổi ROA theo năm",
  roe_yoy_delta: "Thay đổi ROE theo năm",
  debt_ratio_yoy_delta: "Thay đổi nợ / tài sản theo năm",
  ocf_ratio_yoy_delta: "Thay đổi dòng tiền / nợ theo năm",
  negative_ocf_streak: "Số kỳ dòng tiền kinh doanh âm liên tiếp",
  roa: "ROA",
  roe: "ROE",
  eps: "EPS",
  debt_ratio: "Nợ phải trả / tài sản",
  current_ratio: "Thanh toán hiện hành",
  ocf_ratio: "Dòng tiền kinh doanh / nợ",
  operating_margin: "Biên lợi nhuận hoạt động",
  cash_ratio: "Thanh toán tiền mặt",
  debt_to_equity: "Nợ / vốn chủ sở hữu",
  interest_coverage: "Khả năng trả lãi",
  fcf_to_liabilities: "FCF / nợ phải trả",
  altman_z_score: "Altman Z-score",
  composite_health_score: "Điểm sức khỏe nội bộ",
  distress_probability: "Xác suất chỉ báo khó khăn",
  total_assets: "Tổng tài sản",
  total_liabilities: "Tổng nợ phải trả",
  stockholders_equity: "Vốn thuộc cổ đông",
  current_assets: "Tài sản ngắn hạn",
  current_liabilities: "Nợ ngắn hạn",
  retained_earnings: "Lợi nhuận giữ lại",
  revenues: "Doanh thu",
  operating_income: "Lợi nhuận hoạt động",
  net_income: "Lợi nhuận sau thuế",
  operating_cash_flow: "Dòng tiền kinh doanh",
  cash_and_equivalents: "Tiền và tương đương tiền",
  interest_expense: "Chi phí lãi vay",
  capex: "Chi đầu tư tài sản",
  eps_diluted: "EPS pha loãng",
  fiscal_year: "Năm tài chính",
  filed_date: "Ngày công bố",
  accession_number: "Accession",
  model_version: "Phiên bản mô hình",
  cluster_id: "Cụm",
  sector: "Ngành",
  name: "Doanh nghiệp",
  net_profit_margin: "Biên lợi nhuận ròng",
  asset_turnover_avg: "Vòng quay tài sản bình quân",
  equity_multiplier_avg: "Đòn bẩy bình quân",
  roe_dupont_avg: "ROE theo DuPont",
  cash_conversion_qoe: "Chuyển đổi lợi nhuận thành tiền",
  accrual_gap_usd: "Chênh lệch lợi nhuận – tiền (USD)",
  cash_flow_accruals_ratio: "Tỷ lệ dồn tích dòng tiền",
  basis_note: "Cơ sở tính",
  reason: "Giải thích",
  classification_selected: "Kết quả phân loại",
  classification_benchmarks: "Đối chứng phân loại",
  regression: "Đánh giá hồi quy",
  probability_calibration: "Hiệu chỉnh xác suất",
  split_summary: "Phân chia dữ liệu theo thời gian",
  threshold: "Ngưỡng phân loại",
};
/** Keep financial vocabulary consistent, retaining unmapped source identifiers. */
export function label(key: string): string {
  return (
    labels[key] ??
    (key.startsWith("prior_") ? `${label(key.slice(6))} · kỳ trước` : key)
  );
}
const percentageKeys = new Set([
  "roa",
  "roe",
  "debt_ratio",
  "ocf_ratio",
  "operating_margin",
  "cash_flow_accruals_ratio",
  "net_profit_margin",
  "roe_dupont_avg",
  "distress_probability",
  "pred_roa",
  "pred_roe",
  "pred_debt_ratio",
  "pred_ocf_ratio",
]);
/** Apply units according to the API metric. */
export function metric(key: string, value: unknown): string {
  return percentageKeys.has(key) ? percent(value) : number(value);
}
