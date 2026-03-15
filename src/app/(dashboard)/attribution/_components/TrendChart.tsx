'use client';

import {
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { trendData, platformColorHex } from './data';

export function TrendChart() {
  return (
    <div className="bg-surface border border-border rounded-md p-[14px]">
      <h3 className="text-[18px] font-semibold text-text-primary mb-3">
        Attribution Trend
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={trendData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--surface-raised)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              fontSize: '12px',
            }}
            formatter={(value, name) => [`$${Number(value).toLocaleString()}`, name]}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
          />
          <Area
            type="monotone"
            dataKey="chatgpt"
            name="ChatGPT"
            stackId="1"
            fill={platformColorHex.chatgpt}
            fillOpacity={0.7}
            stroke={platformColorHex.chatgpt}
            strokeWidth={1}
          />
          <Area
            type="monotone"
            dataKey="perplexity"
            name="Perplexity"
            stackId="1"
            fill={platformColorHex.perplexity}
            fillOpacity={0.7}
            stroke={platformColorHex.perplexity}
            strokeWidth={1}
          />
          <Area
            type="monotone"
            dataKey="claude"
            name="Claude"
            stackId="1"
            fill={platformColorHex.claude}
            fillOpacity={0.7}
            stroke={platformColorHex.claude}
            strokeWidth={1}
          />
          <Area
            type="monotone"
            dataKey="google_ai_overview"
            name="Google AI Overview"
            stackId="1"
            fill={platformColorHex.google_ai_overview}
            fillOpacity={0.7}
            stroke={platformColorHex.google_ai_overview}
            strokeWidth={1}
          />
          <Area
            type="monotone"
            dataKey="gemini"
            name="Gemini"
            stackId="1"
            fill={platformColorHex.gemini}
            fillOpacity={0.7}
            stroke={platformColorHex.gemini}
            strokeWidth={1}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
