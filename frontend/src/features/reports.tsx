import type { ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { request, type Schema } from "../lib/api/client";
import { date, label, number } from "../lib/formatters";
import {
  Empty,
  Evidence,
  PageTitle,
  Panel,
  QueryState,
  SourceLink,
  Stat,
  TableRegion,
} from "../components/shared";
import { Button } from "../components/ui/button";
/** Publication cutoff and version-aware reporting with untouched source provenance. */
export default function Reports(): ReactElement {
  const [params, setParams] = useSearchParams();
  const identifier = params.get("identifier") ?? "";
  const cutoff = params.get("as_of") ?? "";
  const period = params.get("period_kind") ?? "";
  const apiParams = new URLSearchParams({
    ...(cutoff ? { as_of: cutoff } : {}),
    ...(period ? { period_kind: period } : {}),
  });
  const query = useQuery({
    queryKey: ["reports", identifier, cutoff, period],
    enabled: Boolean(identifier),
    queryFn: ({ signal }) =>
      request<Schema["ReportResponseSchema"]>(
        `/reports/${encodeURIComponent(["FPT", "HPG"].includes(identifier.toUpperCase()) ? `vn:${identifier.toUpperCase()}` : identifier)}?${apiParams}`,
        { signal },
      ),
  });
  const alerts = useQuery({
    queryKey: ["alerts", identifier, cutoff],
    enabled: Boolean(identifier),
    queryFn: () =>
      request<Schema["ReportAlertSchema"][]>(
        `/report-alerts/${encodeURIComponent(["FPT", "HPG"].includes(identifier.toUpperCase()) ? `vn:${identifier.toUpperCase()}` : identifier)}${cutoff ? `?as_of=${cutoff}` : ""}`,
      ),
  });
  const quality = useQuery({
    queryKey: ["quality"],
    queryFn: () => request<Schema["DataQualitySchema"]>("/data-quality"),
  });
  const versions = query.data?.versions ?? [];
  const filing =
    versions.find((row) => String(row.id) === params.get("version")) ??
    versions[0];
  const forecasts = useQuery({
    queryKey: ["filing-evidence", filing?.id],
    enabled: Boolean(filing) && !cutoff,
    queryFn: () =>
      request<Schema["ForecastEvidenceSchema"][]>(
        `/filings/${filing?.id}/forecasts`,
      ),
  });
  return (
    <>
      <PageTitle
        title="Kho báo cáo & nguồn dữ liệu"
        description="Theo dõi phiên bản công bố, truy xuất từng chỉ tiêu và kiểm tra dữ liệu đã có tại một thời điểm."
      />
      <Panel
        title="Tra cứu công bố"
        note="SEC: ticker/CIK · Việt Nam thí điểm: FPT hoặc HPG (chỉ đọc báo cáo)"
      >
        <form
          className="panel-body form-stack"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            setParams(
              Object.fromEntries(
                [...data]
                  .map(([key, value]) => [key, String(value)])
                  .filter(([, value]) => value),
              ),
            );
          }}
        >
          <div className="form-grid">
            <label>
              Doanh nghiệp / nguồn
              <input
                name="identifier"
                defaultValue={identifier}
                placeholder="AAPL, CIK, FPT hoặc HPG"
                required
              />
            </label>
            <label>
              Tính đến ngày công bố (as-of)
              <input name="as_of" type="date" defaultValue={cutoff} />
            </label>
            <label>
              Loại kỳ
              <select name="period_kind" defaultValue={period}>
                <option value="">Tất cả</option>
                <option value="10-K">Báo cáo năm</option>
                <option value="10-Q">Báo cáo quý</option>
              </select>
            </label>
          </div>
          <Button>Đọc báo cáo đã lưu</Button>
        </form>
      </Panel>
      <QueryState
        pending={Boolean(identifier) && query.isFetching}
        error={query.error}
        retry={query.refetch}
      />
      {!identifier && (
        <Empty message="Nhập doanh nghiệp để xem các hồ sơ đã thu nhận. Tra cứu không gọi SEC hoặc cập nhật dữ liệu." />
      )}
      {query.data && !versions.length && (
        <Empty message="Không có báo cáo thỏa mốc công bố và loại kỳ đã chọn." />
      )}
      {filing && (
        <>
          <Panel
            title="Phiên bản báo cáo"
            note={`${versions.length} bản công bố · ${cutoff ? `as-of ${date(cutoff)}` : "Toàn bộ hồ sơ đã thu nhận"}`}
            actions={<SourceLink url={filing.source_url} />}
          >
            <div className="panel-body form-stack">
              <label>
                Chọn phiên bản
                <select
                  value={filing.id}
                  onChange={(event) => {
                    const next = new URLSearchParams(params);
                    next.set("version", event.target.value);
                    setParams(next);
                  }}
                >
                  {versions.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.fiscal_period} {row.fiscal_year} · {row.form_type} ·{" "}
                      {date(row.published_on)} · {row.accession}
                    </option>
                  ))}
                </select>
              </label>
              <div className="notice">
                <strong>
                  {filing.capture_kind === "legacy_snapshot"
                    ? "Bản chụp lịch sử, chưa xác nhận toàn bộ provenance"
                    : filing.capture_kind === "verified_pilot"
                      ? "Dữ liệu Việt Nam thí điểm đã đối chiếu"
                      : filing.capture_kind === "sec_amendment"
                        ? "Hồ sơ sửa đổi SEC · chỉ gồm các trường của bản sửa đổi"
                        : "Hồ sơ đã chuẩn hóa"}
                  .
                </strong>{" "}
                Phạm vi: {filing.scope} · Kết thúc kỳ: {date(filing.period_end)}{" "}
                · Công bố: {date(filing.published_on)}.{" "}
                {filing.accounting_framework ?? ""}
              </div>
              <TableRegion name="Giá trị và nguồn theo từng chỉ tiêu báo cáo">
                <table>
                  <thead>
                    <tr>
                      <th>Chỉ tiêu</th>
                      <th>Giá trị</th>
                      <th>Đơn vị / tiền tệ</th>
                      <th>Nguồn và kỳ</th>
                      <th>Thiếu dữ liệu</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(filing.values).map(([key, value]) => {
                      const source = filing.provenance[key];
                      return (
                        <tr key={key}>
                          <td>{label(key)}</td>
                          <td>{number(value)}</td>
                          <td>
                            {typeof source?.unit === "string"
                              ? source.unit
                              : "—"}
                          </td>
                          <td>
                            <details>
                              <summary>
                                {typeof source?.tag === "string"
                                  ? source.tag
                                  : "Xem provenance"}
                              </summary>
                              <Evidence data={source} />
                            </details>
                          </td>
                          <td>{filing.missing_reasons[key] ?? "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </TableRegion>
              <details>
                <summary>Metadata, fingerprint và nguồn công bố đầy đủ</summary>
                <Evidence
                  data={{
                    issuer_key: filing.issuer_key,
                    accession: filing.accession,
                    captured_at: filing.captured_at,
                    fingerprint: filing.fingerprint,
                    audit_status: filing.audit_status,
                    ratios: filing.ratios,
                    disclosure_url: filing.disclosure_url,
                  }}
                />
              </details>
            </div>
          </Panel>
          <Panel
            title="Bằng chứng dự báo theo phiên bản"
            note={
              cutoff
                ? "Không hiển thị dự báo lưu sau mốc as-of vì API chưa cung cấp thời điểm suy luận để kiểm tra."
                : "Phân biệt đầu vào xác nhận với bản lưu legacy chưa kiểm chứng"
            }
          >
            <div className="panel-body">
              {cutoff ? (
                <p className="muted">
                  Chỉ dùng số liệu công bố có sẵn tại mốc đã chọn.
                </p>
              ) : (
                <>
                  <QueryState
                    pending={forecasts.isPending}
                    error={forecasts.error}
                    retry={forecasts.refetch}
                  />
                  {forecasts.data?.length
                    ? forecasts.data.map((row) => (
                        <details key={row.id}>
                          <summary>
                            {row.model_version} ·{" "}
                            {row.input_status === "verified_inputs"
                              ? "Đầu vào đã lưu tại suy luận"
                              : "Chưa xác nhận đầu vào gốc"}
                          </summary>
                          <Evidence data={row} />
                        </details>
                      ))
                    : !forecasts.isPending && (
                        <Empty message="Chưa có bằng chứng dự báo lưu cho bản báo cáo này." />
                      )}
                </>
              )}
            </div>
          </Panel>
          <Panel
            title="Chuỗi quý & TTM"
            note="Giữ nguyên đơn vị, nguồn, cơ sở lũy kế và lý do thiếu quan sát"
          >
            <div className="panel-body">
              <Evidence data={query.data?.quarterly_series} />
            </div>
          </Panel>
        </>
      )}
      {identifier && (
        <Panel title="Cảnh báo thay đổi giữa các bản công bố">
          <div className="panel-body">
            <QueryState
              pending={alerts.isPending}
              error={alerts.error}
              retry={alerts.refetch}
            />
            {alerts.data?.length
              ? alerts.data.map((row, i) => (
                  <div className="notice" key={i}>
                    <strong>{row.rule}</strong>
                    <p>
                      {date(row.published_on)} · bản {row.previous_filing_id} →{" "}
                      {row.filing_id} · quy tắc v{row.rule_version}
                    </p>
                    <p>Thay đổi: {row.changed_fields.map(label).join(", ")}</p>
                    <SourceLink url={row.source_url} />
                  </div>
                ))
              : alerts.data && (
                  <p className="muted">
                    Không phát hiện cảnh báo trong các hồ sơ đã thu nhận.
                  </p>
                )}
          </div>
        </Panel>
      )}
      <Panel
        title="Chất lượng dữ liệu toàn vũ trụ"
        note="Độ phủ chỉ tiêu của báo cáo năm gần nhất"
      >
        <QueryState
          pending={quality.isPending}
          error={quality.error}
          retry={quality.refetch}
        />
        {quality.data && (
          <div className="panel-body">
            <Stat title="Báo cáo trong mẫu" value={quality.data.report_count} />
            <Evidence data={quality.data.observed} />
          </div>
        )}
      </Panel>
    </>
  );
}
