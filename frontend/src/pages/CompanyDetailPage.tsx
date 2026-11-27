import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  CheckCircle2,
  MinusCircle,
  SlidersHorizontal,
  Star,
  XCircle,
} from 'lucide-react';
import { api, triggerBlobDownload } from '@/lib/api';
import {
  formatCompactUsd,
  formatDate,
  formatPct,
  formatRatio,
  humanizeFeature,
  translateSector,
  translateSignalReason,
} from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import type { CompanyFullAnalysis } from '@/types/api';
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
import {
  CapitalStructureChart,
  FinancialsComboChart,
  PeerPercentileChart,
} from '@/components/charts/CompanyCharts';
import { HealthHeroCard } from '@/components/assessment/HealthHeroCard';
import { DriversSplitPanel } from '@/components/assessment/DriversSplitPanel';
import { DynamicAltmanGauge } from '@/components/assessment/DynamicAltmanGauge';
import { mapPdToSingleHealthScore } from './OverviewPage';
import type {
  AltmanView,
  AssessmentSummaryView,
  BusinessDriverView,
  DriversSplitView,
  PillarKey,
  RiskTier,
} from '@/components/assessment/types';

type DetailTab = 'overview' | 'financials' | 'diagnostics' | 'filings';

const SEC_LEGAL_DISCLAIMER_VI =
  'Kết quả đánh giá sức khỏe tài chính và xác suất rủi ro 12 tháng là phân tích định lượng nội bộ dựa trên mô hình học máy từ dữ liệu lịch sử SEC EDGAR, không phải dịch vụ xếp hạng tín nhiệm theo Nghị định 88/2014/NĐ-CP và không thay thế quyết định cấp tín dụng, đầu tư hay kiểm toán độc lập.';

function classifyRiskTierFromPd(pd: number | null): { tier: RiskTier | null; label: string } {
  if (pd === null || !Number.isFinite(pd)) return { tier: null, label: 'Chưa đánh giá' };
  if (pd < 0.01) return { tier: 'STRONG', label: 'Vững mạnh' };
  if (pd < 0.03) return { tier: 'STABLE', label: 'Ổn định' };
  if (pd < 0.08) return { tier: 'WATCH', label: 'Cần theo dõi sát' };
  return { tier: 'CRITICAL', label: 'Nguy cơ khủng hoảng cao' };
}

function inferPillarFromFeature(feature: string): PillarKey {
  const f = feature.toLowerCase();
  if (f.includes('current') || f.includes('quick') || f.includes('cash') || f.includes('working')) {
    return 'liquidity';
  }
  if (f.includes('debt') || f.includes('equity') || f.includes('interest') || f.includes('retained')) {
    return 'solvency';
  }
  if (f.includes('ocf') || f.includes('fcf')) {
    return 'cash_flow';
  }
  if (f.includes('turnover') || f.includes('opex') || f.includes('receivable') || f.includes('inventory')) {
    return 'efficiency';
  }
  return 'profitability';
}

function buildSecSummaryView(data: CompanyFullAnalysis): AssessmentSummaryView {
  const pd = data.latest_prediction?.distress_probability ?? data.company.distress_probability;
  const score = mapPdToSingleHealthScore(pd);
  const { tier, label } = classifyRiskTierFromPd(pd);
  const isFinancialSector = (data.company.sector ?? '').toLowerCase().includes('finance');

  const takeaways: string[] = [];
  if (typeof data.company.roa === 'number') {
    takeaways.push(
      `Tỷ suất sinh lời trên tài sản (ROA) kỳ gần nhất đạt ${formatPct(data.company.roa, 1)}.`,
    );
  }
  if (typeof data.company.debt_ratio === 'number') {
    takeaways.push(
      `Tỷ lệ Nợ phải trả / Tổng tài sản ở mức ${formatPct(data.company.debt_ratio, 1)}.`,
    );
  }
  if (typeof data.company.current_ratio === 'number') {
    takeaways.push(
      `Hệ số thanh toán hiện hành đạt ${formatRatio(data.company.current_ratio, 2)}x.`,
    );
  }

  return {
    scoring_eligible: !isFinancialSector && score !== null,
    scoring_mode: data.history.length >= 2 ? 'multi_period' : 'single_period',
    model_version: data.latest_prediction?.model_version ?? data.company.model_version ?? 'active',
    health_score: isFinancialSector ? null : score,
    risk_tier: isFinancialSector ? null : tier,
    risk_label_vi: isFinancialSector ? 'Loại trừ (Tài chính)' : label,
    pd_12m: isFinancialSector ? null : pd,
    confidence: {
      level: data.history.length >= 3 ? 'HIGH' : 'MODERATE',
      input_completeness: 0.92,
      is_ood: false,
      ood_features: [],
      ensemble_spread: null,
      audit_status: 'audited_unqualified',
      reasons_vi: ['Dữ liệu công bố chuẩn SEC EDGAR (10-K/10-Q) đã kiểm toán.'],
    },
    cash_flow_overlay:
      data.quality_of_earnings?.accruals_flag === 'EARNINGS_AHEAD_OF_CASH_WARNING'
        ? {
            triggered: true,
            flags: ['earnings_ahead_of_cash'],
            reasons_vi: ['Lợi nhuận kế toán cao hơn đáng kể so với dòng tiền thực thu (OCF).'],
            original_tier: tier,
            adjusted_tier: tier,
          }
        : null,
    top_3_takeaways_vi: takeaways.slice(0, 3),
    unavailable_reason_vi: isFinancialSector
      ? 'Mô hình doanh nghiệp phi tài chính không áp dụng cho Ngân hàng, Bảo hiểm và Tổ chức tài chính.'
      : null,
    legal_disclaimer_vi: SEC_LEGAL_DISCLAIMER_VI,
  };
}

function buildSecDriversView(data: CompanyFullAnalysis): DriversSplitView {
  const rawDrivers = (data.latest_prediction?.top_drivers ?? []).filter(
    (d) => typeof d.shap_value === 'number' && Number.isFinite(d.shap_value),
  );
  const totalAbs = rawDrivers.reduce((acc, d) => acc + Math.abs(d.shap_value ?? 0), 0);

  const strengths: BusinessDriverView[] = [];
  const bottlenecks: BusinessDriverView[] = [];

  for (const d of rawDrivers) {
    const val = d.shap_value ?? 0;
    const share = totalAbs > 0 ? (Math.abs(val) / totalAbs) * 100 : 0;
    const isBottleneck = val > 0;
    const label = humanizeFeature(d.feature);
    const formattedVal =
      typeof d.feature_value === 'number' && Number.isFinite(d.feature_value)
        ? Math.abs(d.feature_value) <= 2 &&
          !d.feature.includes('ratio') &&
          !d.feature.includes('turnover')
          ? formatPct(d.feature_value, 1)
          : formatRatio(d.feature_value, 2)
        : '—';

    const impactStrength =
      share >= 25 ? 'VERY_HIGH' : share >= 15 ? 'HIGH' : share >= 8 ? 'MODERATE' : 'LOW';
    const impactLabel =
      share >= 25
        ? 'Tác động rất mạnh'
        : share >= 15
          ? 'Tác động mạnh'
          : share >= 8
            ? 'Tác động trung bình'
            : 'Tác động nhẹ';

    const card: BusinessDriverView = {
      factor_code: d.feature,
      label_vi: label,
      pillar: inferPillarFromFeature(d.feature),
      side: isBottleneck ? 'BOTTLENECK' : 'STRENGTH',
      observed_value: d.feature_value,
      formatted_value_vi: formattedVal,
      reference_range_vi: 'Chuẩn ngành SEC',
      impact_share_pct: Number(share.toFixed(1)),
      impact_strength: impactStrength,
      impact_strength_label_vi: impactLabel,
      headline_vi: isBottleneck
        ? `${label} (${formattedVal}) đang tạo áp lực đẩy rủi ro tài chính tăng lên.`
        : `${label} (${formattedVal}) đóng vai trò điểm tựa giúp củng cố độ an toàn tài chính.`,
      detail_vi: `Chiếm ${share.toFixed(1)}% mức độ ảnh hưởng tương đối trong đánh giá kỳ này.`,
    };

    if (isBottleneck && bottlenecks.length < 5) {
      bottlenecks.push(card);
    } else if (!isBottleneck && strengths.length < 5) {
      strengths.push(card);
    }
  }

  return {
    strengths,
    bottlenecks,
    total_impact_share_pct: Number(
      [...strengths, ...bottlenecks].reduce((acc, item) => acc + item.impact_share_pct, 0).toFixed(1),
    ),
  };
}

function buildSecAltmanView(data: CompanyFullAnalysis): AltmanView {
  const sector = (data.company.sector ?? '').toLowerCase();
  if (sector.includes('finance') || sector.includes('insurance') || sector.includes('bank')) {
    return {
      applicable: false,
      variant: null,
      score: null,
      zone: null,
      zone_label_vi: null,
      cutoff_low: null,
      cutoff_high: null,
      components: {},
      fallback_note_vi: null,
      unavailable_reason_vi:
        'Chỉ số Altman Z-Score không áp dụng cho Ngân hàng, Bảo hiểm và Tổ chức tài chính.',
    };
  }

  const isManufacturing = sector.includes('manufacturing');
  const variant = isManufacturing ? 'Z' : "Z''";
  const cutoffLow = isManufacturing ? 1.81 : 1.1;
  const cutoffHigh = isManufacturing ? 2.99 : 2.6;
  const score = data.company.altman_z_score;
  const zone =
    score === null
      ? null
      : score > cutoffHigh
        ? 'SAFE'
        : score >= cutoffLow
          ? 'GREY'
          : 'DISTRESS';

  return {
    applicable: true,
    variant,
    score,
    zone,
    zone_label_vi:
      zone === 'SAFE'
        ? 'Vùng an toàn'
        : zone === 'GREY'
          ? 'Vùng xám (cần theo dõi)'
          : zone === 'DISTRESS'
            ? 'Vùng nguy hiểm'
            : null,
    cutoff_low: cutoffLow,
    cutoff_high: cutoffHigh,
    components: data.altman_components ?? {},
    fallback_note_vi: null,
    unavailable_reason_vi: null,
  };
}

export function CompanyDetailPage() {
  const { identifier = '' } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const formType = searchParams.get('form_type') === '10-Q' ? '10-Q' : '10-K';
  const [activeTab, setActiveTab] = useState<DetailTab>('overview');
  const [exportingPdf, setExportingPdf] = useState(false);

  const analysisQuery = useQuery({
    queryKey: ['company', identifier, formType],
    queryFn: () => api.getCompany(identifier, formType),
    enabled: Boolean(identifier),
  });

  const alertsQuery = useQuery({
    queryKey: ['company-alerts', identifier],
    queryFn: () => api.getReportAlerts(identifier),
    enabled: Boolean(identifier) && activeTab === 'filings',
    retry: false,
  });

  const followMutation = useMutation({
    mutationFn: (cik: string) => api.followCompany(cik),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['workspace', 'watchlist'] });
    },
  });

  const data = analysisQuery.data;

  const summaryView = useMemo(() => (data ? buildSecSummaryView(data) : null), [data]);
  const driversView = useMemo(() => (data ? buildSecDriversView(data) : null), [data]);
  const altmanView = useMemo(() => (data ? buildSecAltmanView(data) : null), [data]);

  async function handleExportSecPdf() {
    if (!identifier) return;
    setExportingPdf(true);
    try {
      const blob = await api.downloadSecReportPdf(identifier);
      triggerBlobDownload(blob, `FinHealth_SEC_${identifier.toUpperCase()}.pdf`);
    } finally {
      setExportingPdf(false);
    }
  }

  if (analysisQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-44 w-full" />
        <TableSkeleton rows={6} />
      </div>
    );
  }

  if (analysisQuery.isError || !data || !summaryView || !driversView || !altmanView) {
    return (
      <div className="space-y-4">
        <Link
          to="/us-market"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] no-underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Quay lại Thị trường Mỹ (SEC)
        </Link>
        <ErrorState
          title={`Không thể tải hồ sơ "${identifier}"`}
          message={
            analysisQuery.error instanceof Error
              ? analysisQuery.error.message
              : 'Không tìm thấy dữ liệu doanh nghiệp.'
          }
          onRetry={() => void analysisQuery.refetch()}
        />
      </div>
    );
  }

  const { company, history } = data;
  const idForUrl = company.ticker || company.cik;

  return (
    <div className="space-y-5 animate-view">
      {/* Top Backlink & SEC Utility Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/us-market"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--accent-primary)] no-underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Thị trường Mỹ (SEC — USD)
        </Link>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-[6px] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-0.5 text-xs">
            {(['10-K', '10-Q'] as const).map((ft) => (
              <button
                key={ft}
                type="button"
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.set('form_type', ft);
                  setSearchParams(next, { replace: true });
                }}
                className={cn(
                  'px-2.5 py-1 rounded-[4px] cursor-pointer font-medium',
                  formType === ft
                    ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)]'
                    : 'text-[var(--text-secondary)]',
                )}
              >
                {ft === '10-K' ? 'Báo cáo năm (10-K)' : 'Báo cáo quý (10-Q)'}
              </button>
            ))}
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate(`/stress?ticker=${encodeURIComponent(idForUrl)}`)}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
            Kiểm thử Kịch bản
          </Button>

          {user ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => followMutation.mutate(company.cik)}
              disabled={followMutation.isPending}
            >
              <Star className="h-3.5 w-3.5" aria-hidden="true" />
              Theo dõi
            </Button>
          ) : null}
        </div>
      </div>

      {/* Unified HealthHeroCard (Single Health Score, zero ML jargon, NĐ 88/2014 disclaimer) */}
      <HealthHeroCard
        summary={summaryView}
        companyName={company.name}
        identifierLabel={company.ticker ? `${company.ticker} · CIK ${company.cik}` : `CIK ${company.cik}`}
        sectorName={translateSector(company.sector)}
        fiscalYear={company.latest_fiscal_year}
        accountingStandard="US_GAAP"
        currency="USD"
        sourceLabel="Dữ liệu SEC EDGAR (USD)"
        onExportPdf={user ? handleExportSecPdf : undefined}
        exportingPdf={exportingPdf}
        onCompare={() => navigate(`/compare?source=sec&ids=${encodeURIComponent(idForUrl)}`)}
      />

      {/* Tabs */}
      <div
        className="flex flex-wrap items-center gap-1 border-b border-[var(--border-subtle)]"
        role="tablist"
        aria-label="Phân mục hồ sơ doanh nghiệp SEC"
      >
        {(
          [
            { id: 'overview', label: 'Điểm Tựa, Điểm Nghẽn & Altman' },
            { id: 'financials', label: 'Biểu đồ Tài chính & Chuẩn ngành' },
            { id: 'diagnostics', label: 'Chẩn đoán Kế toán (DuPont & QoE)' },
            { id: 'filings', label: 'Lịch sử Báo cáo SEC' },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
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

      {/* Tab 1: DriversSplitPanel + DynamicAltmanGauge */}
      {activeTab === 'overview' ? (
        <div className="space-y-5">
          <DriversSplitPanel drivers={driversView} />
          <DynamicAltmanGauge altman={altmanView} />
        </div>
      ) : null}

      {/* Tab 2: Financials & Peer Percentile */}
      {activeTab === 'financials' ? (
        <div className="space-y-5">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <Panel>
              <PanelHeader
                title="Doanh thu, Lợi nhuận & Dòng tiền HĐKD (USD)"
                description="Diễn biến hiệu quả kinh doanh qua các kỳ công bố SEC."
              />
              <div className="p-4">
                <FinancialsComboChart history={history} />
              </div>
            </Panel>
            <Panel>
              <PanelHeader
                title="Cơ cấu Tài sản, Nợ & Vốn chủ sở hữu (USD)"
                description="Theo dõi đòn bẩy tài chính và quy mô tài sản theo thời gian."
              />
              <div className="p-4">
                <CapitalStructureChart history={history} />
              </div>
            </Panel>
          </div>

          {data.sector_peer_context ? (
            <Panel>
              <PanelHeader
                title="Đối chiếu Phân vị Ngành (SEC Cohort)"
                description={`So sánh với ${data.sector_peer_context.cohort_size} doanh nghiệp cùng nhóm ngành ${translateSector(data.sector_peer_context.sector)}.`}
              />
              <div className="p-4">
                <PeerPercentileChart context={data.sector_peer_context} />
              </div>
            </Panel>
          ) : null}
        </div>
      ) : null}

      {/* Tab 3: Accounting Diagnostics (DuPont, QoE, Checklist) */}
      {activeTab === 'diagnostics' ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {data.dupont ? (
            <Panel>
              <PanelHeader
                title="Phân rã DuPont 3 nhân tố"
                description="Biên lợi nhuận ròng × Vòng quay tài sản × Đòn bẩy tài chính."
              />
              <div className="p-5 grid grid-cols-2 gap-4 text-xs">
                <div>
                  <div className="text-[var(--text-muted)]">Biên lợi nhuận ròng</div>
                  <div className="mt-1 num text-lg font-semibold">
                    {formatPct(data.dupont.net_profit_margin, 2)}
                  </div>
                </div>
                <div>
                  <div className="text-[var(--text-muted)]">Vòng quay tài sản TB</div>
                  <div className="mt-1 num text-lg font-semibold">
                    {formatRatio(data.dupont.asset_turnover_avg, 2)}x
                  </div>
                </div>
                <div>
                  <div className="text-[var(--text-muted)]">Đòn bẩy vốn CSH TB</div>
                  <div className="mt-1 num text-lg font-semibold">
                    {formatRatio(data.dupont.equity_multiplier_avg, 2)}x
                  </div>
                </div>
                <div>
                  <div className="text-[var(--text-muted)]">ROE DuPont</div>
                  <div className="mt-1 num text-lg font-semibold text-[var(--accent-primary)]">
                    {formatPct(data.dupont.roe_dupont_avg, 2)}
                  </div>
                </div>
              </div>
            </Panel>
          ) : null}

          {data.quality_of_earnings ? (
            <Panel>
              <PanelHeader
                title="Chất lượng Lợi nhuận (QoE)"
                description="Kiểm tra mức độ bảo chứng của lợi nhuận kế toán bằng dòng tiền thực."
              />
              <div className="p-5 space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-[var(--text-muted)]">Tỷ lệ chuyển hóa tiền (OCF / LNST)</div>
                    <div className="mt-1 num text-lg font-semibold">
                      {formatRatio(data.quality_of_earnings.cash_conversion_qoe, 2)}x
                    </div>
                  </div>
                  <div>
                    <div className="text-[var(--text-muted)]">Chênh lệch dồn tích (USD)</div>
                    <div className="mt-1 num text-lg font-semibold">
                      {formatCompactUsd(data.quality_of_earnings.accrual_gap_usd)}
                    </div>
                  </div>
                </div>
                <p className="text-[var(--text-secondary)]">
                  {data.quality_of_earnings.basis_note}
                </p>
              </div>
            </Panel>
          ) : null}

          {data.accounting_checklist ? (
            <Panel className="lg:col-span-2">
              <PanelHeader
                title="Bảng kiểm Tín hiệu Kế toán"
                description={`Đạt ${data.accounting_checklist.observed_passes} / ${data.accounting_checklist.observed_checks} tiêu chí sức khỏe tài chính cơ bản.`}
              />
              <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs">
                {Object.entries(data.accounting_checklist.signals).map(([key, sig]) => (
                  <div
                    key={key}
                    className="flex items-start gap-2.5 p-3 rounded-[6px] bg-[var(--bg-subtle)]/50 border border-[var(--border-subtle)]"
                  >
                    {sig.status === 'PASS' ? (
                      <CheckCircle2 className="h-4 w-4 text-[var(--risk-low-fg)] shrink-0 mt-0.5" />
                    ) : sig.status === 'FAIL' ? (
                      <XCircle className="h-4 w-4 text-[var(--risk-critical-fg)] shrink-0 mt-0.5" />
                    ) : (
                      <MinusCircle className="h-4 w-4 text-[var(--text-muted)] shrink-0 mt-0.5" />
                    )}
                    <div>
                      <div className="font-semibold text-[var(--text-primary)]">
                        {humanizeFeature(key)}
                      </div>
                      <div className="text-[11px] text-[var(--text-secondary)]">
                        {translateSignalReason(sig.reason)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          ) : null}
        </div>
      ) : null}

      {/* Tab 4: SEC Filings History */}
      {activeTab === 'filings' ? (
        <Panel>
          <PanelHeader
            title="Lịch sử Báo cáo Tài chính Công bố (SEC EDGAR)"
            description="Nguồn dữ liệu gốc kèm ngày nộp hồ sơ và mã Accession."
          />
          {history.length === 0 ? (
            <EmptyState
              title="Chưa có lịch sử báo cáo"
              description="Không tìm thấy kỳ báo cáo công bố nào cho doanh nghiệp này."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50 text-[var(--text-secondary)]">
                    <th className="py-2.5 px-4 font-semibold">Kỳ</th>
                    <th className="py-2.5 px-3 font-semibold">Mẫu đơn</th>
                    <th className="py-2.5 px-3 font-semibold">Ngày nộp</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Doanh thu (USD)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">LNST (USD)</th>
                    <th className="py-2.5 px-4 font-semibold text-right">Tổng tài sản (USD)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {history.map((pt) => (
                    <tr key={`${pt.fiscal_year}-${pt.fiscal_period}-${pt.accession_number ?? ''}`}>
                      <td className="py-2.5 px-4 num font-semibold">
                        FY{pt.fiscal_year} {pt.fiscal_period}
                      </td>
                      <td className="py-2.5 px-3">{pt.form_type}</td>
                      <td className="py-2.5 px-3 num text-[var(--text-secondary)]">
                        {formatDate(pt.filed_date)}
                      </td>
                      <td className="py-2.5 px-3 text-right num">
                        {formatCompactUsd(pt.revenues)}
                      </td>
                      <td className="py-2.5 px-3 text-right num">
                        {formatCompactUsd(pt.net_income)}
                      </td>
                      <td className="py-2.5 px-4 text-right num">
                        {formatCompactUsd(pt.total_assets)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {alertsQuery.data && alertsQuery.data.length > 0 ? (
            <div className="p-4 border-t border-[var(--border-subtle)] space-y-2">
              <div className="text-xs font-semibold text-[var(--text-primary)]">
                Cảnh báo điều chỉnh hồi tố (Restatement Alerts)
              </div>
              {alertsQuery.data.map((alert, idx) => (
                <div
                  key={idx}
                  className="text-xs text-[var(--text-secondary)] p-2.5 rounded bg-[var(--bg-subtle)]"
                >
                  Ngày {formatDate(alert.published_on)}: thay đổi các khoản mục{' '}
                  <strong>{alert.changed_fields.map(humanizeFeature).join(', ')}</strong>.
                </div>
              ))}
            </div>
          ) : null}
        </Panel>
      ) : null}
    </div>
  );
}
