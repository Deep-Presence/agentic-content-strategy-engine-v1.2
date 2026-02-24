'use client';

import { cn } from '@/lib/utils/cn';
import { BriefCard } from './brief-card';
import type { ContentBriefItem, ContentBriefStatus } from '@/types/content';

interface BoardViewProps {
  briefs: ContentBriefItem[];
  className?: string;
}

interface ColumnConfig {
  key: string;
  label: string;
  statuses: ContentBriefStatus[];
  dotColor: string;
}

const COLUMNS: ColumnConfig[] = [
  {
    key: 'suggested',
    label: 'Suggested',
    statuses: ['suggested'],
    dotColor: 'bg-cream-500',
  },
  {
    key: 'approved',
    label: 'Approved',
    statuses: ['approved'],
    dotColor: 'bg-ocean-400',
  },
  {
    key: 'in_progress',
    label: 'In Progress',
    statuses: ['research', 'drafting', 'enriching', 'formatting'],
    dotColor: 'bg-ocean-400',
  },
  {
    key: 'evaluating',
    label: 'Evaluating',
    statuses: ['evaluating'],
    dotColor: 'bg-terracotta-400',
  },
  {
    key: 'review',
    label: 'Review',
    statuses: ['review'],
    dotColor: 'bg-terracotta-400',
  },
  {
    key: 'published',
    label: 'Published',
    statuses: ['published'],
    dotColor: 'bg-sage-400',
  },
];

export function BoardView({ briefs, className }: BoardViewProps) {
  const columnBriefs = COLUMNS.map((col) => ({
    ...col,
    items: briefs.filter((b) => col.statuses.includes(b.status)),
  }));

  return (
    <div className={cn('flex gap-4 overflow-x-auto pb-4', className)}>
      {columnBriefs.map((col) => (
        <div
          key={col.key}
          className="flex-shrink-0 w-[300px] flex flex-col"
        >
          <div className="flex items-center gap-2 px-2 py-2 mb-2">
            <span className={cn('h-2.5 w-2.5 rounded-full', col.dotColor)} />
            <h3 className="text-body-sm font-sans font-semibold text-cream-800">
              {col.label}
            </h3>
            <span className="text-caption font-sans text-cream-500 tabular-nums">
              {col.items.length}
            </span>
          </div>

          <div className="flex-1 space-y-2 min-h-[200px]">
            {col.items.length === 0 ? (
              <div className="border border-dashed border-cream-400 rounded-md p-6 text-center">
                <p className="text-caption font-sans text-cream-500">No briefs</p>
              </div>
            ) : (
              col.items.map((brief) => (
                <BriefCard key={brief.id} brief={brief} />
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
