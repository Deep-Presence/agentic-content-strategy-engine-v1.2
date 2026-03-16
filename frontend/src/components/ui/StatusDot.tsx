import { cn } from '@/lib/utils';

interface StatusDotProps {
  color?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  className?: string;
}

export function StatusDot({ color = 'neutral', className }: StatusDotProps) {
  return (
    <span
      className={cn(
        'inline-block w-2 h-2 rounded-full',
        color === 'success' && 'bg-success',
        color === 'warning' && 'bg-warning',
        color === 'error' && 'bg-error',
        color === 'info' && 'bg-accent',
        color === 'neutral' && 'bg-text-tertiary',
        className
      )}
    />
  );
}
