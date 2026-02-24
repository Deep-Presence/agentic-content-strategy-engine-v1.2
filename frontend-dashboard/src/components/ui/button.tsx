import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 font-sans font-medium transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]',
  {
    variants: {
      variant: {
        primary: 'bg-terracotta-400 text-white hover:bg-terracotta-500 shadow-sm',
        secondary: 'bg-white border border-cream-400 text-cream-900 hover:bg-cream-200',
        ghost: 'bg-transparent text-cream-700 hover:bg-cream-200',
        danger: 'bg-error/10 text-error hover:bg-error/20',
      },
      size: {
        sm: 'px-3 py-1.5 text-body-sm rounded-md',
        md: 'px-4 py-2 text-body rounded-md',
        lg: 'px-5 py-2.5 text-body-lg rounded-md',
        icon: 'h-9 w-9 rounded-md',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
export type { ButtonProps };
