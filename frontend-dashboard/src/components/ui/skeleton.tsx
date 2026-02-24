import { cn } from '@/lib/utils/cn';

interface SkeletonProps {
  className?: string;
}

function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn('animate-pulse bg-cream-300 rounded', className)}
    />
  );
}

export { Skeleton };
export type { SkeletonProps };
