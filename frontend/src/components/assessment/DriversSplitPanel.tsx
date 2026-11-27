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

function DriverLedgerRow({
  driver,
  tone,
}: {
  driver: BusinessDriverView;
  tone: 'strength' | 'bottleneck';
}) {
  const isStrength = tone === 'strength';
  const accentFg = isStrength ? 'var(--risk-low-fg)' : 'var(--risk-critical-fg)';
  const accentBg = isStrength ? 'var(--risk-low-bg)' : 'var(--risk-critical-bg)';
  const accentBorder = isStrength ? 'var(--risk-low-border)' : 'var(--risk-critical-border)';
  const clampedShare = Math.max(0, Math.min(100, driver.impact_share_pct));

  return (
    <article
      className="px-5 py-3.5 space-y-2 hover:bg-[var(--bg-hover)]/45 transition-colors"
      aria-label={driver.label_vi}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex flex-wrap items-center gap-2">
          <h4 className="text-[13px] font-bold text-[var(--text-primary)] leading-snug m-0">
            {driver.label_vi}
          </h4>
          <span className="text-[10px] font-semibold uppercase tracking-[0.04em] px-1.5 py-0.5 rounded-[2px] bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
            {PILLAR_SHORT_LABELS_VI[driver.pillar]}
          </span>
        </div>
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] border text-[11px] font-semibold shrink-0"
          style={{
            color: accentFg,
            backgroundColor: accentBg,
            borderColor: accentBorder,
          }}
        >
          {isStrength ? (
            <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
          ) : (
            <ArrowDownRight className="h-3 w-3" aria-hidden="true" />
          )}
          <span>{driver.impact_strength_label_vi}</span>
        </span>
      </div>

      <p className="text-[13px] font-medium text-[var(--text-primary)] leading-snug m-0">
        {driver.headline_vi}
      </p>
      {driver.detail_vi ? (
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed m-0">
          {driver.detail_vi}
        </p>
      ) : null}

      <div className="pt-1.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-4 text-[var(--text-secondary)]">
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

        <div className="flex items-center gap-2 min-w-[144px]">
          <span className="text-[11px] text-[var(--text-muted)]">Tỷ trọng:</span>
          <div className="w-16 h-1.5 rounded-[1px] bg-[var(--bg-subtle)] overflow-hidden">
            <div
              className="h-full"
              style={{
                width: `${clampedShare}%`,
                backgroundColor: accentFg,
              }}
            />
          </div>
          <span className="num text-xs font-semibold text-[var(--text-primary)]">
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
    <section className="surface-ruled overflow-hidden" aria-label={title}>
      <div className="px-5 py-3 bg-[var(--bg-header)] border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[14px] font-bold tracking-[-0.01em] text-[var(--text-primary)] m-0">
            {title}
          </h2>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)] m-0">
            Phân tách các yếu tố tài chính cốt lõi đang nâng đỡ hoặc gây áp lực lên mức độ an toàn của doanh nghiệp.
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-semibold">
          <span className="inline-flex items-center gap-1.5 text-[var(--risk-low-fg)]">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="num">{strengths.length}</span> Điểm tựa
          </span>
          <span className="inline-flex items-center gap-1.5 text-[var(--risk-critical-fg)]">
            <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="num">{bottlenecks.length}</span> Điểm nghẽn
          </span>
        </div>
      </div>

      {/* Flush 2-Column Credit Balance Sheet Ledger (Zero Nested Cards) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-[var(--border-subtle)]">
        {/* Left Ledger: Strengths */}
        <div className="flex flex-col">
          <div
            className="flex items-center gap-2 px-5 py-2.5 border-b border-[var(--border-subtle)] text-xs font-bold uppercase tracking-[0.04em]"
            style={{
              backgroundColor: 'var(--risk-low-bg)',
              color: 'var(--risk-low-fg)',
            }}
          >
            <ShieldCheck className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>Điểm Tựa Tài Chính (Giảm rủi ro)</span>
          </div>

          {strengths.length > 0 ? (
            <div className="divide-y divide-[var(--border-subtle)]">
              {strengths.map((item) => (
                <DriverLedgerRow key={item.factor_code} driver={item} tone="strength" />
              ))}
            </div>
          ) : (
            <div className="px-5 py-8 text-xs text-[var(--text-muted)] text-center">
              Chưa ghi nhận điểm tựa tài chính nổi bật trong kỳ này.
            </div>
          )}
        </div>

        {/* Right Ledger: Bottlenecks */}
        <div className="flex flex-col">
          <div
            className="flex items-center gap-2 px-5 py-2.5 border-b border-[var(--border-subtle)] text-xs font-bold uppercase tracking-[0.04em]"
            style={{
              backgroundColor: 'var(--risk-critical-bg)',
              color: 'var(--risk-critical-fg)',
            }}
          >
            <ShieldAlert className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>Điểm Nghẽn Tài Chính (Đẩy rủi ro tăng)</span>
          </div>

          {bottlenecks.length > 0 ? (
            <div className="divide-y divide-[var(--border-subtle)]">
              {bottlenecks.map((item) => (
                <DriverLedgerRow key={item.factor_code} driver={item} tone="bottleneck" />
              ))}
            </div>
          ) : (
            <div className="px-5 py-8 text-xs text-[var(--text-muted)] text-center">
              Không ghi nhận điểm nghẽn rủi ro đáng kể trong kỳ này.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
