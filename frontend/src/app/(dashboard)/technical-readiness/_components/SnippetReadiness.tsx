'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  LabelList,
} from 'recharts';
import { SNIPPET_DISTRIBUTION } from './tech-readiness-data';

interface SnippetReadinessProps {
  onViewLowPages: () => void;
}

export function SnippetReadiness({ onViewLowPages }: SnippetReadinessProps) {
  const data = SNIPPET_DISTRIBUTION.map((band) => ({
    range: band.range,
    count: band.count,
    label: band.label,
    color: band.color,
  }));

  return (
    <div>
      <div className="mb-3">
        <h2
          className="text-[16px] font-semibold"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          Page Readiness Distribution
        </h2>
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          How many of your pages are ready for AI citation
        </p>
      </div>

      {/* Bar Chart */}
      <div className="border border-[var(--border)] rounded-[var(--radius-md)] p-3 bg-[var(--surface)] mb-3">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data} barCategoryGap="20%">
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="range"
              tick={{ fontSize: 11, fill: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
              width={35}
              label={{
                value: 'Pages',
                angle: -90,
                position: 'insideLeft',
                style: { fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' },
              }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
              <LabelList
                dataKey="count"
                position="top"
                style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fill: 'var(--text-primary)' }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Range labels */}
        <div className="flex justify-around mt-1 px-6">
          {SNIPPET_DISTRIBUTION.map((band) => (
            <span
              key={band.range}
              className="text-[10px] text-center"
              style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
            >
              {band.label}
            </span>
          ))}
        </div>
      </div>

      {/* Alert Callout */}
      <div
        className="rounded-[var(--radius-md)] p-3"
        style={{
          border: '1px solid var(--warning)',
          borderLeft: '3px solid var(--warning)',
          background: 'var(--warning-subtle)',
        }}
      >
        <p
          className="text-[13px] leading-[1.6]"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          <span className="font-semibold">62 pages have readiness below 20</span> — these are virtually uncitable by AI engines.
          Fixing question headings and FAQ sections on these pages would move most of them to the 40-60 range.
        </p>
        <button
          className="mt-2 h-[30px] px-3 text-[12px] font-medium rounded-[var(--radius-sm)] border border-[var(--warning)] hover:bg-[var(--warning-subtle)] transition-colors"
          style={{ color: 'var(--warning)', fontFamily: 'var(--font-display)' }}
          onClick={onViewLowPages}
        >
          View these 62 pages
        </button>
      </div>
    </div>
  );
}
