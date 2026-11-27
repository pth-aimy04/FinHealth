import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  HelpCircle,
  Minus,
} from 'lucide-react';
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import {
  PILLAR_SHORT_LABELS_VI,
  formatScoreVi,
  type ContextualMetricView,
  type MetricStatus,
  type PeerContextView,
  type PillarKey,
  type PillarStatus,
  type PillarsOverviewView,
} from './types';

export interface FivePillarsSectionProps {
  pillars: PillarsOverviewView;
  peerContext?: PeerContextView | null;
  mode?: 'full' | 'overview' | 'table';
}

const PILLAR_STATUS_META: Record<
  PillarStatus,
  { label: string; fg: string; bg: string }
> = {
  STRONG: { label: 'Mạnh', fg: 'var(--risk-low-fg)', bg: 'var(--risk-low-bg)' },
  ADEQUATE: { label: 'Đạt chuẩn', fg: '#1D4ED8', bg: 'rgba(37, 99, 235, 0.12)' },
  WEAK: { label: 'Yếu', fg: 'var(--risk-high-fg)', bg: 'var(--risk-high-bg)' },
  CRITICAL: {
    label: 'Nghiêm trọng',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
  },
  UNAVAILABLE: {
    label: 'Thiếu dữ liệu',
    fg: 'var(--risk-neutral-fg)',
    bg: 'var(--risk-neutral-bg)',
  },
};

const METRIC_STATUS_META: Record<
  MetricStatus,
  { label: string; fg: string; bg: string }
> = {
  GOOD: { label: 'Tốt', fg: 'var(--risk-low-fg)', bg: 'var(--risk-low-bg)' },
  NEUTRAL: {
    label: 'Trung tính',
    fg: 'var(--risk-neutral-fg)',
    bg: 'var(--risk-neutral-bg)',
  },
  WARNING: {
    label: 'Cần lưu ý',
    fg: 'var(--risk-medium-fg)',
    bg: 'var(--risk-medium-bg)',
  },
  CRITICAL: {
    label: 'Nghiêm trọng',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
  },
  UNAVAILABLE: {
    label: 'Thiếu dữ liệu',
    fg: 'var(--risk-neutral-fg)',
    bg: 'var(--risk-neutral-bg)',
  },
};

function formatYoYDelta(metric: ContextualMetricView): {
  text: string;
  tone: 'positive' | 'negative' | 'neutral';
} {
  const delta = metric.yoy_change;
  if (delta === null || delta === undefined || !Number.isFinite(delta)) {
    return { text: '—', tone: 'neutral' };
  }
  const sign = delta > 0 ? '+' : '';
  let text: string;
  if (metric.unit === 'percent') {
    text = `${sign}${(delta * 100).toLocaleString('vi-VN', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })} đpt`;
  } else if (metric.unit === 'days') {
    text = `${sign}${delta.toLocaleString('vi-VN', {
      maximumFractionDigits: 1,
    })} ngày`;
  } else {
    text = `${sign}${delta.toLocaleString('vi-VN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  if (Math.abs(delta) < 1e-6) {
    return { text, tone: 'neutral' };
  }
  const isFavorable =
    metric.good_direction === 'higher' ? delta > 0 : delta < 0;
  return { text, tone: isFavorable ? 'positive' : 'negative' };
}

export function FivePillarsSection({
  pillars,
  peerContext,
  mode = 'full',
}: FivePillarsSectionProps) {
  const [selectedPillar, setSelectedPillar] = useState<PillarKey | 'all'>('all');
  const [openTooltipKey, setOpenTooltipKey] = useState<string | null>(null);

  const radarData = useMemo(
    () =>
      pillars.pillars.map((p) => ({
        pillar: PILLAR_SHORT_LABELS_VI[p.key] ?? p.label_vi,
        fullLabel: p.label_vi,
        score: p.score !== null && Number.isFinite(p.score) ? Number(p.score.toFixed(1)) : 0,
        hasScore: p.score !== null && Number.isFinite(p.score),
      })),
    [pillars.pillars],
  );

  const visiblePillars = useMemo(() => {
    if (selectedPillar === 'all') return pillars.pillars;
    return pillars.pillars.filter((p) => p.key === selectedPillar);
  }, [pillars.pillars, selectedPillar]);

  const totalMetricCount = useMemo(
    () => pillars.pillars.reduce((acc, p) => acc + p.metrics.length, 0),
    [pillars.pillars],
  );

  const showOverview = mode === 'full' || mode === 'overview';
  const showTable = mode === 'full' || mode === 'table';

  return (
    <div className="space-y-5">
      {pillars.is_negative_equity ? (
        <div
          role="alert"
          className="flex items-start gap-2.5 p-3.5 rounded-[8px] border text-xs"
          style={{
            backgroundColor: 'var(--risk-critical-bg)',
            color: 'var(--risk-critical-fg)',
            borderColor: 'rgba(190, 18, 60, 0.25)',
          }}
        >
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <strong className="font-semibold">Cảnh báo âm Vốn chủ sở hữu:</strong>{' '}
            Doanh nghiệp đang có vốn chủ sở hữu âm. Các chỉ số cơ cấu vốn và hiệu quả trên vốn chủ bị áp mức phạt nghiêm trọng (0 điểm).
          </div>
        </div>
      ) : null}

      {showOverview ? (
        <section
          className="surface overflow-hidden"
          aria-label="Tổng quan 5 trụ cột sức khỏe tài chính"
        >
          <div className="px-5 py-3.5 border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text-primary)]">
                5 Trụ cột Sức khỏe Tài chính
              </h2>
              <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                Đánh giá toàn diện từ thanh khoản ngắn hạn, cơ cấu vốn, sinh lời, hiệu quả vận hành đến sức mạnh dòng tiền.
              </p>
            </div>
            {peerContext?.summary_label_vi ? (
              <span className="text-xs px-2.5 py-1 rounded-full bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
                {peerContext.summary_label_vi}
              </span>
            ) : null}
          </div>

          <div className="p-5 grid grid-cols-1 lg:grid-cols-12 gap-5 items-center">
            {/* Radar Chart */}
            <div className="lg:col-span-5 h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="72%" data={radarData}>
                  <PolarGrid stroke="var(--border-strong)" strokeDasharray="3 3" />
                  <PolarAngleAxis
                    dataKey="pillar"
                    tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                  />
                  <PolarRadiusAxis
                    angle={90}
                    domain={[0, 100]}
                    tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                    tickCount={5}
                  />
                  <Radar
                    name="Điểm trụ cột"
                    dataKey="score"
                    stroke="var(--accent-primary)"
                    fill="var(--accent-primary)"
                    fillOpacity={0.22}
                    strokeWidth={2}
                  />
                  <Tooltip
                    formatter={(value: number) => [`${formatScoreVi(value, 1)} / 100`, 'Điểm']}
                    contentStyle={{
                      backgroundColor: 'var(--bg-surface)',
                      borderColor: 'var(--border-strong)',
                      borderRadius: '8px',
                      fontSize: '12px',
                      color: 'var(--text-primary)',
                    }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* 5 Pillar Breakdown Cards */}
            <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-3">
              {pillars.pillars.map((pillar) => {
                const statusMeta = PILLAR_STATUS_META[pillar.status];
                const pct =
                  pillar.score !== null && Number.isFinite(pillar.score)
                    ? Math.max(0, Math.min(100, pillar.score))
                    : 0;
                return (
                  <div
                    key={pillar.key}
                    className="p-3.5 rounded-[8px] border border-[var(--border-subtle)] bg-[var(--bg-subtle)]/40 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="text-xs font-semibold text-[var(--text-primary)] leading-snug">
                          {pillar.label_vi}
                        </h3>
                        <div className="text-[11px] text-[var(--text-muted)]">
                          Trọng số {(pillar.weight * 100).toFixed(0)}% · {pillar.observed_metrics}/
                          {pillar.total_metrics} chỉ số
                        </div>
                      </div>
                      <span
                        className="px-2 py-0.5 rounded-full text-[11px] font-medium shrink-0"
                        style={{ color: statusMeta.fg, backgroundColor: statusMeta.bg }}
                      >
                        {statusMeta.label}
                      </span>
                    </div>

                    <div className="flex items-center gap-2.5">
                      <div className="flex-1 h-2 rounded-full bg-[var(--bg-subtle)] overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: statusMeta.fg,
                          }}
                        />
                      </div>
                      <span className="num text-sm font-bold text-[var(--text-primary)] w-11 text-right">
                        {formatScoreVi(pillar.score, 1)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      ) : null}

      {showTable ? (
        <section
          className="surface overflow-hidden"
          aria-label="Bảng chi tiết 20 chỉ số tài chính"
        >
          <div className="px-5 py-3.5 border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text-primary)]">
                Chi tiết {totalMetricCount} Chỉ số Tài chính Cốt lõi
              </h2>
              <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                Mọi chỉ số đều đi kèm ngưỡng tham chiếu, biến động kỳ trước (YoY) và đối chiếu vị thế ngành.
              </p>
            </div>

            {/* Pillar Filter Tabs */}
            <div
              className="flex flex-wrap items-center gap-1.5"
              role="tablist"
              aria-label="Lọc chỉ số theo trụ cột"
            >
              <button
                type="button"
                role="tab"
                aria-selected={selectedPillar === 'all'}
                onClick={() => setSelectedPillar('all')}
                className={`px-2.5 py-1 rounded-[6px] text-xs font-medium cursor-pointer transition-colors ${
                  selectedPillar === 'all'
                    ? 'bg-[var(--accent-primary)] text-[var(--accent-ink)]'
                    : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                Tất cả ({totalMetricCount})
              </button>
              {pillars.pillars.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  role="tab"
                  aria-selected={selectedPillar === p.key}
                  onClick={() => setSelectedPillar(p.key)}
                  className={`px-2.5 py-1 rounded-[6px] text-xs font-medium cursor-pointer transition-colors ${
                    selectedPillar === p.key
                      ? 'bg-[var(--accent-primary)] text-[var(--accent-ink)]'
                      : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {PILLAR_SHORT_LABELS_VI[p.key]}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50 text-[var(--text-secondary)]">
                  <th className="py-2.5 px-4 font-semibold">Chỉ số tài chính</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Giá trị</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Ngưỡng tham chiếu</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Biến động YoY</th>
                  <th className="py-2.5 px-3 font-semibold">Vị thế ngành</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {visiblePillars.map((pillar) => (
                  <PillarMetricRows
                    key={pillar.key}
                    pillarLabel={pillar.label_vi}
                    metrics={pillar.metrics}
                    showGroupHeader={selectedPillar === 'all'}
                    openTooltipKey={openTooltipKey}
                    onToggleTooltip={(key) =>
                      setOpenTooltipKey((prev) => (prev === key ? null : key))
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function PillarMetricRows({
  pillarLabel,
  metrics,
  showGroupHeader,
  openTooltipKey,
  onToggleTooltip,
}: {
  pillarLabel: string;
  metrics: ContextualMetricView[];
  showGroupHeader: boolean;
  openTooltipKey: string | null;
  onToggleTooltip: (key: string) => void;
}) {
  return (
    <>
      {showGroupHeader ? (
        <tr className="bg-[var(--bg-subtle)]/35">
          <td
            colSpan={6}
            className="py-2 px-4 text-[11px] font-semibold uppercase tracking-wide text-[var(--text-secondary)]"
          >
            {pillarLabel}
          </td>
        </tr>
      ) : null}
      {metrics.map((metric) => {
        const statusMeta = METRIC_STATUS_META[metric.status];
        const yoy = formatYoYDelta(metric);
        const tooltipOpen = openTooltipKey === metric.key;

        return (
          <tr
            key={metric.key}
            className="hover:bg-[var(--bg-hover)]/45 transition-colors align-top"
          >
            <td className="py-3 px-4 max-w-[300px]">
              <div className="flex items-start gap-1.5">
                <span className="font-medium text-[var(--text-primary)] leading-snug">
                  {metric.label_vi}
                </span>
                <button
                  type="button"
                  onClick={() => onToggleTooltip(metric.key)}
                  aria-expanded={tooltipOpen}
                  aria-label={`Giải thích chỉ số ${metric.label_vi}`}
                  title={metric.tooltip_vi}
                  className="text-[var(--text-muted)] hover:text-[var(--accent-primary)] shrink-0 mt-0.5 cursor-pointer"
                >
                  <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
              {tooltipOpen ? (
                <p className="mt-1.5 p-2 rounded-[6px] bg-[var(--bg-subtle)] text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  {metric.tooltip_vi}
                </p>
              ) : null}
            </td>

            <td className="py-3 px-3 text-right num font-semibold text-[var(--text-primary)] whitespace-nowrap">
              {metric.formatted_value_vi}
            </td>

            <td className="py-3 px-3 text-right num text-[var(--text-secondary)] whitespace-nowrap">
              {metric.reference_range_vi}
            </td>

            <td className="py-3 px-3 text-right whitespace-nowrap">
              <span
                className="inline-flex items-center justify-end gap-0.5 num font-medium"
                style={{
                  color:
                    yoy.tone === 'positive'
                      ? 'var(--risk-low-fg)'
                      : yoy.tone === 'negative'
                        ? 'var(--risk-critical-fg)'
                        : 'var(--text-muted)',
                }}
              >
                {yoy.tone === 'positive' ? (
                  <ArrowUp className="h-3 w-3" aria-hidden="true" />
                ) : yoy.tone === 'negative' ? (
                  <ArrowDown className="h-3 w-3" aria-hidden="true" />
                ) : (
                  <Minus className="h-3 w-3" aria-hidden="true" />
                )}
                <span>{yoy.text}</span>
              </span>
            </td>

            <td className="py-3 px-3 text-[var(--text-secondary)]">
              {metric.peer_position ? (
                <div className="space-y-0.5">
                  <div className="font-medium text-[var(--text-primary)]">
                    {metric.peer_position.position_label_vi}
                  </div>
                  {metric.peer_position.n_observed > 0 &&
                  metric.peer_position.percentile !== null ? (
                    <div className="text-[11px] text-[var(--text-muted)] num">
                      Phân vị {Math.round(metric.peer_position.percentile)}% (n=
                      {metric.peer_position.n_observed})
                    </div>
                  ) : null}
                </div>
              ) : (
                <span className="text-[var(--text-muted)]">—</span>
              )}
            </td>

            <td className="py-3 px-4 text-right whitespace-nowrap">
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                style={{ color: statusMeta.fg, backgroundColor: statusMeta.bg }}
              >
                {statusMeta.label}
              </span>
            </td>
          </tr>
        );
      })}
    </>
  );
}
