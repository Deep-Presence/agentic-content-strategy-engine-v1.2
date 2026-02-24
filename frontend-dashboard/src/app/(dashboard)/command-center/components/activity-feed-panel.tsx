'use client';

import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { relativeTime } from '@/lib/utils/format';

export interface ActivityEvent {
  id: string;
  timestamp: string;
  type: 'published' | 'review_ready' | 'pipeline_complete' | 'gap_identified' | 'cycle_started';
  title: string;
  detail: string;
  href?: string;
}

interface ActivityFeedPanelProps {
  events: ActivityEvent[];
}

const EVENT_COLORS: Record<ActivityEvent['type'], string> = {
  published: 'bg-sage-400',
  review_ready: 'bg-terracotta-400',
  pipeline_complete: 'bg-ocean-400',
  gap_identified: 'bg-error',
  cycle_started: 'bg-cream-500',
};

export function ActivityFeedPanel({ events }: ActivityFeedPanelProps) {
  return (
    <Card className="animate-fade-in-up" style={{ animationDelay: '0.35s' }}>
      <CardHeader>
        <CardTitle>Activity Feed</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="max-h-[420px] overflow-y-auto pr-1">
          <div className="relative pl-5">
            {/* Vertical connector line */}
            <div className="absolute left-[5px] top-1 bottom-1 w-px bg-cream-300" />

            <div className="space-y-4">
              {events.map((event) => {
                const content = (
                  <div className="relative group">
                    {/* Dot */}
                    <div
                      className={`absolute -left-5 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white ${EVENT_COLORS[event.type]}`}
                    />

                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-body-sm font-sans font-medium text-cream-900">
                          {event.title}
                        </p>
                        <p className="text-caption text-cream-600 truncate">
                          {event.detail}
                        </p>
                      </div>
                      <span className="text-micro font-sans text-cream-500 whitespace-nowrap shrink-0">
                        {relativeTime(event.timestamp)}
                      </span>
                    </div>
                  </div>
                );

                return event.href ? (
                  <Link
                    key={event.id}
                    href={event.href}
                    className="block hover:bg-cream-100 -mx-2 px-2 py-0.5 rounded transition-colors"
                  >
                    {content}
                  </Link>
                ) : (
                  <div key={event.id} className="py-0.5">{content}</div>
                );
              })}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
