import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/cn';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-body-sm font-sans font-medium text-cream-800"
          >
            {label}
          </label>
        )}
        <input
          id={inputId}
          ref={ref}
          className={cn(
            'w-full bg-white border border-[var(--border-default)] rounded-[6px] px-3 py-2',
            'font-body text-body text-cream-950 placeholder:text-cream-600',
            'focus:outline-none focus:border-terracotta-400 focus:ring-2 focus:ring-terracotta-400/20',
            'disabled:bg-cream-200 disabled:text-cream-600 disabled:cursor-not-allowed',
            'transition-colors duration-150',
            error && 'border-error focus:border-error focus:ring-error/20',
            className
          )}
          {...props}
        />
        {error && (
          <p className="text-caption text-error font-sans">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = 'Input';

export { Input };
export type { InputProps };
