'use client';

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { cn } from '@/lib/utils/cn';

interface ClusterMetrics {
  headers: number;
  lists: number;
  stats: number;
  citations: number;
  faq: number;
  tables: number;
  key_takeaways: number;
}

interface ClusterRadarData {
  name: string;
  color: string;
  metrics: ClusterMetrics;
}

interface ClusterRadarProps {
  clusters: ClusterRadarData[];
  size?: number;
  className?: string;
}

const AXIS_LABELS: Record<keyof ClusterMetrics, string> = {
  headers: 'Headers',
  lists: 'Lists',
  stats: 'Stats',
  citations: 'Citations',
  faq: 'FAQ',
  tables: 'Tables',
  key_takeaways: 'Takeaways',
};

function ClusterRadar({ clusters, size = 400, className }: ClusterRadarProps) {
  const axes = Object.keys(AXIS_LABELS) as (keyof ClusterMetrics)[];

  const chartData = axes.map((axis) => {
    const entry: Record<string, string | number> = { axis: AXIS_LABELS[axis] };
    clusters.forEach((cluster) => {
      entry[cluster.name] = Math.round(cluster.metrics[axis] * 100);
    });
    return entry;
  });

  return (
    <div className={cn('w-full', className)} style={{ height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid stroke="var(--border-default)" />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fontSize: 11, fill: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }}
            tickFormatter={(v: number) => `${v}%`}
          />
          {clusters.map((cluster) => (
            <Radar
              key={cluster.name}
              name={cluster.name}
              dataKey={cluster.name}
              stroke={cluster.color}
              fill={cluster.color}
              fillOpacity={0.1}
              strokeWidth={2}
            />
          ))}
          <Legend
            wrapperStyle={{ fontSize: 12, fontFamily: 'var(--font-sans)' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#ffffff',
              border: '1px solid var(--border-default)',
              borderRadius: 6,
              fontSize: 12,
              fontFamily: 'var(--font-sans)',
            }}
            formatter={(value) => `${value}%`}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

export { ClusterRadar };
export type { ClusterRadarProps, ClusterRadarData, ClusterMetrics };
