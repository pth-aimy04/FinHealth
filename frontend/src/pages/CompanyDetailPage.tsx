import { useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  CheckCircle2,
  GitCompare,
  MinusCircle,
  SlidersHorizontal,
  Star,
  XCircle,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import {
  formatCompactUsd,
  formatDate,
  formatPct,
  formatRatio,
  formatScore,
  formatSigned,
  humanizeFeature,
  translateAltmanZone,
  translateClusterLabel,
  translateSector,
  translateSignalReason,
} from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import {
  Button,
  EmptyState,
  ErrorState,
  MetricTile,
  Panel,
  PanelHeader,
  RiskBadge,
  RiskGauge,
  Skeleton,
  TableSkeleton,
  cn,
} from '@/components/ui/Primitives';
import {
  AltmanZoneChart,
  CapitalStructureChart,
  FinancialsComboChart,
  HealthPillarsRadarChart,
  PeerPercentileChart,
} from '@/components/charts/CompanyCharts';

type DetailTab = 'overview' | 'financials' | 'diagnostics' | 'filings';

export function CompanyDetailPage() {
  const { identifier = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const formType = searchParams.get('form_type') === '10-Q' ? '10-Q' : '10-K';
  const [activeTab, setActiveTab] = useState<DetailTab>('overview');

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

  const shapChartData = useMemo(() => {
    const drivers = data?.latest_prediction?.top_drivers ?? [];
    return drivers
      .filter((d) => typeof d.shap_value === 'number' && Number.isFinite(d.shap_value))
      .slice(0, 10)
      .map((d) => ({
        feature: humanizeFeature(d.feature),
        rawFeature: d.feature,
        shap: d.shap_value as number,
        value: d.feature_value,
      }));
  }, [data]);

  const historyChartData = useMemo(() => {
    const rows = data?.history ?? [];
    return rows.map((r) => ({
      period: `${r.fiscal_year} ${r.fiscal_period}`,
      roa: typeof r.roa === 'number' ? Number((r.roa * 100).toFixed(2)) : null,
      debt_ratio: typeof r.debt_ratio === 'number' ? Number((r.debt_ratio * 100).toFixed(2)) : null,
      ocf_ratio: typeof r.ocf_ratio === 'number' ? Number((r.ocf_ratio * 100).toFixed(2)) : null,
    }));
  }, [data]);

  if (analysisQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[88px]" />
          ))}
        </div>
        <TableSkeleton rows={6} />
      </div>
    );
  }

  if (analysisQuery.isError || !data) {
    return (
      <div className="space-y-4">
        <Link
          to="/screener"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] no-underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Quay lại Sàng lọc Doanh nghiệp
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

  const { company, latest_prediction: pred, history } = data;
  const idForUrl = company.ticker || company.cik;

  return (
    <div className="space-y-5">
      {/* Executive Dossier Hero Banner */}
      <Panel className="p-5">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-center">
          <div className="lg:col-span-8 space-y-2.5">
            <Link
              to="/screener"
              className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--accent-primary)] no-underline"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              Sàng lọc Doanh nghiệp
            </Link>

            <div className="flex flex-wrap items-center gap-2.5">
              <span className="px-2.5 py-1 text-sm font-mono font-bold rounded-[6px] bg-[var(--accent-primary)] text-[var(--accent-ink)]">
                {company.ticker ?? company.cik}
              </span>
              <h1 className="text-xl sm:text-2xl font-bold tracking-[-0.025em]">
                {company.name}
              </h1>
            </div>

            <p className="text-xs text-[var(--text-secondary)]">
              Mã CIK <span className="font-mono font-medium text-[var(--text-primary)]">{company.cik}</span> ·{' '}
              {translateSector(company.sector)} · Kỳ mới nhất{' '}
              <span className="font-mono font-medium text-[var(--text-primary)]">
                {company.latest_fiscal_year ? `FY${company.latest_fiscal_year}` : '—'} ({formType})
              </span>
            </p>

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <div
                className="inline-flex rounded-[6px] border border-[var(--border-subtle)] bg-[var(--bg-subtle)] p-0.5 text-xs"
                role="group"
                aria-label="Loại báo cáo SEC"
              >
                {(['10-K', '10-Q'] as const).map((ft) => (
                  <button
                    key={ft}
                    type="button"
                    onClick={() => setSearchParams({ form_type: ft }, { replace: true })}
                    className={cn(
                      'px-3 py-1 rounded-[4px] font-mono cursor-pointer transition-colors',
                      formType === ft
                        ? 'bg-[var(--bg-surface)] text-[var(--accent-primary)] font-semibold shadow-xs'
                        : 'text-[var(--text-secondary)]',
                    )}
                  >
                    {ft === '10-K' ? '10-K (Năm)' : '10-Q (Quý)'}
                  </button>
                ))}
              </div>

              <Link to={`/stress?id=${encodeURIComponent(idForUrl)}`} className="no-underline">
                <Button variant="primary" size="sm">
                  <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                  Mô phỏng Stress Test
                </Button>
              </Link>

              <Link to={`/compare?ids=${encodeURIComponent(idForUrl)}`} className="no-underline">
                <Button variant="secondary" size="sm">
                  <GitCompare className="h-3.5 w-3.5" aria-hidden="true" />
                  So sánh cùng ngành
                </Button>
              </Link>

              {user ? (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={followMutation.isPending}
                  onClick={() => followMutation.mutate(company.cik)}
                >
                  <Star className="h-3.5 w-3.5" aria-hidden="true" />
                  {followMutation.isSuccess ? 'Đã lưu' : 'Theo dõi'}
                </Button>
              ) : null}
            </div>
          </div>

          {/* Live Credit Risk Arc Gauge */}
          <div className="lg:col-span-4 lg:border-l lg:border-[var(--border-subtle)] lg:pl-5 flex items-center justify-center">
            <RiskGauge
              probability={pred?.distress_probability ?? company.distress_probability}
              riskLevel={pred?.risk_level ?? company.risk_level}
              label={
                pred
                  ? `Dự báo kiệt quệ FY${pred.target_fiscal_year} (${pred.model_version})`
                  : 'Xác suất kiệt quệ năm tới'
              }
            />
          </div>
        </div>
      </Panel>

      {/* Secondary KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricTile
          label="Điểm Sức khỏe Tổng hợp"
          value={formatScore(data.health_pillars?.overall_score ?? company.composite_health_score)}
          meta={`Xếp hạng ${data.health_pillars?.overall_grade ?? company.internal_research_grade} · Nhóm ${company.cohort_scope === 'sector' ? 'cùng ngành' : 'toàn thị trường'}`}
        />
        <MetricTile
          label="Chỉ số Altman Z-Score"
          value={formatRatio(company.altman_z_score)}
          meta={translateAltmanZone(company.altman_zone)}
        />
        <MetricTile
          label="Phân cụm Ngang hàng PCA"
          value={company.cluster_id !== null ? `Cụm #${company.cluster_id}` : '—'}
          meta={translateClusterLabel(company.cluster_label)}
        />
        <MetricTile
          label="Tỷ suất Sinh lời (ROA / ROE)"
          value={`${formatPct(company.roa)} / ${formatPct(company.roe)}`}
          meta={`Tỷ lệ nợ: ${formatPct(company.debt_ratio)} · TT hiện hành: ${formatRatio(company.current_ratio)}`}
        />
      </div>

      {/* Analyst Workflow Tabs */}
      <div className="border-b border-[var(--border-subtle)] flex items-center gap-1 overflow-x-auto" role="tablist">
        {(
          [
            { id: 'overview', label: 'Đánh giá Rủi ro & TreeSHAP' },
            { id: 'financials', label: 'Tài chính, Dòng tiền & Định vị' },
            { id: 'diagnostics', label: 'DuPont, QoE & 8 Tín hiệu Kế toán' },
            { id: 'filings', label: `Báo cáo SEC & Cảnh báo (${history.length})` },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer bg-transparent whitespace-nowrap',
              activeTab === tab.id
                ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: TreeSHAP + 4-Pillar Radar + Recommendations */}
      {activeTab === 'overview' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <Panel className="lg:col-span-7">
            <PanelHeader
              title="Giải thích Tác động Rủi ro (TreeSHAP)"
              description={
                pred
                  ? `Các nhân tố chính đẩy rủi ro tăng (đỏ) hoặc giảm rủi ro (xanh) trong không gian ${pred.output_space} (Giá trị nền: ${formatSigned(pred.base_value)}).`
                  : 'Chưa có dữ liệu giải thích TreeSHAP cho loại báo cáo này.'
              }
            />
            <div className="p-4 h-[350px]">
              {shapChartData.length === 0 ? (
                <EmptyState
                  title="Chưa có yếu tố giải thích TreeSHAP"
                  description="Giải thích TreeSHAP được tính từ báo cáo thường niên 10-K. Hãy chuyển sang 10-K (Năm) ở góc trên."
                />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={shapChartData}
                    layout="vertical"
                    margin={{ top: 4, right: 24, left: 16, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                      axisLine={{ stroke: 'var(--border-subtle)' }}
                    />
                    <YAxis
                      type="category"
                      dataKey="feature"
                      width={205}
                      tick={{ fill: 'var(--text-primary)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <ReferenceLine x={0} stroke="var(--border-strong)" />
                    <Tooltip
                      formatter={(val: unknown) => [formatSigned(Number(val), 4), 'SHAP (log-odds)']}
                      contentStyle={{
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border-strong)',
                        borderRadius: '6px',
                        fontSize: '12px',
                      }}
                    />
                    <Bar dataKey="shap" radius={[3, 3, 3, 3]} maxBarSize={18}>
                      {shapChartData.map((entry) => (
                        <Cell
                          key={entry.rawFeature}
                          fill={entry.shap >= 0 ? '#BE123C' : '#0D7A68'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </Panel>

          <Panel className="lg:col-span-5">
            <PanelHeader
              title="4 Trụ cột Sức khỏe Tài chính"
              description="Đánh giá cân bằng 4 trụ cột cốt lõi và khuyến nghị quản trị rủi ro."
            />
            <div className="p-4 space-y-3">
              <HealthPillarsRadarChart pillars={data.health_pillars} />
              {data.health_pillars && Object.values(data.health_pillars.pillars).length > 0 ? (
                Object.values(data.health_pillars.pillars).map((pillar) => (
                  <div key={pillar.name} className="space-y-1">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-medium text-[var(--text-primary)]">
                        {pillar.label_vi || pillar.name}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="num text-[var(--text-secondary)]">
                          {formatScore(pillar.score)} / 100
                        </span>
                        <RiskBadge level={pillar.status} />
                      </div>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-[var(--bg-subtle)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--accent-primary)]"
                        style={{
                          width: `${Math.min(100, Math.max(0, pillar.score ?? 0))}%`,
                        }}
                      />
                    </div>
                  </div>
                ))
              ) : null}

              {data.recommendations.length > 0 ? (
                <div className="pt-3 mt-3 border-t border-[var(--border-subtle)] space-y-2">
                  <h3 className="text-xs font-semibold text-[var(--text-primary)]">
                    Khuyến nghị Hành động Quản trị
                  </h3>
                  {data.recommendations.slice(0, 3).map((rec, idx) => (
                    <div
                      key={`${rec.feature}-${idx}`}
                      className="p-3 rounded-[6px] bg-[var(--bg-subtle)] text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-[var(--text-primary)]">
                          {humanizeFeature(rec.feature)}
                        </span>
                        <RiskBadge level={rec.priority} />
                      </div>
                      <p className="text-[var(--text-secondary)] leading-relaxed">
                        {rec.action_vi}
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </Panel>
        </div>
      ) : null}

      {/* TAB 2: Financials, Capital Structure, Altman Zone, Peer Percentiles & Ratio Trends */}
      {activeTab === 'financials' ? (
        <div className="space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            <Panel className="lg:col-span-7">
              <PanelHeader
                title="Doanh thu, Lợi nhuận ròng & Dòng tiền hoạt động"
                description={`Diễn biến kết quả kinh doanh và năng lực tạo tiền từ báo cáo ${formType}.`}
              />
              <div className="p-4">
                <FinancialsComboChart history={history} />
              </div>
            </Panel>

            <Panel className="lg:col-span-5">
              <PanelHeader
                title="Cơ cấu Nguồn vốn (Nợ vs Vốn chủ sở hữu)"
                description="Theo dõi tích lũy đòn bẩy nợ hoặc củng cố vốn chủ sở hữu."
              />
              <div className="p-4">
                <CapitalStructureChart history={history} />
              </div>
            </Panel>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            <Panel className="lg:col-span-6">
              <PanelHeader
                title="Quỹ đạo Altman Z-Score & Vùng Cảnh báo"
                description="Vùng Kiệt quệ (< 1.81), Vùng Xám (1.81–2.99) và Vùng An toàn (> 2.99)."
              />
              <div className="p-4">
                <AltmanZoneChart history={history} />
              </div>
            </Panel>

            <Panel className="lg:col-span-6">
              <PanelHeader
                title="Xếp hạng Bách phân vị trong Ngành"
                description={
                  data.sector_peer_context
                    ? `Vị thế tương đối so với nhóm ${translateSector(data.sector_peer_context.sector)} (n = ${data.sector_peer_context.cohort_size}).`
                    : 'Xếp hạng các chỉ số tài chính so với doanh nghiệp cùng ngành.'
                }
              />
              <div className="p-4">
                <PeerPercentileChart context={data.sector_peer_context} />
              </div>
            </Panel>
          </div>

          <Panel>
            <PanelHeader
              title="Diễn biến Các tỷ số Tài chính Cốt lõi (%)"
              description={`Xu hướng ROA, Tỷ lệ nợ và Tỷ lệ dòng tiền hoạt động theo chuỗi báo cáo ${formType}.`}
            />
            <div className="p-4 h-[280px]">
              {historyChartData.length === 0 ? (
                <EmptyState
                  title="Chưa có chuỗi lịch sử"
                  description={`Không tìm thấy báo cáo ${formType} cho doanh nghiệp này.`}
                />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={historyChartData} margin={{ top: 8, right: 20, left: -8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                    <XAxis dataKey="period" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                    <YAxis unit="%" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border-strong)',
                        borderRadius: '6px',
                        fontSize: '12px',
                      }}
                    />
                    <Line type="monotone" dataKey="roa" name="ROA (%)" stroke="#0D7A68" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                    <Line type="monotone" dataKey="debt_ratio" name="Tỷ lệ nợ (%)" stroke="#BE123C" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                    <Line type="monotone" dataKey="ocf_ratio" name="Tỷ lệ OCF (%)" stroke="#1D4ED8" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </Panel>
        </div>
      ) : null}

      {/* TAB 3: DuPont, QoE & 8 Accounting Signals (100% Vietnamese!) */}
      {activeTab === 'diagnostics' ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Panel>
            <PanelHeader
              title="Phân tích DuPont 3 Nhân tố (ROE)"
              description="Phân rã tỷ suất sinh lời vốn chủ sở hữu theo biên lợi nhuận, vòng quay tài sản và đòn bẩy."
            />
            <div className="p-4 grid grid-cols-2 gap-3 text-xs">
              <div className="surface-subtle p-3.5">
                <div className="text-[var(--text-secondary)]">Biên lợi nhuận ròng</div>
                <div className="mt-1 text-base font-semibold num">
                  {formatPct(data.dupont?.net_profit_margin)}
                </div>
              </div>
              <div className="surface-subtle p-3.5">
                <div className="text-[var(--text-secondary)]">Vòng quay tài sản (BQ)</div>
                <div className="mt-1 text-base font-semibold num">
                  {formatRatio(data.dupont?.asset_turnover_avg)}x
                </div>
              </div>
              <div className="surface-subtle p-3.5">
                <div className="text-[var(--text-secondary)]">Đòn bẩy tài chính</div>
                <div className="mt-1 text-base font-semibold num">
                  {formatRatio(data.dupont?.equity_multiplier_avg)}x
                </div>
              </div>
              <div className="surface-subtle p-3.5">
                <div className="text-[var(--text-secondary)]">ROE DuPont (BQ)</div>
                <div className="mt-1 text-base font-semibold num">
                  {formatPct(data.dupont?.roe_dupont_avg)}
                </div>
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Chất lượng Lợi nhuận (QoE) & Dồn tích"
              description="Đánh giá mức độ chuyển hóa lợi nhuận kế toán thành dòng tiền thực tế."
            />
            <div className="p-4 grid grid-cols-2 gap-3 text-xs">
              <div className="surface-subtle p-3.5">
                <div className="text-[var(--text-secondary)]">Tỷ lệ chuyển đổi tiền (OCF / LN)</div>
                <div className="mt-1 text-base font-semibold num">
                  {formatRatio(data.quality_of_earnings?.cash_conversion_qoe)}x
                </div>
              </div>
              <div className="surface-subtle p-3.5">
                <div className="text-[var(--text-secondary)]">Chênh lệch dồn tích (USD)</div>
                <div className="mt-1 text-base font-semibold num">
                  {formatCompactUsd(data.quality_of_earnings?.accrual_gap_usd)}
                </div>
              </div>
              <div className="surface-subtle p-3.5">
                <div className="text-[var(--text-secondary)]">Tỷ lệ dồn tích dòng tiền</div>
                <div className="mt-1 text-base font-semibold num">
                  {formatPct(data.quality_of_earnings?.cash_flow_accruals_ratio)}
                </div>
              </div>
              <div className="surface-subtle p-3.5">
                <div className="text-[var(--text-secondary)]">Đánh giá chất lượng dòng tiền</div>
                <div className="mt-1 font-semibold text-[var(--text-primary)]">
                  {data.quality_of_earnings?.accruals_flag === 'CASH_BACKED_EARNINGS'
                    ? 'Lợi nhuận có dòng tiền hậu thuẫn'
                    : data.quality_of_earnings?.accruals_flag === 'EARNINGS_AHEAD_OF_CASH_WARNING'
                      ? 'Cảnh báo lợi nhuận vượt dòng tiền'
                      : '—'}
                </div>
              </div>
            </div>
          </Panel>

          <Panel className="lg:col-span-2">
            <PanelHeader
              title="Bảng kiểm 8 Tín hiệu Kế toán (Chuẩn Piotroski)"
              description={
                data.accounting_checklist
                  ? `Đạt ${data.accounting_checklist.observed_passes} / ${data.accounting_checklist.observed_checks} tiêu chí sức khỏe kế toán quan sát được.`
                  : 'Kiểm chứng 8 tín hiệu sinh lời, dòng tiền và đòn bẩy theo năm.'
              }
            />
            <div className="divide-y divide-[var(--border-subtle)]">
              {data.accounting_checklist ? (
                Object.entries(data.accounting_checklist.signals).map(([key, sig]) => (
                  <div
                    key={key}
                    className="px-5 py-3 flex flex-wrap items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5">
                      {sig.status === 'PASS' ? (
                        <CheckCircle2 className="h-4 w-4 text-[var(--risk-low-fg)] shrink-0" />
                      ) : sig.status === 'FAIL' ? (
                        <XCircle className="h-4 w-4 text-[var(--risk-critical-fg)] shrink-0" />
                      ) : (
                        <MinusCircle className="h-4 w-4 text-[var(--text-muted)] shrink-0" />
                      )}
                      <div>
                        <div className="font-semibold text-[var(--text-primary)]">
                          {humanizeFeature(key)}
                        </div>
                        <div className="text-[var(--text-secondary)]">
                          {translateSignalReason(sig.reason)}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 num text-[var(--text-secondary)]">
                      <span>Kỳ này: {formatRatio(sig.current_value, 3)}</span>
                      <span>Kỳ trước: {formatRatio(sig.prior_value, 3)}</span>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState
                  title="Chưa có bảng kiểm kế toán"
                  description="Cần tối thiểu hai năm báo cáo liên tiếp để đối chiếu biến động YoY."
                />
              )}
            </div>
          </Panel>
        </div>
      ) : null}

      {/* TAB 4: Filings & Alerts */}
      {activeTab === 'filings' ? (
        <div className="space-y-5">
          <Panel>
            <PanelHeader
              title={`Sổ Báo cáo Tài chính ${formType} đã lưu`}
              description="Số liệu kế toán nguyên bản kèm mã hồ sơ SEC (Accession). Giá trị khuyết thiếu hiển thị '—'."
            />
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                    <th className="py-2.5 px-4 font-semibold">Kỳ báo cáo</th>
                    <th className="py-2.5 px-3 font-semibold">Ngày công bố</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Doanh thu</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Lợi nhuận ròng</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Tổng tài sản</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Tổng nợ</th>
                    <th className="py-2.5 px-3 font-semibold text-right">OCF</th>
                    <th className="py-2.5 px-4 font-semibold">Mã hồ sơ SEC</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {[...history].reverse().map((row) => (
                    <tr key={`${row.fiscal_year}-${row.fiscal_period}-${row.accession_number}`} className="hover:bg-[var(--bg-hover)]">
                      <td className="py-2.5 px-4 font-mono font-medium">
                        FY{row.fiscal_year} {row.fiscal_period}
                      </td>
                      <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                        {formatDate(row.filed_date)}
                      </td>
                      <td className="py-2.5 px-3 text-right num">{formatCompactUsd(row.revenues)}</td>
                      <td className="py-2.5 px-3 text-right num">{formatCompactUsd(row.net_income)}</td>
                      <td className="py-2.5 px-3 text-right num">{formatCompactUsd(row.total_assets)}</td>
                      <td className="py-2.5 px-3 text-right num">
                        {formatCompactUsd(row.total_liabilities)}
                      </td>
                      <td className="py-2.5 px-3 text-right num">
                        {formatCompactUsd(row.operating_cash_flow)}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-[11px] text-[var(--text-muted)]">
                        {row.accession_number ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Cảnh báo Điều chỉnh & Biến động Báo cáo"
              description="Các cảnh báo phát hiện khi đối chiếu phiên bản báo cáo từ /api/v1/report-alerts."
            />
            <div className="p-4">
              {alertsQuery.isLoading ? (
                <TableSkeleton rows={3} />
              ) : (alertsQuery.data ?? []).length === 0 ? (
                <EmptyState
                  title="Không có cảnh báo biến động hồ sơ"
                  description="Chưa ghi nhận điều chỉnh trọng yếu hoặc vượt ngưỡng nào cho doanh nghiệp này."
                />
              ) : (
                <ul className="space-y-2">
                  {(alertsQuery.data ?? []).map((alert, idx) => (
                    <li
                      key={`${alert.filing_id}-${idx}`}
                      className="p-3 rounded-[6px] bg-[var(--bg-subtle)] text-xs flex flex-wrap items-center justify-between gap-2"
                    >
                      <div>
                        <span className="font-mono font-semibold text-[var(--text-primary)]">
                          {alert.rule}
                        </span>
                        <span className="ml-2 text-[var(--text-secondary)]">
                          Trường thay đổi: {alert.changed_fields.join(', ')}
                        </span>
                      </div>
                      <span className="num text-[var(--text-muted)]">
                        {formatDate(alert.published_on)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </div>
      ) : null}
    </div>
  );
}
