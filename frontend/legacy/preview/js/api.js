/** Same-origin financial API client. Requests never supply replacement financial data. */
const ROOT = "/api/v1";
const KNOWN_ERRORS = {
  "Provide 2 to 4 distinct company tickers or CIKs": "Nhập từ 2 đến 4 mã chứng khoán hoặc CIK khác nhau, cách nhau bằng dấu phẩy.",
  "Select 2 to 4 distinct companies": "Chọn từ 2 đến 4 công ty khác nhau.",
  "Simulation requires an annual statement and a fitted model": "Cần báo cáo năm và mô hình đã huấn luyện để chạy mô phỏng.",
  "Revenue and operating income are required for margin shocks": "Cần doanh thu và lợi nhuận hoạt động để mô phỏng thay đổi biên lợi nhuận.",
  "Nonnegative total liabilities are required for a debt shock": "Cần tổng nợ phải trả không âm để mô phỏng thay đổi nợ.",
  "Reported operating cash flow is required for an OCF shock": "Cần số liệu dòng tiền hoạt động trong báo cáo để mô phỏng thay đổi dòng tiền.",
  "Reported assets are required for this balance sheet shock": "Cần số liệu tài sản trong báo cáo để mô phỏng kịch bản này.",
  "Scenario exhausts noncurrent assets under the stated funding assumptions": "Theo các giả định tài trợ này, tài sản dài hạn không đủ để thực hiện kịch bản.",
  "SEC companyfacts contains no supported financial periods": "Dữ liệu SEC chưa có kỳ báo cáo tài chính được hệ thống hỗ trợ.",
  "No active model bundle is loaded": "Chưa có mô hình đang hoạt động.",
  "Write access requires the configured administrator token": "Cần mã xác thực quản trị viên (ADMIN_TOKEN) hợp lệ để thực hiện thao tác ghi.",
};

function errorMessage({ status }, body) {
  const detail = body?.detail;
  if (Object.hasOwn(KNOWN_ERRORS, detail)) return KNOWN_ERRORS[detail];
  if (typeof detail === "string") {
    const missing = /^(?:Company not found|SEC ticker or CIK not found): (.+)$/.exec(detail);
    if (missing) return `Không tìm thấy công ty có mã ${missing[1]}.`;
    const annual = /^No annual statement for (.+) in (?:FY (\d{4})|any year)$/.exec(detail);
    if (annual) return `${annual[1]} chưa có báo cáo năm${annual[2] ? ` cho năm tài chính ${annual[2]}` : ""}.`;
    if (detail.startsWith("Depository institutions,")) {
      return "Các tổ chức tài chính thuộc SIC 6000–6799 cần mô hình vốn theo quy định chuyên ngành.";
    }
    if (detail.includes("is excluded from the industrial panel due to the PARA ticker")) {
      return "Công ty này nằm ngoài tập phân tích do trùng mã PARA và có lịch sử liên quan đến SPAC.";
    }
  }
  if (Array.isArray(detail) && detail.some((row) => row.loc?.includes("common_fiscal_year"))) {
    return "Năm tài chính phải là số nguyên từ 1990 đến 2100.";
  }
  return ({
    401: "Vui lòng đăng nhập để tiếp tục.",
    403: "Bạn không có quyền thực hiện thao tác này hoặc phiên cần được làm mới.",
    404: "Không tìm thấy dữ liệu yêu cầu.",
    422: "Dữ liệu đầu vào hoặc số liệu báo cáo chưa đáp ứng điều kiện phân tích.",
    429: "Đã đạt giới hạn truy vấn SEC. Vui lòng thử lại sau.",
    502: "Không tải được dữ liệu từ SEC EDGAR.",
    503: "Cơ sở dữ liệu tạm thời không khả dụng.",
  })[status] ?? `Không hoàn thành được yêu cầu (HTTP ${status}).`;
}

async function request(path, { method = "GET", signal, json, auth = false } = {}) {
  const csrf = document.cookie.split("; ").find((row) => row.startsWith("finhealth_csrf="))?.split("=")[1];
  let response;
  try {
    response = await fetch(ROOT + path, {
      method,
      signal,
      headers: {
        Accept: "application/json",
        ...(json && { "Content-Type": "application/json" }),
        ...(csrf && { "X-CSRF-Token": decodeURIComponent(csrf) }),
      },
      body: json ? JSON.stringify(json) : undefined,
      cache: "no-store",
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Không kết nối được máy chủ.", { cause: error });
  }
  let body;
  try {
    body = await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(`Không đọc được phản hồi từ máy chủ (HTTP ${response.status}).`, { cause: error });
  }
  if (!response.ok) {
    const error = new Error(errorMessage(response, body), { cause: body?.detail });
    error.status = response.status;
    throw error;
  }
  return body;
}

async function requestWithAdminAuth(path, options = {}) {
  return request(path, options);
}

export const api = {
  reports: (identifier, cutoff, options) => {
    const query = cutoff ? "?" + new URLSearchParams({ as_of: cutoff }) : "";
    return request(`/reports/${encodeURIComponent(identifier)}${query}`, options);
  },
  reportAlerts: (identifier, cutoff, options) => {
    const query = cutoff ? "?" + new URLSearchParams({ as_of: cutoff }) : "";
    return request(`/report-alerts/${encodeURIComponent(identifier)}${query}`, options);
  },
  filingForecasts: (filingId, options) => request(`/filings/${filingId}/forecasts`, options),
  dataQuality: (options) => request("/data-quality", options),
  health: (options) => request("/health", options),
  companies: async (options, filters = {}) => {
    const rows = [];
    const limit = 1000;
    for (let offset = 0; ; offset += limit) {
      const query = new URLSearchParams({ ...filters, limit, offset });
      const page = await request(`/companies?${query}`, options);
      rows.push(...page);
      if (page.length < limit) return rows;
    }
  },
  company: (identifier, options) =>
    request(`/companies/${encodeURIComponent(identifier)}`, options),
  companyHistory: (identifier, options) =>
    request(`/companies/${encodeURIComponent(identifier)}?include_provenance=true`, options),
  compare: (identifiers, year, options) => {
    const query = new URLSearchParams({ identifiers });
    if (year) query.set("common_fiscal_year", year);
    return request(`/companies/compare?${query}`, options);
  },
  analyze: async (identifier, queueEnabled) => {
    if (!queueEnabled) return requestWithAdminAuth(
      `/companies/${encodeURIComponent(identifier)}/analyze?force_refresh=true`, { method: "POST" },
    );
    const job = await requestWithAdminAuth(
      `/ingestion/${encodeURIComponent(identifier)}`, { method: "POST" },
    );
    for (let attempt = 0; attempt < 360; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const status = await requestWithAdminAuth(`/ingestion/status/${job.id}`);
      if (status.status === "succeeded") return api.company(status.company_cik);
      if (status.status === "failed") {
        throw new Error("Không cập nhật được hồ sơ SEC. Kiểm tra mã công ty và thử lại.");
      }
    }
    throw new Error("Tác vụ vẫn đang chờ hoặc đang chạy. Có thể quay lại kiểm tra sau.");
  },
  simulate: (identifier, scenario, options) =>
    request(`/companies/${encodeURIComponent(identifier)}/simulate`,
      { ...options, method: "POST", json: scenario }),
  predictManual: (payload, options) =>
    request("/models/predict-manual", { ...options, method: "POST", json: payload }),
  predictBatch: (payload, options) =>
    request("/models/predict-batch", { ...options, method: "POST", json: payload }),
  clusters: (options) => request("/clusters/map", options),
  modelVersions: (options) => request("/models/versions", options),
  evaluation: (modelVersion, options) => {
    const query = modelVersion ? "?" + new URLSearchParams({ model_version: modelVersion }) : "";
    return request(`/models/evaluation${query}`, options);
  },
  overview: (options) => request("/dashboard/overview", options),
};
