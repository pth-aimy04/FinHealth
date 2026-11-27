import type { ReactElement } from "react";
import type { Schema } from "../lib/api/client";
import { number } from "../lib/formatters";
const statuses: Record<string, string> = {
  STRONG: "Vững mạnh",
  ADEQUATE: "Đáp ứng",
  WEAK: "Yếu",
  CRITICAL: "Cần chú ý",
  UNAVAILABLE: "Chưa đủ dữ liệu",
};
/** Present server-computed pillars separately from the relative composite research score. */
export function HealthPillars({
  data,
}: {
  data: Schema["HealthPillarsSchema"];
}): ReactElement {
  return (
    <>
      <p className="small muted mb-4">
        Điểm nền tảng:{" "}
        <strong className="text-foreground">
          {number(data.overall_score, 1)} /100
        </strong>{" "}
        · {data.overall_grade}
      </p>
      <dl className="evidence">
        {Object.values(data.pillars ?? {}).map((item) => (
          <div key={item.name}>
            <dt>{item.label_vi}</dt>
            <dd>
              <strong>{number(item.score, 1)} /100</strong>
              <p className="small muted">
                {statuses[item.status ?? "UNAVAILABLE"]} ·{" "}
                {item.observed_metrics ?? 0}/{item.total_metrics ?? 0} chỉ tiêu
              </p>
            </dd>
          </div>
        ))}
      </dl>
    </>
  );
}
