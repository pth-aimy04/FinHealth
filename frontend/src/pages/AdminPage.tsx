import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import {
  Button,
  EmptyState,
  MetricStrip,
  MetricTile,
  PageHeader,
  Panel,
  PanelHeader,
  TableSkeleton,
  cn,
} from '@/components/ui/Primitives';
import { ModelLabPage } from './ModelLabPage';
import { ClusterMapPage } from './ClusterMapPage';

type AdminTab = 'system' | 'models' | 'clusters';

export function AdminPage({ initialTab = 'system' }: { initialTab?: AdminTab }) {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<AdminTab>(initialTab);
  const [tickerInput, setTickerInput] = useState('');
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  const overviewQuery = useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: api.getAdminOverview,
    enabled: isAdmin && activeTab === 'system',
  });

  const jobsQuery = useQuery({
    queryKey: ['admin', 'ingestion'],
    queryFn: () => api.getAdminIngestion(),
    enabled: isAdmin && activeTab === 'system',
    refetchInterval: 10_000,
  });

  const eventsQuery = useQuery({
    queryKey: ['admin', 'ingestion-events', selectedRunId],
    queryFn: () => api.getIngestionEvents(selectedRunId!),
    enabled: isAdmin && activeTab === 'system' && selectedRunId !== null,
  });

  const usersQuery = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => api.getAdminUsers(),
    enabled: isAdmin && activeTab === 'system',
  });

  const auditQuery = useQuery({
    queryKey: ['admin', 'audit'],
    queryFn: api.getAdminAudit,
    enabled: isAdmin && activeTab === 'system',
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
      <Panel ruled>
        <div className="px-6 py-14 text-center space-y-2">
          <ShieldAlert className="mx-auto h-7 w-7 text-[var(--risk-critical-fg)]" />
          <h1 className="font-editorial text-lg font-bold">Yêu cầu Quyền Quản trị viên</h1>
          <p className="text-[13px] text-[var(--text-secondary)] max-w-lg mx-auto">
            Hãy đăng nhập bằng tài khoản quản trị viên đã xác thực để điều hành hệ thống, quản trị
            mô hình MLOps, quản lý người dùng và xem nhật ký kiểm toán.
          </p>
        </div>
      </Panel>
    );
  }

  const ov = overviewQuery.data;

  return (
    <div className="space-y-5 animate-view">
      <PageHeader
        title="Cổng Quản trị Hệ thống & MLOps Nội bộ"
        description="Khu vực nội bộ dành riêng cho Quản trị viên: vận hành hàng đợi SEC EDGAR, quản trị người dùng, kiểm định phiên bản mô hình và bản đồ phân cụm PCA."
      />

      <div
        className="flex flex-wrap items-center gap-1 border-b border-[var(--border-strong)]"
        role="tablist"
        aria-label="Phân mục Quản trị & MLOps"
      >
        {(
          [
            { id: 'system', label: 'Hệ thống, SEC Ingestion & Tài khoản' },
            { id: 'models', label: 'Quản trị Mô hình (MLOps)' },
            { id: 'clusters', label: 'Bản đồ Phân cụm (PCA)' },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-4 py-2.5 text-[13px] font-semibold border-b-2 -mb-px transition-colors cursor-pointer bg-transparent',
              activeTab === tab.id
                ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'models' ? <ModelLabPage /> : null}
      {activeTab === 'clusters' ? <ClusterMapPage /> : null}

      {activeTab === 'system' ? (
        <div className="space-y-5">
          <MetricStrip columns={4}>
            <MetricTile
              bare
              label="Kết nối Cơ sở dữ liệu"
              value={ov?.database_connected ? 'Trực tuyến' : 'Ngoại tuyến'}
              accent={ov?.database_connected ? 'low' : 'critical'}
            />
            <MetricTile
              bare
              label="Worker Nạp dữ liệu SEC"
              value={ov?.worker_enabled ? 'Đang bật' : 'Đang tắt'}
              accent={ov?.worker_enabled ? 'low' : 'medium'}
            />
            <MetricTile
              bare
              label="Cấu hình Gửi Email SMTP"
              value={ov?.email_configured ? 'Đã cấu hình' : 'Chưa cấu hình'}
            />
            <MetricTile
              bare
              label="Lần chạy thành công gần nhất"
              value={ov?.last_success ? formatDate(ov.last_success) : '—'}
            />
          </MetricStrip>

          <Panel ruled className="overflow-hidden">
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
                    className="field-control !h-8 !w-36 font-mono uppercase"
                  />
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={submitJobMutation.isPending}
                  >
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
                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Mã phiên</th>
                      <th>Định danh</th>
                      <th>Trạng thái</th>
                      <th>Giai đoạn</th>
                      <th className="text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(jobsQuery.data ?? []).map((job) => (
                      <tr key={job.id}>
                        <td className="num font-semibold">#{job.id}</td>
                        <td className="num font-bold text-[var(--accent-primary)]">{job.identifier}</td>
                        <td className="uppercase text-xs font-semibold">{job.status}</td>
                        <td className="text-[var(--text-secondary)]">{job.stage}</td>
                        <td className="text-right space-x-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedRunId(job.id)}
                          >
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
            <Panel className="overflow-hidden">
              <PanelHeader title={`Sự kiện của Phiên #${selectedRunId}`} />
              <div className="p-4 space-y-1.5 text-xs font-mono bg-[var(--bg-header)]">
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
            <Panel className="overflow-hidden">
              <PanelHeader title="Quản lý Tài khoản Người dùng" />
              <div className="divide-y divide-[var(--border-subtle)] text-[13px]">
                {(usersQuery.data ?? []).map((u) => (
                  <div key={u.id} className="px-4 py-2.5 flex items-center justify-between gap-2">
                    <div>
                      <div className="font-semibold">
                        {u.display_name}{' '}
                        <span className="font-mono text-xs text-[var(--text-muted)]">({u.role})</span>
                      </div>
                      <div className="text-xs text-[var(--text-secondary)] font-mono">{u.email}</div>
                    </div>
                    {u.role !== 'admin' ? (
                      <Button
                        variant={u.active ? 'danger' : 'secondary'}
                        size="sm"
                        onClick={() =>
                          toggleUserMutation.mutate({ id: u.id, active: !u.active })
                        }
                      >
                        {u.active ? 'Khóa' : 'Kích hoạt'}
                      </Button>
                    ) : null}
                  </div>
                ))}
              </div>
            </Panel>

            <Panel className="overflow-hidden">
              <PanelHeader title="Nhật ký Kiểm toán Quản trị (Audit Log)" />
              <div className="divide-y divide-[var(--border-subtle)] text-xs">
                {(auditQuery.data ?? []).slice(0, 15).map((entry) => (
                  <div
                    key={entry.id}
                    className="px-4 py-2.5 flex items-center justify-between gap-2"
                  >
                    <span className="font-mono font-medium">
                      {entry.action} → #{entry.target}
                    </span>
                    <span className="num text-[var(--text-muted)]">
                      {formatDate(entry.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      ) : null}
    </div>
  );
}
