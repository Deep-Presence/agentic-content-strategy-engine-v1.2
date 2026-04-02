'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { battleData } from './data';

const COMPETITORS = [
  { key: 'lovable.dev', color: 'var(--accent)', bold: true },
  { key: 'bolt.new', color: 'var(--error)', bold: false },
  { key: 'cursor.com', color: 'var(--warning)', bold: false },
  { key: 'replit.com', color: 'var(--text-tertiary)', bold: false },
  { key: 'v0.dev', color: 'var(--success)', bold: false },
] as const;

function Favicon({ domain, size = 12 }: { domain: string; size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 2 }}
      onError={(e) => {
        const target = e.target as HTMLImageElement;
        if (!target.dataset.fallback) {
          target.dataset.fallback = '1';
          target.src = `https://logo.clearbit.com/${domain}`;
        }
      }}
    />
  );
}

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload) return null;
  return (
    <div
      className="px-3 py-2 rounded-sm"
      style={{
        background: 'rgba(17,24,28,0.92)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--border-strong)',
      }}
    >
      <p style={{ fontSize: '11px', color: '#A0A0A0', marginBottom: '4px' }}>{label}</p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="flex items-center gap-2" style={{ fontSize: '11px' }}>
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          <span style={{ color: '#A0A0A0' }}>{entry.dataKey}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, color: '#EDEDED', marginLeft: 'auto' }}>
            {entry.value.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}

export function BattleChart() {
  return (
    <div className="rounded-sm overflow-hidden" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <div>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Head-to-Head Daily Battle
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Share of Voice % — daily data points
          </p>
        </div>
        <div className="flex items-center gap-4">
          {COMPETITORS.map((c) => (
            <div key={c.key} className="flex items-center gap-1.5">
              <span
                className="inline-block rounded-full"
                style={{
                  width: '16px',
                  height: c.bold ? '3px' : '1.5px',
                  backgroundColor: c.color,
                }}
              />
              <Favicon domain={c.key} size={12} />
              <span style={{
                fontSize: '11px',
                color: 'var(--text-secondary)',
                fontWeight: c.bold ? 600 : 400,
              }}>
                {c.key}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="px-3 pb-3">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={battleData} margin={{ top: 5, right: 12, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
              stroke="var(--border)"
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
              tickFormatter={(v: number) => `${v}%`}
              stroke="var(--border)"
              tickLine={false}
              domain={[4, 22]}
            />
            <Tooltip content={<CustomTooltip />} />
            {COMPETITORS.map((c) => (
              <Line
                key={c.key}
                type="monotone"
                dataKey={c.key}
                stroke={c.color}
                strokeWidth={c.bold ? 3 : 1.5}
                strokeDasharray={c.bold ? undefined : '6 3'}
                dot={c.bold ? { r: 2, fill: c.color } : false}
                activeDot={{ r: c.bold ? 4 : 3 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
