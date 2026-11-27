import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, SlidersHorizontal, Table2 } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import {
  formatPct,
  formatRatio,
  humanizeFeature,
  translateSector,
} from '@/lib/format';
import {
  RiskReturnScatterChart,
  SectorRiskChart,
} from '@/components/charts/OverviewCharts';
import {
  Button,
  EmptyState,
  ErrorState,
  InlineProbBar,
  MetricTile,
  Panel,
  PanelHeader,
  RiskBadge,
  Skeleton,
  TableSkeleton,
} from '@/components/ui/Primitives';

const RISK_TIERS = [
  { key: 'LOW', label: 'Thấp', fill: '#0D7A68' },
  { key: 'MEDIUM', label: 'Trung bình', fill: '#D97706' },
  { key: 'HIGH', label: 'Cao', fill: '#EA580C' },
  { key: 'CRITICAL', label: 'Nguy kịch', fill: '#BE123C' },
] as const;

export function OverviewPage() {
  const navigate = useNavigate();

  const overviewQuery = useQuery({
    queryKey: ['overview'],
    queryFn: api.getOverview,
  });

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
  });

  const companiesQuery = useQuery({
    queryKey: ['companies', { limit: 200 }],
    queryFn: () => api.getCompanies({ limit: 200 }),
  });

  const qualityQuery = useQuery({
    queryKey: ['data-quality'],
    queryFn: api.getDataQuality,
  });

  const companies = companiesQuery.data ?? [];

  const riskDistribution = useMemo(() => {
    const counts: Record<string, number> = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
    for (const c of companies) {
      const key = (c.risk_level ?? '').toUpperCase();
      if (key in counts) counts[key] += 1;
    }
    return RISK_TIERS.map((tier) => ({
      tier: tier.label,
      count: counts[tier.key],
      fill: tier.fill,
    }));
  }, [companies]);

  const highRiskCount = useMemo(
    () =>
      companies.filter((c) => {
        const lvl = (c.risk_level ?? '').toUpperCase();
        return lvl === 'HIGH' || lvl === 'CRITICAL';
      }).length,
    [companies],
  );

  // Interactive Sector Risk Heatmap (inspired by FireAnt / Koyfin Market Map)
  const sectorHeatmap = useMemo(() => {
    const map = new Map<
      string,
      { rawSector: string; label: string; count: number; probSum: number; probN: number; highRisk: number }
    >();
    for (const c of companies) {
      if (!c.sector) continue;
      const entry = map.get(c.sector) ?? {
        rawSector: c.sector,
        label: translateSector(c.sector),
        count: 0,
        probSum: 0,
        probN: 0,
        highRisk: 0,
      };
      entry.count += 1;
      if (typeof c.distress_probability === 'number' && Number.isFinite(c.distress_probability)) {
        entry.probSum += c.distress_probability;
        entry.probN += 1;
      }
      const lvl = (c.risk_level ?? '').toUpperCase();
      if (lvl === 'HIGH' || lvl === 'CRITICAL') entry.highRisk += 1;
      map.set(c.sector, entry);
    }
    return Array.from(map.values())
      .map((item) => ({
        ...item,
        avgProb: item.probN > 0 ? item.probSum / item.probN : null,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [companies]);

  const triageQueue = useMemo(
    () =>
      [...companies]
        .filter((c) => typeof c.distress_probability === 'number')
        .sort((a, b) => (b.distress_probability ?? -1) - (a.distress_probability ?? -1))
        .slice(0, 10),
    [companies],
  );

  const qualityEntries = useMemo(() => {
    const q = qualityQuery.data;
    if (!q || q.report_count === 0) return [];
    return Object.entries(q.observed)
      .map(([metric, observed]) => ({
        metric,
        observed,
        pct: (observed / q.report_count) * 100,
      }))
      .sort((a, b) => a.pct - b.pct)
      .slice(0, 8);
  }, [qualityQuery.data]);

  if (companiesQuery.isError) {
    return (
      <ErrorState
        title="Không thể tải trang tổng quan thị trường"
        message={
          companiesQuery.error instanceof Error
            ? companiesQuery.error.message
            : 'Không kết nối được tới máy chủ Backend.'
        }
        onRetry={() => {
          void overviewQuery.refetch();
          void companiesQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[1.4rem] font-bold tracking-[-0.025em] text-[var(--text-primary)]">
            Tổng quan Thị trường & Rủi ro Tín dụng
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Bức tranh toàn cảnh sức khỏe tài chính doanh nghiệp SEC, bản đồ nhiệt ngành và danh sách
            cảnh báo kiệt quệ ưu tiên.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/screener" className="no-underline">
            <Button variant="secondary" size="sm">
              <Table2 className="h-3.5 w-3.5" aria-hidden="true" />
              Sàng lọc Doanh nghiệp
            </Button>
          </Link>
          <Link to="/stress" className="no-underline">
            <Button variant="primary" size="sm">
              <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
              Mô phỏng Stress Test
            </Button>
          </Link>
        </div>
      </div>

      {/* Macro KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {overviewQuery.isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[92px]" />)
        ) : (
          <>
            <MetricTile
              label="Doanh nghiệp đang theo dõi"
              value={
                overviewQuery.data
                  ? overviewQuery.data.company_count.toLocaleString('vi-VN')
                  : String(companies.length)
              }
              meta="Báo cáo SEC đã kiểm toán"
            />
            <MetricTile
              label="Báo cáo thường niên 10-K"
              value={
                overviewQuery.data
                  ? overviewQuery.data.annual_statement_count.toLocaleString('vi-VN')
                  : '—'
              }
              meta="Chuỗi lịch sử tài chính"
            />
            <MetricTile
              label="Cảnh báo Rủi ro Cao"
              value={String(highRiskCount)}
              meta="Thuộc mức Cao hoặc Nguy kịch"
              accent={highRiskCount > 0 ? 'high' : 'low'}
            />
            <MetricTile
              label="Mô hình AI đang chạy"
              value={healthQuery.data?.active_model_version ?? '—'}
              meta={
                healthQuery.data?.database_connected
                  ? 'Trực tuyến · Kiểm định Out-of-time'
                  : 'Kết nối CSDL gián đoạn'
              }
              accent={healthQuery.data?.database_connected ? 'low' : 'critical'}
            />
          </>
        )}
      </div>

      {/* Interactive Sector Risk Heatmap (Click a sector tile to filter Screener!) */}
      {sectorHeatmap.length > 0 ? (
        <Panel>
          <PanelHeader
            title="Bản đồ Nhiệt Rủi ro theo Nhóm Ngành"
            description="Bấm vào từng ô ngành để lọc ngay danh sách doanh nghiệp thuộc ngành đó."
          />
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {sectorHeatmap.map((sec) => {
              const avg = sec.avgProb ?? 0;
              const toneBg =
                avg >= 0.25
                  ? 'var(--risk-critical-bg)'
                  : avg >= 0.14
                    ? 'var(--risk-high-bg)'
                    : avg >= 0.08
                      ? 'var(--risk-medium-bg)'
                      : 'var(--risk-low-bg)';
              const toneFg =
                avg >= 0.25
                  ? 'var(--risk-critical-fg)'
                  : avg >= 0.14
                    ? 'var(--risk-high-fg)'
                    : avg >= 0.08
                      ? 'var(--risk-medium-fg)'
                      : 'var(--risk-low-fg)';

              return (
                <button
                  key={sec.rawSector}
                  type="button"
                  onClick={() => navigate(`/screener?sector=${encodeURIComponent(sec.rawSector)}`)}
                  className="interactive-card text-left p-3.5 rounded-[8px] border border-[var(--border-subtle)] bg-[var(--bg-surface)] cursor-pointer flex flex-col justify-between gap-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-semibold text-[var(--text-primary)] leading-snug">
                      {sec.label}
                    </span>
                    <span
                      className="px-2 py-0.5 rounded-full text-[11px] font-mono font-semibold shrink-0"
                      style={{ backgroundColor: toneBg, color: toneFg }}
                    >
                      {formatPct(sec.avgProb)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
                    <span>
                      <strong className="num text-[var(--text-primary)]">{sec.count}</strong> doanh nghiệp
                    </span>
                    <span>
                      {sec.highRisk > 0 ? (
                        <span className="font-medium text-[var(--risk-high-fg)]">
                          {sec.highRisk} cảnh báo cao
                        </span>
                      ) : (
                        <span className="text-[var(--risk-low-fg)]">Ổn định</span>
                      )}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </Panel>
      ) : null}

      {/* Sector Stacked Distribution + Altman Z Frontier */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Panel className="lg:col-span-6">
          <PanelHeader
            title="Biên rủi ro Altman Z-Score vs Xác suất Kiệt quệ"
            description="Định vị rủi ro tín dụng toàn thị trường. Bấm vào từng điểm để mở hồ sơ phân tích."
          />
          <div className="p-4">
            {companiesQuery.isLoading ? (
              <Skeleton className="h-[280px] w-full" />
            ) : (
              <RiskReturnScatterChart companies={companies} />
            )}
          </div>
        </Panel>

        <Panel className="lg:col-span-6">
          <PanelHeader
            title="Cơ cấu Mức rủi ro theo Ngành"
            description="Phân bổ xếp chồng các bậc rủi ro theo nhóm ngành trọng điểm."
          />
          <div className="p-4">
            {companiesQuery.isLoading ? (
              <Skeleton className="h-[280px] w-full" />
            ) : (
              <SectorRiskChart companies={companies} />
            )}
          </div>
        </Panel>
      </div>

      {/* Priority Triage Queue with Inline Probability & Health Bars */}
      <Panel>
        <PanelHeader
          title="Danh sách Cảnh báo Ưu tiên (Top 10 Rủi ro Cao nhất)"
          description="Sắp xếp theo xác suất kiệt quệ năm kế tiếp P(t+1). Dữ liệu khuyết thiếu giữ nguyên '—'."
          actions={
            <Link to="/screener" className="text-xs font-medium text-[var(--accent-primary)] hover:underline no-underline">
              Xem toàn bộ {companies.length} doanh nghiệp →
            </Link>
          }
        />
        {companiesQuery.isLoading ? (
          <TableSkeleton rows={6} />
        ) : triageQueue.length === 0 ? (
          <EmptyState
            title="Chưa có doanh nghiệp được chấm điểm"
            description="Chạy phân tích SEC hoặc kích hoạt gói mô hình để hiển thị bảng xếp hạng rủi ro."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="py-2.5 px-4 font-semibold">Doanh nghiệp</th>
                  <th className="py-2.5 px-3 font-semibold">Nhóm ngành</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Năm TC</th>
                  <th className="py-2.5 px-3 font-semibold text-right">XS Kiệt quệ P(t+1)</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Điểm Sức khỏe</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Altman Z</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Tỷ lệ nợ</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Mức rủi ro</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)] text-xs">
                {triageQueue.map((row) => (
                  <tr key={row.cik} className="hover:bg-[var(--bg-hover)] transition-colors">
                    <td className="py-2.5 px-4">
                      <Link
                        to={`/companies/${encodeURIComponent(row.ticker || row.cik)}`}
                        className="inline-flex items-center gap-2 font-medium text-[var(--text-primary)] hover:text-[var(--accent-primary)] no-underline"
                      >
                        <span className="font-mono font-bold text-[var(--accent-primary)] w-11 shrink-0">
                          {row.ticker ?? row.cik}
                        </span>
                        <span className="truncate max-w-[180px]">{row.name}</span>
                        <ArrowUpRight className="h-3 w-3 opacity-50 shrink-0" aria-hidden="true" />
                      </Link>
                    </td>
                    <td className="py-2.5 px-3 text-[var(--text-secondary)] truncate max-w-[160px]">
                      {translateSector(row.sector)}
                    </td>
                    <td className="py-2.5 px-3 text-right num text-[var(--text-secondary)]">
                      {row.latest_fiscal_year ?? '—'}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <InlineProbBar value={row.distress_probability} tone="risk" />
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <InlineProbBar value={row.composite_health_score} tone="health" />
                    </td>
                    <td className="py-2.5 px-3 text-right num text-[var(--text-secondary)]">
                      {formatRatio(row.altman_z_score)}
                    </td>
                    <td className="py-2.5 px-3 text-right num text-[var(--text-secondary)]">
                      {formatPct(row.debt_ratio)}
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <RiskBadge level={row.risk_level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Bottom Row: Risk Tier Summary + Data Coverage */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Panel className="lg:col-span-7">
          <PanelHeader
            title="Phân bổ Toàn thị trường theo Bậc Rủi ro"
            description="Tổng số doanh nghiệp phân loại theo ngưỡng rủi ro dự báo t+1."
          />
          <div className="p-4 h-[250px]">
            {companiesQuery.isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={riskDistribution} margin={{ top: 8, right: 16, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis
                    dataKey="tier"
                    tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    axisLine={{ stroke: 'var(--border-subtle)' }}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: 'var(--bg-hover)' }}
                    contentStyle={{
                      backgroundColor: 'var(--bg-surface)',
                      border: '1px solid var(--border-strong)',
                      borderRadius: '6px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" name="Số doanh nghiệp" radius={[4, 4, 0, 0]} maxBarSize={56}>
                    {riskDistribution.map((entry) => (
                      <Cell key={entry.tier} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        <Panel className="lg:col-span-5">
          <PanelHeader
            title="Độ phủ Dữ liệu Báo cáo Năm"
            description={
              qualityQuery.data
                ? `Tỷ lệ có số liệu thực trên ${qualityQuery.data.report_count.toLocaleString('vi-VN')} kỳ báo cáo.`
                : 'Độ đầy đủ dữ liệu kế toán.'
            }
          />
          <div className="p-4 space-y-2.5">
            {qualityQuery.isLoading ? (
              <TableSkeleton rows={5} />
            ) : qualityEntries.length === 0 ? (
              <EmptyState
                title="Chưa có thống kê độ phủ"
                description="Chỉ số chất lượng dữ liệu sẽ xuất hiện khi có báo cáo thường niên."
              />
            ) : (
              qualityEntries.map((item) => (
                <div key={item.metric} className="space-y-1">
                  <div className="flex items-center justify-between text-xs gap-2">
                    <span className="text-[var(--text-secondary)] truncate" title={item.metric}>
                      {humanizeFeature(item.metric)}
                    </span>
                    <span className="num text-[var(--text-primary)] font-medium shrink-0">
                      {item.pct.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-[var(--bg-subtle)] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[var(--accent-primary)]"
                      style={{ width: `${Math.min(100, Math.max(0, item.pct))}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
