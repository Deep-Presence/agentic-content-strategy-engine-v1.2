'use client';

import { usePathname } from 'next/navigation';
import { Search, Bell } from 'lucide-react';
import { Avatar } from '@/components/ui/avatar';
import { DropdownMenu, DropdownItem, DropdownSeparator } from '@/components/ui/dropdown-menu';
import { NAV_ITEMS } from '@/lib/utils/constants';

export function TopBar() {
  const pathname = usePathname();

  const currentPage = NAV_ITEMS.find((item) => pathname.startsWith(item.href));
  const pageTitle = currentPage?.label || 'Dashboard';

  return (
    <header className="h-14 border-b border-[var(--border-default)] bg-white flex items-center justify-between px-6">
      <div className="flex items-center gap-2">
        <h1 className="font-sans text-body font-medium text-cream-800">
          {pageTitle}
        </h1>
      </div>

      <div className="flex items-center gap-3">
        {/* Search placeholder */}
        <button className="flex items-center gap-2 px-3 py-1.5 bg-cream-200 rounded-md text-body-sm text-cream-600 hover:bg-cream-300 transition-colors font-sans">
          <Search className="h-4 w-4" />
          <span>Search...</span>
          <kbd className="text-micro bg-cream-300 px-1.5 py-0.5 rounded ml-4">
            /
          </kbd>
        </button>

        {/* Notifications */}
        <button className="p-2 text-cream-600 hover:text-cream-900 hover:bg-cream-200 rounded-md transition-colors relative">
          <Bell className="h-4.5 w-4.5" />
        </button>

        {/* User avatar */}
        <DropdownMenu
          align="right"
          trigger={
            <button className="cursor-pointer">
              <Avatar fallback="User" size="sm" />
            </button>
          }
        >
          <div className="px-3 py-2">
            <p className="text-body-sm font-sans font-medium text-cream-900">
              User
            </p>
            <p className="text-caption text-cream-600">user@example.com</p>
          </div>
          <DropdownSeparator />
          <DropdownItem>Settings</DropdownItem>
          <DropdownSeparator />
          <DropdownItem destructive>Sign out</DropdownItem>
        </DropdownMenu>
      </div>
    </header>
  );
}
