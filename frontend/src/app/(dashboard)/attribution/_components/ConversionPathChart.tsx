'use client';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { conversionPathData } from './data';

export function ConversionPathChart() {
  return (
    <div className="bg-surface border border-border rounded-md p-[14px]">
      <h3 className="text-[18px] font-semibold text-text-primary mb-3">
        Conversion Path
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={conversionPathData} margin={{ left: 10, right: 20, top: 5, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            interval={0}
            angle={-20}
            textAnchor="end"
            height={50}
          />
          <YAxis
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value) => [Number(value).toLocaleString(), 'Volume']}
            contentStyle={{
              background: 'var(--surface-raised)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              fontSize: '12px',
            }}
          />
          <Bar dataKey="value" radius={[3, 3, 0, 0]} barSize={40}>
            {conversionPathData.map((entry, index) => {
              const opacity = 1 - (index / conversionPathData.length) * 0.6;
              return <Cell key={entry.name} fill="var(--accent)" fillOpacity={opacity} />;
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
