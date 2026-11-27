/** Financial workspace controller. All observations and model outputs come from the API. */
import { api } from "./api.js";
import { bindPreview } from "./preview-ui.js";
import { bindAccount, accountRequest, currentUser, ensureUser, savePersonal } from "./accounts.js";
import { bindReports } from "./reports.js";
import { downloadCsv, parseCsv } from "./csv.js";
import { date, label, RESEARCH_GRADE_NOTE } from "./vi.js";
import {
  COLORS, escapeHtml as esc, finite, metricValue, number, percent,
  renderPcaClusterScatterPlot, renderRiskGauge, renderShapWaterfallChart,
  renderTrajectoryForecastChart, renderMultiCompanyComparisonChart,
} from "./charts.js";

const $ = (id) => document.getElementById(id);
const METRICS = ["roa", "roe", "eps", "debt_ratio", "ocf_ratio"];
const ALL_RATIOS = [
  ...METRICS, "debt_to_equity", "current_ratio", "operating_margin", "working_capital_ratio",
  "retained_earnings_ratio", "ebit_to_assets", "asset_turnover", "cash_ratio",
  "interest_coverage", "fcf_to_liabilities",
];
const STRESS_PRESETS = {
  recession: [-10, -3, 0, -15],
  disruption: [-20, -8, 10, -25],
  liquidity: [-25, -6, 20, -45],
};
const COMPOSITE_FIELDS = [
  "composite_health_score", "internal_research_grade", "internal_research_grade_label",
  "cohort_scope", "cohort_size", "methodology_version",
];
const DATA_SOURCES = { health: "Kết nối", companies: "Danh sách công ty", clusters: "Bản đồ PCA",
  evaluation: "Đánh giá mô hình", inventory: "Thống kê dữ liệu", modelVersions: "Danh sách mô hình" };
const CREDIT_METRICS = ["current_ratio", "debt_to_equity", "cash_ratio", "fcf_to_liabilities", "interest_coverage"];
const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const DEMO_TICKERS = ["AAPL", "MSFT", "NVDA", "F", "AAL", "CCL", "LUMN", "KSS"];
const WORKSPACES = {
  screener: "Sàng lọc doanh nghiệp", company: "Phân tích công ty",
  compare: "So sánh công ty", explain: "Giải thích rủi ro",
  manual: "Dự báo thủ công", science: "Mô hình và phân nhóm",
  reports: "Kho báo cáo", admin: "Quản trị dữ liệu",
};
const FIGURES = [
  ["01_correlation_heatmap.png", "Tương quan giữa các chỉ số tài chính"],
  ["02_pca_scree_and_clusters.png", "Phương sai PCA và nhóm sức khỏe tài chính"],
  ["03_roc_pr_curves_comparison.png", "Đường ROC và đường độ chính xác – độ nhạy"],
  ["04_confusion_matrices.png", "Ma trận nhầm lẫn phân loại"],
  ["05_forecasting_actual_vs_predicted.png", "Dự báo và giá trị quan sát"],
  ["06_shap_global_importance.png", "Mức độ ảnh hưởng của các yếu tố tài chính"],
  ["07_reliability_calibration.png", "Đường hiệu chuẩn xác suất (Reliability Curve)"],
];
const state = {
  health: null, companies: [], clusters: [], evaluation: null, scienceEvaluation: null,
  modelVersions: [], scienceVersion: "", inventory: null,
  selected: null, selectedCik: null, tab: "screener", loading: false,
  filters: { search: "", sector: "", risk: "", cluster: "", year: "", minRoa: "", maxDebt: "", minCurrent: "" },
  screened: null, screeningLoading: false,
  sort: [{ key: "distress_probability", direction: -1 }],
};
let savedManualInput = null;
let reportsController = null;
let companyRequest;
let selectionSequence = 0;
let stressRequest;
let stressTimer;
let stressSequence = 0;
let comparisonRequest;
let comparison = null;
let screeningRequest;
let screeningTimer;

function badge(value, kind = value) {
  if (value == null || value === "") return '<span class="muted">—</span>';
  const className = String(kind).toLowerCase().replace(/[^a-z0-9-]/g, "");
  return `<span class="badge ${className}">${esc(label(value))}</span>`;
}

function notice(message, error = false) {
  const element = $("notice");
  element.classList.toggle("error", error);
  element.hidden = !message;
  element.replaceChildren();
  if (!message) return;
  const dismiss = document.createElement("button");
  dismiss.textContent = "×";
  dismiss.setAttribute("aria-label", "Đóng thông báo");
  dismiss.addEventListener("click", () => { element.hidden = true; });
  element.append(document.createTextNode(message), dismiss);
}

function kpi(label, value, note, symbol = "↗", accent = false) {
  return `<article class="kpi card ${accent ? "accent" : ""}"><div class="kpi-label">${esc(label)}
</div><div class="kpi-value">${esc(value)}</div>
    <div class="kpi-note">${esc(note)}</div></article>`;
}

function regimeLabel(id) {
  return label(state.clusters.find((point) => point.cluster_id === Number(id))?.cluster_label ?? `Nhóm ${id}`);
}

function renderStatus() {
  const connected = state.health?.database_connected;
  $("connection").innerHTML = `<i></i>${connected ? "" : "Không kết nối được dữ liệu"}`;
  $("connection").className = `connection ${connected ? "online" : "offline"}`;
  $("active-model").textContent = "";
  const report = state.evaluation?.evaluation_report;
  const count = state.inventory?.company_count ?? state.companies.length;
  const filings = state.inventory?.annual_statement_count;
  const auc = (report?.classification_selected ?? report?.classification_xgboost)?.roc_auc;
  $("header-universe").textContent = `${number(count, 0)} doanh nghiệp · ${number(filings, 0)} hồ sơ`;
  $("header-auc").textContent = `AUC kiểm định ${number(auc, 4)}`;
  $("universe-kpis").innerHTML = [
    kpi("Doanh nghiệp", number(count, 0), "Danh sách doanh nghiệp trong hệ thống", "▦"),
    kpi("Báo cáo năm", number(filings, 0), "Báo cáo tài chính có mã hồ sơ nguồn", "▤"),
    kpi("Cần theo dõi", number(state.companies.filter((row) =>
      ["HIGH", "CRITICAL"].includes(row.risk_level)).length, 0), "Doanh nghiệp có rủi ro cao hoặc rất cao", "↗"),
    kpi("ROC-AUC kiểm định", number(auc, 4),
      `${report?.split_summary?.test_classification_rows ?? "—"} kết quả kỳ tới được đánh giá`, "◈", true),
  ].join("");
}

function renderSelectors() {
  const chosen = state.selectedCik ?? state.companies.find((row) => row.ticker === "AAPL")?.cik;
  $("company-selector").innerHTML = state.companies.map((row) =>
    `<option value="${esc(row.cik)}">${esc(row.ticker ?? row.cik)} · ${esc(row.name)}</option>`).join("");
  if (chosen) $("company-selector").value = chosen;
  $("quick-select").innerHTML = DEMO_TICKERS.filter((ticker) =>
    state.companies.some((row) => row.ticker === ticker)).map((ticker) => {
    const row = state.companies.find((company) => company.ticker === ticker);
    return `<button data-company="${esc(row.cik)}" class="${row.cik === chosen ? "active" : ""}"
      aria-pressed="${row.cik === chosen}">${esc(ticker)}</button>`;
  }).join("");
  const sectors = [...new Set(state.companies.map((row) => row.sector).filter(Boolean))].sort();
  $("sector-filter").innerHTML = '<option value="">Mọi ngành</option>' + sectors.map((sector) =>
    `<option value="${esc(sector)}">${esc(label(sector))}</option>`).join("");
  $("sector-filter").value = state.filters.sector;
  const regimes = [...new Set(state.clusters.map((row) => row.cluster_id))].sort((a, b) => a - b);
  $("cluster-filter").innerHTML = '<option value="">Mọi nhóm</option>' + regimes.map((id) =>
    `<option value="${id}">${esc(regimeLabel(id))}</option>`).join("");
  $("cluster-filter").value = state.filters.cluster;
  const years = [...new Set(state.companies.map((row) => row.latest_fiscal_year).filter(finite))]
    .sort((a, b) => b - a);
  $("year-filter").innerHTML = '<option value="">Mọi năm</option>' + years.map((year) =>
    `<option value="${year}">${year}</option>`).join("");
  $("year-filter").value = state.filters.year;
  $("compare-company-list").innerHTML = '<option value="">Chọn từ danh sách</option>' + state.companies.map((row) =>
    `<option value="${esc(row.ticker ?? row.cik)}">${esc(row.name)}</option>`).join("");
}

function renderDistributions() {
  const total = state.companies.length;
  const distribution = (label, count, color) => `<div class="distribution-row">
    <span class="distribution-label"><i style="color:${color}"></i>${esc(label)}</span>
    <span class="distribution-count">${count} <span class="muted">/ ${total}</span></span>
    <div class="distribution-track"><i style="width:${total ? count / total * 100 : 0}%;background:${color}"></i></div></div>`;
  $("risk-distribution").innerHTML = RISK_LEVELS.map((level, index) =>
    distribution(label(level), state.companies.filter((row) => row.risk_level === level).length, COLORS[index])).join("");
  const unscored = state.companies.filter((row) => !row.risk_level).length;
  if (unscored) $("risk-distribution").innerHTML += distribution("Chưa chấm điểm", unscored, "#94a3b8");
  $("cluster-distribution").innerHTML = [0, 1, 2, 3].map((id) => {
    const label = regimeLabel(id);
    return distribution(label, state.companies.filter((row) => row.cluster_id === id).length, COLORS[id]);
  }).join("");
}

function compareRows(a, b) {
  for (const { key, direction } of state.sort) {
    const av = a[key], bv = b[key];
    if (av == null && bv == null) continue;
    if (av == null) return 1;
    if (bv == null) return -1;
    const result = typeof av === "number" ? av - bv : String(av).localeCompare(String(bv), "vi");
    if (result) return result * direction;
  }
  return (a.ticker ?? a.cik).localeCompare(b.ticker ?? b.cik, "vi");
}

function filteredCompanies() {
  const { search, sector, risk, cluster, year } = state.filters;
  const query = search.toLowerCase().trim();
  return (state.screened ?? state.companies).filter((row) =>
    (!query || `${row.ticker ?? ""} ${row.name} ${row.cik}`.toLowerCase().includes(query)) &&
    (!sector || row.sector === sector) &&
    (!risk || row.risk_level === risk) &&
    (cluster === "" || row.cluster_id === Number(cluster)) &&
    (!year || row.latest_fiscal_year === Number(year))).sort(compareRows);
}

function renderScreener() {
  const companies = filteredCompanies();
  $("export-screener").disabled = !companies.length || state.screeningLoading;
  $("screener-table").setAttribute("aria-busy", String(state.screeningLoading));
  $("result-count").textContent = `${companies.length}/${state.companies.length} công ty · Báo cáo năm mới nhất`;
  $("screener-body").innerHTML = companies.length ? companies.map((row) => {
    const color = COLORS[RISK_LEVELS.indexOf(row.risk_level)] ?? "#9aabb6";
    const width = finite(row.distress_probability) ? Math.min(100, Math.max(0, row.distress_probability * 100)) : 0;
    const scoreText = finite(row.composite_health_score)
      ? `${number(row.composite_health_score, 1)} ${badge(row.internal_research_grade, "research-grade")}`
      : '<span class="muted">—</span>';
    return `<tr data-company="${esc(row.cik)}" class="${row.cik === state.selectedCik ? "selected" : ""}">
      <td><div class="company-cell"><span class="ticker-icon">${esc((row.ticker ?? row.cik).slice(0, 2))}</span>
      <div><button class="company-button" data-company="${esc(row.cik)}">${esc(row.ticker ?? row.cik)}</button>
      <div class="company-name" title="${esc(row.name)}">${esc(row.name)}</div></div></div></td>
      <td class="numeric"><span class="probability-cell"><span class="micro-bar"><i style="width:${width}%;background:${color}"></i></span>${percent(row.distress_probability)}</span></td>
      <td>${badge(row.risk_level)}</td>
      <td class="numeric">${scoreText}</td>
      <td class="numeric">${number(row.altman_z_score)}</td>
      <td class="numeric">${percent(row.roa)}</td><td class="numeric">${percent(row.roe)}</td>
      <td class="numeric">${percent(row.debt_ratio)}</td><td class="numeric">${percent(row.ocf_ratio)}</td>
      <td class="numeric">${row.latest_fiscal_year ?? "—"}</td></tr>`;
  }).join("") : '<tr><td colspan="10" class="empty">Không có công ty phù hợp với bộ lọc.</td></tr>';
  for (const button of document.querySelectorAll("[data-sort]")) {
    const index = state.sort.findIndex((sort) => sort.key === button.dataset.sort);
    const span = button.querySelector("span");
    span.textContent = index >= 0 ? `${state.sort[index].direction === 1 ? "↑" : "↓"}${state.sort.length > 1 ? index + 1 : ""}` : "";
    const heading = button.closest("th");
    heading.setAttribute("aria-sort", index === 0
      ? (state.sort[0].direction === 1 ? "ascending" : "descending") : "none");
  }
}

async function refreshScreening() {
  screeningRequest?.abort();
  screeningRequest = new AbortController();
  const signal = screeningRequest.signal;
  const fields = {
    search: ["q", 1], sector: ["sector", 1], risk: ["risk_level", 1], cluster: ["cluster_id", 1],
    year: ["fiscal_year", 1], minRoa: ["min_roa", 100], maxDebt: ["max_debt_ratio", 100],
    minCurrent: ["min_current_ratio", 1],
  };
  const filters = {};
  for (const [key, [parameter, scale]] of Object.entries(fields)) {
    const value = state.filters[key].trim();
    if (value !== "") filters[parameter] = scale === 1 ? value : Number(value) / scale;
  }
  state.screeningLoading = true;
  renderScreener();
  $("result-count").textContent = "Đang truy vấn bộ lọc…";
  try {
    const rows = Object.keys(filters).length ? await api.companies({ signal }, filters) : null;
    if (signal.aborted) return;
    state.screened = rows;
    state.screeningLoading = false;
    renderScreener();
  } catch (error) {
    if (signal.aborted) return;
    state.screened = [];
    state.screeningLoading = false;
    renderScreener();
    $("result-count").textContent = error.message;
  }
}

function openTab(name) {
  if (!WORKSPACES[name]) return;
  if (name === "admin" && currentUser()?.role !== "admin") name = "screener";
  state.tab = name;
  $("workspace-name").textContent = WORKSPACES[name];
  for (const [key] of Object.entries(WORKSPACES)) {
    const active = name === key;
    $(`panel-${key}`).hidden = !active;
    $(`tab-${key}`).setAttribute("aria-selected", String(active));
    $(`tab-${key}`).tabIndex = active ? 0 : -1;
  }
  location.hash = name;
  window.dispatchEvent(new Event("finhealth:close-menu"));
  if (name === "admin") window.dispatchEvent(new Event("finhealth:open-admin"));
  if (name === "reports" && reportsController) void reportsController.refresh();
}

function renderMaps() {
  const select = (cik) => { openTab("company"); selectCompany(cik); };
  renderPcaClusterScatterPlot($("mini-pca"), state.clusters, state.selectedCik, select, { compact: true });
  renderPcaClusterScatterPlot($("pca-map"), state.clusters, state.selectedCik, select, {
    axis: $("pca-axis").value,
  });
}

function delta(key, current, next) {
  if (!finite(current) || !finite(next)) return "—";
  const change = next - current;
  return `${change >= 0 ? "+" : "−"}${key === "eps"
    ? `$${number(Math.abs(change))}` : `${number(Math.abs(change) * 100, 2)} điểm %`}`;
}

function renderCompany() {
  const analysis = state.selected;
  if (!analysis) return;
  const { company, history, latest_prediction: prediction } = analysis;
  const latest = history.at(-1);
  $("company-overview").innerHTML = `<span class="ticker-icon">${esc(company.ticker ?? "SEC")}</span>
    <div><h2>${esc(company.name)}</h2><div class="company-meta">${esc(company.ticker ?? company.cik)} · CIK ${esc(company.cik)}
      · ${esc(label(company.sector ?? "Unknown"))} (SIC ${esc(company.sic_code ?? "—")})
      · Năm tài chính ${latest?.fiscal_year ?? "—"} · Nộp ${esc(date(latest?.filed_date))}</div>
      <div class="company-tags">${badge(company.cluster_label, `cluster-${company.cluster_id}`)}
        ${badge(company.altman_zone)}
        ${company.internal_research_grade ? badge(company.internal_research_grade, "research-grade") : ""}</div></div>
    <dl class="overview-metrics"><div><dt>Xác suất khó khăn tài chính</dt><dd>${percent(prediction?.distress_probability)}</dd></div>
      <div><dt>Điểm sức khỏe tổng hợp</dt><dd>${finite(company.composite_health_score) ? number(company.composite_health_score, 1) + " / 100" : "—"}</dd></div>
      <div><dt>Altman Z</dt><dd>${number(latest?.altman_z_score)}</dd></div>
      <div><dt>Nợ phải trả / tài sản</dt><dd>${percent(latest?.debt_ratio)}</dd></div></dl>`;
  renderDiagnostic(company, latest, prediction);
  renderCredit(analysis);
  renderFundamentals(analysis);
  $("export-history").disabled = !latest;
  for (const input of $("stress-form").querySelectorAll("input[type=range]")) {
    input.value = input.defaultValue;
  }
  scheduleStress();
  $("forecast-caption").textContent = prediction
    ? `Báo cáo năm ${latest?.fiscal_year ?? "—"} → Dự báo năm ${prediction.target_fiscal_year}`
    : "Chưa có dự báo cho công ty này.";
  $("trajectory-charts").innerHTML = METRICS.map((key) => `<section class="card trajectory-card">
    <div class="card-heading"><h2>${esc(label(key))}</h2><span class="muted">Năm tài chính ${latest?.fiscal_year ?? "—"}</span></div>
    <div class="trajectory-stat">${metricValue(key, latest?.[key])}<small>Kỳ tới ${metricValue(key, prediction?.[`pred_${key}`])}</small></div>
    <div id="trajectory-${key}" class="chart trajectory-chart"></div></section>`).join("");
  for (const key of METRICS) renderTrajectoryForecastChart($(`trajectory-${key}`), history, prediction, key);
  $("forecast-table").innerHTML = METRICS.map((key) => `<tr><td>${esc(label(key))}</td>
    <td class="numeric">${metricValue(key, latest?.[key])}</td>
    <td class="numeric">${metricValue(key, prediction?.[`pred_${key}`])}</td>
    <td class="numeric">${delta(key, latest?.[key], prediction?.[`pred_${key}`])}</td></tr>`).join("");
  $("history-table").innerHTML = history.toReversed().map((row) => `<tr><td>${row.fiscal_year}</td>
    <td>${esc(date(row.filed_date))}</td>${[
      "total_assets", "total_liabilities", "stockholders_equity", "revenues", "net_income", "operating_cash_flow",
    ].map((key) => `<td class="numeric">${number(row[key], 0)}</td>`).join("")}
    ${["roa", "roe"].map((key) => `<td class="numeric">${percent(row[key])}</td>`).join("")}
    <td class="numeric">${number(row.eps)}</td><td class="numeric">${percent(row.debt_ratio)}</td>
    <td class="numeric">${percent(row.ocf_ratio)}</td><td class="numeric">${number(row.altman_z_score)}</td>
    <td>${badge(row.altman_zone)}</td><td class="muted">${esc(row.accession_number ?? "—")}</td></tr>`).join("")
    || '<tr><td colspan="16" class="empty">Chưa có lịch sử báo cáo năm.</td></tr>';
  renderAttribution(analysis);
}

function creditValue(key, value) {
  return ["interest_coverage", "cash_ratio", "current_ratio", "debt_to_equity"].includes(key)
    ? (finite(value) ? number(value, 2) + "×" : "—")
    : percent(value);
}

function renderCredit({ history, sector_peer_context: peers }) {
  const latest = history.at(-1);
  $("print-memo").disabled = !latest;
  $("credit-ratios").innerHTML = CREDIT_METRICS.map((key) =>
    `<div><span>${esc(label(key))}</span><strong>${creditValue(key, latest?.[key])}</strong></div>`).join("");
  $("peer-cohort").textContent = peers
    ? `${label(peers.cohort === "sector" ? peers.sector : peers.cohort)} · ${peers.cohort_size} công ty`
    : "Chưa có nhóm đối chiếu theo năm";
  $("peer-table").innerHTML = Object.entries(peers?.metrics ?? {}).map(([key, stat]) => {
    const percentile = stat.percentile;
    return `<tr><td>${esc(label(key))}</td>
      <td class="numeric">${creditValue(key, latest?.[key])}</td>
      <td class="numeric">${creditValue(key, stat.median)}</td>
      <td>${finite(percentile) ?
        `<span class="peer-rank"><progress max="100" value="${percentile}" aria-label="Phân vị"></progress>
        <strong>P${number(percentile, 1)}</strong></span>` : "—"}</td>
      <td class="numeric">${stat.n_observed}</td></tr>`;
  }).join("");
}

function scheduleStress(delay = 220) {
  const sequence = ++stressSequence;
  stressRequest?.abort();
  clearTimeout(stressTimer);
  const form = $("stress-form");
  const scenario = {};
  for (const input of form.querySelectorAll("input[type=range]")) {
    const value = Number(input.value);
    input.previousElementSibling.textContent =
      `${value > 0 ? "+" : ""}${value}${input.id === "stress-margin" ? " điểm %" : "%"}`;
    scenario[input.name] = value / 100;
    input.disabled = !state.selected?.latest_prediction;
  }
  for (const button of document.querySelectorAll("[data-stress-preset]")) {
    button.disabled = !state.selected?.latest_prediction;
  }
  $("stress-result").replaceChildren();
  if (!state.selected?.latest_prediction) {
    $("stress-status").textContent = "Cần mô hình đã huấn luyện và báo cáo tài chính năm.";
    return;
  }
  $("stress-status").textContent = "Đang tính kết quả kịch bản…";
  const cik = state.selectedCik;
  stressTimer = setTimeout(async () => {
    stressRequest = new AbortController();
    try {
      const result = await api.simulate(cik, scenario, { signal: stressRequest.signal });
      if (sequence === stressSequence && cik === state.selectedCik) renderStress(result);
    } catch (error) {
      if (sequence === stressSequence && error.name !== "AbortError") {
        $("stress-status").textContent = error.message;
      }
    }
  }, delay);
}

const PILLAR_STATUS_LABELS = {
  STRONG: ["Tốt", "low"],
  ADEQUATE: ["Đạt", "medium"],
  WEAK: ["Yếu", "high"],
  CRITICAL: ["Cảnh báo", "critical"],
  UNAVAILABLE: ["Thiếu dữ liệu", "unavailable"],
};

const PRIORITY_BADGES = {
  HIGH: ["Ưu tiên cao", "critical"],
  MEDIUM: ["Ưu tiên vừa", "medium"],
  LOW: ["Duy trì", "low"],
};

const CATEGORY_LABELS = {
  PROFITABILITY: "Sinh lời",
  LIQUIDITY: "Thanh khoản",
  SOLVENCY: "Cấu trúc vốn & Đòn bẩy",
  CASH_FLOW: "Dòng tiền & Hiệu quả",
};

function renderHealthPillarsAndAdvice(healthPillars, recommendations) {
  const pillars = Object.values(healthPillars?.pillars ?? {});
  const overall = finite(healthPillars?.overall_score) ? `${number(healthPillars.overall_score, 1)} / 100` : "—";
  const grade = healthPillars?.overall_grade ?? "UNSCORED";
  const pillarCards = pillars.map((p) => {
    const [statusLabel, statusClass] = PILLAR_STATUS_LABELS[p.status] ?? ["—", "unavailable"];
    const scoreText = finite(p.score) ? `${number(p.score, 1)} / 100` : "—";
    return `<div><span>${esc(p.label_vi)} (${p.observed_metrics}/${p.total_metrics} chỉ số)</span>
      <strong>${scoreText} ${badge(statusLabel, statusClass)}</strong></div>`;
  }).join("");
  const adviceRows = (recommendations ?? []).map((rec) => {
    const [prioLabel, prioClass] = PRIORITY_BADGES[rec.priority] ?? [rec.priority, "medium"];
    const catLabel = CATEGORY_LABELS[rec.category] ?? rec.category;
    const featLabel = rec.feature === "overall_health" ? "Tổng thể" : label(rec.feature);
    const curVal = rec.feature === "overall_health"
      ? "—"
      : CREDIT_METRICS.includes(rec.feature)
        ? creditValue(rec.feature, rec.current_value)
        : metricValue(rec.feature, rec.current_value);
    return `<tr>
      <td>${badge(prioLabel, prioClass)}</td>
      <td>${esc(catLabel)}</td>
      <td><strong>${esc(featLabel)}</strong></td>
      <td class="numeric">${curVal}</td>
      <td class="numeric">${esc(rec.target_benchmark)}</td>
      <td>${esc(rec.action_vi)}</td>
    </tr>`;
  }).join("");
  return `
    <div class="card-heading"><h2>Chấm điểm sức khỏe 4 trụ cột (${overall} · Hạng ${esc(grade)})</h2>
      <span class="muted">Chuẩn hóa độc lập trên thang 0–100 từ các tỷ số quan sát được</span></div>
    <div class="credit-ratios">${pillarCards}</div>
    <div class="card-heading"><h2>Khuyến nghị quản trị rủi ro theo các yếu tố ảnh hưởng</h2>
      <span class="muted">Tự động tổng hợp từ các đặc trưng làm tăng rủi ro phá sản</span></div>
    <div class="table-scroll"><table class="data-table">
      <thead><tr><th>Mức ưu tiên</th><th>Trụ cột</th><th>Chỉ tiêu</th><th class="numeric">Hiện tại</th><th class="numeric">Ngưỡng mục tiêu</th><th>Khuyến nghị hành động</th></tr></thead>
      <tbody>${adviceRows || '<tr><td colspan="6" class="empty">Chưa có khuyến nghị.</td></tr>'}</tbody>
    </table></div>`;
}

function renderFundamentals({
  company,
  dupont,
  quality_of_earnings: qoe,
  accounting_checklist: checklist,
  health_pillars: healthPillars,
  recommendations,
}) {
  const score = finite(company.composite_health_score) ? number(company.composite_health_score, 1) + " / 100" : "—";
  const chartValue = (label, value) => `<div><span>${esc(label)}</span><strong>${value}</strong></div>`;
  const signed = (value) => finite(value) ? `${value >= 0 ? "+" : ""}${number(value * 100, 2)} điểm %` : "—";
  const multiple = (value) => finite(value) ? number(value, 3) + "×" : "—";
  const basis = qoe?.accruals_basis === "average_assets" ? "Tài sản bình quân"
    : qoe?.accruals_basis === "ending_assets" ? "Tài sản cuối kỳ" : "Thiếu dữ liệu tài sản";
  const bridge = dupont?.bridge;
  const reference = (key, row) => {
    if (key === "positive_ocf" || key === "cash_exceeds_net_income") {
      return finite(row.prior_value) ? "$" + number(row.prior_value, 0) : "—";
    }
    const formatter = ["improving_liquidity", "improving_asset_turnover"].includes(key) ? multiple : percent;
    return formatter(row.prior_value);
  };
  $("company-fundamentals").innerHTML = `
    <div class="credit-ratios">
      ${chartValue("Điểm sức khỏe tài chính tổng hợp", score)}
      ${chartValue(RESEARCH_GRADE_NOTE, badge(company.internal_research_grade, "research-grade"))}
      ${chartValue("Nhóm đối chiếu", `${esc(label(company.cohort_scope === "sector" ? company.sector : company.cohort_scope))} · ${company.cohort_size} công ty`)}
    </div>
    <p class="card-footnote">${esc(company.methodology_version)} · Điểm là trung bình của bốn phân vị tính trên cùng một nhóm có đủ dữ liệu: ROA, dòng tiền hoạt động / nợ phải trả,
      hệ số thanh toán hiện hành và phân vị đảo chiều của nợ phải trả / tài sản.</p>
    <div class="analytics-columns">
      <section><h3>ROE theo DuPont ba nhân tố</h3>
        <dl><div><dt>Biên lợi nhuận ròng</dt><dd>${percent(dupont?.net_profit_margin, 2)}</dd></div>
        <div><dt>Vòng quay tài sản bình quân</dt><dd>${multiple(dupont?.asset_turnover_avg)}</dd></div>
        <div><dt>Hệ số nhân vốn chủ sở hữu bình quân</dt><dd>${multiple(dupont?.equity_multiplier_avg)}</dd></div>
        <div><dt>ROE theo vốn chủ sở hữu bình quân</dt><dd>${percent(dupont?.roe_dupont_avg, 2)}</dd></div>
        <div><dt>ROE của mô hình theo vốn chủ sở hữu cuối kỳ</dt><dd>${percent(dupont?.roe_ending_equity, 2)}</dd></div></dl>
        <p class="muted">ROE DuPont lấy lợi nhuận ròng chia cho vốn chủ sở hữu bình quân đầu và cuối kỳ. Vốn chủ sở hữu mỗi kỳ phải đạt ít nhất 5% tổng tài sản của kỳ đó. ROE của mô hình dùng vốn cuối kỳ và được giới hạn ở ±300%.</p>
        ${dupont?.reason ? `<p class="muted">${esc(label(dupont.reason))}</p>` : ""}
        <h3>Đóng góp vào thay đổi ROE so với năm trước</h3>
        <dl><div><dt>Biên lợi nhuận ròng</dt><dd>${signed(bridge?.margin_contribution)}</dd></div>
        <div><dt>Vòng quay tài sản</dt><dd>${signed(bridge?.turnover_contribution)}</dd></div>
        <div><dt>Hệ số nhân vốn chủ sở hữu</dt><dd>${signed(bridge?.leverage_contribution)}</dd></div>
        <div><dt>Thay đổi tổng cộng</dt><dd>${signed(bridge?.delta_roe_dupont_avg)}</dd></div></dl>
        ${dupont?.bridge_reason ? `<p class="muted">${esc(label(dupont.bridge_reason))}</p>` : ""}
      </section>
      <section><h3>Chất lượng lợi nhuận</h3>
        <dl><div><dt>Dòng tiền hoạt động / lợi nhuận ròng</dt><dd>${multiple(qoe?.cash_conversion_qoe)}</dd></div>
        <div><dt>Lợi nhuận ròng trừ dòng tiền hoạt động</dt><dd>${finite(qoe?.accrual_gap_usd) ? "$" + number(qoe.accrual_gap_usd, 0) : "—"}</dd></div>
        <div><dt>Tỷ lệ dồn tích theo dòng tiền · ${basis}</dt><dd>${percent(qoe?.cash_flow_accruals_ratio, 2)}</dd></div></dl>
        ${qoe?.cash_conversion_reason ? `<p class="muted">${esc(label(qoe.cash_conversion_reason))}</p>` : ""}
        ${qoe?.accruals_flag ? badge(label(qoe.accruals_flag), "research-grade") : ""}
        <p class="muted">Chênh lệch giữa lợi nhuận ròng và dòng tiền hoạt động là tín hiệu sàng lọc. Kết luận về thao túng lợi nhuận cần thêm bằng chứng.</p>
      </section>
    </div>
    <div class="card-heading"><h2>Các tín hiệu kế toán cơ bản</h2>
      <span class="muted">${checklist?.observed_passes ?? 0} đạt / ${checklist?.observed_checks ?? 0} có dữ liệu</span></div>
    <div class="table-scroll"><table class="data-table"><thead><tr><th>Tín hiệu</th><th>Kết quả</th><th>Hiện tại</th><th>Đối chiếu</th><th>Căn cứ</th></tr></thead>
      <tbody>${Object.entries(checklist?.signals ?? {}).map(([key, row]) => `
        <tr><td>${esc(label(key))}</td><td>${badge(row.status, row.status === "PASS" ? "low" : row.status === "FAIL" ? "high" : "unavailable")}</td>
        <td>${reference(key, { prior_value: row.current_value })}</td><td>${reference(key, row)}</td>
        <td>${esc(label(row.reason))}</td></tr>`).join("")}</tbody></table></div>
    <p class="card-footnote">Tám tiêu chí dựa trên phương pháp Piotroski. Đòn bẩy tính theo tổng nợ phải trả và biên lợi nhuận tính theo lợi nhuận hoạt động. Chỉ tổng hợp các tiêu chí có đủ dữ liệu.</p>
    ${renderHealthPillarsAndAdvice(healthPillars, recommendations)}`;
}

function exportScreener() {
  const columns = ["cik", "ticker", "name", "sector", "form_type", "fiscal_year", "period_end_date",
    "filed_date", "accession_number", ...ALL_RATIOS, ...COMPOSITE_FIELDS, "altman_z_score",
    "altman_zone", "distress_probability", "model_version"];
  const rows = filteredCompanies().map((row) => ({
    ...row, form_type: row.latest_fiscal_year == null ? null : "10-K",
    fiscal_year: row.latest_fiscal_year, period_end_date: row.latest_period_end_date,
    sector: row.sector == null ? null : label(row.sector),
    altman_zone: row.altman_zone == null ? null : label(row.altman_zone),
    internal_research_grade: row.internal_research_grade == null ? null : label(row.internal_research_grade),
    internal_research_grade_label: row.internal_research_grade_label ? RESEARCH_GRADE_NOTE : null,
    cohort_scope: row.cohort_scope === "sector" ? "Cùng ngành" : label(row.cohort_scope),
  }));
  if (rows.length) downloadCsv("finhealth-sang-loc.csv", columns, rows, label);
}

async function exportHistory() {
  const { company } = state.selected;
  const button = $("export-history");
  button.disabled = true;
  try {
    const { history } = await api.companyHistory(company.cik);
    const columns = [
      "cik", "ticker", "name", "sector", "form_type", "fiscal_year", "fiscal_period",
      "period_end_date", "filed_date", "accession_number", "total_assets", "current_assets",
      "total_liabilities", "current_liabilities", "stockholders_equity", "retained_earnings",
      "revenues", "net_income", "operating_income", "operating_cash_flow", "cash_and_equivalents",
      "interest_expense", "capex", "eps_basic", "eps_diluted", ...ALL_RATIOS, "altman_z_score",
      "altman_zone", "field_provenance",
    ];
    const rows = history.filter((row) => row.form_type === "10-K").toReversed().map((row) => ({
      ...row, cik: company.cik, ticker: company.ticker, name: company.name,
      sector: company.sector && label(company.sector), altman_zone: row.altman_zone && label(row.altman_zone),
      field_provenance: row.field_provenance ? JSON.stringify(row.field_provenance) : null,
    }));
    if (rows.length) downloadCsv(`finhealth-${company.cik}-lich-su-10k.csv`, columns, rows, label);
  } catch (error) {
    notice(`Không xuất được lịch sử báo cáo năm. ${error.message}`, true);
  } finally {
    if (state.selectedCik === company.cik) button.disabled = false;
  }
}

function renderComparisonChart() {
  if (!comparison) return;
  const metric = $("compare-metric").value;
  renderMultiCompanyComparisonChart($("comparison-chart"), comparison, metric);
  $("comparison-note").textContent = metric === "operating_margin"
    ? "Biên lợi nhuận hoạt động chỉ hiển thị số liệu lịch sử vì mô hình hiện tại không dự báo chỉ tiêu này."
    : "Đường liền thể hiện số liệu báo cáo. Đường đứt thể hiện dự báo kỳ tới từ hồ sơ được chọn.";
}

function renderComparison(data) {
  const { companies, cohort_medians: medians } = data;
  $("compare-head").innerHTML = `<tr><th>Chỉ tiêu</th>${companies.map((row) =>
    `<th><button type="button" class="text-button" data-company="${esc(row.cik)}">${esc(row.ticker ?? row.cik)}</button>
    <small class="compare-name">${esc(row.name)}</small></th>`).join("")}<th>Trung vị nhóm đã chọn</th></tr>`;
  const row = (label, values, midpoint = "—") => `<tr><th scope="row">${esc(label)}</th>${values.map(
    (value) => `<td>${value}</td>`).join("")}<td>${midpoint}</td></tr>`;
  const textRow = (key, format = label) => row(label(key), companies.map((item) => esc(format(item[key]))));
  const metricRow = (label, key, format) => row(label, companies.map((item) => format(item[key])), format(medians[key]));
  $("compare-body").innerHTML = [
    textRow("fiscal_year"), textRow("period_end_date", date),
    textRow("filed_date", date), textRow("accession_number"),
    metricRow("Điểm sức khỏe tổng hợp / 100", "composite_health_score", number),
    row(RESEARCH_GRADE_NOTE, companies.map(
      (item) => `${esc(label(item.internal_research_grade))}<small class="compare-name">${esc(label(item.cohort_scope === "sector" ? item.sector : item.cohort_scope))} · ${item.cohort_size} công ty</small>`)),
    metricRow("Xác suất theo chỉ báo khó khăn tài chính", "distress_probability", percent),
    metricRow("Điểm Altman", "altman_z_score", number), textRow("altman_model_variant"),
    textRow("cluster_label"),
    ...ALL_RATIOS.map((key) => metricRow(label(key), key,
      (value) => CREDIT_METRICS.includes(key) ? creditValue(key, value) : metricValue(key, value))),
    row("ROE DuPont theo vốn chủ sở hữu bình quân", companies.map((item) => percent(item.dupont.roe_dupont_avg)),
      percent(medians.roe_dupont_avg)),
    row("Dòng tiền hoạt động / lợi nhuận ròng", companies.map((item) => finite(item.quality_of_earnings.cash_conversion_qoe)
      ? number(item.quality_of_earnings.cash_conversion_qoe, 3) + "×" : "—"),
      finite(medians.cash_conversion_qoe) ? number(medians.cash_conversion_qoe, 3) + "×" : "—"),
    textRow("target_fiscal_year"),
    ...METRICS.map((key) => metricRow(`Dự báo kỳ tới · ${label(key)}`, "pred_" + key, (value) => metricValue(key, value))),
  ].join("");
  $("compare-context").textContent = data.common_fiscal_year ? "Cùng năm tài chính " + data.common_fiscal_year : "10-K mới nhất của từng công ty";
  $("compare-results").hidden = false;
  renderComparisonChart();
}

async function runComparison() {
  comparisonRequest?.abort();
  const controller = new AbortController();
  comparisonRequest = controller;
  $("compare-status").textContent = "Đang tải số liệu báo cáo năm…";
  $("compare-results").hidden = true;
  try {
    const data = await api.compare($("compare-identifiers").value, $("compare-year").value,
      { signal: controller.signal });
    if (comparisonRequest !== controller) return;
    comparison = data;
    renderComparison(data);
    $("compare-status").textContent = "";
  } catch (error) {
    if (comparisonRequest === controller && error.name !== "AbortError") {
      $("compare-status").textContent = error.message;
    }
  }
}

function renderStress({ baseline, stressed, probability_delta: change, altman_z_delta: zChange,
  is_ood_scenario: ood, ood_features: outside, top_shifted_shap_drivers: shifts, assumptions }) {
  $("stress-status").textContent = ood
    ? `Các chỉ tiêu sau nằm ngoài khoảng huấn luyện (P1–P99): ${outside.map(label).join(", ")}. Cần thận trọng khi diễn giải.`
    : ood == null ? "Chưa có thông tin về khoảng giá trị huấn luyện của mô hình." : "Các đầu vào nằm trong khoảng giá trị huấn luyện.";
  $("stress-result").innerHTML = `<div class="stress-comparison">
    <div><span>Xác suất theo chỉ báo khó khăn tài chính</span>
      <strong>${percent(baseline.prediction.distress_probability)} → ${percent(stressed.prediction.distress_probability)}</strong>
      <small>${change >= 0 ? "+" : ""}${number(change * 100, 2)} điểm %</small></div>
    <div><span>Altman Z</span><strong>${number(baseline.metrics.altman_z_score)} → ${number(stressed.metrics.altman_z_score)}</strong>
      <small>${finite(zChange) && zChange >= 0 ? "+" : ""}${number(zChange, 3)}</small></div>
    <div><span>Nhóm PCA</span><strong>${esc(label(baseline.metrics.cluster_label))} → ${esc(label(stressed.metrics.cluster_label))}</strong></div>
    </div><details><summary>Dự báo, thay đổi tác động của các yếu tố và các giả định</summary>
      <div class="table-scroll"><table class="data-table"><thead>
      <tr><th>Chỉ tiêu kỳ tới</th><th class="numeric">Kịch bản cơ sở</th><th class="numeric">Kịch bản căng thẳng</th></tr>
      </thead><tbody>${METRICS.map((key) => `<tr><td>${esc(label(key))}</td>
        <td class="numeric">${metricValue(key, baseline.prediction["pred_" + key])}</td>
        <td class="numeric">${metricValue(key, stressed.prediction["pred_" + key])}</td></tr>`).join("")}
      </tbody></table></div>
      <h3>Các thay đổi lớn nhất về ${(stressed?.prediction?.output_space ?? baseline?.prediction?.output_space) === "probability" ? "đóng góp xác suất" : "đóng góp log-odds"}</h3>
      <ul>${shifts.map((row) => `<li>${esc(label(row.feature))}
        ${number(row.baseline, 3)} → ${number(row.stressed, 3)} (${row.delta >= 0 ? "+" : ""}${number(row.delta, 3)})</li>`).join("")}</ul>
      <ul>${assumptions.map((line) => `<li>${esc(label(line))}</li>`).join("")}</ul>
    </details>`;
}

function printCreditMemo() {
  const { company, history, latest_prediction: prediction, sector_peer_context: peers } = state.selected;
  const latest = history.at(-1);
  if (!latest) return;
  const isProb = prediction?.output_space === "probability";
  const forecasts = METRICS.map((key) => `<tr><td>${esc(label(key))}</td>
    <td>${metricValue(key, history.at(-2)?.[key])}</td><td>${metricValue(key, latest[key])}</td>
    <td>${metricValue(key, prediction?.["pred_" + key])}</td></tr>`).join("");
  const sources = ["cash_and_equivalents", "interest_expense", "capex"].map((key) => {
    const source = latest.field_provenance?.[key];
    return `<li>${esc(label(key))} · ${esc(source?.tag ?? "Thiếu dữ liệu")}${source
      ? ` · ${esc(source.unit)} · ${esc(source.accn)}` : ""}</li>`;
  }).join("");
  $("credit-memo").innerHTML = `<header><p>FINHEALTH / NGHIÊN CỨU TÍN DỤNG</p>
    <h1>Báo cáo rủi ro tín dụng</h1><h2>${esc(company.name)} · ${esc(company.ticker ?? company.cik)}</h2>
    <p>CIK ${esc(company.cik)} · ${esc(label(company.sector ?? "Unknown"))} · Năm tài chính ${latest.fiscal_year}</p></header>
    <h3>Nguồn hồ sơ</h3><p>${esc(latest.form_type)} · Mã hồ sơ SEC ${esc(latest.accession_number ?? "—")}
    · Kết thúc kỳ ${esc(date(latest.period_end_date))} · Nộp ngày ${esc(date(latest.filed_date))}</p><ul>${sources}</ul>
    <h3>Chỉ số tín dụng</h3><p>${CREDIT_METRICS.map((key) =>
      `${esc(label(key))} ${creditValue(key, latest[key])}`).join(" · ")}</p>
    <h3>Nhóm đối chiếu</h3><p>${esc(label(peers?.cohort === "sector" ? peers.sector : peers?.cohort))}
      · ${peers?.cohort_size ?? 0} công ty</p>
    <table><thead><tr><th>Chỉ tiêu</th><th>Trung vị</th><th>Phân vị</th><th>Số quan sát</th></tr></thead><tbody>
    ${Object.entries(peers?.metrics ?? {}).map(([key, stat]) => `<tr>
      <td>${esc(label(key))}</td><td>${creditValue(key, stat.median)}</td>
      <td>${number(stat.percentile, 1)}</td><td>${stat.n_observed}</td></tr>`).join("")}</tbody></table>
    <h3>Xu hướng tài chính</h3><table><thead><tr><th>Chỉ tiêu</th><th>Năm trước</th><th>Năm mới nhất</th>
      <th>Dự báo năm ${prediction?.target_fiscal_year ?? "—"}</th></tr></thead><tbody>${forecasts}</tbody></table>
    <h3>Đánh giá rủi ro</h3><p>Chỉ báo khó khăn tài chính ${percent(prediction?.distress_probability)} ·
      ${esc(label(prediction?.risk_level ?? "UNSCORED"))} · Altman Z ${number(latest.altman_z_score)} ·
      Mô hình ${esc(prediction?.model_version ?? "Thiếu dữ liệu")}</p>
    <ul>${(prediction?.top_drivers ?? []).slice(0, 5).map((row) =>
      `<li>${esc(label(row.feature))} · ${number(row.shap_value, 4)} ${isProb ? "đóng góp xác suất trước hiệu chỉnh" : "log-odds trước hiệu chỉnh"}</li>`).join("")}</ul>
    <p class="memo-disclosure">Chỉ báo khó khăn tài chính được tính từ số liệu kế toán năm. Phạm vi mô hình chỉ bao gồm chỉ báo này. Altman X4 dùng vốn chủ sở hữu theo giá trị sổ sách. Phương pháp giải thích đóng góp của các yếu tố cho ${isProb ? "xác suất gốc trước hiệu chỉnh" : "điểm log-odds trước hiệu chỉnh"}.</p>`;
  window.print();
}

function renderDiagnostic(company, latest, prediction) {
  const drivers = prediction?.top_drivers?.slice(0, 3) ?? [];
  const shapUnit = prediction?.output_space === "probability" ? "đóng góp xác suất" : "log-odds";
  const forecastDeltas = ["roa", "debt_ratio", "ocf_ratio"].filter((key) =>
    finite(latest?.[key]) && finite(prediction?.[`pred_${key}`])).map((key) =>
    `${label(key)} ${delta(key, latest[key], prediction[`pred_${key}`])}`);
  const notes = [
    `${company.ticker ?? company.name} · Nhóm sức khỏe tài chính ${label(company.cluster_label ?? "UNAVAILABLE")}.
      Xác suất khó khăn tài chính kỳ tới ${percent(prediction?.distress_probability)}. Mức rủi ro ${label(prediction?.risk_level ?? "UNSCORED").toLowerCase()}.`,
    `Điểm Altman theo vốn chủ sở hữu sổ sách ${number(latest?.altman_z_score, 3)} · ${label(latest?.altman_zone ?? "UNAVAILABLE")}.
      Nợ phải trả / tài sản ${percent(latest?.debt_ratio)} và dòng tiền hoạt động / nợ phải trả ${percent(latest?.ocf_ratio)}.`,
    prediction && forecastDeltas.length
      ? `Dự báo năm ${prediction.target_fiscal_year} so với năm báo cáo gần nhất · ${forecastDeltas.join(" · ")}.`
      : "Chưa có số liệu để đối chiếu dự báo với kỳ gần nhất.",
    drivers.length ? `Các yếu tố tác động mạnh nhất đến dự báo gồm ${drivers.map((row) =>
      `${label(row.feature)} (${row.shap_value >= 0 ? "+" : ""}${number(row.shap_value, 3)} ${shapUnit},
      ${row.shap_value >= 0 ? "tăng" : "giảm"} rủi ro)`).join(" · ")}.`
      : "Chưa có thông tin giải thích cho kỳ này.",
  ];
  $("diagnostic-summary").innerHTML = notes.map((note) => `<li>${esc(note)}</li>`).join("");
}

function renderAttribution({ company, history, latest_prediction: prediction, altman_components: components }) {
  const latest = history.at(-1);
  const isProb = prediction?.output_space === "probability";
  $("explain-company").textContent = `${company.ticker ?? company.cik} · ${company.name} · Dữ liệu tài chính năm ${latest?.fiscal_year ?? "—"}`;
  const threshold = (state.evaluation?.evaluation_report?.classification_selected ?? state.evaluation?.evaluation_report?.classification_xgboost)?.threshold;
  renderRiskGauge($("explain-gauge"), prediction?.distress_probability, prediction?.risk_level, threshold);
  $("gauge-context").textContent = prediction
    ? `Chỉ báo khó khăn tài chính năm ${prediction.target_fiscal_year}. Ngưỡng phân loại được chọn trên tập hiệu chỉnh.`
    : "Chưa có dự báo khó khăn tài chính kỳ tới.";
  const scaleLabel = $("shap-scale-label");
  if (scaleLabel) {
    scaleLabel.textContent = isProb ? "Đóng góp có dấu trên thang xác suất" : "Đóng góp có dấu trên thang log-odds";
  }
  renderShapWaterfallChart($("shap-chart"), prediction);
  const contributions = prediction?.contributions ?? {};
  const all = Object.entries(contributions).sort((a, b) => Math.abs(b[1] ?? 0) - Math.abs(a[1] ?? 0));
  const complete = finite(prediction?.base_value) && all.length && all.every(([, value]) => finite(value));
  const summed = complete ? prediction.base_value + all.reduce((sum, [, value]) => sum + value, 0) : null;
  const finalProbability = finite(summed)
    ? (isProb ? summed : 1 / (1 + Math.exp(-summed)))
    : null;
  const shapErr = state.evaluation?.evaluation_report?.shap_margin_max_abs_error;
  $("shap-reconciliation").innerHTML = [
    `Giá trị gốc <strong>${number(prediction?.base_value, 4)}</strong>`,
    `Giá trị gốc + tổng đóng góp <strong>${number(summed, 4)} ${isProb ? "(xác suất)" : "log-odds"}</strong>`,
    `${isProb ? "Xác suất gốc trước hiệu chỉnh" : "Xác suất sigmoid trước hiệu chỉnh"} <strong>${percent(finalProbability, 3)}</strong>`,
    `Xác suất mô hình công bố <strong>${percent(prediction?.distress_probability, 3)}</strong>`,
    ...(finite(shapErr) ? [`Sai số đối soát phần giải thích tối đa <strong>${shapErr.toExponential(2)}</strong>`] : []),
  ].map((text) => `<span>${text}</span>`).join("");
  $("feature-count").textContent = `${all.length} đặc trưng của mô hình`;
  $("attribution-table").innerHTML = all.map(([key, value]) => `<tr>
    <td>${esc(label(key))}</td><td class="numeric" title="${esc(latest?.[key])}">${metricValue(key, latest?.[key])}</td>
    <td class="numeric" title="${esc(prediction?.feature_values?.[key])}">${metricValue(key, prediction?.feature_values?.[key])}</td>
    <td class="numeric ${finite(value) ? (value >= 0 ? "critical" : "low") : "neutral"}" title="${esc(value)}">${finite(value) ? (value >= 0 ? "+" : "") + number(value, 5) : "—"}</td>
    <td class="effect ${finite(value) ? (value >= 0 ? "critical" : "low") : "neutral"}">${finite(value) ? (value >= 0 ? "Tăng rủi ro →" : "← Giảm rủi ro") : "—"}</td></tr>`).join("")
    || '<tr><td colspan="5" class="empty">Chưa lưu đóng góp của các đặc trưng.</td></tr>';
  const manufacturing = company.sic_code != null && Number(company.sic_code) >= 2000 && Number(company.sic_code) <= 3999;
  const weights = manufacturing ? [1.2, 1.4, 3.3, 0.6, 1] : [6.56, 3.26, 6.72, 1.05];
  $("altman-variant").textContent = manufacturing ? "Sản xuất · SIC 2000–3999" : "Ngoài ngành sản xuất · Z″";
  $("altman-score").innerHTML = `${number(latest?.altman_z_score, 3)} ${badge(latest?.altman_zone)}`;
  const componentLabels = ["Vốn lưu động / tài sản", "Lợi nhuận giữ lại / tài sản",
    "Lợi nhuận hoạt động / tài sản", "Vốn chủ sở hữu theo sổ sách / nợ phải trả", "Doanh thu / tài sản"];
  $("altman-table").innerHTML = componentLabels.map((label, index) => {
    const value = components?.[`X${index + 1}`], weight = weights[index];
    return `<tr><td><strong>X${index + 1}</strong> · ${label}</td><td class="numeric">${number(value, 4)}</td>
      <td class="numeric">${finite(weight) ? number(weight) : "Không áp dụng"}</td>
      <td class="numeric">${finite(value) && finite(weight) ? number(value * weight, 4) : "—"}</td></tr>`;
  }).join("");
}

function renderModelSelectors() {
  const pickModel = (dataset) => {
    const candidates = state.modelVersions.filter((item) => item.dataset === dataset);
    return candidates.find((item) => item.is_active) ?? candidates.sort((a, b) =>
      String(b.created_at ?? "").localeCompare(String(a.created_at ?? "")) ||
      String(a.model_version).localeCompare(String(b.model_version)))[0];
  };
  const manualModels = [[pickModel("sec"), "Cảnh báo sớm khó khăn tài chính"],
    [pickModel("kaggle"), "Dự báo nguy cơ phá sản"]].filter(([item]) => item);
  const manualOptions = manualModels.map(([item, name]) =>
    `<option value="${esc(item.model_version)}">${esc(name)}</option>`).join("");
  const scienceOptions = manualOptions;
  const manualSelect = $("manual-model-version");
  if (manualSelect && manualOptions) {
    const prev = manualSelect.value;
    manualSelect.innerHTML = manualOptions;
    if (prev && manualModels.some(([item]) => item.model_version === prev)) {
      manualSelect.value = prev;
    }
  }
  const scienceSelect = $("science-model-select");
  if (scienceSelect && scienceOptions) {
    scienceSelect.innerHTML = scienceOptions;
    const preferred = state.scienceVersion || state.evaluation?.model_version || "";
    const chosen = manualModels.some(([item]) => item.model_version === preferred)
      ? preferred : manualModels[0]?.[0].model_version;
    if (chosen) scienceSelect.value = chosen;
  }
}

function renderScience() {
  const evaluation = state.scienceEvaluation ?? state.evaluation;
  if (!evaluation) {
    $("science-model").textContent = "Chưa có kết quả đánh giá";
    $("benchmark-table").innerHTML = '<tr><td colspan="11" class="empty">Máy chủ chưa có báo cáo đánh giá cho mô hình hiện hành.</td></tr>';
    return;
  }
  const report = evaluation.evaluation_report;
  const summary = report.split_summary;
  const cluster = report.clustering;
  const strategyLabel = report.imbalance_strategy === "smote" ? "SMOTE" : "Class Weight";
  $("science-model").textContent = "Kết quả đánh giá";
  $("science-kpis").innerHTML = [
    kpi("Quan sát huấn luyện theo đặc trưng", number(summary.train_feature_rows, 0), `Đến năm tài chính ${summary.train_end_year}`, "▤"),
    kpi("Quan sát huấn luyện có nhãn hợp lệ", number(summary.train_supervised_rows, 0), "Nhãn đã quan sát được tại thời điểm chốt tập huấn luyện", "◷"),
    kpi("Quan sát kiểm định ngoài giai đoạn huấn luyện", number(summary.test_rows, 0), `${summary.test_classification_rows} kết quả kỳ tới có nhãn`, "↗"),
    kpi("Phương sai tích lũy của PCA", percent(cluster.cumulative_variance_ratio), "Ba thành phần chính đầu tiên", "◈", true),
  ].join("");
  $("pca-legend").innerHTML = [0, 1, 2, 3].map((id) =>
    `<span><i style="background:${COLORS[id]}"></i>${esc(regimeLabel(id))}</span>`).join("");
  $("cluster-diagnostics").textContent = `Silhouette ${number(cluster.silhouette_score, 3)} · Tâm cụm trong không gian đặc trưng gốc`;
  $("centroid-table").innerHTML = Object.entries(cluster.cluster_profiles).sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([id, profile]) => `<tr><td>${badge(regimeLabel(id), `cluster-${id}`)}</td>
      <td class="numeric">${number(profile.health_score, 3)}</td>
      ${["roa", "roe", "ocf_ratio", "current_ratio", "debt_ratio"].map((key) =>
        `<td class="numeric">${metricValue(key, profile.centroid[key])}</td>`).join("")}</tr>`).join("");
  const selectedModel = report.selected_model_name ?? "xgboost";
  const classification = report.classification_candidates
    ? {
        ...report.classification_candidates,
        ...(report.classification_xgboost_raw && { xgboost_raw: report.classification_xgboost_raw }),
      }
    : {
        [report.probability_calibration ? "XGBoost đã hiệu chỉnh" : "XGBoost"]: report.classification_xgboost,
        ...(report.classification_xgboost_raw && { "XGBoost trước hiệu chỉnh": report.classification_xgboost_raw }),
        ...report.classification_baselines,
      };
  $("classification-context").textContent = `${summary.test_classification_rows} quan sát có nhãn · Mô hình chính: ${label(selectedModel)} · Ngày hiệu chỉnh ${date(summary.threshold_calibration_asof)}`;
  $("benchmark-table").innerHTML = Object.entries(classification).map(([name, row]) => {
    const isSelected = name === selectedModel;
    return `<tr><td><strong>${esc(label(name))}${isSelected ? " (Mô hình chính)" : ""}</strong></td><td class="numeric">${percent(row.threshold)}</td>
    ${["roc_auc", "pr_auc", "precision", "recall", "f1_score", "f2_score", "brier_score", "log_loss"].map((key) =>
      `<td class="numeric">${number(row[key], 4)}</td>`).join("")}
    <td class="numeric">${["tn", "fp", "fn", "tp"].map((key) => row.confusion_matrix[key]).join(" / ")}</td></tr>`;
  }).join("");
  const pairedModel = report.forecasting_paired?.model ?? {};
  const pairedPersist = report.forecasting_paired?.persistence ?? {};
  const shrinkage = report.forecast_shrinkage ?? {};
  $("regression-table").innerHTML = Object.entries(report.forecasting).map(([key, row]) => {
    const m = pairedModel[key] ?? row;
    const p = pairedPersist[key];
    return `<tr><td>${esc(label(key))}</td>
      <td class="numeric">${number(m.r2, 4)}</td>
      <td class="numeric">${number(p?.r2, 4)}</td>
      <td class="numeric">${number(m.mae, 4)}</td>
      <td class="numeric">${number(p?.mae, 4)}</td>
      <td class="numeric">${number(m.rmse, 4)}</td>
      <td class="numeric">${finite(shrinkage[key]) ? number(shrinkage[key], 2) : "—"}</td>
      <td class="numeric">${number(m.n_samples ?? row.n_samples, 0)}</td></tr>`;
  }).join("");
  const validationCard = $("validation-card");
  const validationCandidates = report.validation_candidates;
  if (validationCard && validationCandidates && Object.keys(validationCandidates).length) {
    validationCard.hidden = false;
    const cal = report.probability_calibration;
    const shapErr = report.shap_margin_max_abs_error;
    const countsBefore = report.train_class_counts_before;
    const countsAfter = report.train_class_counts_after;
    const countText = countsBefore && countsAfter
      ? `${countsBefore[0] ?? countsBefore["0"]} / ${countsBefore[1] ?? countsBefore["1"]} → ${countsAfter[0] ?? countsAfter["0"]} / ${countsAfter[1] ?? countsAfter["1"]}`
      : `scale_pos_weight = ${number(report.classifier_scale_pos_weight, 2)}`;
    $("calibration-meta").textContent = `${summary.validation_rows ?? "—"} quan sát validation (${summary.validation_positive_rows ?? "—"} dương tính) · ${summary.threshold_source ?? ""}`;
    $("calibration-summary").innerHTML = [
      `<div><span>Mô hình được chọn</span><strong>${esc(label(selectedModel))}</strong></div>`,
      `<div><span>Cân bằng dữ liệu (Âm / Dương)</span><strong>${esc(strategyLabel)} (${esc(countText)})</strong></div>`,
      `<div><span>Hiệu chuẩn Platt (slope / intercept)</span><strong>${Array.isArray(cal) && cal.length === 2 ? `${number(cal[0], 4)} / ${number(cal[1], 4)}` : "—"}</strong></div>`,
      `<div><span>Sai số đối soát phần giải thích tối đa</span><strong>${finite(shapErr) ? shapErr.toExponential(2) : "—"}</strong></div>`,
      `<div><span>Tỷ lệ dương tính tập kiểm định</span><strong>${percent(report.classification_selected?.prevalence, 2)}</strong></div>`,
    ].join("");
    $("validation-table").innerHTML = Object.entries(validationCandidates).map(([name, row]) => {
      const isSelected = name === selectedModel;
      return `<tr><td><strong>${esc(label(name))}${isSelected ? " (Được chọn)" : ""}</strong></td>
        <td class="numeric">${percent(row.threshold)}</td>
        <td class="numeric">${number(row.roc_auc, 4)}</td>
        <td class="numeric">${number(row.pr_auc, 4)}</td>
        <td class="numeric">${number(row.f2_score, 4)}</td>
        <td class="numeric">${number(row.brier_score, 4)}</td>
        <td class="numeric">${number(row.log_loss, 4)}</td></tr>`;
    }).join("");
  } else if (validationCard) {
    validationCard.hidden = true;
  }
}

function renderFigures() {
  $("figure-gallery").innerHTML = FIGURES.map(([file, title], index) =>
    `<button class="figure-card" data-figure="${index}" aria-label="Xem ${esc(title)}">
      <img loading="lazy" src="/api/v1/figures/${file}" alt="${esc(title)}">
      <span>${esc(title)}<i aria-hidden="true">↗</i></span></button>`).join("");
  for (const image of $("figure-gallery").querySelectorAll("img")) {
    image.addEventListener("error", () => {
      image.hidden = true;
      image.closest("button").disabled = true;
      const label = document.createElement("p");
      label.className = "empty";
      label.textContent = "Biểu đồ chưa có trên máy chủ";
      image.after(label);
    }, { once: true });
  }
}

async function selectCompany(identifier, suppliedAnalysis = null) {
  const sequence = ++selectionSequence;
  companyRequest?.abort();
  companyRequest = new AbortController();
  $("workspace").setAttribute("aria-busy", "true");
  try {
    const analysis = suppliedAnalysis ?? await api.company(identifier, { signal: companyRequest.signal });
    if (sequence !== selectionSequence) return;
    state.selected = analysis;
    state.selectedCik = analysis.company.cik;
    renderSelectors();
    renderCompany();
    renderScreener();
    renderMaps();
    if (state.tab === "reports" && reportsController) void reportsController.refresh();
  } catch (error) {
    if (error.name !== "AbortError") notice(`Không tải được dữ liệu công ty. ${error.message}`, true);
  } finally {
    if (sequence === selectionSequence) $("workspace").setAttribute("aria-busy", "false");
  }
}

async function loadUniverse() {
  const keys = ["health", "companies", "clusters", "evaluation", "inventory", "modelVersions"];
  const results = await Promise.allSettled([
    api.health(), api.companies(), api.clusters(), api.evaluation(), api.overview(), api.modelVersions(),
  ]);
  const failures = [];
  results.forEach((result, index) => {
    if (result.status === "fulfilled") state[keys[index]] = result.value;
    else failures.push(`${DATA_SOURCES[keys[index]]}: ${result.reason.message}`);
  });
  if (failures.length) notice(failures.join(" · "), true);
  if (!state.scienceVersion && state.evaluation?.model_version) {
    state.scienceVersion = state.evaluation.model_version;
    state.scienceEvaluation = state.evaluation;
  }
  renderStatus();
  renderSelectors();
  renderModelSelectors();
  renderScreener();
  renderDistributions();
  renderScience();
  renderMaps();
  await refreshScreening();
}

function renderManualResult(data) {
  const { prediction, ratios } = data;
  const isProb = prediction?.output_space === "probability";
  const threshold = data.classification_threshold
    ?? (state.evaluation?.evaluation_report?.classification_selected
      ?? state.evaluation?.evaluation_report?.classification_xgboost)?.threshold;
  $("manual-result-title").textContent = `${data.company_name} · FY ${data.fiscal_year}`;
  renderRiskGauge($("manual-gauge"), prediction?.distress_probability, prediction?.risk_level, threshold);
  const oodNote = data.is_ood_scenario
    ? ` · Cảnh báo ngoài khoảng huấn luyện (P1–P99): ${data.ood_features.map(label).join(", ")}`
    : "";
  const versionObj = state.modelVersions.find((v) => v.model_version === prediction?.model_version);
  const horizonNote = versionObj?.dataset === "kaggle"
    ? "Mục tiêu: Dự báo xác suất Phá sản pháp lý thực tế (sự kiện hiếm nên ngưỡng phân loại thấp hơn cảnh báo khó khăn tài chính)"
    : "Mục tiêu: Cảnh báo sớm Khó khăn / Kiệt quệ tài chính kỳ tới (suy giảm dòng tiền & đòn bẩy)";
  $("manual-summary-meta").innerHTML =
    `<strong>${esc(horizonNote)}</strong> · Nhóm sức khỏe: ${badge(data.cluster_label, `cluster-${data.cluster_id}`)}
     · Altman ${data.is_manufacturing ? "Z" : "Z″"}: <strong>${number(data.altman_z_score, 3)}</strong> ${badge(data.altman_zone)}${esc(oodNote)}`;
  $("manual-shap-scale").textContent = isProb
    ? "Đóng góp có dấu trên thang xác suất" : "Đóng góp có dấu trên thang log-odds";
  renderShapWaterfallChart($("manual-shap-chart"), prediction);
  const contributions = prediction?.contributions ?? {};
  const all = Object.entries(contributions).sort((a, b) => Math.abs(b[1] ?? 0) - Math.abs(a[1] ?? 0));
  const complete = finite(prediction?.base_value) && all.length && all.every(([, v]) => finite(v));
  const summed = complete ? prediction.base_value + all.reduce((s, [, v]) => s + v, 0) : null;
  const rawProb = finite(summed) ? (isProb ? summed : 1 / (1 + Math.exp(-summed))) : null;
  $("manual-shap-reconciliation").innerHTML = [
    `Giá trị gốc <strong>${number(prediction?.base_value, 4)}</strong>`,
    `Giá trị gốc + tổng đóng góp <strong>${number(summed, 4)} ${isProb ? "(xác suất)" : "log-odds"}</strong>`,
    `${isProb ? "Xác suất gốc trước hiệu chỉnh" : "Xác suất sigmoid trước hiệu chỉnh"} <strong>${percent(rawProb, 3)}</strong>`,
    `Xác suất mô hình công bố <strong>${percent(prediction?.distress_probability, 3)}</strong>`,
  ].map((text) => `<span>${text}</span>`).join("");
  $("manual-feature-count").textContent = `${all.length} đặc trưng của mô hình`;
  $("manual-attribution-table").innerHTML = all.map(([key, value]) => `<tr>
    <td>${esc(label(key))}</td>
    <td class="numeric">${metricValue(key, ratios?.[key])}</td>
    <td class="numeric">${metricValue(key, prediction?.feature_values?.[key])}</td>
    <td class="numeric ${finite(value) ? (value >= 0 ? "critical" : "low") : "neutral"}">${finite(value) ? (value >= 0 ? "+" : "") + number(value, 5) : "—"}</td>
    <td class="effect ${finite(value) ? (value >= 0 ? "critical" : "low") : "neutral"}">${finite(value) ? (value >= 0 ? "Tăng rủi ro →" : "← Giảm rủi ro") : "—"}</td></tr>`).join("");
  $("manual-altman-meta").textContent = `Dự báo năm tài chính ${prediction?.target_fiscal_year ?? "—"}`;
  $("manual-ratios-table").innerHTML = ALL_RATIOS.map((key) => {
    const forecast = METRICS.includes(key) ? metricValue(key, prediction?.[`pred_${key}`]) : "—";
    const current = CREDIT_METRICS.includes(key) ? creditValue(key, ratios?.[key]) : metricValue(key, ratios?.[key]);
    return `<tr><td>${esc(label(key))}</td><td class="numeric">${current}</td><td class="numeric">${forecast}</td></tr>`;
  }).join("");
  const pillarsContainer = $("manual-pillars-and-advice");
  if (pillarsContainer) {
    const checklist = data.accounting_checklist;
    const dupont = data.dupont;
    const qoe = data.quality_of_earnings;
    const extraMeta = `<div class="credit-ratios" style="margin-top:0.75rem;">
      <div><span>ROE DuPont bình quân</span><strong>${percent(dupont?.roe_dupont_avg, 2)}</strong></div>
      <div><span>Chuyển hóa dòng tiền (OCF / Lợi nhuận ròng)</span><strong>${finite(qoe?.cash_conversion_qoe) ? number(qoe.cash_conversion_qoe, 3) + "×" : "—"}</strong></div>
      <div><span>Checklist tín hiệu kế toán (Piotroski)</span><strong>${checklist?.observed_passes ?? 0} đạt / ${checklist?.observed_checks ?? 0} có dữ liệu</strong></div>
    </div>`;
    pillarsContainer.innerHTML = renderHealthPillarsAndAdvice(data.health_pillars, data.recommendations) + extraMeta;
  }
  $("manual-results").hidden = false;
}

function fillManualFromSelected() {
  const analysis = state.selected;
  const latest = analysis?.history?.at(-1);
  if (!latest) {
    $("manual-status").textContent = "Chưa có công ty nào được chọn để nạp số liệu.";
    return;
  }
  const prior = analysis.history.at(-2);
  const form = $("manual-form");
  const manufacturing = analysis.company.sic_code != null
    && Number(analysis.company.sic_code) >= 2000 && Number(analysis.company.sic_code) <= 3999;
  const setVal = (name, val) => {
    const el = form.elements.namedItem(name);
    if (el) el.value = val == null ? "" : String(val);
  };
  setVal("company_name", `${analysis.company.ticker ?? analysis.company.cik} · ${analysis.company.name}`);
  setVal("fiscal_year", latest.fiscal_year);
  setVal("is_manufacturing", String(manufacturing));
  for (const field of [
    "total_assets", "current_assets", "total_liabilities", "current_liabilities",
    "stockholders_equity", "retained_earnings", "revenues", "operating_income",
    "net_income", "operating_cash_flow", "cash_and_equivalents", "interest_expense",
    "capex", "eps_diluted",
  ]) {
    setVal(field, latest[field] ?? (field === "eps_diluted" ? latest.eps : null));
  }
  if (prior && prior.fiscal_year === latest.fiscal_year - 1) {
    setVal("prior_total_assets", prior.total_assets);
    setVal("prior_current_assets", prior.current_assets);
    setVal("prior_total_liabilities", prior.total_liabilities);
    setVal("prior_current_liabilities", prior.current_liabilities);
    setVal("prior_stockholders_equity", prior.stockholders_equity);
    setVal("prior_revenues", prior.revenues);
    setVal("prior_operating_income", prior.operating_income);
    setVal("prior_net_income", prior.net_income);
    setVal("prior_operating_cash_flow", prior.operating_cash_flow);
  }
  $("manual-status").textContent = `Đã nạp số liệu thật FY ${latest.fiscal_year} của ${analysis.company.ticker ?? analysis.company.cik}. Bạn có thể chỉnh sửa và bấm Dự báo.`;
}

const VN_PRESETS = {
  FPT: {
    company_name: "VN:FPT · Công ty Cổ phần FPT (BCTC Hợp nhất Kiểm toán)",
    fiscal_year: 2025,
    is_manufacturing: false,
    total_assets: 88141991634625,
    current_assets: 54210000000000,
    total_liabilities: 44393950887086,
    current_liabilities: 41524928721230,
    stockholders_equity: 43748040747539,
    retained_earnings: 14120000000000,
    revenues: 70112825100710,
    operating_income: 13050000000000,
    net_income: 11232339450734,
    operating_cash_flow: 10136043915911,
    cash_and_equivalents: 9315000000000,
    interest_expense: 545000000000,
    capex: 3850000000000,
    eps_diluted: 6420,
  },
  HPG: {
    company_name: "VN:HPG · CTCP Tập đoàn Hòa Phát (BCTC Hợp nhất Kiểm toán)",
    fiscal_year: 2025,
    is_manufacturing: true,
    total_assets: 257899200817547,
    current_assets: 112450000000000,
    total_liabilities: 126679189940972,
    current_liabilities: 94186268324508,
    stockholders_equity: 131220010876575,
    retained_earnings: 48650000000000,
    revenues: 156116094618482,
    operating_income: 18420000000000,
    net_income: 15514931571606,
    operating_cash_flow: 17365859056591,
    cash_and_equivalents: 14200000000000,
    interest_expense: 3420000000000,
    capex: 12500000000000,
    eps_diluted: 2420,
    prior_total_assets: 224489707553981,
    prior_current_assets: 96500000000000,
    prior_total_liabilities: 109842249570282,
    prior_current_liabilities: 75225243262689,
    prior_stockholders_equity: 114647457983699,
    prior_revenues: 138855112131387,
    prior_operating_income: 14500000000000,
    prior_net_income: 12020023621271,
    prior_operating_cash_flow: 6608320655215,
  },
};

function fillManualFromVietnamPreset(code) {
  const preset = VN_PRESETS[code];
  if (!preset) return;
  const form = $("manual-form");
  const setVal = (name, val) => {
    const el = form.elements.namedItem(name);
    if (el) el.value = val == null ? "" : String(val);
  };
  for (const field of [
    "company_name", "fiscal_year", "is_manufacturing",
    "total_assets", "current_assets", "total_liabilities", "current_liabilities",
    "stockholders_equity", "retained_earnings", "revenues", "operating_income",
    "net_income", "operating_cash_flow", "cash_and_equivalents", "interest_expense",
    "capex", "eps_diluted", "prior_total_assets", "prior_current_assets",
    "prior_total_liabilities", "prior_current_liabilities", "prior_stockholders_equity",
    "prior_revenues", "prior_operating_income", "prior_net_income", "prior_operating_cash_flow",
  ]) {
    setVal(field, preset[field]);
  }
  $("manual-status").textContent = `Đã nạp số liệu ví dụ của ${preset.company_name} (VND). Kiểm tra dữ liệu và bấm Dự báo để tiếp tục.`;
}

const BATCH_COLUMNS = [
  "company_name", "fiscal_year", "is_manufacturing",
  "total_assets", "current_assets", "total_liabilities", "current_liabilities",
  "stockholders_equity", "retained_earnings", "revenues", "operating_income",
  "net_income", "operating_cash_flow", "cash_and_equivalents", "interest_expense",
  "capex", "eps_diluted", "prior_total_assets", "prior_total_liabilities",
  "prior_stockholders_equity", "prior_net_income", "prior_operating_cash_flow",
];

function downloadBatchTemplate() {
  const sampleRows = [
    VN_PRESETS.FPT,
    VN_PRESETS.HPG,
    {
      company_name: "Doanh nghiệp Mẫu Rủi ro cao",
      fiscal_year: 2025,
      is_manufacturing: true,
      total_assets: 120000000000,
      current_assets: 32000000000,
      total_liabilities: 108000000000,
      current_liabilities: 75000000000,
      stockholders_equity: 12000000000,
      retained_earnings: -18000000000,
      revenues: 65000000000,
      operating_income: -6500000000,
      net_income: -11200000000,
      operating_cash_flow: -8400000000,
      cash_and_equivalents: 3500000000,
      interest_expense: 5200000000,
      capex: 1500000000,
      eps_diluted: -1120,
      prior_total_assets: 135000000000,
      prior_total_liabilities: 111000000000,
      prior_stockholders_equity: 24000000000,
      prior_net_income: -4500000000,
      prior_operating_cash_flow: -3100000000,
    },
  ];
  downloadCsv("finhealth-mau-danh-muc-bctc.csv", BATCH_COLUMNS, sampleRows, (c) => c);
}

let lastBatchResponse = null;

function renderBatchResults(data) {
  lastBatchResponse = data;
  const counts = data.risk_counts ?? {};
  const highCount = (counts.HIGH ?? 0) + (counts.CRITICAL ?? 0);
  $("batch-kpis").innerHTML = [
    `<div><span>Tổng số doanh nghiệp</span><strong>${number(data.total_companies, 0)}</strong></div>`,
    `<div><span>Rủi ro thấp (LOW)</span><strong>${number(counts.LOW ?? 0, 0)}</strong></div>`,
    `<div><span>Rủi ro trung bình (MEDIUM)</span><strong>${number(counts.MEDIUM ?? 0, 0)}</strong></div>`,
    `<div><span>Rủi ro cao &amp; rất cao</span><strong>${number(highCount, 0)}</strong></div>`,
    `<div><span>Xác suất rủi ro TB</span><strong>${percent(data.average_distress_probability, 2)}</strong></div>`,
    `<div><span>Điểm sức khỏe 4 trụ cột TB</span><strong>${finite(data.average_health_score) ? number(data.average_health_score, 1) + " / 100" : "—"}</strong></div>`,
  ].join("");
  $("batch-table-body").innerHTML = (data.results ?? []).map((item) => `
    <tr>
      <td><strong>${esc(item.company_name)}</strong></td>
      <td class="numeric">${esc(String(item.fiscal_year))}</td>
      <td class="numeric">${percent(item.distress_probability, 2)}</td>
      <td>${badge(item.risk_level)}</td>
      <td class="numeric">${finite(item.overall_health_score) ? `${number(item.overall_health_score, 1)} (${esc(item.overall_health_grade)})` : "—"}</td>
      <td class="numeric">${finite(item.altman_z_score) ? `${number(item.altman_z_score, 2)} ${badge(item.altman_zone)}` : "—"}</td>
      <td>${badge(item.cluster_label, `cluster-${item.cluster_id}`)}</td>
      <td class="numeric">${percent(item.roa, 2)}</td>
      <td class="numeric">${percent(item.debt_ratio, 2)}</td>
      <td>${item.top_risk_driver ? esc(label(item.top_risk_driver)) : "—"}</td>
      <td>${esc(item.top_recommendation_vi ?? "—")}</td>
    </tr>`).join("");
  $("batch-results").hidden = false;
  $("export-batch-csv").disabled = !(data.results && data.results.length);
}

async function handleBatchCsvUpload(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  await ensureUser(() => processBatchCsv(file));
}

async function processBatchCsv(file) {
  $("batch-status").textContent = `Đang đọc file ${file.name} và chấm điểm danh mục…`;
  try {
    const text = await file.text();
    const rawRows = parseCsv(text);
    if (!rawRows.length) {
      $("batch-status").textContent = "File CSV trống hoặc không đúng định dạng.";
      return;
    }
    const items = rawRows.slice(0, 200).map((row, index) => {
      const mfgRaw = String(row.is_manufacturing ?? "true").trim().toLowerCase();
      const item = {
        company_name: String(row.company_name || `Doanh nghiệp #${index + 1}`).trim(),
        fiscal_year: Number(row.fiscal_year || 2025),
        is_manufacturing: !["false", "0", "no", "phi sản xuất"].includes(mfgRaw),
      };
      for (const numField of BATCH_COLUMNS.slice(3)) {
        const rawVal = String(row[numField] ?? "").trim();
        if (rawVal !== "" && Number.isFinite(Number(rawVal))) {
          item[numField] = Number(rawVal);
        }
      }
      return item;
    });
    const selectedVersion = String($("manual-model-version")?.value || "").trim();
    const res = await api.predictBatch({
      ...(selectedVersion ? { model_version: selectedVersion } : {}),
      items,
    });
    renderBatchResults(res);
    $("batch-status").textContent = `Đã chấm điểm thành công ${res.total_companies} doanh nghiệp từ file ${file.name}.`;
  } catch (error) {
    $("batch-status").textContent = `Lỗi chấm điểm file CSV: ${error.message}`;
  }
}

function exportBatchCsv() {
  if (!lastBatchResponse?.results?.length) return;
  const cols = [
    "company_name", "fiscal_year", "is_manufacturing", "distress_probability", "risk_level",
    "overall_health_score", "overall_health_grade", "altman_z_score", "altman_zone",
    "cluster_label", "roa", "roe", "debt_ratio", "current_ratio", "ocf_ratio",
    "top_risk_driver", "top_recommendation_vi",
  ];
  downloadCsv("finhealth-ket-qua-danh-muc.csv", cols, lastBatchResponse.results, label);
}

async function submitManualForm(event) {
  event.preventDefault();
  const form = $("manual-form");
  const button = $("manual-submit");
  const raw = new FormData(form);
  const selectedVersion = String(raw.get("model_version") || "").trim();
  const payload = {
    ...(selectedVersion ? { model_version: selectedVersion } : {}),
    company_name: String(raw.get("company_name") || "Doanh nghiệp tự nhập").trim(),
    fiscal_year: Number(raw.get("fiscal_year") || 2025),
    is_manufacturing: raw.get("is_manufacturing") === "true",
  };
  for (const field of [
    "total_assets", "current_assets", "total_liabilities", "current_liabilities",
    "stockholders_equity", "retained_earnings", "revenues", "operating_income",
    "net_income", "operating_cash_flow", "cash_and_equivalents", "interest_expense",
    "capex", "eps_diluted", "prior_total_assets", "prior_current_assets",
    "prior_total_liabilities", "prior_current_liabilities", "prior_stockholders_equity",
    "prior_revenues", "prior_operating_income", "prior_net_income", "prior_operating_cash_flow",
  ]) {
    const val = String(raw.get(field) ?? "").trim();
    if (val !== "") payload[field] = Number(val);
  }
  button.disabled = true;
  $("manual-status").textContent = "Đang tính tỷ số, dự báo và phân tích các yếu tố ảnh hưởng…";
  try {
    const result = await api.predictManual(payload);
    savedManualInput = { ...structuredClone(payload), model_version: result.prediction.model_version };
    $("save-analysis").disabled = false;
    renderManualResult(result);
    $("manual-status").textContent = "Đã hoàn tất dự báo và giải thích kết quả.";
  } catch (error) {
    $("manual-status").textContent = `Lỗi dự báo: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

async function analyze(event) {
  event.preventDefault();
  if (state.loading) return;
  const identifier = $("analyze-input").value.trim();
  if (!identifier) return;
  state.loading = true;
  const button = $("analyze-button");
  button.disabled = true;
  button.querySelector(".spinner").hidden = false;
  button.querySelector(".analyze-label").textContent = "Đang phân tích…";
  notice(`Đang lấy hồ sơ của ${identifier.toUpperCase()} từ SEC EDGAR và cập nhật phân tích…`);
  try {
    const analysis = await api.analyze(identifier, state.health?.ingestion_queue_enabled);
    await loadUniverse();
    await selectCompany(analysis.company.cik, analysis);
    openTab("company");
    notice(`${analysis.company.ticker ?? analysis.company.cik} đã được cập nhật từ SEC EDGAR. Có thể xem lịch sử tài chính và các dự báo hiện có.`);
  } catch (error) {
    notice(`Không phân tích được hồ sơ SEC. ${error.message}`, true);
  } finally {
    state.loading = false;
    button.disabled = false;
    button.querySelector(".spinner").hidden = true;
    button.querySelector(".analyze-label").textContent = "Phân tích hồ sơ SEC";
  }
}

function bindEvents() {
  for (const form of [$("analyze-form"), $("compare-form")]) {
    form.addEventListener("invalid", ({ target }) => {
      const message = target.id === "compare-year"
        ? "Nhập năm tài chính là số nguyên từ 1990 đến 2100."
        : target.id === "compare-identifiers" ? "Nhập mã chứng khoán hoặc CIK để so sánh."
          : "Nhập mã chứng khoán hoặc CIK của công ty.";
      target.setCustomValidity(message);
    }, true);
    form.addEventListener("input", ({ target }) => target.setCustomValidity(""));
  }
  document.addEventListener("click", (event) => {
    const scenario = event.target.closest("[data-stress-preset]");
    if (scenario) {
      const preset = STRESS_PRESETS[scenario.dataset.stressPreset];
      $("stress-form").querySelectorAll("input[type=range]").forEach((input, index) => {
        input.value = preset[index];
      });
      scheduleStress(0);
    }
    const comparePreset = event.target.closest("[data-compare-preset]");
    if (comparePreset) {
      $("compare-identifiers").value = comparePreset.dataset.comparePreset;
      $("compare-identifiers").setCustomValidity("");
      $("compare-form").requestSubmit();
    }
    const vnPreset = event.target.closest("[data-vn-preset]");
    if (vnPreset) {
      fillManualFromVietnamPreset(vnPreset.dataset.vnPreset);
    }
    const company = event.target.closest("[data-company]");
    if (company) {
      openTab("company");
      selectCompany(company.dataset.company);
    }
    const tab = event.target.closest("[data-tab], [data-open-tab]");
    if (tab) openTab(tab.dataset.tab ?? tab.dataset.openTab);
    const sort = event.target.closest("[data-sort]");
    if (sort) {
      const existing = state.sort.find((item) => item.key === sort.dataset.sort);
      const item = { key: sort.dataset.sort, direction: existing ? -existing.direction : -1 };
      state.sort = event.shiftKey
        ? [...state.sort.filter((item) => item.key !== sort.dataset.sort), item] : [item];
      renderScreener();
    }
    const figure = event.target.closest("[data-figure]");
    if (figure) {
      const [file, title] = FIGURES[Number(figure.dataset.figure)];
      $("figure-title").textContent = title;
      $("figure-image").src = `/api/v1/figures/${file}`;
      $("figure-image").alt = title;
      $("figure-download").href = `/api/v1/figures/${file}`;
      $("figure-lightbox").showModal();
    }
  });
  $("company-selector").addEventListener("change", (event) => {
    openTab("company");
    selectCompany(event.target.value);
  });
  for (const [id, key] of [["screener-search", "search"], ["sector-filter", "sector"], ["risk-filter", "risk"],
    ["cluster-filter", "cluster"], ["year-filter", "year"], ["min-roa-filter", "minRoa"],
    ["max-debt-filter", "maxDebt"], ["min-current-filter", "minCurrent"]]) {
    $(id).addEventListener($(id).tagName === "INPUT" ? "input" : "change", (event) => {
      state.filters[key] = event.target.value;
      screeningRequest?.abort();
      clearTimeout(screeningTimer);
      state.screeningLoading = true;
      $("export-screener").disabled = true;
      screeningTimer = setTimeout(refreshScreening, 200);
    });
  }
  $("reset-filters").addEventListener("click", () => {
    for (const key of Object.keys(state.filters)) state.filters[key] = "";
    for (const id of ["screener-search", "sector-filter", "risk-filter", "cluster-filter", "year-filter",
      "min-roa-filter", "max-debt-filter", "min-current-filter"]) $(id).value = "";
    clearTimeout(screeningTimer);
    state.sort = [{ key: "distress_probability", direction: -1 }];
    void refreshScreening();
  });
  $("pca-axis").addEventListener("change", renderMaps);
  $("science-model-select")?.addEventListener("change", async (event) => {
    const version = event.target.value;
    if (!version) return;
    state.scienceVersion = version;
    try {
      state.scienceEvaluation = version === state.evaluation?.model_version
        ? state.evaluation
        : await api.evaluation(version);
      renderScience();
    } catch (error) {
      notice(`Không tải được báo cáo kiểm định cho ${version}. ${error.message}`, true);
    }
  });
  $("analyze-form").addEventListener("submit", analyze);
  $("manual-form").addEventListener("submit", (event) => {
    event.preventDefault();
    ensureUser(() => submitManualForm(event)).catch((error) => notice(error.message, true));
  });
  $("manual-fill-selected").addEventListener("click", fillManualFromSelected);
  $("manual-reset").addEventListener("click", () => {
    $("manual-results").hidden = true;
    $("manual-status").textContent = "";
  });
  $("download-batch-template")?.addEventListener("click", downloadBatchTemplate);
  $("batch-csv-input")?.addEventListener("change", (event) => handleBatchCsvUpload(event).catch((error) => notice(error.message, true)));
  $("export-batch-csv")?.addEventListener("click", () => ensureUser(exportBatchCsv).catch((error) => notice(error.message, true)));
  $("stress-form").addEventListener("input", () => scheduleStress());
  $("stress-form").addEventListener("reset", () => setTimeout(scheduleStress, 0));
  $("print-memo").addEventListener("click", () => ensureUser(printCreditMemo).catch((error) => notice(error.message, true)));
  $("export-screener").addEventListener("click", () => ensureUser(exportScreener).catch((error) => notice(error.message, true)));
  $("export-history").addEventListener("click", () => ensureUser(exportHistory).catch((error) => notice(error.message, true)));
  $("compare-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runComparison();
  });
  $("compare-company-list").addEventListener("change", (event) => {
    const issuer = event.target.value;
    event.target.value = "";
    if (!issuer) return;
    const input = $("compare-identifiers");
    const selected = input.value.split(",").map((value) => value.trim()).filter(Boolean);
    if (selected.some((value) => value.toUpperCase() === issuer.toUpperCase())) return;
    if (selected.length >= 4) {
      $("compare-status").textContent = "Đã chọn tối đa bốn công ty. Hãy bỏ bớt một công ty trước khi thêm.";
      return;
    }
    input.value = [...selected, issuer].join(", ");
    input.setCustomValidity("");
    $("compare-status").textContent = "";
  });
  $("compare-metric").addEventListener("change", renderComparisonChart);
  $("close-figure").addEventListener("click", () => $("figure-lightbox").close());
  $("figure-lightbox").addEventListener("click", (event) => {
    if (event.target === $("figure-lightbox")) $("figure-lightbox").close();
  });
  document.querySelector(".workspace-nav").addEventListener("keydown", (event) => {
    const tabs = Object.keys(WORKSPACES).filter((name) => !$(`tab-${name}`).hidden);
    let index = tabs.indexOf(state.tab);
    if (["ArrowDown", "ArrowRight"].includes(event.key)) index = (index + 1) % tabs.length;
    else if (["ArrowUp", "ArrowLeft"].includes(event.key)) index = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") index = 0;
    else if (event.key === "End") index = tabs.length - 1;
    else return;
    event.preventDefault();
    openTab(tabs[index]);
    $(`tab-${tabs[index]}`).focus();
  });
  window.addEventListener("hashchange", () => {
    const name = location.hash.slice(1);
    if (WORKSPACES[name] && name !== state.tab) openTab(name);
  });
}

async function start() {
  bindEvents();
  await bindAccount();
  bindPreview();
  $("follow-company").onclick = () => {
    const cik = state.selectedCik;
    if (!cik) return notice("Chọn doanh nghiệp trước khi theo dõi.", true);
    ensureUser(async () => {
      await accountRequest(`/me/watchlist/${encodeURIComponent(cik)}`, "POST");
      notice("Đã lưu doanh nghiệp vào danh sách theo dõi.");
    }).catch((error) => notice(error.message, true));
  };
  $("save-filter").onclick = () => {
    const mapping = {search: ["q", 1], sector: ["sector", 1], risk: ["risk_level", 1],
      cluster: ["cluster_id", 1], year: ["fiscal_year", 1], minRoa: ["min_roa", 100],
      maxDebt: ["max_debt_ratio", 100], minCurrent: ["min_current_ratio", 1]};
    const filters = {};
    for (const [key, [name, scale]] of Object.entries(mapping)) {
      const value = state.filters[key];
      if (value !== "") filters[name] = ["q", "sector", "risk_level"].includes(name) ? value : Number(value) / scale;
    }
    savePersonal("screeners", {name: `Bộ lọc ${new Date().toLocaleString("vi-VN")}`, filters})
      .catch((error) => notice(error.message, true));
  };
  $("save-analysis").onclick = () => {
    if (!savedManualInput) return;
    const inputs = structuredClone(savedManualInput);
    savePersonal("analyses", {name: `${inputs.company_name} · FY ${inputs.fiscal_year}`, inputs})
      .catch((error) => notice(error.message, true));
  };
  window.addEventListener("finhealth:open-company", (event) => {
    openTab("company");
    selectCompany(event.detail.cik).catch((error) => notice(error.message, true));
  });
  window.addEventListener("finhealth:apply-screener", (event) => {
    const filters = event.detail.filters;
    for (const [id, key, parameter, scale] of [
      ["screener-search", "search", "q", 1], ["sector-filter", "sector", "sector", 1],
      ["risk-filter", "risk", "risk_level", 1], ["cluster-filter", "cluster", "cluster_id", 1],
      ["year-filter", "year", "fiscal_year", 1], ["min-roa-filter", "minRoa", "min_roa", 100],
      ["max-debt-filter", "maxDebt", "max_debt_ratio", 100], ["min-current-filter", "minCurrent", "min_current_ratio", 1],
    ]) {
      const value = filters[parameter];
      state.filters[key] = value == null ? "" : String(typeof value === "number" ? value * scale : value);
      $(id).value = state.filters[key];
    }
    openTab("screener");
    refreshScreening();
  });
  reportsController = bindReports(() => state.selectedCik ?? $("company-selector").value);
  renderFigures();
  openTab(location.hash.slice(1) || "screener");
  await loadUniverse();
  const selected = state.companies.find((row) => row.ticker === "AAPL") ?? state.companies[0];
  if (selected) await selectCompany(selected.cik);
  else {
    notice("Cơ sở dữ liệu chưa có công ty nào. Nhập mã chứng khoán để phân tích hồ sơ SEC.", true);
    for (const id of ["company-overview", "attribution-table"]) $(id).textContent = "Chưa có dữ liệu công ty.";
  }
}

start().catch((error) => notice(`Không khởi tạo được bảng phân tích. ${error.message}`, true));
