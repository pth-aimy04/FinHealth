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

const TOOLTIP_STYLE = {
  backgroundColor: 'var(--bg-surface)',
  border: '1px solid var(--border-strong)',
  borderRadius: '3px',
  fontSize: '12px',
  color: 'var(--text-primary)',
};

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
      <section className="surface p-10 text-center space-y-2">
        <CalendarRange className="mx-auto h-7 w-7 text-[var(--text-muted)]" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          Chưa có dữ liệu lịch sử đa kỳ
        </h3>
        <p className="text-[13px] text-[var(--text-secondary)] max-w-md mx-auto">
          Hãy bổ sung ít nhất 2 kỳ báo cáo tài chính đã chốt để theo dõi quỹ đạo Điểm Sức khỏe và xu hướng dòng tiền qua các năm.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      {/* Period & Accounting Standard Context Strip */}
      <section className="surface px-5 py-3 flex flex-wrap items-center justify-between gap-3 bg-[var(--bg-header)]">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-[var(--accent-primary)]" aria-hidden="true" />
          <span className="text-[13px] font-bold text-[var(--text-primary)]">
            Chuỗi lịch sử {sorted.length} kỳ tài chính (
            {sorted[0].fiscal_year} – {sorted[sorted.length - 1].fiscal_year})
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {sorted.map((pt) => (
            <span
              key={pt.statement_id}
              className="num text-[11px] font-semibold px-2 py-0.5 rounded-[2px] bg-[var(--bg-surface)] text-[var(--text-secondary)] border border-[var(--border-strong)]"
            >
              FY{pt.fiscal_year} · {formatStandardShortVi(pt.accounting_standard)}
            </span>
          ))}
        </div>
      </section>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <section className="surface overflow-hidden">
          <div className="px-5 py-3 bg-[var(--bg-header)] border-b border-[var(--border-subtle)]">
            <h3 className="text-[14px] font-bold text-[var(--text-primary)] m-0">
              Quỹ đạo Điểm Sức khỏe & Nguy cơ khủng hoảng
            </h3>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)] m-0">
              Theo dõi biến động Điểm Sức khỏe (0–100) song song với Tỷ lệ nguy cơ khủng hoảng 12 tháng (%).
            </p>
          </div>
          <div className="p-4 h-[290px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={trajectoryData}
                margin={{ top: 10, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="2 2" vertical={false} />
                <XAxis
                  dataKey="yearLabel"
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                />
                <YAxis
                  yAxisId="left"
                  domain={[0, 100]}
                  tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fill: 'var(--risk-critical-fg)', fontSize: 11 }}
                  tickFormatter={(v: number) => `${v}%`}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
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
                  fill="var(--chart-1)"
                  fillOpacity={0.88}
                  radius={[2, 2, 0, 0]}
                  maxBarSize={38}
                  isAnimationActive={false}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="pd_pct"
                  name="Nguy cơ 12 tháng"
                  stroke="var(--chart-4)"
                  strokeWidth={2.5}
                  dot={{ r: 3.5, fill: 'var(--chart-4)' }}
                  connectNulls
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="surface overflow-hidden">
          <div className="px-5 py-3 bg-[var(--bg-header)] border-b border-[var(--border-subtle)]">
            <h3 className="text-[14px] font-bold text-[var(--text-primary)] m-0">
              Doanh thu, Lợi nhuận, Dòng tiền & Tổng nợ ({scaleUnitLabel})
            </h3>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)] m-0">
              Đối chiếu quy mô doanh thu, chất lượng lợi nhuận bằng dòng tiền HĐKD và áp lực nợ phải trả.
            </p>
          </div>
          <div className="p-4 h-[290px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={trajectoryData}
                margin={{ top: 10, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="2 2" vertical={false} />
                <XAxis
                  dataKey="yearLabel"
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                />
                <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  formatter={(value: number, name: string) => [
                    `${formatScoreVi(value, 1)} ${scaleUnitLabel}`,
                    name,
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar
                  dataKey="revenues"
                  name="Doanh thu"
                  fill="var(--chart-1)"
                  fillOpacity={0.85}
                  radius={[2, 2, 0, 0]}
                  maxBarSize={26}
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="total_liabilities"
                  name="Tổng nợ phải trả"
                  fill="var(--chart-5)"
                  fillOpacity={0.55}
                  radius={[2, 2, 0, 0]}
                  maxBarSize={26}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="net_income"
                  name="Lợi nhuận sau thuế"
                  stroke="var(--chart-2)"
                  strokeWidth={2.2}
                  dot={{ r: 3.5 }}
                  connectNulls
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="operating_cash_flow"
                  name="Dòng tiền HĐKD (OCF)"
                  stroke="var(--chart-3)"
                  strokeWidth={2.2}
                  strokeDasharray="4 2"
                  dot={{ r: 3.5 }}
                  connectNulls
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {/* Multi-period Tabular Ledger Summary */}
      <section className="surface-ruled overflow-hidden">
        <div className="px-5 py-3 bg-[var(--bg-header)] border-b border-[var(--border-subtle)]">
          <h3 className="text-[14px] font-bold text-[var(--text-primary)] m-0">
            Bảng tổng hợp diễn biến theo từng năm tài chính
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="ledger-table">
            <thead>
              <tr>
                <th>Kỳ</th>
                <th>Chuẩn / Kiểm toán</th>
                <th className="text-right">Điểm Sức khỏe</th>
                <th className="text-right">Nguy cơ 12T</th>
                <th className="text-right">Doanh thu</th>
                <th className="text-right">LNST</th>
                <th className="text-right">OCF</th>
                <th className="text-right">Tỷ lệ nợ</th>
                <th className="text-right">Altman</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((pt) => {
                const tierMeta = pt.risk_tier ? RISK_TIER_STYLE[pt.risk_tier] : null;
                return (
                  <tr key={pt.statement_id}>
                    <td className="num font-bold text-[var(--text-primary)]">
                      FY{pt.fiscal_year}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      <div className="font-medium text-[var(--text-primary)]">
                        {formatStandardShortVi(pt.accounting_standard)}
                      </div>
                      <div className="text-[11px] text-[var(--text-muted)]">
                        {formatAuditStatusVi(pt.audit_status)}
                      </div>
                    </td>
                    <td className="text-right">
                      <span
                        className="num font-bold"
                        style={{ color: tierMeta?.fg ?? 'var(--text-primary)' }}
                      >
                        {formatScoreVi(pt.health_score, 1)}
                      </span>
                    </td>
                    <td className="text-right num text-[var(--text-primary)]">
                      {formatPctVi(pt.pd_12m, 2)}
                    </td>
                    <td className="text-right num text-[var(--text-primary)]">
                      {formatCompactCurrencyVi(pt.revenues, pt.currency)}
                    </td>
                    <td className="text-right num text-[var(--text-primary)]">
                      {formatCompactCurrencyVi(pt.net_income, pt.currency)}
                    </td>
                    <td className="text-right num text-[var(--text-primary)]">
                      {formatCompactCurrencyVi(pt.operating_cash_flow, pt.currency)}
                    </td>
                    <td className="text-right num text-[var(--text-secondary)]">
                      {formatPctVi(pt.debt_ratio, 1)}
                    </td>
                    <td className="text-right num text-[var(--text-secondary)]">
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
