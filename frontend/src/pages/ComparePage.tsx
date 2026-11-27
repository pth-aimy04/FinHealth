import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, X } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import { formatPct, formatRatio, formatScore } from '@/lib/format';
import {
  Button,
  EmptyState,
  ErrorState,
  Panel,
  PanelHeader,
  TableSkeleton,
  cn,
} from '@/components/ui/Primitives';
import { CompareTrendChart } from '@/components/charts/CompareStressCharts';

const DEFAULT_PEERS = ['AAPL', 'MSFT', 'AAL'];

export function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [inputTicker, setInputTicker] = useState('');

  const idsParam = searchParams.get('ids');
  const identifiers = idsParam
    ? idsParam
        .split(',')
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean)
    : DEFAULT_PEERS;
  const periodPolicy =
    searchParams.get('policy') === 'common_fiscal_year'
      ? 'common_fiscal_year'
      : 'latest_annual';

  function updateIds(next: string[]) {
    const params = new URLSearchParams(searchParams);
    params.set('ids', next.join(','));
    setSearchParams(params, { replace: true });
  }

  function addTicker(event: React.FormEvent) {
    event.preventDefault();
    const cleaned = inputTicker.trim().toUpperCase();
    if (!cleaned || identifiers.includes(cleaned) || identifiers.length >= 5) return;
    updateIds([...identifiers, cleaned]);
    setInputTicker('');
  }

  const compareQuery = useQuery({
    queryKey: ['compare', identifiers.join(','), periodPolicy],
    queryFn: () => api.compareCompanies(identifiers, periodPolicy),
    enabled: identifiers.length >= 2,
  });

  const companies = compareQuery.data?.companies ?? [];

  const chartData = companies.map((c) => ({
    name: c.ticker ?? c.cik,
    distress: typeof c.distress_probability === 'number' ? Number((c.distress_probability * 100).toFixed(1)) : 0,
    health: typeof c.composite_health_score === 'number' ? Number(c.composite_health_score.toFixed(1)) : 0,
  }));

  const metricRows: Array<{
    key: string;
    label: string;
    format: (v: number | null | undefined) => string;
    get: (c: (typeof companies)[number]) => number | null | undefined;
  }> = [
    { key: 'distress_probability', label: 'Xác suất kiệt quệ P(t+1)', format: formatPct, get: (c) => c.distress_probability },
    { key: 'composite_health_score', label: 'Điểm Sức khỏe Tổng hợp', format: formatScore, get: (c) => c.composite_health_score },
    { key: 'altman_z_score', label: 'Chỉ số Altman Z-Score', format: formatRatio, get: (c) => c.altman_z_score },
    { key: 'roa', label: 'Tỷ suất sinh lời tài sản (ROA)', format: formatPct, get: (c) => c.roa },
    { key: 'roe', label: 'Tỷ suất sinh lời vốn CSH (ROE)', format: formatPct, get: (c) => c.roe },
    { key: 'operating_margin', label: 'Biên lợi nhuận hoạt động', format: formatPct, get: (c) => c.operating_margin },
    { key: 'debt_ratio', label: 'Tỷ lệ Nợ / Tổng tài sản', format: formatPct, get: (c) => c.debt_ratio },
    { key: 'current_ratio', label: 'Hệ số thanh toán hiện hành', format: formatRatio, get: (c) => c.current_ratio },
    { key: 'ocf_ratio', label: 'Tỷ lệ dòng tiền hoạt động (OCF)', format: formatPct, get: (c) => c.ocf_ratio },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[1.375rem] font-semibold tracking-[-0.02em]">
            So sánh Doanh nghiệp Cùng ngành
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Đối chiếu trực tiếp từ 2 đến 5 doanh nghiệp cạnh nhau cùng trung vị nhóm ngành.
          </p>
        </div>

        <div
          className="inline-flex rounded-[4px] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-0.5 text-xs"
          role="group"
          aria-label="Chính sách căn chỉnh kỳ tài chính"
        >
          {(
            [
              { id: 'latest_annual', label: 'Năm mới nhất' },
              { id: 'common_fiscal_year', label: 'Cùng năm tài chính' },
            ] as const
          ).map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => {
                const next = new URLSearchParams(searchParams);
                next.set('policy', opt.id);
                setSearchParams(next, { replace: true });
              }}
              className={cn(
                'px-2.5 py-1 rounded-[3px] cursor-pointer',
                periodPolicy === opt.id
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] font-medium'
                  : 'text-[var(--text-secondary)]',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <Panel className="p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {identifiers.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-xs font-mono font-medium"
            >
              {id}
              <button
                type="button"
                onClick={() => updateIds(identifiers.filter((item) => item !== id))}
                aria-label={`Bỏ ${id}`}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer bg-transparent border-0 p-0"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ))}
        </div>

        <form onSubmit={addTicker} className="flex items-center gap-2">
          <input
            type="text"
            value={inputTicker}
            onChange={(e) => setInputTicker(e.target.value)}
            placeholder="Thêm mã (VD: F, BA)"
            aria-label="Thêm mã chứng khoán để so sánh"
            className="h-8 px-2.5 text-xs font-mono uppercase bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px] w-44"
          />
          <Button type="submit" variant="secondary" size="sm" disabled={identifiers.length >= 5}>
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            Thêm
          </Button>
        </form>
      </Panel>

      {identifiers.length < 2 ? (
        <Panel>
          <EmptyState
            title="Cần chọn tối thiểu 2 doanh nghiệp"
            description="Hãy thêm ít nhất 2 mã chứng khoán hoặc CIK ở thanh trên để lập bảng so sánh."
          />
        </Panel>
      ) : compareQuery.isLoading ? (
        <Panel>
          <TableSkeleton rows={8} />
        </Panel>
      ) : compareQuery.isError ? (
        <ErrorState
          message={
            compareQuery.error instanceof Error
              ? compareQuery.error.message
              : 'Không thể thực hiện so sánh.'
          }
          onRetry={() => void compareQuery.refetch()}
        />
      ) : (
        <>
          <Panel>
            <PanelHeader
              title="Đối chiếu Xác suất Kiệt quệ & Điểm Sức khỏe"
              description={
                compareQuery.data?.common_fiscal_year
                  ? `Đồng bộ trên cùng năm tài chính FY${compareQuery.data.common_fiscal_year}`
                  : 'Đối chiếu trên báo cáo thường niên 10-K mới nhất của từng doanh nghiệp'
              }
            />
            <div className="p-4 h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 16, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-primary)', fontSize: 12 }} />
                  <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-surface)',
                      border: '1px solid var(--border-strong)',
                      borderRadius: '4px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="health" name="Điểm sức khỏe (0-100)" fill="#0F766E" radius={[3, 3, 0, 0]} maxBarSize={42} />
                  <Bar dataKey="distress" name="XS Kiệt quệ (%)" fill="#DC2626" radius={[3, 3, 0, 0]} maxBarSize={42} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          {compareQuery.data ? (
            <Panel>
              <PanelHeader
                title="Xu hướng Lịch sử Nhiều năm giữa Các Doanh nghiệp"
                description="Chuyển đổi linh hoạt giữa sinh lời, đòn bẩy, dòng tiền và khả năng thanh toán."
              />
              <div className="p-4">
                <CompareTrendChart data={compareQuery.data} />
              </div>
            </Panel>
          ) : null}

          <Panel>
            <PanelHeader
              title="Ma trận Chỉ số Tài chính Chi tiết"
              description="Cột Trung vị nhóm tính trên toàn bộ kỳ báo cáo năm gần nhất của tập dữ liệu."
            />
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                    <th className="py-2.5 px-4 font-medium">Chỉ tiêu</th>
                    {companies.map((c) => (
                      <th key={c.cik} className="py-2.5 px-3 font-medium text-right">
                        <Link
                          to={`/companies/${encodeURIComponent(c.ticker || c.cik)}`}
                          className="font-mono text-[var(--accent-primary)] hover:underline no-underline"
                        >
                          {c.ticker ?? c.cik} (FY{c.fiscal_year})
                        </Link>
                      </th>
                    ))}
                    <th className="py-2.5 px-4 font-medium text-right">Trung vị nhóm</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {metricRows.map((row) => (
                    <tr key={row.key} className="hover:bg-[var(--bg-hover)]">
                      <td className="py-2.5 px-4 font-medium text-[var(--text-primary)]">
                        {row.label}
                      </td>
                      {companies.map((c) => (
                        <td key={c.cik} className="py-2.5 px-3 text-right num">
                          {row.format(row.get(c))}
                        </td>
                      ))}
                      <td className="py-2.5 px-4 text-right num text-[var(--text-secondary)]">
                        {row.format(compareQuery.data?.cohort_medians[row.key])}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
