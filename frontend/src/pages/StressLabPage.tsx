import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertTriangle, Play, RotateCcw } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import { formatPct, formatSigned, humanizeFeature } from '@/lib/format';
import type { StressScenarioRequest } from '@/types/api';
import {
  Button,
  EmptyState,
  ErrorState,
  MetricTile,
  Panel,
  PanelHeader,
  RiskBadge,
} from '@/components/ui/Primitives';
import { StressComparisonChart } from '@/components/charts/CompareStressCharts';

const NEUTRAL: StressScenarioRequest = {
  revenue_shock_pct: 0,
  operating_margin_delta_pct: 0,
  debt_change_pct: 0,
  ocf_shock_pct: 0,
};

const PRESETS: Array<{ label: string; scenario: StressScenarioRequest }> = [
  {
    label: 'Cú sốc Suy thoái',
    scenario: {
      revenue_shock_pct: -0.25,
      operating_margin_delta_pct: -0.08,
      debt_change_pct: 0.2,
      ocf_shock_pct: -0.35,
    },
  },
  {
    label: 'Tăng vọt Đòn bẩy Nợ',
    scenario: {
      revenue_shock_pct: -0.05,
      operating_margin_delta_pct: -0.03,
      debt_change_pct: 0.5,
      ocf_shock_pct: -0.2,
    },
  },
  {
    label: 'Phục hồi & Giảm nợ',
    scenario: {
      revenue_shock_pct: 0.15,
      operating_margin_delta_pct: 0.04,
      debt_change_pct: -0.25,
      ocf_shock_pct: 0.25,
    },
  },
];

export function StressLabPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [identifier, setIdentifier] = useState(searchParams.get('id') ?? 'AAPL');
  const [scenario, setScenario] = useState<StressScenarioRequest>(PRESETS[0].scenario);

  const companiesQuery = useQuery({
    queryKey: ['companies', { limit: 150 }],
    queryFn: () => api.getCompanies({ limit: 150 }),
    staleTime: 120_000,
  });

  const simMutation = useMutation({
    mutationFn: () => api.simulateStress(identifier, scenario),
  });

  const result = simMutation.data;

  const shiftData = (result?.top_shifted_shap_drivers ?? []).map((item) => ({
    feature: humanizeFeature(item.feature),
    delta: item.delta,
  }));

  function updateSlider(key: keyof StressScenarioRequest, pctValue: number) {
    setScenario((prev) => ({ ...prev, [key]: pctValue / 100 }));
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[1.375rem] font-semibold tracking-[-0.02em]">
          Mô phỏng Sức chịu đựng (What-If Stress Test)
        </h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          Giả lập cú sốc doanh thu, biên lợi nhuận, nợ vay và dòng tiền hoạt động để kiểm tra độ
          nhạy rủi ro và dịch chuyển TreeSHAP mà không làm thay đổi dữ liệu gốc.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Panel className="lg:col-span-4">
          <PanelHeader
            title="Tham số Kịch bản Giả lập"
            description="Chọn doanh nghiệp và thiết lập mức cú sốc giới hạn."
          />
          <div className="p-4 space-y-4">
            <div>
              <label htmlFor="stress-issuer" className="block text-xs font-medium mb-1">
                Doanh nghiệp (Mã CK hoặc CIK)
              </label>
              <select
                id="stress-issuer"
                value={identifier}
                onChange={(e) => {
                  setIdentifier(e.target.value);
                  setSearchParams({ id: e.target.value }, { replace: true });
                }}
                className="w-full h-9 px-2.5 text-xs bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
              >
                {(companiesQuery.data ?? []).map((c) => {
                  const val = c.ticker || c.cik;
                  return (
                    <option key={c.cik} value={val}>
                      {val} — {c.name}
                    </option>
                  );
                })}
                {!companiesQuery.data ? <option value={identifier}>{identifier}</option> : null}
              </select>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => setScenario(preset.scenario)}
                  className="px-2 py-1 text-[11px] rounded-[4px] border border-[var(--border-subtle)] bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] cursor-pointer"
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <div className="space-y-3.5 text-xs">
              {(
                [
                  { key: 'revenue_shock_pct', label: 'Biến động Doanh thu', min: -50, max: 50 },
                  { key: 'operating_margin_delta_pct', label: 'Thay đổi Biên hoạt động', min: -30, max: 30 },
                  { key: 'debt_change_pct', label: 'Thay đổi Tổng nợ vay', min: -50, max: 100 },
                  { key: 'ocf_shock_pct', label: 'Biến động Dòng tiền (OCF)', min: -80, max: 80 },
                ] as const
              ).map((slider) => {
                const pct = Math.round(scenario[slider.key] * 100);
                return (
                  <div key={slider.key} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label htmlFor={slider.key} className="font-medium text-[var(--text-primary)]">
                        {slider.label}
                      </label>
                      <span className="num font-semibold text-[var(--accent-primary)]">
                        {pct > 0 ? `+${pct}%` : `${pct}%`}
                      </span>
                    </div>
                    <input
                      id={slider.key}
                      type="range"
                      min={slider.min}
                      max={slider.max}
                      step={1}
                      value={pct}
                      onChange={(e) => updateSlider(slider.key, Number(e.target.value))}
                      className="w-full accent-[var(--accent-primary)] cursor-pointer"
                    />
                  </div>
                );
              })}
            </div>

            <div className="flex items-center gap-2 pt-2">
              <Button
                variant="primary"
                className="flex-1"
                disabled={simMutation.isPending}
                onClick={() => simMutation.mutate()}
              >
                <Play className="h-3.5 w-3.5" aria-hidden="true" />
                {simMutation.isPending ? 'Đang mô phỏng...' : 'Chạy mô phỏng'}
              </Button>
              <Button
                variant="secondary"
                onClick={() => setScenario(NEUTRAL)}
                aria-label="Đặt lại các cú sốc về 0%"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </Panel>

        <div className="lg:col-span-8 space-y-4">
          {simMutation.isError ? (
            <ErrorState
              title="Mô phỏng thất bại"
              message={
                simMutation.error instanceof Error
                  ? simMutation.error.message
                  : 'Không thể chạy kịch bản stress test.'
              }
              onRetry={() => simMutation.mutate()}
            />
          ) : !result ? (
            <Panel>
              <EmptyState
                title="Sẵn sàng mô phỏng"
                description="Chọn doanh nghiệp và mức cú sốc bên trái, sau đó bấm Chạy mô phỏng để so sánh xác suất kiệt quệ trước và sau cú sốc."
                action={
                  <Button variant="primary" size="sm" onClick={() => simMutation.mutate()}>
                    Chạy Kịch bản Suy thoái mặc định
                  </Button>
                }
              />
            </Panel>
          ) : (
            <>
              {result.is_ood_scenario ? (
                <div
                  role="alert"
                  className="surface px-4 py-3 flex items-start gap-3 border-[var(--risk-medium-fg)]/40 bg-[var(--risk-medium-bg)]"
                >
                  <AlertTriangle
                    className="h-4 w-4 shrink-0 mt-0.5 text-[var(--risk-medium-fg)]"
                    aria-hidden="true"
                  />
                  <div className="text-xs">
                    <div className="font-semibold text-[var(--risk-medium-fg)]">
                      Cảnh báo Kịch bản Ngoài phân phối huấn luyện (OOD)
                    </div>
                    <p className="mt-0.5 text-[var(--text-primary)]">
                      Các chỉ số sau cú sốc vượt ngoài vùng dữ liệu huấn luyện đối với:{' '}
                      <span className="font-mono">{result.ood_features.join(', ')}</span>.
                    </p>
                  </div>
                </div>
              ) : null}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <MetricTile
                  label="XS Kiệt quệ Cơ sở"
                  value={formatPct(result.baseline.prediction.distress_probability)}
                  meta={`Mức rủi ro: ${result.baseline.prediction.risk_level ?? '—'}`}
                />
                <MetricTile
                  label="XS Kiệt quệ Sau cú sốc"
                  value={formatPct(result.stressed.prediction.distress_probability)}
                  meta={`Biến động: ${formatSigned(result.probability_delta * 100, 2)} đ%`}
                  accent={result.probability_delta > 0.05 ? 'critical' : result.probability_delta < -0.02 ? 'low' : 'medium'}
                />
                <MetricTile
                  label="Biến động Altman Z"
                  value={formatSigned(result.altman_z_delta, 2)}
                  meta={result.cluster_shift ? 'Đã dịch chuyển cụm PCA' : 'Giữ nguyên cụm PCA'}
                />
              </div>

              <Panel>
                <PanelHeader
                  title="Các yếu tố TreeSHAP Dịch chuyển Mạnh nhất (Sau cú sốc − Cơ sở)"
                  description="Mức dịch chuyển biên XGBoost thô (log-odds) do kịch bản cú sốc gây ra."
                  actions={<RiskBadge level={result.stressed.prediction.risk_level} />}
                />
                <div className="p-4 h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={shiftData}
                      layout="vertical"
                      margin={{ top: 4, right: 20, left: 16, bottom: 4 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
                      <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                      <YAxis
                        type="category"
                        dataKey="feature"
                        width={185}
                        tick={{ fill: 'var(--text-primary)', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <ReferenceLine x={0} stroke="var(--border-strong)" />
                      <Tooltip
                        formatter={(v: unknown) => [formatSigned(Number(v), 4), 'Biến động SHAP']}
                        contentStyle={{
                          backgroundColor: 'var(--bg-surface)',
                          border: '1px solid var(--border-strong)',
                          borderRadius: '4px',
                          fontSize: '12px',
                        }}
                      />
                      <Bar dataKey="delta" radius={[2, 2, 2, 2]} maxBarSize={18}>
                        {shiftData.map((entry) => (
                          <Cell
                            key={entry.feature}
                            fill={entry.delta >= 0 ? '#DC2626' : '#0F766E'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Panel>

              <Panel>
                <PanelHeader
                  title="So sánh Tỷ số Tài chính Cốt lõi: Cơ sở vs Sau cú sốc"
                  description="Tác động trực tiếp của kịch bản lên khả năng sinh lời, đòn bẩy và dòng tiền."
                />
                <div className="p-4">
                  <StressComparisonChart result={result} />
                </div>
              </Panel>

              <Panel>
                <PanelHeader title="Giả định của Kịch bản Mô phỏng" />
                <ul className="p-4 list-disc pl-8 space-y-1 text-xs text-[var(--text-secondary)]">
                  {result.assumptions.map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              </Panel>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
