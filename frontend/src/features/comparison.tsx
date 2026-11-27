import { useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { request, type Schema } from "../lib/api/client";
import { date, label, metric, percent } from "../lib/formatters";
import {
  Empty,
  Evidence,
  PageTitle,
  Panel,
  QueryState,
  TableRegion,
} from "../components/shared";
import { Button } from "../components/ui/button";
import { HistoryChart } from "./company";
import { ComparisonChart } from "./comparison-chart";
/** Two-to-four issuer comparison using explicitly aligned annual API periods. */
export default function Comparison(): ReactElement {
  const [params, setParams] = useSearchParams();
  const identifiers = params.get("identifiers") ?? "";
  const year = params.get("common_fiscal_year") ?? "";
  const [validation, setValidation] = useState("");
  const query = useQuery({
    queryKey: ["compare", identifiers, year],
    enabled: identifiers.split(",").filter(Boolean).length >= 2,
    queryFn: ({ signal }) =>
      request<Schema["CompanyComparisonResponseSchema"]>(
        `/companies/compare?${new URLSearchParams({ identifiers, ...(year ? { common_fiscal_year: year } : {}) })}`,
        { signal },
      ),
  });
  const result = query.data;
  return (
    <>
      <PageTitle
        title="So sánh doanh nghiệp"
        description="Đặt 2–4 doanh nghiệp cạnh nhau, căn chỉnh năm tài chính và đối chiếu nền tảng kế toán."
      />
      <Panel
        title="Nhóm nghiên cứu"
        note="Nhập ticker hoặc CIK, phân cách bằng dấu phẩy"
      >
        <form
          className="panel-body form-stack"
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            const ids = String(form.get("identifiers"))
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean);
            if (
              ids.length < 2 ||
              ids.length > 4 ||
              new Set(ids).size !== ids.length
            ) {
              setValidation("Chọn 2–4 doanh nghiệp khác nhau.");
              return;
            }
            setValidation("");
            setParams({
              identifiers: ids.join(","),
              ...(form.get("year")
                ? { common_fiscal_year: String(form.get("year")) }
                : {}),
            });
          }}
        >
          <div className="form-grid">
            <label>
              Doanh nghiệp
              <input
                name="identifiers"
                defaultValue={identifiers}
                placeholder="Ví dụ: AAPL, MSFT"
                required
              />
            </label>
            <label>
              Năm tài chính chung
              <input
                name="year"
                type="number"
                min={1990}
                max={2100}
                defaultValue={year}
                placeholder="Trống = báo cáo năm mới nhất"
              />
            </label>
          </div>
          {validation && (
            <p role="alert" className="field-error">
              {validation}
            </p>
          )}
          <Button>So sánh nhóm</Button>
        </form>
      </Panel>
      <QueryState
        pending={query.isFetching}
        error={query.error}
        retry={query.refetch}
      />
      {!identifiers && (
        <Empty message="Chọn doanh nghiệp từ bảng sàng lọc hoặc nhập ticker/CIK ở trên để bắt đầu." />
      )}
      {result && (
        <>
          <div className="notice">
            <strong>
              {result.period_policy === "common_fiscal_year"
                ? `Năm tài chính chung: ${result.common_fiscal_year}`
                : "Báo cáo năm mới nhất của từng doanh nghiệp"}
              .
            </strong>{" "}
            USD và USD/cổ phiếu · Kết thúc kỳ có thể khác nhau. Trung vị chỉ
            thuộc nhóm đã chọn; không phải benchmark toàn thị trường.
          </div>
          <Panel
            title="Đối chiếu chỉ số"
            note={`Phiên bản mô hình: ${result.active_model_version ?? "—"}`}
          >
            <TableRegion name="So sánh chỉ số nhóm doanh nghiệp">
              <table>
                <thead>
                  <tr>
                    <th>Chỉ tiêu</th>
                    {result.companies.map((row) => (
                      <th key={row.cik}>
                        <Link to={`/company/${row.cik}`}>
                          {row.ticker ?? row.cik}
                        </Link>
                        <div>
                          {row.fiscal_year} · {date(row.period_end_date)}
                        </div>
                        <div className="muted">
                          Công bố {date(row.filed_date)}
                        </div>
                      </th>
                    ))}
                    <th>Trung vị nhóm</th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      "roa",
                      "roe",
                      "eps",
                      "debt_ratio",
                      "current_ratio",
                      "ocf_ratio",
                      "altman_z_score",
                      "composite_health_score",
                    ] as const
                  ).map((key) => (
                    <tr key={key}>
                      <td>{label(key)}</td>
                      {result.companies.map((row) => (
                        <td key={row.cik}>{metric(key, row[key])}</td>
                      ))}
                      <td>{metric(key, result.cohort_medians[key])}</td>
                    </tr>
                  ))}
                  <tr>
                    <td>Chỉ báo khó khăn · dự báo</td>
                    {result.companies.map((row) => (
                      <td key={row.cik}>
                        {percent(row.distress_probability)}
                        <div className="muted">
                          Kỳ {row.target_fiscal_year ?? "—"}
                        </div>
                      </td>
                    ))}
                    <td>—</td>
                  </tr>
                  {(
                    [
                      "pred_roa",
                      "pred_roe",
                      "pred_eps",
                      "pred_debt_ratio",
                      "pred_ocf_ratio",
                    ] as const
                  ).map((key) => (
                    <tr key={key}>
                      <td>Dự báo · {label(key.slice(5))}</td>
                      {result.companies.map((row) => (
                        <td key={row.cik}>{metric(key, row[key])}</td>
                      ))}
                      <td>—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableRegion>
          </Panel>
          <ComparisonChart result={result} />
          <div className="grid-equal">
            {result.companies.map((row) => (
              <Panel
                key={row.cik}
                title={`${row.ticker ?? row.cik} · Lịch sử ROA`}
                note="Thực tế theo năm tài chính · %"
              >
                <HistoryChart
                  history={
                    result.historical_series[row.cik] ??
                    result.historical_series[row.ticker ?? ""] ??
                    []
                  }
                />
                <details className="panel-body">
                  <summary>DuPont, chất lượng lợi nhuận và nguồn</summary>
                  <Evidence data={row} />
                </details>
              </Panel>
            ))}
          </div>
        </>
      )}
    </>
  );
}
