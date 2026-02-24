'use client';

import { useState, useRef, useEffect, type ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

interface DropdownMenuProps {
  trigger: ReactNode;
  children: ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

function DropdownMenu({ trigger, children, align = 'left', className }: DropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={ref} className={cn('relative', className)}>
      <div onClick={() => setOpen(!open)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute z-50 mt-1 min-w-[180px] bg-white border border-[var(--border-default)] rounded-md shadow-lg py-1',
            align === 'right' ? 'right-0' : 'left-0'
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
  children: ReactNode;
  className?: string;
  destructive?: boolean;
}

function DropdownItem({ onClick, children, className, destructive }: DropdownItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left px-3 py-2 text-body-sm font-sans transition-colors',
        destructive
          ? 'text-error hover:bg-error/10'
          : 'text-cream-800 hover:bg-cream-200',
        className
      )}
    >
      {children}
    </button>
  );
}

function DropdownSeparator() {
  return <div className="h-px my-1 bg-[var(--border-subtle)]" />;
}

export { DropdownMenu, DropdownItem, DropdownSeparator };
export type { DropdownMenuProps, DropdownItemProps };
