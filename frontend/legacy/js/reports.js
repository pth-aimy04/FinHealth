/** Browse verified report versions without requesting a fresh upstream pull. */
import { api } from "./api.js";
import { escapeHtml as esc } from "./charts.js";
import { date, label } from "./vi.js";

const $ = (id) => document.getElementById(id);
const sections = [
  ["Bảng cân đối kế toán", ["total_assets", "current_assets", "total_liabilities",
    "current_liabilities", "stockholders_equity", "cash_and_equivalents"]],
  ["Kết quả kinh doanh", ["revenues", "operating_income", "net_income", "parent_net_income",
    "interest_expense", "eps_basic", "eps_diluted"]],
  ["Lưu chuyển tiền tệ", ["operating_cash_flow", "capex"]],
];
const names = { parent_net_income: "Lợi nhuận thuộc cổ đông công ty mẹ" };
const format = (value) => typeof value === "number" ? value.toLocaleString("vi-VN") : "—";
const percent = (value) => value == null ? "—" : format(value * 100) + "%";

function renderFiling(versions) {
  const filing = versions.find((row) => String(row.id) === $("report-version").value);
  if (!filing) {
    $("report-detail").replaceChildren();
    $("report-detail").hidden = true;
    return;
  }
  $("report-detail").hidden = false;
  const url = filing.source_url;
  const link = url?.startsWith("https://")
    ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Mở báo cáo nguồn ↗</a>`
    : "";
  const scope = filing.scope === "consolidated" ? "Hợp nhất" : "Ngữ cảnh đã chọn từ SEC";
  const ratios = [
    ["Nợ phải trả / tài sản", filing.ratios.debt_ratio, "%"],
    ["Biên lợi nhuận sau thuế", filing.ratios.net_margin, "%"],
    ["Dòng tiền kinh doanh / lợi nhuận sau thuế", filing.ratios.cash_conversion, "×"],
  ];
  const disclosureLabel = filing.capture_kind === "legacy_snapshot"
    ? "Bản chụp từ dữ liệu trước khi triển khai kho phiên bản"
    : filing.capture_kind === "verified_pilot"
      ? "Dòng số liệu thí điểm đã đối chiếu với công bố gốc" : "Số liệu đã chuẩn hóa";
  const amendment = filing.capture_kind === "sec_amendment";
  $("report-detail").innerHTML = `<div class="card-heading"><div>
    <h2>${esc(filing.issuer_name ?? filing.issuer_key)} · ${esc(filing.fiscal_period)} ${filing.fiscal_year}</h2>
    <p class="muted">${scope} · Công bố ${date(filing.published_on)} · ${esc(filing.accession)}</p>
    <p class="muted">${amendment ? "Hồ sơ sửa đổi SEC · Chỉ gồm số liệu có trong bản sửa đổi" : disclosureLabel}</p>
    </div>${link}</div><div class="credit-ratios">${ratios.map(([title, value, suffix]) =>
    `<div><span>${title}</span><strong>${value == null ? "—"
      : format(suffix === "%" ? value * 100 : value) + suffix}</strong></div>`).join("")}</div>
    ${sections.map(([name, keys]) => `<section>
      <div class="card-heading"><h2>${name}</h2></div>
      <div class="table-scroll"><table class="data-table">
      <thead><tr><th>Chỉ tiêu</th><th>Giá trị</th><th>Đơn vị</th><th>Kỳ số liệu</th><th>Nguồn</th></tr></thead>
      <tbody>${keys.map((key) => {
    const source = filing.provenance?.[key];
    return `<tr><td>${esc(names[key] ?? label(key))}</td><td>${format(filing.values[key])}</td>
      <td>${esc(source?.unit ?? "—")}</td>
      <td>${source ? `${source.duration_basis === "YTD" ? "Lũy kế " : ""}${source.start ? `${date(source.start)} – ` : ""}${date(source.end ?? filing.period_end)}` : "—"}</td>
      <td>${esc(source?.tag ?? (source?.line ? `${source.form} · dòng ${source.line}`
      : source?.derived ? "Tính theo đẳng thức kế toán" : "Chưa có số liệu đủ căn cứ"))}</td></tr>`;
  }).join("")}</tbody></table></div></section>`).join("")}`;
}

export function bindReports(getCompany) {
  let current = [];
  let controller;
  let evidenceRequest;
  async function showVersion() {
    evidenceRequest?.abort();
    evidenceRequest = new AbortController();
    const signal = evidenceRequest.signal;
    renderFiling(current);
    $("report-evidence").replaceChildren();
    $("report-evidence").hidden = true;
    const id = Number($("report-version").value);
    if (!id || $("report-cutoff").value) return;
    try {
      const evidence = await api.filingForecasts(id, { signal });
      if (!signal.aborted && evidence.length) {
        $("report-evidence").hidden = false;
        $("report-evidence").innerHTML = `<div class="card-heading"><h2>Dự báo lưu theo bản báo cáo</h2></div>
          <div class="table-scroll"><table class="data-table"><thead><tr><th>Mô hình</th><th>Kỳ dự báo</th><th>Xác suất chỉ báo</th><th>Đầu vào</th></tr></thead>
          <tbody>${evidence.map((row) => `<tr><td>${esc(row.model_version)}</td>
          <td>${esc(row.outputs.target_fiscal_year)}</td>
          <td>${row.outputs.distress_probability == null ? "—" : format(row.outputs.distress_probability * 100) + "%"}</td>
          <td>${row.input_status === "verified_inputs" ? "Đã lưu tại lúc suy luận" : "Chưa xác nhận được đầu vào gốc"}</td></tr>`).join("")}</tbody></table></div>`;
      }
    } catch (error) {
      if (!signal.aborted) {
        $("report-evidence").hidden = false;
        $("report-evidence").textContent = error.message;
      }
    }
  }
  async function refresh(event) {
    event?.preventDefault();
    controller?.abort();
    evidenceRequest?.abort();
    controller = new AbortController();
    const signal = controller.signal;
    const issuer = $("report-issuer").value;
    const identifier = issuer === "sec" ? getCompany() : issuer;
    if (!identifier) {
      $("report-status").textContent = "Chọn một công ty ở thanh điều hướng trước.";
      return;
    }
    $("report-status").textContent = "Đang tải báo cáo…";
    current = [];
    $("report-version").replaceChildren();
    for (const id of ["report-detail", "report-quarters", "report-evidence", "report-quality"]) {
      $(id).replaceChildren();
      $(id).hidden = true;
    }
    $("report-alerts").replaceChildren();
    try {
      const data = await api.reports(identifier, $("report-cutoff").value, { signal });
      if (signal.aborted) return;
      current = data.versions;
      $("report-version").innerHTML = current.map((filing) =>
        `<option value="${filing.id}">${esc(filing.form_type)} · ${date(filing.period_end)}
          · nộp ${date(filing.published_on)} · ${esc(filing.accession)}</option>`).join("");
      $("report-status").textContent = current.length
        ? `${current.length} bản báo cáo có trong kho.` : "Chưa có báo cáo ở ngày được chọn.";
      void showVersion();
      $("report-quarters").hidden = false;
      if (data.quarterly_series.length) {
        $("report-quarters").innerHTML = `<div class="card-heading"><h2>Doanh thu và dòng tiền theo quý</h2></div>
          <div class="table-scroll"><table class="data-table">
          <thead><tr><th>Kỳ</th><th>Đơn vị</th><th>Doanh thu quý</th><th>So với cùng kỳ</th><th>So với quý trước</th>
          <th>Dòng tiền quý</th><th>Doanh thu 4 quý</th><th>Dòng tiền 4 quý</th></tr></thead>
          <tbody>${data.quarterly_series.toReversed().map((row) => `<tr>
            <td>${esc(row.fiscal_period)} ${row.fiscal_year}<br><small>${date(row.period_end)}</small></td>
            <td>${esc(row.flows.revenues.unit ?? row.flows.operating_cash_flow.unit ?? "—")}</td>
            <td>${format(row.flows.revenues.value)}</td>
            <td>${percent(row.flows.revenues.yoy_growth)}</td><td>${percent(row.flows.revenues.qoq_growth)}</td>
            <td>${format(row.flows.operating_cash_flow.value)}</td><td>${format(row.flows.revenues.ttm)}</td>
            <td>${format(row.flows.operating_cash_flow.ttm)}</td></tr>`).join("")}</tbody></table></div>
          <p class="card-footnote">Tổng 4 quý chỉ tính khi có đủ bốn quan sát liên tiếp và cùng cơ sở.</p>`;
      } else {
        $("report-quarters").innerHTML = `<div class="card-heading"><h2>Doanh thu và dòng tiền theo quý</h2></div>
          <p class="muted">Chưa có chuỗi báo cáo quý xác nhận cho tổ chức phát hành này (hệ thống chỉ ghi nhận các kỳ quý vượt qua kiểm định lịch tài chính và cùng cơ sở kế toán).</p>`;
      }
      const alerts = await api.reportAlerts(identifier, $("report-cutoff").value, { signal });
      if (!signal.aborted && alerts.length) {
        $("report-status").textContent += ` ${alerts.length} thay đổi số liệu giữa các bản công bố.`;
        $("report-alerts").innerHTML = `<ul class="card-footnote">
          ${alerts.map((alert) => `<li>${date(alert.published_on)} · Thay đổi
            ${alert.changed_fields.map((key) => esc(names[key] ?? label(key))).join(", ")}
            · Bản ${alert.previous_filing_id} → ${alert.filing_id}</li>`).join("")}</ul>`;
      }
      if (issuer === "sec" && !$("report-cutoff").value) {
        const quality = await api.dataQuality({ signal });
        if (!signal.aborted) {
          $("report-quality").hidden = false;
          $("report-quality").innerHTML = `<div class="card-heading">
            <h2>Độ phủ dữ liệu · Báo cáo năm mới nhất</h2></div><div class="credit-ratios">
            ${Object.entries(quality.observed).map(([metric, count]) =>
              `<div><span>${esc(label(metric))}</span><strong>${count} / ${quality.report_count}</strong></div>`).join("")}</div>`;
        }
      }
    } catch (error) {
      if (!signal.aborted) $("report-status").textContent = error.message;
    }
  }
  $("report-query").addEventListener("submit", refresh);
  $("report-issuer").addEventListener("change", refresh);
  $("report-version").addEventListener("change", showVersion);
  return { refresh };
}
