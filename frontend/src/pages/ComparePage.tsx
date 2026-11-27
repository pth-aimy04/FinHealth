import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Building2, Globe, Plus, Scale, X } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { RISK_TIER_META, formatPct, formatRatio, formatScore } from '@/lib/format';
import {
  Button,
  EmptyState,
  ErrorState,
  Panel,
  PanelHeader,
  TableSkeleton,
  cn,
} from '@/components/ui/Primitives';
import { mapPdToSingleHealthScore } from './OverviewPage';

const DEFAULT_SEC_PEERS = ['AAPL', 'MSFT', 'AAL'];
const MAX_COMPARE_COUNT = 4;

export function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, activeOrg } = useAuth();

  const initialSource = searchParams.get('source') === 'org' && user ? 'org' : 'sec';
  const [source, setSource] = useState<'org' | 'sec'>(initialSource);
  const [inputTicker, setInputTicker] = useState('');
  const [selectedOrgIdToAdd, setSelectedOrgIdToAdd] = useState('');
  const [limitNotice, setLimitNotice] = useState<string | null>(null);

  const idsParam = searchParams.get('ids');
  const secIdentifiers =
    source === 'sec'
      ? idsParam
          ? idsParam
              .split(',')
              .map((s) => s.trim().toUpperCase())
              .filter(Boolean)
              .slice(0, MAX_COMPARE_COUNT)
          : DEFAULT_SEC_PEERS
      : [];

  const orgCompanyIds =
    source === 'org' && idsParam
      ? idsParam
          .split(',')
          .map((s) => Number(s.trim()))
          .filter((n) => Number.isInteger(n) && n > 0)
          .slice(0, MAX_COMPARE_COUNT)
      : [];

  const useCommonYear = searchParams.get('common_year') !== null;
  const commonYearValue = useCommonYear
    ? Number(searchParams.get('common_year')) || new Date().getFullYear() - 1
    : null;

  const orgListQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'companies'],
    queryFn: () => api.getOrgCompanies(),
    enabled: Boolean(user && activeOrg && source === 'org'),
  });

  const secCompareQuery = useQuery({
    queryKey: ['compare', 'sec', secIdentifiers.join(','), commonYearValue ?? 'latest'],
    queryFn: () => api.compareCompanies(secIdentifiers, commonYearValue),
    enabled: source === 'sec' && secIdentifiers.length >= 2,
  });

  const orgCompareQuery = useQuery({
    queryKey: [
      'compare',
      'org',
      activeOrg?.id,
      orgCompanyIds.join(','),
      commonYearValue ?? 'latest',
    ],
    queryFn: () => api.compareOrgCompanies(orgCompanyIds, commonYearValue),
    enabled: source === 'org' && Boolean(user && activeOrg) && orgCompanyIds.length >= 2,
  });

  function updateSearch(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null) next.delete(k);
      else next.set(k, v);
    }
    setSearchParams(next, { replace: true });
  }

  function switchSource(nextSource: 'org' | 'sec') {
    setSource(nextSource);
    setLimitNotice(null);
    updateSearch({ source: nextSource, ids: null });
  }

  function addSecTicker(e: React.FormEvent) {
    e.preventDefault();
    const cleaned = inputTicker.trim().toUpperCase();
    if (!cleaned || secIdentifiers.includes(cleaned)) return;
    if (secIdentifiers.length >= MAX_COMPARE_COUNT) {
      setLimitNotice('Chỉ hỗ trợ so sánh tối đa 4 doanh nghiệp cùng lúc.');
      return;
    }
    setLimitNotice(null);
    updateSearch({ source: 'sec', ids: [...secIdentifiers, cleaned].join(',') });
    setInputTicker('');
  }

  function addOrgCompany(e: React.FormEvent) {
    e.preventDefault();
    const numericId = Number(selectedOrgIdToAdd);
    if (!Number.isInteger(numericId) || numericId <= 0 || orgCompanyIds.includes(numericId)) return;
    if (orgCompanyIds.length >= MAX_COMPARE_COUNT) {
      setLimitNotice('Chỉ hỗ trợ so sánh tối đa 4 doanh nghiệp cùng lúc.');
      return;
    }
    setLimitNotice(null);
    updateSearch({ source: 'org', ids: [...orgCompanyIds, numericId].join(',') });
    setSelectedOrgIdToAdd('');
  }

  const orgCompanies = orgListQuery.data ?? [];
  const activeLoading = source === 'org' ? orgCompareQuery.isLoading : secCompareQuery.isLoading;
  const activeError = source === 'org' ? orgCompareQuery.error : secCompareQuery.error;

  const chartData =
    source === 'org'
      ? (orgCompareQuery.data?.companies ?? []).map((item) => ({
          name: item.company.ticker || item.company.name.slice(0, 18),
          health: item.health_score !== null ? Number(item.health_score.toFixed(1)) : 0,
          pd: item.pd_12m !== null ? Number((item.pd_12m * 100).toFixed(2)) : 0,
        }))
      : (secCompareQuery.data?.companies ?? []).map((item) => {
          const score = mapPdToSingleHealthScore(item.distress_probability);
          return {
            name: item.ticker ?? item.cik,
            health: score ?? 0,
            pd:
              typeof item.distress_probability === 'number'
                ? Number((item.distress_probability * 100).toFixed(2))
                : 0,
          };
        });

  return (
    <div className="space-y-5 animate-view">
      {/* Header & Source Switch */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-[-0.025em] text-[var(--text-primary)]">
            So sánh Trực diện Doanh nghiệp (2–4 DN)
          </h1>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Đặt song song Điểm Sức khỏe, Nguy cơ khủng hoảng 12 tháng, Altman Z-Score và các chỉ số
            tài chính cốt lõi.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Source Switcher */}
          <div
            className="inline-flex rounded-[6px] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-0.5 text-xs"
            role="group"
            aria-label="Chọn nguồn doanh nghiệp so sánh"
          >
            {user && activeOrg ? (
              <button
                type="button"
                onClick={() => switchSource('org')}
                className={cn(
                  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[4px] font-medium cursor-pointer',
                  source === 'org'
                    ? 'bg-[var(--accent-primary)] text-[var(--accent-ink)]'
                    : 'text-[var(--text-secondary)]',
                )}
              >
                <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
                DN Tổ chức (VND)
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => switchSource('sec')}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[4px] font-medium cursor-pointer',
                source === 'sec'
                  ? 'bg-[var(--accent-primary)] text-[var(--accent-ink)]'
                  : 'text-[var(--text-secondary)]',
              )}
            >
              <Globe className="h-3.5 w-3.5" aria-hidden="true" />
              Thị trường Mỹ (SEC — USD)
            </button>
          </div>

          {/* Period Policy + Common Fiscal Year */}
          <div className="inline-flex items-center gap-1.5 rounded-[6px] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-1 text-xs">
            <button
              type="button"
              onClick={() => updateSearch({ common_year: null })}
              className={cn(
                'px-2.5 py-1 rounded-[4px] cursor-pointer font-medium',
                !useCommonYear
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)]'
                  : 'text-[var(--text-secondary)]',
              )}
            >
              Năm mới nhất
            </button>
            <button
              type="button"
              onClick={() =>
                updateSearch({
                  common_year: String(commonYearValue ?? new Date().getFullYear() - 1),
                })
              }
              className={cn(
                'px-2.5 py-1 rounded-[4px] cursor-pointer font-medium',
                useCommonYear
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)]'
                  : 'text-[var(--text-secondary)]',
              )}
            >
              Cùng năm tài chính
            </button>
            {useCommonYear ? (
              <input
                type="number"
                min={2010}
                max={2035}
                value={commonYearValue ?? ''}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  if (Number.isInteger(val) && val >= 2010 && val <= 2035) {
                    updateSearch({ common_year: String(val) });
                  }
                }}
                aria-label="Chọn năm tài chính chung"
                className="w-20 h-7 px-2 rounded border border-[var(--border-strong)] bg-[var(--bg-canvas)] num text-xs"
              />
            ) : null}
          </div>
        </div>
      </div>

      {/* Selector Bar (2-4 companies enforced) */}
      <Panel className="p-4 space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {source === 'sec'
              ? secIdentifiers.map((ticker) => (
                  <span
                    key={ticker}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[6px] bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-xs font-mono font-semibold"
                  >
                    {ticker}
                    <button
                      type="button"
                      onClick={() => {
                        setLimitNotice(null);
                        updateSearch({
                          source: 'sec',
                          ids: secIdentifiers.filter((x) => x !== ticker).join(','),
                        });
                      }}
                      aria-label={`Bỏ ${ticker}`}
                      className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer bg-transparent border-0 p-0"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </span>
                ))
              : orgCompanyIds.map((cid) => {
                  const found = orgCompanies.find((c) => c.id === cid);
                  return (
                    <span
                      key={cid}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[6px] bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-xs font-medium"
                    >
                      {found ? found.name : `DN #${cid}`}
                      <button
                        type="button"
                        onClick={() => {
                          setLimitNotice(null);
                          updateSearch({
                            source: 'org',
                            ids: orgCompanyIds.filter((x) => x !== cid).join(','),
                          });
                        }}
                        aria-label={`Bỏ doanh nghiệp ${found?.name ?? cid}`}
                        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer bg-transparent border-0 p-0"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  );
                })}
          </div>

          {source === 'sec' ? (
            <form onSubmit={addSecTicker} className="flex items-center gap-2">
              <input
                type="text"
                value={inputTicker}
                onChange={(e) => setInputTicker(e.target.value)}
                placeholder="Thêm mã CK (VD: NVDA)"
                aria-label="Thêm mã chứng khoán SEC để so sánh"
                className="h-8 px-2.5 text-xs font-mono uppercase rounded-[6px] border border-[var(--border-strong)] bg-[var(--bg-canvas)] w-44"
              />
              <Button
                type="submit"
                variant="secondary"
                size="sm"
                disabled={secIdentifiers.length >= MAX_COMPARE_COUNT}
              >
                <Plus className="h-3.5 w-3.5" />
                Thêm ({secIdentifiers.length}/{MAX_COMPARE_COUNT})
              </Button>
            </form>
          ) : (
            <form onSubmit={addOrgCompany} className="flex items-center gap-2">
              <select
                value={selectedOrgIdToAdd}
                onChange={(e) => setSelectedOrgIdToAdd(e.target.value)}
                aria-label="Chọn doanh nghiệp tổ chức để so sánh"
                className="h-8 px-2.5 text-xs rounded-[6px] border border-[var(--border-strong)] bg-[var(--bg-canvas)] min-w-[220px]"
              >
                <option value="">Chọn doanh nghiệp tổ chức...</option>
                {orgCompanies
                  .filter((c) => !orgCompanyIds.includes(c.id))
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.tax_code ? `(${c.tax_code})` : ''}
                    </option>
                  ))}
              </select>
              <Button
                type="submit"
                variant="secondary"
                size="sm"
                disabled={orgCompanyIds.length >= MAX_COMPARE_COUNT || !selectedOrgIdToAdd}
              >
                <Plus className="h-3.5 w-3.5" />
                Thêm ({orgCompanyIds.length}/{MAX_COMPARE_COUNT})
              </Button>
            </form>
          )}
        </div>

        {limitNotice ? (
          <p className="text-xs text-[var(--risk-medium-fg)]" role="status">
            {limitNotice}
          </p>
        ) : null}
      </Panel>

      {/* Main Comparison Content */}
      {(source === 'sec' && secIdentifiers.length < 2) ||
      (source === 'org' && orgCompanyIds.length < 2) ? (
        <EmptyState
          title="Cần ít nhất 2 doanh nghiệp để so sánh"
          description="Hãy chọn từ 2 đến 4 doanh nghiệp ở thanh phía trên để đối chiếu trực tiếp."
        />
      ) : activeLoading ? (
        <Panel>
          <TableSkeleton rows={8} />
        </Panel>
      ) : activeError ? (
        <ErrorState
          title="Không thể tải dữ liệu so sánh"
          message={activeError instanceof Error ? activeError.message : 'Vui lòng thử lại.'}
        />
      ) : (
        <>
          {/* Bar Chart Comparison */}
          {chartData.length > 0 ? (
            <Panel>
              <PanelHeader
                title="Biểu đồ Đối chiếu Điểm Sức khỏe & Nguy cơ 12 tháng"
                description="Điểm Sức khỏe cao hơn và Nguy cơ 12 tháng thấp hơn thể hiện nền tảng tài chính an toàn hơn."
              />
              <div className="p-4 h-[270px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 4 }}>
                    <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                    <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-surface)',
                        borderColor: 'var(--border-strong)',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '12px' }} />
                    <Bar
                      dataKey="health"
                      name="Điểm Sức khỏe (0–100)"
                      fill="var(--accent-primary)"
                      radius={[4, 4, 0, 0]}
                      maxBarSize={44}
                    />
                    <Bar
                      dataKey="pd"
                      name="Nguy cơ 12 tháng (%)"
                      fill="#BE123C"
                      radius={[4, 4, 0, 0]}
                      maxBarSize={44}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          ) : null}

          {/* Side-by-Side Comparison Table */}
          {source === 'org' && orgCompareQuery.data ? (
            <Panel>
              <PanelHeader
                title="Bảng So sánh Doanh nghiệp Tổ chức"
                description={`Kỳ đối chiếu: ${orgCompareQuery.data.common_fiscal_year ? `FY${orgCompareQuery.data.common_fiscal_year}` : 'Năm đã chốt mới nhất'}`}
              />
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50 text-[var(--text-secondary)]">
                      <th className="py-3 px-4 font-semibold">Chỉ tiêu</th>
                      {orgCompareQuery.data.companies.map((col) => (
                        <th key={col.company.id} className="py-3 px-4 font-semibold text-right">
                          <Link
                            to={`/portfolio/${col.company.id}`}
                            className="text-[var(--accent-primary)] hover:underline no-underline"
                          >
                            {col.company.name}
                          </Link>
                          <div className="text-[10px] font-normal text-[var(--text-muted)] num">
                            FY{col.fiscal_year}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    <tr>
                      <td className="py-2.5 px-4 font-medium">Điểm Sức khỏe (0–100)</td>
                      {orgCompareQuery.data.companies.map((col) => (
                        <td key={col.company.id} className="py-2.5 px-4 text-right num font-bold">
                          {formatScore(col.health_score, 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 font-medium">Xếp hạng rủi ro</td>
                      {orgCompareQuery.data.companies.map((col) => {
                        const meta = col.risk_tier ? RISK_TIER_META[col.risk_tier] : null;
                        return (
                          <td key={col.company.id} className="py-2.5 px-4 text-right">
                            <span
                              className="inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold"
                              style={
                                meta
                                  ? { color: meta.fg, backgroundColor: meta.bg }
                                  : undefined
                              }
                            >
                              {col.risk_label_vi}
                            </span>
                          </td>
                        );
                      })}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 font-medium">Nguy cơ khủng hoảng 12 tháng</td>
                      {orgCompareQuery.data.companies.map((col) => (
                        <td key={col.company.id} className="py-2.5 px-4 text-right num">
                          {formatPct(col.pd_12m, 2)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 font-medium">Altman Z-Score</td>
                      {orgCompareQuery.data.companies.map((col) => (
                        <td key={col.company.id} className="py-2.5 px-4 text-right num">
                          {col.altman.applicable ? formatRatio(col.altman.score, 2) : 'Không áp dụng'}
                        </td>
                      ))}
                    </tr>
                    {(
                      [
                        ['roa', 'ROA', formatPct],
                        ['roe', 'ROE', formatPct],
                        ['debt_ratio', 'Tỷ lệ nợ / Tổng tài sản', formatPct],
                        ['current_ratio', 'Thanh toán ngắn hạn', formatRatio],
                        ['ocf_ratio', 'Dòng tiền HĐKD / Tổng nợ', formatPct],
                      ] as const
                    ).map(([key, label, fmt]) => (
                      <tr key={key}>
                        <td className="py-2.5 px-4 text-[var(--text-secondary)]">{label}</td>
                        {orgCompareQuery.data!.companies.map((col) => (
                          <td key={col.company.id} className="py-2.5 px-4 text-right num">
                            {fmt(col.core_metrics[key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          ) : null}

          {source === 'sec' && secCompareQuery.data ? (
            <Panel>
              <PanelHeader
                title="Bảng So sánh Thị trường Mỹ (SEC — USD)"
                description={`Kỳ đối chiếu: ${secCompareQuery.data.common_fiscal_year ? `FY${secCompareQuery.data.common_fiscal_year}` : 'Năm công bố mới nhất'}`}
              />
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50 text-[var(--text-secondary)]">
                      <th className="py-3 px-4 font-semibold">Chỉ tiêu</th>
                      {secCompareQuery.data.companies.map((col) => (
                        <th key={col.cik} className="py-3 px-4 font-semibold text-right">
                          <Link
                            to={`/us-market/${encodeURIComponent(col.ticker || col.cik)}`}
                            className="text-[var(--accent-primary)] hover:underline no-underline font-mono"
                          >
                            {col.ticker ?? col.cik}
                          </Link>
                          <div className="text-[10px] font-normal text-[var(--text-muted)] num">
                            FY{col.fiscal_year}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    <tr>
                      <td className="py-2.5 px-4 font-medium">Điểm Sức khỏe (0–100)</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="py-2.5 px-4 text-right num font-bold">
                          {formatScore(mapPdToSingleHealthScore(col.distress_probability), 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 font-medium">Nguy cơ khủng hoảng 12 tháng</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="py-2.5 px-4 text-right num">
                          {formatPct(col.distress_probability, 2)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 font-medium">Altman Z-Score</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="py-2.5 px-4 text-right num">
                          {formatRatio(col.altman_z_score, 2)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 text-[var(--text-secondary)]">ROA</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="py-2.5 px-4 text-right num">
                          {formatPct(col.roa, 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 text-[var(--text-secondary)]">ROE</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="py-2.5 px-4 text-right num">
                          {formatPct(col.roe, 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 text-[var(--text-secondary)]">Tỷ lệ nợ / Tổng TS</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="py-2.5 px-4 text-right num">
                          {formatPct(col.debt_ratio, 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2.5 px-4 text-[var(--text-secondary)]">Thanh toán hiện hành</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="py-2.5 px-4 text-right num">
                          {formatRatio(col.current_ratio, 2)}x
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </Panel>
          ) : null}

          {/* Legal Disclaimer */}
          <div className="surface-subtle px-4 py-3 flex items-start gap-2 text-[11px] text-[var(--text-muted)]">
            <Scale className="h-3.5 w-3.5 shrink-0 mt-0.5" aria-hidden="true" />
            <p>
              Kết quả so sánh và chấm điểm rủi ro là phân tích định lượng nội bộ dựa trên dữ liệu tài
              chính lịch sử, không phải dịch vụ xếp hạng tín nhiệm theo Nghị định 88/2014/NĐ-CP.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
