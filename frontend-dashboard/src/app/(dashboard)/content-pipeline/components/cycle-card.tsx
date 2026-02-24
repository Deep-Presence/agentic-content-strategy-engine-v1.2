import Link from 'next/link';
import { CheckCircle2, Circle, RefreshCw } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils/cn';
import { shortDate } from '@/lib/utils/format';
import { BriefStatusBadge } from './brief-status-badge';
import type { Cycle } from '@/types/content';

interface CycleCardProps {
  cycle: Cycle;
  isActive?: boolean;
  className?: string;
}

export function CycleCard({ cycle, isActive = false, className }: CycleCardProps) {
  const progress = cycle.total_count > 0
    ? Math.round((cycle.completed_count / cycle.total_count) * 100)
    : 0;
  const isComplete = cycle.completed_count === cycle.total_count && cycle.total_count > 0;

  return (
    <Card accent={isActive ? 'sage' : 'none'} className={cn(className)}>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-body font-sans font-semibold text-cream-950">
              {cycle.name}
            </h3>
            <p className="text-caption font-sans text-cream-600">
              {shortDate(cycle.start_date)} — {shortDate(cycle.end_date)}
            </p>
          </div>
          {isComplete && (
            <CheckCircle2 className="h-5 w-5 text-sage-400" />
          )}
        </div>

        <div className="flex items-center gap-3">
          <Progress
            value={cycle.completed_count}
            max={cycle.total_count || 1}
            color={isComplete ? 'sage' : 'terracotta'}
            className="flex-1"
          />
          <span className="text-body-sm font-sans tabular-nums text-cream-700 whitespace-nowrap">
            {cycle.completed_count}/{cycle.total_count} ({progress}%)
          </span>
        </div>

        {isActive && cycle.briefs.length > 0 && (
          <div className="space-y-1.5 pt-1">
            {cycle.briefs.map((brief) => {
              const isPublished = brief.status === 'published';
              const isInProgress = ['research', 'drafting', 'enriching', 'formatting', 'evaluating', 'review'].includes(brief.status);
              return (
                <Link
                  key={brief.id}
                  href={`/content-pipeline/${brief.id}`}
                  className="flex items-center gap-2 py-1 px-2 rounded hover:bg-cream-100 transition-colors group"
                >
                  {isPublished ? (
                    <CheckCircle2 className="h-4 w-4 text-sage-400 shrink-0" />
                  ) : isInProgress ? (
                    <RefreshCw className="h-4 w-4 text-ocean-400 shrink-0" />
                  ) : (
                    <Circle className="h-4 w-4 text-cream-500 shrink-0" />
                  )}
                  <span className="text-body-sm font-body text-cream-800 truncate flex-1 group-hover:text-sage-400">
                    {brief.title}
                  </span>
                  <BriefStatusBadge status={brief.status} />
                </Link>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
