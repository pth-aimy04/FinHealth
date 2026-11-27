import { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import {
  ArrowUpDown,
  BookmarkPlus,
  GitCompare,
  RotateCcw,
  Star,
} from 'lucide-react';
import { api } from '@/lib/api';
import { formatPct, formatRatio, translateSector } from '@/lib/format';
import type { CompanySummary } from '@/types/api';
import { useAuth } from '@/context/AuthContext';
import { mapPdToSingleHealthScore } from './OverviewPage';
import {
  Button,
  EmptyState,
  ErrorState,
  InlineProbBar,
  Panel,
  PanelHeader,
  RiskBadge,
  TableSkeleton,
  cn,
} from '@/components/ui/Primitives';

const columnHelper = createColumnHelper<CompanySummary>();

const ANALYST_PRESETS: Array<{ label: string; params: Record<string, string> }> = [
  { label: 'Cảnh báo Nguy kịch', params: { risk_level: 'CRITICAL' } },
  { label: 'Rủi ro Cao', params: { risk_level: 'HIGH' } },
  { label: 'An toàn & Sinh lời tốt (ROA ≥ 10%)', params: { risk_level: 'LOW', min_roa: '0.10' } },
  { label: 'Đòn bẩy Thận trọng (Nợ ≤ 50%)', params: { max_debt_ratio: '0.50' } },
];

export function ScreenerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [sorting, setSorting] = useState<SortingState>([
    { id: 'distress_probability', desc: true },
  ]);
  const [density, setDensity] = useState<'compact' | 'comfortable'>('compact');
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [screenerName, setScreenerName] = useState('');
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const q = searchParams.get('q') ?? '';
  const sector = searchParams.get('sector') ?? '';
  const riskLevel = searchParams.get('risk_level') ?? '';
  const minRoa = searchParams.get('min_roa') ?? '';
  const maxDebt = searchParams.get('max_debt_ratio') ?? '';

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value.trim()) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    setSearchParams(next, { replace: true });
  }

  const companiesQuery = useQuery({
    queryKey: ['companies', { q, sector, riskLevel, minRoa, maxDebt }],
    queryFn: () =>
      api.getCompanies({
        limit: 200,
        q: q || undefined,
        sector: sector || undefined,
        risk_level: riskLevel || undefined,
        min_roa: minRoa !== '' ? Number(minRoa) : undefined,
        max_debt_ratio: maxDebt !== '' ? Number(maxDebt) : undefined,
      }),
  });

  const watchlistQuery = useQuery({
    queryKey: ['workspace', 'watchlist'],
    queryFn: api.getWatchlist,
    enabled: Boolean(user),
  });

  const watchedCiks = useMemo(
    () => new Set((watchlistQuery.data ?? []).map((item) => item.cik)),
    [watchlistQuery.data],
  );

  const followMutation = useMutation({
    mutationFn: (cik: string) => api.followCompany(cik),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['workspace', 'watchlist'] });
    },
  });

  const saveScreenerMutation = useMutation({
    mutationFn: () =>
      api.saveScreener(screenerName.trim(), {
        q: q || undefined,
        sector: sector || undefined,
        risk_level: riskLevel || undefined,
        min_roa: minRoa !== '' ? Number(minRoa) : undefined,
        max_debt_ratio: maxDebt !== '' ? Number(maxDebt) : undefined,
      }),
    onSuccess: () => {
      setScreenerName('');
      setSaveMessage('Đã lưu bộ lọc vào Danh mục Cá nhân.');
      void queryClient.invalidateQueries({ queryKey: ['workspace', 'screeners'] });
    },
  });

  const allCompanies = companiesQuery.data ?? [];

  const sectors = useMemo(() => {
    const set = new Set<string>();
    for (const row of allCompanies) {
      if (row.sector) set.add(row.sector);
    }
    return Array.from(set).sort();
  }, [allCompanies]);

  function toggleCompare(id: string) {
    setSelectedTickers((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : prev.length < 4 ? [...prev, id] : prev,
    );
  }

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: 'select',
        header: () => <span className="sr-only">So sánh</span>,
        cell: ({ row }) => {
          const id = row.original.ticker || row.original.cik;
          const checked = selectedTickers.includes(id);
          return (
            <input
              type="checkbox"
              checked={checked}
              onChange={() => toggleCompare(id)}
              aria-label={`Chọn ${id} để so sánh`}
              className="h-3.5 w-3.5 accent-[var(--accent-primary)] cursor-pointer"
            />
          );
        },
      }),
      columnHelper.accessor((row) => row.ticker ?? row.cik, {
        id: 'ticker',
        header: 'Doanh nghiệp',
        cell: ({ row }) => {
          const item = row.original;
          const id = item.ticker || item.cik;
          return (
            <Link
              to={`/us-market/${encodeURIComponent(id)}`}
              className="flex items-center gap-2 no-underline text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
            >
              <span className="font-mono font-bold text-[var(--accent-primary)] w-11 shrink-0">
                {item.ticker ?? '—'}
              </span>
              <span className="truncate max-w-[140px] font-medium">{item.name}</span>
            </Link>
          );
        },
      }),
      columnHelper.accessor('sector', {
        header: 'Nhóm ngành',
        cell: (info) => (
          <span className="text-[var(--text-secondary)] truncate block max-w-[125px]">
            {translateSector(info.getValue())}
          </span>
        ),
      }),
      columnHelper.accessor('latest_fiscal_year', {
        header: 'Năm TC',
        cell: (info) => <span className="num text-[var(--text-secondary)]">{info.getValue() ?? '—'}</span>,
      }),
      columnHelper.accessor('distress_probability', {
        header: 'XS Kiệt quệ',
        cell: (info) => <InlineProbBar value={info.getValue()} tone="risk" />,
      }),
      columnHelper.accessor('risk_level', {
        header: 'Mức rủi ro',
        cell: (info) => <RiskBadge level={info.getValue()} />,
      }),
      columnHelper.accessor((row) => mapPdToSingleHealthScore(row.distress_probability), {
        id: 'unified_health_score',
        header: 'Điểm SK',
        cell: (info) => <InlineProbBar value={info.getValue()} tone="health" />,
      }),
      columnHelper.accessor('altman_z_score', {
        header: 'Altman Z',
        cell: (info) => <span className="num">{formatRatio(info.getValue())}</span>,
      }),
      columnHelper.accessor('roa', {
        header: 'ROA',
        cell: (info) => <span className="num">{formatPct(info.getValue())}</span>,
      }),
      columnHelper.accessor('debt_ratio', {
        header: 'Tỷ lệ nợ',
        cell: (info) => <span className="num">{formatPct(info.getValue())}</span>,
      }),
      columnHelper.display({
        id: 'watch',
        header: () => <span className="sr-only">Theo dõi</span>,
        cell: ({ row }) => {
          const isWatched = watchedCiks.has(row.original.cik);
          return (
            <button
              type="button"
              disabled={!user || followMutation.isPending || isWatched}
              onClick={() => followMutation.mutate(row.original.cik)}
              title={
                !user
                  ? 'Đăng nhập để thêm vào danh sách theo dõi'
                  : isWatched
                    ? 'Đã có trong danh sách theo dõi'
                    : 'Thêm vào danh sách theo dõi'
              }
              aria-label={`Theo dõi ${row.original.ticker ?? row.original.name}`}
              className={cn(
                'p-1 rounded-[4px] transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed',
                isWatched
                  ? 'text-[var(--risk-medium-fg)]'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]',
              )}
            >
              <Star className="h-3.5 w-3.5" fill={isWatched ? 'currentColor' : 'none'} />
            </button>
          );
        },
      }),
    ],
    [selectedTickers, watchedCiks, user, followMutation],
  );

  const table = useReactTable({
    data: allCompanies,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const numericCols = new Set([
    'latest_fiscal_year',
    'distress_probability',
    'unified_health_score',
    'altman_z_score',
    'roa',
    'debt_ratio',
  ]);

  return (
    <div className="space-y-4 min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[1.4rem] font-bold tracking-[-0.025em]">
            Sàng lọc Cổ phiếu & Rủi ro Tín dụng
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Bộ lọc đa tiêu chí trên dữ liệu báo cáo SEC. Chọn nhanh kịch bản mẫu hoặc tự thiết lập
            ngưỡng chỉ số.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {selectedTickers.length >= 2 ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() =>
                navigate(`/compare?source=sec&ids=${encodeURIComponent(selectedTickers.join(','))}`)
              }
            >
              <GitCompare className="h-3.5 w-3.5" aria-hidden="true" />
              So sánh đã chọn ({selectedTickers.length})
            </Button>
          ) : null}

          <div
            className="inline-flex rounded-[6px] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-0.5 text-xs"
            role="group"
            aria-label="Mật độ dòng bảng"
          >
            <button
              type="button"
              onClick={() => setDensity('compact')}
              className={cn(
                'px-2.5 py-1 rounded-[4px] cursor-pointer transition-colors',
                density === 'compact'
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                  : 'text-[var(--text-secondary)]',
              )}
            >
              Gọn
            </button>
            <button
              type="button"
              onClick={() => setDensity('comfortable')}
              className={cn(
                'px-2.5 py-1 rounded-[4px] cursor-pointer transition-colors',
                density === 'comfortable'
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                  : 'text-[var(--text-secondary)]',
              )}
            >
              Thoáng
            </button>
          </div>
        </div>
      </div>

      {/* Analyst Quick-Filter Preset Pills */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-[var(--text-muted)]">Bộ lọc nhanh:</span>
        {ANALYST_PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => setSearchParams(preset.params, { replace: true })}
            className="px-3 py-1.5 text-xs font-medium rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--accent-primary)] hover:border-[var(--accent-primary)]/40 hover:bg-[var(--accent-soft)] transition-all cursor-pointer"
          >
            {preset.label}
          </button>
        ))}
        {(q || sector || riskLevel || minRoa || maxDebt) ? (
          <Button variant="ghost" size="sm" onClick={() => setSearchParams({}, { replace: true })}>
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            Đặt lại
          </Button>
        ) : null}
      </div>

      <Panel className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
          <div className="lg:col-span-2">
            <label htmlFor="filter-q" className="block text-[11px] font-medium text-[var(--text-secondary)] mb-1">
              Tìm mã CK, tên công ty hoặc CIK
            </label>
            <input
              id="filter-q"
              type="search"
              value={q}
              onChange={(e) => updateParam('q', e.target.value)}
              placeholder="VD: AAPL, Airlines, 0000320193"
              className="w-full h-9 px-3 text-xs bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[6px]"
            />
          </div>

          <div>
            <label htmlFor="filter-risk" className="block text-[11px] font-medium text-[var(--text-secondary)] mb-1">
              Mức rủi ro
            </label>
            <select
              id="filter-risk"
              value={riskLevel}
              onChange={(e) => updateParam('risk_level', e.target.value)}
              className="w-full h-9 px-2.5 text-xs bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[6px]"
            >
              <option value="">Tất cả mức</option>
              <option value="LOW">Rủi ro thấp</option>
              <option value="MEDIUM">Trung bình</option>
              <option value="HIGH">Rủi ro cao</option>
              <option value="CRITICAL">Nguy kịch</option>
            </select>
          </div>

          <div>
            <label htmlFor="filter-sector" className="block text-[11px] font-medium text-[var(--text-secondary)] mb-1">
              Nhóm ngành
            </label>
            <select
              id="filter-sector"
              value={sector}
              onChange={(e) => updateParam('sector', e.target.value)}
              className="w-full h-9 px-2.5 text-xs bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[6px]"
            >
              <option value="">Tất cả ngành</option>
              {sectors.map((s) => (
                <option key={s} value={s}>
                  {translateSector(s)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="filter-roa" className="block text-[11px] font-medium text-[var(--text-secondary)] mb-1">
              ROA tối thiểu (thập phân)
            </label>
            <input
              id="filter-roa"
              type="number"
              step="0.01"
              value={minRoa}
              onChange={(e) => updateParam('min_roa', e.target.value)}
              placeholder="0.05"
              className="w-full h-9 px-2.5 text-xs num bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[6px]"
            />
          </div>

          <div>
            <label htmlFor="filter-debt" className="block text-[11px] font-medium text-[var(--text-secondary)] mb-1">
              Tỷ lệ nợ tối đa
            </label>
            <input
              id="filter-debt"
              type="number"
              step="0.05"
              value={maxDebt}
              onChange={(e) => updateParam('max_debt_ratio', e.target.value)}
              placeholder="0.80"
              className="w-full h-9 px-2.5 text-xs num bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[6px]"
            />
          </div>
        </div>

        <div className="mt-3 pt-3 border-t border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            <span className="num font-semibold text-[var(--text-primary)]">{allCompanies.length}</span>
            <span>doanh nghiệp phù hợp</span>
          </div>

          {user ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (screenerName.trim()) saveScreenerMutation.mutate();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={screenerName}
                onChange={(e) => setScreenerName(e.target.value)}
                placeholder="Đặt tên bộ lọc để lưu..."
                aria-label="Tên bộ lọc cần lưu"
                className="h-8 px-2.5 text-xs bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[6px] w-48"
              />
              <Button
                type="submit"
                variant="secondary"
                size="sm"
                disabled={!screenerName.trim() || saveScreenerMutation.isPending}
              >
                <BookmarkPlus className="h-3.5 w-3.5" aria-hidden="true" />
                Lưu bộ lọc
              </Button>
              {saveMessage ? (
                <span className="text-xs text-[var(--risk-low-fg)]">{saveMessage}</span>
              ) : null}
            </form>
          ) : null}
        </div>
      </Panel>

      <Panel className="min-w-0 overflow-hidden">
        <PanelHeader
          title="Kết quả Sàng lọc Doanh nghiệp"
          description="Bấm vào tiêu đề cột để sắp xếp. Đánh dấu từ 2 đến 4 doanh nghiệp để so sánh song song."
        />
        {companiesQuery.isLoading ? (
          <TableSkeleton rows={10} />
        ) : companiesQuery.isError ? (
          <ErrorState
            message={
              companiesQuery.error instanceof Error
                ? companiesQuery.error.message
                : 'Không thể tải danh sách doanh nghiệp.'
            }
            onRetry={() => void companiesQuery.refetch()}
          />
        ) : allCompanies.length === 0 ? (
          <EmptyState
            title="Không tìm thấy doanh nghiệp phù hợp"
            description="Hãy nới rộng điều kiện ROA, tỷ lệ nợ hoặc xóa từ khóa tìm kiếm."
            action={
              <Button variant="secondary" size="sm" onClick={() => setSearchParams({})}>
                Xóa toàn bộ bộ lọc
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr
                    key={headerGroup.id}
                    className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[11px] uppercase tracking-wider text-[var(--text-muted)]"
                  >
                    {headerGroup.headers.map((header) => {
                      const isNumeric = numericCols.has(header.column.id);
                      const canSort = header.column.getCanSort();
                      return (
                        <th
                          key={header.id}
                          className={cn(
                            'py-2.5 px-2 font-semibold whitespace-nowrap',
                            isNumeric && 'text-right',
                          )}
                        >
                          {header.isPlaceholder ? null : canSort ? (
                            <button
                              type="button"
                              onClick={header.column.getToggleSortingHandler()}
                              className={cn(
                                'inline-flex items-center gap-1 hover:text-[var(--text-primary)] cursor-pointer bg-transparent border-0 p-0 text-inherit uppercase',
                                isNumeric && 'flex-row-reverse',
                              )}
                            >
                              {flexRender(header.column.columnDef.header, header.getContext())}
                              <ArrowUpDown className="h-3 w-3 opacity-60" aria-hidden="true" />
                            </button>
                          ) : (
                            flexRender(header.column.columnDef.header, header.getContext())
                          )}
                        </th>
                      );
                    })}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)] text-xs">
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="hover:bg-[var(--bg-hover)] transition-colors">
                    {row.getVisibleCells().map((cell) => {
                      const isNumeric = numericCols.has(cell.column.id);
                      return (
                        <td
                          key={cell.id}
                          className={cn(
                            'px-2 whitespace-nowrap',
                            density === 'compact' ? 'py-2' : 'py-3',
                            isNumeric && 'text-right',
                          )}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
