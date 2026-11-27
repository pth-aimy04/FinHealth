import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, Lock, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import {
  Button,
  EmptyState,
  Panel,
  PanelHeader,
  TableSkeleton,
} from '@/components/ui/Primitives';

export function WorkspacePage() {
  const { user, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const watchlistQuery = useQuery({
    queryKey: ['workspace', 'watchlist'],
    queryFn: api.getWatchlist,
    enabled: Boolean(user),
  });

  const screenersQuery = useQuery({
    queryKey: ['workspace', 'screeners'],
    queryFn: api.getScreeners,
    enabled: Boolean(user),
  });

  const analysesQuery = useQuery({
    queryKey: ['workspace', 'analyses'],
    queryFn: api.getSavedAnalyses,
    enabled: Boolean(user),
  });

  const deleteMutation = useMutation({
    mutationFn: ({
      collection,
      id,
    }: {
      collection: 'watchlist' | 'screeners' | 'analyses';
      id: number;
    }) => api.deleteSavedItem(collection, id),
    onSuccess: (_data, vars) => {
      void queryClient.invalidateQueries({ queryKey: ['workspace', vars.collection] });
    },
  });

  if (authLoading) {
    return <TableSkeleton rows={5} />;
  }

  if (!user) {
    return (
      <Panel>
        <div className="px-6 py-14 text-center space-y-3">
          <Lock className="mx-auto h-8 w-8 text-[var(--text-muted)]" strokeWidth={1.5} />
          <h1 className="text-base font-semibold">Đăng nhập để mở Không gian Cá nhân</h1>
          <p className="text-xs text-[var(--text-secondary)] max-w-md mx-auto">
            Danh sách theo dõi, bộ lọc đã lưu và các báo cáo chấm điểm riêng tư được bảo vệ theo
            đúng tài khoản đã xác thực của bạn.
          </p>
          <div className="pt-2">
            <Link to="/account" className="no-underline">
              <Button variant="primary">Đăng nhập hoặc Đăng ký</Button>
            </Link>
          </div>
        </div>
      </Panel>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[1.375rem] font-semibold tracking-[-0.02em]">
          Không gian Cá nhân
        </h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          Đang đăng nhập dưới tên <span className="font-medium text-[var(--text-primary)]">{user.display_name}</span> ({user.email}).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel>
          <PanelHeader
            title={`Danh sách Theo dõi (${watchlistQuery.data?.length ?? 0})`}
            description="Các doanh nghiệp SEC bạn đang theo dõi."
          />
          {watchlistQuery.isLoading ? (
            <TableSkeleton rows={4} />
          ) : (watchlistQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="Danh sách theo dõi đang trống"
              description="Bấm biểu tượng ngôi sao ở Bộ lọc doanh nghiệp hoặc Hồ sơ công ty để thêm vào đây."
              action={
                <Link to="/screener" className="no-underline">
                  <Button variant="secondary" size="sm">Mở Bộ lọc doanh nghiệp</Button>
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-[var(--border-subtle)] text-xs">
              {(watchlistQuery.data ?? []).map((item) => (
                <li key={item.id} className="px-4 py-3 flex items-center justify-between gap-2">
                  <Link
                    to={`/companies/${encodeURIComponent(item.ticker || item.cik)}`}
                    className="flex items-center gap-2 no-underline text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
                  >
                    <span className="font-mono font-semibold text-[var(--accent-primary)]">
                      {item.ticker ?? item.cik}
                    </span>
                    <span className="truncate max-w-[220px]">{item.name}</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate({ collection: 'watchlist', id: item.id })}
                    aria-label={`Bỏ theo dõi ${item.name}`}
                    className="p-1.5 text-[var(--text-muted)] hover:text-[var(--risk-critical-fg)] cursor-pointer bg-transparent border-0"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel>
          <PanelHeader
            title={`Bộ lọc Đã lưu (${screenersQuery.data?.length ?? 0})`}
            description="Mở lại nhanh các tiêu chí sàng lọc đã thiết lập."
          />
          {screenersQuery.isLoading ? (
            <TableSkeleton rows={4} />
          ) : (screenersQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="Chưa có bộ lọc nào được lưu"
              description="Thiết lập điều kiện lọc trên trang Bộ lọc doanh nghiệp rồi nhấn Lưu bộ lọc."
            />
          ) : (
            <ul className="divide-y divide-[var(--border-subtle)] text-xs">
              {(screenersQuery.data ?? []).map((sc) => {
                const qs = new URLSearchParams();
                for (const [k, v] of Object.entries(sc.filters)) {
                  if (v !== null && v !== undefined && v !== '') qs.set(k, String(v));
                }
                return (
                  <li key={sc.id} className="px-4 py-3 flex items-center justify-between gap-2">
                    <Link
                      to={`/screener?${qs.toString()}`}
                      className="inline-flex items-center gap-1.5 font-medium text-[var(--text-primary)] hover:text-[var(--accent-primary)] no-underline"
                    >
                      <span>{sc.name}</span>
                      <ArrowUpRight className="h-3.5 w-3.5 opacity-60" />
                    </Link>
                    <button
                      type="button"
                      onClick={() => deleteMutation.mutate({ collection: 'screeners', id: sc.id })}
                      aria-label={`Xóa bộ lọc ${sc.name}`}
                      className="p-1.5 text-[var(--text-muted)] hover:text-[var(--risk-critical-fg)] cursor-pointer bg-transparent border-0"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel className="lg:col-span-2">
          <PanelHeader
            title={`Phân tích Tự nhập Đã lưu (${analysesQuery.data?.length ?? 0})`}
            description="Các hồ sơ chấm điểm báo cáo tự nhập được máy chủ tính toán lại và lưu riêng tư."
          />
          {analysesQuery.isLoading ? (
            <TableSkeleton rows={3} />
          ) : (analysesQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="Chưa có phân tích nào được lưu"
              description="Chấm điểm một báo cáo tự nhập trong mục Mô hình & Chấm điểm rồi lưu lại tại đây."
              action={
                <Link to="/models" className="no-underline">
                  <Button variant="secondary" size="sm">Mở Phòng thí nghiệm Mô hình</Button>
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-[var(--border-subtle)] text-xs">
              {(analysesQuery.data ?? []).map((item) => (
                <li key={item.id} className="px-4 py-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium text-[var(--text-primary)]">{item.name}</div>
                    <div className="text-[var(--text-secondary)]">
                      Mô hình <span className="font-mono">{item.model_version}</span> · Đã lưu ngày{' '}
                      {formatDate(item.created_at)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate({ collection: 'analyses', id: item.id })}
                    aria-label={`Xóa phân tích ${item.name}`}
                    className="p-1.5 text-[var(--text-muted)] hover:text-[var(--risk-critical-fg)] cursor-pointer bg-transparent border-0"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
