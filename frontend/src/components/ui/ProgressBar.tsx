import { cn } from '@/lib/utils';

interface ProgressBarProps {
  value: number;
  max?: number;
  className?: string;
}

export function ProgressBar({ value, max = 100, className }: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={cn('w-full h-[6px] bg-surface rounded-[3px] overflow-hidden', className)}>
      <div
        className="h-full bg-accent rounded-[3px] transition-[width] duration-600 ease-[cubic-bezier(0.16,1,0.3,1)]"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
