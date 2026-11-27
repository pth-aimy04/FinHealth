import { useMemo, useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import {
  ArrowDownUp,
  ArrowRight,
  BookmarkPlus,
  Building2,
  Download,
  Filter,
  Search,
} from "lucide-react";
import {
  companies,
  filterKeys,
  mutate,
  type Company,
  type Schema,
} from "../lib/api/client";
import { date, label, metric, number } from "../lib/formatters";
import { downloadCsv } from "../lib/csv";
import { useSession } from "../app/session";
import {
  Empty,
  PageTitle,
  Panel,
  QueryState,
  Risk,
  Stat,
  TableRegion,
} from "../components/shared";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";

/** Restore multi-column sort from a shareable URL. */
export function readSort(value: string | null): SortingState {
  const allowed = [
    "ticker",
    "name",
    "sector",
    "roa",
    "roe",
    "debt_ratio",
    "current_ratio",
    "altman_z_score",
    "distress_probability",
    "composite_health_score",
    "latest_fiscal_year",
  ];
  return (value ?? "ticker:asc").split(",").flatMap((item) => {
    const [id, direction] = item.split(":");
    return allowed.includes(id) ? [{ id, desc: direction === "desc" }] : [];
  });
}
/** Complete public research table with URL filters, sorting, paging, column selection and exports. */
export default function Screener(): ReactElement {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useSession();
  const [visible, setVisible] = useState<Record<string, boolean>>({
    roe: false,
    current_ratio: false,
    altman_z_score: false,
  });
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const filterString = new URLSearchParams(
    [...params].filter(([key]) => filterKeys.some((item) => item === key)),
  ).toString();
  const query = useQuery({
    queryKey: ["companies", filterString],
    queryFn: ({ signal }) =>
      companies(new URLSearchParams(filterString), signal),
  });
  const universe = useQuery({
    queryKey: ["companies", ""],
    queryFn: ({ signal }) => companies(undefined, signal),
    staleTime: 60_000,
  });
  const data = query.data ?? [];
  const columns = useMemo<ColumnDef<Company>[]>(
    () => [
      {
        id: "select",
        header: "Chọn",
        enableSorting: false,
        cell: ({ row }) => (
          <input
            type="checkbox"
            aria-label={`So sánh ${row.original.ticker ?? row.original.cik}`}
            checked={selected.includes(row.original.cik)}
            disabled={
              selected.length >= 4 && !selected.includes(row.original.cik)
            }
            onChange={(event) =>
              setSelected((current) =>
                event.target.checked
                  ? [...current, row.original.cik]
                  : current.filter((cik) => cik !== row.original.cik),
              )
            }
          />
        ),
      },
      {
        accessorKey: "ticker",
        header: "Doanh nghiệp",
        cell: ({ row }) => (
          <div className="company-cell">
            <span className="ticker-mark" aria-hidden="true">
              {(row.original.ticker ?? "CIK").slice(0, 3)}
            </span>
            <div>
              <Link to={`/company/${row.original.cik}`}>
                {row.original.ticker ?? row.original.cik}
              </Link>
              <div className="company-name" title={row.original.name}>
                {row.original.name}
              </div>
            </div>
          </div>
        ),
      },
      {
        accessorKey: "sector",
        header: "Ngành",
        cell: ({ getValue }) => (
          <span className="muted">{getValue<string>() ?? "—"}</span>
        ),
      },
      ...(
        [
          "roa",
          "roe",
          "debt_ratio",
          "current_ratio",
          "altman_z_score",
          "composite_health_score",
        ] as const
      ).map((key) => ({
        accessorKey: key,
        header: label(key),
        sortUndefined: "last" as const,
        cell: ({ row }: { row: { original: Company } }) =>
          metric(key, row.original[key]),
      })),
      {
        accessorKey: "distress_probability",
        header: "Chỉ báo rủi ro",
        sortUndefined: "last",
        cell: ({ row }) => <Risk value={row.original.risk_level} />,
      },
      { accessorKey: "latest_fiscal_year", header: "Kỳ tài chính" },
    ],
    [selected],
  );
  const sorting = readSort(params.get("sort"));
  const pageIndex = Math.max(0, Number(params.get("page") ?? 1) - 1) || 0;
  const pageSize = [10, 25, 50, 100].includes(Number(params.get("size")))
    ? Number(params.get("size"))
    : 10;
  const update = (key: string, value: string): void => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next);
  };
  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnVisibility: visible,
      pagination: { pageIndex, pageSize },
    },
    onColumnVisibilityChange: setVisible,
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      update(
        "sort",
        next
          .map((item) => `${item.id}:${item.desc ? "desc" : "asc"}`)
          .join(","),
      );
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    autoResetPageIndex: false,
  });
  const save = async (): Promise<void> => {
    setSaveBusy(true);
    setSaveError("");
    const parsed = Object.fromEntries(
      [...new URLSearchParams(filterString)].map(([key, value]) => [
        key,
        ["q", "sector", "risk_level"].includes(key) ? value : Number(value),
      ]),
    );
    try {
      await mutate("/me/screeners", { name: saveName, filters: parsed });
      setSaving(false);
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Không lưu được bộ lọc",
      );
    } finally {
      setSaveBusy(false);
    }
  };
  const latest = (universe.data ?? [])
    .map((row) => row.filed_date)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1);
  return (
    <>
      <PageTitle
        title="Sàng lọc doanh nghiệp"
        description="Khám phá nền tảng tài chính. Nhận diện rủi ro. Tìm doanh nghiệp phù hợp với nghiên cứu của bạn."
        actions={
          <Button variant="outline" asChild>
            <Link to="/compare">
              <ArrowDownUp size={16} aria-hidden="true" />
              So sánh doanh nghiệp
            </Link>
          </Button>
        }
      />
      <div className="stats">
        <Stat
          title="Doanh nghiệp phù hợp"
          value={number(data.length, 0)}
          detail="Sau khi áp dụng bộ lọc"
          icon={<Building2 size={19} />}
        />
        <Stat
          title="Rủi ro thấp"
          value={number(
            data.filter((row) => row.risk_level === "LOW").length,
            0,
          )}
          detail="Nhãn theo mô hình đang hoạt động"
        />
        <Stat
          title="Có điểm sức khỏe"
          value={number(
            data.filter((row) => row.composite_health_score != null).length,
            0,
          )}
          detail="Điểm nghiên cứu nội bộ / 100"
        />
        <Stat
          title="Công bố mới nhất"
          value={date(latest)}
          detail="Trong tập doanh nghiệp đã lưu"
        />
      </div>
      <Panel
        title="Vũ trụ doanh nghiệp"
        note="Báo cáo năm SEC · Tỷ số dạng thập phân (ROA 5% = 0,05)"
        actions={
          <span className="small muted">
            <Filter size={14} className="inline" aria-hidden="true" /> Bộ lọc
            nghiên cứu
          </span>
        }
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            const next = new URLSearchParams(params);
            filterKeys.forEach((key) => {
              const value = String(form.get(key) ?? "").trim();
              if (value) next.set(key, value);
              else next.delete(key);
            });
            next.delete("page");
            setParams(next);
          }}
          key={filterString}
        >
          <div className="filters">
            <label>
              Tìm doanh nghiệp
              <input
                name="q"
                defaultValue={params.get("q") ?? ""}
                placeholder="Ticker, tên doanh nghiệp hoặc CIK"
              />
            </label>
            <label>
              Ngành
              <select name="sector" defaultValue={params.get("sector") ?? ""}>
                <option value="">Tất cả ngành</option>
                {[
                  ...new Set(
                    (universe.data ?? []).flatMap((row) =>
                      row.sector ? [row.sector] : [],
                    ),
                  ),
                ]
                  .sort()
                  .map((sector) => (
                    <option key={sector}>{sector}</option>
                  ))}
              </select>
            </label>
            <label>
              Mức rủi ro
              <select
                name="risk_level"
                defaultValue={params.get("risk_level") ?? ""}
              >
                <option value="">Tất cả mức</option>
                {Object.entries({
                  LOW: "Thấp",
                  MEDIUM: "Trung bình",
                  HIGH: "Cao",
                  CRITICAL: "Rất cao",
                }).map(([key, value]) => (
                  <option key={key} value={key}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Năm tài chính
              <input
                type="number"
                name="fiscal_year"
                min={1990}
                max={2100}
                defaultValue={params.get("fiscal_year") ?? ""}
                placeholder="Tất cả năm"
              />
            </label>
          </div>
          <details
            className="disclosure"
            open={[
              "cluster_id",
              "min_roa",
              "max_debt_ratio",
              "min_current_ratio",
            ].some((key) => params.has(key))}
          >
            <summary>Bộ lọc tỷ số và phân cụm</summary>
            <div className="filter-extra">
              {[
                ["cluster_id", "Mã cụm"],
                ["min_roa", "ROA tối thiểu"],
                ["max_debt_ratio", "Nợ / tài sản tối đa"],
                ["min_current_ratio", "Thanh toán hiện hành tối thiểu"],
              ].map(([key, title]) => (
                <label key={key}>
                  {title}
                  <input
                    name={key}
                    type="number"
                    step={key === "cluster_id" ? "1" : "any"}
                    min={
                      key === "cluster_id" || key === "min_current_ratio"
                        ? 0
                        : undefined
                    }
                    defaultValue={params.get(key) ?? ""}
                  />
                </label>
              ))}
            </div>
          </details>
          <div className="table-footer">
            <div className="actions">
              <Button type="submit">
                <Search size={16} aria-hidden="true" />
                Áp dụng bộ lọc
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setParams({})}
              >
                Đặt lại
              </Button>
            </div>
            <div className="actions">
              <Button
                type="button"
                variant="outline"
                onClick={() => (user ? setSaving(true) : navigate("/account"))}
              >
                <BookmarkPlus size={16} aria-hidden="true" />
                Lưu bộ lọc
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={!data.length || !user}
                title={
                  user
                    ? "Xuất toàn bộ kết quả đã sắp xếp"
                    : "Đăng nhập để xuất CSV"
                }
                onClick={() =>
                  downloadCsv(
                    "finhealth-screener.csv",
                    [
                      "cik",
                      "ticker",
                      "name",
                      "sector",
                      "latest_fiscal_year",
                      "filed_date",
                      "accession_number",
                      "roa",
                      "debt_ratio",
                      "risk_level",
                    ],
                    table.getSortedRowModel().rows.map((row) => row.original),
                    label,
                  )
                }
              >
                <Download size={16} aria-hidden="true" />
                Xuất CSV
              </Button>
            </div>
          </div>
        </form>
        <details className="disclosure">
          <summary>Hiển thị cột</summary>
          <div className="column-options">
            {table
              .getAllLeafColumns()
              .filter(
                (column) => column.id !== "select" && column.id !== "ticker",
              )
              .map((column) => (
                <label className="checkbox-label" key={column.id}>
                  <input
                    type="checkbox"
                    checked={column.getIsVisible()}
                    onChange={column.getToggleVisibilityHandler()}
                  />
                  {typeof column.columnDef.header === "string"
                    ? column.columnDef.header
                    : label(column.id)}
                </label>
              ))}
          </div>
        </details>
        <QueryState
          pending={query.isPending}
          error={query.error}
          retry={query.refetch}
        />
        {query.data &&
          (data.length ? (
            <>
              <TableRegion name="Kết quả sàng lọc doanh nghiệp">
                <table>
                  <thead>
                    {table.getHeaderGroups().map((group) => (
                      <tr key={group.id}>
                        {group.headers.map((header) => (
                          <th
                            key={header.id}
                            aria-sort={
                              header.column.getIsSorted() === "asc"
                                ? "ascending"
                                : header.column.getIsSorted() === "desc"
                                  ? "descending"
                                  : undefined
                            }
                          >
                            {header.column.getCanSort() ? (
                              <button
                                onClick={header.column.getToggleSortingHandler()}
                              >
                                {flexRender(
                                  header.column.columnDef.header,
                                  header.getContext(),
                                )}
                                <ArrowDownUp size={12} aria-hidden="true" />
                              </button>
                            ) : (
                              flexRender(
                                header.column.columnDef.header,
                                header.getContext(),
                              )
                            )}
                          </th>
                        ))}
                      </tr>
                    ))}
                  </thead>
                  <tbody>
                    {table.getRowModel().rows.map((row) => (
                      <tr key={row.id}>
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id}>
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableRegion>
              <div className="table-footer">
                <span className="small muted">
                  {data.length} doanh nghiệp · Giữ Shift để sắp xếp nhiều cột
                </span>
                <div className="actions">
                  <label className="sr-only" htmlFor="page-size">
                    Số dòng mỗi trang
                  </label>
                  <select
                    id="page-size"
                    value={pageSize}
                    onChange={(event) => update("size", event.target.value)}
                  >
                    {[10, 25, 50, 100].map((size) => (
                      <option key={size} value={size}>
                        {size} dòng
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="outline"
                    disabled={pageIndex === 0}
                    onClick={() => update("page", String(pageIndex))}
                  >
                    Trước
                  </Button>
                  <span className="small">
                    {pageIndex + 1} / {Math.max(1, table.getPageCount())}
                  </span>
                  <Button
                    variant="outline"
                    disabled={!table.getCanNextPage()}
                    onClick={() => update("page", String(pageIndex + 2))}
                  >
                    Sau
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <Empty />
          ))}
      </Panel>
      {selected.length > 0 && (
        <div className="notice actions">
          <strong>{selected.length}/4 doanh nghiệp được chọn</strong>
          <Button
            disabled={selected.length < 2}
            onClick={() =>
              navigate(`/compare?identifiers=${selected.join(",")}`)
            }
          >
            So sánh lựa chọn
            <ArrowRight size={16} aria-hidden="true" />
          </Button>
          <Button variant="ghost" onClick={() => setSelected([])}>
            Bỏ chọn
          </Button>
        </div>
      )}
      <p className="muted small">
        {!user && "Đăng nhập để xuất dữ liệu và lưu nghiên cứu. "}Chỉ báo khó
        khăn tài chính là proxy của mô hình; không phải xác suất vỡ nợ đã được
        kiểm chứng.
      </p>
      <Dialog
        open={saving}
        onOpenChange={setSaving}
        title="Lưu bộ lọc nghiên cứu"
      >
        <form
          className="form-stack"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <label>
            Tên bộ lọc
            <input
              required
              maxLength={120}
              value={saveName}
              onChange={(event) => setSaveName(event.target.value)}
            />
          </label>
          <p role="alert" className="field-error">
            {saveError}
          </p>
          <Button disabled={saveBusy || !saveName.trim()}>
            {saveBusy ? "Đang lưu…" : "Lưu vào workspace"}
          </Button>
        </form>
      </Dialog>
    </>
  );
}
export type ScreeningFilters = Schema["CompanyScreeningFilters"];
