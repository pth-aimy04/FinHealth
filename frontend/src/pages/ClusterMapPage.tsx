import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight } from 'lucide-react';
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { api } from '@/lib/api';
import { formatPct, formatRatio } from '@/lib/format';
import type { ClusterPoint } from '@/types/api';
import {
  Button,
  EmptyState,
  ErrorState,
  Panel,
  PanelHeader,
  Skeleton,
} from '@/components/ui/Primitives';

const CLUSTER_COLORS = ['#0F766E', '#1D4ED8', '#D97706', '#DC2626', '#475569'];

export function ClusterMapPage() {
  const [selected, setSelected] = useState<ClusterPoint | null>(null);
  const [clusterFilter, setClusterFilter] = useState<string>('ALL');

  const query = useQuery({
    queryKey: ['clusters', 'map'],
    queryFn: api.getClusterMap,
  });

  const points = query.data ?? [];

  const clusters = useMemo(() => {
    const map = new Map<number, { id: number; label: string; rows: ClusterPoint[] }>();
    for (const p of points) {
      if (typeof p.pca_comp_1 !== 'number' || typeof p.pca_comp_2 !== 'number') continue;
      const existing = map.get(p.cluster_id);
      if (existing) {
        existing.rows.push(p);
      } else {
        map.set(p.cluster_id, { id: p.cluster_id, label: p.cluster_label, rows: [p] });
      }
    }
    return Array.from(map.values()).sort((a, b) => a.id - b.id);
  }, [points]);

  const visibleClusters =
    clusterFilter === 'ALL'
      ? clusters
      : clusters.filter((c) => String(c.id) === clusterFilter);

  if (query.isError) {
    return (
      <ErrorState
        message={query.error instanceof Error ? query.error.message : 'Không thể tải bản đồ phân cụm PCA.'}
        onRetry={() => void query.refetch()}
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[1.375rem] font-semibold tracking-[-0.02em]">
            Bản đồ Phân cụm Ngang hàng (PCA)
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Phép chiếu thành phần chính 2 chiều từ hồ sơ báo cáo năm 10-K mới nhất. Bấm vào từng
            điểm để xem chi tiết doanh nghiệp.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <label htmlFor="cluster-filter" className="text-[var(--text-secondary)]">
            Lọc cụm:
          </label>
          <select
            id="cluster-filter"
            value={clusterFilter}
            onChange={(e) => setClusterFilter(e.target.value)}
            className="h-8 px-2.5 bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded-[4px]"
          >
            <option value="ALL">Tất cả cụm ({points.length})</option>
            {clusters.map((c) => (
              <option key={c.id} value={String(c.id)}>
                #{c.id} {c.label} ({c.rows.length})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Panel className="lg:col-span-8">
          <PanelHeader
            title="Không gian Trạng thái Tài chính (PC1 vs PC2)"
            description="Màu sắc thể hiện cụm sức khỏe tài chính; bấm vào từng điểm để kiểm tra."
          />
          <div className="p-4 h-[440px]">
            {query.isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : visibleClusters.length === 0 ? (
              <EmptyState
                title="Chưa có tọa độ PCA"
                description="Tọa độ phân cụm sẽ hiển thị sau khi quy trình PCA chạy trên báo cáo năm."
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 12, right: 20, bottom: 12, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis
                    type="number"
                    dataKey="pca_comp_1"
                    name="PC1"
                    tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="pca_comp_2"
                    name="PC2"
                    tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                  />
                  <ZAxis range={[55, 55]} />
                  <Tooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    content={({ payload }) => {
                      const pt = payload?.[0]?.payload as ClusterPoint | undefined;
                      if (!pt) return null;
                      return (
                        <div className="surface p-2.5 text-xs space-y-1">
                          <div className="font-mono font-semibold text-[var(--accent-primary)]">
                            {pt.ticker ?? pt.cik} · {pt.name}
                          </div>
                          <div className="text-[var(--text-secondary)]">
                            Cụm: {pt.cluster_label} (FY{pt.fiscal_year})
                          </div>
                          <div className="num">
                            XS Kiệt quệ: {formatPct(pt.distress_probability)} · Z: {formatRatio(pt.altman_z_score)}
                          </div>
                        </div>
                      );
                    }}
                  />
                  {visibleClusters.map((group) => (
                    <Scatter
                      key={group.id}
                      name={`#${group.id} ${group.label}`}
                      data={group.rows}
                      fill={CLUSTER_COLORS[group.id % CLUSTER_COLORS.length]}
                      onClick={(node) => {
                        if (node?.payload) setSelected(node.payload as ClusterPoint);
                      }}
                      className="cursor-pointer"
                    />
                  ))}
                </ScatterChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        <Panel className="lg:col-span-4 flex flex-col">
          <PanelHeader
            title="Chi tiết Doanh nghiệp Chọn"
            description="Tọa độ thành phần chính và tóm tắt rủi ro."
          />
          <div className="p-4 flex-1 space-y-4">
            {selected ? (
              <div className="space-y-3 text-xs">
                <div>
                  <div className="font-mono text-base font-semibold text-[var(--accent-primary)]">
                    {selected.ticker ?? selected.cik}
                  </div>
                  <div className="text-sm font-medium text-[var(--text-primary)]">
                    {selected.name}
                  </div>
                  <div className="text-[var(--text-secondary)] mt-0.5">
                    CIK {selected.cik} · Năm tài chính FY{selected.fiscal_year}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div className="surface-subtle p-2.5">
                    <div className="text-[var(--text-secondary)]">XS Kiệt quệ</div>
                    <div className="mt-0.5 text-sm font-semibold num">
                      {formatPct(selected.distress_probability)}
                    </div>
                  </div>
                  <div className="surface-subtle p-2.5">
                    <div className="text-[var(--text-secondary)]">Altman Z</div>
                    <div className="mt-0.5 text-sm font-semibold num">
                      {formatRatio(selected.altman_z_score)}
                    </div>
                  </div>
                  <div className="surface-subtle p-2.5">
                    <div className="text-[var(--text-secondary)]">Tọa độ PC1 / PC2</div>
                    <div className="mt-0.5 font-mono">
                      {formatRatio(selected.pca_comp_1)} / {formatRatio(selected.pca_comp_2)}
                    </div>
                  </div>
                  <div className="surface-subtle p-2.5">
                    <div className="text-[var(--text-secondary)]">Nhóm cụm</div>
                    <div className="mt-0.5 font-medium truncate">{selected.cluster_label}</div>
                  </div>
                </div>

                <Link
                  to={`/companies/${encodeURIComponent(selected.ticker || selected.cik)}`}
                  className="no-underline block"
                >
                  <Button variant="primary" size="sm" className="w-full">
                    Mở Hồ sơ Phân tích Chi tiết
                    <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </Button>
                </Link>
              </div>
            ) : (
              <EmptyState
                title="Chưa chọn doanh nghiệp"
                description="Bấm vào bất kỳ điểm nào trên bản đồ PCA để xem chi tiết cụm và chỉ số rủi ro."
              />
            )}

            <div className="pt-3 border-t border-[var(--border-subtle)] space-y-2">
              <h3 className="text-xs font-semibold text-[var(--text-primary)]">Chú giải Cụm PCA</h3>
              {clusters.map((c) => (
                <div key={c.id} className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2 text-[var(--text-secondary)]">
                    <span
                      className="h-2.5 w-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: CLUSTER_COLORS[c.id % CLUSTER_COLORS.length] }}
                    />
                    <span>{c.label}</span>
                  </span>
                  <span className="num text-[var(--text-primary)] font-medium">{c.rows.length}</span>
                </div>
              ))}
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
