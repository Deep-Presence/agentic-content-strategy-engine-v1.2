'use client';

import { StatusDot } from '@/components/ui';
import { Database, BarChart3, Code2, Globe } from 'lucide-react';
import Link from 'next/link';

interface IntegrationStatusItem {
  name: string;
  category: string;
  icon: React.ReactNode;
  status: string;
  connected: boolean;
}

const items: IntegrationStatusItem[] = [
  { name: 'Salesforce', category: 'CRM', icon: <Database size={20} strokeWidth={1.5} />, status: 'Not Connected', connected: false },
  { name: 'HubSpot', category: 'CRM', icon: <Database size={20} strokeWidth={1.5} />, status: 'Not Connected', connected: false },
  { name: 'Google Analytics 4', category: 'Analytics', icon: <BarChart3 size={20} strokeWidth={1.5} />, status: 'Not Connected', connected: false },
  { name: 'Plausible', category: 'Analytics', icon: <BarChart3 size={20} strokeWidth={1.5} />, status: 'Not Connected', connected: false },
  { name: 'Mixpanel', category: 'Analytics', icon: <BarChart3 size={20} strokeWidth={1.5} />, status: 'Not Connected', connected: false },
  { name: 'Deep Presence Pixel', category: 'Attribution', icon: <Code2 size={20} strokeWidth={1.5} />, status: 'Not Installed', connected: false },
  { name: 'WordPress', category: 'CMS', icon: <Globe size={20} strokeWidth={1.5} />, status: 'Not Connected', connected: false },
  { name: 'Webflow', category: 'CMS', icon: <Globe size={20} strokeWidth={1.5} />, status: 'Not Connected', connected: false },
  { name: 'Ghost', category: 'CMS', icon: <Globe size={20} strokeWidth={1.5} />, status: 'Not Connected', connected: false },
];

const categories = ['CRM', 'Analytics', 'Attribution', 'CMS'];

export function IntegrationStatusCards() {
  return (
    <div className="space-y-4">
      {categories.map((cat) => {
        const catItems = items.filter((i) => i.category === cat);
        if (catItems.length === 0) return null;
        return (
          <div key={cat}>
            <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
              {cat}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {catItems.map((item) => (
                <div
                  key={item.name}
                  className="bg-surface border border-border rounded-md p-3 h-[60px] flex items-center gap-3 hover:border-border-strong transition-[border-color] duration-150"
                >
                  <span className="text-text-tertiary flex-shrink-0">{item.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[13px] font-medium text-text-primary">{item.name}</span>
                      <StatusDot color={item.connected ? 'success' : 'neutral'} />
                    </div>
                    <p className="text-[11px] text-text-tertiary truncate">{item.status}</p>
                  </div>
                  <Link
                    href="/settings?tab=integrations"
                    className="text-[12px] text-accent hover:underline flex-shrink-0"
                  >
                    Connect →
                  </Link>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
