'use client';

import { cn } from '@/lib/utils';
import { Search, Bell, Sun, Moon } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { Avatar } from './Avatar';
import { useThemeStore } from '@/stores/theme';

const routeLabels: Record<string, string> = {
  '/': 'Home',
  '/analytics': 'Analytics',
  '/analytics/lab': 'Deep Embedding Lab',
  '/content': 'Content Studio',
  '/content/synced': 'Synced Content',
  '/planner': 'Content Planner',
  '/artifacts': 'Brand Artifacts',
  '/attribution': 'Attribution',
  '/settings': 'Settings',
};

interface TopBarProps {
  onSearchClick?: () => void;
  notificationCount?: number;
  className?: string;
}

export function TopBar({ onSearchClick, notificationCount = 0, className }: TopBarProps) {
  const pathname = usePathname();
  const { mode, toggle: toggleTheme } = useThemeStore();

  const breadcrumbs = pathname.split('/').filter(Boolean);
  const pageTitle = routeLabels[pathname] || breadcrumbs[breadcrumbs.length - 1] || 'Home';

  return (
    <header
      className={cn(
        'h-[44px] px-4 flex items-center justify-between border-b border-border bg-surface',
        className
      )}
    >
      {/* Left: Breadcrumbs */}
      <div className="flex items-center gap-1 text-[13px]">
        {breadcrumbs.length > 1 && (
          <>
            {breadcrumbs.slice(0, -1).map((crumb, i) => (
              <span key={i} className="text-text-tertiary capitalize">
                {routeLabels['/' + breadcrumbs.slice(0, i + 1).join('/')] || crumb}
                <span className="mx-1 text-text-tertiary">/</span>
              </span>
            ))}
          </>
        )}
        <span className="text-text-primary font-medium">{pageTitle}</span>
      </div>

      {/* Right: Search, Notifications, Avatar */}
      <div className="flex items-center gap-3">
        <button
          onClick={onSearchClick}
          className="h-[30px] px-3 flex items-center gap-2 rounded-sm border border-border text-[13px] text-text-tertiary hover:border-border-strong hover:text-text-secondary transition-colors cursor-pointer"
        >
          <Search size={14} strokeWidth={1.5} />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden sm:inline text-[10px] px-1 py-0.5 rounded bg-bg border border-border text-text-tertiary">
            ⌘K
          </kbd>
        </button>

        <button className="relative p-1.5 rounded-sm text-text-tertiary hover:text-text-primary hover:bg-bg transition-colors cursor-pointer">
          <Bell size={18} strokeWidth={1.5} />
          {notificationCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-[14px] h-[14px] rounded-full bg-accent text-[8px] text-text-on-accent flex items-center justify-center font-medium">
              {notificationCount > 9 ? '9+' : notificationCount}
            </span>
          )}
        </button>

        <button
          onClick={toggleTheme}
          className="p-1.5 rounded-sm text-text-tertiary hover:text-text-primary hover:bg-bg transition-colors cursor-pointer"
          title={mode === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {mode === 'light' ? <Moon size={16} strokeWidth={1.5} /> : <Sun size={16} strokeWidth={1.5} />}
        </button>

        <Avatar name="User" size="md" className="!w-[28px] !h-[28px] !text-[10px]" />
      </div>
    </header>
  );
}
