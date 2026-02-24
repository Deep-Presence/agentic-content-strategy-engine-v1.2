import { forwardRef, type SelectHTMLAttributes } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, id, children, value, onChange, ...props }, ref) => {
    // Avoid React warning: use defaultValue when no onChange is provided
    const valueProps = onChange
      ? { value, onChange }
      : value !== undefined
      ? { defaultValue: value }
      : {};
    const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-body-sm font-sans font-medium text-cream-800"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <select
            id={selectId}
            ref={ref}
            className={cn(
              'w-full appearance-none bg-white border border-[var(--border-default)] rounded-[6px] px-3 py-2 pr-8',
              'font-sans text-body text-cream-950',
              'focus:outline-none focus:border-terracotta-400 focus:ring-2 focus:ring-terracotta-400/20',
              'disabled:bg-cream-200 disabled:text-cream-600 disabled:cursor-not-allowed',
              'transition-colors duration-150',
              error && 'border-error focus:border-error focus:ring-error/20',
              className
            )}
            {...props}
            {...valueProps}
          >
            {children}
          </select>
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-cream-600 pointer-events-none" />
        </div>
        {error && (
          <p className="text-caption text-error font-sans">{error}</p>
        )}
      </div>
    );
  }
);
Select.displayName = 'Select';

export { Select };
export type { SelectProps };
