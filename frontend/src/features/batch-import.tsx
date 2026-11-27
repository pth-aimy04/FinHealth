import { useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { mutate, request, type Schema } from "../lib/api/client";
import { parseCsv, downloadCsv } from "../lib/csv";
import { label } from "../lib/formatters";
import { Button } from "../components/ui/button";
import { QueryState } from "../components/shared";
/** Import explicit statement CSV without manufacturing absent financial observations. */
export function BatchImport({
  onResult,
}: {
  onResult: (result: Schema["BatchPredictionResponseSchema"]) => void;
}): ReactElement {
  const [version, setVersion] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const versions = useQuery({
    queryKey: ["versions"],
    queryFn: () =>
      request<Schema["ModelVersionSummarySchema"][]>("/models/versions"),
  });
  const columns = [
    "company_name",
    "fiscal_year",
    "is_manufacturing",
    "total_assets",
    "total_liabilities",
    "current_assets",
    "current_liabilities",
    "stockholders_equity",
    "retained_earnings",
    "revenues",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "cash_and_equivalents",
    "interest_expense",
    "capex",
    "eps_diluted",
    "prior_total_assets",
    "prior_current_assets",
    "prior_total_liabilities",
    "prior_current_liabilities",
    "prior_stockholders_equity",
    "prior_revenues",
    "prior_operating_income",
    "prior_net_income",
    "prior_operating_cash_flow",
  ];
  const run = async (): Promise<void> => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      if (file.size > 1_900_000)
        throw new Error("File quá lớn. Giới hạn dưới 1,9 MB và 200 báo cáo.");
      const records = parseCsv(await file.text());
      if (!records.length || records.length > 200)
        throw new Error("Cần từ 1 đến 200 báo cáo.");
      const items = records.map((record, index) => {
        const output: Record<string, unknown> = {};
        Object.entries(record).forEach(([key, value]) => {
          if (!columns.includes(key))
            throw new Error(`Cột không được hỗ trợ: ${key}`);
          if (["company_name"].includes(key)) output[key] = value;
          else if (key === "is_manufacturing") {
            if (!["true", "false", "1", "0"].includes(value))
              throw new Error(
                `Dòng ${index + 2}: is_manufacturing phải là true/false.`,
              );
            output[key] = ["true", "1"].includes(value);
          } else {
            if (value && !Number.isFinite(Number(value)))
              throw new Error(
                `Dòng ${index + 2}: ${label(key)} phải là số, dùng dấu chấm thập phân.`,
              );
            output[key] = value === "" ? null : Number(value);
          }
        });
        if (
          typeof output.total_assets !== "number" ||
          output.total_assets <= 0 ||
          typeof output.total_liabilities !== "number" ||
          output.total_liabilities < 0
        )
          throw new Error(
            `Dòng ${index + 2}: tổng tài sản phải dương, tổng nợ phải trả không âm.`,
          );
        return output;
      });
      onResult(
        await mutate<Schema["BatchPredictionResponseSchema"]>(
          "/models/predict-batch",
          { items, ...(version ? { model_version: version } : {}) },
        ),
      );
    } catch (cause) {
      setError(
        cause instanceof Error ? cause : new Error("Không đọc được CSV."),
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="form-stack mb-8">
      <div className="notice">
        Nhập CSV theo mẫu. Số liệu cùng đơn vị trong mỗi dòng; dấu chấm thập
        phân, không dùng dấu phân nhóm. Ô trống được giữ là thiếu dữ liệu.
      </div>
      <Button
        variant="outline"
        onClick={() =>
          downloadCsv("finhealth-statement-template.csv", columns, [])
        }
      >
        Tải mẫu CSV
      </Button>
      <label>
        Mô hình áp dụng cho CSV
        <select
          value={version}
          onChange={(event) => setVersion(event.target.value)}
        >
          <option value="">Mô hình đang hoạt động</option>
          {versions.data?.map((row) => (
            <option key={row.model_version}>{row.model_version}</option>
          ))}
        </select>
      </label>
      <label>
        Chọn file báo cáo CSV
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </label>
      <Button disabled={!file || busy} onClick={() => void run()}>
        {busy ? "Đang đánh giá…" : "Đánh giá file CSV"}
      </Button>
      <QueryState error={error} />
    </div>
  );
}
