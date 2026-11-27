import type { ButtonHTMLAttributes, ReactNode } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Inbox,
  MinusCircle,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import { isFiniteNumber } from '@/lib/format';

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  type = 'button',
  ...props
}: ButtonProps) {
  const base =
    'inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer select-none active:scale-[0.99]';
  const sizes = {
    sm: 'h-8 px-3 text-xs rounded-[6px]',
    md: 'h-9 px-4 text-sm rounded-[6px]',
  };
  const variants = {
    primary:
      'bg-[var(--accent-primary)] text-[var(--accent-ink)] hover:bg-[var(--accent-primary-hover)] border border-transparent shadow-xs',
    secondary:
      'bg-[var(--bg-surface)] text-[var(--text-primary)] border border-[var(--border-strong)] hover:bg-[var(--bg-hover)]',
    ghost:
      'bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] border border-transparent',
    danger:
      'bg-[var(--risk-critical-bg)] text-[var(--risk-critical-fg)] border border-[var(--risk-critical-fg)]/25 hover:opacity-90',
  };

  return (
    <button
      type={type}
      className={cn(base, sizes[size], variants[variant], className)}
      {...props}
    />
  );
}

export function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={cn('surface', className)}>{children}</section>;
}

export function PanelHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-[var(--border-subtle)]',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-sm font-semibold tracking-[-0.01em] text-[var(--text-primary)]">
          {title}
        </h2>
        {description ? (
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function RiskBadge({ level }: { level: string | null | undefined }) {
  const normalized = (level ?? 'UNSCORED').toUpperCase();

  const config: Record<
    string,
    { label: string; fg: string; bg: string; icon: typeof CheckCircle2 }
  > = {
    LOW: { label: 'Rủi ro thấp', fg: 'var(--risk-low-fg)', bg: 'var(--risk-low-bg)', icon: CheckCircle2 },
    SAFE: { label: 'Vùng an toàn', fg: 'var(--risk-low-fg)', bg: 'var(--risk-low-bg)', icon: CheckCircle2 },
    STRONG: { label: 'Mạnh', fg: 'var(--risk-low-fg)', bg: 'var(--risk-low-bg)', icon: CheckCircle2 },
    MEDIUM: { label: 'Trung bình', fg: 'var(--risk-medium-fg)', bg: 'var(--risk-medium-bg)', icon: AlertTriangle },
    GREY: { label: 'Vùng xám', fg: 'var(--risk-medium-fg)', bg: 'var(--risk-medium-bg)', icon: AlertTriangle },
    ADEQUATE: { label: 'Đạt chuẩn', fg: 'var(--risk-medium-fg)', bg: 'var(--risk-medium-bg)', icon: AlertTriangle },
    HIGH: { label: 'Rủi ro cao', fg: 'var(--risk-high-fg)', bg: 'var(--risk-high-bg)', icon: AlertCircle },
    WEAK: { label: 'Yếu', fg: 'var(--risk-high-fg)', bg: 'var(--risk-high-bg)', icon: AlertCircle },
    CRITICAL: { label: 'Nguy kịch', fg: 'var(--risk-critical-fg)', bg: 'var(--risk-critical-bg)', icon: ShieldAlert },
    DISTRESS: { label: 'Vùng kiệt quệ', fg: 'var(--risk-critical-fg)', bg: 'var(--risk-critical-bg)', icon: ShieldAlert },
  };

  const entry = config[normalized] ?? {
    label: normalized === 'UNSCORED' ? 'Chưa chấm điểm' : normalized,
    fg: 'var(--risk-neutral-fg)',
    bg: 'var(--risk-neutral-bg)',
    icon: MinusCircle,
  };
  const Icon = entry.icon;

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-medium rounded-full whitespace-nowrap"
      style={{ color: entry.fg, backgroundColor: entry.bg }}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{entry.label}</span>
    </span>
  );
}

/** Đồng hồ bán nguyệt đo xác suất kiệt quệ (chuẩn credit risk terminal). */
export function RiskGauge({
  probability,
  riskLevel,
  label = 'Xác suất kiệt quệ P(t+1)',
}: {
  probability: number | null | undefined;
  riskLevel: string | null | undefined;
  label?: string;
}) {
  const valid = isFiniteNumber(probability);
  const clamped = valid ? Math.max(0, Math.min(1, probability)) : 0;
  const radius = 56;
  const circumference = Math.PI * radius;
  const offset = circumference * (1 - clamped);

  const lvl = (riskLevel ?? '').toUpperCase();
  const strokeColor =
    lvl === 'CRITICAL'
      ? '#BE123C'
      : lvl === 'HIGH'
        ? '#EA580C'
        : lvl === 'MEDIUM'
          ? '#D97706'
          : '#0D7A68';

  return (
    <div className="flex flex-col items-center justify-center py-2">
      <div className="relative w-[156px] h-[92px] flex items-end justify-center">
        <svg viewBox="0 0 140 82" className="w-full h-full overflow-visible" aria-hidden="true">
          <path
            d="M 14 70 A 56 56 0 0 1 126 70"
            fill="none"
            stroke="var(--bg-subtle)"
            strokeWidth="12"
            strokeLinecap="round"
          />
          {valid ? (
            <path
              d="M 14 70 A 56 56 0 0 1 126 70"
              fill="none"
              stroke={strokeColor}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: 'stroke-dashoffset 450ms cubic-bezier(0.16, 1, 0.3, 1)' }}
            />
          ) : null}
        </svg>
        <div className="absolute bottom-1 text-center">
          <div className="text-2xl font-bold num tracking-[-0.03em]" style={{ color: valid ? strokeColor : 'var(--text-muted)' }}>
            {valid ? `${(clamped * 100).toFixed(1)}%` : '—'}
          </div>
        </div>
      </div>
      <div className="mt-1 text-[11px] font-medium text-[var(--text-secondary)]">{label}</div>
      <div className="mt-1.5">
        <RiskBadge level={riskLevel} />
      </div>
    </div>
  );
}

/** Thanh tỷ lệ trực quan nằm gọn trong ô bảng (giống FireAnt / Simplize). */
export function InlineProbBar({
  value,
  tone = 'risk',
}: {
  value: number | null | undefined;
  tone?: 'risk' | 'health';
}) {
  if (!isFiniteNumber(value)) {
    return <span className="num text-[var(--text-muted)]">—</span>;
  }
  const pct = tone === 'risk' ? Math.max(0, Math.min(100, value * 100)) : Math.max(0, Math.min(100, value));
  const color =
    tone === 'risk'
      ? pct >= 60
        ? '#BE123C'
        : pct >= 35
          ? '#EA580C'
          : pct >= 15
            ? '#D97706'
            : '#0D7A68'
      : pct >= 70
        ? '#0D7A68'
        : pct >= 45
          ? '#D97706'
          : '#BE123C';

  return (
    <div className="inline-flex items-center justify-end gap-2 min-w-[92px]">
      <div className="w-12 h-1.5 rounded-full bg-[var(--bg-subtle)] overflow-hidden hidden sm:block">
        <div
          className="h-full rounded-full"
          style={{
            width: `${pct}%`,
            backgroundColor: color,
            transition: 'width 320ms cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        />
      </div>
      <span className="num font-semibold text-right w-11">
        {tone === 'risk' ? `${pct.toFixed(1)}%` : value.toFixed(1)}
      </span>
    </div>
  );
}

export function MetricTile({
  label,
  value,
  meta,
  accent,
}: {
  label: string;
  value: string;
  meta?: string;
  accent?: 'low' | 'medium' | 'high' | 'critical';
}) {
  const valueColor = accent ? `var(--risk-${accent}-fg)` : 'var(--text-primary)';
  return (
    <div className="surface interactive-card px-4 py-3.5">
      <div className="text-xs font-medium text-[var(--text-secondary)]">{label}</div>
      <div
        className="mt-1.5 text-2xl font-semibold num tracking-[-0.025em]"
        style={{ color: valueColor }}
      >
        {value}
      </div>
      {meta ? (
        <div className="mt-1 text-xs text-[var(--text-muted)] truncate" title={meta}>
          {meta}
        </div>
      ) : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-[6px] bg-[var(--bg-subtle)]', className)}
      aria-hidden="true"
    />
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="p-4 space-y-2.5" role="status" aria-busy="true" aria-label="Đang tải dữ liệu">
      {Array.from({ length: rows }).map((_, idx) => (
        <Skeleton key={idx} className="h-9 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div role="status" className="px-6 py-12 text-center">
      <Inbox
        className="mx-auto h-8 w-8 text-[var(--text-muted)]"
        strokeWidth={1.5}
        aria-hidden="true"
      />
      <h3 className="mt-3 text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
      <p className="mt-1 mx-auto max-w-md text-xs text-[var(--text-secondary)]">{description}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = 'Không thể tải dữ liệu',
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="surface px-5 py-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
    >
      <div className="flex items-start gap-3">
        <AlertCircle
          className="h-5 w-5 shrink-0 mt-0.5 text-[var(--risk-critical-fg)]"
          aria-hidden="true"
        />
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
          <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Thử lại
        </Button>
      ) : null}
    </div>
  );
}
