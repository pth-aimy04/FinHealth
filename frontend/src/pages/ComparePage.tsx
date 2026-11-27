import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Building2, Globe2, Plus, Scale, X } from 'lucide-react';
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
  PageHeader,
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
  const { user, activeOrg, isLoading: authLoading, isOrgsLoading } = useAuth();

  const urlSource = searchParams.get('source');
  const waitingForOrgAuth = urlSource === 'org' && (authLoading || isOrgsLoading);
  const [source, setSource] = useState<'org' | 'sec'>(
    urlSource === 'org' && user ? 'org' : 'sec',
  );
  const [inputTicker, setInputTicker] = useState('');
  const [selectedOrgIdToAdd, setSelectedOrgIdToAdd] = useState('');
  const [limitNotice, setLimitNotice] = useState<string | null>(null);

  useEffect(() => {
    if (urlSource === 'org' && user && activeOrg) {
      setSource('org');
    } else if (urlSource === 'sec') {
      setSource('sec');
    } else if (urlSource === 'org' && !authLoading && !user) {
      setSource('sec');
    }
  }, [urlSource, user, activeOrg, authLoading]);

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
  const [commonYearDraft, setCommonYearDraft] = useState(
    commonYearValue !== null ? String(commonYearValue) : '',
  );

  useEffect(() => {
    setCommonYearDraft(commonYearValue !== null ? String(commonYearValue) : '');
  }, [commonYearValue]);

  const orgListQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'companies'],
    queryFn: () => api.getOrgCompanies(),
    enabled: Boolean(user && activeOrg && source === 'org'),
  });

  const secCompareQuery = useQuery({
    queryKey: ['compare', 'sec', secIdentifiers.join(','), commonYearValue ?? 'latest'],
    queryFn: () => api.compareCompanies(secIdentifiers, commonYearValue),
    enabled:
      !waitingForOrgAuth &&
      !(urlSource === 'org' && Boolean(user && activeOrg)) &&
      source === 'sec' &&
      secIdentifiers.length >= 2,
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
    enabled: !waitingForOrgAuth && source === 'org' && Boolean(user && activeOrg) && orgCompanyIds.length >= 2,
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
  const activeLoading =
    waitingForOrgAuth || (source === 'org' ? orgCompareQuery.isLoading : secCompareQuery.isLoading);
  const activeError =
    waitingForOrgAuth ? null : source === 'org' ? orgCompareQuery.error : secCompareQuery.error;

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
      <PageHeader
        title="So sánh Trực diện Doanh nghiệp (2–4 DN)"
        description="Đặt song song Điểm Sức khỏe, Nguy cơ khủng hoảng 12 tháng, Altman Z-Score và các chỉ số tài chính cốt lõi."
        actions={
          <>
            <div
              className="inline-flex rounded-[3px] border border-[var(--border-strong)] bg-[var(--bg-surface)] p-0.5 text-xs"
              role="group"
              aria-label="Chọn nguồn doanh nghiệp so sánh"
            >
              {user && activeOrg ? (
                <button
                  type="button"
                  onClick={() => switchSource('org')}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-3 py-1 rounded-[2px] font-semibold cursor-pointer border-0',
                    source === 'org'
                      ? 'bg-[var(--accent-primary)] text-[var(--accent-ink)]'
                      : 'bg-transparent text-[var(--text-secondary)]',
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
                  'inline-flex items-center gap-1.5 px-3 py-1 rounded-[2px] font-semibold cursor-pointer border-0',
                  source === 'sec'
                    ? 'bg-[var(--accent-primary)] text-[var(--accent-ink)]'
                    : 'bg-transparent text-[var(--text-secondary)]',
                )}
              >
                <Globe2 className="h-3.5 w-3.5" aria-hidden="true" />
                Thị trường Mỹ (SEC — USD)
              </button>
            </div>

            <div className="inline-flex items-center gap-1 rounded-[3px] border border-[var(--border-strong)] bg-[var(--bg-surface)] p-0.5 text-xs">
              <button
                type="button"
                onClick={() => updateSearch({ common_year: null })}
                className={cn(
                  'px-2.5 py-1 rounded-[2px] cursor-pointer font-semibold border-0',
                  !useCommonYear
                    ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)]'
                    : 'bg-transparent text-[var(--text-secondary)]',
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
                  'px-2.5 py-1 rounded-[2px] cursor-pointer font-semibold border-0',
                  useCommonYear
                    ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)]'
                    : 'bg-transparent text-[var(--text-secondary)]',
                )}
              >
                Cùng năm tài chính
              </button>
              {useCommonYear ? (
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={4}
                  value={commonYearDraft}
                  onChange={(e) => {
                    const digits = e.target.value.replace(/[^\d]/g, '').slice(0, 4);
                    setCommonYearDraft(digits);
                    const val = Number(digits);
                    if (digits.length === 4 && Number.isInteger(val) && val >= 2010 && val <= 2035) {
                      updateSearch({ common_year: String(val) });
                    }
                  }}
                  onBlur={() => {
                    const val = Number(commonYearDraft);
                    if (Number.isInteger(val) && val >= 2010 && val <= 2035) {
                      updateSearch({ common_year: String(val) });
                    } else if (commonYearValue !== null) {
                      setCommonYearDraft(String(commonYearValue));
                    }
                  }}
                  aria-label="Chọn năm tài chính chung"
                  className="field-control !w-16 !h-7 num"
                />
              ) : null}
            </div>
          </>
        }
      />

      {/* Peer Selection Ribbon */}
      <Panel className="px-4 py-3 bg-[var(--bg-header)] space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {source === 'sec'
              ? secIdentifiers.map((ticker) => (
                  <span
                    key={ticker}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] bg-[var(--bg-surface)] border border-[var(--border-strong)] text-xs font-mono font-bold text-[var(--accent-primary)]"
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
                      className="text-[var(--text-muted)] hover:text-[var(--risk-critical-fg)] cursor-pointer bg-transparent border-0 p-0"
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
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] bg-[var(--bg-surface)] border border-[var(--border-strong)] text-xs font-semibold text-[var(--text-primary)]"
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
                        className="text-[var(--text-muted)] hover:text-[var(--risk-critical-fg)] cursor-pointer bg-transparent border-0 p-0"
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
                className="field-control !h-8 !w-44 font-mono uppercase"
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
                className="field-control !h-8 !min-w-[230px]"
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
          <p className="text-xs font-semibold text-[var(--risk-medium-fg)] m-0" role="status">
            {limitNotice}
          </p>
        ) : null}
      </Panel>

      {/* Main Comparison Content */}
      {(source === 'sec' && secIdentifiers.length < 2) ||
      (source === 'org' && orgCompanyIds.length < 2) ? (
        <Panel>
          <EmptyState
            title="Cần ít nhất 2 doanh nghiệp để so sánh"
            description="Hãy chọn từ 2 đến 4 doanh nghiệp ở thanh phía trên để đối chiếu trực tiếp."
          />
        </Panel>
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
          {chartData.length > 0 ? (
            <Panel className="overflow-hidden">
              <PanelHeader
                title="Biểu đồ Đối chiếu Điểm Sức khỏe & Nguy cơ 12 tháng"
                description="Điểm Sức khỏe cao hơn và Nguy cơ 12 tháng thấp hơn thể hiện nền tảng tài chính an toàn hơn."
              />
              <div className="p-4 h-[270px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 4 }}>
                    <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="2 2" vertical={false} />
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-primary)', fontSize: 12, fontWeight: 600 }} />
                    <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border-strong)',
                        borderRadius: '3px',
                        fontSize: '12px',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '12px' }} />
                    <Bar
                      dataKey="health"
                      name="Điểm Sức khỏe (0–100)"
                      fill="var(--chart-1)"
                      radius={[2, 2, 0, 0]}
                      maxBarSize={42}
                      isAnimationActive={false}
                    />
                    <Bar
                      dataKey="pd"
                      name="Nguy cơ 12 tháng (%)"
                      fill="var(--chart-4)"
                      radius={[2, 2, 0, 0]}
                      maxBarSize={42}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          ) : null}

          {source === 'org' && orgCompareQuery.data ? (
            <Panel ruled className="overflow-hidden">
              <PanelHeader
                title="Bảng So sánh Doanh nghiệp Tổ chức"
                description={`Kỳ đối chiếu: ${orgCompareQuery.data.common_fiscal_year ? `FY${orgCompareQuery.data.common_fiscal_year}` : 'Năm đã chốt mới nhất'}`}
              />
              <div className="overflow-x-auto">
                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Chỉ tiêu</th>
                      {orgCompareQuery.data.companies.map((col) => (
                        <th key={col.company.id} className="text-right">
                          <Link
                            to={`/portfolio/${col.company.id}`}
                            className="text-[var(--accent-primary)] hover:underline no-underline normal-case text-[13px] font-bold"
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
                  <tbody>
                    <tr className="bg-[var(--bg-header)]/50">
                      <td className="font-bold">Điểm Sức khỏe (0–100)</td>
                      {orgCompareQuery.data.companies.map((col) => (
                        <td key={col.company.id} className="text-right num font-bold text-[14px]">
                          {formatScore(col.health_score, 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="font-semibold">Xếp hạng rủi ro</td>
                      {orgCompareQuery.data.companies.map((col) => {
                        const meta = col.risk_tier ? RISK_TIER_META[col.risk_tier] : null;
                        return (
                          <td key={col.company.id} className="text-right">
                            <span
                              className="inline-block px-2 py-0.5 rounded-[2px] border text-[11px] font-semibold"
                              style={
                                meta
                                  ? {
                                      color: meta.fg,
                                      backgroundColor: meta.bg,
                                      borderColor: 'currentColor',
                                    }
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
                      <td className="font-semibold">Nguy cơ khủng hoảng 12 tháng</td>
                      {orgCompareQuery.data.companies.map((col) => (
                        <td key={col.company.id} className="text-right num font-semibold">
                          {formatPct(col.pd_12m, 2)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="font-semibold">Altman Z-Score</td>
                      {orgCompareQuery.data.companies.map((col) => (
                        <td key={col.company.id} className="text-right num">
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
                        <td className="text-[var(--text-secondary)]">{label}</td>
                        {orgCompareQuery.data!.companies.map((col) => (
                          <td key={col.company.id} className="text-right num">
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
            <Panel ruled className="overflow-hidden">
              <PanelHeader
                title="Bảng So sánh Thị trường Mỹ (SEC — USD)"
                description={`Kỳ đối chiếu: ${secCompareQuery.data.common_fiscal_year ? `FY${secCompareQuery.data.common_fiscal_year}` : 'Năm công bố mới nhất'}`}
              />
              <div className="overflow-x-auto">
                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Chỉ tiêu</th>
                      {secCompareQuery.data.companies.map((col) => (
                        <th key={col.cik} className="text-right">
                          <Link
                            to={`/us-market/${encodeURIComponent(col.ticker || col.cik)}`}
                            className="text-[var(--accent-primary)] hover:underline no-underline font-mono text-[13px] font-bold"
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
                  <tbody>
                    <tr className="bg-[var(--bg-header)]/50">
                      <td className="font-bold">Điểm Sức khỏe (0–100)</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="text-right num font-bold text-[14px]">
                          {formatScore(mapPdToSingleHealthScore(col.distress_probability), 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="font-semibold">Nguy cơ khủng hoảng 12 tháng</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="text-right num font-semibold">
                          {formatPct(col.distress_probability, 2)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="font-semibold">Altman Z-Score</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="text-right num">
                          {formatRatio(col.altman_z_score, 2)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="text-[var(--text-secondary)]">ROA</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="text-right num">
                          {formatPct(col.roa, 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="text-[var(--text-secondary)]">ROE</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="text-right num">
                          {formatPct(col.roe, 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="text-[var(--text-secondary)]">Tỷ lệ nợ / Tổng TS</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="text-right num">
                          {formatPct(col.debt_ratio, 1)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="text-[var(--text-secondary)]">Thanh toán hiện hành</td>
                      {secCompareQuery.data.companies.map((col) => (
                        <td key={col.cik} className="text-right num">
                          {formatRatio(col.current_ratio, 2)}x
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </Panel>
          ) : null}

          <div className="px-4 py-3 rounded-[3px] border border-[var(--border-subtle)] bg-[var(--bg-header)] flex items-start gap-2 text-[11px] text-[var(--text-muted)]">
            <Scale className="h-3.5 w-3.5 shrink-0 mt-0.5 text-[var(--text-secondary)]" aria-hidden="true" />
            <p className="m-0">
              Kết quả so sánh và chấm điểm rủi ro là phân tích định lượng nội bộ dựa trên dữ liệu tài
              chính lịch sử, không phải dịch vụ xếp hạng tín nhiệm theo Nghị định 88/2014/NĐ-CP.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
