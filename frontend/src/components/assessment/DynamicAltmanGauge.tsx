import { AlertCircle, Building2, Info } from 'lucide-react';
import {
  formatScoreVi,
  type AltmanVariant,
  type AltmanView,
  type AltmanZone,
} from './types';

export interface DynamicAltmanGaugeProps {
  altman: AltmanView;
}

const VARIANT_META: Record<
  'Z' | "Z'" | "Z''",
  { title: string; subtitle: string; code: string }
> = {
  Z: {
    title: 'Altman Z-Score',
    subtitle: 'Doanh nghiệp sản xuất niêm yết (dùng vốn hóa thị trường)',
    code: 'Z',
  },
  "Z'": {
    title: "Altman Z'-Score",
    subtitle: 'Doanh nghiệp sản xuất chưa niêm yết (dùng vốn chủ sổ sách)',
    code: "Z'",
  },
  "Z''": {
    title: "Altman Z''-Score",
    subtitle: 'Doanh nghiệp thương mại, dịch vụ & phi sản xuất',
    code: "Z''",
  },
};

function normalizeAltmanVariant(variant: AltmanVariant | null): 'Z' | "Z'" | "Z''" {
  if (variant === 'Z') return 'Z';
  if (variant === "Z'" || variant === 'Z_PRIME') return "Z'";
  return "Z''";
}

const ZONE_STYLE: Record<
  AltmanZone,
  { label: string; fg: string; bg: string; border: string }
> = {
  SAFE: {
    label: 'Vùng an toàn',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
    border: 'var(--risk-low-border)',
  },
  GREY: {
    label: 'Vùng xám (cần theo dõi)',
    fg: 'var(--risk-medium-fg)',
    bg: 'var(--risk-medium-bg)',
    border: 'var(--risk-medium-border)',
  },
  DISTRESS: {
    label: 'Vùng nguy hiểm',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
    border: 'var(--risk-critical-border)',
  },
};

const COMPONENT_LABELS_VI: Record<string, string> = {
  X1: 'Vốn lưu động / Tổng tài sản',
  X2: 'Lợi nhuận giữ lại / Tổng tài sản',
  X3: 'EBIT / Tổng tài sản',
  X4: 'Vốn chủ sở hữu / Tổng nợ phải trả',
  X5: 'Doanh thu / Tổng tài sản',
};

export function DynamicAltmanGauge({ altman }: DynamicAltmanGaugeProps) {
  if (!altman.applicable) {
    return (
      <section
        className="surface p-5"
        aria-label="Chỉ số Altman Z-Score không áp dụng"
        data-testid="altman-excluded-card"
      >
        <div className="flex items-start gap-3">
          <div className="h-9 w-9 rounded-[3px] bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center justify-center shrink-0 text-[var(--text-secondary)]">
            <Building2 className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="space-y-1">
            <h2 className="text-[14px] font-bold text-[var(--text-primary)] m-0">
              Chỉ số Altman Z-Score — Không áp dụng
            </h2>
            <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed m-0">
              {altman.unavailable_reason_vi ||
                'Chỉ số Altman Z-Score không áp dụng cho Ngân hàng, Bảo hiểm và Tổ chức tài chính.'}
            </p>
          </div>
        </div>
      </section>
    );
  }

  const variant = normalizeAltmanVariant(altman.variant);
  const variantMeta = VARIANT_META[variant];
  const zoneMeta = altman.zone ? ZONE_STYLE[altman.zone] : null;
  const cutoffLow = altman.cutoff_low ?? 1.1;
  const cutoffHigh = altman.cutoff_high ?? 2.6;

  const minScale = Math.min(0, cutoffLow - 1.2);
  const maxScale = Math.max(cutoffHigh + 1.8, (altman.score ?? cutoffHigh) + 0.6);
  const span = Math.max(0.1, maxScale - minScale);

  const toPct = (val: number) =>
    Math.max(0, Math.min(100, ((val - minScale) / span) * 100));

  const lowPct = toPct(cutoffLow);
  const highPct = toPct(cutoffHigh);
  const scorePct =
    altman.score !== null && Number.isFinite(altman.score)
      ? toPct(altman.score)
      : null;

  const componentEntries = Object.entries(altman.components ?? {}).filter(
    ([, v]) => v !== null && v !== undefined && Number.isFinite(v),
  );

  return (
    <section
      className="surface overflow-hidden"
      aria-label={`Thước đo ${variantMeta.title}`}
      data-testid="altman-gauge-card"
    >
      <div className="px-5 py-3 bg-[var(--bg-header)] border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-[14px] font-bold tracking-[-0.01em] text-[var(--text-primary)] m-0">
              {variantMeta.title}
            </h2>
            <span className="num text-[11px] font-semibold px-1.5 py-0.5 rounded-[2px] bg-[var(--bg-surface)] text-[var(--text-secondary)] border border-[var(--border-strong)]">
              Biến thể {variant}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)] m-0">
            {variantMeta.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-[10px] font-semibold uppercase tracking-[0.05em] text-[var(--text-muted)]">
              Điểm hiện tại
            </div>
            <div
              className="num text-xl font-bold tracking-[-0.02em] leading-tight"
              style={{ color: zoneMeta?.fg ?? 'var(--text-primary)' }}
              data-testid="altman-score-value"
            >
              {formatScoreVi(altman.score, 2)}
            </div>
          </div>
          {zoneMeta ? (
            <span
              className="px-2.5 py-1 rounded-[2px] border text-xs font-semibold"
              style={{
                color: zoneMeta.fg,
                backgroundColor: zoneMeta.bg,
                borderColor: zoneMeta.border,
              }}
              data-testid="altman-zone-badge"
            >
              {altman.zone_label_vi || zoneMeta.label}
            </span>
          ) : null}
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Precision 3-Zone Ruler */}
        <div className="space-y-2">
          <div className="relative pt-6 pb-1">
            {scorePct !== null ? (
              <div
                className="absolute top-0 -translate-x-1/2 flex flex-col items-center"
                style={{ left: `${scorePct}%` }}
              >
                <span
                  className="num text-[11px] font-bold px-1.5 py-0.5 rounded-[2px]"
                  style={{
                    backgroundColor: zoneMeta?.fg ?? 'var(--text-primary)',
                    color: '#FFFFFF',
                  }}
                >
                  {formatScoreVi(altman.score, 2)}
                </span>
                <div
                  className="w-0.5 h-2"
                  style={{ backgroundColor: zoneMeta?.fg ?? 'var(--text-primary)' }}
                />
              </div>
            ) : null}

            <div className="h-3 w-full rounded-[2px] overflow-hidden flex gap-[1px] bg-[var(--border-subtle)]">
              <div
                className="h-full"
                style={{
                  width: `${lowPct}%`,
                  backgroundColor: 'var(--risk-critical-fg)',
                  opacity: 0.85,
                }}
                title={`Vùng nguy hiểm (< ${formatScoreVi(cutoffLow, 2)})`}
              />
              <div
                className="h-full"
                style={{
                  width: `${Math.max(0, highPct - lowPct)}%`,
                  backgroundColor: 'var(--risk-medium-fg)',
                  opacity: 0.85,
                }}
                title={`Vùng xám (${formatScoreVi(cutoffLow, 2)} – ${formatScoreVi(cutoffHigh, 2)})`}
              />
              <div
                className="h-full flex-1"
                style={{
                  backgroundColor: 'var(--risk-low-fg)',
                  opacity: 0.85,
                }}
                title={`Vùng an toàn (> ${formatScoreVi(cutoffHigh, 2)})`}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="flex items-center gap-1.5 text-[var(--risk-critical-fg)]">
              <span className="h-2 w-2 rounded-[1px] bg-[var(--risk-critical-fg)] shrink-0" />
              <span>
                Nguy hiểm{' '}
                <strong className="num" data-testid="altman-cutoff-low">
                  &lt; {cutoffLow.toFixed(2)}
                </strong>
              </span>
            </div>
            <div className="flex items-center justify-center gap-1.5 text-[var(--risk-medium-fg)]">
              <span className="h-2 w-2 rounded-[1px] bg-[var(--risk-medium-fg)] shrink-0" />
              <span>
                Vùng xám{' '}
                <strong className="num">
                  {cutoffLow.toFixed(2)}–{cutoffHigh.toFixed(2)}
                </strong>
              </span>
            </div>
            <div className="flex items-center justify-end gap-1.5 text-[var(--risk-low-fg)]">
              <span className="h-2 w-2 rounded-[1px] bg-[var(--risk-low-fg)] shrink-0" />
              <span>
                An toàn{' '}
                <strong className="num" data-testid="altman-cutoff-high">
                  &gt; {cutoffHigh.toFixed(2)}
                </strong>
              </span>
            </div>
          </div>
        </div>

        {altman.fallback_note_vi ? (
          <div className="flex items-start gap-2 p-3 rounded-[2px] bg-[var(--bg-header)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)]">
            <Info className="h-4 w-4 shrink-0 mt-0.5 text-[var(--accent-primary)]" aria-hidden="true" />
            <span>{altman.fallback_note_vi}</span>
          </div>
        ) : null}

        {altman.unavailable_reason_vi && altman.score === null ? (
          <div className="flex items-start gap-2 p-3 rounded-[2px] border border-[var(--risk-medium-border)] bg-[var(--risk-medium-bg)] text-xs text-[var(--risk-medium-fg)]">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{altman.unavailable_reason_vi}</span>
          </div>
        ) : null}
      </div>

      {/* Flush Hairline-Divided Component Strip (Zero Nested Boxes) */}
      {componentEntries.length > 0 ? (
        <div className="border-t border-[var(--border-subtle)] bg-[var(--bg-header)]/60">
          <div className="px-5 py-2 border-b border-[var(--border-subtle)] text-[10px] font-bold uppercase tracking-[0.06em] text-[var(--text-muted)]">
            Các thành phần cấu thành
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border-subtle)]">
            {componentEntries.map(([code, val]) => (
              <div key={code} className="px-4 py-3">
                <div
                  className="text-[11px] font-medium text-[var(--text-secondary)] truncate"
                  title={COMPONENT_LABELS_VI[code] ?? code}
                >
                  <span className="num font-bold text-[var(--accent-primary)] mr-1">{code}</span>
                  {COMPONENT_LABELS_VI[code] ?? code}
                </div>
                <div className="mt-1 num text-sm font-bold text-[var(--text-primary)]">
                  {formatScoreVi(val, 3)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
