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
    'inline-flex items-center justify-center gap-1.5 font-semibold tracking-[-0.005em] transition-colors duration-150 disabled:opacity-45 disabled:cursor-not-allowed cursor-pointer select-none whitespace-nowrap';
  const sizes = {
    sm: 'h-8 px-3 text-xs rounded-[3px]',
    md: 'h-9 px-4 text-[13px] rounded-[3px]',
  };
  const variants = {
    primary:
      'bg-[var(--accent-primary)] text-[var(--accent-ink)] hover:bg-[var(--accent-primary-hover)] border border-[var(--accent-primary)]',
    secondary:
      'bg-[var(--bg-surface)] text-[var(--text-primary)] border border-[var(--border-strong)] hover:bg-[var(--bg-hover)] hover:border-[var(--text-secondary)]',
    ghost:
      'bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] border border-transparent',
    danger:
      'bg-[var(--risk-critical-bg)] text-[var(--risk-critical-fg)] border border-[var(--risk-critical-border)] hover:opacity-90',
  };

  return (
    <button
      type={type}
      className={cn(base, sizes[size], variants[variant], className)}
      {...props}
    />
  );
}

/** Standard Institutional Page Masthead with Source Serif 4 Title & Bottom Rule */
export function PageHeader({
  title,
  description,
  actions,
  meta,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'pb-4 border-b border-[var(--border-strong)] flex flex-wrap items-end justify-between gap-4',
        className,
      )}
    >
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="font-editorial text-[1.5rem] sm:text-[1.75rem] font-semibold tracking-[-0.02em] leading-tight text-[var(--text-primary)]">
            {title}
          </h1>
          {meta}
        </div>
        {description ? (
          <p className="text-[13px] text-[var(--text-secondary)] max-w-3xl leading-relaxed">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** Architectural Ledger Panel — Crisp 1px borders, optional 2px Navy top rule, zero blurred shadow */
export function Panel({
  children,
  className,
  ruled = false,
}: {
  children: ReactNode;
  className?: string;
  ruled?: boolean;
}) {
  return (
    <section className={cn('min-w-0', ruled ? 'surface-ruled' : 'surface', className)}>
      {children}
    </section>
  );
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
        'flex flex-wrap items-center justify-between gap-3 px-4 sm:px-5 py-3 bg-[var(--bg-header)] border-b border-[var(--border-subtle)]',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-[14px] font-bold tracking-[-0.01em] text-[var(--text-primary)] leading-snug">
          {title}
        </h2>
        {description ? (
          <p className="mt-0.5 text-xs text-[var(--text-secondary)] leading-snug">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** Single-Plane Horizontal KPI Ledger Strip — Replaces scattered floating stat cards */
export function MetricStrip({
  children,
  columns = 4,
  className,
}: {
  children: ReactNode;
  columns?: 3 | 4 | 5;
  className?: string;
}) {
  const colClass =
    columns === 3
      ? 'grid-cols-1 sm:grid-cols-3'
      : columns === 5
        ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5'
        : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';
  return (
    <div
      className={cn(
        'surface-ruled grid divide-y sm:divide-y-0 sm:divide-x divide-[var(--border-subtle)]',
        colClass,
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Sharp Institutional Risk Stamp (Rectangular 2px corners + hairline border, zero consumer bubbles) */
export function RiskBadge({ level }: { level: string | null | undefined }) {
  const normalized = (level ?? 'UNSCORED').toUpperCase();

  const config: Record<
    string,
    { label: string; fg: string; bg: string; border: string; icon: typeof CheckCircle2 }
  > = {
    LOW: {
      label: 'Rủi ro thấp',
      fg: 'var(--risk-low-fg)',
      bg: 'var(--risk-low-bg)',
      border: 'var(--risk-low-border)',
      icon: CheckCircle2,
    },
    SAFE: {
      label: 'Vùng an toàn',
      fg: 'var(--risk-low-fg)',
      bg: 'var(--risk-low-bg)',
      border: 'var(--risk-low-border)',
      icon: CheckCircle2,
    },
    STRONG: {
      label: 'Mạnh',
      fg: 'var(--risk-low-fg)',
      bg: 'var(--risk-low-bg)',
      border: 'var(--risk-low-border)',
      icon: CheckCircle2,
    },
    STABLE: {
      label: 'Ổn định',
      fg: 'var(--risk-stable-fg)',
      bg: 'var(--risk-stable-bg)',
      border: 'var(--risk-stable-border)',
      icon: CheckCircle2,
    },
    MEDIUM: {
      label: 'Trung bình',
      fg: 'var(--risk-medium-fg)',
      bg: 'var(--risk-medium-bg)',
      border: 'var(--risk-medium-border)',
      icon: AlertTriangle,
    },
    GREY: {
      label: 'Vùng xám',
      fg: 'var(--risk-medium-fg)',
      bg: 'var(--risk-medium-bg)',
      border: 'var(--risk-medium-border)',
      icon: AlertTriangle,
    },
    ADEQUATE: {
      label: 'Đạt chuẩn',
      fg: 'var(--risk-stable-fg)',
      bg: 'var(--risk-stable-bg)',
      border: 'var(--risk-stable-border)',
      icon: CheckCircle2,
    },
    HIGH: {
      label: 'Rủi ro cao',
      fg: 'var(--risk-high-fg)',
      bg: 'var(--risk-high-bg)',
      border: 'var(--risk-high-border)',
      icon: AlertCircle,
    },
    WEAK: {
      label: 'Yếu',
      fg: 'var(--risk-high-fg)',
      bg: 'var(--risk-high-bg)',
      border: 'var(--risk-high-border)',
      icon: AlertCircle,
    },
    CRITICAL: {
      label: 'Nguy kịch',
      fg: 'var(--risk-critical-fg)',
      bg: 'var(--risk-critical-bg)',
      border: 'var(--risk-critical-border)',
      icon: ShieldAlert,
    },
    DISTRESS: {
      label: 'Vùng kiệt quệ',
      fg: 'var(--risk-critical-fg)',
      bg: 'var(--risk-critical-bg)',
      border: 'var(--risk-critical-border)',
      icon: ShieldAlert,
    },
  };

  const entry = config[normalized] ?? {
    label: normalized === 'UNSCORED' ? 'Chưa chấm điểm' : normalized,
    fg: 'var(--risk-neutral-fg)',
    bg: 'var(--risk-neutral-bg)',
    border: 'var(--risk-neutral-border)',
    icon: MinusCircle,
  };
  const Icon = entry.icon;

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold rounded-[2px] border whitespace-nowrap tracking-[0.01em]"
      style={{
        color: entry.fg,
        backgroundColor: entry.bg,
        borderColor: entry.border,
      }}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span>{entry.label}</span>
    </span>
  );
}

/** Precision Credit Risk Gauge calibrated to Capital Institutional palette */
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
      ? 'var(--risk-critical-fg)'
      : lvl === 'HIGH'
        ? 'var(--risk-high-fg)'
        : lvl === 'MEDIUM'
          ? 'var(--risk-medium-fg)'
          : 'var(--risk-low-fg)';

  return (
    <div className="flex flex-col items-center justify-center py-2">
      <div className="relative w-[156px] h-[90px] flex items-end justify-center">
        <svg viewBox="0 0 140 82" className="w-full h-full overflow-visible" aria-hidden="true">
          <path
            d="M 14 70 A 56 56 0 0 1 126 70"
            fill="none"
            stroke="var(--bg-subtle)"
            strokeWidth="10"
            strokeLinecap="butt"
          />
          {valid ? (
            <path
              d="M 14 70 A 56 56 0 0 1 126 70"
              fill="none"
              stroke={strokeColor}
              strokeWidth="10"
              strokeLinecap="butt"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: 'stroke-dashoffset 320ms cubic-bezier(0.16, 1, 0.3, 1)' }}
            />
          ) : null}
        </svg>
        <div className="absolute bottom-1 text-center">
          <div
            className="text-2xl font-bold num tracking-[-0.03em]"
            style={{ color: valid ? strokeColor : 'var(--text-muted)' }}
          >
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

/** Sharp inline micro-bar for financial tables (Capital IQ / Morningstar style) */
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
  const pct =
    tone === 'risk'
      ? Math.max(0, Math.min(100, value * 100))
      : Math.max(0, Math.min(100, value));
  const color =
    tone === 'risk'
      ? pct >= 8
        ? 'var(--risk-critical-fg)'
        : pct >= 3
          ? 'var(--risk-high-fg)'
          : pct >= 1
            ? 'var(--risk-medium-fg)'
            : 'var(--risk-low-fg)'
      : pct >= 80
        ? 'var(--risk-low-fg)'
        : pct >= 60
          ? 'var(--risk-stable-fg)'
          : pct >= 35
            ? 'var(--risk-medium-fg)'
            : 'var(--risk-critical-fg)';

  return (
    <div className="inline-flex items-center justify-end gap-2.5 min-w-[98px]">
      <div className="w-12 h-1.5 rounded-[1px] bg-[var(--bg-subtle)] overflow-hidden hidden sm:block">
        <div
          className="h-full"
          style={{
            width: `${pct}%`,
            backgroundColor: color,
            transition: 'width 260ms ease',
          }}
        />
      </div>
      <span className="num font-semibold text-right w-12 text-[var(--text-primary)]">
        {tone === 'risk' ? `${pct.toFixed(1)}%` : value.toFixed(1)}
      </span>
    </div>
  );
}

/** Ledger Metric Cell — Works standalone or inside MetricStrip (bare=true) */
export function MetricTile({
  label,
  value,
  meta,
  accent,
  bare = false,
}: {
  label: string;
  value: string;
  meta?: string;
  accent?: 'low' | 'medium' | 'high' | 'critical';
  bare?: boolean;
}) {
  const valueColor = accent ? `var(--risk-${accent}-fg)` : 'var(--text-primary)';
  return (
    <div className={cn('min-w-0', bare ? 'px-4 sm:px-5 py-3.5' : 'surface px-4 py-3.5')}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-secondary)]">
        {label}
      </div>
      <div
        className="mt-1.5 text-xl sm:text-[1.45rem] lg:text-[1.625rem] font-bold num tracking-[-0.03em] leading-tight break-words"
        style={{ color: valueColor }}
      >
        {value}
      </div>
      {meta ? (
        <div className="mt-1.5 text-xs text-[var(--text-muted)] truncate" title={meta}>
          {meta}
        </div>
      ) : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-[3px] bg-[var(--bg-subtle)]', className)}
      aria-hidden="true"
    />
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="p-4 space-y-2" role="status" aria-busy="true" aria-label="Đang tải dữ liệu">
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
        className="mx-auto h-7 w-7 text-[var(--text-muted)]"
        strokeWidth={1.5}
        aria-hidden="true"
      />
      <h3 className="mt-3 text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
      <p className="mt-1 mx-auto max-w-md text-[13px] text-[var(--text-secondary)]">
        {description}
      </p>
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
      className="surface px-4 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-[var(--risk-critical-border)] bg-[var(--risk-critical-bg)]/50"
    >
      <div className="flex items-start gap-3">
        <AlertCircle
          className="h-4 w-4 shrink-0 mt-0.5 text-[var(--risk-critical-fg)]"
          aria-hidden="true"
        />
        <div>
          <h3 className="text-[13px] font-semibold text-[var(--risk-critical-fg)]">{title}</h3>
          <p className="mt-0.5 text-xs text-[var(--text-primary)]">{message}</p>
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
