'use client';

import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { Settings, ChevronsLeft, ChevronsRight } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';
import { useSidebarStore } from '@/stores/sidebar';
import { WorkspaceSelector } from './WorkspaceSelector';
import { Avatar } from './Avatar';

interface NavSection {
  header?: string;
  items: { label: string; href: string }[];
}

const navSections: NavSection[] = [
  {
    items: [
      { label: 'Brand Presence', href: '/' },
    ],
  },
  {
    header: 'Intelligence',
    items: [
      { label: 'Citation intelligence', href: '/analytics' },
      { label: 'Competitive position', href: '/competitive-position' },
      { label: 'Prompt tracking', href: '/prompt-tracking' },
    ],
  },
  {
    header: 'Signals',
    items: [
      { label: 'Content performance', href: '/content-performance' },
      { label: 'Technical readiness', href: '/technical-readiness' },
      { label: 'Embedding lab', href: '/embedding-lab' },
    ],
  },
  {
    header: 'Content',
    items: [
      { label: 'Content planner', href: '/planner' },
      { label: 'Content studio', href: '/content-studio' },
    ],
  },
  {
    header: 'Knowledge',
    items: [
      { label: 'Brand artifact', href: '/artifacts' },
    ],
  },
];

const allNavHrefs = navSections.flatMap(s => s.items.map(i => i.href));

function isNavActive(href: string, pathname: string): boolean {
  if (href === '/') return pathname === '/';
  const matches = pathname === href || pathname.startsWith(href + '/');
  if (!matches) return false;
  // Don't activate if a more specific sibling route also matches
  return !allNavHrefs.some(other =>
    other !== href &&
    other.startsWith(href) &&
    (pathname === other || pathname.startsWith(other + '/'))
  );
}

export function Sidebar() {
  const { collapsed, toggle } = useSidebarStore();
  const pathname = usePathname();
  const [hovered, setHovered] = useState(false);

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
      {/* Collapse/expand edge trigger */}
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

      {/* Logo */}
      <div className={cn(
        'flex items-center gap-2',
        collapsed ? 'justify-center px-2 pt-3 pb-1' : 'px-4 pt-4 pb-2'
      )}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="flex-shrink-0">
          <rect width="24" height="24" rx="6" fill="var(--accent)" />
          <text x="12" y="16" textAnchor="middle" fill="#fff" fontSize="11" fontWeight="700" fontFamily="JetBrains Mono, monospace">DP</text>
        </svg>
        {!collapsed && (
          <span
            className="text-[14px] font-semibold"
            style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
          >
            Deep Presence
          </span>
        )}
      </div>

      {/* Workspace selector */}
      <div className={cn(collapsed ? 'px-2 pb-2' : 'px-3 pb-3')}>
        <WorkspaceSelector collapsed={collapsed} />
      </div>

      {/* Separator */}
      <div className={cn('border-t border-border', collapsed ? 'mx-2' : 'mx-3')} />

      {/* Nav */}
      <nav className={cn(
        'flex-1 overflow-y-auto pt-2',
        collapsed ? 'px-1' : 'px-2',
      )}>
        {navSections.map((section, sIdx) => (
          <div key={sIdx} className={cn(sIdx === 0 ? 'mt-2' : 'mt-4')}>
            {section.header && !collapsed && (
              <div className="px-2 mb-1 text-[10px] font-medium uppercase tracking-[0.06em] text-accent">
                {section.header}
              </div>
            )}
            {collapsed && section.header && (
              <div className="border-t border-border mx-1 my-2" />
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = isNavActive(item.href, pathname);
                const isPrimary = item.href === '/' && !section.header;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'flex items-center rounded-sm transition-colors duration-100',
                      collapsed
                        ? 'justify-center h-[30px] w-full text-[10px] font-medium'
                        : isPrimary ? 'h-[34px] px-2 text-[13px] font-medium' : 'h-[30px] px-2 text-[13px]',
                      active
                        ? 'bg-accent-subtle text-accent font-medium'
                        : isPrimary
                          ? 'text-text-primary hover:bg-bg'
                          : 'text-text-secondary hover:bg-bg hover:text-text-primary'
                    )}
                    title={collapsed ? item.label : undefined}
                  >
                    {collapsed
                      ? <span>{item.label.charAt(0)}</span>
                      : <span>{item.label}</span>
                    }
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom: Settings + User */}
      <div className={cn('border-t border-border', collapsed ? 'px-1 py-2' : 'px-2 py-2')}>
        <Link
          href="/settings"
          className={cn(
            'flex items-center rounded-sm transition-colors duration-100',
            collapsed
              ? 'justify-center h-[30px] w-full'
              : 'h-[30px] px-2 text-[13px]',
            pathname === '/settings'
              ? 'bg-accent-subtle text-accent font-medium'
              : 'text-text-secondary hover:bg-bg hover:text-text-primary'
          )}
          title={collapsed ? 'Settings' : undefined}
        >
          {collapsed
            ? <Settings size={16} strokeWidth={1.5} />
            : <span>Settings</span>
          }
        </Link>

        {!collapsed && (
          <div className="flex items-center gap-2 mt-2 px-2 py-1">
            <Avatar name="Shank Keshri" size="sm" />
            <span className="text-[12px] text-text-secondary truncate">shank keshri</span>
          </div>
        )}
        {collapsed && (
          <div className="flex justify-center mt-1">
            <Avatar name="Shank Keshri" size="sm" />
          </div>
        )}
      </div>
    </motion.aside>
  );
}
