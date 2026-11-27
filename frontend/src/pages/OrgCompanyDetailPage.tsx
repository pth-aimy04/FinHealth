import { useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileUp,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { api, triggerBlobDownload } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import {
  ACCOUNTING_STANDARD_LABELS,
  AUDIT_STATUS_LABELS,
  formatMoney,
} from '@/lib/format';
import {
  Button,
  EmptyState,
  ErrorState,
  Panel,
  PanelHeader,
  Skeleton,
  TableSkeleton,
  cn,
} from '@/components/ui/Primitives';
import { HealthHeroCard } from '@/components/assessment/HealthHeroCard';
import { DriversSplitPanel } from '@/components/assessment/DriversSplitPanel';
import { FivePillarsSection } from '@/components/assessment/FivePillarsSection';
import { DynamicAltmanGauge } from '@/components/assessment/DynamicAltmanGauge';
import { MultiPeriodHistoryCharts } from '@/components/assessment/MultiPeriodHistoryCharts';

type OrgDetailTab = 'overview' | 'metrics' | 'history' | 'statements';

export function OrgCompanyDetailPage() {
  const { id = '' } = useParams();
  const companyId = Number(id);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { activeOrg, activeOrgRole } = useAuth();

  const initialTab = (searchParams.get('tab') as OrgDetailTab | null) ?? 'overview';
  const [activeTab, setActiveTab] = useState<OrgDetailTab>(
    ['overview', 'metrics', 'history', 'statements'].includes(initialTab)
      ? initialTab
      : 'overview',
  );
  const [selectedYear, setSelectedYear] = useState<number | undefined>(undefined);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const xmlInputRef = useRef<HTMLInputElement>(null);
  const excelInputRef = useRef<HTMLInputElement>(null);

  const canWrite = activeOrgRole === 'analyst' || activeOrgRole === 'org_admin';
  const isValidId = Number.isInteger(companyId) && companyId > 0;

  const companyQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'company', companyId],
    queryFn: () => api.getOrgCompany(companyId),
    enabled: isValidId,
  });

  const analysisQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'analysis', companyId, selectedYear ?? 'latest'],
    queryFn: () => api.getOrgCompanyAnalysis(companyId, selectedYear),
    enabled: isValidId,
    retry: false,
  });

  const statementsQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'statements', companyId],
    queryFn: () => api.getOrgCompanyStatements(companyId),
    enabled: isValidId,
  });

  const recomputeMutation = useMutation({
    mutationFn: () => api.recomputeOrgCompanyAnalysis(companyId, selectedYear),
    onSuccess: () => {
      setActionError(null);
      setActionMessage('Đã cập nhật lại kết quả đánh giá tài chính.');
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'analysis', companyId],
      });
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : 'Không thể tính lại đánh giá.');
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: (statementId: number) => api.finalizeOrgStatement(companyId, statementId),
    onSuccess: () => {
      setActionError(null);
      setActionMessage('Đã chốt BCTC thành công và sẵn sàng chấm điểm.');
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'statements', companyId],
      });
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'analysis', companyId],
      });
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : 'Không thể chốt BCTC.');
    },
  });

  const deleteStmtMutation = useMutation({
    mutationFn: (statementId: number) => api.deleteOrgStatement(companyId, statementId),
    onSuccess: () => {
      setActionError(null);
      setActionMessage('Đã xóa kỳ BCTC.');
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'statements', companyId],
      });
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'analysis', companyId],
      });
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : 'Không thể xóa BCTC.');
    },
  });

  const importXmlMutation = useMutation({
    mutationFn: (file: File) => api.importHtkkXmlStatement(companyId, file),
    onSuccess: () => {
      setActionError(null);
      setActionMessage('Đã nạp thành công tờ khai BCTC từ file XML HTKK.');
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'statements', companyId],
      });
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'analysis', companyId],
      });
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : 'Không thể đọc file XML HTKK.');
    },
  });

  const importExcelMutation = useMutation({
    mutationFn: (file: File) => api.importExcelStatement(companyId, file),
    onSuccess: () => {
      setActionError(null);
      setActionMessage('Đã nạp thành công BCTC từ file Excel.');
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'statements', companyId],
      });
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'analysis', companyId],
      });
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : 'Không thể đọc file Excel BCTC.');
    },
  });

  async function handleExportPdf() {
    if (!isValidId) return;
    setExportingPdf(true);
    setActionError(null);
    try {
      const blob = await api.downloadOrgReportPdf(companyId, selectedYear);
      const slug = (companyQuery.data?.tax_code || `company-${companyId}`).replace(/\W+/g, '_');
      triggerBlobDownload(blob, `FinHealth_Report_${slug}.pdf`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Không thể xuất báo cáo PDF.');
    } finally {
      setExportingPdf(false);
    }
  }

  async function handleDownloadTemplate(standard: 'TT99_2025' | 'TT200_2014' | 'TT133_2016') {
    setActionError(null);
    try {
      const blob = await api.downloadBctcTemplate(standard, new Date().getFullYear() - 1);
      triggerBlobDownload(blob, `FinHealth_BCTC_${standard}.xlsx`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Không thể tải biểu mẫu Excel.');
    }
  }

  function switchTab(tab: OrgDetailTab) {
    setActiveTab(tab);
    const next = new URLSearchParams(searchParams);
    next.set('tab', tab);
    setSearchParams(next, { replace: true });
  }

  if (!isValidId) {
    return (
      <ErrorState
        title="Mã doanh nghiệp không hợp lệ"
        message="Vui lòng chọn doanh nghiệp từ Danh bạ Doanh nghiệp của tổ chức."
      />
    );
  }

  if (companyQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-44 w-full" />
        <TableSkeleton rows={6} />
      </div>
    );
  }

  if (companyQuery.isError || !companyQuery.data) {
    return (
      <div className="space-y-4">
        <Link
          to="/portfolio"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] no-underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Quay lại Danh bạ Doanh nghiệp
        </Link>
        <ErrorState
          title="Không tìm thấy hồ sơ doanh nghiệp"
          message={
            companyQuery.error instanceof Error
              ? companyQuery.error.message
              : 'Doanh nghiệp không tồn tại hoặc không thuộc tổ chức hiện tại.'
          }
          onRetry={() => void companyQuery.refetch()}
        />
      </div>
    );
  }

  const company = companyQuery.data;
  const analysis = analysisQuery.data;
  const statements = statementsQuery.data ?? [];
  const availableYears = Array.from(
    new Set(
      statements
        .filter((s) => s.status === 'finalized')
        .map((s) => s.fiscal_year),
    ),
  ).sort((a, b) => b - a);

  return (
    <div className="space-y-5 animate-view">
      {/* Breadcrumb & Period Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/portfolio"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--accent-primary)] no-underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Danh bạ Doanh nghiệp
        </Link>

        <div className="flex flex-wrap items-center gap-2">
          {availableYears.length > 1 ? (
            <label className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
              <span>Kỳ đánh giá:</span>
              <select
                value={selectedYear ?? ''}
                onChange={(e) =>
                  setSelectedYear(e.target.value ? Number(e.target.value) : undefined)
                }
                className="h-8 px-2.5 rounded-[6px] border border-[var(--border-strong)] bg-[var(--bg-surface)] text-xs text-[var(--text-primary)]"
              >
                <option value="">Kỳ mới nhất</option>
                {availableYears.map((yr) => (
                  <option key={yr} value={yr}>
                    FY{yr}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {canWrite && analysis ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => recomputeMutation.mutate()}
              disabled={recomputeMutation.isPending}
            >
              <RefreshCw
                className={cn('h-3.5 w-3.5', recomputeMutation.isPending && 'animate-spin')}
                aria-hidden="true"
              />
              Cập nhật đánh giá
            </Button>
          ) : null}
        </div>
      </div>

      {actionMessage ? (
        <div
          role="status"
          className="p-3 rounded-[8px] text-xs font-medium flex items-center justify-between gap-3"
          style={{ backgroundColor: 'var(--risk-low-bg)', color: 'var(--risk-low-fg)' }}
        >
          <span>{actionMessage}</span>
          <button
            type="button"
            onClick={() => setActionMessage(null)}
            className="underline cursor-pointer bg-transparent border-0 text-inherit"
          >
            Đóng
          </button>
        </div>
      ) : null}

      {actionError ? (
        <ErrorState title="Thao tác chưa hoàn tất" message={actionError} />
      ) : null}

      {/* Hero 3-Second Card (when analysis is available) */}
      {analysisQuery.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : analysis ? (
        <HealthHeroCard
          summary={analysis.summary}
          companyName={analysis.company.name}
          identifierLabel={
            analysis.company.tax_code
              ? `MST: ${analysis.company.tax_code}`
              : analysis.company.ticker ?? undefined
          }
          sectorName={analysis.company.sector_name}
          fiscalYear={analysis.company.fiscal_year}
          accountingStandard={analysis.company.accounting_standard}
          currency={analysis.company.currency}
          sourceLabel="Danh bạ DN Tổ chức"
          onExportPdf={handleExportPdf}
          exportingPdf={exportingPdf}
          onNewStatement={canWrite ? () => switchTab('statements') : undefined}
          onCompare={() => navigate(`/compare?source=org&ids=${companyId}`)}
        />
      ) : (
        <Panel className="p-5 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-lg font-bold text-[var(--text-primary)]">{company.name}</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              Doanh nghiệp chưa có kỳ BCTC nào ở trạng thái Đã chốt (finalized). Hãy nhập hoặc chốt
              BCTC ở tab Quản lý & Nhập BCTC để kích hoạt chấm điểm tự động.
            </p>
          </div>
          {canWrite ? (
            <Button variant="primary" size="sm" onClick={() => switchTab('statements')}>
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              Nhập BCTC ngay
            </Button>
          ) : null}
        </Panel>
      )}

      {/* 4 UX Tabs */}
      <div
        className="flex flex-wrap items-center gap-1 border-b border-[var(--border-subtle)]"
        role="tablist"
        aria-label="Phân mục hồ sơ doanh nghiệp"
      >
        {(
          [
            { id: 'overview', label: 'Tổng quan & Điểm Tựa / Điểm Nghẽn' },
            { id: 'metrics', label: 'Chi tiết 20 Chỉ số' },
            { id: 'history', label: 'Lịch sử Đa kỳ (3–5 năm)' },
            { id: 'statements', label: `Quản lý & Nhập BCTC (${statements.length})` },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => switchTab(tab.id)}
            className={cn(
              'px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer bg-transparent',
              activeTab === tab.id
                ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Overview & Drivers + 5 Pillars Radar + Dynamic Altman */}
      {activeTab === 'overview' ? (
        analysis ? (
          <div className="space-y-5">
            <DriversSplitPanel drivers={analysis.drivers} />
            <FivePillarsSection
              pillars={analysis.pillars}
              peerContext={analysis.peer_context}
              mode="overview"
            />
            <DynamicAltmanGauge altman={analysis.altman} />
          </div>
        ) : (
          <EmptyState
            title="Chưa có dữ liệu phân tích"
            description="Cần ít nhất 1 kỳ BCTC đã chốt để hiển thị Điểm Tựa, Điểm Nghẽn và 5 trụ cột tài chính."
          />
        )
      ) : null}

      {/* Tab 2: Detailed 20-Metric Table */}
      {activeTab === 'metrics' ? (
        analysis ? (
          <FivePillarsSection
            pillars={analysis.pillars}
            peerContext={analysis.peer_context}
            mode="table"
          />
        ) : (
          <EmptyState
            title="Chưa có bảng 20 chỉ số"
            description="Chốt ít nhất 1 kỳ BCTC để hệ thống tính toán bộ 20 chỉ số tài chính chuẩn."
          />
        )
      ) : null}

      {/* Tab 3: Multi-Period History (3-5y) */}
      {activeTab === 'history' ? (
        <MultiPeriodHistoryCharts
          history={analysis?.history ?? []}
          currency={analysis?.company.currency ?? 'VND'}
        />
      ) : null}

      {/* Tab 4: Financial Statements Management & Import */}
      {activeTab === 'statements' ? (
        <div className="space-y-4">
          {canWrite ? (
            <Panel className="p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-0.5">
                <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                  Nhập Báo cáo Tài chính kỳ mới
                </h2>
                <p className="text-xs text-[var(--text-secondary)]">
                  Hỗ trợ nạp trực tiếp file XML từ HTKK, file Excel mẫu (TT99/TT200/TT133) hoặc nhập
                  qua biểu mẫu Web.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  ref={xmlInputRef}
                  type="file"
                  accept=".xml"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) importXmlMutation.mutate(file);
                    e.target.value = '';
                  }}
                />
                <input
                  ref={excelInputRef}
                  type="file"
                  accept=".xlsx"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) importExcelMutation.mutate(file);
                    e.target.value = '';
                  }}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => xmlInputRef.current?.click()}
                  disabled={importXmlMutation.isPending}
                >
                  <FileUp className="h-3.5 w-3.5" aria-hidden="true" />
                  {importXmlMutation.isPending ? 'Đang nạp XML...' : 'Nạp XML HTKK'}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => excelInputRef.current?.click()}
                  disabled={importExcelMutation.isPending}
                >
                  <FileSpreadsheet className="h-3.5 w-3.5" aria-hidden="true" />
                  {importExcelMutation.isPending ? 'Đang nạp Excel...' : 'Nạp Excel BCTC'}
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => navigate(`/portfolio/${companyId}/statements/new`)}
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  Biểu mẫu Web 3 phần
                </Button>
              </div>
            </Panel>
          ) : null}

          {/* Template Downloads Strip */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-secondary)]">
            <span>Tải file Excel mẫu chuẩn:</span>
            {(['TT99_2025', 'TT200_2014', 'TT133_2016'] as const).map((std) => (
              <button
                key={std}
                type="button"
                onClick={() => void handleDownloadTemplate(std)}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[6px] bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] cursor-pointer border border-[var(--border-subtle)]"
              >
                <Download className="h-3 w-3" aria-hidden="true" />
                {ACCOUNTING_STANDARD_LABELS[std] ?? std}
              </button>
            ))}
          </div>

          <Panel>
            <PanelHeader
              title="Danh sách các kỳ Báo cáo Tài chính"
              description="Kỳ ở trạng thái Đã chốt sẽ tự động được đưa vào tính điểm sức khỏe và chuỗi lịch sử đa kỳ."
            />
            {statementsQuery.isLoading ? (
              <TableSkeleton rows={4} />
            ) : statements.length === 0 ? (
              <EmptyState
                title="Chưa có kỳ BCTC nào"
                description="Hãy tải lên file XML HTKK, Excel chuẩn hoặc nhập mới qua biểu mẫu Web."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50 text-[var(--text-secondary)]">
                      <th className="py-2.5 px-4 font-semibold">Kỳ</th>
                      <th className="py-2.5 px-3 font-semibold">Chuẩn / Kiểm toán</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Tổng tài sản</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Doanh thu</th>
                      <th className="py-2.5 px-3 font-semibold text-right">LNST</th>
                      <th className="py-2.5 px-3 font-semibold">Trạng thái</th>
                      {canWrite ? (
                        <th className="py-2.5 px-4 font-semibold text-right">Thao tác</th>
                      ) : null}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {statements.map((stmt) => (
                      <tr
                        key={stmt.id}
                        className="hover:bg-[var(--bg-hover)]/45 transition-colors"
                      >
                        <td className="py-3 px-4 num font-semibold text-[var(--text-primary)]">
                          FY{stmt.fiscal_year} ({stmt.fiscal_period})
                        </td>
                        <td className="py-3 px-3 text-[var(--text-secondary)]">
                          <div>
                            {ACCOUNTING_STANDARD_LABELS[stmt.accounting_standard] ??
                              stmt.accounting_standard}
                          </div>
                          <div className="text-[11px] text-[var(--text-muted)]">
                            {AUDIT_STATUS_LABELS[stmt.audit_status] ?? stmt.audit_status}
                          </div>
                        </td>
                        <td className="py-3 px-3 text-right num text-[var(--text-primary)]">
                          {formatMoney(stmt.total_assets, stmt.currency, 1)}
                        </td>
                        <td className="py-3 px-3 text-right num text-[var(--text-primary)]">
                          {formatMoney(stmt.revenues, stmt.currency, 1)}
                        </td>
                        <td className="py-3 px-3 text-right num text-[var(--text-primary)]">
                          {formatMoney(stmt.net_income, stmt.currency, 1)}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                            style={
                              stmt.status === 'finalized'
                                ? {
                                    color: 'var(--risk-low-fg)',
                                    backgroundColor: 'var(--risk-low-bg)',
                                  }
                                : {
                                    color: 'var(--risk-medium-fg)',
                                    backgroundColor: 'var(--risk-medium-bg)',
                                  }
                            }
                          >
                            {stmt.status === 'finalized' ? 'Đã chốt' : 'Bản nháp'}
                          </span>
                        </td>
                        {canWrite ? (
                          <td className="py-3 px-4 text-right whitespace-nowrap">
                            <div className="inline-flex items-center gap-1.5">
                              {stmt.status !== 'finalized' ? (
                                <Button
                                  variant="primary"
                                  size="sm"
                                  onClick={() => finalizeMutation.mutate(stmt.id)}
                                  disabled={finalizeMutation.isPending}
                                >
                                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                                  Chốt BCTC
                                </Button>
                              ) : null}
                              <Button
                                variant="ghost"
                                size="sm"
                                aria-label={`Xóa BCTC FY${stmt.fiscal_year}`}
                                onClick={() => deleteStmtMutation.mutate(stmt.id)}
                                disabled={deleteStmtMutation.isPending}
                              >
                                <Trash2 className="h-3.5 w-3.5 text-[var(--risk-critical-fg)]" />
                              </Button>
                            </div>
                          </td>
                        ) : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      ) : null}
    </div>
  );
}
