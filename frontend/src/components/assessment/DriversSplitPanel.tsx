import { ArrowDownRight, ArrowUpRight, ShieldAlert, ShieldCheck } from 'lucide-react';
import {
  PILLAR_SHORT_LABELS_VI,
  formatPctVi,
  type BusinessDriverView,
  type DriversSplitView,
} from './types';

export interface DriversSplitPanelProps {
  drivers: DriversSplitView;
  title?: string;
}

function DriverCard({
  driver,
  tone,
}: {
  driver: BusinessDriverView;
  tone: 'strength' | 'bottleneck';
}) {
  const isStrength = tone === 'strength';
  const accentFg = isStrength ? 'var(--risk-low-fg)' : 'var(--risk-critical-fg)';
  const accentBg = isStrength ? 'var(--risk-low-bg)' : 'var(--risk-critical-bg)';
  const clampedShare = Math.max(0, Math.min(100, driver.impact_share_pct));

  return (
    <article
      className="p-3.5 rounded-[8px] border border-[var(--border-subtle)] bg-[var(--bg-surface)] space-y-2"
      aria-label={driver.label_vi}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <h4 className="text-sm font-semibold text-[var(--text-primary)] leading-snug">
              {driver.label_vi}
            </h4>
            <span className="text-[11px] px-1.5 py-0.5 rounded bg-[var(--bg-subtle)] text-[var(--text-secondary)]">
              {PILLAR_SHORT_LABELS_VI[driver.pillar]}
            </span>
          </div>
        </div>
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold shrink-0"
          style={{ color: accentFg, backgroundColor: accentBg }}
        >
          {isStrength ? (
            <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
          ) : (
            <ArrowDownRight className="h-3 w-3" aria-hidden="true" />
          )}
          <span>{driver.impact_strength_label_vi}</span>
        </span>
      </div>

      <p className="text-xs font-medium text-[var(--text-primary)] leading-relaxed">
        {driver.headline_vi}
      </p>
      {driver.detail_vi ? (
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {driver.detail_vi}
        </p>
      ) : null}

      {/* Observed Value vs Reference + Relative Impact Share */}
      <div className="pt-1.5 border-t border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <div className="flex flex-wrap items-center gap-3 text-[var(--text-secondary)]">
          <span>
            Thực tế:{' '}
            <strong className="num font-semibold text-[var(--text-primary)]">
              {driver.formatted_value_vi}
            </strong>
          </span>
          <span>
            Tham chiếu:{' '}
            <span className="num text-[var(--text-secondary)]">
              {driver.reference_range_vi}
            </span>
          </span>
        </div>

        <div className="flex items-center gap-2 min-w-[140px]">
          <span className="text-[var(--text-muted)]">Tỷ trọng:</span>
          <div className="w-16 h-1.5 rounded-full bg-[var(--bg-subtle)] overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${clampedShare}%`,
                backgroundColor: accentFg,
              }}
            />
          </div>
          <span className="num font-semibold text-[var(--text-primary)]">
            {formatPctVi(clampedShare, 1, true)}
          </span>
        </div>
      </div>
    </article>
  );
}

export function DriversSplitPanel({
  drivers,
  title = 'Điểm Tựa & Điểm Nghẽn Tài Chính',
}: DriversSplitPanelProps) {
  const strengths = drivers.strengths.slice(0, 5);
  const bottlenecks = drivers.bottlenecks.slice(0, 5);

  return (
    <section className="surface overflow-hidden" aria-label={title}>
      <div className="px-5 py-3.5 border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text-primary)]">
            {title}
          </h2>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            Phân tách các yếu tố tài chính cốt lõi đang nâng đỡ hoặc gây áp lực lên mức độ an toàn của doanh nghiệp.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="inline-flex items-center gap-1 font-medium text-[var(--risk-low-fg)]">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            {strengths.length} Điểm tựa
          </span>
          <span className="inline-flex items-center gap-1 font-medium text-[var(--risk-critical-fg)]">
            <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
            {bottlenecks.length} Điểm nghẽn
          </span>
        </div>
      </div>

      <div className="p-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Green Column: Strengths */}
        <div className="space-y-3">
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-[6px] text-xs font-semibold"
            style={{
              backgroundColor: 'var(--risk-low-bg)',
              color: 'var(--risk-low-fg)',
            }}
          >
            <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>Điểm Tựa Tài Chính (Giảm rủi ro)</span>
          </div>

          {strengths.length > 0 ? (
            <div className="space-y-2.5">
              {strengths.map((item) => (
                <DriverCard key={item.factor_code} driver={item} tone="strength" />
              ))}
            </div>
          ) : (
            <div className="p-4 rounded-[8px] border border-dashed border-[var(--border-strong)] text-xs text-[var(--text-muted)] text-center">
              Chưa ghi nhận điểm tựa tài chính nổi bật trong kỳ này.
            </div>
          )}
        </div>

        {/* Red Column: Bottlenecks */}
        <div className="space-y-3">
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-[6px] text-xs font-semibold"
            style={{
              backgroundColor: 'var(--risk-critical-bg)',
              color: 'var(--risk-critical-fg)',
            }}
          >
            <ShieldAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>Điểm Nghẽn Tài Chính (Đẩy rủi ro tăng)</span>
          </div>

          {bottlenecks.length > 0 ? (
            <div className="space-y-2.5">
              {bottlenecks.map((item) => (
                <DriverCard key={item.factor_code} driver={item} tone="bottleneck" />
              ))}
            </div>
          ) : (
            <div className="p-4 rounded-[8px] border border-dashed border-[var(--border-strong)] text-xs text-[var(--text-muted)] text-center">
              Không ghi nhận điểm nghẽn rủi ro đáng kể trong kỳ này.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
