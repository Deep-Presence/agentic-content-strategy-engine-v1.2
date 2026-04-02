'use client';

import { SNIPPET_DISTRIBUTION } from './tech-readiness-data';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts';

export function SnippetDistribution() {
  const data = SNIPPET_DISTRIBUTION.map((d) => ({
    ...d,
    xLabel: `${d.range}\n${d.label}`,
  }));

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
      <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>
        Snippet Readiness Distribution
      </h3>
      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
        Pages grouped by AEO snippet readiness score
      </p>
      <div style={{ width: '100%', height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barCategoryGap="20%" margin={{ top: 20, right: 8, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="range"
              tick={{ fontSize: 10, fill: 'var(--text-secondary)' }}
              axisLine={{ stroke: 'var(--border)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--surface-raised)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 11,
              }}
              formatter={(value, _name, props) => [
                `${value} pages`,
                (props as unknown as { payload: { label: string } }).payload.label,
              ]}
            />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
              <LabelList
                dataKey="count"
                position="top"
                style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', fill: 'var(--text-primary)' }}
              />
              {SNIPPET_DISTRIBUTION.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* Callout */}
      <div style={{
        background: 'rgba(229, 72, 77, 0.06)',
        border: '1px solid rgba(229, 72, 77, 0.15)',
        borderRadius: '4px',
        padding: '8px',
        marginTop: '8px',
        fontSize: '12px',
        color: 'var(--text-secondary)',
      }}>
        <span style={{ marginRight: '4px' }}>{'\u26A0\uFE0F'}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--error)' }}>62 pages</span> have snippet readiness below 20 — these are virtually uncitable by AI engines.
      </div>
    </div>
  );
}
