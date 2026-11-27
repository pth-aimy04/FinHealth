import { useQuery } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Building2,
  FileText,
  ShieldCheck,
} from "lucide-react";
import { companies, request, type Schema } from "../lib/api/client";
import { date, number, percent } from "../lib/formatters";
import {
  Empty,
  PageTitle,
  Panel,
  QueryState,
  Risk,
  Stat,
  TableRegion,
  riskLabels,
} from "../components/shared";
import { Button } from "../components/ui/button";
import { Chart } from "../components/charts/chart";
/** Inventory and risk distribution from persisted API observations. */
export default function Overview(): ReactElement {
  const inventory = useQuery({
    queryKey: ["overview"],
    queryFn: () =>
      request<{ company_count: number; annual_statement_count: number }>(
        "/dashboard/overview",
      ),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => request<Schema["HealthCheckSchema"]>("/health"),
  });
  const query = useQuery({
    queryKey: ["companies", ""],
    queryFn: ({ signal }) => companies(undefined, signal),
  });
  const rows = query.data ?? [];
  const scored = rows.filter((row) => row.risk_level != null);
  const sectorCounts = Object.entries(
    rows.reduce<Record<string, number>>((acc, row) => {
      const key = row.sector ?? "Chưa phân ngành";
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {}),
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const latest = rows
    .flatMap((row) => (row.filed_date ? [row.filed_date] : []))
    .sort()
    .at(-1);
  return (
    <>
      <PageTitle
        eyebrow="FINHEALTH / TỔNG QUAN"
        title="Toàn cảnh sức khỏe tài chính"
        description="Từ dữ liệu báo cáo đến góc nhìn rủi ro. Bắt đầu nghiên cứu với những gì doanh nghiệp thực sự công bố."
        actions={
          <Button asChild>
            <Link to="/screener">
              Khám phá doanh nghiệp
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </Button>
        }
      />
      <QueryState
        pending={inventory.isPending}
        error={inventory.error}
        retry={inventory.refetch}
      />
      <div className="stats">
        <Stat
          title="Doanh nghiệp"
          value={number(inventory.data?.company_count, 0)}
          icon={<Building2 size={19} />}
          detail="Độ phủ trong cơ sở dữ liệu"
        />
        <Stat
          title="Báo cáo năm"
          value={number(inventory.data?.annual_statement_count, 0)}
          icon={<FileText size={19} />}
          detail="Báo cáo 10-K đã thu nhận"
        />
        <Stat
          title="Có đánh giá rủi ro"
          value={number(scored.length, 0)}
          icon={<ShieldCheck size={19} />}
          detail={`${rows.length} doanh nghiệp trong vũ trụ SEC`}
        />
        <Stat
          title="Mô hình hoạt động"
          value={health.data?.active_model_version ?? "—"}
          icon={<Activity size={19} />}
          detail={
            health.data?.database_connected
              ? "Đã kết nối cơ sở dữ liệu"
              : "Chưa xác nhận trạng thái kết nối"
          }
        />
      </div>
      <QueryState
        pending={query.isPending}
        error={query.error ?? health.error}
        retry={() => {
          void query.refetch();
          void health.refetch();
        }}
      />
      {!query.isPending && !query.error && rows.length === 0 && <Empty />}
      <div className="grid-two">
        <Panel
          title="Độ phủ theo ngành"
          note="6 ngành có nhiều doanh nghiệp nhất · đơn vị: doanh nghiệp"
        >
          {sectorCounts.length ? (
            <Chart
              summary="Số doanh nghiệp đã lưu theo ngành. Đây là độ phủ dữ liệu, không phải tỷ trọng thị trường."
              option={{
                xAxis: {
                  type: "value",
                  minInterval: 1,
                  splitLine: { show: false },
                },
                yAxis: {
                  type: "category",
                  data: sectorCounts.map(([key]) => key),
                  axisLabel: { width: 120, overflow: "truncate" },
                },
                grid: { left: 150, right: 36, top: 20, bottom: 36 },
                series: [
                  {
                    name: "Doanh nghiệp",
                    type: "bar",
                    barWidth: 14,
                    itemStyle: { borderRadius: [0, 3, 3, 0] },
                    data: sectorCounts.map(([, value]) => value),
                    label: { show: true, position: "right" },
                  },
                ],
              }}
              columns={["Ngành", "Doanh nghiệp"]}
              rows={sectorCounts}
            />
          ) : (
            <Empty />
          )}
        </Panel>
        <Panel
          title="Phân bố chỉ báo rủi ro"
          note={`${scored.length} quan sát có nhãn · ${rows.length - scored.length} chưa đánh giá`}
        >
          <div className="distribution">
            {Object.entries(riskLabels).map(([key, text], index) => {
              const count = rows.filter((row) => row.risk_level === key).length;
              return (
                <div className="distribution-row" key={key}>
                  <Risk value={key} />
                  <div
                    className="bar-track"
                    role="img"
                    aria-label={`${text}: ${count} doanh nghiệp`}
                  >
                    <div
                      className="bar-fill"
                      style={{
                        width: `${scored.length ? (count / scored.length) * 100 : 0}%`,
                        background: `var(--chart-${[2, 3, 5, 4][index]})`,
                      }}
                    />
                  </div>
                  <span>{count}</span>
                </div>
              );
            })}
            <p className="small muted">
              Nhãn mô hình dựa trên proxy khó khăn tài chính. Chưa phải xếp hạng
              tín dụng bên ngoài.
            </p>
          </div>
        </Panel>
      </div>
      <Panel
        title="Bắt đầu nghiên cứu"
        note={`Ngày công bố mới nhất: ${date(latest)} · Chọn doanh nghiệp để xem nguồn và kỳ tài chính`}
        actions={
          <Link className="small source-link" to="/screener">
            Xem tất cả
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        }
      >
        <TableRegion name="Doanh nghiệp trong vũ trụ nghiên cứu">
          <table>
            <thead>
              <tr>
                <th>Doanh nghiệp</th>
                <th>Ngành</th>
                <th>ROA</th>
                <th>Nợ / tài sản</th>
                <th>Chỉ báo rủi ro</th>
                <th>Kỳ</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 5).map((row) => (
                <tr key={row.cik}>
                  <td>
                    <div className="company-cell">
                      <span className="ticker-mark" aria-hidden="true">
                        {row.ticker?.slice(0, 3) ?? "CIK"}
                      </span>
                      <div>
                        <Link to={`/company/${row.cik}`}>
                          {row.ticker ?? row.cik}
                        </Link>
                        <div className="company-name" title={row.name}>
                          {row.name}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="muted">{row.sector ?? "—"}</td>
                  <td>{percent(row.roa)}</td>
                  <td>{percent(row.debt_ratio)}</td>
                  <td>
                    <Risk value={row.risk_level} />
                  </td>
                  <td>{row.latest_fiscal_year ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableRegion>
      </Panel>
      <div className="notice">
        <strong>Đọc dữ liệu trong đúng ngữ cảnh.</strong> Điểm sức khỏe là thước
        đo nghiên cứu nội bộ. Kết quả phụ thuộc vào độ phủ báo cáo, kỳ tài chính
        và phiên bản mô hình. Dữ liệu Việt Nam thí điểm chỉ phục vụ đọc báo cáo.
      </div>
    </>
  );
}
