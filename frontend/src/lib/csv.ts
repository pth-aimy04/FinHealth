/** Serialize CSV with spreadsheet-formula protection and preserved signed numbers. */
export function serializeCsv(
  columns: string[],
  rows: Record<string, unknown>[],
  heading: (key: string) => string = (key) => key,
): string {
  const cell = (value: unknown, text = false): string => {
    if (value == null) return "";
    if (typeof value === "number")
      return Number.isFinite(value) ? String(value) : "";
    let result =
      typeof value === "object" ? JSON.stringify(value) : String(value);
    if (text || /^[\s\uFEFF]*[=+@-]|^[\t\r\n]/u.test(result))
      result = "'" + result;
    return /[",\r\n]/u.test(result)
      ? '"' + result.replaceAll('"', '""') + '"'
      : result;
  };
  return (
    [
      columns.map((key) => cell(heading(key))).join(","),
      ...rows.map((row) =>
        columns.map((key) => cell(row[key], key === "cik")).join(","),
      ),
    ].join("\r\n") + "\r\n"
  );
}
/** Download a user-requested table. */
export function downloadCsv(
  filename: string,
  columns: string[],
  rows: Record<string, unknown>[],
  heading?: (key: string) => string,
): void {
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", serializeCsv(columns, rows, heading)], {
      type: "text/csv;charset=utf-8",
    }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Read quoted CSV, including embedded newlines, without silently coercing financial values. */
export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  const input = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < input.length; i++) {
    const char = input[i];
    if (char === '"') {
      if (quoted && input[i + 1] === '"') {
        cell += '"';
        i++;
      } else quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell.trim());
      cell = "";
    } else if ((char === "\r" || char === "\n") && !quoted) {
      if (char === "\r" && input[i + 1] === "\n") i++;
      row.push(cell.trim());
      if (row.some(Boolean)) rows.push(row);
      row = [];
      cell = "";
    } else cell += char;
  }
  if (quoted) throw new Error("CSV có dấu nháy chưa đóng.");
  row.push(cell.trim());
  if (row.some(Boolean)) rows.push(row);
  const headers = rows.shift() ?? [];
  if (new Set(headers).size !== headers.length)
    throw new Error("CSV có tên cột trùng nhau.");
  return rows.map((values, index) => {
    if (values.length !== headers.length)
      throw new Error(`Số cột không khớp ở dòng ${index + 2}.`);
    return Object.fromEntries(headers.map((key, i) => [key, values[i]]));
  });
}
