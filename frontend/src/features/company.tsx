import { HealthPillars } from "../components/health-pillars";
import { historySeries } from "../lib/series";
import { useMemo, useState, type ReactElement } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import * as Tabs from "@radix-ui/react-tabs";
import { BookmarkPlus, Download, FileText, Printer } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  mutate,
  request,
  type Analysis,
  type History,
  type Prediction,
  type Schema,
} from "../lib/api/client";
import { date, label, metric, number, percent } from "../lib/formatters";
import { downloadCsv } from "../lib/csv";
import { useSession } from "../app/session";
import {
  Empty,
  Evidence,
  PageTitle,
  Panel,
  QueryState,
  Risk,
  Stat,
  TableRegion,
} from "../components/shared";
import { Button } from "../components/ui/button";
import { Chart } from "../components/charts/chart";

const ratios = [
  "roa",
  "roe",
  "debt_ratio",
  "ocf_ratio",
  "current_ratio",
  "cash_ratio",
  "interest_coverage",
  "fcf_to_liabilities",
  "operating_margin",
  "eps",
  "debt_to_equity",
  "altman_z_score",
] as const;
/** Annual series with dashed forecast and accessible exact values. */
export function HistoryChart({
  history,
  prediction,
  field = "roa",
}: {
  history: History[];
  prediction?: Prediction | null;
  field?: "roa" | "roe" | "debt_ratio" | "ocf_ratio" | "eps";
}): ReactElement {
  const points = useMemo(
    () => historySeries(history, prediction, field),
    [history, prediction, field],
  );
  const multiplier = field === "eps" ? 1 : 100;
  const option = useMemo(
    () => ({
      xAxis: {
        type: "category",
        data: points.years.map(String),
        boundaryGap: false,
      },
      yAxis: {
        type: "value",
        name: field === "eps" ? "USD/cổ phiếu" : "%",
        splitLine: { lineStyle: { opacity: 0.12 } },
      },
      series: [
        {
          name: "Thực tế",
          type: "line",
          symbolSize: 6,
          connectNulls: false,
          data: points.actual.map((value) =>
            value === null ? null : value * multiplier,
          ),
          lineStyle: { width: 2 },
        },
        {
          name: "Dự báo",
          type: "line",
          symbol: "diamond",
          connectNulls: false,
          lineStyle: { type: "dashed", width: 2 },
          data: points.forecast.map((value) =>
            value === null ? null : value * multiplier,
          ),
        },
      ],
    }),
    [points, field, multiplier],
  );
  return (
    <Chart
      summary={`${label(field)} theo kỳ tài chính · ${field === "eps" ? "USD/cổ phiếu" : "%"} · thực tế nét liền, dự báo nét đứt. Quan sát thiếu được ngắt.`}
      option={option}
      columns={["Năm", "Thực tế", "Dự báo"]}
      rows={points.years.map((year, i) => [
        year,
        metric(field, points.actual[i]),
        metric(field, points.forecast[i]),
      ])}
    />
  );
}
/** Output-space aware attribution, separated from calibrated proxy probability. */
export function PredictionView({
  prediction,
}: {
  prediction: Prediction;
}): ReactElement {
  const contributions = Object.entries(prediction.contributions ?? {});
  return (
    <>
      <div className="stats">
        <Stat
          title="Xác suất chỉ báo khó khăn"
          value={percent(prediction.distress_probability)}
          detail={<Risk value={prediction.risk_level} />}
        />
        <Stat
          title="Năm dự báo"
          value={prediction.target_fiscal_year}
          detail={prediction.target_fiscal_period}
        />
        <Stat title="Mô hình" value={prediction.model_version} />
        <Stat
          title="Không gian TreeSHAP"
          value={prediction.output_space}
          detail="Tách riêng khỏi xác suất đã hiệu chỉnh"
        />
      </div>
      <Panel
        title="TreeSHAP · đóng góp vào đầu ra gốc"
        note={`Base value ${number(prediction.base_value, 5)} · raw margin ${number(prediction.raw_margin, 5)} · raw probability ${percent(prediction.raw_probability)}`}
      >
        <Chart
          summary={`Đóng góp TreeSHAP theo ${prediction.output_space}; dấu dương tăng đầu ra gốc, dấu âm giảm đầu ra gốc.`}
          option={{
            grid: { left: 150, right: 32, top: 24, bottom: 36 },
            xAxis: { type: "value", name: prediction.output_space },
            yAxis: {
              type: "category",
              data: contributions.map(([key]) => label(key)),
              axisLabel: { width: 130, overflow: "truncate" },
            },
            series: [
              {
                name: "TreeSHAP",
                type: "bar",
                data: contributions.map(([, value]) => value),
                barMaxWidth: 16,
              },
            ],
          }}
          columns={["Đặc trưng", "Đầu vào fitted", "Đóng góp TreeSHAP"]}
          rows={contributions.map(([key, value]) => [
            label(key),
            number(prediction.feature_values?.[key], 6),
            number(value, 6),
          ])}
        />
        <div className="panel-body">
          <TableRegion name="Toàn bộ đầu vào và đóng góp TreeSHAP">
            <table>
              <thead>
                <tr>
                  <th>Đặc trưng</th>
                  <th>Đầu vào fitted</th>
                  <th>TreeSHAP ({prediction.output_space})</th>
                </tr>
              </thead>
              <tbody>
                {contributions.map(([key, value]) => (
                  <tr key={key}>
                    <td>{label(key)}</td>
                    <td>{number(prediction.feature_values?.[key], 6)}</td>
                    <td>{number(value, 6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableRegion>
        </div>
      </Panel>
      <Panel
        title="Các tỷ số dự báo"
        note={`Kỳ ${prediction.target_fiscal_year} · kết quả mô hình, không phải số liệu đã công bố`}
      >
        <div className="panel-body">
          <Evidence
            data={Object.fromEntries(
              [
                "pred_roa",
                "pred_roe",
                "pred_eps",
                "pred_debt_ratio",
                "pred_ocf_ratio",
              ].map((key) => [key, prediction[key as keyof Prediction]]),
            )}
          />
        </div>
      </Panel>
    </>
  );
}
const stressSchema = z.object({
  revenue_shock_pct: z.number().min(-0.5).max(0.5),
  operating_margin_delta_pct: z.number().min(-0.3).max(0.3),
  debt_change_pct: z.number().min(-0.5).max(1),
  ocf_shock_pct: z.number().min(-0.8).max(0.8),
});
type Stress = z.infer<typeof stressSchema>;
/** Explicit read-only accounting shocks using the actual simulation endpoint. */
function StressForm({ identifier }: { identifier: string }): ReactElement {
  const form = useForm<Stress>({
    resolver: zodResolver(stressSchema),
    defaultValues: {
      revenue_shock_pct: 0,
      operating_margin_delta_pct: 0,
      debt_change_pct: 0,
      ocf_shock_pct: 0,
    },
  });
  const mutation = useMutation({
    mutationFn: (input: Stress) =>
      mutate<Schema["StressSimulationResponseSchema"]>(
        `/companies/${encodeURIComponent(identifier)}/simulate`,
        input,
      ),
  });
  const presets: Record<string, Stress> = {
    "Suy thoái": {
      revenue_shock_pct: -0.15,
      operating_margin_delta_pct: -0.05,
      debt_change_pct: 0.2,
      ocf_shock_pct: -0.25,
    },
    "Gián đoạn": {
      revenue_shock_pct: -0.3,
      operating_margin_delta_pct: -0.1,
      debt_change_pct: 0.3,
      ocf_shock_pct: -0.4,
    },
    "Thanh khoản": {
      revenue_shock_pct: 0,
      operating_margin_delta_pct: 0,
      debt_change_pct: 0.4,
      ocf_shock_pct: -0.5,
    },
  };
  return (
    <Panel
      title="Mô phỏng sức chịu đựng"
      note="Giá trị dạng thập phân · −0,15 tương ứng giảm 15% · không ghi lại báo cáo"
    >
      <div className="panel-body">
        <div className="actions mb-6">
          {Object.entries(presets).map(([name, value]) => (
            <Button
              key={name}
              variant="outline"
              onClick={() => form.reset(value)}
            >
              {name}
            </Button>
          ))}
        </div>
        <form
          className="form-stack"
          onSubmit={form.handleSubmit((input) => mutation.mutate(input))}
        >
          <div className="form-grid">
            {Object.entries({
              revenue_shock_pct: "Thay đổi doanh thu [−0,5; 0,5]",
              operating_margin_delta_pct: "Thay đổi biên hoạt động [−0,3; 0,3]",
              debt_change_pct: "Thay đổi nợ [−0,5; 1]",
              ocf_shock_pct: "Thay đổi dòng tiền [−0,8; 0,8]",
            }).map(([key, text]) => {
              const name = key as keyof Stress;
              return (
                <label key={key}>
                  {text}
                  <input
                    type="number"
                    step="any"
                    {...form.register(name, { valueAsNumber: true })}
                    aria-invalid={Boolean(form.formState.errors[name])}
                    aria-describedby={`${key}-error`}
                  />
                  <span id={`${key}-error`} className="field-error">
                    {form.formState.errors[name]?.message}
                  </span>
                </label>
              );
            })}
          </div>
          <Button disabled={mutation.isPending}>
            {mutation.isPending ? "Đang mô phỏng…" : "Chạy mô phỏng"}
          </Button>
        </form>
        <QueryState error={mutation.error} retry={() => mutation.reset()} />
        {mutation.data && (
          <>
            <div className="notice mt-6">
              Mô phỏng giả định ·{" "}
              {mutation.data.is_ood_scenario
                ? "Cảnh báo: ngoài miền dữ liệu huấn luyện"
                : "Xem giả định trước khi diễn giải"}
            </div>
            <TableRegion name="Đối chiếu thực tế và mô phỏng">
              <table>
                <thead>
                  <tr>
                    <th>Chỉ tiêu</th>
                    <th>Cơ sở</th>
                    <th>Mô phỏng</th>
                  </tr>
                </thead>
                <tbody>
                  {ratios.map((key) => (
                    <tr key={key}>
                      <td>{label(key)}</td>
                      <td>
                        {metric(key, mutation.data?.baseline.metrics[key])}
                      </td>
                      <td>
                        {metric(key, mutation.data?.stressed.metrics[key])}
                      </td>
                    </tr>
                  ))}
                  <tr>
                    <td>Chỉ báo khó khăn</td>
                    <td>
                      {percent(
                        mutation.data.baseline.prediction.distress_probability,
                      )}
                    </td>
                    <td>
                      {percent(
                        mutation.data.stressed.prediction.distress_probability,
                      )}
                    </td>
                  </tr>
                </tbody>
              </table>
            </TableRegion>
            <Evidence
              data={{
                assumptions: mutation.data.assumptions,
                ood_features: mutation.data.ood_features,
                top_shifted_shap_drivers:
                  mutation.data.top_shifted_shap_drivers,
              }}
            />
          </>
        )}
      </div>
    </Panel>
  );
}
/** Company research with financials, forensic evidence, forecast attribution and simulations. */
export default function CompanyPage(): ReactElement {
  const { identifier = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "overview";
  const formType = params.get("form") === "10-Q" ? "10-Q" : "10-K";
  const { user } = useSession();
  const client = useQueryClient();
  const [chartField, setChartField] = useState<
    "roa" | "roe" | "eps" | "debt_ratio" | "ocf_ratio"
  >("roa");
  const query = useQuery({
    queryKey: ["company", identifier, formType],
    queryFn: ({ signal }) =>
      request<Analysis>(
        `/companies/${encodeURIComponent(identifier)}?include_provenance=true&form_type=${formType}`,
        { signal },
      ),
  });
  const evaluation = useQuery({
    queryKey: ["evaluation", ""],
    queryFn: () =>
      request<Schema["ModelEvaluationResponseSchema"]>("/models/evaluation"),
  });
  const follow = useMutation({
    mutationFn: () => mutate(`/me/watchlist/${query.data?.company.cik}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["workspace"] }),
  });
  const result = query.data;
  const selected = evaluation.data?.evaluation_report.classification_selected;
  const threshold =
    selected && typeof selected === "object" && "threshold" in selected
      ? selected.threshold
      : null;
  const change = (key: string, value: string): void => {
    const next = new URLSearchParams(params);
    next.set(key, value);
    setParams(next);
  };
  return (
    <>
      <PageTitle
        eyebrow="NGHIÊN CỨU / PHÂN TÍCH DOANH NGHIỆP"
        title={
          result
            ? `${result.company.ticker ?? result.company.cik} · ${result.company.name}`
            : "Phân tích doanh nghiệp"
        }
        description={
          result
            ? `${result.company.sector ?? "Chưa phân ngành"} · CIK ${result.company.cik} · Công bố ${date(result.company.filed_date)}`
            : "Đọc hồ sơ tài chính và các kết quả nghiên cứu đã lưu."
        }
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to={`/reports?identifier=${identifier}`}>
                <FileText size={16} aria-hidden="true" />
                Báo cáo nguồn
              </Link>
            </Button>
            <Button
              variant="outline"
              disabled={
                !user || !result || follow.isPending || follow.isSuccess
              }
              title={!user ? "Đăng nhập để theo dõi" : undefined}
              onClick={() => follow.mutate()}
            >
              <BookmarkPlus size={16} aria-hidden="true" />
              {follow.isSuccess ? "Đã theo dõi" : "Theo dõi"}
            </Button>
          </>
        }
      />
      <QueryState
        pending={query.isPending}
        error={query.error ?? follow.error}
        retry={query.refetch}
      />
      {result && (
        <>
          <div className="notice">
            <strong>
              Phạm vi {formType} · {result.company.latest_fiscal_year ?? "—"}.
            </strong>{" "}
            Số liệu tài chính SEC: USD; EPS: USD/cổ phiếu. Điểm sức khỏe là nội
            bộ, không phải xếp hạng tín dụng. Xác suất khó khăn là proxy.
            Accession: {result.company.accession_number ?? "—"}.
          </div>
          <div className="toolbar mb-6">
            <label>
              Kỳ báo cáo
              <select
                value={formType}
                onChange={(event) => change("form", event.target.value)}
              >
                <option>10-K</option>
                <option>10-Q</option>
              </select>
            </label>
          </div>
          <Tabs.Root
            value={tab}
            onValueChange={(value) => change("tab", value)}
          >
            <Tabs.List className="tabs-list" aria-label="Nội dung phân tích">
              {[
                ["overview", "Tổng quan"],
                ["financials", "Tài chính"],
                ["quality", "Chất lượng lợi nhuận"],
                ["prediction", "Dự báo & TreeSHAP"],
                ["stress", "Mô phỏng"],
                ["memo", "Credit memo"],
              ].map(([value, text]) => (
                <Tabs.Trigger key={value} value={value} className="tab-trigger">
                  {text}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            <Tabs.Content value="overview">
              <div className="stats">
                <Stat
                  title="Điểm sức khỏe nội bộ"
                  value={number(result.company.composite_health_score, 1)}
                  detail={`${result.company.internal_research_grade} · thang 0–100`}
                />
                <Stat title="ROA" value={percent(result.company.roa)} />
                <Stat
                  title="Nợ phải trả / tài sản"
                  value={percent(result.company.debt_ratio)}
                />
                <Stat
                  title="Chỉ báo khó khăn"
                  value={percent(
                    result.latest_prediction?.distress_probability,
                  )}
                  detail={<Risk value={result.latest_prediction?.risk_level} />}
                />
              </div>
              <div className="grid-two">
                <Panel
                  title="Lịch sử & triển vọng"
                  note="Kỳ tài chính · dữ liệu báo cáo và kết quả mô hình"
                  actions={
                    <select
                      aria-label="Chỉ tiêu biểu đồ"
                      value={chartField}
                      onChange={(event) =>
                        setChartField(
                          z
                            .enum([
                              "roa",
                              "roe",
                              "eps",
                              "debt_ratio",
                              "ocf_ratio",
                            ])
                            .parse(event.target.value),
                        )
                      }
                    >
                      {["roa", "roe", "eps", "debt_ratio", "ocf_ratio"].map(
                        (key) => (
                          <option key={key} value={key}>
                            {label(key)}
                          </option>
                        ),
                      )}
                    </select>
                  }
                >
                  {result.history.length ? (
                    <HistoryChart
                      history={result.history}
                      prediction={result.latest_prediction}
                      field={chartField}
                    />
                  ) : (
                    <Empty />
                  )}
                </Panel>
                <Panel
                  title="Nền tảng tài chính"
                  note="Theo các chỉ tiêu quan sát · khác với điểm sức khỏe tương đối"
                >
                  <div className="panel-body">
                    {result.health_pillars ? (
                      <HealthPillars data={result.health_pillars} />
                    ) : (
                      <Empty />
                    )}
                  </div>
                </Panel>
              </div>
              <Panel
                title="Đối chiếu doanh nghiệp cùng nhóm"
                note={`${result.sector_peer_context?.cohort_size ?? 0} doanh nghiệp · ${result.sector_peer_context?.cohort === "sector" ? "cùng ngành" : "toàn vũ trụ"}`}
              >
                <TableRegion name="Trung vị ngành và thứ hạng phần trăm">
                  <table>
                    <thead>
                      <tr>
                        <th>Chỉ tiêu</th>
                        <th>Doanh nghiệp</th>
                        <th>Trung vị nhóm</th>
                        <th>Percentile</th>
                        <th>Quan sát</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(
                        result.sector_peer_context?.metrics ?? {},
                      ).map(([key, value]) => (
                        <tr key={key}>
                          <td>{label(key)}</td>
                          <td>
                            {metric(
                              key,
                              result.company[
                                key as keyof typeof result.company
                              ],
                            )}
                          </td>
                          <td>{metric(key, value.median)}</td>
                          <td>{number(value.percentile, 1)} /100</td>
                          <td>{value.n_observed}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableRegion>
              </Panel>
              <Panel title="Gợi ý nghiên cứu">
                <div className="panel-body">
                  {(result.recommendations ?? []).length ? (
                    (result.recommendations ?? []).map((item, i) => (
                      <div className="notice" key={i}>
                        <strong>
                          {
                            { HIGH: "Cao", MEDIUM: "Trung bình", LOW: "Thấp" }[
                              item.priority
                            ]
                          }{" "}
                          · {label(item.feature)}
                        </strong>
                        <p>{item.action_vi}</p>
                        <p>Đối chiếu: {item.target_benchmark}</p>
                      </div>
                    ))
                  ) : (
                    <Empty message="Chưa có khuyến nghị đủ căn cứ." />
                  )}
                </div>
              </Panel>
            </Tabs.Content>
            <Tabs.Content value="financials">
              <Panel
                title="Chỉ số tài chính"
                note="Tỷ số, lần và USD/cổ phiếu theo từng chỉ tiêu"
              >
                <div className="panel-body">
                  <Evidence
                    data={Object.fromEntries(
                      ratios.map((key) => [key, result.company[key]]),
                    )}
                  />
                </div>
              </Panel>
              <Panel
                title="Lịch sử báo cáo"
                note="USD · lưu nguyên accession, ngày công bố và provenance"
                actions={
                  <Button
                    variant="outline"
                    disabled={!user}
                    title={!user ? "Đăng nhập để xuất CSV" : undefined}
                    onClick={() =>
                      downloadCsv(
                        "finhealth-history.csv",
                        Object.keys(result.history[0] ?? {}),
                        result.history,
                        label,
                      )
                    }
                  >
                    <Download size={16} aria-hidden="true" />
                    Xuất lịch sử CSV
                  </Button>
                }
              >
                <TableRegion name="Lịch sử tài chính và nguồn SEC">
                  <table>
                    <thead>
                      <tr>
                        <th>Kỳ</th>
                        <th>Doanh thu (USD)</th>
                        <th>Lợi nhuận (USD)</th>
                        <th>ROA</th>
                        <th>ROE</th>
                        <th>Ngày công bố</th>
                        <th>Accession</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.history.map((row, i) => (
                        <tr key={i}>
                          <td>
                            {row.fiscal_period} {row.fiscal_year}
                          </td>
                          <td>{number(row.revenues)}</td>
                          <td>{number(row.net_income)}</td>
                          <td>{percent(row.roa)}</td>
                          <td>{percent(row.roe)}</td>
                          <td>{date(row.filed_date)}</td>
                          <td>{row.accession_number ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableRegion>
                <details className="panel-body">
                  <summary>Nguồn từng trường và chỉ số lịch sử đầy đủ</summary>
                  <Evidence data={result.history} />
                </details>
              </Panel>
              <Panel title="DuPont & cầu nối ROE">
                <div className="panel-body">
                  <Evidence data={result.dupont} />
                </div>
              </Panel>
              <Panel title="Các thành phần Altman">
                <div className="panel-body">
                  <Evidence data={result.altman_components} />
                </div>
              </Panel>
            </Tabs.Content>
            <Tabs.Content value="quality">
              <div className="grid-equal">
                <Panel title="Chất lượng lợi nhuận & dồn tích">
                  <div className="panel-body">
                    <Evidence data={result.quality_of_earnings} />
                  </div>
                </Panel>
                <Panel
                  title="Checklist kế toán"
                  note="Chỉ đánh giá các tín hiệu đã quan sát"
                >
                  <div className="panel-body">
                    <Evidence data={result.accounting_checklist} />
                  </div>
                </Panel>
              </div>
            </Tabs.Content>
            <Tabs.Content value="prediction">
              <div className="notice">
                Ngưỡng phân loại validation:{" "}
                <strong>
                  {typeof threshold === "number"
                    ? percent(threshold)
                    : "Chưa có dữ liệu"}
                </strong>
                . Ngưỡng này thuộc mô hình{" "}
                {evaluation.data?.model_version ?? "—"}. TreeSHAP giải thích đầu
                ra gốc; xác suất hiệu chỉnh được trình bày riêng.
              </div>
              {result.latest_prediction ? (
                <PredictionView prediction={result.latest_prediction} />
              ) : (
                <Empty message="Chưa có dự báo lưu cho báo cáo và mô hình này." />
              )}
            </Tabs.Content>
            <Tabs.Content value="stress">
              <StressForm identifier={identifier} />
            </Tabs.Content>
            <Tabs.Content value="memo">
              <Panel
                title="Bản ghi nhớ nghiên cứu tín dụng"
                note="Bản tổng hợp nội bộ · không phải khuyến nghị cấp tín dụng"
                actions={
                  <Button
                    variant="outline"
                    disabled={!user}
                    title={!user ? "Đăng nhập để in" : undefined}
                    onClick={() => window.print()}
                  >
                    <Printer size={16} aria-hidden="true" />
                    In / lưu PDF
                  </Button>
                }
              >
                <article className="panel-body form-stack">
                  <h2>{result.company.name}</h2>
                  <p>
                    CIK {result.company.cik} · Kỳ{" "}
                    {result.company.latest_fiscal_year} · Công bố{" "}
                    {date(result.company.filed_date)} ·{" "}
                    {result.company.accession_number}
                  </p>
                  <p>
                    Điểm sức khỏe:{" "}
                    {number(result.company.composite_health_score)} /100 (
                    {result.company.internal_research_grade}). Chỉ báo khó khăn:{" "}
                    {percent(result.latest_prediction?.distress_probability)}.
                  </p>
                  <Evidence
                    data={Object.fromEntries(
                      ratios.map((key) => [key, result.company[key]]),
                    )}
                  />
                  <h3>Cơ sở và giới hạn</h3>
                  <p>
                    Thước đo nghiên cứu nội bộ; proxy khó khăn tài chính không
                    đồng nghĩa xác suất vỡ nợ. Chưa bao gồm đánh giá định tính
                    hoặc thẩm định tín dụng.
                  </p>
                  <Evidence data={result.quality_of_earnings} />
                  <Evidence data={result.recommendations} />
                </article>
              </Panel>
            </Tabs.Content>
          </Tabs.Root>
        </>
      )}
    </>
  );
}
