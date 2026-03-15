import { cn } from '@/lib/utils';

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        'h-[30px] px-2 rounded-sm border border-border bg-surface font-body text-[12px] text-text-primary',
        'outline-none transition-[border-color] duration-[120ms] ease-out',
        'hover:border-border-strong',
        'focus:border-accent focus:border-2 focus:bg-surface-raised focus:shadow-[0_0_0_3px_var(--accent-subtle)]',
        'placeholder:text-text-tertiary',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        className
      )}
      {...props}
    />
  );
}
