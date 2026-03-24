'use client';

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { donutData, totalRevenue, platformColorHex } from './data';
import type { Platform } from '@/types';

export function RevenueDonutChart() {
  return (
    <div className="bg-surface border border-border rounded-md p-[14px]">
      <h3 className="text-[18px] font-semibold text-text-primary mb-3">
        Revenue by Platform
      </h3>
      <div className="relative">
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie
              data={donutData}
              cx="50%"
              cy="50%"
              innerRadius={70}
              outerRadius={110}
              paddingAngle={2}
              dataKey="value"
              strokeWidth={0}
            >
              {donutData.map((entry) => (
                <Cell key={entry.platform} fill={platformColorHex[entry.platform as Platform]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value) => [`$${Number(value).toLocaleString()}`, 'Revenue']}
              contentStyle={{
                background: 'var(--surface-raised)',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                fontSize: '12px',
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        {/* Center label */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            <div className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary">
              ${(totalRevenue / 1000).toFixed(1)}K
            </div>
            <div className="text-[11px] text-text-tertiary uppercase tracking-[0.06em]">Total</div>
          </div>
        </div>
      </div>
      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 justify-center">
        {donutData.map((entry) => (
          <div key={entry.platform} className="flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: platformColorHex[entry.platform as Platform] }}
            />
            <span className="text-[11px] text-text-secondary">{entry.name}</span>
            <span className="text-[11px] text-text-primary font-medium">
              ${(entry.value / 1000).toFixed(1)}K
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
