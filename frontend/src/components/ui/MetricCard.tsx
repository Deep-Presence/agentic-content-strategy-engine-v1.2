import { cn } from '@/lib/utils';

interface MetricCardProps {
  label: string;
  value: string | number;
  delta?: string;
  deltaType?: 'positive' | 'negative' | 'neutral';
  className?: string;
}

export function MetricCard({ label, value, delta, deltaType = 'neutral', className }: MetricCardProps) {
  return (
    <div className={cn('bg-surface border border-border rounded-md p-4 min-h-[80px]', className)}>
      <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary leading-[1.4]">
        {label}
      </p>
      <div className="flex items-baseline gap-2 mt-1.5">
        <p className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary">
          {value}
        </p>
        {delta && (
          <p className={cn(
            'text-[12px] font-medium',
            deltaType === 'positive' && 'text-success',
            deltaType === 'negative' && 'text-error',
            deltaType === 'neutral' && 'text-text-tertiary',
          )}>
            {delta}
          </p>
        )}
      </div>
    </div>
  );
}
