import { useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileUp,
  Pencil,
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
  formatPct,
  formatRatio,
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
  const canDelete = activeOrgRole === 'org_admin';
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
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'companies'],
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
      void queryClient.invalidateQueries({
        queryKey: ['org', activeOrg?.id, 'companies'],
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
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--accent-primary)] no-underline"
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
      {/* Breadcrumb & Period Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/portfolio"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--accent-primary)] no-underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Danh bạ Doanh nghiệp
        </Link>

        <div className="flex flex-wrap items-center gap-2">
          {availableYears.length > 1 ? (
            <label className="inline-flex items-center gap-2 text-xs font-semibold text-[var(--text-secondary)]">
              <span>Kỳ đánh giá:</span>
              <select
                value={selectedYear ?? ''}
                onChange={(e) =>
                  setSelectedYear(e.target.value ? Number(e.target.value) : undefined)
                }
                className="field-control !h-8 !w-auto num"
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
              variant="secondary"
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
          className="px-4 py-2.5 rounded-[3px] border text-xs font-semibold flex items-center justify-between gap-3"
          style={{
            backgroundColor: 'var(--risk-low-bg)',
            color: 'var(--risk-low-fg)',
            borderColor: 'var(--risk-low-border)',
          }}
        >
          <span>{actionMessage}</span>
          <button
            type="button"
            onClick={() => setActionMessage(null)}
            className="underline cursor-pointer bg-transparent border-0 text-inherit font-semibold"
          >
            Đóng
          </button>
        </div>
      ) : null}

      {actionError ? (
        <ErrorState title="Thao tác chưa hoàn tất" message={actionError} />
      ) : null}

      {/* Institutional Credit Tearsheet Masthead */}
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
        <Panel ruled className="p-5 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="font-editorial text-xl font-bold text-[var(--text-primary)] m-0">
              {company.name}
            </h1>
            <p className="text-[13px] text-[var(--text-secondary)] m-0">
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

      {/* Institutional Underlined Tabs */}
      <div
        className="flex flex-wrap items-center gap-1 border-b border-[var(--border-strong)]"
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

            {/* DuPont & Quality of Earnings Diagnostics (Flush Hairline Matrices) */}
            {analysis.diagnostics &&
            (analysis.diagnostics.dupont || analysis.diagnostics.quality_of_earnings) ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {analysis.diagnostics.dupont ? (
                  <Panel className="overflow-hidden">
                    <PanelHeader
                      title="Phân rã DuPont 3 nhân tố"
                      description="Biên lợi nhuận ròng × Vòng quay tài sản × Đòn bẩy vốn chủ sở hữu."
                    />
                    <div className="grid grid-cols-2 divide-x divide-y divide-[var(--border-subtle)] text-xs">
                      <div className="p-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-muted)]">
                          Biên lợi nhuận ròng
                        </div>
                        <div className="mt-1.5 num text-lg font-bold text-[var(--text-primary)]">
                          {formatPct(
                            analysis.diagnostics.dupont.net_profit_margin as number | null | undefined,
                            2,
                          )}
                        </div>
                      </div>
                      <div className="p-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-muted)]">
                          Vòng quay tài sản TB
                        </div>
                        <div className="mt-1.5 num text-lg font-bold text-[var(--text-primary)]">
                          {formatRatio(
                            analysis.diagnostics.dupont.asset_turnover_avg as number | null | undefined,
                            2,
                          )}
                          x
                        </div>
                      </div>
                      <div className="p-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-muted)]">
                          Đòn bẩy vốn CSH TB
                        </div>
                        <div className="mt-1.5 num text-lg font-bold text-[var(--text-primary)]">
                          {formatRatio(
                            analysis.diagnostics.dupont.equity_multiplier_avg as
                              | number
                              | null
                              | undefined,
                            2,
                          )}
                          x
                        </div>
                      </div>
                      <div className="p-4 bg-[var(--accent-soft)]/40">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-secondary)]">
                          ROE DuPont
                        </div>
                        <div className="mt-1.5 num text-lg font-bold text-[var(--accent-primary)]">
                          {formatPct(
                            analysis.diagnostics.dupont.roe_dupont_avg as number | null | undefined,
                            2,
                          )}
                        </div>
                      </div>
                    </div>
                  </Panel>
                ) : null}

                {analysis.diagnostics.quality_of_earnings ? (
                  <Panel className="overflow-hidden">
                    <PanelHeader
                      title="Chất lượng Lợi nhuận (QoE)"
                      description="Đối chiếu mức độ bảo chứng lợi nhuận kế toán bằng dòng tiền hoạt động (OCF)."
                    />
                    <div className="divide-y divide-[var(--border-subtle)] text-xs">
                      <div className="grid grid-cols-2 divide-x divide-[var(--border-subtle)]">
                        <div className="p-4">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-muted)]">
                            Chuyển hóa tiền (OCF / LNST)
                          </div>
                          <div className="mt-1.5 num text-lg font-bold text-[var(--text-primary)]">
                            {formatRatio(
                              analysis.diagnostics.quality_of_earnings.cash_conversion_qoe as
                                | number
                                | null
                                | undefined,
                              2,
                            )}
                            x
                          </div>
                        </div>
                        <div className="p-4">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-muted)]">
                            Tỷ lệ dồn tích (Accruals)
                          </div>
                          <div className="mt-1.5 num text-lg font-bold text-[var(--text-primary)]">
                            {formatPct(
                              analysis.diagnostics.quality_of_earnings.cash_flow_accruals_ratio as
                                | number
                                | null
                                | undefined,
                              2,
                            )}
                          </div>
                        </div>
                      </div>
                      {analysis.diagnostics.quality_of_earnings.accruals_flag ? (
                        <div className="px-4 py-3 bg-[var(--bg-header)] text-xs font-medium text-[var(--text-secondary)]">
                          <strong className="text-[var(--text-primary)]">Đánh giá: </strong>
                          {analysis.diagnostics.quality_of_earnings.accruals_flag ===
                          'CASH_BACKED_EARNINGS'
                            ? 'Lợi nhuận được bảo chứng bằng dòng tiền thực'
                            : 'Lợi nhuận kế toán cao hơn dòng tiền thực — cần theo dõi công nợ & tồn kho'}
                        </div>
                      ) : null}
                    </div>
                  </Panel>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : (
          <Panel>
            <EmptyState
              title="Chưa có dữ liệu phân tích"
              description="Cần ít nhất 1 kỳ BCTC đã chốt để hiển thị Điểm Tựa, Điểm Nghẽn và 5 trụ cột tài chính."
            />
          </Panel>
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
          <Panel>
            <EmptyState
              title="Chưa có bảng 20 chỉ số"
              description="Chốt ít nhất 1 kỳ BCTC để hệ thống tính toán bộ 20 chỉ số tài chính chuẩn."
            />
          </Panel>
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
          <Panel ruled className="overflow-hidden">
            <PanelHeader
              title="Danh sách các kỳ Báo cáo Tài chính"
              description="Kỳ ở trạng thái Đã chốt sẽ tự động được đưa vào tính điểm sức khỏe và chuỗi lịch sử đa kỳ."
              actions={
                canWrite ? (
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
                ) : undefined
              }
            />

            {/* Docked Template Downloads Ribbon */}
            <div className="px-5 py-2.5 bg-[var(--bg-subtle)]/55 border-b border-[var(--border-subtle)] flex flex-wrap items-center gap-2 text-xs text-[var(--text-secondary)]">
              <span className="font-semibold">Tải file Excel mẫu chuẩn:</span>
              {(['TT99_2025', 'TT200_2014', 'TT133_2016'] as const).map((std) => (
                <button
                  key={std}
                  type="button"
                  onClick={() => void handleDownloadTemplate(std)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[2px] bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] font-medium cursor-pointer border border-[var(--border-strong)]"
                >
                  <Download className="h-3 w-3 text-[var(--accent-primary)]" aria-hidden="true" />
                  {ACCOUNTING_STANDARD_LABELS[std] ?? std}
                </button>
              ))}
            </div>

            {statementsQuery.isLoading ? (
              <TableSkeleton rows={4} />
            ) : statements.length === 0 ? (
              <EmptyState
                title="Chưa có kỳ BCTC nào"
                description="Hãy tải lên file XML HTKK, Excel chuẩn hoặc nhập mới qua biểu mẫu Web."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Kỳ</th>
                      <th>Chuẩn / Kiểm toán</th>
                      <th className="text-right">Tổng tài sản</th>
                      <th className="text-right">Doanh thu</th>
                      <th className="text-right">LNST</th>
                      <th>Trạng thái</th>
                      {canWrite ? <th className="text-right">Thao tác</th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {statements.map((stmt) => (
                      <tr key={stmt.id}>
                        <td className="num font-bold text-[var(--text-primary)]">
                          FY{stmt.fiscal_year} ({stmt.fiscal_period})
                        </td>
                        <td className="text-[var(--text-secondary)]">
                          <div className="font-medium text-[var(--text-primary)]">
                            {ACCOUNTING_STANDARD_LABELS[stmt.accounting_standard] ??
                              stmt.accounting_standard}
                          </div>
                          <div className="text-[11px] text-[var(--text-muted)]">
                            {AUDIT_STATUS_LABELS[stmt.audit_status] ?? stmt.audit_status}
                          </div>
                        </td>
                        <td className="text-right num text-[var(--text-primary)]">
                          {formatMoney(stmt.total_assets, stmt.currency, 1)}
                        </td>
                        <td className="text-right num text-[var(--text-primary)]">
                          {formatMoney(stmt.revenues, stmt.currency, 1)}
                        </td>
                        <td className="text-right num text-[var(--text-primary)]">
                          {formatMoney(stmt.net_income, stmt.currency, 1)}
                        </td>
                        <td>
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded-[2px] border text-[11px] font-semibold"
                            style={
                              stmt.status === 'finalized'
                                ? {
                                    color: 'var(--risk-low-fg)',
                                    backgroundColor: 'var(--risk-low-bg)',
                                    borderColor: 'var(--risk-low-border)',
                                  }
                                : {
                                    color: 'var(--risk-medium-fg)',
                                    backgroundColor: 'var(--risk-medium-bg)',
                                    borderColor: 'var(--risk-medium-border)',
                                  }
                            }
                          >
                            {stmt.status === 'finalized' ? 'Đã chốt' : 'Bản nháp'}
                          </span>
                        </td>
                        {canWrite ? (
                          <td className="text-right whitespace-nowrap">
                            <div className="inline-flex items-center gap-1.5">
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() =>
                                  navigate(`/portfolio/${companyId}/statements/${stmt.id}/edit`)
                                }
                              >
                                <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                                Sửa
                              </Button>
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
                              {canDelete ? (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  aria-label={`Xóa BCTC FY${stmt.fiscal_year}`}
                                  onClick={() => deleteStmtMutation.mutate(stmt.id)}
                                  disabled={deleteStmtMutation.isPending}
                                >
                                  <Trash2 className="h-3.5 w-3.5 text-[var(--risk-critical-fg)]" />
                                </Button>
                              ) : null}
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
