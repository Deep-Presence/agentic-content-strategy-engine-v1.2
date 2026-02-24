'use client';

import Link from 'next/link';
import { FileText } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { relativeTime } from '@/lib/utils/format';
import { BriefStatusBadge } from './brief-status-badge';
import { ContentTypeBadge } from './content-type-badge';
import { CitabilityScoreBadge } from './citability-score-badge';
import type { ContentBriefItem } from '@/types/content';

interface BriefCardProps {
  brief: ContentBriefItem;
  compact?: boolean;
  className?: string;
}

export function BriefCard({ brief, compact = false, className }: BriefCardProps) {
  return (
    <Link href={`/content-pipeline/${brief.id}`}>
      <Card hoverable className={cn('p-3', className)}>
        <div className="space-y-2">
          <div className="flex items-start gap-2">
            <FileText className="h-4 w-4 text-sage-400 mt-0.5 shrink-0" />
            <h4 className="text-body-sm font-body font-medium text-cream-950 line-clamp-2 leading-snug">
              {brief.title}
            </h4>
          </div>

          <div className="flex items-center gap-1.5 flex-wrap">
            <ContentTypeBadge type={brief.content_type} />
            <span className="text-caption font-sans text-cream-600 truncate max-w-[140px]">
              {brief.cluster}
            </span>
          </div>

          {!compact && (
            <>
              {brief.citability_score != null ? (
                <CitabilityScoreBadge score={brief.citability_score} size="sm" showBar />
              ) : (
                <div className="flex items-center gap-2">
                  <span className="text-caption font-sans tabular-nums text-cream-500">&mdash;</span>
                  <div className="flex-1 h-1.5 bg-cream-300 rounded-full overflow-hidden min-w-[60px]" />
                </div>
              )}

              <div className="flex items-center justify-between text-caption font-sans text-cream-600">
                <span>{brief.target_word_count.toLocaleString()} words</span>
                <span>{relativeTime(brief.updated_at)}</span>
              </div>
            </>
          )}
        </div>
      </Card>
    </Link>
  );
}
