/** Vietnamese presentation labels for stable API identifiers. */
const labels = {
  LOW: "Thấp", MEDIUM: "Trung bình", HIGH: "Cao", CRITICAL: "Rất cao",
  SAFE: "An toàn", GREY: "Vùng xám", DISTRESS: "Khó khăn tài chính",
  PASS: "Đạt", FAIL: "Không đạt", UNAVAILABLE: "Thiếu dữ liệu", UNSCORED: "Chưa chấm điểm",
  sector: "Ngành", universe: "Toàn bộ doanh nghiệp phi tài chính",
  "Strong Financial Health": "Tài chính vững mạnh",
  "Stable / Moderate Leverage": "Ổn định, đòn bẩy vừa phải",
  "Elevated Leverage / Watchlist": "Đòn bẩy cao, cần theo dõi",
  "Financial Distress / High Risk": "Khó khăn tài chính, rủi ro cao",
  "Agriculture, Forestry and Fishing": "Nông nghiệp, lâm nghiệp và thủy sản",
  Mining: "Khai khoáng", Construction: "Xây dựng", Manufacturing: "Sản xuất",
  "Transportation, Communications and Utilities": "Vận tải, thông tin liên lạc và tiện ích",
  "Wholesale Trade": "Bán buôn", "Retail Trade": "Bán lẻ",
  "Finance, Insurance and Real Estate": "Tài chính, bảo hiểm và bất động sản",
  Services: "Dịch vụ", "Public Administration": "Hành chính công", Unknown: "Chưa xác định",
  roa: "Sinh lời trên tài sản (ROA)", roe: "Sinh lời trên vốn chủ sở hữu (ROE)",
  eps: "Lợi nhuận trên mỗi cổ phiếu (EPS)", debt_ratio: "Nợ phải trả / tài sản",
  debt_to_equity: "Nợ phải trả / vốn chủ sở hữu", current_ratio: "Hệ số thanh toán hiện hành",
  operating_margin: "Biên lợi nhuận hoạt động", ocf_ratio: "Dòng tiền hoạt động / nợ phải trả",
  working_capital_ratio: "Vốn lưu động / tài sản", retained_earnings_ratio: "Lợi nhuận giữ lại / tài sản",
  ebit_to_assets: "Lợi nhuận hoạt động / tài sản", asset_turnover: "Vòng quay tài sản",
  cash_ratio: "Hệ số thanh toán bằng tiền", interest_coverage: "Khả năng trả lãi vay",
  fcf_to_liabilities: "Dòng tiền tự do / nợ phải trả",
  roa_yoy_delta: "Thay đổi ROA so với năm trước", roe_yoy_delta: "Thay đổi ROE so với năm trước",
  debt_ratio_yoy_delta: "Thay đổi tỷ lệ nợ so với năm trước",
  ocf_ratio_yoy_delta: "Thay đổi tỷ lệ dòng tiền hoạt động so với năm trước",
  negative_ocf_streak: "Số năm liên tiếp có dòng tiền hoạt động âm",
  positive_roa: "ROA dương", positive_ocf: "Dòng tiền hoạt động dương", improving_roa: "ROA tăng",
  cash_exceeds_net_income: "Dòng tiền hoạt động vượt lợi nhuận ròng",
  declining_leverage: "Tỷ lệ nợ phải trả giảm", improving_liquidity: "Khả năng thanh toán hiện hành cải thiện",
  improving_operating_margin: "Biên lợi nhuận hoạt động tăng", improving_asset_turnover: "Vòng quay tài sản tăng",
  current_gt_reference: "Cao hơn mức đối chiếu", current_lt_reference: "Thấp hơn mức đối chiếu",
  strict_improvement_not_met: "Chưa đạt điều kiện", missing_accounting_input: "Thiếu số liệu kế toán",
  missing_prior_annual: "Thiếu báo cáo năm trước", annual_filings_required: "Cần báo cáo năm",
  nonconsecutive_fiscal_year: "Hai năm tài chính không liền nhau", missing_filing_date: "Thiếu ngày nộp hồ sơ",
  non_forward_publication: "Ngày nộp báo cáo phải sau ngày nộp báo cáo năm trước",
  missing_or_insufficient_equity: "Thiếu vốn chủ sở hữu hoặc vốn dưới 5% tổng tài sản",
  missing_or_nonpositive_assets: "Thiếu tổng tài sản hoặc tổng tài sản không dương",
  missing_income_or_nonpositive_revenue: "Thiếu lợi nhuận ròng hoặc doanh thu dương",
  nonfinite_dupont: "Không tính được các thành phần DuPont",
  missing_net_income: "Thiếu lợi nhuận ròng", non_positive_net_income: "Lợi nhuận ròng không dương",
  missing_operating_cash_flow: "Thiếu dòng tiền hoạt động", unusable_conversion_ratio: "Không tính được tỷ lệ chuyển đổi tiền mặt",
  EARNINGS_AHEAD_OF_CASH_WARNING: "Cảnh báo lợi nhuận vượt dòng tiền",
  CASH_BACKED_EARNINGS: "Lợi nhuận được dòng tiền hỗ trợ",
  Z: "Altman Z (Sản xuất)", "Z″": "Altman Z″ (Phi sản xuất)",
  Excluded: "Không áp dụng",
  cik: "CIK", ticker: "Mã chứng khoán", name: "Tên công ty", form_type: "Loại hồ sơ",
  fiscal_year: "Năm tài chính", fiscal_period: "Kỳ tài chính", period_end_date: "Ngày kết thúc kỳ",
  filed_date: "Ngày nộp hồ sơ", accession_number: "Mã hồ sơ SEC", total_assets: "Tổng tài sản",
  current_assets: "Tài sản ngắn hạn", total_liabilities: "Tổng nợ phải trả",
  current_liabilities: "Nợ ngắn hạn", stockholders_equity: "Vốn chủ sở hữu của cổ đông",
  retained_earnings: "Lợi nhuận giữ lại", revenues: "Doanh thu", net_income: "Lợi nhuận ròng",
  operating_income: "Lợi nhuận hoạt động", operating_cash_flow: "Dòng tiền hoạt động",
  cash_and_equivalents: "Tiền và các khoản tương đương tiền", interest_expense: "Chi phí lãi vay",
  capex: "Chi đầu tư tài sản cố định", eps_basic: "EPS cơ bản", eps_diluted: "EPS pha loãng",
  altman_z_score: "Điểm Altman Z", altman_zone: "Vùng Altman", field_provenance: "Nguồn dữ liệu từng chỉ tiêu (JSON)",
  distress_probability: "Xác suất khó khăn tài chính", model_version: "Phiên bản mô hình",
  composite_health_score: "Điểm sức khỏe tài chính tổng hợp", internal_research_grade: "Xếp hạng nghiên cứu nội bộ",
  internal_research_grade_label: "Giải thích xếp hạng", cohort_scope: "Phạm vi đối chiếu",
  cohort_size: "Số doanh nghiệp đối chiếu", methodology_version: "Phiên bản phương pháp",
  target_fiscal_year: "Năm tài chính dự báo", altman_model_variant: "Biến thể Altman", cluster_label: "Nhóm PCA",
  xgboost: "XGBoost", lightgbm: "LightGBM", random_forest: "Random Forest",
  logistic_regression: "Hồi quy Logistic", altman_z_baseline: "Altman Z-Score",
  xgboost_raw: "XGBoost trước hiệu chuẩn",
  "The operating margin shock is additive. A 25% marginal tax rate applies to incremental operating earnings, with other income and interest costs held fixed.":
    "Mức sốc biên lợi nhuận hoạt động được cộng trực tiếp theo điểm phần trăm. Phần thay đổi lợi nhuận hoạt động chịu thuế suất biên 25%. Thu nhập khác và chi phí lãi vay giữ nguyên.",
  "Financing changes scale reported total and current liabilities together. Retained earnings and book equity move by the after-tax earnings impact. Assets absorb the sum of both changes, preserving the original balance sheet residual.":
    "Tổng nợ phải trả và nợ ngắn hạn thay đổi theo cùng tỷ lệ. Lợi nhuận giữ lại và vốn chủ sở hữu theo sổ sách thay đổi theo phần lợi nhuận sau thuế. Tài sản điều chỉnh theo tổng hai khoản thay đổi để giữ nguyên chênh lệch ban đầu của bảng cân đối.",
  "The OCF shock applies its percentage to the absolute reported OCF. The independent OCF shock changes cash flow without specifying a working capital or financing bridge. Observed cash, current assets and capex are held fixed. The balance sheet asset adjustment is assigned to noncurrent assets.":
    "Tỷ lệ sốc dòng tiền hoạt động áp dụng trên giá trị tuyệt đối của số liệu báo cáo. Đây là giả định độc lập với vốn lưu động và nguồn tài trợ. Tiền, tài sản ngắn hạn và chi đầu tư giữ nguyên. Phần điều chỉnh tài sản được ghi vào tài sản dài hạn.",
  "Shares are held fixed. EPS uses shares implied by reported earnings and EPS when they are available and have matching signs.":
    "Số cổ phiếu giữ nguyên. Khi lợi nhuận và EPS báo cáo có đủ dữ liệu và cùng dấu, số cổ phiếu dùng để tính EPS được suy ra từ hai giá trị này.",
};

export const label = (key) => Object.hasOwn(labels, key) ? labels[key] : key ?? "—";
export const RESEARCH_GRADE_NOTE = "Xếp hạng nghiên cứu nội bộ (không phải xếp hạng tín nhiệm của tổ chức xếp hạng)";

/** Format the API's calendar date without applying a time-zone offset. */
export function date(value) {
  if (value == null) return "—";
  const parts = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return parts ? `${parts[3]}/${parts[2]}/${parts[1]}` : value;
}
