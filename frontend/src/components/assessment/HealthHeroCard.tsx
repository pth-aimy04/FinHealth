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
    score !== null && Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;

  // Circular score ring geometry
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - clampedScore / 100);

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
      className="surface overflow-hidden"
    >
      {/* Top Identity & Actions Bar */}
      <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-4 border-b border-[var(--border-subtle)]">
        <div className="min-w-0 space-y-1">
          {companyName ? (
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg sm:text-xl font-bold tracking-[-0.02em] text-[var(--text-primary)] truncate">
                {companyName}
              </h1>
              {identifierLabel ? (
                <span className="num text-xs font-medium px-2 py-0.5 rounded-[5px] bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
                  {identifierLabel}
                </span>
              ) : null}
              {sourceLabel ? (
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[var(--accent-soft)] text-[var(--accent-primary)]">
                  {sourceLabel}
                </span>
              ) : null}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--text-secondary)]">
            {sectorName ? <span>Ngành: {sectorName}</span> : null}
            {fiscalYear ? (
              <span className="num">Kỳ BCTC: FY{fiscalYear}</span>
            ) : null}
            {accountingStandard ? (
              <span>Chuẩn: {formatStandardShortVi(accountingStandard)}</span>
            ) : null}
            {currency ? <span className="num">Tiền tệ: {currency}</span> : null}
            <span>Chế độ: {scoringModeLabel}</span>
          </div>
        </div>

        {(onExportPdf || onNewStatement || onCompare) ? (
          <div className="flex flex-wrap items-center gap-2 shrink-0">
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

      {/* Main 3-Second Rule Body */}
      <div className="p-5 grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Left: Single Health Score + 4-Tier Classification */}
        <div className="lg:col-span-4 flex items-center gap-4 p-4 rounded-[8px] bg-[var(--bg-subtle)]/70 border border-[var(--border-subtle)]">
          <div className="relative w-[104px] h-[104px] shrink-0 flex items-center justify-center">
            <svg
              viewBox="0 0 104 104"
              className="w-full h-full -rotate-90"
              aria-hidden="true"
            >
              <circle
                cx="52"
                cy="52"
                r={radius}
                fill="none"
                stroke="var(--border-strong)"
                strokeWidth="8"
                strokeOpacity="0.35"
              />
              {summary.scoring_eligible && score !== null ? (
                <circle
                  cx="52"
                  cy="52"
                  r={radius}
                  fill="none"
                  stroke={tierStyle?.ring ?? 'var(--accent-primary)'}
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={dashOffset}
                  style={{
                    transition: 'stroke-dashoffset 450ms cubic-bezier(0.16, 1, 0.3, 1)',
                  }}
                />
              ) : null}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <span
                className="num text-2xl font-bold tracking-[-0.03em]"
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
              <span className="text-[10px] font-medium text-[var(--text-muted)]">
                / 100 điểm
              </span>
            </div>
          </div>

          <div className="min-w-0 space-y-2">
            <div className="text-xs font-medium text-[var(--text-secondary)]">
              Điểm Sức khỏe Tài chính
            </div>
            {tierStyle ? (
              <div
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
                style={{
                  color: tierStyle.fg,
                  backgroundColor: tierStyle.bg,
                  border: `1px solid ${tierStyle.border}`,
                }}
                data-testid="risk-tier-badge"
              >
                <TierIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>{summary.risk_label_vi || tierStyle.label}</span>
              </div>
            ) : (
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-[var(--risk-neutral-bg)] text-[var(--risk-neutral-fg)]">
                <Info className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>{summary.risk_label_vi || 'Không áp dụng'}</span>
              </div>
            )}

            {!summary.scoring_eligible && summary.unavailable_reason_vi ? (
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                {summary.unavailable_reason_vi}
              </p>
            ) : null}
          </div>
        </div>

        {/* Middle: 12-Month PD + 4-Layer Confidence + Cash Flow Overlay */}
        <div className="lg:col-span-4 flex flex-col justify-between gap-3 p-4 rounded-[8px] border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-medium text-[var(--text-secondary)]">
                Nguy cơ khủng hoảng 12 tháng
              </div>
              <div
                className="mt-1 num text-2xl font-bold tracking-[-0.025em]"
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
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium cursor-pointer transition-opacity hover:opacity-90"
                style={{
                  color: confidenceMeta.fg,
                  backgroundColor: confidenceMeta.bg,
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

          {/* Expandable 4-Layer Confidence Explanation */}
          {summary.confidence && confidenceOpen ? (
            <div
              id="confidence-detail-panel"
              className="p-3 rounded-[6px] bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-2 text-xs"
            >
              <div className="font-semibold text-[var(--text-primary)]">
                4 tiêu chí đánh giá độ tin cậy
              </div>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[var(--text-secondary)]">
                <div>
                  <dt className="text-[11px] text-[var(--text-muted)]">Độ đầy đủ dữ liệu</dt>
                  <dd className="num font-medium text-[var(--text-primary)]">
                    {formatPctVi(summary.confidence.input_completeness, 0)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] text-[var(--text-muted)]">Kiểm tra ngoại lệ</dt>
                  <dd className="font-medium text-[var(--text-primary)]">
                    {summary.confidence.is_ood ? 'Có chỉ số bất thường' : 'Trong vùng chuẩn'}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] text-[var(--text-muted)]">Độ phân tán đánh giá</dt>
                  <dd className="num font-medium text-[var(--text-primary)]">
                    {summary.confidence.ensemble_spread !== null
                      ? formatPctVi(summary.confidence.ensemble_spread, 2)
                      : 'Ổn định'}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] text-[var(--text-muted)]">Trạng thái kiểm toán</dt>
                  <dd className="font-medium text-[var(--text-primary)]">
                    {formatAuditStatusVi(summary.confidence.audit_status)}
                  </dd>
                </div>
              </dl>
              {summary.confidence.reasons_vi.length > 0 ? (
                <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-[var(--text-secondary)]">
                  {summary.confidence.reasons_vi.map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          {/* Cash-flow Overlay Alert Flag */}
          {summary.cash_flow_overlay?.triggered ? (
            <div
              role="alert"
              className="flex items-start gap-2 p-2.5 rounded-[6px] text-xs"
              style={{
                backgroundColor: 'var(--risk-high-bg)',
                color: 'var(--risk-high-fg)',
              }}
            >
              <Waves className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
              <div className="space-y-0.5">
                <div className="font-semibold">Cảnh báo áp lực dòng tiền & kiểm toán</div>
                {summary.cash_flow_overlay.reasons_vi.map((reason, idx) => (
                  <p key={idx} className="leading-snug opacity-95">
                    {reason}
                  </p>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
              <CheckCircle2 className="h-3.5 w-3.5 text-[var(--risk-low-fg)] shrink-0" aria-hidden="true" />
              <span>Không phát hiện cờ cảnh báo dòng tiền bất thường.</span>
            </div>
          )}
        </div>

        {/* Right: Top 3 Executive Takeaways */}
        <div className="lg:col-span-4 flex flex-col justify-between p-4 rounded-[8px] border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
              3 Nhận định trọng tâm
            </div>
            {summary.top_3_takeaways_vi.length > 0 ? (
              <ol className="mt-2.5 space-y-2">
                {summary.top_3_takeaways_vi.slice(0, 3).map((item, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2.5 text-xs text-[var(--text-primary)] leading-relaxed"
                  >
                    <span className="num inline-flex items-center justify-center h-5 w-5 rounded-full shrink-0 text-[11px] font-semibold bg-[var(--accent-soft)] text-[var(--accent-primary)]">
                      {idx + 1}
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-2.5 text-xs text-[var(--text-muted)]">
                Chưa có đủ dữ liệu tài chính để tổng hợp nhận định điều hành.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Mandatory Legal Disclaimer Footer (NĐ 88/2014/NĐ-CP) */}
      <div className="px-5 py-2.5 bg-[var(--bg-subtle)]/60 border-t border-[var(--border-subtle)] flex items-start gap-2 text-[11px] text-[var(--text-muted)] leading-relaxed">
        <Scale className="h-3.5 w-3.5 shrink-0 mt-0.5 text-[var(--text-secondary)]" aria-hidden="true" />
        <p data-testid="legal-disclaimer">{summary.legal_disclaimer_vi}</p>
      </div>
    </section>
  );
}
