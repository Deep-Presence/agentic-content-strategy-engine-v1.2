'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { cn } from '@/lib/utils/cn';

interface ClusterComparison {
  cluster: string;
  clusterId: string;
  companySimilarity: number;
  citationSimilarity: number;
}

interface ClusterBoxplotProps {
  data: ClusterComparison[];
  height?: number;
  className?: string;
}

function ClusterBoxplot({ data, height = 350, className }: ClusterBoxplotProps) {
  const chartData = data.map((d) => ({
    name: d.cluster.length > 14 ? d.cluster.slice(0, 14) + '...' : d.cluster,
    fullName: d.cluster,
    'Company Similarity': parseFloat(d.companySimilarity.toFixed(2)),
    'Citation Similarity': parseFloat(d.citationSimilarity.toFixed(2)),
  }));

  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle, #f0ede6)" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'ui-sans-serif, sans-serif' }}
            axisLine={{ stroke: 'var(--border-default)' }}
            tickLine={false}
            interval={0}
            angle={-20}
            textAnchor="end"
            height={50}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'ui-sans-serif, sans-serif' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => v.toFixed(1)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#ffffff',
              border: '1px solid var(--border-default)',
              borderRadius: 6,
              fontSize: 12,
              fontFamily: 'ui-sans-serif, sans-serif',
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, fontFamily: 'ui-sans-serif, sans-serif' }}
          />
          <Bar dataKey="Company Similarity" fill="#788c5d" radius={[3, 3, 0, 0]} maxBarSize={30} />
          <Bar dataKey="Citation Similarity" fill="#6a9bcc" radius={[3, 3, 0, 0]} maxBarSize={30} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export { ClusterBoxplot };
export type { ClusterBoxplotProps, ClusterComparison };
