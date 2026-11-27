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
  { label: string; fg: string; bg: string }
> = {
  SAFE: {
    label: 'Vùng an toàn',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
  },
  GREY: {
    label: 'Vùng xám (cần theo dõi)',
    fg: 'var(--risk-medium-fg)',
    bg: 'var(--risk-medium-bg)',
  },
  DISTRESS: {
    label: 'Vùng nguy hiểm',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
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
  // Financial Institution / Excluded State
  if (!altman.applicable) {
    return (
      <section
        className="surface p-5 space-y-3"
        aria-label="Chỉ số Altman Z-Score không áp dụng"
        data-testid="altman-excluded-card"
      >
        <div className="flex items-start gap-3">
          <div className="h-9 w-9 rounded-[8px] bg-[var(--bg-subtle)] flex items-center justify-center shrink-0 text-[var(--text-secondary)]">
            <Building2 className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="space-y-1">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Chỉ số Altman Z-Score — Không áp dụng
            </h2>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
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

  // Dynamic scale bounds around cutoff_low and cutoff_high
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
      <div className="px-5 py-3.5 border-b border-[var(--border-subtle)] flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text-primary)]">
              {variantMeta.title}
            </h2>
            <span className="num text-[11px] font-semibold px-2 py-0.5 rounded bg-[var(--bg-subtle)] text-[var(--text-secondary)]">
              Biến thể {variant}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
            {variantMeta.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="text-right">
            <div className="text-[11px] text-[var(--text-muted)]">Điểm hiện tại</div>
            <div
              className="num text-xl font-bold tracking-[-0.02em]"
              style={{ color: zoneMeta?.fg ?? 'var(--text-primary)' }}
              data-testid="altman-score-value"
            >
              {formatScoreVi(altman.score, 2)}
            </div>
          </div>
          {zoneMeta ? (
            <span
              className="px-2.5 py-1 rounded-full text-xs font-semibold"
              style={{ color: zoneMeta.fg, backgroundColor: zoneMeta.bg }}
              data-testid="altman-zone-badge"
            >
              {altman.zone_label_vi || zoneMeta.label}
            </span>
          ) : null}
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Dynamic 3-Zone Bar */}
        <div className="space-y-2">
          <div className="relative pt-5 pb-1">
            {/* Score Marker */}
            {scorePct !== null ? (
              <div
                className="absolute top-0 -translate-x-1/2 flex flex-col items-center"
                style={{ left: `${scorePct}%` }}
              >
                <span
                  className="num text-[11px] font-bold px-1.5 py-0.5 rounded shadow-xs"
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

            {/* 3-Zone Segmented Track */}
            <div className="h-3.5 w-full rounded-full overflow-hidden flex border border-[var(--border-subtle)]">
              <div
                className="h-full"
                style={{
                  width: `${lowPct}%`,
                  backgroundColor: 'var(--risk-critical-fg)',
                  opacity: 0.78,
                }}
                title={`Vùng nguy hiểm (< ${formatScoreVi(cutoffLow, 2)})`}
              />
              <div
                className="h-full"
                style={{
                  width: `${Math.max(0, highPct - lowPct)}%`,
                  backgroundColor: 'var(--risk-medium-fg)',
                  opacity: 0.78,
                }}
                title={`Vùng xám (${formatScoreVi(cutoffLow, 2)} – ${formatScoreVi(cutoffHigh, 2)})`}
              />
              <div
                className="h-full flex-1"
                style={{
                  backgroundColor: 'var(--risk-low-fg)',
                  opacity: 0.78,
                }}
                title={`Vùng an toàn (> ${formatScoreVi(cutoffHigh, 2)})`}
              />
            </div>
          </div>

          {/* Dynamic Cutoff Legend */}
          <div className="grid grid-cols-3 gap-2 text-[11px]">
            <div className="flex items-center gap-1.5 text-[var(--risk-critical-fg)]">
              <span className="h-2 w-2 rounded-full bg-[var(--risk-critical-fg)] shrink-0" />
              <span>
                Nguy hiểm{' '}
                <strong className="num" data-testid="altman-cutoff-low">
                  &lt; {cutoffLow.toFixed(2)}
                </strong>
              </span>
            </div>
            <div className="flex items-center justify-center gap-1.5 text-[var(--risk-medium-fg)]">
              <span className="h-2 w-2 rounded-full bg-[var(--risk-medium-fg)] shrink-0" />
              <span>
                Vùng xám{' '}
                <strong className="num">
                  {cutoffLow.toFixed(2)}–{cutoffHigh.toFixed(2)}
                </strong>
              </span>
            </div>
            <div className="flex items-center justify-end gap-1.5 text-[var(--risk-low-fg)]">
              <span className="h-2 w-2 rounded-full bg-[var(--risk-low-fg)] shrink-0" />
              <span>
                An toàn{' '}
                <strong className="num" data-testid="altman-cutoff-high">
                  &gt; {cutoffHigh.toFixed(2)}
                </strong>
              </span>
            </div>
          </div>
        </div>

        {/* Fallback Note (e.g. Z -> Z' when missing market cap) */}
        {altman.fallback_note_vi ? (
          <div className="flex items-start gap-2 p-3 rounded-[6px] bg-[var(--bg-subtle)] text-xs text-[var(--text-secondary)]">
            <Info className="h-4 w-4 shrink-0 mt-0.5 text-[var(--accent-primary)]" aria-hidden="true" />
            <span>{altman.fallback_note_vi}</span>
          </div>
        ) : null}

        {altman.unavailable_reason_vi && altman.score === null ? (
          <div className="flex items-start gap-2 p-3 rounded-[6px] bg-[var(--risk-medium-bg)] text-xs text-[var(--risk-medium-fg)]">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{altman.unavailable_reason_vi}</span>
          </div>
        ) : null}

        {/* Components Breakdown */}
        {componentEntries.length > 0 ? (
          <div className="pt-2 border-t border-[var(--border-subtle)]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)] mb-2">
              Các thành phần cấu thành
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              {componentEntries.map(([code, val]) => (
                <div
                  key={code}
                  className="p-2 rounded-[6px] bg-[var(--bg-subtle)]/60 border border-[var(--border-subtle)]"
                >
                  <div className="text-[10px] font-medium text-[var(--text-muted)] truncate" title={COMPONENT_LABELS_VI[code] ?? code}>
                    {COMPONENT_LABELS_VI[code] ?? code}
                  </div>
                  <div className="mt-0.5 num text-xs font-semibold text-[var(--text-primary)]">
                    {formatScoreVi(val, 3)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
