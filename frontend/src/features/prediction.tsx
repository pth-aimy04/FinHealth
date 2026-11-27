import { useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import {
  mutate,
  request,
  type ManualInput,
  type Schema,
} from "../lib/api/client";
import { label } from "../lib/formatters";
import { Evidence, PageTitle, Panel, QueryState } from "../components/shared";
import { DataForm, type Field } from "../components/data-form";
import { Button } from "../components/ui/button";
import { PredictionView } from "./company";
import { BatchImport } from "./batch-import";
import { downloadCsv } from "../lib/csv";
const numericKeys = [
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
] as const satisfies readonly (keyof ManualInput)[];
const nonnegative = new Set([
  "total_liabilities",
  "current_assets",
  "current_liabilities",
  "revenues",
  "cash_and_equivalents",
  "interest_expense",
  "capex",
  "prior_current_assets",
  "prior_total_liabilities",
  "prior_current_liabilities",
  "prior_revenues",
]);
/** Convert explicit statement entries to the exact API request; empty optional facts stay null. */
export function manualPayload(values: Record<string, string>): ManualInput {
  return {
    company_name: values.company_name,
    fiscal_year: Number(values.fiscal_year),
    is_manufacturing: values.is_manufacturing === "true",
    ...(values.model_version ? { model_version: values.model_version } : {}),
    ...Object.fromEntries(
      numericKeys.map((key) => [
        key,
        values[key]?.trim() ? Number(values[key]) : null,
      ]),
    ),
    total_assets: Number(values.total_assets),
    total_liabilities: Number(values.total_liabilities),
  };
}
/** Authenticated statement scoring, portfolio JSON scoring and explicit owner-side saving. */
export default function PredictionPage(): ReactElement {
  const { user, pending } = useSession();
  const client = useQueryClient();
  const [mode, setMode] = useState("manual");
  const [result, setResult] = useState<
    Schema["ManualPredictionResponseSchema"] | null
  >(null);
  const [input, setInput] = useState<ManualInput | null>(null);
  const [batch, setBatch] = useState<
    Schema["BatchPredictionResponseSchema"] | null
  >(null);
  const [saveStatus, setSaveStatus] = useState("");
  const versions = useQuery({
    queryKey: ["versions"],
    queryFn: () =>
      request<Schema["ModelVersionSummarySchema"][]>("/models/versions"),
  });
  const versionField: Field = {
    name: "model_version",
    label: "Phiên bản mô hình",
    type: "select",
    options: [
      { value: "", label: "Mô hình đang hoạt động" },
      ...(versions.data ?? []).map((row) => ({
        value: row.model_version,
        label: `${row.model_version} · ${row.dataset}`,
      })),
    ],
  };
  const fields: Field[] = [
    {
      name: "company_name",
      label: "Tên doanh nghiệp",
      required: true,
      max: 120,
    },
    {
      name: "fiscal_year",
      label: "Năm tài chính",
      type: "number",
      required: true,
      min: 1990,
      max: 2100,
      integer: true,
      defaultValue: String(new Date().getFullYear() - 1),
    },
    {
      name: "is_manufacturing",
      label: "Phân loại doanh nghiệp",
      type: "select",
      defaultValue: "true",
      options: [
        { value: "true", label: "Sản xuất" },
        { value: "false", label: "Phi sản xuất" },
      ],
    },
    versionField,
    ...numericKeys.map((key) => ({
      name: key,
      label: label(key),
      type: "number" as const,
      required: key === "total_assets" || key === "total_liabilities",
      min:
        key === "total_assets" || key === "prior_total_assets"
          ? Number.MIN_VALUE
          : nonnegative.has(key)
            ? 0
            : undefined,
    })),
  ];
  return (
    <>
      <PageTitle
        title="Dự báo từ báo cáo tự nhập"
        description="Đánh giá một doanh nghiệp hoặc danh mục qua mô hình đã công bố. Số liệu được xử lý trên máy chủ; không huấn luyện lại."
      />
      <QueryState
        pending={pending}
        error={versions.error}
        retry={versions.refetch}
      />
      {!user ? (
        <div className="notice">
          Cần đăng nhập để chạy dự báo thủ công và hàng loạt.{" "}
          <Link to="/account">Đăng nhập</Link>
        </div>
      ) : (
        <>
          <div className="account-tabs">
            <Button
              variant={mode === "manual" ? "default" : "outline"}
              onClick={() => setMode("manual")}
            >
              Một doanh nghiệp
            </Button>
            <Button
              variant={mode === "batch" ? "default" : "outline"}
              onClick={() => setMode("batch")}
            >
              Danh mục hàng loạt
            </Button>
          </div>
          <div className="notice">
            Các số tiền phải cùng đơn vị và tiền tệ cho toàn bộ một báo cáo; EPS
            phải cùng đơn vị tiền tệ/cổ phiếu. Mô hình học từ SEC và các bundle
            được chỉ rõ; nhập số liệu ngoài phạm vi có thể tạo kết quả ngoài
            miền huấn luyện. Để trống chỉ tiêu chưa quan sát, không nhập 0 thay
            thế.
          </div>
          {mode === "manual" ? (
            <Panel
              title="Số liệu tài chính"
              note="Các trường có * là bắt buộc · kỳ trước dùng cho đặc trưng biến động"
            >
              <div className="panel-body">
                <DataForm
                  fields={fields}
                  submit="Chạy dự báo"
                  onSubmit={async (values) => {
                    const payload = manualPayload(values);
                    const output = await mutate<
                      Schema["ManualPredictionResponseSchema"]
                    >("/models/predict-manual", payload);
                    setInput(payload);
                    setResult(output);
                    setSaveStatus("");
                    return "Đã nhận kết quả dự báo.";
                  }}
                />
              </div>
            </Panel>
          ) : (
            <Panel
              title="Dự báo danh mục"
              note="JSON theo ManualStatementInputSchema · tối đa 200 doanh nghiệp"
            >
              <div className="panel-body">
                <BatchImport onResult={setBatch} />
                <details className="mb-6">
                  <summary>Nhập JSON nâng cao · contract đầu vào</summary>
                  <p className="muted small">
                    Nhập mảng JSON các báo cáo. Mỗi mục cần total_assets &gt; 0
                    và total_liabilities ≥ 0; dùng đúng tên trường bên dưới. Dữ
                    liệu nhập phải cùng đơn vị trong từng báo cáo.
                  </p>
                  <p className="small">{numericKeys.join(", ")}</p>
                </details>
                <DataForm
                  fields={[
                    versionField,
                    {
                      name: "items",
                      label: "Mảng báo cáo JSON",
                      type: "textarea",
                      required: true,
                      hint: "Tên trường theo contract ở trên. Các chỉ tiêu chưa có: null hoặc bỏ trường.",
                    },
                  ]}
                  submit="Đánh giá danh mục"
                  onSubmit={async (values) => {
                    let items: unknown;
                    try {
                      items = JSON.parse(values.items);
                    } catch {
                      throw new Error(
                        "JSON chưa hợp lệ. Kiểm tra dấu ngoặc và dấu phẩy.",
                      );
                    }
                    if (
                      !Array.isArray(items) ||
                      items.length < 1 ||
                      items.length > 200
                    )
                      throw new Error("Cần mảng từ 1 đến 200 báo cáo.");
                    const output = await mutate<
                      Schema["BatchPredictionResponseSchema"]
                    >("/models/predict-batch", {
                      items,
                      ...(values.model_version
                        ? { model_version: values.model_version }
                        : {}),
                    });
                    setBatch(output);
                    return "Đã đánh giá danh mục.";
                  }}
                />
              </div>
            </Panel>
          )}
          {mode === "manual" && result && (
            <>
              <div className="notice">
                {result.is_ood_scenario
                  ? "Cảnh báo ngoài miền huấn luyện: " +
                    (result.ood_features ?? []).join(", ")
                  : "Kết quả suy luận từ dữ liệu tự nhập."}{" "}
                Ngưỡng phân loại: {result.classification_threshold ?? "—"}.
              </div>
              <PredictionView prediction={result.prediction} />
              <Panel title="Chẩn đoán tài chính">
                <div className="panel-body">
                  <Evidence
                    data={{
                      ratios: result.ratios,
                      health_pillars: result.health_pillars,
                      dupont: result.dupont,
                      quality_of_earnings: result.quality_of_earnings,
                      accounting_checklist: result.accounting_checklist,
                      recommendations: result.recommendations,
                    }}
                  />
                </div>
              </Panel>
              <Panel
                title="Lưu phân tích riêng tư"
                note="Lưu kết quả cùng dữ liệu đầu vào và phiên bản mô hình"
              >
                <div className="panel-body">
                  <DataForm
                    fields={[
                      {
                        name: "name",
                        label: "Tên phân tích",
                        required: true,
                        max: 120,
                      },
                    ]}
                    submit="Lưu vào workspace"
                    onSubmit={async (values) => {
                      await mutate("/me/analyses", {
                        name: values.name,
                        inputs: input,
                      });
                      await client.invalidateQueries({
                        queryKey: ["workspace"],
                      });
                      setSaveStatus("Đã lưu.");
                      return "Đã lưu phân tích.";
                    }}
                  />
                  {saveStatus && <p className="positive mt-4">{saveStatus}</p>}
                </div>
              </Panel>
            </>
          )}
          {mode === "batch" && batch && (
            <Panel
              title="Kết quả danh mục"
              note="Kết quả proxy nghiên cứu · không phải xác suất vỡ nợ đã kiểm chứng"
              actions={
                <Button
                  variant="outline"
                  onClick={() =>
                    downloadCsv(
                      "finhealth-portfolio.csv",
                      Object.keys(batch.results?.[0] ?? {}),
                      batch.results ?? [],
                      label,
                    )
                  }
                >
                  Xuất kết quả CSV
                </Button>
              }
            >
              <div className="panel-body">
                <Evidence data={batch} />
              </div>
            </Panel>
          )}
        </>
      )}
    </>
  );
}
