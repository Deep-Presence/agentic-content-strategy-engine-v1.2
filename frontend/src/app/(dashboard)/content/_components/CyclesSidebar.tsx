'use client';

import { cn } from '@/lib/utils';
import { StatusDot, Badge } from '@/components/ui';
import { ChevronDown, ChevronRight, Clock } from 'lucide-react';
import { useState } from 'react';
import type { ExtendedBrief, StageId } from './content-data';

const stageToColor: Record<StageId | 'published', 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  triage: 'neutral',
  brief: 'info',
  generating: 'warning',
  review: 'error',
  approved: 'success',
  published: 'success',
};

interface CyclesSidebarProps {
  items: ExtendedBrief[];
  selectedBriefId: string | null;
  onSelectBrief: (id: string) => void;
}

export function CyclesSidebar({ items, selectedBriefId, onSelectBrief }: CyclesSidebarProps) {
  const [currentExpanded, setCurrentExpanded] = useState(true);
  const [historyExpanded, setHistoryExpanded] = useState(false);

  const currentItems = items.filter((b) => b.stage !== 'approved');
  const historyItems = items.filter((b) => b.stage === 'approved');

  return (
    <div className="border-r border-border w-[220px] min-w-[220px] overflow-y-auto bg-surface">
      <div className="p-3">
        {/* Current Cycle */}
        <button
          onClick={() => setCurrentExpanded(!currentExpanded)}
          className="flex items-center gap-1 w-full cursor-pointer"
        >
          {currentExpanded ? (
            <ChevronDown size={12} strokeWidth={1.5} className="text-text-tertiary" />
          ) : (
            <ChevronRight size={12} strokeWidth={1.5} className="text-text-tertiary" />
          )}
          <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
            Current Cycle
          </span>
          <Badge variant="info" className="ml-auto">{currentItems.length}</Badge>
        </button>

        {currentExpanded && (
          <div className="mt-2 space-y-0.5">
            {currentItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectBrief(item.id)}
                className={cn(
                  'flex items-center gap-2 p-[5px_8px] rounded-sm w-full text-left cursor-pointer',
                  'hover:bg-accent-subtle transition-colors duration-100',
                  selectedBriefId === item.id && 'bg-accent-subtle'
                )}
              >
                <StatusDot color={stageToColor[item.stage as StageId]} />
                <span
                  className={cn(
                    'text-[12px] truncate flex-1',
                    selectedBriefId === item.id ? 'text-accent' : 'text-text-primary'
                  )}
                >
                  {item.title}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Published */}
        <button
          onClick={() => setHistoryExpanded(!historyExpanded)}
          className="flex items-center gap-1 w-full mt-4 cursor-pointer"
        >
          {historyExpanded ? (
            <ChevronDown size={12} strokeWidth={1.5} className="text-text-tertiary" />
          ) : (
            <ChevronRight size={12} strokeWidth={1.5} className="text-text-tertiary" />
          )}
          <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
            Published
          </span>
          <Badge variant="success" className="ml-auto">{historyItems.length}</Badge>
        </button>

        {historyExpanded && (
          <div className="mt-2 space-y-0.5">
            {historyItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectBrief(item.id)}
                className={cn(
                  'flex items-start gap-2 p-[5px_8px] rounded-sm w-full text-left cursor-pointer',
                  'hover:bg-accent-subtle transition-colors duration-100',
                  selectedBriefId === item.id && 'bg-accent-subtle'
                )}
              >
                <StatusDot color="success" className="mt-1" />
                <div className="flex-1 min-w-0">
                  <span className={cn('text-[12px] line-clamp-2 block', selectedBriefId === item.id ? 'text-accent' : 'text-text-primary')}>
                    {item.title}
                  </span>
                  <div className="flex items-center gap-1 mt-0.5">
                    <Clock size={9} strokeWidth={1.5} className="text-text-tertiary" />
                    <span className="text-[10px] text-text-tertiary">
                      {item.publishedAt
                        ? new Date(item.publishedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                        : '—'}
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* History link */}
        <div className="mt-4 pt-3 border-t border-border">
          <button className="text-[11px] text-accent hover:text-accent-hover transition-colors cursor-pointer">
            View all past cycles →
          </button>
        </div>
      </div>
    </div>
  );
}
