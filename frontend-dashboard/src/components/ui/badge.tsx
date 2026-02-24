import { type HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils/cn';

const badgeVariants = cva(
  'inline-flex items-center px-2 py-0.5 rounded text-caption font-sans font-medium',
  {
    variants: {
      variant: {
        default: 'bg-cream-300 text-cream-800',
        terracotta: 'bg-terracotta-50 text-terracotta-500 border border-terracotta-200',
        blue: 'bg-ocean-50 text-ocean-500 border border-ocean-200',
        green: 'bg-sage-50 text-sage-500 border border-sage-200',
        warning: 'bg-warning/10 text-warning',
        error: 'bg-error/10 text-error',
        success: 'bg-sage-50 text-sage-500',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant, className }))} {...props} />
  );
}

export { Badge, badgeVariants };
export type { BadgeProps };
