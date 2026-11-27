import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, Lock, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import {
  Button,
  EmptyState,
  PageHeader,
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
      <Panel ruled>
        <div className="px-6 py-14 text-center space-y-3">
          <Lock className="mx-auto h-7 w-7 text-[var(--text-muted)]" strokeWidth={1.5} />
          <h1 className="font-editorial text-lg font-bold">Đăng nhập để mở Không gian Cá nhân</h1>
          <p className="text-[13px] text-[var(--text-secondary)] max-w-md mx-auto">
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
    <div className="space-y-5 animate-view">
      <PageHeader
        title="Không gian Cá nhân"
        description={`Đang đăng nhập dưới tên ${user.display_name} (${user.email}).`}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel ruled className="overflow-hidden">
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
                <Link to="/us-market" className="no-underline">
                  <Button variant="secondary" size="sm">Mở Thị trường Mỹ (SEC)</Button>
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-[var(--border-subtle)] text-[13px] list-none p-0 m-0">
              {(watchlistQuery.data ?? []).map((item) => (
                <li key={item.id} className="px-4 py-3 flex items-center justify-between gap-2 hover:bg-[var(--bg-hover)]/45">
                  <Link
                    to={`/us-market/${encodeURIComponent(item.ticker || item.cik)}`}
                    className="flex items-center gap-2 no-underline text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
                  >
                    <span className="num text-xs font-bold px-1.5 py-0.5 rounded-[2px] bg-[var(--accent-soft)] text-[var(--accent-primary)] border border-[var(--accent-border)]">
                      {item.ticker ?? item.cik}
                    </span>
                    <span className="truncate max-w-[240px] font-semibold">{item.name}</span>
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

        <Panel ruled className="overflow-hidden">
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
            <ul className="divide-y divide-[var(--border-subtle)] text-[13px] list-none p-0 m-0">
              {(screenersQuery.data ?? []).map((sc) => {
                const qs = new URLSearchParams();
                for (const [k, v] of Object.entries(sc.filters)) {
                  if (v !== null && v !== undefined && v !== '') qs.set(k, String(v));
                }
                return (
                  <li key={sc.id} className="px-4 py-3 flex items-center justify-between gap-2 hover:bg-[var(--bg-hover)]/45">
                    <Link
                      to={`/us-market?${qs.toString()}`}
                      className="inline-flex items-center gap-1.5 font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)] no-underline"
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

        <Panel className="lg:col-span-2 overflow-hidden">
          <PanelHeader
            title={`Phân tích Tự nhập Đã lưu (${analysesQuery.data?.length ?? 0})`}
            description="Các hồ sơ chấm điểm báo cáo tự nhập được máy chủ tính toán lại và lưu riêng tư."
          />
          {analysesQuery.isLoading ? (
            <TableSkeleton rows={3} />
          ) : (analysesQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="Chưa có phân tích nào được lưu"
              description="Quản lý danh bạ doanh nghiệp và nhập BCTC để theo dõi sức khỏe tài chính chuyên sâu."
              action={
                <Link to="/portfolio" className="no-underline">
                  <Button variant="secondary" size="sm">Mở Danh bạ Doanh nghiệp</Button>
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-[var(--border-subtle)] text-[13px] list-none p-0 m-0">
              {(analysesQuery.data ?? []).map((item) => (
                <li key={item.id} className="px-4 py-3 flex items-center justify-between gap-3 hover:bg-[var(--bg-hover)]/45">
                  <div>
                    <div className="font-semibold text-[var(--text-primary)]">{item.name}</div>
                    <div className="text-xs text-[var(--text-secondary)]">
                      Mô hình <span className="font-mono">{item.model_version}</span> · Đã lưu ngày{' '}
                      <span className="num">{formatDate(item.created_at)}</span>
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
