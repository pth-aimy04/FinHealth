/** Responsive SVG charts with keyboard access, pointer tooltips and explicit missing values. */
import { date, label as vietnamese } from "./vi.js";

export const COLORS = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444"];
export const finite = (value) => typeof value === "number" && Number.isFinite(value);
export const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#39;");

export function number(value, digits = 2) {
  return finite(value) ? value.toLocaleString("vi-VN", {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  }) : "—";
}

export function percent(value, digits = 1) {
  return finite(value) ? `${number(value * 100, digits)}%` : "—";
}

export function metricValue(key, value) {
  if (!finite(value)) return "—";
  if (key === "eps") return `$${number(value)}`;
  if (key === "negative_ocf_streak") return number(value, 0);
  if (["current_ratio", "debt_to_equity", "asset_turnover"].includes(key)) {
    return `${number(value)}×`;
  }
  return percent(value);
}

function empty(container, message) {
  container.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
}

function setup(container, width, height, label) {
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img"
    aria-label="${escapeHtml(label)}"></svg><div class="tooltip" hidden></div>`;
  return [container.querySelector("svg"), container.querySelector(".tooltip")];
}

function showTooltip(container, tooltip, content, event, target) {
  tooltip.innerHTML = content;
  tooltip.hidden = false;
  const bounds = container.getBoundingClientRect();
  const point = target?.getBoundingClientRect();
  const x = event?.clientX ?? point?.x ?? bounds.x;
  const y = event?.clientY ?? point?.y ?? bounds.y;
  tooltip.style.left = `${Math.max(4, Math.min(x - bounds.x + 12,
    bounds.width - tooltip.offsetWidth - 6))}px`;
  tooltip.style.top = `${Math.max(4, Math.min(y - bounds.y - 15,
    bounds.height - tooltip.offsetHeight - 4))}px`;
}

function hoverTargets(container, svg, tooltip, describe, select) {
  for (const target of svg.querySelectorAll("[data-point]")) {
    const index = Number(target.dataset.point);
    const reveal = (event) => showTooltip(container, tooltip, describe(index), event, target);
    target.addEventListener("pointermove", reveal);
    target.addEventListener("focus", () => reveal());
    target.addEventListener("pointerleave", () => { tooltip.hidden = true; });
    target.addEventListener("blur", () => { tooltip.hidden = true; });
    if (select) {
      target.addEventListener("click", () => select(index));
      target.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select(index);
        }
      });
    }
  }
}

function extent(values, includeZero = false) {
  const data = values.filter(finite);
  if (includeZero) data.push(0);
  let low = Math.min(...data), high = Math.max(...data);
  const pad = Math.max((high - low) * 0.14, Math.abs(high) * 0.04, 0.01);
  low -= pad;
  high += pad;
  return [low, high];
}

function ticks(low, high, count = 4) {
  return Array.from({ length: count + 1 }, (_, index) => low + (high - low) * index / count);
}

export function renderMultiCompanyComparisonChart(container, comparison, metric) {
  const { companies, historical_series: history } = comparison;
  const palette = ["#087a66", "#3056b3", "#9b5213", "#9b3676"];
  const series = companies.map((company, index) => {
    const points = (history[company.cik] ?? []).map((row) => ({
      year: row.fiscal_year, value: row[metric], filed: row.filed_date,
    }));
    const value = company[`pred_${metric}`];
    const forecast = finite(value) && finite(company.target_fiscal_year)
      ? { year: company.target_fiscal_year, value, forecast: true } : null;
    return { label: company.ticker ?? company.cik, color: palette[index], points, forecast };
  });
  const all = series.flatMap(({ points, forecast }) => forecast ? [...points, forecast] : points);
  const usable = all.filter((point) => finite(point.value));
  if (!usable.length) return empty(container, "Chỉ tiêu đã chọn chưa có số liệu báo cáo.");
  const width = 900, height = 320, left = 60, right = 55, top = 30, bottom = 65;
  const lowYear = Math.min(...all.map((point) => point.year));
  const highYear = Math.max(...all.map((point) => point.year));
  const [low, high] = extent(usable.map((point) => point.value));
  const x = (year) => left + (year - lowYear) / Math.max(1, highYear - lowYear) * (width - left - right);
  const y = (value) => top + (high - value) / (high - low) * (height - top - bottom);
  const [svg, tooltip] = setup(container, width, height, `${vietnamese(metric)} của các công ty đã chọn`);
  const pointLabels = [];
  let markup = ticks(low, high).map((value) =>
    `<line class="gridline" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/>
    <text x="${left - 8}" y="${y(value) + 3}" text-anchor="end">${escapeHtml(percent(value))}</text>`).join("");
  const yearTicks = new Set([lowYear, highYear]);
  for (let year = lowYear; year < highYear; year += Math.max(1, Math.ceil((highYear - lowYear) / 8))) {
    yearTicks.add(year);
  }
  for (const year of yearTicks) {
    markup += `<text x="${x(year)}" y="${height - bottom + 20}" text-anchor="middle">${year}</text>`;
  }
  series.forEach(({ label, color, points, forecast }, index) => {
    let trajectory = "", previous = null;
    for (const point of points) {
      if (!finite(point.value)) { previous = null; continue; }
      trajectory += `${previous === point.year - 1 ? "L" : "M"}${x(point.year)},${y(point.value)} `;
      previous = point.year;
    }
    markup += `<path d="${trajectory}" stroke="${color}" stroke-width="2.1" fill="none"/>`;
    const latest = points.at(-1);
    if (forecast && finite(latest?.value)) {
      markup += `<path d="M${x(latest.year)},${y(latest.value)} L${x(forecast.year)},${y(forecast.value)}"
        stroke="${color}" stroke-width="2.1" stroke-dasharray="5 4" fill="none"/>`;
    }
    for (const point of forecast ? [...points, forecast] : points) {
      if (!finite(point.value)) continue;
      const idx = pointLabels.length;
      const title = `${label} · Năm ${point.year} · ${percent(point.value)} · ${point.forecast ? "Dự báo kỳ tới" : "Theo báo cáo"}`;
      pointLabels.push(`<strong>${escapeHtml(title)}</strong>${point.filed ? `<span>Nộp ngày ${escapeHtml(date(point.filed))}</span>` : ""}`);
      markup += `<circle cx="${x(point.year)}" cy="${y(point.value)}" r="${point.forecast ? 5 : 3}" fill="${color}"/>
        <circle data-point="${idx}" tabindex="0" role="img" aria-label="${escapeHtml(title)}"
          cx="${x(point.year)}" cy="${y(point.value)}" r="9" fill="transparent"/>`;
    }
    markup += `<text x="${left + index * 175}" y="${height - 13}" style="fill:${color};font-weight:700">
      ${escapeHtml(label)}</text>`;
  });
  svg.innerHTML = markup;
  hoverTargets(container, svg, tooltip, (index) => pointLabels[index]);
}

export function renderTrajectoryForecastChart(container, history, prediction, metricKey, options = {}) {
  const points = history.filter((row) => row.form_type === "10-K")
    .toSorted((a, b) => a.fiscal_year - b.fiscal_year);
  const forecast = prediction?.[`pred_${metricKey}`];
  const years = points.map((point) => point.fiscal_year);
  const forecastYear = prediction?.target_fiscal_year;
  if (finite(forecast) && finite(forecastYear)) years.push(forecastYear);
  const values = points.map((point) => point[metricKey]);
  if (finite(forecast)) values.push(forecast);
  if (!values.some(finite) || !years.length) return empty(container, "Chưa có số liệu để vẽ biểu đồ.");
  const width = 440, height = 205;
  const left = 53, right = 23, top = 27, bottom = 35;
  const [low, high] = extent(values, true);
  const first = Math.min(...years), last = Math.max(...years);
  const x = (year) => left + (year - first) / Math.max(last - first, 1) * (width - left - right);
  const y = (value) => top + (high - value) / (high - low) * (height - top - bottom);
  const [svg, tooltip] = setup(container, width, height, `${vietnamese(metricKey)}, số liệu báo cáo và dự báo`);
  const format = (value) => options.format?.(value) ?? metricValue(metricKey, value);
  const actual = points.at(-1);
  let markup = "";
  if (finite(forecast) && actual && forecastYear > actual.fiscal_year) {
    markup += `<rect x="${x(actual.fiscal_year)}" y="${top - 12}" width="${x(forecastYear) - x(actual.fiscal_year)}"
      height="${height - bottom - top + 12}" fill="#3b82f60a"/>
      <text x="${x(forecastYear)}" y="12" text-anchor="end" style="fill:#6b98cd;font-size:9px">DỰ BÁO</text>`;
  }
  for (const value of ticks(low, high, 3)) {
    markup += `<line class="gridline" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/>
      <text x="${left - 9}" y="${y(value) + 3}" text-anchor="end">${escapeHtml(format(value))}</text>`;
  }
  const references = options.referenceLines ?? [0];
  for (const value of references.filter((value) => value >= low && value <= high)) {
    markup += `<line class="reference" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/>`;
  }
  let path = "", connected = false;
  for (const row of points) {
    if (!finite(row[metricKey])) { connected = false; continue; }
    path += `${connected ? "L" : "M"}${x(row.fiscal_year)},${y(row[metricKey])} `;
    connected = true;
  }
  markup += `<path d="${path}" fill="none" stroke="#168f79" stroke-width="2.3" stroke-linejoin="round"/>`;
  const plotted = points.map((point) => ({
    year: point.fiscal_year, value: point[metricKey], kind: "Theo hồ sơ 10-K",
  }));
  if (finite(forecast) && finite(forecastYear)) {
    if (finite(actual?.[metricKey])) markup += `<path d="M${x(actual.fiscal_year)},${y(actual[metricKey])}
      L${x(forecastYear)},${y(forecast)}" fill="none" stroke="#3b82f6" stroke-width="2.2" stroke-dasharray="5 4"/>`;
    plotted.push({ year: forecastYear, value: forecast, kind: "Dự báo kỳ tới của XGBoost", forecast: true });
  }
  for (const [index, row] of plotted.entries()) {
    if (!finite(row.value)) continue;
    const isForecast = row.forecast;
    markup += `<circle cx="${x(row.year)}" cy="${y(row.value)}" r="${isForecast ? 6 : 3}"
      fill="${isForecast ? "#3b82f6" : "#fff"}" stroke="${isForecast ? "#d2e3fe" : "#168f79"}"
      stroke-width="${isForecast ? 3 : 1.8}"/>
      <circle data-point="${index}" tabindex="0" role="img" aria-label="Năm ${row.year} ${escapeHtml(format(row.value))}"
      cx="${x(row.year)}" cy="${y(row.value)}" r="10" fill="transparent"/>`;
  }
  const displayedYears = [...new Set([first, ...years.filter((_, index) => index % 4 === 0), last])];
  for (const year of displayedYears) markup += `<text x="${x(year)}" y="${height - 10}" text-anchor="middle">${year}</text>`;
  markup += `<line class="crosshair" y1="${top}" y2="${height - bottom}" visibility="hidden"/>`;
  svg.innerHTML = markup;
  hoverTargets(container, svg, tooltip, (index) => {
    const row = plotted[index];
    return `<strong>Năm ${row.year} · ${escapeHtml(format(row.value))}</strong><span>${row.kind}</span>`;
  });
  svg.addEventListener("pointermove", (event) => {
    const rect = svg.getBoundingClientRect();
    const px = (event.clientX - rect.x) / rect.width * width;
    const valid = plotted.filter((row) => finite(row.value));
    const nearest = valid.reduce((a, b) => Math.abs(x(a.year) - px) < Math.abs(x(b.year) - px) ? a : b);
    const line = svg.querySelector(".crosshair");
    line.setAttribute("x1", x(nearest.year));
    line.setAttribute("x2", x(nearest.year));
    line.setAttribute("visibility", "visible");
    showTooltip(container, tooltip, `<strong>Năm ${nearest.year} · ${escapeHtml(format(nearest.value))}</strong>
      <span>${nearest.kind}</span>`, event);
  });
  svg.addEventListener("pointerleave", () => {
    tooltip.hidden = true;
    svg.querySelector(".crosshair").setAttribute("visibility", "hidden");
  });
}

export function renderRiskGauge(container, probability, riskLevel, threshold) {
  if (!finite(probability)) return empty(container, "Chưa có dự báo hiện hành.");
  const color = ({ LOW: COLORS[0], MEDIUM: COLORS[1], HIGH: COLORS[2], CRITICAL: COLORS[3] })[riskLevel] ?? "#8495a0";
  const p = Math.max(0, Math.min(1, probability));
  const arc = "M 30 140 A 100 100 0 0 1 230 140";
  const angle = Math.PI * (1 - threshold);
  const marker = finite(threshold) && threshold >= 0 && threshold <= 1
    ? `<line x1="${130 + 89 * Math.cos(angle)}" y1="${140 - 89 * Math.sin(angle)}"
      x2="${130 + 113 * Math.cos(angle)}" y2="${140 - 113 * Math.sin(angle)}" stroke="#253e50" stroke-width="2"/>
      <text x="130" y="191" text-anchor="middle" class="gauge-label">Ngưỡng phân loại ${percent(threshold)}</text>`
    : "";
  container.innerHTML = `<svg viewBox="0 0 260 210" role="img"
    aria-label="Xác suất khó khăn tài chính ${percent(probability)}, mức rủi ro ${escapeHtml(vietnamese(riskLevel))}, ngưỡng ${percent(threshold)}">
    <path d="${arc}" fill="none" stroke="#edf1f4" stroke-width="13" stroke-linecap="round"/>
    <path d="${arc}" fill="none" stroke="${color}" stroke-width="13" stroke-linecap="round"
      pathLength="100" stroke-dasharray="${p * 100} 100"/>
    ${marker}<text x="130" y="125" text-anchor="middle" class="gauge-value">${percent(probability)}</text>
    <text x="130" y="147" text-anchor="middle" class="gauge-label">${riskLevel ? `Rủi ro ${escapeHtml(vietnamese(riskLevel).toLowerCase())}` : "Chưa phân loại"}</text>
    <text x="24" y="164" class="gauge-label">0%</text><text x="236" y="164" text-anchor="end" class="gauge-label">100%</text>
    </svg>`;
}

export function renderShapWaterfallChart(container, prediction) {
  const drivers = prediction?.top_drivers?.filter((row) => finite(row.shap_value)) ?? [];
  if (!drivers.length) return empty(container, "Chưa có thông tin giải thích kết quả.");
  const isProb = prediction?.output_space === "probability";
  const unit = isProb ? "đóng góp xác suất" : "log-odds";
  const scaleName = isProb ? "thang xác suất" : "thang log-odds";
  const width = 800, left = 245, right = 75, top = 26, rowHeight = 36;
  const height = top + drivers.length * rowHeight + 37;
  const max = Math.max(...drivers.map((row) => Math.abs(row.shap_value)), 0.001) * 1.15;
  const zero = left + (width - left - right) / 2;
  const scale = (width - left - right) / (2 * max);
  const [svg, tooltip] = setup(container, width, height, `Ảnh hưởng của các yếu tố đến dự báo trên ${scaleName}`);
  let markup = "";
  for (const value of [-max, -max / 2, 0, max / 2, max]) {
    const x = zero + value * scale;
    markup += `<line class="${value === 0 ? "reference" : "gridline"}" x1="${x}" x2="${x}"
      y1="17" y2="${height - 27}"/><text x="${x}" y="${height - 9}" text-anchor="middle">${number(value)}</text>`;
  }
  for (const [index, row] of drivers.entries()) {
    const y = top + index * rowHeight;
    const x = zero + Math.min(0, row.shap_value) * scale;
    const color = row.shap_value >= 0 ? COLORS[3] : COLORS[0];
    markup += `<text class="feature-label" x="${left - 15}" y="${y + 7}" text-anchor="end">${escapeHtml(vietnamese(row.feature))}</text>
      <text x="${left - 15}" y="${y + 21}" text-anchor="end" style="font-size:9px">Đầu vào ${escapeHtml(metricValue(row.feature, row.feature_value))}</text>
      <rect x="${x}" y="${y}" width="${Math.max(1, Math.abs(row.shap_value) * scale)}" height="19" rx="3" fill="${color}"/>
      <text x="${width - 7}" y="${y + 13}" text-anchor="end" style="fill:${color}">${row.shap_value >= 0 ? "+" : ""}${number(row.shap_value, 3)}</text>
      <rect data-point="${index}" x="0" y="${y - 3}" width="${width}" height="32" fill="transparent"
        tabindex="0" role="img" aria-label="${escapeHtml(vietnamese(row.feature))}, ${number(row.shap_value, 3)} ${unit}"/>`;
  }
  svg.innerHTML = markup;
  hoverTargets(container, svg, tooltip, (index) => {
    const row = drivers[index];
    return `<strong>${escapeHtml(vietnamese(row.feature))}</strong>
      <span>Đầu vào mô hình ${escapeHtml(metricValue(row.feature, row.feature_value))}</span>
      <span>Đóng góp ${row.shap_value >= 0 ? "+" : ""}${number(row.shap_value, 5)} ${unit}</span>
      <span>${row.shap_value >= 0 ? "Tăng" : "Giảm"} rủi ro dự báo</span>`;
  });
}

export function renderPcaClusterScatterPlot(container, clusterPoints, selectedCik, onSelectCompany, options = {}) {
  const axis = options.axis ?? "pca_comp_2";
  const points = clusterPoints.filter((row) => finite(row.pca_comp_1) && finite(row[axis]));
  if (!points.length) return empty(container, "Chưa có tọa độ PCA.");
  const compact = options.compact ?? false;
  const width = compact ? 360 : 1100, height = compact ? 260 : 410;
  const left = compact ? 40 : 62, right = 25, top = 27, bottom = 43;
  const [xmin, xmax] = extent(points.map((row) => row.pca_comp_1), true);
  const [ymin, ymax] = extent(points.map((row) => row[axis]), true);
  const x = (value) => left + (value - xmin) / (xmax - xmin) * (width - left - right);
  const y = (value) => top + (ymax - value) / (ymax - ymin) * (height - top - bottom);
  const [svg, tooltip] = setup(container, width, height, `Nhóm sức khỏe tài chính theo PC1 và ${axis.endsWith("3") ? "PC3" : "PC2"}`);
  let markup = `<rect x="${left}" y="${top}" width="${width - left - right}" height="${height - top - bottom}"
    fill="#fbfcfd" rx="4"/>`;
  const quadrantWidth = x(0) - left;
  const quadrantHeight = y(0) - top;
  markup += `<rect x="${left}" y="${top}" width="${quadrantWidth}" height="${quadrantHeight}" fill="#10b98104"/>
    <rect x="${x(0)}" y="${y(0)}" width="${width - right - x(0)}" height="${height - bottom - y(0)}" fill="#ef444403"/>`;
  for (const value of ticks(xmin, xmax)) markup += `<line class="gridline" x1="${x(value)}" x2="${x(value)}"
    y1="${top}" y2="${height - bottom}"/><text x="${x(value)}" y="${height - bottom + 17}" text-anchor="middle">${number(value, 1)}</text>`;
  for (const value of ticks(ymin, ymax)) markup += `<line class="gridline" x1="${left}" x2="${width - right}"
    y1="${y(value)}" y2="${y(value)}"/><text x="${left - 10}" y="${y(value) + 3}" text-anchor="end">${number(value, 1)}</text>`;
  markup += `<line class="reference" x1="${x(0)}" x2="${x(0)}" y1="${top}" y2="${height - bottom}"/>
    <line class="reference" x1="${left}" x2="${width - right}" y1="${y(0)}" y2="${y(0)}"/>
    <text class="axis-label" x="${(left + width - right) / 2}" y="${height - 3}" text-anchor="middle">PC1</text>
    <text class="axis-label" x="12" y="17">${axis.endsWith("3") ? "PC3" : "PC2"}</text>`;
  for (const [index, row] of points.entries()) {
    const color = COLORS[row.cluster_id] ?? "#8295a4";
    const radius = (compact ? 3 : 4) + (finite(row.distress_probability) ? row.distress_probability * 4 : 0);
    if (row.cik === selectedCik) {
      markup += `<circle cx="${x(row.pca_comp_1)}" cy="${y(row[axis])}" r="${radius + 5}"
        fill="none" stroke="#243e51" stroke-width="1.5"/>
        <text x="${x(row.pca_comp_1) + 12}" y="${y(row[axis]) - 9}" style="fill:#253e51;font-weight:600">${escapeHtml(row.ticker ?? row.cik)}</text>`;
    }
    markup += `<circle data-point="${index}" tabindex="0" role="button"
      aria-label="Mở phân tích ${escapeHtml(row.ticker ?? row.name)}, ${escapeHtml(vietnamese(row.cluster_label))}"
      cx="${x(row.pca_comp_1)}" cy="${y(row[axis])}" r="${radius}" fill="${color}" fill-opacity=".82"
      stroke="#fff" stroke-width="1.2"/>`;
  }
  svg.innerHTML = markup;
  hoverTargets(container, svg, tooltip, (index) => {
    const row = points[index];
    return `<strong>${escapeHtml(row.ticker ?? row.cik)} · ${escapeHtml(row.name)}</strong>
      <span>${escapeHtml(vietnamese(row.cluster_label))}</span><span>Xác suất khó khăn tài chính ${percent(row.distress_probability)}</span>
      <span>Altman Z ${number(row.altman_z_score, 3)}</span>
      <span>PC1 ${number(row.pca_comp_1, 3)} · ${axis.endsWith("3") ? "PC3" : "PC2"} ${number(row[axis], 3)}</span>`;
  }, (index) => onSelectCompany(points[index].cik));
}
