'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils/cn';
import { NAV_ITEMS } from '@/lib/utils/constants';
import {
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarSectionLabel,
} from '@/components/ui/sidebar';
import { Select } from '@/components/ui/select';
import { useAppStore } from '@/stores/app-store';

export function SidebarNav() {
  const pathname = usePathname();
  const { currentCompany, companies, setCurrentCompany } = useAppStore();

  // Group nav items by section
  const mainItem = NAV_ITEMS.filter((item) => !item.section);
  const sections = NAV_ITEMS.reduce<Record<string, typeof NAV_ITEMS>>((acc, item) => {
    if (item.section) {
      if (!acc[item.section]) acc[item.section] = [];
      acc[item.section].push(item);
    }
    return acc;
  }, {});

  return (
    <Sidebar>
      <SidebarHeader>
        <Link href="/command-center" className="flex items-center gap-2 px-1">
          <div className="h-8 w-8 rounded-md bg-terracotta-400 flex items-center justify-center">
            <span className="text-white font-serif font-semibold text-body-lg">D</span>
          </div>
          <span className="font-serif font-semibold text-heading-4 text-cream-950">
            Deep Presence
          </span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        {/* Main navigation (Command Center) */}
        {mainItem.map((item) => {
          const Icon = item.icon;
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-body-sm font-sans font-medium transition-colors',
                isActive
                  ? 'bg-cream-100 text-terracotta-400 font-semibold'
                  : 'text-cream-800 hover:bg-cream-200'
              )}
            >
              <Icon className="h-[18px] w-[18px]" />
              {item.label}
            </Link>
          );
        })}

        {/* Sections */}
        {Object.entries(sections).map(([section, items]) => (
          <div key={section}>
            <SidebarSectionLabel>{section}</SidebarSectionLabel>
            {items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-md text-body-sm font-sans font-medium transition-colors',
                    isActive
                      ? 'bg-cream-100 text-terracotta-400 font-semibold'
                      : 'text-cream-800 hover:bg-cream-200'
                  )}
                >
                  <Icon className="h-[18px] w-[18px]" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </SidebarContent>

      <SidebarFooter>
        <Select
          value={currentCompany}
          onChange={(e) => setCurrentCompany(e.target.value)}
          className="text-caption"
        >
          {companies.length === 0 && (
            <option value="">No companies</option>
          )}
          {companies.map((company) => (
            <option key={company} value={company}>
              {company.charAt(0).toUpperCase() + company.slice(1)}
            </option>
          ))}
        </Select>
      </SidebarFooter>
    </Sidebar>
  );
}
