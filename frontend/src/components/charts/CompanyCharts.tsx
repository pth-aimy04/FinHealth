import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type {
  HealthPillars,
  HistoricalMetricPoint,
  SectorPeerContext,
} from '@/types/api';
import { formatCompactUsd, formatRatio, humanizeFeature } from '@/lib/format';
import { EmptyState } from '@/components/ui/Primitives';

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--bg-surface)',
  border: '1px solid var(--border-strong)',
  borderRadius: '3px',
  fontSize: '12px',
  color: 'var(--text-primary)',
};

export function FinancialsComboChart({ history }: { history: HistoricalMetricPoint[] }) {
  const data = useMemo(
    () =>
      history.slice(-12).map((row) => ({
        period: `${row.fiscal_year}${row.fiscal_period !== 'FY' ? ` ${row.fiscal_period}` : ''}`,
        revenues: row.revenues,
        net_income: row.net_income,
        ocf: row.operating_cash_flow,
      })),
    [history],
  );

  if (data.length === 0) {
    return (
      <EmptyState
        title="Chưa có chuỗi dữ liệu tài chính"
        description="Không tìm thấy lịch sử doanh thu hoặc dòng tiền được lưu cho kỳ này."
      />
    );
  }

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 16, left: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 2" stroke="var(--border-subtle)" vertical={false} />
          <XAxis
            dataKey="period"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--border-subtle)' }}
          />
          <YAxis
            tickFormatter={(v: number) => formatCompactUsd(v)}
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={68}
          />
          <Tooltip
            formatter={(val: unknown, name: string) => [formatCompactUsd(Number(val)), name]}
            contentStyle={TOOLTIP_STYLE}
          />
          <Legend wrapperStyle={{ fontSize: '11px' }} />
          <ReferenceLine y={0} stroke="var(--border-strong)" />
          <Bar dataKey="revenues" name="Doanh thu" fill="var(--chart-1)" radius={[2, 2, 0, 0]} maxBarSize={26} isAnimationActive={false} />
          <Bar dataKey="net_income" name="Lợi nhuận ròng" fill="var(--chart-2)" radius={[2, 2, 0, 0]} maxBarSize={26} isAnimationActive={false} />
          <Line
            type="monotone"
            dataKey="ocf"
            name="Dòng tiền hoạt động (OCF)"
            stroke="var(--chart-3)"
            strokeWidth={2.2}
            dot={{ r: 3 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CapitalStructureChart({ history }: { history: HistoricalMetricPoint[] }) {
  const data = useMemo(
    () =>
      history.slice(-12).map((row) => ({
        period: `${row.fiscal_year}${row.fiscal_period !== 'FY' ? ` ${row.fiscal_period}` : ''}`,
        liabilities: row.total_liabilities,
        equity: row.stockholders_equity,
      })),
    [history],
  );

  if (data.length === 0) {
    return (
      <EmptyState
        title="Chưa có lịch sử bảng cân đối"
        description="Không có chuỗi dữ liệu tài sản và nguồn vốn được lưu."
      />
    );
  }

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, left: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 2" stroke="var(--border-subtle)" vertical={false} />
          <XAxis
            dataKey="period"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--border-subtle)' }}
          />
          <YAxis
            tickFormatter={(v: number) => formatCompactUsd(v)}
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={68}
          />
          <Tooltip
            formatter={(val: unknown, name: string) => [formatCompactUsd(Number(val)), name]}
            contentStyle={TOOLTIP_STYLE}
          />
          <Legend wrapperStyle={{ fontSize: '11px' }} />
          <ReferenceLine y={0} stroke="var(--border-strong)" />
          <Bar dataKey="liabilities" stackId="cap" name="Tổng nợ phải trả" fill="var(--chart-4)" maxBarSize={30} isAnimationActive={false} />
          <Bar
            dataKey="equity"
            stackId="cap"
            name="Vốn chủ sở hữu"
            fill="var(--chart-1)"
            radius={[2, 2, 0, 0]}
            maxBarSize={30}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AltmanZoneChart({ history }: { history: HistoricalMetricPoint[] }) {
  const data = useMemo(
    () =>
      history
        .filter((r) => typeof r.altman_z_score === 'number' && Number.isFinite(r.altman_z_score))
        .slice(-12)
        .map((r) => ({
          period: `${r.fiscal_year}${r.fiscal_period !== 'FY' ? ` ${r.fiscal_period}` : ''}`,
          z: Number((r.altman_z_score as number).toFixed(2)),
        })),
    [history],
  );

  if (data.length === 0) {
    return (
      <EmptyState
        title="Chưa có chuỗi Altman Z-Score"
        description="Cần đầy đủ dữ liệu vốn lưu động, lợi nhuận giữ lại, EBIT và đòn bẩy để tính Z-Score."
      />
    );
  }

  const maxZ = Math.max(4.5, ...data.map((d) => d.z + 0.6));
  const minZ = Math.min(0, ...data.map((d) => d.z - 0.5));

  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 16, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 2" stroke="var(--border-subtle)" />
          <XAxis
            dataKey="period"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--border-subtle)' }}
          />
          <YAxis
            domain={[minZ, maxZ]}
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <ReferenceArea y1={minZ} y2={1.81} fill="#B41D2D" fillOpacity={0.07} />
          <ReferenceArea y1={1.81} y2={2.99} fill="#B0791C" fillOpacity={0.07} />
          <ReferenceArea y1={2.99} y2={maxZ} fill="#0D6E4E" fillOpacity={0.06} />
          <ReferenceLine y={1.81} stroke="var(--risk-critical-fg)" strokeDasharray="4 4" />
          <ReferenceLine y={2.99} stroke="var(--risk-low-fg)" strokeDasharray="4 4" />
          <Tooltip
            formatter={(val: unknown) => [formatRatio(Number(val)), 'Altman Z-Score']}
            contentStyle={TOOLTIP_STYLE}
          />
          <Area
            type="monotone"
            dataKey="z"
            name="Altman Z-Score"
            stroke="var(--chart-1)"
            fill="var(--chart-1)"
            fillOpacity={0.14}
            strokeWidth={2.2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

const RADAR_SHORT_LABELS: Record<string, string> = {
  profitability: 'Sinh lời',
  liquidity: 'Thanh khoản',
  solvency: 'An toàn vốn',
  cash_flow: 'Dòng tiền',
  cash_flow_efficiency: 'Dòng tiền',
};

export function HealthPillarsRadarChart({ pillars }: { pillars: HealthPillars | null }) {
  const data = useMemo(() => {
    if (!pillars) return [];
    return Object.values(pillars.pillars).map((p) => ({
      pillar: RADAR_SHORT_LABELS[p.name] ?? p.label_vi ?? p.name,
      score: typeof p.score === 'number' ? Number(p.score.toFixed(1)) : 0,
      hasScore: typeof p.score === 'number',
    }));
  }, [pillars]);

  if (data.length === 0 || !data.some((d) => d.hasScore)) {
    return (
      <EmptyState
        title="Chưa đủ dữ liệu vẽ Radar 4 trụ cột"
        description="Thiếu các chỉ số tài chính cơ bản để chấm điểm 4 trụ cột sức khỏe."
      />
    );
  }

  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="66%">
          <PolarGrid stroke="var(--border-subtle)" />
          <PolarAngleAxis dataKey="pillar" tick={{ fill: 'var(--text-primary)', fontSize: 11, fontWeight: 600 }} />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
          />
          <Tooltip
            formatter={(v: unknown) => [`${Number(v).toFixed(1)} / 100`, 'Điểm trụ cột']}
            contentStyle={TOOLTIP_STYLE}
          />
          <Radar
            name="Trụ cột sức khỏe"
            dataKey="score"
            stroke="var(--chart-1)"
            fill="var(--chart-1)"
            fillOpacity={0.2}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PeerPercentileChart({ context }: { context: SectorPeerContext | null }) {
  const data = useMemo(() => {
    if (!context) return [];
    return Object.entries(context.metrics)
      .filter(([, m]) => typeof m.percentile === 'number' && Number.isFinite(m.percentile))
      .map(([key, m]) => ({
        metric: humanizeFeature(key),
        percentile: Number((m.percentile as number).toFixed(1)),
        median: m.median,
        n: m.n_observed,
      }))
      .slice(0, 8);
  }, [context]);

  if (data.length === 0) {
    return (
      <EmptyState
        title="Chưa có dữ liệu xếp hạng ngành"
        description="Cần dữ liệu báo cáo thường niên mới nhất trong nhóm ngành để tính bách phân vị."
      />
    );
  }

  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 12, bottom: 4 }}>
          <CartesianGrid strokeDasharray="2 2" stroke="var(--border-subtle)" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            unit="%"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
          />
          <YAxis
            type="category"
            dataKey="metric"
            width={175}
            tick={{ fill: 'var(--text-primary)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <ReferenceLine x={50} stroke="var(--border-strong)" strokeDasharray="3 3" />
          <Tooltip
            formatter={(val: unknown) => [`Bách phân vị thứ ${Number(val).toFixed(1)}`, 'Xếp hạng ngành']}
            contentStyle={TOOLTIP_STYLE}
          />
          <Bar dataKey="percentile" radius={[0, 2, 2, 0]} maxBarSize={16} isAnimationActive={false}>
            {data.map((row) => (
              <Cell
                key={row.metric}
                fill={
                  row.percentile >= 65
                    ? 'var(--risk-low-fg)'
                    : row.percentile >= 35
                      ? 'var(--chart-1)'
                      : 'var(--chart-3)'
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
