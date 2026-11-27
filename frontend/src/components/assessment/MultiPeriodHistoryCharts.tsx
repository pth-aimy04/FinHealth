import { useMemo } from 'react';
import { CalendarRange, TrendingUp } from 'lucide-react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  RISK_TIER_STYLE,
  formatAuditStatusVi,
  formatCompactCurrencyVi,
  formatPctVi,
  formatScoreVi,
  formatStandardShortVi,
  type MultiPeriodHistoryPointView,
} from './types';

export interface MultiPeriodHistoryChartsProps {
  history: MultiPeriodHistoryPointView[];
  currency?: string;
}

export function MultiPeriodHistoryCharts({
  history,
  currency,
}: MultiPeriodHistoryChartsProps) {
  const sorted = useMemo(
    () => [...history].sort((a, b) => a.fiscal_year - b.fiscal_year),
    [history],
  );

  const effectiveCurrency = currency ?? sorted[sorted.length - 1]?.currency ?? 'VND';
  const scaleDivisor = effectiveCurrency.toUpperCase() === 'VND' ? 1e9 : 1e6;
  const scaleUnitLabel =
    effectiveCurrency.toUpperCase() === 'VND' ? 'Tỷ VND' : 'Triệu USD';

  const trajectoryData = useMemo(
    () =>
      sorted.map((pt) => ({
        yearLabel: `FY${pt.fiscal_year}`,
        standard: formatStandardShortVi(pt.accounting_standard),
        health_score:
          pt.health_score !== null && Number.isFinite(pt.health_score)
            ? Number(pt.health_score.toFixed(1))
            : null,
        pd_pct:
          pt.pd_12m !== null && Number.isFinite(pt.pd_12m)
            ? Number((pt.pd_12m * 100).toFixed(2))
            : null,
        revenues:
          pt.revenues !== null && Number.isFinite(pt.revenues)
            ? Number((pt.revenues / scaleDivisor).toFixed(2))
            : null,
        net_income:
          pt.net_income !== null && Number.isFinite(pt.net_income)
            ? Number((pt.net_income / scaleDivisor).toFixed(2))
            : null,
        operating_cash_flow:
          pt.operating_cash_flow !== null && Number.isFinite(pt.operating_cash_flow)
            ? Number((pt.operating_cash_flow / scaleDivisor).toFixed(2))
            : null,
        total_liabilities:
          pt.total_liabilities !== null && Number.isFinite(pt.total_liabilities)
            ? Number((pt.total_liabilities / scaleDivisor).toFixed(2))
            : null,
      })),
    [sorted, scaleDivisor],
  );

  if (sorted.length === 0) {
    return (
      <section className="surface p-8 text-center space-y-2">
        <CalendarRange className="mx-auto h-7 w-7 text-[var(--text-muted)]" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          Chưa có dữ liệu lịch sử đa kỳ
        </h3>
        <p className="text-xs text-[var(--text-secondary)] max-w-md mx-auto">
          Hãy bổ sung ít nhất 2 kỳ báo cáo tài chính đã chốt để theo dõi quỹ đạo Điểm Sức khỏe và xu hướng dòng tiền qua các năm.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      {/* Period & Accounting Standard Bridge Strip */}
      <section className="surface p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-[var(--accent-primary)]" aria-hidden="true" />
          <span className="text-xs font-semibold text-[var(--text-primary)]">
            Chuỗi lịch sử {sorted.length} kỳ tài chính (
            {sorted[0].fiscal_year} – {sorted[sorted.length - 1].fiscal_year})
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {sorted.map((pt) => (
            <span
              key={pt.statement_id}
              className="num text-[11px] px-2 py-0.5 rounded bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]"
            >
              FY{pt.fiscal_year} · {formatStandardShortVi(pt.accounting_standard)}
            </span>
          ))}
        </div>
      </section>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {/* Chart 1: Health Score 0-100 & PD 12m Trajectory */}
        <section className="surface overflow-hidden">
          <div className="px-5 py-3.5 border-b border-[var(--border-subtle)]">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              Quỹ đạo Điểm Sức khỏe & Nguy cơ khủng hoảng
            </h3>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              Theo dõi biến động Điểm Sức khỏe (0–100) song song với Tỷ lệ nguy cơ khủng hoảng 12 tháng (%).
            </p>
          </div>
          <div className="p-4 h-[290px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={trajectoryData}
                margin={{ top: 10, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="yearLabel"
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                />
                <YAxis
                  yAxisId="left"
                  domain={[0, 100]}
                  tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                  label={{
                    value: 'Điểm (0–100)',
                    angle: -90,
                    position: 'insideLeft',
                    style: { fill: 'var(--text-muted)', fontSize: 11 },
                  }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fill: 'var(--risk-critical-fg)', fontSize: 11 }}
                  tickFormatter={(v: number) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--bg-surface)',
                    borderColor: 'var(--border-strong)',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: 'var(--text-primary)',
                  }}
                  formatter={(value: number, name: string) =>
                    name === 'Nguy cơ 12 tháng'
                      ? [`${formatScoreVi(value, 2)}%`, name]
                      : [`${formatScoreVi(value, 1)} / 100`, name]
                  }
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar
                  yAxisId="left"
                  dataKey="health_score"
                  name="Điểm Sức khỏe"
                  fill="var(--accent-primary)"
                  fillOpacity={0.82}
                  radius={[5, 5, 0, 0]}
                  maxBarSize={42}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="pd_pct"
                  name="Nguy cơ 12 tháng"
                  stroke="#BE123C"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#BE123C' }}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Chart 2: Revenue, Net Income, OCF & Total Liabilities */}
        <section className="surface overflow-hidden">
          <div className="px-5 py-3.5 border-b border-[var(--border-subtle)]">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              Doanh thu, Lợi nhuận, Dòng tiền & Tổng nợ ({scaleUnitLabel})
            </h3>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              Đối chiếu quy mô doanh thu, chất lượng lợi nhuận bằng dòng tiền HĐKD và áp lực nợ phải trả.
            </p>
          </div>
          <div className="p-4 h-[290px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={trajectoryData}
                margin={{ top: 10, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="yearLabel"
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                />
                <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--bg-surface)',
                    borderColor: 'var(--border-strong)',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: 'var(--text-primary)',
                  }}
                  formatter={(value: number, name: string) => [
                    `${formatScoreVi(value, 1)} ${scaleUnitLabel}`,
                    name,
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar
                  dataKey="revenues"
                  name="Doanh thu"
                  fill="#0A6B5C"
                  fillOpacity={0.78}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                />
                <Bar
                  dataKey="total_liabilities"
                  name="Tổng nợ phải trả"
                  fill="#64748B"
                  fillOpacity={0.55}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                />
                <Line
                  type="monotone"
                  dataKey="net_income"
                  name="Lợi nhuận sau thuế"
                  stroke="#2563EB"
                  strokeWidth={2.2}
                  dot={{ r: 3.5 }}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="operating_cash_flow"
                  name="Dòng tiền HĐKD (OCF)"
                  stroke="#D97706"
                  strokeWidth={2.2}
                  strokeDasharray="4 2"
                  dot={{ r: 3.5 }}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {/* Multi-period Tabular Summary */}
      <section className="surface overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border-subtle)]">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Bảng tổng hợp diễn biến theo từng năm tài chính
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50 text-[var(--text-secondary)]">
                <th className="py-2.5 px-4 font-semibold">Kỳ</th>
                <th className="py-2.5 px-3 font-semibold">Chuẩn / Kiểm toán</th>
                <th className="py-2.5 px-3 font-semibold text-right">Điểm Sức khỏe</th>
                <th className="py-2.5 px-3 font-semibold text-right">Nguy cơ 12T</th>
                <th className="py-2.5 px-3 font-semibold text-right">Doanh thu</th>
                <th className="py-2.5 px-3 font-semibold text-right">LNST</th>
                <th className="py-2.5 px-3 font-semibold text-right">OCF</th>
                <th className="py-2.5 px-3 font-semibold text-right">Tỷ lệ nợ</th>
                <th className="py-2.5 px-4 font-semibold text-right">Altman</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {sorted.map((pt) => {
                const tierMeta = pt.risk_tier ? RISK_TIER_STYLE[pt.risk_tier] : null;
                return (
                  <tr
                    key={pt.statement_id}
                    className="hover:bg-[var(--bg-hover)]/40 transition-colors"
                  >
                    <td className="py-2.5 px-4 num font-semibold text-[var(--text-primary)]">
                      FY{pt.fiscal_year}
                    </td>
                    <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                      <div>{formatStandardShortVi(pt.accounting_standard)}</div>
                      <div className="text-[11px] text-[var(--text-muted)]">
                        {formatAuditStatusVi(pt.audit_status)}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <span
                        className="num font-semibold"
                        style={{ color: tierMeta?.fg ?? 'var(--text-primary)' }}
                      >
                        {formatScoreVi(pt.health_score, 1)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right num text-[var(--text-primary)]">
                      {formatPctVi(pt.pd_12m, 2)}
                    </td>
                    <td className="py-2.5 px-3 text-right num text-[var(--text-primary)]">
                      {formatCompactCurrencyVi(pt.revenues, pt.currency)}
                    </td>
                    <td className="py-2.5 px-3 text-right num text-[var(--text-primary)]">
                      {formatCompactCurrencyVi(pt.net_income, pt.currency)}
                    </td>
                    <td className="py-2.5 px-3 text-right num text-[var(--text-primary)]">
                      {formatCompactCurrencyVi(pt.operating_cash_flow, pt.currency)}
                    </td>
                    <td className="py-2.5 px-3 text-right num text-[var(--text-secondary)]">
                      {formatPctVi(pt.debt_ratio, 1)}
                    </td>
                    <td className="py-2.5 px-4 text-right num text-[var(--text-secondary)]">
                      {pt.altman_z_score !== null
                        ? `${formatScoreVi(pt.altman_z_score, 2)}${pt.altman_variant ? ` (${pt.altman_variant})` : ''}`
                        : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
