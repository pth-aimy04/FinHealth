import { useState, type ReactElement } from "react";
import type { Schema } from "../lib/api/client";
import { metric, label } from "../lib/formatters";
import { Chart } from "../components/charts/chart";
import { Panel } from "../components/shared";
type Metric = "roa" | "roe" | "eps" | "debt_ratio" | "ocf_ratio";
/** Overlay aligned issuer histories and forecasts without bridging absent annual observations. */
export function ComparisonChart({
  result,
}: {
  result: Schema["CompanyComparisonResponseSchema"];
}): ReactElement {
  const [field, setField] = useState<Metric>("roa");
  const years = Object.values(result.historical_series)
    .flatMap((rows) => rows.map((row) => row.fiscal_year))
    .concat(
      result.companies.flatMap((row) =>
        row.target_fiscal_year ? [row.target_fiscal_year] : [],
      ),
    );
  if (!years.length) return <></>;
  const timeline = Array.from(
    { length: Math.max(...years) - Math.min(...years) + 1 },
    (_, i) => Math.min(...years) + i,
  );
  const series = result.companies.flatMap((company, index) => {
    const history =
      result.historical_series[company.cik] ??
      result.historical_series[company.ticker ?? ""] ??
      [];
    const color = `var(--chart-${index + 1})`;
    const values = timeline.map(
      (year) =>
        history.find((row) => row.fiscal_year === year)?.[field] ?? null,
    );
    const forecast = timeline.map((year) =>
      year === company.target_fiscal_year
        ? (company[`pred_${field}`] ?? null)
        : year === company.fiscal_year &&
            company.target_fiscal_year === year + 1
          ? (company[field] ?? null)
          : null,
    );
    const scale = (value: number | null): number | null =>
      value === null ? null : field === "eps" ? value : value * 100;
    return [
      {
        name: `${company.ticker ?? company.cik} · thực tế`,
        type: "line",
        connectNulls: false,
        data: values.map(scale),
        lineStyle: { type: "solid", width: 2 },
        itemStyle: { color },
      },
      {
        name: `${company.ticker ?? company.cik} · dự báo`,
        type: "line",
        symbol: "diamond",
        connectNulls: false,
        data: forecast.map(scale),
        lineStyle: { type: "dashed", width: 2 },
        itemStyle: { color },
      },
    ];
  });
  return (
    <Panel
      title="Lịch sử & dự báo đối chiếu"
      note={
        field === "eps"
          ? "USD/cổ phiếu · chỉ so sánh các báo cáo SEC"
          : "% · theo năm tài chính, ngày kết thúc kỳ có thể khác nhau"
      }
      actions={
        <label>
          Chỉ tiêu
          <select
            value={field}
            onChange={(event) => {
              const next = event.target.value;
              if (
                next === "roa" ||
                next === "roe" ||
                next === "eps" ||
                next === "debt_ratio" ||
                next === "ocf_ratio"
              )
                setField(next);
            }}
          >
            {["roa", "roe", "eps", "debt_ratio", "ocf_ratio"].map((key) => (
              <option key={key} value={key}>
                {label(key)}
              </option>
            ))}
          </select>
        </label>
      }
    >
      <Chart
        summary="Nét liền: thực tế; nét đứt và hình thoi: dự báo theo báo cáo gốc đã chọn. Thiếu dữ liệu được ngắt; không có dải tin cậy được suy đoán."
        option={{
          xAxis: { type: "category", data: timeline.map(String) },
          yAxis: {
            type: "value",
            name: field === "eps" ? "USD/cổ phiếu" : "%",
            splitLine: { lineStyle: { opacity: 0.1 } },
          },
          grid: { top: 65, left: 60, right: 28, bottom: 40 },
          series,
        }}
        columns={[
          "Năm",
          ...result.companies.flatMap((row) => [
            `${row.ticker ?? row.cik} thực tế`,
            `${row.ticker ?? row.cik} dự báo`,
          ]),
        ]}
        rows={timeline.map((year) => [
          year,
          ...result.companies.flatMap((company) => {
            const history =
              result.historical_series[company.cik] ??
              result.historical_series[company.ticker ?? ""] ??
              [];
            return [
              metric(
                field,
                history.find((row) => row.fiscal_year === year)?.[field],
              ),
              metric(
                field,
                company.target_fiscal_year === year
                  ? company[`pred_${field}`]
                  : null,
              ),
            ];
          }),
        ])}
      />
    </Panel>
  );
}
