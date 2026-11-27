import { useEffect, useState } from 'react';
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
  MetricStrip,
  MetricTile,
  PageHeader,
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
  const paramIdentifier = searchParams.get('id') ?? searchParams.get('ticker') ?? 'AAPL';
  const [identifier, setIdentifier] = useState(paramIdentifier);
  const [scenario, setScenario] = useState<StressScenarioRequest>(PRESETS[0].scenario);

  useEffect(() => {
    if (paramIdentifier && paramIdentifier !== identifier) {
      setIdentifier(paramIdentifier);
    }
  }, [paramIdentifier, identifier]);

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
    <div className="space-y-5 animate-view">
      <PageHeader
        title="Mô phỏng Sức chịu đựng (What-If Stress Test)"
        description="Giả lập cú sốc doanh thu, biên lợi nhuận, nợ vay và dòng tiền hoạt động để kiểm tra độ nhạy rủi ro mà không làm thay đổi dữ liệu gốc."
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        <Panel ruled className="lg:col-span-4 overflow-hidden">
          <PanelHeader
            title="Tham số Kịch bản Giả lập"
            description="Chọn doanh nghiệp và thiết lập mức cú sốc giới hạn."
          />
          <div className="p-4 space-y-4 text-xs">
            <div>
              <label htmlFor="stress-issuer" className="block font-semibold text-[var(--text-secondary)] mb-1">
                Doanh nghiệp (Mã CK hoặc CIK)
              </label>
              <select
                id="stress-issuer"
                value={identifier}
                onChange={(e) => {
                  setIdentifier(e.target.value);
                  setSearchParams({ id: e.target.value }, { replace: true });
                }}
                className="field-control"
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
                  className="px-2.5 py-1 text-[11px] font-semibold rounded-[2px] border border-[var(--border-strong)] bg-[var(--bg-header)] hover:bg-[var(--accent-soft)] hover:text-[var(--accent-primary)] hover:border-[var(--accent-primary)] text-[var(--text-secondary)] cursor-pointer transition-colors"
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <div className="space-y-3.5 pt-2 border-t border-[var(--border-subtle)]">
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
                      <label htmlFor={slider.key} className="font-semibold text-[var(--text-primary)]">
                        {slider.label}
                      </label>
                      <span className="num font-bold text-[var(--accent-primary)]">
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

            <div className="flex items-center gap-2 pt-3 border-t border-[var(--border-subtle)]">
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

        <div className="lg:col-span-8 min-w-0 space-y-5">
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
                  className="px-4 py-3 rounded-[3px] border border-[var(--risk-medium-border)] bg-[var(--risk-medium-bg)] flex items-start gap-3"
                >
                  <AlertTriangle
                    className="h-4 w-4 shrink-0 mt-0.5 text-[var(--risk-medium-fg)]"
                    aria-hidden="true"
                  />
                  <div className="text-xs">
                    <div className="font-bold text-[var(--risk-medium-fg)]">
                      Cảnh báo Kịch bản Ngoài phân phối huấn luyện (OOD)
                    </div>
                    <p className="mt-0.5 text-[var(--text-primary)] m-0">
                      Các chỉ số sau cú sốc vượt ngoài vùng dữ liệu huấn luyện đối với:{' '}
                      <span className="font-semibold">
                        {result.ood_features.map(humanizeFeature).join(', ')}
                      </span>
                      .
                    </p>
                  </div>
                </div>
              ) : null}

              <MetricStrip columns={3}>
                <MetricTile
                  bare
                  label="XS Kiệt quệ Cơ sở"
                  value={formatPct(result.baseline.prediction.distress_probability)}
                  meta={`Mức rủi ro: ${result.baseline.prediction.risk_level ?? '—'}`}
                />
                <MetricTile
                  bare
                  label="XS Kiệt quệ Sau cú sốc"
                  value={formatPct(result.stressed.prediction.distress_probability)}
                  meta={`Biến động: ${formatSigned(result.probability_delta * 100, 2)} đ%`}
                  accent={
                    result.probability_delta > 0.05
                      ? 'critical'
                      : result.probability_delta < -0.02
                        ? 'low'
                        : 'medium'
                  }
                />
                <MetricTile
                  bare
                  label="Biến động Altman Z"
                  value={formatSigned(result.altman_z_delta, 2)}
                  meta={result.cluster_shift ? 'Đã dịch chuyển cụm PCA' : 'Giữ nguyên cụm PCA'}
                />
              </MetricStrip>

              <Panel className="overflow-hidden">
                <PanelHeader
                  title="Các Yếu tố Tài chính Dịch chuyển Mạnh nhất (Sau cú sốc − Cơ sở)"
                  description="Mức biến động tác động của từng chỉ tiêu tài chính lên rủi ro do kịch bản cú sốc gây ra."
                  actions={<RiskBadge level={result.stressed.prediction.risk_level} />}
                />
                <div className="p-4 h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={shiftData}
                      layout="vertical"
                      margin={{ top: 4, right: 20, left: 16, bottom: 4 }}
                    >
                      <CartesianGrid strokeDasharray="2 2" stroke="var(--border-subtle)" horizontal={false} />
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
                        formatter={(v: unknown) => [formatSigned(Number(v), 4), 'Mức dịch chuyển tác động']}
                        contentStyle={{
                          backgroundColor: 'var(--bg-surface)',
                          border: '1px solid var(--border-strong)',
                          borderRadius: '3px',
                          fontSize: '12px',
                        }}
                      />
                      <Bar dataKey="delta" radius={[2, 2, 2, 2]} maxBarSize={16} isAnimationActive={false}>
                        {shiftData.map((entry) => (
                          <Cell
                            key={entry.feature}
                            fill={entry.delta >= 0 ? 'var(--chart-4)' : 'var(--chart-2)'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Panel>

              <Panel className="overflow-hidden">
                <PanelHeader
                  title="So sánh Tỷ số Tài chính Cốt lõi: Cơ sở vs Sau cú sốc"
                  description="Tác động trực tiếp của kịch bản lên khả năng sinh lời, đòn bẩy và dòng tiền."
                />
                <div className="p-4">
                  <StressComparisonChart result={result} />
                </div>
              </Panel>

              <Panel className="overflow-hidden">
                <PanelHeader title="Giả định của Kịch bản Mô phỏng" />
                <ul className="p-4 list-disc pl-8 space-y-1 text-[13px] text-[var(--text-secondary)] m-0">
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
