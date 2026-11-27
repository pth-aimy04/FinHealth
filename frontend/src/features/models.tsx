import { useMemo, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { request, type Schema } from "../lib/api/client";
import { number, percent } from "../lib/formatters";
import {
  Empty,
  Evidence,
  PageTitle,
  Panel,
  QueryState,
  Stat,
  TableRegion,
} from "../components/shared";
import { Chart } from "../components/charts/chart";
const figures = [
  "01_correlation_heatmap",
  "02_pca_scree_and_clusters",
  "03_roc_pr_curves_comparison",
  "04_confusion_matrices",
  "05_forecasting_actual_vs_predicted",
  "06_shap_global_importance",
  "07_reliability_calibration",
];
const figureNames = [
  "Tương quan đặc trưng",
  "PCA và phân cụm",
  "ROC / Precision–Recall",
  "Ma trận nhầm lẫn",
  "Thực tế và dự báo",
  "Độ quan trọng TreeSHAP",
  "Hiệu chỉnh xác suất",
];
/** Evaluation, PCA research drilldown and original model figures. */
export default function Models(): ReactElement {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const version = params.get("version") ?? "";
  const axis = params.get("axis") === "3" ? "pca_comp_3" : "pca_comp_2";
  const cluster = params.get("cluster") ?? "";
  const versions = useQuery({
    queryKey: ["versions"],
    queryFn: () =>
      request<Schema["ModelVersionSummarySchema"][]>("/models/versions"),
  });
  const evaluation = useQuery({
    queryKey: ["evaluation", version],
    queryFn: () =>
      request<Schema["ModelEvaluationResponseSchema"]>(
        `/models/evaluation${version ? `?model_version=${version}` : ""}`,
      ),
  });
  const points = useQuery({
    queryKey: ["clusters"],
    queryFn: () => request<Schema["ClusterPointSchema"][]>("/clusters/map"),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => request<Schema["HealthCheckSchema"]>("/health"),
  });
  const visible = useMemo(
    () =>
      (points.data ?? []).filter(
        (row) =>
          (cluster === "" || String(row.cluster_id) === cluster) &&
          row.pca_comp_1 !== null &&
          row[axis] !== null,
      ),
    [points.data, cluster, axis],
  );
  const update = (key: string, value: string): void => {
    const next = new URLSearchParams(params);
    next.set(key, value);
    setParams(next);
  };
  const report = evaluation.data?.evaluation_report;
  const selected = report?.classification_selected;
  const metrics: Record<string, unknown> =
    selected && typeof selected === "object"
      ? Object.fromEntries(Object.entries(selected))
      : {};
  return (
    <>
      <PageTitle
        title="Mô hình & phân cụm"
        description="Kiểm tra hiệu năng nghiên cứu, cách hiệu chỉnh xác suất và vị trí doanh nghiệp trong không gian đặc trưng."
      />
      <div className="notice">
        Đây là đánh giá mô hình trên tập kiểm tra. Các chỉ số dưới đây không
        phải kết quả tài chính hoặc mức độ tín nhiệm của một doanh nghiệp.
      </div>
      <Panel title="Phiên bản nghiên cứu">
        <div className="panel-body">
          <label>
            Mô hình
            <select
              value={version}
              onChange={(event) => update("version", event.target.value)}
            >
              <option value="">Mô hình đang hoạt động</option>
              {versions.data?.map((row) => (
                <option key={row.model_version} value={row.model_version}>
                  {row.model_version} · {row.dataset}{" "}
                  {row.is_active ? "· hoạt động" : ""}
                </option>
              ))}
            </select>
          </label>
          <QueryState error={versions.error} retry={versions.refetch} />
        </div>
      </Panel>
      <QueryState
        pending={evaluation.isPending}
        error={evaluation.error}
        retry={evaluation.refetch}
      />
      {report && (
        <>
          <div className="stats">
            <Stat title="ROC AUC · test" value={number(metrics.roc_auc, 4)} />
            <Stat title="PR AUC · test" value={number(metrics.pr_auc, 4)} />
            <Stat
              title="Brier score · test"
              value={number(metrics.brier_score, 4)}
              detail="Thấp hơn là tốt hơn"
            />
            <Stat
              title="Ngưỡng phân loại"
              value={percent(metrics.threshold)}
              detail="Theo validation của phiên bản đã chọn"
            />
          </div>
          <div className="grid-equal">
            <Panel title="Đối chứng phân loại">
              <div className="panel-body">
                <Evidence
                  data={
                    report.classification_candidates ??
                    report.classification_baselines
                  }
                />
              </div>
            </Panel>
            <Panel title="Hồi quy & calibration">
              <div className="panel-body">
                <Evidence
                  data={{
                    regression:
                      report.forecasting ??
                      report.regression_metrics ??
                      report.regression_results ??
                      report.regression,
                    probability_calibration: report.probability_calibration,
                    split_summary: report.split_summary,
                    clustering: report.clustering,
                  }}
                />
              </div>
            </Panel>
          </div>
          <details className="notice">
            <summary>Toàn bộ báo cáo đánh giá và provenance</summary>
            <Evidence data={report} />
          </details>
        </>
      )}
      <Panel
        title="Bản đồ PCA · mô hình đang hoạt động"
        note={`Vị trí lưu từ ${health.data?.active_model_version ?? "—"}; độc lập với bộ đánh giá đã chọn`}
      >
        <div className="panel-body toolbar">
          <label>
            Trục tung
            <select
              value={axis}
              onChange={(event) =>
                update("axis", event.target.value === "pca_comp_3" ? "3" : "2")
              }
            >
              <option value="pca_comp_2">PC2</option>
              <option value="pca_comp_3">PC3</option>
            </select>
          </label>
          <label>
            Nhóm doanh nghiệp
            <select
              value={cluster}
              onChange={(event) => update("cluster", event.target.value)}
            >
              <option value="">Tất cả cụm</option>
              {[...new Set(points.data?.map((row) => row.cluster_id))]
                .sort()
                .map((id) => (
                  <option key={id} value={id}>
                    Cụm {id}
                  </option>
                ))}
            </select>
          </label>
        </div>
        <QueryState
          pending={points.isPending}
          error={points.error}
          retry={points.refetch}
        />
        {visible.length ? (
          <>
            <Chart
              summary="Vị trí doanh nghiệp PC1 × PC2/PC3 · đơn vị: điểm PCA. Chọn một điểm hoặc liên kết trong bảng để đọc doanh nghiệp."
              option={{
                xAxis: {
                  type: "value",
                  name: "PC1",
                  splitLine: { lineStyle: { opacity: 0.1 } },
                },
                yAxis: {
                  type: "value",
                  name: axis === "pca_comp_2" ? "PC2" : "PC3",
                  splitLine: { lineStyle: { opacity: 0.1 } },
                },
                tooltip: { trigger: "item" },
                series: [...new Set(visible.map((row) => row.cluster_id))].map(
                  (id, index) => ({
                    name: `Cụm ${id}`,
                    type: "scatter",
                    symbol: ["circle", "rect", "triangle", "diamond"][
                      index % 4
                    ],
                    symbolSize: 10,
                    data: visible.flatMap((row, sourceIndex) =>
                      row.cluster_id === id
                        ? [
                            {
                              value: [row.pca_comp_1, row[axis]],
                              name: `${row.ticker ?? row.cik} · cụm ${row.cluster_id}`,
                              sourceIndex,
                            },
                          ]
                        : [],
                    ),
                  }),
                ),
              }}
              columns={[
                "Doanh nghiệp",
                "PC1",
                axis === "pca_comp_2" ? "PC2" : "PC3",
                "Cụm",
              ]}
              rows={visible.map((row) => [
                row.ticker ?? row.cik,
                number(row.pca_comp_1),
                number(row[axis]),
                row.cluster_label,
              ])}
              onPoint={(index) => navigate(`/company/${visible[index].cik}`)}
            />
            <TableRegion name="Drilldown doanh nghiệp trong cụm PCA">
              <table>
                <thead>
                  <tr>
                    <th>Doanh nghiệp</th>
                    <th>Cụm</th>
                    <th>PC1</th>
                    <th>{axis === "pca_comp_2" ? "PC2" : "PC3"}</th>
                    <th>Kỳ</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row) => (
                    <tr key={row.cik}>
                      <td>
                        <Link to={`/company/${row.cik}`}>
                          {row.ticker ?? row.cik} · {row.name}
                        </Link>
                      </td>
                      <td>{row.cluster_label}</td>
                      <td>{number(row.pca_comp_1)}</td>
                      <td>{number(row[axis])}</td>
                      <td>{row.fiscal_year}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableRegion>
          </>
        ) : (
          points.data && <Empty />
        )}
      </Panel>
      <Panel
        title="Hình nghiên cứu gốc"
        note="Hình từ bundle đã công bố, không thay đổi theo bộ chọn mô hình phía trên. Mở ảnh để phóng to."
      >
        <div className="figure-grid">
          {figures.map((name, i) => (
            <a
              key={name}
              href={`/api/v1/figures/${name}.png`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <img
                loading="lazy"
                width={1200}
                height={1000}
                style={{ aspectRatio: "6/5", objectFit: "contain" }}
                src={`/api/v1/figures/${name}.png`}
                alt={figureNames[i]}
              />
              <p>
                {String(i + 1).padStart(2, "0")} · {figureNames[i]}
              </p>
            </a>
          ))}
        </div>
      </Panel>
    </>
  );
}
