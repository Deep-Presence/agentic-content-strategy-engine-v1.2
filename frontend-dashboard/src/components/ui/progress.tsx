import { forwardRef, type HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils/cn';

const progressVariants = cva('h-2 rounded-full transition-all duration-500 ease-out', {
  variants: {
    color: {
      terracotta: 'bg-terracotta-400',
      ocean: 'bg-ocean-400',
      sage: 'bg-sage-400',
      warning: 'bg-warning',
      error: 'bg-error',
    },
  },
  defaultVariants: {
    color: 'terracotta',
  },
});

interface ProgressProps
  extends Omit<HTMLAttributes<HTMLDivElement>, 'color'>,
    VariantProps<typeof progressVariants> {
  value: number;
  max?: number;
  animated?: boolean;
}

const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, max = 100, color, animated = true, ...props }, ref) => {
    const percentage = Math.min(100, Math.max(0, (value / max) * 100));

    return (
      <div
        ref={ref}
        className={cn('w-full h-2 bg-cream-300 rounded-full overflow-hidden', className)}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        {...props}
      >
        <div
          className={cn(
            progressVariants({ color }),
            animated && 'transition-[width] duration-500'
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    );
  }
);
Progress.displayName = 'Progress';

export { Progress, progressVariants };
export type { ProgressProps };
