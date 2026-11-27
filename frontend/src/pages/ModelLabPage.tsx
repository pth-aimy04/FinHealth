import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { BookmarkPlus, Cpu, Play } from 'lucide-react';
import { api } from '@/lib/api';
import { formatDate, formatPct, formatRatio, formatScore, formatSigned, humanizeFeature } from '@/lib/format';
import type { ManualStatementInput } from '@/types/api';
import { useAuth } from '@/context/AuthContext';
import {
  Button,
  EmptyState,
  ErrorState,
  MetricTile,
  Panel,
  PanelHeader,
  RiskBadge,
  TableSkeleton,
  cn,
} from '@/components/ui/Primitives';
import { ModelBenchmarkChart } from '@/components/charts/CompareStressCharts';

const PUBLICATION_FIGURES = [
  { file: '03_roc_pr_curves_comparison.png', title: 'Đường cong ROC & Precision-Recall' },
  { file: '06_shap_global_importance.png', title: 'Mức độ quan trọng đặc trưng TreeSHAP toàn cục' },
  { file: '07_reliability_calibration.png', title: 'Độ tin cậy hiệu chuẩn xác suất' },
  { file: '02_pca_scree_and_clusters.png', title: 'Biểu đồ PCA Scree & Phân cụm ngang hàng' },
  { file: '04_confusion_matrices.png', title: 'Ma trận nhầm lẫn kiểm định Out-of-Time' },
  { file: '05_forecasting_actual_vs_predicted.png', title: 'Dự báo chỉ số: Thực tế vs Dự đoán' },
];

const SAMPLE_MANUAL: ManualStatementInput = {
  company_name: 'Công ty Công nghiệp Mẫu',
  fiscal_year: 2025,
  is_manufacturing: true,
  total_assets: 1_200_000_000,
  current_assets: 420_000_000,
  total_liabilities: 780_000_000,
  current_liabilities: 310_000_000,
  stockholders_equity: 420_000_000,
  retained_earnings: 180_000_000,
  revenues: 950_000_000,
  operating_income: 85_000_000,
  net_income: 52_000_000,
  operating_cash_flow: 98_000_000,
};

type ModelTab = 'evaluation' | 'manual' | 'batch';

export function ModelLabPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<ModelTab>('evaluation');
  const [selectedVersion, setSelectedVersion] = useState<string | undefined>(undefined);
  const [manualInput, setManualInput] = useState<ManualStatementInput>(SAMPLE_MANUAL);
  const [batchJson, setBatchJson] = useState(
    JSON.stringify(
      [
        SAMPLE_MANUAL,
        {
          ...SAMPLE_MANUAL,
          company_name: 'Doanh nghiệp Vận tải Khó khăn',
          total_liabilities: 1_120_000_000,
          stockholders_equity: 80_000_000,
          net_income: -95_000_000,
          operating_cash_flow: -40_000_000,
        },
      ],
      null,
      2,
    ),
  );
  const [batchParseError, setBatchParseError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  const versionsQuery = useQuery({
    queryKey: ['models', 'versions'],
    queryFn: api.getModelVersions,
  });

  const evalQuery = useQuery({
    queryKey: ['models', 'evaluation', selectedVersion],
    queryFn: () => api.getModelEvaluation(selectedVersion),
  });

  const manualMutation = useMutation({
    mutationFn: () => api.predictManual({ ...manualInput, model_version: selectedVersion }),
  });

  const saveAnalysisMutation = useMutation({
    mutationFn: () => api.saveAnalysis(manualInput.company_name, manualInput),
    onSuccess: () => setSavedNotice('Đã lưu vào Không gian cá nhân.'),
  });

  const batchMutation = useMutation({
    mutationFn: (items: ManualStatementInput[]) => api.predictBatch(items, selectedVersion),
  });

  function updateManualField(field: keyof ManualStatementInput, value: string | number | boolean) {
    setManualInput((prev) => ({ ...prev, [field]: value }));
  }

  function runBatch() {
    try {
      const parsed = JSON.parse(batchJson) as ManualStatementInput[];
      if (!Array.isArray(parsed) || parsed.length === 0) {
        setBatchParseError('Vui lòng nhập mảng JSON gồm ít nhất 1 báo cáo doanh nghiệp.');
        return;
      }
      setBatchParseError(null);
      batchMutation.mutate(parsed);
    } catch {
      setBatchParseError('Cú pháp JSON không hợp lệ. Hãy kiểm tra lại định dạng.');
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[1.375rem] font-semibold tracking-[-0.02em]">
            Phòng thí nghiệm Mô hình ML & Chấm điểm
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Kiểm tra các gói mô hình theo thời gian, kết quả kiểm định out-of-time và chấm điểm báo
            cáo tài chính tự nhập hoặc theo lô danh mục.
          </p>
        </div>

        {(versionsQuery.data ?? []).length > 0 ? (
          <div className="flex items-center gap-2 text-xs">
            <label htmlFor="model-ver-select" className="text-[var(--text-secondary)]">
              Phiên bản mô hình:
            </label>
            <select
              id="model-ver-select"
              value={selectedVersion ?? ''}
              onChange={(e) => setSelectedVersion(e.target.value || undefined)}
              className="h-8 px-2.5 font-mono bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded-[4px]"
            >
              <option value="">Mặc định đang chạy</option>
              {(versionsQuery.data ?? []).map((v) => (
                <option key={v.model_version} value={v.model_version}>
                  {v.model_version} {v.is_active ? '(đang chạy)' : ''}
                </option>
              ))}
            </select>
          </div>
        ) : null}
      </div>

      <div className="border-b border-[var(--border-subtle)] flex items-center gap-1" role="tablist">
        {(
          [
            { id: 'evaluation', label: 'Kho Mô hình & Đánh giá' },
            { id: 'manual', label: 'Chấm điểm Báo cáo Tự nhập' },
            { id: 'batch', label: 'Chấm điểm Danh mục theo Lô' },
          ] as const
        ).map((item) => (
          <button
            key={item.id}
            role="tab"
            type="button"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            className={cn(
              'px-4 py-2.5 text-xs font-medium border-b-2 transition-colors cursor-pointer bg-transparent',
              tab === item.id
                ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'evaluation' ? (
        <div className="space-y-5">
          <Panel>
            <PanelHeader
              title="Danh sách Phiên bản Mô hình đã lưu"
              description="Các gói mô hình bất biến trong thư mục data/artifacts/models."
            />
            {versionsQuery.isLoading ? (
              <TableSkeleton rows={3} />
            ) : (versionsQuery.data ?? []).length === 0 ? (
              <EmptyState
                title="Chưa có gói mô hình nào"
                description="Huấn luyện một gói mô hình mới qua API để hiển thị trong danh sách."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                      <th className="py-2.5 px-4 font-medium">Phiên bản</th>
                      <th className="py-2.5 px-3 font-medium">Mô hình chọn</th>
                      <th className="py-2.5 px-3 font-medium">Tập dữ liệu</th>
                      <th className="py-2.5 px-3 font-medium">Xử lý mất cân bằng</th>
                      <th className="py-2.5 px-3 font-medium">Ngày tạo</th>
                      <th className="py-2.5 px-4 font-medium text-right">Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {(versionsQuery.data ?? []).map((v) => (
                      <tr key={v.model_version} className="hover:bg-[var(--bg-hover)]">
                        <td className="py-2.5 px-4 font-mono font-semibold text-[var(--accent-primary)]">
                          {v.model_version}
                        </td>
                        <td className="py-2.5 px-3">{v.selected_model_name ?? '—'}</td>
                        <td className="py-2.5 px-3 text-[var(--text-secondary)]">{v.dataset}</td>
                        <td className="py-2.5 px-3 font-mono text-[var(--text-secondary)]">
                          {v.imbalance_strategy ?? '—'}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                          {formatDate(v.created_at)}
                        </td>
                        <td className="py-2.5 px-4 text-right">
                          {v.is_active ? (
                            <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--risk-low-bg)] text-[var(--risk-low-fg)]">
                              Đang chạy
                            </span>
                          ) : (
                            <span className="text-[var(--text-muted)]">Lưu trữ</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {evalQuery.data ? (
            <Panel>
              <PanelHeader
                title={`Đối chiếu Hiệu năng Các mô hình Phân loại (${evalQuery.data.model_version})`}
                description="So sánh tương tác ROC-AUC, PR-AUC và điểm F1 trên tập kiểm định out-of-time."
              />
              <div className="p-4">
                <ModelBenchmarkChart report={evalQuery.data.evaluation_report} />
              </div>
            </Panel>
          ) : null}

          <Panel>
            <PanelHeader
              title="Biểu đồ Đánh giá Nghiên cứu (Publication Figures)"
              description="Hình ảnh độ phân giải cao đọc trực tiếp từ /api/v1/figures."
            />
            <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {PUBLICATION_FIGURES.map((fig) => (
                <figure key={fig.file} className="surface-subtle overflow-hidden m-0">
                  <img
                    src={`/api/v1/figures/${fig.file}`}
                    alt={fig.title}
                    loading="lazy"
                    className="w-full h-48 object-contain bg-white p-2"
                  />
                  <figcaption className="px-3 py-2 text-xs font-medium text-[var(--text-secondary)] border-t border-[var(--border-subtle)]">
                    {fig.title}
                  </figcaption>
                </figure>
              ))}
            </div>
          </Panel>

          {evalQuery.data ? (
            <Panel>
              <PanelHeader
                title={`Báo cáo Đánh giá JSON gốc (${evalQuery.data.model_version})`}
                description="Báo cáo chi tiết được lưu kèm gói mô hình đã huấn luyện."
              />
              <pre className="p-4 text-[11px] font-mono overflow-x-auto max-h-80 text-[var(--text-secondary)]">
                {JSON.stringify(evalQuery.data.evaluation_report, null, 2)}
              </pre>
            </Panel>
          ) : null}
        </div>
      ) : null}

      {tab === 'manual' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <Panel className="lg:col-span-5">
            <PanelHeader
              title="Nhập Số liệu Báo cáo Tài chính"
              description="Nhập số liệu (đơn vị USD) để tính tỷ số, Altman Z và giải thích TreeSHAP."
            />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setSavedNotice(null);
                manualMutation.mutate();
              }}
              className="p-4 space-y-3 text-xs"
            >
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label htmlFor="m-name" className="block font-medium mb-1">Tên doanh nghiệp</label>
                  <input
                    id="m-name"
                    type="text"
                    required
                    value={manualInput.company_name}
                    onChange={(e) => updateManualField('company_name', e.target.value)}
                    className="w-full h-8 px-2.5 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                  />
                </div>
                <div>
                  <label htmlFor="m-fy" className="block font-medium mb-1">Năm tài chính</label>
                  <input
                    id="m-fy"
                    type="number"
                    required
                    value={manualInput.fiscal_year}
                    onChange={(e) => updateManualField('fiscal_year', Number(e.target.value))}
                    className="w-full h-8 px-2.5 num bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                  />
                </div>
                <div className="flex items-end pb-1.5">
                  <label className="inline-flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={manualInput.is_manufacturing}
                      onChange={(e) => updateManualField('is_manufacturing', e.target.checked)}
                      className="accent-[var(--accent-primary)]"
                    />
                    <span>Doanh nghiệp sản xuất</span>
                  </label>
                </div>
                {(
                  [
                    ['total_assets', 'Tổng tài sản *'],
                    ['total_liabilities', 'Tổng nợ phải trả *'],
                    ['current_assets', 'Tài sản ngắn hạn'],
                    ['current_liabilities', 'Nợ ngắn hạn'],
                    ['stockholders_equity', 'Vốn chủ sở hữu'],
                    ['retained_earnings', 'Lợi nhuận giữ lại'],
                    ['revenues', 'Doanh thu thuần'],
                    ['operating_income', 'Lợi nhuận hoạt động (EBIT)'],
                    ['net_income', 'Lợi nhuận ròng'],
                    ['operating_cash_flow', 'Dòng tiền hoạt động (OCF)'],
                  ] as const
                ).map(([field, label]) => (
                  <div key={field}>
                    <label htmlFor={`m-${field}`} className="block font-medium mb-1">
                      {label}
                    </label>
                    <input
                      id={`m-${field}`}
                      type="number"
                      required={field === 'total_assets' || field === 'total_liabilities'}
                      value={manualInput[field] ?? ''}
                      onChange={(e) =>
                        updateManualField(
                          field,
                          e.target.value === '' ? (null as unknown as number) : Number(e.target.value),
                        )
                      }
                      className="w-full h-8 px-2.5 num bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                    />
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2 pt-2">
                <Button type="submit" variant="primary" disabled={manualMutation.isPending}>
                  <Cpu className="h-3.5 w-3.5" aria-hidden="true" />
                  {manualMutation.isPending ? 'Đang chấm điểm...' : 'Chạy dự báo mô hình'}
                </Button>
                {user && manualMutation.data ? (
                  <Button
                    variant="secondary"
                    disabled={saveAnalysisMutation.isPending}
                    onClick={() => saveAnalysisMutation.mutate()}
                  >
                    <BookmarkPlus className="h-3.5 w-3.5" aria-hidden="true" />
                    Lưu vào Không gian cá nhân
                  </Button>
                ) : null}
                {savedNotice ? (
                  <span className="text-[var(--risk-low-fg)]">{savedNotice}</span>
                ) : null}
              </div>
            </form>
          </Panel>

          <div className="lg:col-span-7 space-y-4">
            {manualMutation.isError ? (
              <ErrorState
                message={
                  manualMutation.error instanceof Error
                    ? manualMutation.error.message
                    : 'Không thể thực hiện dự báo.'
                }
              />
            ) : !manualMutation.data ? (
              <Panel>
                <EmptyState
                  title="Chưa có kết quả chấm điểm"
                  description="Nhập số liệu báo cáo bên trái và bấm Chạy dự báo để tính xác suất kiệt quệ, Altman Z và TreeSHAP."
                />
              </Panel>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <MetricTile
                    label="Xác suất Kiệt quệ"
                    value={formatPct(manualMutation.data.prediction.distress_probability)}
                    meta={`Mô hình ${manualMutation.data.prediction.model_version}`}
                  />
                  <MetricTile
                    label="Altman Z-Score"
                    value={formatRatio(manualMutation.data.altman_z_score)}
                    meta={manualMutation.data.altman_zone ?? '—'}
                  />
                  <MetricTile
                    label="Điểm Sức khỏe"
                    value={formatScore(manualMutation.data.health_pillars?.overall_score)}
                    meta={`Hạng ${manualMutation.data.health_pillars?.overall_grade ?? '—'}`}
                  />
                </div>

                <Panel>
                  <PanelHeader
                    title="Các yếu tố TreeSHAP hàng đầu"
                    actions={<RiskBadge level={manualMutation.data.prediction.risk_level} />}
                  />
                  <div className="divide-y divide-[var(--border-subtle)] text-xs">
                    {manualMutation.data.prediction.top_drivers.slice(0, 8).map((d) => (
                      <div key={d.feature} className="px-4 py-2.5 flex items-center justify-between">
                        <span className="font-medium">{humanizeFeature(d.feature)}</span>
                        <span
                          className="num font-semibold"
                          style={{
                            color:
                              (d.shap_value ?? 0) >= 0
                                ? 'var(--risk-critical-fg)'
                                : 'var(--risk-low-fg)',
                          }}
                        >
                          {formatSigned(d.shap_value, 4)} log-odds
                        </span>
                      </div>
                    ))}
                  </div>
                </Panel>
              </>
            )}
          </div>
        </div>
      ) : null}

      {tab === 'batch' ? (
        <div className="space-y-4">
          <Panel>
            <PanelHeader
              title="Dữ liệu Danh mục JSON theo Lô (tối đa 200 doanh nghiệp)"
              description="Gửi mảng báo cáo tài chính để chấm điểm tổng hợp rủi ro toàn danh mục."
              actions={
                <Button variant="primary" size="sm" onClick={runBatch} disabled={batchMutation.isPending}>
                  <Play className="h-3.5 w-3.5" aria-hidden="true" />
                  {batchMutation.isPending ? 'Đang chấm lô...' : 'Chấm điểm danh mục'}
                </Button>
              }
            />
            <div className="p-4 space-y-2">
              <textarea
                rows={10}
                value={batchJson}
                onChange={(e) => setBatchJson(e.target.value)}
                aria-label="Mảng JSON báo cáo doanh nghiệp"
                className="w-full p-3 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
              />
              {batchParseError ? (
                <p role="alert" className="text-xs text-[var(--risk-critical-fg)]">
                  {batchParseError}
                </p>
              ) : null}
            </div>
          </Panel>

          {batchMutation.data ? (
            <Panel>
              <PanelHeader
                title={`Kết quả Chấm điểm Danh mục (${batchMutation.data.total_companies} doanh nghiệp)`}
                description={`XS kiệt quệ trung bình: ${formatPct(batchMutation.data.average_distress_probability)} · Mô hình ${batchMutation.data.model_version}`}
              />
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                      <th className="py-2.5 px-4 font-medium">Doanh nghiệp</th>
                      <th className="py-2.5 px-3 font-medium text-right">XS Kiệt quệ</th>
                      <th className="py-2.5 px-3 font-medium text-right">Điểm SK</th>
                      <th className="py-2.5 px-3 font-medium text-right">Altman Z</th>
                      <th className="py-2.5 px-3 font-medium">Yếu tố rủi ro chính</th>
                      <th className="py-2.5 px-4 font-medium text-right">Mức rủi ro</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {batchMutation.data.results.map((r, i) => (
                      <tr key={`${r.company_name}-${i}`} className="hover:bg-[var(--bg-hover)]">
                        <td className="py-2.5 px-4 font-medium">{r.company_name}</td>
                        <td className="py-2.5 px-3 text-right num font-semibold">
                          {formatPct(r.distress_probability)}
                        </td>
                        <td className="py-2.5 px-3 text-right num">
                          {formatScore(r.overall_health_score)}
                        </td>
                        <td className="py-2.5 px-3 text-right num">
                          {formatRatio(r.altman_z_score)}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--text-secondary)]">
                          {r.top_risk_driver ? humanizeFeature(r.top_risk_driver) : '—'}
                        </td>
                        <td className="py-2.5 px-4 text-right">
                          <RiskBadge level={r.risk_level} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
