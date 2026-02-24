'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  format,
  isSameMonth,
  isSameDay,
  addMonths,
  subMonths,
  parseISO,
  isToday,
} from 'date-fns';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import type { ContentBriefItem } from '@/types/content';

interface CalendarViewProps {
  briefs: ContentBriefItem[];
  className?: string;
}

const STATUS_DOT_COLORS: Record<string, string> = {
  suggested: 'bg-cream-500',
  approved: 'bg-ocean-400',
  research: 'bg-ocean-400',
  drafting: 'bg-ocean-400',
  enriching: 'bg-ocean-400',
  formatting: 'bg-ocean-400',
  evaluating: 'bg-terracotta-400',
  review: 'bg-terracotta-400',
  published: 'bg-sage-400',
  draft_saved: 'bg-cream-600',
  rejected: 'bg-error',
};

export function CalendarView({ briefs, className }: CalendarViewProps) {
  const [currentMonth, setCurrentMonth] = useState(new Date());

  const days = useMemo(() => {
    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calStart = startOfWeek(monthStart);
    const calEnd = endOfWeek(monthEnd);
    return eachDayOfInterval({ start: calStart, end: calEnd });
  }, [currentMonth]);

  const briefsByDate = useMemo(() => {
    const map = new Map<string, ContentBriefItem[]>();
    for (const brief of briefs) {
      const dateKey = format(parseISO(brief.updated_at), 'yyyy-MM-dd');
      const existing = map.get(dateKey) ?? [];
      existing.push(brief);
      map.set(dateKey, existing);
    }
    return map;
  }, [briefs]);

  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <div className={cn('', className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-serif text-heading-3 text-cream-950">
          {format(currentMonth, 'MMMM yyyy')}
        </h3>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setCurrentMonth(new Date())}>
            Today
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-7 border border-[var(--border-default)] rounded-md overflow-hidden">
        {weekDays.map((day) => (
          <div
            key={day}
            className="px-2 py-2 text-center text-caption font-sans font-semibold text-cream-700 bg-cream-200 border-b border-[var(--border-default)]"
          >
            {day}
          </div>
        ))}

        {days.map((day) => {
          const dateKey = format(day, 'yyyy-MM-dd');
          const dayBriefs = briefsByDate.get(dateKey) ?? [];
          const inMonth = isSameMonth(day, currentMonth);
          const today = isToday(day);

          return (
            <div
              key={dateKey}
              className={cn(
                'min-h-[100px] p-1.5 border-b border-r border-[var(--border-subtle)]',
                !inMonth && 'bg-cream-100 opacity-50',
                today && 'bg-sage-50/50'
              )}
            >
              <span
                className={cn(
                  'inline-flex items-center justify-center h-6 w-6 rounded-full text-caption font-sans',
                  today
                    ? 'bg-sage-400 text-white font-semibold'
                    : 'text-cream-700'
                )}
              >
                {format(day, 'd')}
              </span>

              <div className="mt-1 space-y-0.5">
                {dayBriefs.slice(0, 3).map((brief) => (
                  <Link
                    key={brief.id}
                    href={`/content-pipeline/${brief.id}`}
                    className="flex items-center gap-1 px-1 py-0.5 rounded hover:bg-cream-200 transition-colors group"
                  >
                    <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', STATUS_DOT_COLORS[brief.status] ?? 'bg-cream-500')} />
                    <span className="text-micro font-sans text-cream-800 truncate group-hover:text-sage-400">
                      {brief.title}
                    </span>
                  </Link>
                ))}
                {dayBriefs.length > 3 && (
                  <span className="text-micro font-sans text-cream-500 px-1">
                    +{dayBriefs.length - 3} more
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
