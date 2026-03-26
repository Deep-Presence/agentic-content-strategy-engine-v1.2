'use client';

import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import {
  Home, BarChart3, FlaskConical, PenSquare, CalendarRange,
  BookOpen, TrendingUp, RefreshCw, Settings, ChevronsLeft, ChevronsRight,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';
import { useSidebarStore } from '@/stores/sidebar';
import { LocusLogo } from './LocusLogo';
import { WorkspaceSelector } from './WorkspaceSelector';

const navItems = [
  { label: 'Home', href: '/', icon: Home, exact: true },
  { label: 'Analytics', href: '/analytics', icon: BarChart3 },
  { label: 'Deep Embedding Lab', href: '/analytics/lab', icon: FlaskConical },
  { label: 'Content Studio', href: '/content', icon: PenSquare, exact: true },
  { label: 'Synced Content', href: '/content/synced', icon: RefreshCw },
  { label: 'Content Planner', href: '/planner', icon: CalendarRange },
  { label: 'Brand Artifacts', href: '/artifacts', icon: BookOpen },
  { label: 'Attribution', href: '/attribution', icon: TrendingUp },
];

export function Sidebar() {
  const { collapsed, toggle } = useSidebarStore();
  const pathname = usePathname();
  const [hovered, setHovered] = useState(false);

  // Keyboard shortcut: Cmd+B or Ctrl+B to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'b' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggle]);

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 52 : 200 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="relative h-screen bg-surface border-r border-border flex flex-col flex-shrink-0 overflow-hidden"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Collapse/expand edge trigger — appears on hover */}
      <button
        onClick={toggle}
        className={cn(
          'absolute top-1/2 -translate-y-1/2 right-0 z-10',
          'w-[16px] h-[32px] flex items-center justify-center',
          'bg-surface border border-border rounded-l-sm',
          'text-text-tertiary hover:text-text-primary',
          'transition-opacity duration-150 cursor-pointer',
          hovered ? 'opacity-100' : 'opacity-0',
        )}
      >
        {collapsed
          ? <ChevronsRight size={12} strokeWidth={1.5} />
          : <ChevronsLeft size={12} strokeWidth={1.5} />
        }
      </button>

      {/* Logo + workspace area */}
      <div className={cn(
        'p-4',
        collapsed && 'p-2 flex justify-center',
      )}>
        {collapsed
          ? <LocusLogo variant="symbol" size={24} />
          : (
            <div className="space-y-2">
              <LocusLogo variant="compact" size={24} animated />
              <WorkspaceSelector />
            </div>
          )
        }
      </div>

      {/* Separator */}
      <div className={cn('border-t border-border', collapsed ? 'mx-2 my-2' : 'mx-3 my-2')} />

      {/* Nav */}
      <nav className={cn('flex-1 space-y-1', collapsed ? 'px-1' : 'px-2')}>
        {navItems.map((item) => {
          const isActive = item.exact
            ? pathname === item.href
            : pathname === item.href || pathname.startsWith(item.href + '/');
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center rounded-sm transition-colors duration-100',
                collapsed
                  ? 'justify-center h-[34px] w-full'
                  : 'gap-[8px] h-[34px] px-3 text-[13px] font-medium',
                isActive
                  ? 'bg-accent-subtle text-accent'
                  : 'text-text-secondary hover:bg-bg hover:text-text-primary'
              )}
            >
              <Icon size={collapsed ? 18 : 16} strokeWidth={1.5} className="flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Bottom separator + Settings */}
      <div className={cn('border-t border-border', collapsed ? 'mx-2 my-2' : 'mx-3 my-2')} />
      <div className={cn('pb-3', collapsed ? 'px-1' : 'px-2')}>
        <Link
          href="/settings"
          className={cn(
            'flex items-center rounded-sm transition-colors duration-100',
            collapsed
              ? 'justify-center h-[34px] w-full'
              : 'gap-[8px] h-[34px] px-3 text-[13px] font-medium',
            pathname === '/settings'
              ? 'bg-accent-subtle text-accent'
              : 'text-text-secondary hover:bg-bg hover:text-text-primary'
          )}
        >
          <Settings size={collapsed ? 18 : 16} strokeWidth={1.5} className="flex-shrink-0" />
          {!collapsed && <span>Settings</span>}
        </Link>
      </div>
    </motion.aside>
  );
}
