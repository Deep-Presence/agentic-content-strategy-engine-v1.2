'use client';

import { cn } from '@/lib/utils';

interface FilterOption {
  value: string;
  label: string;
}

interface Filter {
  key: string;
  label: string;
  options: FilterOption[];
  value: string;
}

interface FilterBarProps {
  filters: Filter[];
  onChange: (key: string, value: string) => void;
  className?: string;
}

export function FilterBar({ filters, onChange, className }: FilterBarProps) {
  return (
    <div className={cn('flex items-center gap-3 flex-wrap', className)}>
      {filters.map((filter) => (
        <div key={filter.key} className="flex items-center gap-1.5">
          <label className="text-[12px] font-medium text-text-tertiary">
            {filter.label}
          </label>
          <select
            value={filter.value}
            onChange={(e) => onChange(filter.key, e.target.value)}
            className="h-[32px] px-2.5 rounded-sm border border-border bg-surface text-[13px] text-text-primary outline-none cursor-pointer hover:border-border-strong transition-colors"
          >
            {filter.options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}
