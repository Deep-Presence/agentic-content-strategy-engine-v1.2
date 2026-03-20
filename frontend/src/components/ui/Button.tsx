import { cn } from '@/lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive';
  size?: 'sm' | 'default' | 'lg';
}

export function Button({ variant = 'primary', size = 'default', className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-body font-medium transition-all',
        'duration-[120ms] ease-out cursor-pointer',
        size === 'sm' && 'h-[26px] px-2 text-[11px]',
        size === 'default' && 'h-[30px] px-3 text-[12px]',
        size === 'lg' && 'h-[34px] px-4 text-[13px]',
        variant === 'primary' && 'bg-accent text-text-on-accent rounded-sm hover:bg-accent-hover',
        variant === 'secondary' && 'bg-transparent text-text-primary border border-border rounded-sm hover:border-border-strong hover:bg-surface',
        variant === 'ghost' && 'bg-transparent text-text-secondary rounded-sm hover:bg-surface hover:text-text-primary',
        variant === 'destructive' && 'bg-error text-white rounded-sm',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
