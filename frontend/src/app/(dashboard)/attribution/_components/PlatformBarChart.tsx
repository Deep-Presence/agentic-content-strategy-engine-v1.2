'use client';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { platformData, platformLabels, platformColorHex } from './data';
import type { Platform } from '@/types';

export function PlatformBarChart() {
  const data = (Object.keys(platformData) as Platform[])
    .map((p) => ({
      name: platformLabels[p],
      revenue: platformData[p].revenue,
      platform: p,
    }))
    .sort((a, b) => b.revenue - a.revenue);

  return (
    <div className="bg-surface border border-border rounded-md p-[14px]">
      <h3 className="text-[18px] font-semibold text-text-primary mb-3">
        Platform Revenue
      </h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={120}
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value) => [`$${Number(value).toLocaleString()}`, 'Revenue']}
            contentStyle={{
              background: 'var(--surface-raised)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              fontSize: '12px',
            }}
          />
          <Bar dataKey="revenue" radius={[0, 3, 3, 0]} barSize={24}>
            {data.map((entry) => (
              <Cell key={entry.platform} fill={platformColorHex[entry.platform]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
