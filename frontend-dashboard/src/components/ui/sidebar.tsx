'use client';

import { type ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

interface SidebarProps {
  children: ReactNode;
  className?: string;
}

function Sidebar({ children, className }: SidebarProps) {
  return (
    <aside
      className={cn(
        'w-60 h-screen bg-[var(--bg-tertiary)] border-r border-[var(--border-default)] flex flex-col shrink-0',
        className
      )}
    >
      {children}
    </aside>
  );
}

interface SidebarHeaderProps {
  children: ReactNode;
  className?: string;
}

function SidebarHeader({ children, className }: SidebarHeaderProps) {
  return (
    <div className={cn('p-4 pb-2', className)}>
      {children}
    </div>
  );
}

interface SidebarContentProps {
  children: ReactNode;
  className?: string;
}

function SidebarContent({ children, className }: SidebarContentProps) {
  return (
    <nav className={cn('flex-1 overflow-y-auto px-2 py-2', className)}>
      {children}
    </nav>
  );
}

interface SidebarFooterProps {
  children: ReactNode;
  className?: string;
}

function SidebarFooter({ children, className }: SidebarFooterProps) {
  return (
    <div className={cn('p-3 border-t border-[var(--border-default)]', className)}>
      {children}
    </div>
  );
}

interface SidebarSectionLabelProps {
  children: ReactNode;
  className?: string;
}

function SidebarSectionLabel({ children, className }: SidebarSectionLabelProps) {
  return (
    <div
      className={cn(
        'text-micro uppercase tracking-[1.5px] text-cream-600 font-sans font-medium px-3 pt-4 pb-1.5',
        className
      )}
    >
      {children}
    </div>
  );
}

export { Sidebar, SidebarHeader, SidebarContent, SidebarFooter, SidebarSectionLabel };
export type { SidebarProps };
