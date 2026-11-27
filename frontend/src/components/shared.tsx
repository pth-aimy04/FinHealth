import type { ReactElement, ReactNode } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  Database,
  LoaderCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError } from "../lib/api/client";
import { label, metric, number } from "../lib/formatters";
import { Button } from "./ui/button";
/** Page title with a consistent hierarchy. */
export function PageTitle({
  eyebrow = "KHÔNG GIAN NGHIÊN CỨU",
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}): ReactElement {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      {actions && <div className="actions">{actions}</div>}
    </header>
  );
}
/** A research panel with optional heading actions. */
export function Panel({
  title,
  note,
  children,
  actions,
  className = "",
}: {
  title: string;
  note?: string;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
}): ReactElement {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {note && <p className="muted small">{note}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
/** Query loading, recoverable failure and authorization feedback. */
export function QueryState({
  pending,
  error,
  retry,
}: {
  pending?: boolean;
  error?: Error | null;
  retry?: () => unknown;
}): ReactElement | null {
  if (pending)
    return (
      <div className="state" role="status">
        <LoaderCircle className="spin" aria-hidden="true" />
        <span>Đang đọc dữ liệu…</span>
        <div className="skeleton" />
      </div>
    );
  if (!error) return null;
  const auth = error instanceof ApiError && [401, 403].includes(error.status);
  return (
    <div className="state error" role="alert">
      <AlertCircle aria-hidden="true" />
      <h2>{auth ? "Quyền truy cập bị giới hạn" : "Chưa tải được dữ liệu"}</h2>
      <p>{error.message}</p>
      {auth ? (
        <Button asChild>
          <Link to="/account">Đăng nhập</Link>
        </Button>
      ) : (
        retry && (
          <Button variant="outline" onClick={() => void retry()}>
            Thử lại
          </Button>
        )
      )}
    </div>
  );
}
/** Empty observations never become invented metrics. */
export function Empty({
  message = "Chưa có dữ liệu phù hợp. Hãy điều chỉnh bộ lọc hoặc chọn doanh nghiệp khác.",
}: {
  message?: string;
}): ReactElement {
  return (
    <div className="state">
      <Database aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}
export const riskLabels: Record<string, string> = {
  LOW: "Thấp",
  MEDIUM: "Trung bình",
  HIGH: "Cao",
  CRITICAL: "Rất cao",
};
/** Risk uses a label and a symbol in addition to semantic color. */
export function Risk({ value }: { value?: string | null }): ReactElement {
  return (
    <span className={`risk risk-${value ?? "unknown"}`}>
      <span aria-hidden="true">{value === "LOW" ? "○" : "△"}</span>
      {value ? (riskLabels[value] ?? value) : "Chưa đánh giá"}
    </span>
  );
}
/** Metric tiles share tabular formatting. */
export function Stat({
  title,
  value,
  detail,
  icon,
}: {
  title: string;
  value: ReactNode;
  detail?: ReactNode;
  icon?: ReactNode;
}): ReactElement {
  return (
    <div className="stat">
      <div className="stat-top">
        <span>{title}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <div className="muted small">
        {detail ?? "Dữ liệu đã lưu trong hệ thống"}
      </div>
    </div>
  );
}
/** Wrap wide tables in a named, keyboard-focusable region. */
export function TableRegion({
  name,
  children,
}: {
  name: string;
  children: ReactNode;
}): ReactElement {
  return (
    <div className="table-region" role="region" aria-label={name} tabIndex={0}>
      {children}
    </div>
  );
}
/** Show extensible backend evidence recursively without hiding original field identifiers. */
export function Evidence({ data }: { data: unknown }): ReactElement {
  if (data == null) return <span className="muted">—</span>;
  if (typeof data !== "object")
    return (
      <span>
        {typeof data === "boolean"
          ? data
            ? "Có"
            : "Không"
          : typeof data === "number"
            ? number(data, 6)
            : String(data)}
      </span>
    );
  if (Array.isArray(data))
    return (
      <div className="evidence-list">
        {data.length ? (
          data.map((item, index) => (
            <div key={index}>
              <Evidence data={item} />
            </div>
          ))
        ) : (
          <span className="muted">Chưa có dữ liệu</span>
        )}
      </div>
    );
  return (
    <dl className="evidence">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt>{label(key)}</dt>
          <dd>
            {value !== null && typeof value === "object" ? (
              <details>
                <summary>Xem chi tiết</summary>
                <Evidence data={value} />
              </details>
            ) : typeof value === "number" ? (
              metric(key, value)
            ) : (
              <Evidence data={value} />
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
/** External provenance links only accept HTTPS URLs. */
export function SourceLink({
  url,
  children = "Báo cáo gốc",
}: {
  url?: string | null;
  children?: ReactNode;
}): ReactElement | null {
  return url?.startsWith("https://") ? (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="source-link"
    >
      {children}
      <ArrowUpRight size={14} aria-hidden="true" />
    </a>
  ) : null;
}
