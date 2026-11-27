import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import type { CompanySummary } from '@/types/api';
import { formatPct, formatRatio, translateSector } from '@/lib/format';
import { EmptyState } from '@/components/ui/Primitives';

const RISK_FILL: Record<string, string> = {
  LOW: '#0D7A68',
  MEDIUM: '#D97706',
  HIGH: '#EA580C',
  CRITICAL: '#BE123C',
};

const RISK_VI: Record<string, string> = {
  LOW: 'Thấp',
  MEDIUM: 'Trung bình',
  HIGH: 'Cao',
  CRITICAL: 'Nguy kịch',
};

export function SectorRiskChart({ companies }: { companies: CompanySummary[] }) {
  const data = useMemo(() => {
    const map = new Map<
      string,
      { sector: string; LOW: number; MEDIUM: number; HIGH: number; CRITICAL: number; total: number }
    >();
    for (const c of companies) {
      const sector = translateSector(c.sector);
      const entry = map.get(sector) ?? {
        sector,
        LOW: 0,
        MEDIUM: 0,
        HIGH: 0,
        CRITICAL: 0,
        total: 0,
      };
      const risk = (c.risk_level ?? '').toUpperCase();
      if (risk === 'LOW' || risk === 'MEDIUM' || risk === 'HIGH' || risk === 'CRITICAL') {
        entry[risk] += 1;
        entry.total += 1;
      }
      map.set(sector, entry);
    }
    return Array.from(map.values())
      .filter((r) => r.total > 0)
      .sort((a, b) => b.HIGH + b.CRITICAL - (a.HIGH + a.CRITICAL) || b.total - a.total)
      .slice(0, 7);
  }, [companies]);

  if (data.length === 0) {
    return (
      <EmptyState
        title="Chưa có dữ liệu rủi ro theo ngành"
        description="Biểu đồ phân bổ ngành sẽ hiển thị sau khi doanh nghiệp được chấm điểm rủi ro."
      />
    );
  }

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--border-subtle)' }}
          />
          <YAxis
            type="category"
            dataKey="sector"
            width={165}
            tick={{ fill: 'var(--text-primary)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: 'var(--bg-hover)' }}
            contentStyle={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-strong)',
              borderRadius: '6px',
              fontSize: '12px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '11px' }} />
          <Bar dataKey="LOW" stackId="risk" name="Thấp" fill={RISK_FILL.LOW} maxBarSize={18} />
          <Bar dataKey="MEDIUM" stackId="risk" name="Trung bình" fill={RISK_FILL.MEDIUM} maxBarSize={18} />
          <Bar dataKey="HIGH" stackId="risk" name="Cao" fill={RISK_FILL.HIGH} maxBarSize={18} />
          <Bar
            dataKey="CRITICAL"
            stackId="risk"
            name="Nguy kịch"
            fill={RISK_FILL.CRITICAL}
            radius={[0, 3, 3, 0]}
            maxBarSize={18}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface FrontierPoint {
  ticker: string;
  name: string;
  cik: string;
  z: number;
  probPct: number;
  risk: string;
  rawProb: number;
}

export function RiskReturnScatterChart({ companies }: { companies: CompanySummary[] }) {
  const navigate = useNavigate();

  const points = useMemo<FrontierPoint[]>(() => {
    const out: FrontierPoint[] = [];
    for (const c of companies) {
      if (
        typeof c.altman_z_score === 'number' &&
        Number.isFinite(c.altman_z_score) &&
        typeof c.distress_probability === 'number' &&
        Number.isFinite(c.distress_probability)
      ) {
        out.push({
          ticker: c.ticker ?? c.cik,
          name: c.name,
          cik: c.cik,
          z: Math.max(-2, Math.min(12, c.altman_z_score)),
          probPct: Number((c.distress_probability * 100).toFixed(1)),
          risk: (c.risk_level ?? 'LOW').toUpperCase(),
          rawProb: c.distress_probability,
        });
      }
    }
    return out;
  }, [companies]);

  if (points.length === 0) {
    return (
      <EmptyState
        title="Chưa có dữ liệu biên rủi ro"
        description="Cần dữ liệu cả Altman Z-Score và xác suất kiệt quệ t+1 để vẽ biểu đồ."
      />
    );
  }

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 14, right: 20, bottom: 14, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis
            type="number"
            dataKey="z"
            name="Altman Z"
            domain={[-2, 12]}
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
            label={{
              value: 'Altman Z-Score (giới hạn -2..12)',
              position: 'insideBottom',
              offset: -6,
              fill: 'var(--text-muted)',
              fontSize: 11,
            }}
          />
          <YAxis
            type="number"
            dataKey="probPct"
            name="Xác suất kiệt quệ"
            unit="%"
            domain={[0, 100]}
            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
          />
          <ZAxis range={[52, 52]} />
          <ReferenceLine
            x={1.81}
            stroke="#BE123C"
            strokeDasharray="4 4"
            label={{ value: 'Z=1.81', position: 'insideTopLeft', fill: '#BE123C', fontSize: 10 }}
          />
          <ReferenceLine
            x={2.99}
            stroke="#0D7A68"
            strokeDasharray="4 4"
            label={{ value: 'Z=2.99', position: 'insideTopRight', fill: '#0D7A68', fontSize: 10 }}
          />
          <Tooltip
            cursor={{ strokeDasharray: '3 3' }}
            content={({ payload }) => {
              const pt = payload?.[0]?.payload as FrontierPoint | undefined;
              if (!pt) return null;
              return (
                <div className="surface p-2.5 text-xs space-y-1">
                  <div className="font-mono font-semibold text-[var(--accent-primary)]">
                    {pt.ticker} · {pt.name}
                  </div>
                  <div className="num text-[var(--text-secondary)]">
                    Xác suất kiệt quệ P(t+1):{' '}
                    <strong className="text-[var(--text-primary)]">{formatPct(pt.rawProb)}</strong>
                  </div>
                  <div className="num text-[var(--text-secondary)]">
                    Altman Z: <strong className="text-[var(--text-primary)]">{formatRatio(pt.z)}</strong> · Mức:{' '}
                    {RISK_VI[pt.risk] ?? pt.risk}
                  </div>
                </div>
              );
            }}
          />
          <Scatter
            data={points}
            className="cursor-pointer"
            onClick={(node) => {
              const pt = node?.payload as FrontierPoint | undefined;
              if (pt) navigate(`/companies/${encodeURIComponent(pt.ticker)}`);
            }}
          >
            {points.map((pt) => (
              <Cell key={pt.cik} fill={RISK_FILL[pt.risk] ?? '#475569'} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
