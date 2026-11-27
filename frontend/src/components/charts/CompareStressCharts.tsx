import { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type {
  CompanyComparisonResponse,
  StressSimulationResponse,
} from '@/types/api';
import { EmptyState } from '@/components/ui/Primitives';

const SERIES_COLORS = ['#0F766E', '#1D4ED8', '#D97706', '#DC2626', '#475569'];

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--bg-surface)',
  border: '1px solid var(--border-strong)',
  borderRadius: '4px',
  fontSize: '12px',
};

type CompareMetricKey = 'roa' | 'debt_ratio' | 'ocf_ratio' | 'operating_margin' | 'altman_z_score';

const COMPARE_METRICS: Array<{ key: CompareMetricKey; label: string; isPct: boolean }> = [
  { key: 'roa', label: 'ROA (%)', isPct: true },
  { key: 'debt_ratio', label: 'Tỷ lệ nợ (%)', isPct: true },
  { key: 'ocf_ratio', label: 'Tỷ lệ OCF (%)', isPct: true },
  { key: 'operating_margin', label: 'Biên hoạt động (%)', isPct: true },
  { key: 'altman_z_score', label: 'Altman Z-Score', isPct: false },
];

/** Biểu đồ xu hướng lịch sử nhiều năm giữa các doanh nghiệp so sánh. */
export function CompareTrendChart({ data }: { data: CompanyComparisonResponse }) {
  const [metric, setMetric] = useState<CompareMetricKey>('roa');
  const metricDef = COMPARE_METRICS.find((m) => m.key === metric) ?? COMPARE_METRICS[0];

  const { chartData, seriesKeys } = useMemo(() => {
    const yearMap = new Map<number, Record<string, number | null>>();
    const keys: Array<{ key: string; label: string }> = [];

    for (const company of data.companies) {
      const id = company.ticker ?? company.cik;
      const series = data.historical_series[company.cik] ?? data.historical_series[id] ?? [];
      keys.push({ key: id, label: id });
      for (const pt of series) {
        const row = yearMap.get(pt.fiscal_year) ?? { year: pt.fiscal_year };
        const raw = pt[metric];
        row[id] =
          typeof raw === 'number' && Number.isFinite(raw)
            ? Number((metricDef.isPct ? raw * 100 : raw).toFixed(2))
            : null;
        yearMap.set(pt.fiscal_year, row);
      }
    }

    const sorted = Array.from(yearMap.entries())
      .sort(([a], [b]) => a - b)
      .map(([, row]) => row);
    return { chartData: sorted, seriesKeys: keys };
  }, [data, metric, metricDef.isPct]);

  if (chartData.length === 0) {
    return (
      <EmptyState
        title="Chưa có chuỗi lịch sử nhiều năm"
        description="Cần dữ liệu báo cáo thường niên để vẽ biểu đồ đối chiếu xu hướng."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {COMPARE_METRICS.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setMetric(m.key)}
            className={`px-2.5 py-1 text-xs rounded-[4px] border cursor-pointer transition-colors ${
              metric === m.key
                ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] border-[var(--accent-primary)]/40 font-medium'
                : 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 20, left: -4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
            <XAxis dataKey="year" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <YAxis
              unit={metricDef.isPct ? '%' : ''}
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: '11px' }} />
            {seriesKeys.map((s, idx) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Biểu đồ so sánh các tỷ số tài chính cốt lõi: Cơ sở vs Sau cú sốc Stress Test. */
export function StressComparisonChart({ result }: { result: StressSimulationResponse }) {
  const rows = useMemo(() => {
    const b = result.baseline.metrics;
    const s = result.stressed.metrics;
    const items: Array<{ label: string; baseline: number | null; stressed: number | null }> = [
      {
        label: 'ROA (%)',
        baseline: typeof b.roa === 'number' ? Number((b.roa * 100).toFixed(2)) : null,
        stressed: typeof s.roa === 'number' ? Number((s.roa * 100).toFixed(2)) : null,
      },
      {
        label: 'Biên hoạt động (%)',
        baseline: typeof b.operating_margin === 'number' ? Number((b.operating_margin * 100).toFixed(2)) : null,
        stressed: typeof s.operating_margin === 'number' ? Number((s.operating_margin * 100).toFixed(2)) : null,
      },
      {
        label: 'Tỷ lệ nợ (%)',
        baseline: typeof b.debt_ratio === 'number' ? Number((b.debt_ratio * 100).toFixed(2)) : null,
        stressed: typeof s.debt_ratio === 'number' ? Number((s.debt_ratio * 100).toFixed(2)) : null,
      },
      {
        label: 'Tỷ lệ OCF (%)',
        baseline: typeof b.ocf_ratio === 'number' ? Number((b.ocf_ratio * 100).toFixed(2)) : null,
        stressed: typeof s.ocf_ratio === 'number' ? Number((s.ocf_ratio * 100).toFixed(2)) : null,
      },
    ];
    return items.filter((item) => item.baseline !== null || item.stressed !== null);
  }, [result]);

  if (rows.length === 0) return null;

  return (
    <div className="h-[240px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: 'var(--text-primary)', fontSize: 11 }} />
          <YAxis unit="%" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
          <ReferenceLine y={0} stroke="var(--border-strong)" />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: '11px' }} />
          <Bar dataKey="baseline" name="Kịch bản cơ sở" fill="#0F766E" radius={[2, 2, 0, 0]} maxBarSize={32} />
          <Bar dataKey="stressed" name="Sau cú sốc" fill="#DC2626" radius={[2, 2, 0, 0]} maxBarSize={32} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Biểu đồ đối chiếu các mô hình phân loại ML từ evaluation_report. */
export function ModelBenchmarkChart({ report }: { report: Record<string, unknown> }) {
  const rows = useMemo(() => {
    const out: Array<{ model: string; roc_auc: number | null; pr_auc: number | null; f1: number | null }> = [];
    for (const [key, val] of Object.entries(report)) {
      if (!key.startsWith('classification_') || !val || typeof val !== 'object') continue;
      const rec = val as Record<string, unknown>;
      const roc = typeof rec.roc_auc === 'number' ? Number((rec.roc_auc * 100).toFixed(1)) : null;
      const pr = typeof rec.pr_auc === 'number' ? Number((rec.pr_auc * 100).toFixed(1)) : null;
      const f1 = typeof rec.f1 === 'number' ? Number((rec.f1 * 100).toFixed(1)) : null;
      if (roc !== null || pr !== null || f1 !== null) {
        out.push({
          model: key.replace('classification_', '').replace(/_/g, ' ').toUpperCase(),
          roc_auc: roc,
          pr_auc: pr,
          f1,
        });
      }
    }
    return out;
  }, [report]);

  if (rows.length === 0) return null;

  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
          <XAxis dataKey="model" tick={{ fill: 'var(--text-primary)', fontSize: 11 }} />
          <YAxis domain={[0, 100]} unit="%" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: '11px' }} />
          <Bar dataKey="roc_auc" name="ROC-AUC (%)" fill="#0F766E" radius={[2, 2, 0, 0]} maxBarSize={28} />
          <Bar dataKey="pr_auc" name="PR-AUC (%)" fill="#1D4ED8" radius={[2, 2, 0, 0]} maxBarSize={28} />
          <Bar dataKey="f1" name="Điểm F1 (%)" fill="#D97706" radius={[2, 2, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
