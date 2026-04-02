'use client';

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  ResponsiveContainer, Cell,
} from 'recharts';
import type { VelocityDatum, LifecycleStage } from './data';

const LIFECYCLE_COLORS: Record<LifecycleStage, string> = {
  growing: '#6CB8D2',
  peaking: '#F5A623',
  stable: 'rgba(104,112,118,0.4)',
  declining: '#E87C3F',
  stale: '#E5484D',
};

interface VelocityChartProps {
  data: VelocityDatum[];
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: VelocityDatum }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div
      style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 4, padding: '8px 12px',
        boxShadow: 'var(--shadow-float)',
      }}
    >
      <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>{d.title}</p>
      <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{d.velocity}</span> citations/week
      </p>
      <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{d.lifecycle}</p>
      <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>{d.cluster}</p>
    </div>
  );
}

export function VelocityChart({ data }: VelocityChartProps) {
  const chartData = data.map((d) => ({
    ...d,
    label: d.title.length > 18 ? d.title.slice(0, 18) + '\u2026' : d.title,
  }));

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: 4, padding: 12 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
        Citation Velocity by Content
      </h3>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
        Citations per week by content piece — bars colored by lifecycle stage
      </p>
      <div style={{ height: 280, marginTop: 12 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 60, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
              angle={-45}
              textAnchor="end"
              height={70}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={1.0}
              stroke="#E5484D"
              strokeDasharray="4 4"
              label={{
                value: 'Stale threshold',
                position: 'right',
                style: { fontSize: 10, fill: '#E5484D' },
              }}
            />
            <Bar dataKey="velocity" radius={[3, 3, 0, 0]} maxBarSize={36}>
              {chartData.map((entry, idx) => (
                <Cell key={idx} fill={LIFECYCLE_COLORS[entry.lifecycle]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'flex', gap: 16, marginTop: 8, paddingLeft: 4 }}>
        {(['growing', 'peaking', 'stable', 'declining', 'stale'] as const).map((s) => (
          <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: LIFECYCLE_COLORS[s] }} />
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'capitalize' }}>{s}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
