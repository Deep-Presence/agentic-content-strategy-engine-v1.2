'use client';

import { cn } from '@/lib/utils';

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  className?: string;
}

export function Toggle({ checked, onChange, className }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative w-[36px] h-[20px] rounded-[10px] transition-colors duration-200 cursor-pointer',
        checked ? 'bg-accent' : 'bg-border',
        className
      )}
    >
      <span
        className={cn(
          'absolute top-[2px] left-[2px] w-[16px] h-[16px] rounded-full bg-white',
          'shadow-[0_1px_3px_rgba(0,0,0,0.15)] transition-transform duration-200',
          'ease-[cubic-bezier(0.16,1,0.3,1)]',
          checked && 'translate-x-[16px]'
        )}
      />
    </button>
  );
}
