import { cn } from '@/lib/utils';

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  trend?: 'up' | 'down' | 'flat';
  className?: string;
}

export function Sparkline({ data, width = 60, height = 16, trend, className }: SparklineProps) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 2) - 1;
    return `${x},${y}`;
  }).join(' ');

  const detectedTrend = trend || (data[data.length - 1] > data[0] ? 'up' : data[data.length - 1] < data[0] ? 'down' : 'flat');
  const strokeColor = detectedTrend === 'up' ? 'var(--success)' : detectedTrend === 'down' ? 'var(--error)' : 'var(--text-tertiary)';

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={cn('inline-block', className)}>
      <polyline
        points={points}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
