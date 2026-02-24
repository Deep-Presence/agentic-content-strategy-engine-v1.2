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
  ReferenceLine,
} from 'recharts';
import { cn } from '@/lib/utils/cn';

interface ComparisonDataPoint {
  cluster: string;
  clusterId: string;
  companySimilarity: number;
  citationSimilarity: number;
}

interface CompanyVsCitationProps {
  data: ComparisonDataPoint[];
  height?: number;
  className?: string;
}

function CompanyVsCitation({ data, height = 350, className }: CompanyVsCitationProps) {
  const chartData = data.map((d) => ({
    name: d.cluster.length > 12 ? d.cluster.slice(0, 12) + '...' : d.cluster,
    fullName: d.cluster,
    gap: parseFloat((d.citationSimilarity - d.companySimilarity).toFixed(3)),
    company: parseFloat(d.companySimilarity.toFixed(3)),
    citation: parseFloat(d.citationSimilarity.toFixed(3)),
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
            domain={[-0.3, 0.3]}
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
            formatter={(value) => {
              const num = typeof value === 'number' ? value : 0;
              return num.toFixed(3);
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12, fontFamily: 'ui-sans-serif, sans-serif' }} />
          <ReferenceLine y={0} stroke="var(--border-strong, #d4d1c7)" strokeWidth={1} />
          <Bar
            dataKey="gap"
            name="Gap (Citation - Company)"
            radius={[3, 3, 0, 0]}
            maxBarSize={40}
            fill="#d97757"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export { CompanyVsCitation };
export type { CompanyVsCitationProps, ComparisonDataPoint };
