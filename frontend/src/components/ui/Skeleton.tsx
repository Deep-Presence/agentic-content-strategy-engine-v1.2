import { cn } from '@/lib/utils';

interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  className?: string;
}

export function Skeleton({ variant = 'text', width, height, className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-[shimmer_1.5s_infinite_linear]',
        'bg-[length:800px_100%]',
        variant === 'text' && 'h-3 rounded-sm',
        variant === 'circular' && 'rounded-full',
        variant === 'rectangular' && 'rounded-sm',
        className
      )}
      style={{
        width,
        height,
        backgroundImage: 'linear-gradient(90deg, var(--surface) 25%, var(--border-subtle) 50%, var(--surface) 75%)',
      }}
    />
  );
}
