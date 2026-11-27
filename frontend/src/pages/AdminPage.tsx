import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import {
  Button,
  EmptyState,
  MetricTile,
  Panel,
  PanelHeader,
  TableSkeleton,
} from '@/components/ui/Primitives';

export function AdminPage() {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [tickerInput, setTickerInput] = useState('');
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  const overviewQuery = useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: api.getAdminOverview,
    enabled: isAdmin,
  });

  const jobsQuery = useQuery({
    queryKey: ['admin', 'ingestion'],
    queryFn: () => api.getAdminIngestion(),
    enabled: isAdmin,
    refetchInterval: 10_000,
  });

  const eventsQuery = useQuery({
    queryKey: ['admin', 'ingestion-events', selectedRunId],
    queryFn: () => api.getIngestionEvents(selectedRunId!),
    enabled: isAdmin && selectedRunId !== null,
  });

  const usersQuery = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => api.getAdminUsers(),
    enabled: isAdmin,
  });

  const auditQuery = useQuery({
    queryKey: ['admin', 'audit'],
    queryFn: api.getAdminAudit,
    enabled: isAdmin,
  });

  const submitJobMutation = useMutation({
    mutationFn: () => api.submitIngestion(tickerInput.trim().toUpperCase()),
    onSuccess: () => {
      setTickerInput('');
      void queryClient.invalidateQueries({ queryKey: ['admin', 'ingestion'] });
    },
  });

  const retryJobMutation = useMutation({
    mutationFn: (id: number) => api.retryIngestion(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'ingestion'] });
    },
  });

  const toggleUserMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => api.setUserActive(id, active),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });

  if (!isAdmin) {
    return (
      <Panel>
        <div className="px-6 py-14 text-center space-y-2">
          <ShieldAlert className="mx-auto h-8 w-8 text-[var(--risk-critical-fg)]" />
          <h1 className="text-base font-semibold">Yêu cầu Quyền Quản trị viên</h1>
          <p className="text-xs text-[var(--text-secondary)]">
            Hãy đăng nhập bằng tài khoản quản trị viên đã xác thực để điều hành hàng đợi thu thập
            SEC, quản lý người dùng và xem nhật ký kiểm toán.
          </p>
        </div>
      </Panel>
    );
  }

  const ov = overviewQuery.data;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[1.375rem] font-semibold tracking-[-0.02em]">
          Quản trị Hệ thống & Dây chuyền SEC EDGAR
        </h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          Giám sát sức khỏe hệ thống, hàng đợi nạp dữ liệu SEC có giới hạn tốc độ, quản lý tài khoản
          và nhật ký kiểm toán.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricTile
          label="Kết nối Cơ sở dữ liệu"
          value={ov?.database_connected ? 'Trực tuyến' : 'Ngoại tuyến'}
          accent={ov?.database_connected ? 'low' : 'critical'}
        />
        <MetricTile
          label="Worker Nạp dữ liệu SEC"
          value={ov?.worker_enabled ? 'Đang bật' : 'Đang tắt'}
          accent={ov?.worker_enabled ? 'low' : 'medium'}
        />
        <MetricTile
          label="Cấu hình Gửi Email SMTP"
          value={ov?.email_configured ? 'Đã cấu hình' : 'Chưa cấu hình'}
        />
        <MetricTile
          label="Lần chạy thành công gần nhất"
          value={ov?.last_success ? formatDate(ov.last_success) : '—'}
        />
      </div>

      <Panel>
        <PanelHeader
          title="Hàng đợi Nạp dữ liệu SEC EDGAR"
          description="Gửi mã chứng khoán hoặc CIK để đưa vào hàng đợi cập nhật báo cáo SEC."
          actions={
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (tickerInput.trim()) submitJobMutation.mutate();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value)}
                placeholder="Mã CK hoặc CIK"
                aria-label="Nhập mã chứng khoán hoặc CIK để nạp dữ liệu"
                className="h-8 px-2.5 text-xs font-mono uppercase bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px] w-36"
              />
              <Button type="submit" variant="primary" size="sm" disabled={submitJobMutation.isPending}>
                <Play className="h-3.5 w-3.5" />
                Đưa vào hàng đợi
              </Button>
            </form>
          }
        />
        {jobsQuery.isLoading ? (
          <TableSkeleton rows={4} />
        ) : (jobsQuery.data ?? []).length === 0 ? (
          <EmptyState
            title="Chưa có phiên nạp dữ liệu nào"
            description="Các tác vụ cập nhật dữ liệu từ SEC EDGAR sẽ hiển thị tại đây."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="py-2 px-4 font-medium">Mã phiên</th>
                  <th className="py-2 px-3 font-medium">Định danh</th>
                  <th className="py-2 px-3 font-medium">Trạng thái</th>
                  <th className="py-2 px-3 font-medium">Giai đoạn</th>
                  <th className="py-2 px-4 font-medium text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {(jobsQuery.data ?? []).map((job) => (
                  <tr key={job.id} className="hover:bg-[var(--bg-hover)]">
                    <td className="py-2 px-4 font-mono">#{job.id}</td>
                    <td className="py-2 px-3 font-mono font-semibold">{job.identifier}</td>
                    <td className="py-2 px-3 uppercase">{job.status}</td>
                    <td className="py-2 px-3 text-[var(--text-secondary)]">{job.stage}</td>
                    <td className="py-2 px-4 text-right space-x-2">
                      <Button variant="ghost" size="sm" onClick={() => setSelectedRunId(job.id)}>
                        Nhật ký
                      </Button>
                      {job.status === 'failed' ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => retryJobMutation.mutate(job.id)}
                        >
                          <RefreshCw className="h-3 w-3" /> Chạy lại
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {selectedRunId !== null ? (
        <Panel>
          <PanelHeader title={`Sự kiện của Phiên #${selectedRunId}`} />
          <div className="p-4 space-y-1.5 text-xs font-mono">
            {(eventsQuery.data ?? []).map((ev, idx) => (
              <div key={idx} className="flex items-center justify-between gap-2">
                <span>
                  [{ev.stage}] {ev.message}
                </span>
                <span className="text-[var(--text-muted)]">{formatDate(ev.created_at)}</span>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel>
          <PanelHeader title="Quản lý Tài khoản Người dùng" />
          <div className="divide-y divide-[var(--border-subtle)] text-xs">
            {(usersQuery.data ?? []).map((u) => (
              <div key={u.id} className="px-4 py-2.5 flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium">
                    {u.display_name}{' '}
                    <span className="font-mono text-[var(--text-muted)]">({u.role})</span>
                  </div>
                  <div className="text-[var(--text-secondary)]">{u.email}</div>
                </div>
                {u.role !== 'admin' ? (
                  <Button
                    variant={u.active ? 'danger' : 'secondary'}
                    size="sm"
                    onClick={() => toggleUserMutation.mutate({ id: u.id, active: !u.active })}
                  >
                    {u.active ? 'Khóa' : 'Kích hoạt'}
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Nhật ký Kiểm toán Quản trị (Audit Log)" />
          <div className="divide-y divide-[var(--border-subtle)] text-xs">
            {(auditQuery.data ?? []).slice(0, 15).map((entry) => (
              <div key={entry.id} className="px-4 py-2.5 flex items-center justify-between gap-2">
                <span className="font-mono">
                  {entry.action} → #{entry.target}
                </span>
                <span className="text-[var(--text-muted)]">{formatDate(entry.created_at)}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
