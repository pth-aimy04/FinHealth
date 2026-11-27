import { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileDown,
  FilePlus2,
  GitCompare,
  Info,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Waves,
} from 'lucide-react';
import { Button } from '@/components/ui/Primitives';
import {
  CONFIDENCE_META_VI,
  RISK_TIER_STYLE,
  formatAuditStatusVi,
  formatPctVi,
  formatScoreVi,
  formatStandardShortVi,
  type AssessmentSummaryView,
  type RiskTier,
} from './types';

export interface HealthHeroCardProps {
  summary: AssessmentSummaryView;
  companyName?: string;
  identifierLabel?: string;
  sectorName?: string | null;
  fiscalYear?: number | null;
  accountingStandard?: string | null;
  currency?: string | null;
  sourceLabel?: string;
  onExportPdf?: () => void;
  exportingPdf?: boolean;
  onNewStatement?: () => void;
  onCompare?: () => void;
}

function getTierIcon(tier: RiskTier | null) {
  switch (tier) {
    case 'STRONG':
      return CheckCircle2;
    case 'STABLE':
      return ShieldCheck;
    case 'WATCH':
      return AlertTriangle;
    case 'CRITICAL':
      return ShieldAlert;
    default:
      return Info;
  }
}

export function HealthHeroCard({
  summary,
  companyName,
  identifierLabel,
  sectorName,
  fiscalYear,
  accountingStandard,
  currency,
  sourceLabel,
  onExportPdf,
  exportingPdf = false,
  onNewStatement,
  onCompare,
}: HealthHeroCardProps) {
  const [confidenceOpen, setConfidenceOpen] = useState(false);

  const tierStyle = summary.risk_tier ? RISK_TIER_STYLE[summary.risk_tier] : null;
  const TierIcon = getTierIcon(summary.risk_tier);
  const score = summary.health_score;
  const clampedScore =
    score !== null && Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : null;

  const confidenceMeta = summary.confidence
    ? CONFIDENCE_META_VI[summary.confidence.level]
    : null;

  const scoringModeLabel =
    summary.scoring_mode === 'multi_period'
      ? 'Đánh giá đa kỳ'
      : summary.scoring_mode === 'single_period'
        ? 'Đánh giá đơn kỳ'
        : 'Không áp dụng';

  return (
    <section
      aria-label="Tóm tắt sức khỏe tài chính"
      className="surface-ruled overflow-hidden"
    >
      {/* Institutional Entity Masthead Strip */}
      <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-4 bg-[var(--bg-header)] border-b border-[var(--border-subtle)]">
        <div className="min-w-0 space-y-1.5">
          {companyName ? (
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="font-editorial text-xl sm:text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] leading-tight break-words">
                {companyName}
              </h1>
              {identifierLabel ? (
                <span className="num text-xs font-semibold px-2 py-0.5 rounded-[2px] bg-[var(--bg-surface)] text-[var(--text-primary)] border border-[var(--border-strong)]">
                  {identifierLabel}
                </span>
              ) : null}
              {sourceLabel ? (
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-[2px] bg-[var(--accent-soft)] text-[var(--accent-primary)] border border-[var(--accent-border)]">
                  {sourceLabel}
                </span>
              ) : null}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--text-secondary)]">
            {sectorName ? <span>Ngành: {sectorName}</span> : null}
            {fiscalYear ? (
              <span className="font-medium text-[var(--text-primary)]">
                Kỳ BCTC: <span className="num">FY{fiscalYear}</span>
              </span>
            ) : null}
            {accountingStandard ? (
              <span>Chuẩn: {formatStandardShortVi(accountingStandard)}</span>
            ) : null}
            {currency ? (
              <span>
                Tiền tệ: <span className="num font-medium">{currency}</span>
              </span>
            ) : null}
            <span>Chế độ: {scoringModeLabel}</span>
          </div>
        </div>

        {onExportPdf || onNewStatement || onCompare ? (
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            {onNewStatement ? (
              <Button variant="secondary" size="sm" onClick={onNewStatement}>
                <FilePlus2 className="h-3.5 w-3.5" aria-hidden="true" />
                Nhập BCTC kỳ mới
              </Button>
            ) : null}
            {onCompare ? (
              <Button variant="secondary" size="sm" onClick={onCompare}>
                <GitCompare className="h-3.5 w-3.5" aria-hidden="true" />
                So sánh
              </Button>
            ) : null}
            {onExportPdf ? (
              <Button
                variant="primary"
                size="sm"
                onClick={onExportPdf}
                disabled={exportingPdf}
                aria-busy={exportingPdf}
              >
                <FileDown className="h-3.5 w-3.5" aria-hidden="true" />
                {exportingPdf ? 'Đang xuất PDF...' : 'Xuất Báo cáo PDF'}
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* 3-Column Hairline-Divided Credit Tearsheet Body (Zero Nested Cards) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-[var(--border-subtle)]">
        {/* Column 1: Calibrated Health Score & 4-Zone Linear Spectrum */}
        <div className="lg:col-span-4 p-5 flex flex-col justify-between gap-4">
          <div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-secondary)]">
                Điểm Sức khỏe Tài chính
              </span>
              {tierStyle ? (
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[11px] font-semibold border"
                  style={{
                    color: tierStyle.fg,
                    backgroundColor: tierStyle.bg,
                    borderColor: tierStyle.border,
                  }}
                  data-testid="risk-tier-badge"
                >
                  <TierIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
                  <span>{summary.risk_label_vi || tierStyle.label}</span>
                </span>
              ) : (
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[11px] font-semibold border bg-[var(--risk-neutral-bg)] text-[var(--risk-neutral-fg)] border-[var(--risk-neutral-border)]"
                  data-testid="risk-tier-badge"
                >
                  <Info className="h-3 w-3 shrink-0" aria-hidden="true" />
                  <span>{summary.risk_label_vi || 'Không áp dụng'}</span>
                </span>
              )}
            </div>

            <div className="mt-3 flex items-baseline gap-2">
              <span
                className="num text-[2.5rem] font-bold tracking-[-0.035em] leading-none"
                style={{
                  color:
                    summary.scoring_eligible && tierStyle
                      ? tierStyle.fg
                      : 'var(--text-muted)',
                }}
                data-testid="health-score-value"
              >
                {summary.scoring_eligible ? formatScoreVi(score, 1) : '—'}
              </span>
              <span className="num text-xs font-medium text-[var(--text-muted)]">
                / 100 điểm
              </span>
            </div>
          </div>

          {summary.scoring_eligible && clampedScore !== null ? (
            <div className="space-y-1.5">
              {/* Precision Calibrated 4-Tier Ruler (0 | 35 | 60 | 80 | 100) */}
              <div className="relative pt-2.5 pb-0.5">
                <div
                  className="absolute top-0 -translate-x-1/2 flex flex-col items-center pointer-events-none"
                  style={{ left: `${clampedScore}%` }}
                >
                  <span
                    className="h-2 w-2 rotate-45 border border-[var(--bg-surface)]"
                    style={{ backgroundColor: tierStyle?.fg ?? 'var(--text-primary)' }}
                  />
                </div>
                <div className="h-2.5 w-full rounded-[2px] overflow-hidden flex gap-[1px] bg-[var(--border-subtle)]">
                  <div
                    className="h-full"
                    style={{ width: '35%', backgroundColor: 'var(--risk-critical-fg)', opacity: 0.85 }}
                    title="0–35: Nguy cơ khủng hoảng cao"
                  />
                  <div
                    className="h-full"
                    style={{ width: '25%', backgroundColor: 'var(--risk-medium-fg)', opacity: 0.85 }}
                    title="35–60: Cần theo dõi sát"
                  />
                  <div
                    className="h-full"
                    style={{ width: '20%', backgroundColor: 'var(--risk-stable-fg)', opacity: 0.85 }}
                    title="60–80: Ổn định"
                  />
                  <div
                    className="h-full flex-1"
                    style={{ backgroundColor: 'var(--risk-low-fg)', opacity: 0.85 }}
                    title="80–100: Vững mạnh"
                  />
                </div>
              </div>
              <div className="flex justify-between num text-[10px] text-[var(--text-muted)]">
                <span>0</span>
                <span>35</span>
                <span>60</span>
                <span>80</span>
                <span>100</span>
              </div>
            </div>
          ) : summary.unavailable_reason_vi ? (
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              {summary.unavailable_reason_vi}
            </p>
          ) : null}
        </div>

        {/* Column 2: 12-Month PD + 4-Layer Confidence Audit + Cash-Flow Overlay */}
        <div className="lg:col-span-4 p-5 flex flex-col justify-between gap-3.5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-secondary)]">
                Nguy cơ khủng hoảng 12 tháng
              </div>
              <div
                className="mt-2.5 num text-[2.125rem] font-bold tracking-[-0.03em] leading-none"
                style={{
                  color:
                    summary.scoring_eligible && tierStyle
                      ? tierStyle.fg
                      : 'var(--text-muted)',
                }}
                data-testid="pd-12m-value"
              >
                {summary.scoring_eligible ? formatPctVi(summary.pd_12m, 2) : '—'}
              </div>
            </div>

            {summary.confidence && confidenceMeta ? (
              <button
                type="button"
                onClick={() => setConfidenceOpen((prev) => !prev)}
                aria-expanded={confidenceOpen}
                aria-controls="confidence-detail-panel"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[2px] border text-xs font-semibold cursor-pointer transition-opacity hover:opacity-90"
                style={{
                  color: confidenceMeta.fg,
                  backgroundColor: confidenceMeta.bg,
                  borderColor: 'currentColor',
                }}
              >
                <span>Độ tin cậy: {confidenceMeta.label}</span>
                {confidenceOpen ? (
                  <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
                )}
              </button>
            ) : null}
          </div>

          {summary.confidence && confidenceOpen ? (
            <div
              id="confidence-detail-panel"
              className="p-3 rounded-[2px] bg-[var(--bg-header)] border border-[var(--border-subtle)] space-y-2 text-xs"
            >
              <div className="text-[11px] font-bold uppercase tracking-[0.04em] text-[var(--text-primary)]">
                4 tiêu chí đánh giá độ tin cậy
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[var(--text-secondary)] m-0">
                <div>
                  <dt className="text-[11px] text-[var(--text-muted)]">Độ đầy đủ dữ liệu</dt>
                  <dd className="num font-semibold text-[var(--text-primary)] m-0">
                    {formatPctVi(summary.confidence.input_completeness, 0)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] text-[var(--text-muted)]">Kiểm tra ngoại lệ</dt>
                  <dd className="font-semibold text-[var(--text-primary)] m-0">
                    {summary.confidence.is_ood ? 'Có chỉ số bất thường' : 'Trong vùng chuẩn'}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] text-[var(--text-muted)]">Độ phân tán đánh giá</dt>
                  <dd className="num font-semibold text-[var(--text-primary)] m-0">
                    {summary.confidence.ensemble_spread !== null
                      ? formatPctVi(summary.confidence.ensemble_spread, 2)
                      : 'Ổn định'}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] text-[var(--text-muted)]">Trạng thái kiểm toán</dt>
                  <dd className="font-semibold text-[var(--text-primary)] m-0">
                    {formatAuditStatusVi(summary.confidence.audit_status)}
                  </dd>
                </div>
              </dl>
              {summary.confidence.reasons_vi.length > 0 ? (
                <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-[var(--text-secondary)] m-0 pt-1 border-t border-[var(--border-subtle)]">
                  {summary.confidence.reasons_vi.map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          {summary.cash_flow_overlay?.triggered ? (
            <div
              role="alert"
              className="flex items-start gap-2 p-2.5 rounded-[2px] border text-xs"
              style={{
                backgroundColor: 'var(--risk-high-bg)',
                color: 'var(--risk-high-fg)',
                borderColor: 'var(--risk-high-border)',
              }}
            >
              <Waves className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
              <div className="space-y-0.5">
                <div className="font-semibold">Cảnh báo áp lực dòng tiền & kiểm toán</div>
                {summary.cash_flow_overlay.reasons_vi.map((reason, idx) => (
                  <p key={idx} className="leading-snug m-0 text-[var(--text-primary)]">
                    {reason}
                  </p>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)] pt-1 border-t border-[var(--border-subtle)]">
              <CheckCircle2
                className="h-3.5 w-3.5 text-[var(--risk-low-fg)] shrink-0"
                aria-hidden="true"
              />
              <span>Không phát hiện cờ cảnh báo dòng tiền bất thường.</span>
            </div>
          )}
        </div>

        {/* Column 3: Top 3 Executive Credit Memo Takeaways */}
        <div className="lg:col-span-4 p-5 flex flex-col justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-secondary)]">
              3 Nhận định trọng tâm
            </div>
            {summary.top_3_takeaways_vi.length > 0 ? (
              <ol className="mt-3 space-y-2.5 list-none p-0 m-0">
                {summary.top_3_takeaways_vi.slice(0, 3).map((item, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2.5 text-[13px] text-[var(--text-primary)] leading-snug"
                  >
                    <span className="num inline-flex items-center justify-center h-5 w-5 rounded-[2px] shrink-0 text-[11px] font-bold bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-strong)] mt-0.5">
                      {idx + 1}
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-3 text-xs text-[var(--text-muted)]">
                Chưa có đủ dữ liệu tài chính để tổng hợp nhận định điều hành.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Mandatory Legal Disclaimer Footer (Decree 88/2014/ND-CP) */}
      <div className="px-5 py-2.5 bg-[var(--bg-header)] border-t border-[var(--border-subtle)] flex items-start gap-2 text-[11px] text-[var(--text-muted)] leading-relaxed">
        <Scale
          className="h-3.5 w-3.5 shrink-0 mt-0.5 text-[var(--text-secondary)]"
          aria-hidden="true"
        />
        <p data-testid="legal-disclaimer" className="m-0">
          {summary.legal_disclaimer_vi}
        </p>
      </div>
    </section>
  );
}
