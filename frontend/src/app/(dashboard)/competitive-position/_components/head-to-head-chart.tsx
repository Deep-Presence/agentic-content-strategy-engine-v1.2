'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts';
import { SOV_TREND, MILESTONES } from './data';
import { BrandLogo } from './brand-logo';

const COMPETITOR_COLORS: Record<string, string> = {
  you: 'var(--accent)',
  'bolt.new': '#E5484D',
  'cursor.com': '#34B27B',
  'replit.com': '#F5A623',
  'v0.dev': '#9D8CE0',
  'emergent.sh': 'var(--text-secondary)',
};

const LEGEND_ENTRIES = [
  { key: 'you', label: 'You (Lovable)', domain: 'lovable.dev' },
  { key: 'bolt.new', label: 'Bolt.new', domain: 'bolt.new' },
  { key: 'cursor.com', label: 'Cursor', domain: 'cursor.com' },
  { key: 'replit.com', label: 'Replit', domain: 'replit.com' },
  { key: 'v0.dev', label: 'V0.dev', domain: 'v0.dev' },
  { key: 'emergent.sh', label: 'Emergent', domain: 'emergent.sh' },
];

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: 'rgba(17,24,28,0.92)',
        backdropFilter: 'blur(8px)',
        borderRadius: '6px',
        padding: '8px 12px',
        boxShadow: 'var(--shadow-float)',
      }}
    >
      <p style={{ fontSize: '11px', fontWeight: 600, color: '#EDEDED', marginBottom: '4px' }}>{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} style={{ fontSize: '11px', color: '#EDEDED', lineHeight: 1.5 }}>
          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: entry.color, marginRight: '6px' }} />
          {entry.dataKey === 'you' ? 'You' : entry.dataKey}: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{entry.value}%</span>
        </p>
      ))}
    </div>
  );
}

export function HeadToHeadChart() {
  // Find milestone positions in data
  const milestoneData = MILESTONES.map((m) => {
    const idx = SOV_TREND.findIndex((d) => d.date === m.date);
    if (idx === -1) return null;
    return { ...m, x: SOV_TREND[idx].date, y: SOV_TREND[idx].you };
  }).filter(Boolean) as (typeof MILESTONES[number] & { x: string; y: number })[];

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: '6px',
        padding: '14px',
        animation: 'fadeIn 300ms ease 300ms both',
      }}
    >
      {/* Header + Legend */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            Your Position
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Share of voice trend over 28 days — how often AI engines cite each brand
          </p>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
          {LEGEND_ENTRIES.map((entry) => (
            <div key={entry.key} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <BrandLogo domain={entry.domain} size={12} />
              <div style={{ width: '20px', height: '0', borderTop: `${entry.key === 'you' ? '3px' : '1.5px'} solid ${COMPETITOR_COLORS[entry.key]}`, opacity: entry.key === 'you' ? 1 : 0.6 }} />
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>{entry.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={SOV_TREND} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="none" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fontFamily: 'var(--font-display)', fill: 'var(--text-secondary)' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            interval={4}
          />
          <YAxis
            tick={{ fontSize: 11, fontFamily: 'var(--font-mono)', fill: 'var(--text-secondary)' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `${v}%`}
            domain={['auto', 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Your line — boldest */}
          <Line
            type="monotone"
            dataKey="you"
            stroke="var(--accent)"
            strokeWidth={3}
            dot={false}
            activeDot={{ r: 4, fill: 'var(--accent)', stroke: 'var(--surface)', strokeWidth: 2 }}
          />

          {/* Competitor lines — thinner, slightly transparent */}
          {(['bolt.new', 'cursor.com', 'replit.com', 'v0.dev', 'emergent.sh'] as const).map((key) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COMPETITOR_COLORS[key]}
              strokeWidth={1.5}
              strokeOpacity={0.6}
              dot={false}
              activeDot={{ r: 3, fill: COMPETITOR_COLORS[key], stroke: 'var(--surface)', strokeWidth: 2 }}
            />
          ))}

          {/* Milestone dots on the chart */}
          {milestoneData.map((m, i) => (
            <ReferenceDot
              key={i}
              x={m.x}
              y={m.y}
              r={4}
              fill={m.color}
              stroke="var(--surface)"
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Milestone legend strip below chart */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginTop: '10px', padding: '0 4px' }}>
        {MILESTONES.map((m, i) => (
          <div
            key={i}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', animation: `fadeUp 300ms ease ${400 + i * 50}ms both` }}
          >
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: m.color, flexShrink: 0 }} />
            <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>{m.date}</span>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>{m.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
