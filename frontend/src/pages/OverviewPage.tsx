import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowUpRight,
  Building2,
  FileSpreadsheet,
  GitCompare,
  Globe,
  PlusCircle,
  Sparkles,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import {
  BUSINESS_TYPE_LABELS,
  RELATIONSHIP_TAG_LABELS,
  formatPct,
  translateSector,
} from '@/lib/format';
import {
  Button,
  ErrorState,
  MetricTile,
  Panel,
  PanelHeader,
  Skeleton,
  TableSkeleton,
} from '@/components/ui/Primitives';

/** Monotonic PD -> 0..100 single Health Score aligned with backend map_pd_to_health_score. */
export function mapPdToSingleHealthScore(pd: number | null | undefined): number | null {
  if (typeof pd !== 'number' || !Number.isFinite(pd)) return null;
  const p = Math.max(0, Math.min(1, pd));
  if (p <= 0.01) return Number((100 - (p / 0.01) * 15).toFixed(1));
  if (p <= 0.03) return Number((85 - ((p - 0.01) / 0.02) * 20).toFixed(1));
  if (p <= 0.08) return Number((65 - ((p - 0.03) / 0.05) * 25).toFixed(1));
  return Number(Math.max(0, 40 - ((p - 0.08) / 0.92) * 40).toFixed(1));
}

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
    const sampleCount = orgCompanies.filter((c) => c.is_sample).length;
    return { total, eligible, excluded, sampleCount };
  }, [orgCompanies]);

  const secHighlights = useMemo(() => {
    const scored = secCompanies.filter(
      (c) => typeof c.distress_probability === 'number' && Number.isFinite(c.distress_probability),
    );
    const highAlert = scored.filter((c) => (c.distress_probability ?? 0) >= 0.08).length;
    const topWatch = [...scored]
      .sort((a, b) => (b.distress_probability ?? 0) - (a.distress_probability ?? 0))
      .slice(0, 6);
    return { total: secOverviewQuery.data?.company_count ?? secCompanies.length, highAlert, topWatch };
  }, [secCompanies, secOverviewQuery.data]);

  return (
    <div className="space-y-6 animate-view">
      {/* Page Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-[-0.025em] text-[var(--text-primary)]">
            Tổng quan Sức khỏe Doanh nghiệp
          </h1>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            {activeOrg
              ? `Không gian làm việc: ${activeOrg.name} · Quản lý danh bạ nội bộ (VND) song song với Thị trường Mỹ (SEC — USD).`
              : 'Đánh giá rủi ro tài chính doanh nghiệp minh bạch, trực quan và chuẩn mực.'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
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
        </div>
      </div>

      {/* Authenticated Organization Workspace Section */}
      {user && activeOrg ? (
        <>
          {seedFeedback ? (
            <div
              role="status"
              className="p-3.5 rounded-[8px] text-xs font-medium flex items-center justify-between gap-3"
              style={{
                backgroundColor: 'var(--risk-low-bg)',
                color: 'var(--risk-low-fg)',
              }}
            >
              <span>{seedFeedback}</span>
              <button
                type="button"
                onClick={() => setSeedFeedback(null)}
                className="underline cursor-pointer bg-transparent border-0 text-inherit"
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

          {/* M02: 1-Click Sample Onboarding Card when Workspace is Empty */}
          {!orgCompaniesQuery.isLoading && orgCompanies.length === 0 ? (
            <section
              aria-label="Khởi tạo nhanh doanh nghiệp mẫu"
              className="surface p-6 sm:p-8 border-2 border-dashed border-[var(--accent-primary)]/40"
            >
              <div className="max-w-2xl space-y-3">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-[var(--accent-soft)] text-[var(--accent-primary)]">
                  <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                  Bắt đầu trong 30 giây
                </div>
                <h2 className="text-lg font-bold text-[var(--text-primary)]">
                  Không gian làm việc của bạn chưa có doanh nghiệp nào
                </h2>
                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  Trải nghiệm ngay trọn bộ phân tích 5 trụ cột, Điểm Tựa & Điểm Nghẽn tài chính,
                  Altman Z-Score và lịch sử đa kỳ 4–5 năm bằng cách khởi tạo 3 hồ sơ doanh nghiệp
                  mẫu Việt Nam (Vững mạnh · Suy giảm ngầm · Nguy cơ cao), hoặc tự tạo doanh nghiệp
                  đầu tiên của bạn.
                </p>
                <div className="pt-2 flex flex-wrap items-center gap-3">
                  {canWrite ? (
                    <Button
                      variant="primary"
                      onClick={() => seedSamplesMutation.mutate()}
                      disabled={seedSamplesMutation.isPending}
                    >
                      <Sparkles className="h-4 w-4" aria-hidden="true" />
                      {seedSamplesMutation.isPending
                        ? 'Đang khởi tạo 3 DN mẫu...'
                        : 'Khởi tạo 3 Doanh nghiệp mẫu Việt Nam'}
                    </Button>
                  ) : null}
                  <Button variant="secondary" onClick={() => navigate('/portfolio')}>
                    <Building2 className="h-4 w-4" aria-hidden="true" />
                    Tự thêm Doanh nghiệp mới
                  </Button>
                </div>
              </div>
            </section>
          ) : (
            <>
              {/* Workspace KPI Strip */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {orgCompaniesQuery.isLoading ? (
                  Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[88px]" />)
                ) : (
                  <>
                    <MetricTile
                      label="Doanh nghiệp đang quản lý"
                      value={String(orgStats.total)}
                      meta={`Workspace: ${activeOrg.name}`}
                    />
                    <MetricTile
                      label="Đủ điều kiện chấm điểm"
                      value={String(orgStats.eligible)}
                      meta="Doanh nghiệp phi tài chính"
                      accent="low"
                    />
                    <MetricTile
                      label="Loại trừ chấm điểm (TCTC)"
                      value={String(orgStats.excluded)}
                      meta="Ngân hàng, Bảo hiểm, TCTC"
                    />
                    <MetricTile
                      label="Kho Thị trường Mỹ (SEC)"
                      value={String(secHighlights.total)}
                      meta="Dữ liệu đối chiếu USD"
                    />
                  </>
                )}
              </div>

              {/* Org Portfolio Quick Table */}
              <Panel>
                <PanelHeader
                  title="Danh bạ Doanh nghiệp của Tổ chức"
                  description="Chọn doanh nghiệp để xem đánh giá sức khỏe tài chính chi tiết, 5 trụ cột và xuất báo cáo PDF."
                  actions={
                    <div className="flex items-center gap-2">
                      {canWrite && orgStats.sampleCount === 0 ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => seedSamplesMutation.mutate()}
                          disabled={seedSamplesMutation.isPending}
                        >
                          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                          Nạp 3 DN mẫu
                        </Button>
                      ) : null}
                      <Link
                        to="/portfolio"
                        className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent-primary)] hover:underline no-underline"
                      >
                        Xem tất cả <ArrowUpRight className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  }
                />

                {orgCompaniesQuery.isLoading ? (
                  <TableSkeleton rows={4} />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50 text-[var(--text-secondary)]">
                          <th className="py-2.5 px-4 font-semibold">Doanh nghiệp</th>
                          <th className="py-2.5 px-3 font-semibold">MST / Mã CK</th>
                          <th className="py-2.5 px-3 font-semibold">Loại hình</th>
                          <th className="py-2.5 px-3 font-semibold">Quan hệ</th>
                          <th className="py-2.5 px-4 font-semibold text-right">Hồ sơ</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-subtle)]">
                        {orgCompanies.slice(0, 8).map((company) => (
                          <tr
                            key={company.id}
                            className="hover:bg-[var(--bg-hover)]/45 transition-colors"
                          >
                            <td className="py-3 px-4">
                              <Link
                                to={`/portfolio/${company.id}`}
                                className="font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)] no-underline"
                              >
                                {company.name}
                              </Link>
                              {company.is_sample ? (
                                <span className="ml-2 text-[10px] font-medium px-1.5 py-0.5 rounded bg-[var(--accent-soft)] text-[var(--accent-primary)]">
                                  Mẫu VN
                                </span>
                              ) : null}
                              {company.sector_name ? (
                                <div className="text-[11px] text-[var(--text-muted)]">
                                  {company.sector_name}
                                </div>
                              ) : null}
                            </td>
                            <td className="py-3 px-3 num text-[var(--text-secondary)]">
                              {company.tax_code || company.ticker || '—'}
                            </td>
                            <td className="py-3 px-3 text-[var(--text-secondary)]">
                              {BUSINESS_TYPE_LABELS[company.business_type] ?? company.business_type}
                            </td>
                            <td className="py-3 px-3">
                              <span className="px-2 py-0.5 rounded-full bg-[var(--bg-subtle)] text-[var(--text-secondary)] text-[11px]">
                                {RELATIONSHIP_TAG_LABELS[company.relationship_tag] ??
                                  company.relationship_tag}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <Link
                                to={`/portfolio/${company.id}`}
                                className="inline-flex items-center gap-1 font-medium text-[var(--accent-primary)] hover:underline no-underline"
                              >
                                Xem đánh giá <ArrowUpRight className="h-3.5 w-3.5" />
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            </>
          )}
        </>
      ) : (
        /* Unauthenticated Welcome Banner */
        <Panel className="p-6 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1 max-w-2xl">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">
              Đăng nhập để quản lý Danh bạ Doanh nghiệp & Thẩm định Hàng loạt
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Tạo tài khoản miễn phí để nhập BCTC chuẩn TT99/TT200/TT133, nạp XML HTKK, chấm điểm
              sức khỏe doanh nghiệp và xuất báo cáo PDF chuyên nghiệp.
            </p>
          </div>
          <Button variant="primary" size="sm" onClick={() => navigate('/account')}>
            Đăng nhập / Đăng ký
          </Button>
        </Panel>
      )}

      {/* Clearly Separated US Market (SEC EDGAR — USD) Snapshot */}
      <Panel>
        <PanelHeader
          title="Thị trường Mỹ (SEC EDGAR — USD)"
          description="Kho dữ liệu công bố công khai từ Ủy ban Chứng khoán Hoa Kỳ (USD) dùng để sàng lọc và đối chiếu chuẩn ngành."
          actions={
            <Link
              to="/us-market"
              className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent-primary)] hover:underline no-underline"
            >
              <Globe className="h-3.5 w-3.5" aria-hidden="true" />
              Mở Thị trường Mỹ (SEC)
            </Link>
          }
        />

        {secCompaniesQuery.isLoading ? (
          <TableSkeleton rows={4} />
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
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50 text-[var(--text-secondary)]">
                  <th className="py-2.5 px-4 font-semibold">Mã / Doanh nghiệp (USD)</th>
                  <th className="py-2.5 px-3 font-semibold">Ngành</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Điểm Sức khỏe</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Nguy cơ 12T</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Chi tiết</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {secHighlights.topWatch.map((item) => {
                  const id = item.ticker || item.cik;
                  const unifiedScore = mapPdToSingleHealthScore(item.distress_probability);
                  return (
                    <tr
                      key={item.cik}
                      className="hover:bg-[var(--bg-hover)]/45 transition-colors"
                    >
                      <td className="py-2.5 px-4">
                        <span className="num font-semibold text-[var(--accent-primary)] mr-2">
                          {item.ticker ?? item.cik}
                        </span>
                        <span className="text-[var(--text-primary)]">{item.name}</span>
                      </td>
                      <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                        {translateSector(item.sector)}
                      </td>
                      <td className="py-2.5 px-3 text-right num font-semibold text-[var(--text-primary)]">
                        {unifiedScore !== null ? `${unifiedScore.toFixed(1)} / 100` : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right num text-[var(--text-primary)]">
                        {formatPct(item.distress_probability, 2)}
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <Link
                          to={`/us-market/${encodeURIComponent(id)}`}
                          className="inline-flex items-center gap-1 font-medium text-[var(--accent-primary)] hover:underline no-underline"
                        >
                          Mở hồ sơ <ArrowUpRight className="h-3.5 w-3.5" />
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
    </div>
  );
}
