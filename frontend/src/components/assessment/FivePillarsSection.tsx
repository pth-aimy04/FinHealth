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
  { label: string; fg: string; bg: string; border: string }
> = {
  STRONG: {
    label: 'Mạnh',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
    border: 'var(--risk-low-border)',
  },
  ADEQUATE: {
    label: 'Đạt chuẩn',
    fg: 'var(--risk-stable-fg)',
    bg: 'var(--risk-stable-bg)',
    border: 'var(--risk-stable-border)',
  },
  WEAK: {
    label: 'Yếu',
    fg: 'var(--risk-high-fg)',
    bg: 'var(--risk-high-bg)',
    border: 'var(--risk-high-border)',
  },
  CRITICAL: {
    label: 'Nghiêm trọng',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
    border: 'var(--risk-critical-border)',
  },
  UNAVAILABLE: {
    label: 'Thiếu dữ liệu',
    fg: 'var(--risk-neutral-fg)',
    bg: 'var(--risk-neutral-bg)',
    border: 'var(--risk-neutral-border)',
  },
};

const METRIC_STATUS_META: Record<
  MetricStatus,
  { label: string; fg: string; bg: string; border: string }
> = {
  GOOD: {
    label: 'Tốt',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
    border: 'var(--risk-low-border)',
  },
  NEUTRAL: {
    label: 'Trung tính',
    fg: 'var(--risk-neutral-fg)',
    bg: 'var(--risk-neutral-bg)',
    border: 'var(--risk-neutral-border)',
  },
  WARNING: {
    label: 'Cần lưu ý',
    fg: 'var(--risk-medium-fg)',
    bg: 'var(--risk-medium-bg)',
    border: 'var(--risk-medium-border)',
  },
  CRITICAL: {
    label: 'Nghiêm trọng',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
    border: 'var(--risk-critical-border)',
  },
  UNAVAILABLE: {
    label: 'Thiếu dữ liệu',
    fg: 'var(--risk-neutral-fg)',
    bg: 'var(--risk-neutral-bg)',
    border: 'var(--risk-neutral-border)',
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
          className="flex items-start gap-2.5 p-3.5 rounded-[3px] border text-xs"
          style={{
            backgroundColor: 'var(--risk-critical-bg)',
            color: 'var(--risk-critical-fg)',
            borderColor: 'var(--risk-critical-border)',
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
          <div className="px-5 py-3 bg-[var(--bg-header)] border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-[14px] font-bold tracking-[-0.01em] text-[var(--text-primary)] m-0">
                5 Trụ cột Sức khỏe Tài chính
              </h2>
              <p className="mt-0.5 text-xs text-[var(--text-secondary)] m-0">
                Đánh giá toàn diện từ thanh khoản ngắn hạn, cơ cấu vốn, sinh lời, hiệu quả vận hành đến sức mạnh dòng tiền.
              </p>
            </div>
            {peerContext?.summary_label_vi ? (
              <span className="text-[11px] font-semibold px-2.5 py-1 rounded-[2px] bg-[var(--bg-surface)] text-[var(--text-secondary)] border border-[var(--border-strong)]">
                {peerContext.summary_label_vi}
              </span>
            ) : null}
          </div>

          {/* Flush Split: Radar Left + 5-Row Hairline Pillar Ledger Right (Zero Nested Cards) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-[var(--border-subtle)]">
            <div className="lg:col-span-5 min-w-0 p-5 flex items-center justify-center">
              <div className="h-[270px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="72%" data={radarData}>
                    <PolarGrid stroke="var(--border-strong)" strokeDasharray="2 2" />
                    <PolarAngleAxis
                      dataKey="pillar"
                      tick={{ fill: 'var(--text-primary)', fontSize: 12, fontWeight: 600 }}
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
                      stroke="var(--chart-1)"
                      fill="var(--chart-1)"
                      fillOpacity={0.18}
                      strokeWidth={2}
                      isAnimationActive={false}
                    />
                    <Tooltip
                      formatter={(value: number) => [`${formatScoreVi(value, 1)} / 100`, 'Điểm']}
                      contentStyle={{
                        backgroundColor: 'var(--bg-surface)',
                        borderColor: 'var(--border-strong)',
                        borderRadius: '3px',
                        fontSize: '12px',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="lg:col-span-7 min-w-0 divide-y divide-[var(--border-subtle)]">
              {pillars.pillars.map((pillar) => {
                const statusMeta = PILLAR_STATUS_META[pillar.status];
                const pct =
                  pillar.score !== null && Number.isFinite(pillar.score)
                    ? Math.max(0, Math.min(100, pillar.score))
                    : 0;
                return (
                  <div
                    key={pillar.key}
                    className="px-5 py-3.5 hover:bg-[var(--bg-hover)]/45 transition-colors"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="text-[13px] font-bold text-[var(--text-primary)] leading-snug m-0">
                          {pillar.label_vi}
                        </h3>
                        <div className="text-[11px] text-[var(--text-muted)] num">
                          Trọng số {(pillar.weight * 100).toFixed(0)}% · {pillar.observed_metrics}/
                          {pillar.total_metrics} chỉ số ghi nhận
                        </div>
                      </div>
                      <div className="flex items-center gap-2.5 shrink-0">
                        <span className="num text-base font-bold text-[var(--text-primary)]">
                          {formatScoreVi(pillar.score, 1)}
                        </span>
                        <span
                          className="px-2 py-0.5 rounded-[2px] border text-[11px] font-semibold"
                          style={{
                            color: statusMeta.fg,
                            backgroundColor: statusMeta.bg,
                            borderColor: statusMeta.border,
                          }}
                        >
                          {statusMeta.label}
                        </span>
                      </div>
                    </div>

                    <div className="mt-2 h-1.5 w-full rounded-[1px] bg-[var(--bg-subtle)] overflow-hidden">
                      <div
                        className="h-full transition-all duration-300"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: statusMeta.fg,
                        }}
                      />
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
          className="surface-ruled overflow-hidden"
          aria-label="Bảng chi tiết 20 chỉ số tài chính"
        >
          <div className="px-5 py-3 bg-[var(--bg-header)] border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-[14px] font-bold tracking-[-0.01em] text-[var(--text-primary)] m-0">
                Chi tiết {totalMetricCount} Chỉ số Tài chính Cốt lõi
              </h2>
              <p className="mt-0.5 text-xs text-[var(--text-secondary)] m-0">
                Mọi chỉ số đều đi kèm ngưỡng tham chiếu, biến động kỳ trước (YoY) và đối chiếu vị thế ngành.
              </p>
            </div>

            {/* Docked Institutional Filter Tabs */}
            <div
              className="flex flex-wrap items-center gap-1"
              role="tablist"
              aria-label="Lọc chỉ số theo trụ cột"
            >
              <button
                type="button"
                role="tab"
                aria-selected={selectedPillar === 'all'}
                onClick={() => setSelectedPillar('all')}
                className={`px-2.5 py-1 rounded-[2px] text-xs font-semibold border cursor-pointer transition-colors ${
                  selectedPillar === 'all'
                    ? 'bg-[var(--accent-primary)] text-[var(--accent-ink)] border-[var(--accent-primary)]'
                    : 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-strong)] hover:text-[var(--text-primary)]'
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
                  className={`px-2.5 py-1 rounded-[2px] text-xs font-semibold border cursor-pointer transition-colors ${
                    selectedPillar === p.key
                      ? 'bg-[var(--accent-primary)] text-[var(--accent-ink)] border-[var(--accent-primary)]'
                      : 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-strong)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {PILLAR_SHORT_LABELS_VI[p.key]}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Chỉ số tài chính</th>
                  <th className="text-right">Giá trị</th>
                  <th className="text-right">Ngưỡng tham chiếu</th>
                  <th className="text-right">Biến động YoY</th>
                  <th>Vị thế ngành</th>
                  <th className="text-right">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
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
        <tr className="!bg-[var(--bg-subtle)]">
          <td
            colSpan={6}
            className="!py-2 !px-4 text-[11px] font-bold uppercase tracking-[0.06em] text-[var(--text-primary)]"
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
          <tr key={metric.key} className="align-top">
            <td className="max-w-[320px]">
              <div className="flex items-start gap-1.5">
                <span className="font-semibold text-[var(--text-primary)] leading-snug">
                  {metric.label_vi}
                </span>
                <button
                  type="button"
                  onClick={() => onToggleTooltip(metric.key)}
                  aria-expanded={tooltipOpen}
                  aria-label={`Giải thích chỉ số ${metric.label_vi}`}
                  title={metric.tooltip_vi}
                  className="text-[var(--text-muted)] hover:text-[var(--accent-primary)] shrink-0 mt-0.5 cursor-pointer bg-transparent border-0 p-0"
                >
                  <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
              {tooltipOpen ? (
                <p className="mt-1.5 p-2.5 rounded-[2px] bg-[var(--bg-header)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] leading-relaxed m-0">
                  {metric.tooltip_vi}
                </p>
              ) : null}
            </td>

            <td className="text-right num font-bold text-[var(--text-primary)] whitespace-nowrap">
              {metric.formatted_value_vi}
            </td>

            <td className="text-right num text-[var(--text-secondary)] whitespace-nowrap">
              {metric.reference_range_vi}
            </td>

            <td className="text-right whitespace-nowrap">
              <span
                className="inline-flex items-center justify-end gap-0.5 num font-semibold"
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

            <td className="text-[var(--text-secondary)]">
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

            <td className="text-right whitespace-nowrap">
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-[2px] border text-[11px] font-semibold"
                style={{
                  color: statusMeta.fg,
                  backgroundColor: statusMeta.bg,
                  borderColor: statusMeta.border,
                }}
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
