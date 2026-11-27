import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  FileSpreadsheet,
  Loader2,
  Upload,
} from 'lucide-react';
import { api, triggerBlobDownload } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import {
  CONFIDENCE_LEVEL_META,
  RISK_TIER_META,
  formatDate,
  formatPct,
  formatScore,
} from '@/lib/format';
import {
  Button,
  EmptyState,
  ErrorState,
  PageHeader,
  Panel,
  PanelHeader,
  TableSkeleton,
  cn,
} from '@/components/ui/Primitives';

const JOB_STATUS_LABELS: Record<string, { label: string; fg: string; bg: string; border: string }> = {
  queued: {
    label: 'Đang chờ xử lý',
    fg: 'var(--risk-medium-fg)',
    bg: 'var(--risk-medium-bg)',
    border: 'var(--risk-medium-border)',
  },
  running: {
    label: 'Đang chấm điểm',
    fg: 'var(--risk-stable-fg)',
    bg: 'var(--risk-stable-bg)',
    border: 'var(--risk-stable-border)',
  },
  completed: {
    label: 'Hoàn tất',
    fg: 'var(--risk-low-fg)',
    bg: 'var(--risk-low-bg)',
    border: 'var(--risk-low-border)',
  },
  failed: {
    label: 'Lỗi xử lý',
    fg: 'var(--risk-critical-fg)',
    bg: 'var(--risk-critical-bg)',
    border: 'var(--risk-critical-border)',
  },
};

export function BatchAssessmentPage() {
  const { user, activeOrg, activeOrgRole } = useAuth();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [downloadingTemplate, setDownloadingTemplate] = useState(false);
  const [exportingJobId, setExportingJobId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const canWrite = activeOrgRole === 'analyst' || activeOrgRole === 'org_admin';

  const jobsQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'batch-jobs'],
    queryFn: api.getBatchJobs,
    enabled: Boolean(user && activeOrg),
    refetchInterval: (query) => {
      const list = query.state.data ?? [];
      const hasActive = list.some((j) => j.status === 'queued' || j.status === 'running');
      return hasActive ? 2500 : false;
    },
  });

  const activeJobId = selectedJobId ?? jobsQuery.data?.[0]?.id ?? null;

  const jobDetailQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'batch-job-detail', activeJobId],
    queryFn: () => api.getBatchJobDetail(activeJobId!),
    enabled: Boolean(user && activeOrg && activeJobId !== null),
    refetchInterval: (query) => {
      const st = query.state.data?.status;
      return st === 'queued' || st === 'running' ? 2000 : false;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.createBatchJob(file),
    onSuccess: (created) => {
      setErrorMsg(null);
      setFeedback(`Đã tiếp nhận lô thẩm định "${created.filename}" (#${created.id}).`);
      setSelectedJobId(created.id);
      void queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'batch-jobs'] });
    },
    onError: (err) => {
      setErrorMsg(err instanceof Error ? err.message : 'Không thể tải lên file Excel.');
    },
  });

  async function handleDownloadTemplate() {
    setDownloadingTemplate(true);
    setErrorMsg(null);
    try {
      const blob = await api.downloadBatchTemplate();
      triggerBlobDownload(blob, 'FinHealth_Batch_Template.xlsx');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Không thể tải file mẫu.');
    } finally {
      setDownloadingTemplate(false);
    }
  }

  async function handleExportExcel(jobId: number) {
    setExportingJobId(jobId);
    setErrorMsg(null);
    try {
      const blob = await api.downloadBatchExport(jobId);
      triggerBlobDownload(blob, `FinHealth_Batch_Result_${jobId}.xlsx`);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Không thể xuất file Excel kết quả.');
    } finally {
      setExportingJobId(null);
    }
  }

  if (!user || !activeOrg) {
    return (
      <Panel ruled className="p-10 text-center space-y-2">
        <FileSpreadsheet className="mx-auto h-7 w-7 text-[var(--text-muted)]" />
        <h1 className="font-editorial text-lg font-bold text-[var(--text-primary)]">
          Đăng nhập để sử dụng Thẩm định Hàng loạt
        </h1>
        <p className="text-[13px] text-[var(--text-secondary)] max-w-lg mx-auto">
          Tính năng tải lên danh mục tối đa 500 doanh nghiệp qua Excel chỉ khả dụng trong không gian
          làm việc của tổ chức.
        </p>
      </Panel>
    );
  }

  const jobs = jobsQuery.data ?? [];
  const detail = jobDetailQuery.data;
  const progressPct =
    detail && detail.total_rows > 0
      ? Math.round((detail.processed_rows / detail.total_rows) * 100)
      : 0;

  return (
    <div className="space-y-5 animate-view">
      <PageHeader
        title="Thẩm định Hàng loạt qua Excel"
        description="Tải lên danh sách tối đa 500 doanh nghiệp (.xlsx ≤ 10 MB), tự động kiểm tra cân đối kế toán, chấm điểm rủi ro theo lô và xếp hạng ưu tiên từ cao xuống thấp."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void handleDownloadTemplate()}
              disabled={downloadingTemplate}
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              {downloadingTemplate ? 'Đang tải mẫu...' : 'Tải file Excel mẫu'}
            </Button>

            {canWrite ? (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) uploadMutation.mutate(file);
                    e.target.value = '';
                  }}
                />
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadMutation.isPending}
                >
                  <Upload className="h-3.5 w-3.5" aria-hidden="true" />
                  {uploadMutation.isPending ? 'Đang tải lên...' : 'Tải lên file Excel (.xlsx)'}
                </Button>
              </>
            ) : null}
          </>
        }
      />

      {feedback ? (
        <div
          role="status"
          className="px-4 py-2.5 rounded-[3px] border text-xs font-semibold flex items-center justify-between"
          style={{
            backgroundColor: 'var(--risk-low-bg)',
            color: 'var(--risk-low-fg)',
            borderColor: 'var(--risk-low-border)',
          }}
        >
          <span>{feedback}</span>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="underline cursor-pointer bg-transparent border-0 text-inherit font-semibold"
          >
            Đóng
          </button>
        </div>
      ) : null}

      {errorMsg ? <ErrorState title="Lỗi thao tác lô thẩm định" message={errorMsg} /> : null}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Batch Job History Queue */}
        <Panel ruled className="lg:col-span-4 overflow-hidden">
          <PanelHeader
            title="Danh sách Lô đã tải lên"
            description={`${jobs.length} lô trong ${activeOrg.name}`}
          />
          {jobsQuery.isLoading ? (
            <TableSkeleton rows={4} />
          ) : jobs.length === 0 ? (
            <EmptyState
              title="Chưa có lô thẩm định nào"
              description="Tải file Excel mẫu, điền số liệu các doanh nghiệp cần rà soát và tải lên hệ thống."
            />
          ) : (
            <div className="divide-y divide-[var(--border-subtle)]">
              {jobs.map((job) => {
                const st = JOB_STATUS_LABELS[job.status] ?? JOB_STATUS_LABELS.queued;
                const isSelected = job.id === activeJobId;
                return (
                  <button
                    key={job.id}
                    type="button"
                    onClick={() => setSelectedJobId(job.id)}
                    className={cn(
                      'w-full text-left px-4 py-3 transition-colors cursor-pointer bg-transparent border-0',
                      isSelected ? 'bg-[var(--accent-soft)]' : 'hover:bg-[var(--bg-hover)]',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[13px] font-semibold text-[var(--text-primary)] truncate">
                        <span className="num text-[var(--accent-primary)]">#{job.id}</span> · {job.filename}
                      </span>
                      <span
                        className="px-1.5 py-0.5 rounded-[2px] border text-[10px] font-semibold shrink-0"
                        style={{ color: st.fg, backgroundColor: st.bg, borderColor: st.border }}
                      >
                        {st.label}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                      <span className="num">
                        {job.processed_rows}/{job.total_rows} dòng ({job.succeeded_rows} đạt,{' '}
                        {job.failed_rows} lỗi)
                      </span>
                      <span className="num">{formatDate(job.created_at)}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </Panel>

        {/* Right: Selected Batch Job Detail & Risk-Ranked Priority Ledger */}
        <div className="lg:col-span-8 min-w-0 space-y-5">
          {activeJobId === null ? (
            <Panel className="p-10 text-center text-[13px] text-[var(--text-muted)]">
              Chọn một lô thẩm định ở cột bên trái để xem tiến độ và bảng xếp hạng rủi ro.
            </Panel>
          ) : jobDetailQuery.isLoading ? (
            <Panel>
              <TableSkeleton rows={6} />
            </Panel>
          ) : detail ? (
            <Panel ruled className="overflow-hidden">
              <div className="px-5 py-4 bg-[var(--bg-header)] border-b border-[var(--border-subtle)] space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-[15px] font-bold text-[var(--text-primary)] m-0">
                        Lô #{detail.id}: {detail.filename}
                      </h2>
                      {detail.status === 'running' || detail.status === 'queued' ? (
                        <Loader2 className="h-4 w-4 animate-spin text-[var(--accent-primary)]" />
                      ) : detail.status === 'completed' ? (
                        <CheckCircle2 className="h-4 w-4 text-[var(--risk-low-fg)]" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-[var(--risk-critical-fg)]" />
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-[var(--text-secondary)] m-0">
                      Đã xử lý <strong className="num">{detail.processed_rows}/{detail.total_rows}</strong> doanh nghiệp · Thành công:{' '}
                      <strong className="num text-[var(--risk-low-fg)]">{detail.succeeded_rows}</strong> · Lỗi dòng:{' '}
                      <strong className="num text-[var(--risk-critical-fg)]">{detail.failed_rows}</strong>
                    </p>
                  </div>

                  {detail.status === 'completed' ? (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => void handleExportExcel(detail.id)}
                      disabled={exportingJobId === detail.id}
                    >
                      <Download className="h-3.5 w-3.5" aria-hidden="true" />
                      {exportingJobId === detail.id
                        ? 'Đang xuất Excel...'
                        : 'Tải bảng tổng hợp Excel'}
                    </Button>
                  ) : null}
                </div>

                {/* Precision Execution Progress Ruler */}
                <div className="space-y-1">
                  <div className="h-2 w-full rounded-[1px] bg-[var(--bg-subtle)] overflow-hidden">
                    <div
                      className="h-full transition-all duration-300"
                      style={{
                        width: `${progressPct}%`,
                        backgroundColor:
                          detail.status === 'failed'
                            ? 'var(--risk-critical-fg)'
                            : 'var(--accent-primary)',
                      }}
                    />
                  </div>
                  <div className="flex justify-between text-[11px] text-[var(--text-muted)] num">
                    <span>Tiến độ: {progressPct}%</span>
                    <span>
                      <Clock className="inline h-3 w-3 mr-1" aria-hidden="true" />
                      {formatDate(detail.created_at)}
                    </span>
                  </div>
                </div>
              </div>

              {detail.rows.length === 0 ? (
                <EmptyState
                  title="Chưa có dòng kết quả"
                  description="Hệ thống đang xử lý dữ liệu lô thẩm định."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="ledger-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Doanh nghiệp / MST</th>
                        <th className="text-right">Điểm (0–100)</th>
                        <th className="text-right">Nguy cơ 12T</th>
                        <th>Xếp hạng / Tin cậy</th>
                        <th>Điểm nghẽn chính / Ghi chú</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.rows.map((row) => {
                        const tierMeta = row.risk_tier ? RISK_TIER_META[row.risk_tier] : null;
                        const confMeta = row.confidence_level
                          ? CONFIDENCE_LEVEL_META[row.confidence_level]
                          : null;
                        return (
                          <tr key={row.id} className="align-top">
                            <td className="num text-[var(--text-muted)]">{row.row_index}</td>
                            <td>
                              <div className="font-semibold text-[var(--text-primary)]">
                                {row.company_name}
                              </div>
                              <div className="text-[11px] text-[var(--text-muted)] num">
                                {row.tax_code ? `MST: ${row.tax_code}` : '—'}
                                {row.fiscal_year ? ` · FY${row.fiscal_year}` : ''}
                              </div>
                            </td>
                            <td className="text-right num font-bold text-[var(--text-primary)]">
                              {formatScore(row.health_score, 1)}
                            </td>
                            <td className="text-right num font-semibold text-[var(--text-primary)]">
                              {formatPct(row.pd_12m, 2)}
                            </td>
                            <td className="space-y-1">
                              {tierMeta ? (
                                <span
                                  className="inline-block px-2 py-0.5 rounded-[2px] border text-[11px] font-semibold"
                                  style={{
                                    color: tierMeta.fg,
                                    backgroundColor: tierMeta.bg,
                                    borderColor: 'currentColor',
                                  }}
                                >
                                  {tierMeta.label}
                                </span>
                              ) : (
                                <span className="inline-block px-2 py-0.5 rounded-[2px] border border-[var(--risk-neutral-border)] text-[11px] bg-[var(--risk-neutral-bg)] text-[var(--risk-neutral-fg)]">
                                  {row.status === 'failed'
                                    ? 'Lỗi dữ liệu'
                                    : row.status === 'excluded'
                                      ? 'Loại trừ TCTC'
                                      : 'Đang chờ'}
                                </span>
                              )}
                              {confMeta ? (
                                <div className="text-[10px] text-[var(--text-muted)]">
                                  {confMeta.label}
                                </div>
                              ) : null}
                            </td>
                            <td className="text-[var(--text-secondary)] max-w-[260px]">
                              {row.error_message ? (
                                <span className="text-[var(--risk-critical-fg)] font-medium">
                                  {row.error_message}
                                </span>
                              ) : (
                                <span>{row.top_bottleneck_vi || '—'}</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}
