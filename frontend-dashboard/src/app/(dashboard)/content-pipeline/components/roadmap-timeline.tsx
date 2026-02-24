'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { format, parseISO, startOfWeek, addWeeks, isWithinInterval } from 'date-fns';
import { cn } from '@/lib/utils/cn';
import type { ContentBriefItem, ContentType } from '@/types/content';

interface RoadmapTimelineProps {
  briefs: ContentBriefItem[];
  weeks?: number;
  className?: string;
}

const STATUS_COLORS: Record<string, string> = {
  suggested: 'bg-cream-400',
  approved: 'bg-ocean-200',
  research: 'bg-ocean-300',
  drafting: 'bg-ocean-300',
  enriching: 'bg-ocean-300',
  formatting: 'bg-ocean-300',
  evaluating: 'bg-terracotta-200',
  review: 'bg-terracotta-300',
  published: 'bg-sage-300',
  draft_saved: 'bg-cream-500',
  rejected: 'bg-error/30',
};

const TYPE_LABELS: Record<ContentType, string> = {
  blog: 'Blog Posts',
  guide: 'Guides',
  case_study: 'Case Studies',
  product_page: 'Product Pages',
};

export function RoadmapTimeline({ briefs, weeks = 8, className }: RoadmapTimelineProps) {
  const weekColumns = useMemo(() => {
    const start = startOfWeek(new Date());
    return Array.from({ length: weeks }, (_, i) => {
      const weekStart = addWeeks(start, i - 2);
      const weekEnd = addWeeks(weekStart, 1);
      return { start: weekStart, end: weekEnd, label: format(weekStart, 'MMM d') };
    });
  }, [weeks]);

  const contentTypes = useMemo(() => {
    const types = new Set(briefs.map((b) => b.content_type));
    return Array.from(types) as ContentType[];
  }, [briefs]);

  return (
    <div className={cn('overflow-x-auto', className)}>
      <div className="min-w-[800px]">
        {/* Week headers */}
        <div className="flex border-b border-[var(--border-default)]">
          <div className="w-[140px] shrink-0 px-3 py-2">
            <span className="text-caption font-sans font-semibold text-cream-700 uppercase tracking-wider">
              Type
            </span>
          </div>
          {weekColumns.map((week) => (
            <div
              key={week.label}
              className="flex-1 min-w-[100px] px-2 py-2 text-center border-l border-[var(--border-subtle)]"
            >
              <span className="text-caption font-sans font-medium text-cream-700">
                {week.label}
              </span>
            </div>
          ))}
        </div>

        {/* Rows by content type */}
        {contentTypes.map((type) => {
          const typeBriefs = briefs.filter((b) => b.content_type === type);
          return (
            <div key={type} className="flex border-b border-[var(--border-subtle)] min-h-[60px]">
              <div className="w-[140px] shrink-0 px-3 py-3 flex items-start">
                <span className="text-body-sm font-sans font-medium text-cream-800">
                  {TYPE_LABELS[type]}
                </span>
              </div>
              {weekColumns.map((week) => {
                const weekBriefs = typeBriefs.filter((b) => {
                  const briefDate = parseISO(b.updated_at);
                  return isWithinInterval(briefDate, { start: week.start, end: week.end });
                });
                return (
                  <div
                    key={week.label}
                    className="flex-1 min-w-[100px] px-1 py-2 border-l border-[var(--border-subtle)] space-y-1"
                  >
                    {weekBriefs.map((brief) => (
                      <Link
                        key={brief.id}
                        href={`/content-pipeline/${brief.id}`}
                        className={cn(
                          'block px-2 py-1 rounded text-micro font-sans text-cream-900 truncate hover:opacity-80 transition-opacity',
                          STATUS_COLORS[brief.status] ?? 'bg-cream-300'
                        )}
                        title={brief.title}
                      >
                        {brief.title}
                      </Link>
                    ))}
                  </div>
                );
              })}
            </div>
          );
        })}

        {contentTypes.length === 0 && (
          <div className="text-center py-12">
            <p className="text-body font-sans text-cream-600">No content to display on the roadmap.</p>
          </div>
        )}
      </div>
    </div>
  );
}
