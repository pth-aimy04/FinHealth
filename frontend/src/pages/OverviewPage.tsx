import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowUpRight,
  Building2,
  Database,
  FileSpreadsheet,
  GitCompare,
  Globe2,
  PlusCircle,
  SlidersHorizontal,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import {
  BUSINESS_TYPE_LABELS,
  RELATIONSHIP_TAG_LABELS,
  RISK_TIER_META,
  formatPct,
  formatScore,
  translateSector,
} from '@/lib/format';
import {
  Button,
  ErrorState,
  InlineProbBar,
  MetricStrip,
  MetricTile,
  PageHeader,
  Panel,
  PanelHeader,
  RiskBadge,
  Skeleton,
  TableSkeleton,
} from '@/components/ui/Primitives';
import { SectorRiskChart } from '@/components/charts/OverviewCharts';

/** Monotonic PD -> 0..100 single Health Score aligned with backend map_pd_to_health_score (80/60/35). */
export function mapPdToSingleHealthScore(pd: number | null | undefined): number | null {
  if (typeof pd !== 'number' || !Number.isFinite(pd)) return null;
  const p = Math.max(0, Math.min(1, pd));
  if (p < 0.01) return Number((100 - 20 * (p / 0.01)).toFixed(1));
  if (p < 0.03) return Number((80 - 20 * ((p - 0.01) / 0.02)).toFixed(1));
  if (p < 0.08) return Number((60 - 25 * ((p - 0.03) / 0.05)).toFixed(1));
  const tail = Math.min(
    1,
    Math.log1p((p - 0.08) / 0.08) / Math.log1p((1 - 0.08) / 0.08),
  );
  return Number(Math.max(0, 35 * (1 - tail)).toFixed(1));
}

const SAMPLE_ARCHETYPES = [
  {
    name: 'Hồ sơ Mẫu 01 · Doanh nghiệp Vững mạnh',
    profile: 'Thanh khoản tốt, dòng tiền hoạt động dương đều, đòn bẩy thấp',
    tier: 'Vững mạnh (80–100)',
    tone: 'var(--risk-low-fg)',
  },
  {
    name: 'Hồ sơ Mẫu 02 · Suy giảm Ngầm',
    profile: 'Lợi nhuận kế toán dương nhưng tồn kho & phải thu phình to, OCF âm',
    tier: 'Theo dõi sát (35–60)',
    tone: 'var(--risk-medium-fg)',
  },
  {
    name: 'Hồ sơ Mẫu 03 · Áp lực Tín dụng Cao',
    profile: 'Nợ ngắn hạn lớn, biên lợi nhuận suy giảm mạnh, rủi ro 12T cao',
    tier: 'Nguy cơ cao (< 35)',
    tone: 'var(--risk-critical-fg)',
  },
];

export function OverviewPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, activeOrg, activeOrgRole } = useAuth();
  const [seedFeedback, setSeedFeedback] = useState<string | null>(null);

  const canWrite = activeOrgRole === 'analyst' || activeOrgRole === 'org_admin';

  const orgCompaniesQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'companies'],
    queryFn: () => api.getOrgCompanies(),
    enabled: Boolean(user && activeOrg),
  });

  const secOverviewQuery = useQuery({
    queryKey: ['overview'],
    queryFn: api.getOverview,
  });

  const secCompaniesQuery = useQuery({
    queryKey: ['companies', { limit: 120 }],
    queryFn: () => api.getCompanies({ limit: 120 }),
  });

  const seedSamplesMutation = useMutation({
    mutationFn: () => api.seedOrgSamples(),
    onSuccess: (res) => {
      setSeedFeedback(
        res.created_companies > 0
          ? `Đã khởi tạo ${res.created_companies} doanh nghiệp mẫu Việt Nam (${res.created_statements} kỳ BCTC).`
          : 'Bộ 3 doanh nghiệp mẫu Việt Nam đã có sẵn trong không gian làm việc.',
      );
      void queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'companies'] });
    },
  });

  const orgCompanies = orgCompaniesQuery.data ?? [];
  const secCompanies = secCompaniesQuery.data ?? [];

  const orgStats = useMemo(() => {
    const total = orgCompanies.length;
    const eligible = orgCompanies.filter((c) => c.scoring_eligible).length;
    const excluded = total - eligible;
    const watchOrCritical = orgCompanies.filter(
      (c) => c.latest_risk_tier === 'WATCH' || c.latest_risk_tier === 'CRITICAL',
    ).length;
    const sampleCount = orgCompanies.filter((c) => c.is_sample).length;
    return { total, eligible, excluded, watchOrCritical, sampleCount };
  }, [orgCompanies]);

  const secHighlights = useMemo(() => {
    const scored = secCompanies.filter(
      (c) => typeof c.distress_probability === 'number' && Number.isFinite(c.distress_probability),
    );
    const highAlert = scored.filter((c) => (c.distress_probability ?? 0) >= 0.08).length;
    const avgScore =
      scored.length > 0
        ? scored.reduce((acc, c) => acc + (mapPdToSingleHealthScore(c.distress_probability) ?? 0), 0) /
          scored.length
        : null;
    const topWatch = [...scored]
      .sort((a, b) => (b.distress_probability ?? 0) - (a.distress_probability ?? 0))
      .slice(0, 7);
    return {
      total: secOverviewQuery.data?.company_count ?? secCompanies.length,
      highAlert,
      avgScore,
      topWatch,
    };
  }, [secCompanies, secOverviewQuery.data]);

  return (
    <div className="space-y-6 animate-view">
      {/* Institutional Page Masthead */}
      <PageHeader
        title="Bảng điều hành Sức khỏe Tài chính"
        description={
          activeOrg
            ? `Không gian tổ chức: ${activeOrg.name} · Quản trị danh bạ doanh nghiệp nội bộ (VND) song song với kho đối chiếu thị trường Mỹ SEC EDGAR (USD).`
            : 'Hệ thống thẩm định sức khỏe tài chính doanh nghiệp và cảnh báo sớm nguy cơ kiệt quệ 12 tháng.'
        }
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => navigate('/batch')}>
              <FileSpreadsheet className="h-3.5 w-3.5" aria-hidden="true" />
              Thẩm định Hàng loạt
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('/compare')}>
              <GitCompare className="h-3.5 w-3.5" aria-hidden="true" />
              So sánh Doanh nghiệp
            </Button>
            <Button variant="primary" size="sm" onClick={() => navigate('/portfolio')}>
              <PlusCircle className="h-3.5 w-3.5" aria-hidden="true" />
              Danh bạ Doanh nghiệp
            </Button>
          </>
        }
      />

      {/* Feedback / Error Banners */}
      {seedFeedback ? (
        <div
          role="status"
          className="px-4 py-3 rounded-[3px] border text-xs font-semibold flex items-center justify-between gap-3"
          style={{
            backgroundColor: 'var(--risk-low-bg)',
            color: 'var(--risk-low-fg)',
            borderColor: 'var(--risk-low-border)',
          }}
        >
          <span>{seedFeedback}</span>
          <button
            type="button"
            onClick={() => setSeedFeedback(null)}
            className="underline cursor-pointer bg-transparent border-0 text-inherit font-semibold"
          >
            Đóng
          </button>
        </div>
      ) : null}

      {seedSamplesMutation.isError ? (
        <ErrorState
          title="Không thể khởi tạo doanh nghiệp mẫu"
          message={
            seedSamplesMutation.error instanceof Error
              ? seedSamplesMutation.error.message
              : 'Đã xảy ra lỗi khi tạo dữ liệu mẫu.'
          }
        />
      ) : null}

      {/* Unified Horizontal KPI Ledger Strip (Zero Floating Shadow Boxes) */}
      {user && activeOrg ? (
        orgCompaniesQuery.isLoading ? (
          <Skeleton className="h-[92px] w-full" />
        ) : (
          <MetricStrip columns={4}>
            <MetricTile
              bare
              label="Hồ sơ trong Danh bạ Tổ chức"
              value={String(orgStats.total)}
              meta={`Đủ điều kiện chấm điểm: ${orgStats.eligible} · Loại trừ TCTC: ${orgStats.excluded}`}
            />
            <MetricTile
              bare
              label="Doanh nghiệp cần theo dõi"
              value={String(orgStats.watchOrCritical)}
              meta="Xếp loại Theo dõi sát hoặc Nguy cơ cao"
              accent={orgStats.watchOrCritical > 0 ? 'critical' : 'low'}
            />
            <MetricTile
              bare
              label="Kho đối chiếu SEC EDGAR (USD)"
              value={String(secHighlights.total)}
              meta={`${secHighlights.highAlert} mã có nguy cơ 12T ≥ 8,0%`}
            />
            <MetricTile
              bare
              label="Điểm Sức khỏe TB (SEC)"
              value={secHighlights.avgScore !== null ? `${secHighlights.avgScore.toFixed(1)} / 100` : '—'}
              meta="Thang điểm đơn điệu chuẩn hóa 0–100"
            />
          </MetricStrip>
        )
      ) : (
        <MetricStrip columns={3}>
          <MetricTile
            bare
            label="Kho doanh nghiệp SEC EDGAR (USD)"
            value={String(secHighlights.total)}
            meta="Báo cáo 10-K / 10-Q đã chuẩn hóa"
          />
          <MetricTile
            bare
            label="Cảnh báo Nguy cơ Cao (≥ 8%)"
            value={String(secHighlights.highAlert)}
            meta="Xác suất kiệt quệ 12 tháng hiệu chuẩn"
            accent={secHighlights.highAlert > 0 ? 'critical' : 'low'}
          />
          <MetricTile
            bare
            label="Chuẩn BCTC Việt Nam hỗ trợ"
            value="TT99 · TT200 · TT133"
            meta="Nhập Web 3 phần, Excel mẫu & XML HTKK"
          />
        </MetricStrip>
      )}

      {/* Main Asymmetric Analytical Workspace (8 / 4 Institutional Split) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Left 8 Columns: Organization Portfolio Ledger OR Structured Quick-Start */}
        <div className="xl:col-span-8 min-w-0 space-y-6">
          {user && activeOrg ? (
            !orgCompaniesQuery.isLoading && orgCompanies.length === 0 ? (
              <Panel ruled className="overflow-hidden">
                <PanelHeader
                  title="Khởi tạo Không gian Thẩm định Doanh nghiệp"
                  description="Nạp sẵn 3 bộ hồ sơ doanh nghiệp mẫu Việt Nam (đa kỳ 4–5 năm) để kiểm nghiệm toàn bộ công cụ phân tích, hoặc thêm trực tiếp hồ sơ khách hàng đầu tiên."
                  actions={
                    <div className="flex flex-wrap items-center gap-2">
                      {canWrite ? (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => seedSamplesMutation.mutate()}
                          disabled={seedSamplesMutation.isPending}
                        >
                          <Database className="h-3.5 w-3.5" aria-hidden="true" />
                          {seedSamplesMutation.isPending
                            ? 'Đang khởi tạo...'
                            : 'Khởi tạo 3 Doanh nghiệp mẫu Việt Nam'}
                        </Button>
                      ) : null}
                      <Button variant="secondary" size="sm" onClick={() => navigate('/portfolio')}>
                        <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
                        Tự thêm Doanh nghiệp mới
                      </Button>
                    </div>
                  }
                />
                <div className="overflow-x-auto">
                  <table className="ledger-table">
                    <thead>
                      <tr>
                        <th>Bộ hồ sơ mẫu tích hợp</th>
                        <th>Kịch bản tài chính minh họa</th>
                        <th className="text-right">Nhóm phân loại</th>
                      </tr>
                    </thead>
                    <tbody>
                      {SAMPLE_ARCHETYPES.map((row) => (
                        <tr key={row.name}>
                          <td className="font-semibold text-[var(--text-primary)]">{row.name}</td>
                          <td className="text-[var(--text-secondary)]">{row.profile}</td>
                          <td className="text-right num font-semibold" style={{ color: row.tone }}>
                            {row.tier}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            ) : (
              <Panel ruled className="overflow-hidden">
                <PanelHeader
                  title="Danh bạ Doanh nghiệp của Tổ chức (VND)"
                  description="Bấm vào tên doanh nghiệp để mở Credit Tearsheet 5 trụ cột, Điểm Tựa / Điểm Nghẽn và xuất báo cáo A4 PDF."
                  actions={
                    <div className="flex items-center gap-2">
                      {canWrite && orgStats.sampleCount === 0 ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => seedSamplesMutation.mutate()}
                          disabled={seedSamplesMutation.isPending}
                        >
                          <Database className="h-3.5 w-3.5" aria-hidden="true" />
                          Nạp 3 DN mẫu
                        </Button>
                      ) : null}
                      <Link
                        to="/portfolio"
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--accent-primary)] hover:underline no-underline"
                      >
                        Mở toàn bộ danh bạ <ArrowUpRight className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  }
                />

                {orgCompaniesQuery.isLoading ? (
                  <TableSkeleton rows={5} />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="ledger-table">
                      <thead>
                        <tr>
                          <th>Doanh nghiệp</th>
                          <th>MST / Mã CK</th>
                          <th>Quan hệ · Loại hình</th>
                          <th className="text-right">Điểm & Xếp loại</th>
                          <th className="text-right">Hồ sơ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {orgCompanies.slice(0, 8).map((company) => {
                          const tierMeta =
                            company.latest_risk_tier && RISK_TIER_META[company.latest_risk_tier]
                              ? RISK_TIER_META[company.latest_risk_tier]
                              : null;
                          return (
                            <tr key={company.id}>
                              <td>
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <Link
                                    to={`/portfolio/${company.id}`}
                                    className="font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)] no-underline"
                                  >
                                    {company.name}
                                  </Link>
                                  {company.is_sample ? (
                                    <span className="text-[10px] font-semibold uppercase tracking-[0.04em] px-1.5 py-0.5 rounded-[2px] bg-[var(--accent-soft)] text-[var(--accent-primary)] border border-[var(--accent-border)]">
                                      Mẫu VN
                                    </span>
                                  ) : null}
                                </div>
                                {company.sector_name ? (
                                  <div className="text-[11px] text-[var(--text-muted)] mt-0.5">
                                    {company.sector_name}
                                  </div>
                                ) : null}
                              </td>
                              <td className="num text-[var(--text-secondary)]">
                                {company.tax_code || company.ticker || '—'}
                              </td>
                              <td>
                                <div className="text-xs font-medium text-[var(--text-primary)]">
                                  {RELATIONSHIP_TAG_LABELS[company.relationship_tag] ??
                                    company.relationship_tag}
                                </div>
                                <div className="text-[11px] text-[var(--text-muted)]">
                                  {BUSINESS_TYPE_LABELS[company.business_type] ?? company.business_type}
                                </div>
                              </td>
                              <td className="text-right whitespace-nowrap">
                                {!company.scoring_eligible ? (
                                  <span className="inline-block px-2 py-0.5 rounded-[2px] border border-[var(--risk-medium-border)] bg-[var(--risk-medium-bg)] text-[var(--risk-medium-fg)] text-[11px] font-semibold">
                                    Loại trừ (TCTC)
                                  </span>
                                ) : tierMeta ? (
                                  <div className="inline-flex items-center gap-2">
                                    <span className="num font-bold text-[var(--text-primary)]">
                                      {formatScore(company.latest_health_score, 1)}
                                    </span>
                                    <span
                                      className="px-2 py-0.5 rounded-[2px] border text-[11px] font-semibold"
                                      style={{
                                        color: tierMeta.fg,
                                        backgroundColor: tierMeta.bg,
                                        borderColor: 'currentColor',
                                      }}
                                    >
                                      {tierMeta.label}
                                    </span>
                                  </div>
                                ) : (
                                  <span className="text-xs text-[var(--text-muted)]">Chờ chốt BCTC</span>
                                )}
                              </td>
                              <td className="text-right whitespace-nowrap">
                                <Link
                                  to={`/portfolio/${company.id}`}
                                  className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--accent-primary)] hover:underline no-underline"
                                >
                                  Xem đánh giá <ArrowUpRight className="h-3.5 w-3.5" />
                                </Link>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            )
          ) : (
            <Panel ruled className="p-5 sm:p-6 flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1.5 max-w-2xl">
                <h2 className="font-editorial text-lg font-bold text-[var(--text-primary)] m-0">
                  Không gian Thẩm định Doanh nghiệp Nội bộ (VND)
                </h2>
                <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed m-0">
                  Đăng nhập để quản trị danh mục khách hàng & đối tác, nhập BCTC chuẩn TT99/TT200/TT133,
                  nạp trực tiếp tệp XML HTKK, chạy thẩm định hàng loạt Excel và xuất báo cáo A4 PDF.
                </p>
              </div>
              <Button variant="primary" size="md" onClick={() => navigate('/account')}>
                Đăng nhập / Đăng ký
              </Button>
            </Panel>
          )}

          {/* SEC Reference Watchlist Ledger (USD) */}
          <Panel className="overflow-hidden">
            <PanelHeader
              title="Danh sách Giám sát Rủi ro — Thị trường Mỹ (SEC EDGAR · USD)"
              description="Các doanh nghiệp niêm yết Hoa Kỳ có xác suất nguy cơ 12 tháng cao nhất trong kho đối chiếu công khai."
              actions={
                <Link
                  to="/us-market"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--accent-primary)] hover:underline no-underline"
                >
                  <Globe2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Mở Bộ lọc SEC
                </Link>
              }
            />

            {secCompaniesQuery.isLoading ? (
              <TableSkeleton rows={5} />
            ) : secCompaniesQuery.isError ? (
              <div className="p-4">
                <ErrorState
                  title="Không thể tải dữ liệu Thị trường Mỹ (SEC)"
                  message={
                    secCompaniesQuery.error instanceof Error
                      ? secCompaniesQuery.error.message
                      : 'Vui lòng thử lại sau.'
                  }
                  onRetry={() => void secCompaniesQuery.refetch()}
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Mã / Doanh nghiệp (USD)</th>
                      <th>Ngành</th>
                      <th className="text-right">Điểm Sức khỏe</th>
                      <th className="text-right">Nguy cơ 12T</th>
                      <th className="text-right">Mức rủi ro</th>
                    </tr>
                  </thead>
                  <tbody>
                    {secHighlights.topWatch.map((item) => {
                      const id = item.ticker || item.cik;
                      const unifiedScore = mapPdToSingleHealthScore(item.distress_probability);
                      return (
                        <tr key={item.cik}>
                          <td>
                            <Link
                              to={`/us-market/${encodeURIComponent(id)}`}
                              className="inline-flex items-center gap-2 no-underline group"
                            >
                              <span className="num text-xs font-bold px-1.5 py-0.5 rounded-[2px] bg-[var(--accent-soft)] text-[var(--accent-primary)] border border-[var(--accent-border)]">
                                {item.ticker ?? item.cik}
                              </span>
                              <span className="font-semibold text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] truncate max-w-[220px]">
                                {item.name}
                              </span>
                            </Link>
                          </td>
                          <td className="text-[var(--text-secondary)]">
                            {translateSector(item.sector)}
                          </td>
                          <td className="text-right">
                            <InlineProbBar value={unifiedScore} tone="health" />
                          </td>
                          <td className="text-right num font-semibold text-[var(--text-primary)]">
                            {formatPct(item.distress_probability, 2)}
                          </td>
                          <td className="text-right">
                            <RiskBadge level={item.risk_level} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        {/* Right 4 Columns: Sector Risk Distribution & Analytical Tools Rail */}
        <div className="xl:col-span-4 min-w-0 space-y-6">
          <Panel className="overflow-hidden">
            <PanelHeader
              title="Phân bổ Rủi ro theo Ngành (SEC)"
              description="Cơ cấu mức độ rủi ro tín dụng trên kho doanh nghiệp đối chiếu."
            />
            <div className="p-4">
              {secCompaniesQuery.isLoading ? (
                <Skeleton className="h-[260px] w-full" />
              ) : (
                <SectorRiskChart companies={secCompanies} />
              )}
            </div>
          </Panel>

          <Panel className="overflow-hidden">
            <PanelHeader
              title="Công cụ Nghiệp vụ Nhanh"
              description="Truy cập trực tiếp các quy trình thẩm định cốt lõi."
            />
            <div className="divide-y divide-[var(--border-subtle)]">
              <Link
                to="/batch"
                className="flex items-center justify-between gap-3 px-4 py-3.5 hover:bg-[var(--bg-hover)] no-underline transition-colors"
              >
                <div className="flex items-start gap-2.5">
                  <FileSpreadsheet className="h-4 w-4 text-[var(--accent-primary)] mt-0.5 shrink-0" />
                  <div>
                    <div className="text-[13px] font-semibold text-[var(--text-primary)]">
                      Thẩm định Danh mục Excel theo Lô
                    </div>
                    <div className="text-xs text-[var(--text-secondary)]">
                      Chấm điểm tới 500 doanh nghiệp & xếp hạng ưu tiên rủi ro
                    </div>
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-[var(--text-muted)] shrink-0" />
              </Link>

              <Link
                to="/compare"
                className="flex items-center justify-between gap-3 px-4 py-3.5 hover:bg-[var(--bg-hover)] no-underline transition-colors"
              >
                <div className="flex items-start gap-2.5">
                  <GitCompare className="h-4 w-4 text-[var(--accent-primary)] mt-0.5 shrink-0" />
                  <div>
                    <div className="text-[13px] font-semibold text-[var(--text-primary)]">
                      So sánh Trực diện 2–4 Doanh nghiệp
                    </div>
                    <div className="text-xs text-[var(--text-secondary)]">
                      Đối chiếu Điểm Sức khỏe, Altman Z & tỷ số tài chính
                    </div>
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-[var(--text-muted)] shrink-0" />
              </Link>

              <Link
                to="/stress"
                className="flex items-center justify-between gap-3 px-4 py-3.5 hover:bg-[var(--bg-hover)] no-underline transition-colors"
              >
                <div className="flex items-start gap-2.5">
                  <SlidersHorizontal className="h-4 w-4 text-[var(--accent-primary)] mt-0.5 shrink-0" />
                  <div>
                    <div className="text-[13px] font-semibold text-[var(--text-primary)]">
                      Mô phỏng Sức chịu đựng (Stress Test)
                    </div>
                    <div className="text-xs text-[var(--text-secondary)]">
                      Giả lập cú sốc doanh thu, nợ vay & dòng tiền (What-If)
                    </div>
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-[var(--text-muted)] shrink-0" />
              </Link>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
