'use client';

import { useCallback } from 'react';
import {
  ComposedChart,
  Area,
  CartesianGrid,
  XAxis,
  Tooltip,
  ResponsiveContainer,
  Line,
} from 'recharts';
import type { DayData, ViewConfig } from './mock-data';
import { COMPETITORS } from './mock-data';

interface PresenceChartProps {
  data: DayData[];
  viewConfig: ViewConfig;
  hoverIdx: number | null;
  onHover: (idx: number | null) => void;
  showCompetitors: boolean;
}

// Resolve known CSS var() to hex for SVG gradient stops
const COLOR_MAP: Record<string, string> = {
  'var(--accent)': '#5BA4C4',
  'var(--success)': '#34B27B',
  'var(--warning)': '#DC7B18',
  '#8B5CF6': '#8B5CF6',
};

function HoverTracker({ active, payload, onHover }: {
  active?: boolean;
  payload?: Array<{ payload: { _idx: number } }>;
  onHover: (idx: number | null) => void;
}) {
  if (active && payload?.[0]) {
    const idx = payload[0].payload._idx;
    if (typeof idx === 'number') {
      requestAnimationFrame(() => onHover(idx));
    }
  }
  return null;
}

export function PresenceChart({ data, viewConfig, hoverIdx, onHover, showCompetitors }: PresenceChartProps) {
  const chartData = data.map((d, i) => ({ ...d, _idx: i }));
  const gradientId = `area-grad-${viewConfig.key}`;
  const hex = COLOR_MAP[viewConfig.color] || '#5BA4C4';

  // Show top 5 non-you competitors when toggled
  const competitorLines = showCompetitors
    ? COMPETITORS.filter(c => !c.isYou).slice(0, 5)
    : [];

  const handleMouseLeave = useCallback(() => onHover(null), [onHover]);

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: '0 0 var(--radius-md) var(--radius-md)',
        background: 'var(--surface)',
        padding: 12,
      }}
    >
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart
          data={chartData}
          margin={{ top: 8, right: 8, left: 4, bottom: 0 }}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={hex} stopOpacity={0.2} />
              <stop offset="100%" stopColor={hex} stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--border)"
            strokeOpacity={0.5}
            vertical={false}
          />

          <XAxis
            dataKey="dateShort"
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            interval={Math.max(0, Math.floor(data.length / 5) - 1)}
          />

          {competitorLines.map((comp) => (
            <Line
              key={comp.domain}
              type="monotone"
              dataKey={comp.keys[viewConfig.key] as string}
              stroke="var(--text-tertiary)"
              strokeWidth={1}
              strokeDasharray="4 4"
              strokeOpacity={0.3}
              dot={false}
              isAnimationActive={false}
            />
          ))}

          <Area
            type="monotone"
            dataKey={viewConfig.dataKey as string}
            stroke={hex}
            strokeWidth={2.5}
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
            dot={false}
            activeDot={{
              r: 5,
              fill: hex,
              stroke: 'var(--surface)',
              strokeWidth: 2,
            }}
          />

          <Tooltip
            content={<HoverTracker onHover={onHover} />}
            cursor={{
              stroke: 'var(--border-strong)',
              strokeWidth: 1,
              strokeDasharray: '4 4',
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
