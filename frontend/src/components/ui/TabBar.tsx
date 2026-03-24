'use client';

import { cn } from '@/lib/utils';
import { X } from 'lucide-react';

interface Tab {
  id: string;
  label: string;
  closable?: boolean;
}

interface TabBarProps {
  tabs: Tab[];
  activeTab: string;
  onTabClick: (id: string) => void;
  onTabClose?: (id: string) => void;
  className?: string;
}

export function TabBar({ tabs, activeTab, onTabClick, onTabClose, className }: TabBarProps) {
  return (
    <div className={cn('flex items-center gap-0 border-b border-border overflow-x-auto', className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabClick(tab.id)}
          className={cn(
            'flex items-center gap-1.5 px-4 h-[36px] text-[13px] font-medium transition-colors whitespace-nowrap cursor-pointer',
            'border-b-2 -mb-[1px]',
            activeTab === tab.id
              ? 'border-accent text-accent'
              : 'border-transparent text-text-secondary hover:text-text-primary'
          )}
        >
          <span>{tab.label}</span>
          {tab.closable && onTabClose && (
            <span
              onClick={(e) => { e.stopPropagation(); onTabClose(tab.id); }}
              className="p-0.5 rounded-sm hover:bg-surface text-text-tertiary hover:text-text-primary"
            >
              <X size={11} strokeWidth={1.5} />
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
