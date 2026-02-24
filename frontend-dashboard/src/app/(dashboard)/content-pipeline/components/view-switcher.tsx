'use client';

import { LayoutGrid, Table2, Calendar, IterationCw, GanttChart } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { useContentStore } from '@/stores/content-store';

const VIEWS = [
  { key: 'board' as const, label: 'Board', icon: LayoutGrid },
  { key: 'table' as const, label: 'Table', icon: Table2 },
  { key: 'calendar' as const, label: 'Calendar', icon: Calendar },
  { key: 'cycles' as const, label: 'Cycles', icon: IterationCw },
  { key: 'roadmap' as const, label: 'Roadmap', icon: GanttChart },
] as const;

interface ViewSwitcherProps {
  className?: string;
}

export function ViewSwitcher({ className }: ViewSwitcherProps) {
  const { activeView, setActiveView } = useContentStore();

  return (
    <div className={cn('flex border-b border-[var(--border-default)]', className)}>
      {VIEWS.map(({ key, label, icon: Icon }) => {
        const isActive = activeView === key;
        return (
          <button
            key={key}
            onClick={() => setActiveView(key)}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2.5 text-body-sm font-sans font-medium transition-colors relative',
              isActive
                ? 'text-sage-400'
                : 'text-cream-700 hover:text-cream-900'
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
            {isActive && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-sage-400" />
            )}
          </button>
        );
      })}
    </div>
  );
}
