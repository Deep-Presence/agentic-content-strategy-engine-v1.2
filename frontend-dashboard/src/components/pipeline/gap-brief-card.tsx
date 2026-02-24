import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import type { GapBrief } from '@/types/gap-analysis';

interface GapBriefCardProps {
  brief: GapBrief;
  rank?: number;
  className?: string;
}

const CLASSIFICATION_BADGE = {
  significant_gap: { variant: 'error' as const, label: 'Significant Gap' },
  gap_to_close: { variant: 'warning' as const, label: 'Gap to Close' },
  roughly_equal: { variant: 'default' as const, label: 'Roughly Equal' },
  company_wins: { variant: 'green' as const, label: 'Company Wins' },
} as const;

export function GapBriefCard({ brief, rank, className }: GapBriefCardProps) {
  const classification = CLASSIFICATION_BADGE[brief.gap_classification];

  return (
    <Link href={`/signal-analysis/briefs/${brief.query_id}`}>
      <Card hoverable className={cn('group', className)}>
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                {rank !== undefined && (
                  <span className="text-caption font-sans font-semibold text-cream-600">
                    #{rank}
                  </span>
                )}
                <Badge variant="blue">{brief.cluster}</Badge>
                <Badge variant={classification.variant}>{classification.label}</Badge>
              </div>
              <p className="text-body font-body text-cream-900 truncate">
                {brief.query_text}
              </p>
              <div className="flex items-center gap-4 mt-2 text-caption font-sans text-cream-600">
                <span>
                  Gap: <span className="font-medium text-cream-800">{brief.gap_score.toFixed(3)}</span>
                </span>
                <span>
                  Best match: <span className="font-medium text-cream-800">{brief.best_company_unit.similarity.toFixed(3)}</span>
                </span>
                <span>
                  Avg citation: <span className="font-medium text-cream-800">{brief.avg_citation_similarity.toFixed(3)}</span>
                </span>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-cream-500 group-hover:text-ocean-400 transition-colors shrink-0 mt-1" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
