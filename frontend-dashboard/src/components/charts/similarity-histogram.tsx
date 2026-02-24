'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { cn } from '@/lib/utils/cn';

interface HistogramBin {
  range: string;
  count: number;
}

interface SimilarityHistogramProps {
  data: HistogramBin[];
  color?: string;
  height?: number;
  className?: string;
}

function SimilarityHistogram({
  data,
  color = 'var(--color-ocean-400, #6a9bcc)',
  height = 300,
  className,
}: SimilarityHistogramProps) {
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle, #f0ede6)" />
          <XAxis
            dataKey="range"
            tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'ui-sans-serif, sans-serif' }}
            axisLine={{ stroke: 'var(--border-default)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'ui-sans-serif, sans-serif' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#ffffff',
              border: '1px solid var(--border-default)',
              borderRadius: 6,
              fontSize: 12,
              fontFamily: 'ui-sans-serif, sans-serif',
            }}
            formatter={(value) => [value, 'Citations']}
            labelFormatter={(label) => `Similarity: ${label}`}
          />
          <Bar
            dataKey="count"
            fill={color}
            radius={[3, 3, 0, 0]}
            maxBarSize={50}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export { SimilarityHistogram };
export type { SimilarityHistogramProps, HistogramBin };
