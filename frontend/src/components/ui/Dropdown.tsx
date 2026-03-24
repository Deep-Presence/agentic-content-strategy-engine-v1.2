'use client';

import { cn } from '@/lib/utils';
import { useEffect, useRef, useState } from 'react';

interface DropdownProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

export function Dropdown({ trigger, children, align = 'left', className }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative inline-block">
      <div onClick={() => setOpen(!open)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute z-40 mt-1 py-1 min-w-[160px]',
            'bg-surface-raised border border-border rounded-md shadow-float',
            align === 'right' ? 'right-0' : 'left-0',
            className
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}

interface DropdownItemProps {
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function DropdownItem({ onClick, children, className }: DropdownItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left px-3 py-[5px] text-[12px] text-text-primary',
        'hover:bg-accent-subtle transition-colors cursor-pointer',
        className
      )}
    >
      {children}
    </button>
  );
}
