/** RFC 4180 export with distinct numeric and spreadsheet-safe text fields. */
function cell(value, forceText = false) {
  if (value == null) return "";
  if (typeof value === "number" && !forceText) return Number.isFinite(value) ? String(value) : "";
  let text = String(value);
  if (text && (forceText || /^[\s\uFEFF]*[=+@-]|^[\t\r\n]/u.test(text))) text = "'" + text;
  return /[",\r\n]/u.test(text) ? '"' + text.replaceAll('"', '""') + '"' : text;
}

export function serializeCsv(columns, rows, heading = (name) => name) {
  const header = columns.map((name) => cell(heading(name))).join(",");
  const records = rows.map((row) => columns.map((name) => cell(row[name], name === "cik")).join(","));
  return [header, ...records].join("\r\n") + "\r\n";
}

export function downloadCsv(filename, columns, rows, heading) {
  const url = URL.createObjectURL(new Blob(["\uFEFF", serializeCsv(columns, rows, heading)], {
    type: "text/csv;charset=utf-8",
  }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function parseCsv(text) {
  const clean = String(text ?? "").replace(/^\uFEFF/, "").trim();
  if (!clean) return [];
  const rows = [];
  let row = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < clean.length; i += 1) {
    const ch = clean[i];
    if (inQuotes) {
      if (ch === '"' && clean[i + 1] === '"') {
        current += '"';
        i += 1;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        current += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(current.trim());
      current = "";
    } else if (ch === "\r" || ch === "\n") {
      if (ch === "\r" && clean[i + 1] === "\n") i += 1;
      row.push(current.trim());
      if (row.some((v) => v !== "")) rows.push(row);
      row = [];
      current = "";
    } else {
      current += ch;
    }
  }
  row.push(current.trim());
  if (row.some((v) => v !== "")) rows.push(row);
  if (rows.length < 2) return [];
  const headers = rows[0].map((h) => h.replace(/^'/, "").trim());
  return rows.slice(1).map((values) => {
    const obj = {};
    headers.forEach((h, idx) => {
      if (h) obj[h] = (values[idx] ?? "").replace(/^'/, "").trim();
    });
    return obj;
  });
}
