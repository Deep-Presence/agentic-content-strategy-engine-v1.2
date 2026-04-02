'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { GAP_TREND } from './data';

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.[0]) return null;
  return (
    <div
      className="px-3 py-2 rounded-sm"
      style={{
        background: 'rgba(17,24,28,0.92)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--border-strong)',
      }}
    >
      <p style={{ fontSize: '11px', color: '#A0A0A0', marginBottom: '2px' }}>{label}</p>
      <p style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 500, color: '#EDEDED' }}>
        {payload[0].value}pp
      </p>
    </div>
  );
}

export function GapTrendChart() {
  return (
    <div className="rounded-sm overflow-hidden" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div className="px-3 pt-3 pb-2">
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Gap to #1 Trend
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          8-week gap trajectory vs bolt.new — closing toward 0
        </p>
      </div>

      <div className="px-3 pb-3">
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={GAP_TREND} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="gapGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--error)" stopOpacity={0.15} />
                <stop offset="100%" stopColor="var(--error)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="week"
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
              stroke="var(--border)"
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
              tickFormatter={(v: number) => `${v}pp`}
              stroke="var(--border)"
              tickLine={false}
              domain={[-9, 1]}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="var(--success)" strokeDasharray="4 4" strokeWidth={1.5} />
            <Area
              type="monotone"
              dataKey="gap"
              stroke="var(--error)"
              strokeWidth={2}
              fill="url(#gapGradient)"
              dot={{ r: 3, fill: 'var(--error)', stroke: 'var(--surface)', strokeWidth: 2 }}
              activeDot={{ r: 5 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
