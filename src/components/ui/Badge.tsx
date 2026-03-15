import { cn } from '@/lib/utils';

interface BadgeProps {
  variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = 'neutral', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-[3px] h-[22px] px-2 rounded-full text-[11px] font-medium',
        variant === 'success' && 'bg-success-subtle text-success',
        variant === 'warning' && 'bg-warning-subtle text-warning',
        variant === 'error' && 'bg-error-subtle text-error',
        variant === 'info' && 'bg-info-subtle text-info',
        variant === 'neutral' && 'bg-surface text-text-secondary',
        className
      )}
    >
      {children}
    </span>
  );
}
