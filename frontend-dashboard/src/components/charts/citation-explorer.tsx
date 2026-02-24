'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { cn } from '@/lib/utils/cn';

interface PlatformBreakdownData {
  platform: string;
  totalCitations: number;
  uniqueCitations: number;
  avgSimilarity: number;
  topDomain: string;
}

interface CitationExplorerProps {
  data: PlatformBreakdownData[];
  onPlatformClick?: (platform: string) => void;
  height?: number;
  className?: string;
}

const PLATFORM_COLORS: Record<string, string> = {
  ChatGPT: '#6a9bcc',
  Claude: '#d97757',
  Perplexity: '#788c5d',
  Gemini: '#e8926d',
};

function CitationExplorer({
  data,
  onPlatformClick,
  height = 300,
  className,
}: CitationExplorerProps) {
  const chartData = data.map((d) => ({
    name: d.platform,
    total: d.totalCitations,
    unique: d.uniqueCitations,
    avgSimilarity: d.avgSimilarity,
    topDomain: d.topDomain,
  }));

  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 80, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle, #f0ede6)" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 10, fill: 'var(--text-tertiary)', fontFamily: 'ui-sans-serif, sans-serif' }}
            axisLine={{ stroke: 'var(--border-default)' }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 12, fill: 'var(--text-secondary)', fontFamily: 'ui-sans-serif, sans-serif', fontWeight: 500 }}
            axisLine={false}
            tickLine={false}
            width={75}
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
          <Bar
            dataKey="total"
            name="Total Citations"
            radius={[0, 3, 3, 0]}
            maxBarSize={24}
            onClick={(entry) => {
              if (entry && typeof entry === 'object' && 'name' in entry) {
                onPlatformClick?.(entry.name as string);
              }
            }}
            className="cursor-pointer"
          >
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={PLATFORM_COLORS[entry.name] || '#b0aea5'} />
            ))}
          </Bar>
          <Bar
            dataKey="unique"
            name="Unique Citations"
            radius={[0, 3, 3, 0]}
            maxBarSize={24}
            fillOpacity={0.5}
            onClick={(entry) => {
              if (entry && typeof entry === 'object' && 'name' in entry) {
                onPlatformClick?.(entry.name as string);
              }
            }}
            className="cursor-pointer"
          >
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={PLATFORM_COLORS[entry.name] || '#b0aea5'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export { CitationExplorer };
export type { CitationExplorerProps, PlatformBreakdownData };
