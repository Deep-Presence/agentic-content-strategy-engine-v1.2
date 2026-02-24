'use client';

import { X, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import type { GapBrief } from '@/types/gap-analysis';

interface QueryDrillDownProps {
  brief: GapBrief | null;
  onClose: () => void;
  className?: string;
}

const classificationVariants: Record<string, 'error' | 'warning' | 'default' | 'success'> = {
  significant_gap: 'error',
  gap_to_close: 'warning',
  roughly_equal: 'default',
  company_wins: 'success',
};

const classificationLabels: Record<string, string> = {
  significant_gap: 'Significant Gap',
  gap_to_close: 'Gap to Close',
  roughly_equal: 'Roughly Equal',
  company_wins: 'Company Wins',
};

function QueryDrillDown({ brief, onClose, className }: QueryDrillDownProps) {
  if (!brief) return null;

  return (
    <div className={cn('bg-white border-l border-[var(--border-default)] overflow-y-auto', className)}>
      <div className="p-4 border-b border-[var(--border-default)] flex items-start justify-between gap-2">
        <div>
          <h3 className="font-serif text-heading-4 font-semibold text-cream-950">
            Query Detail
          </h3>
          <p className="text-body-sm text-cream-700 mt-1">{brief.query_text}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="p-4 space-y-4">
        {/* Gap Score & Classification */}
        <div className="flex items-center gap-3">
          <div className="text-center">
            <div className="text-heading-2 font-sans font-semibold tabular-nums text-terracotta-400">
              {(brief.gap_score * 100).toFixed(0)}%
            </div>
            <div className="text-micro text-cream-600 font-sans">Gap Score</div>
          </div>
          <Badge variant={classificationVariants[brief.gap_classification]}>
            {classificationLabels[brief.gap_classification]}
          </Badge>
        </div>

        {/* Cluster */}
        <div>
          <span className="text-caption font-sans font-semibold text-cream-600 uppercase tracking-wide">
            Cluster
          </span>
          <p className="text-body font-sans text-cream-900 mt-0.5">
            {brief.cluster} ({brief.cluster_id})
          </p>
        </div>

        {/* Best Company Match */}
        <Card accent="sage">
          <CardContent className="p-3">
            <div className="text-caption font-sans font-semibold text-sage-500 uppercase tracking-wide mb-1">
              Best Company Match
            </div>
            <div className="text-body-sm font-sans text-cream-900">
              Similarity: <span className="font-medium tabular-nums">{brief.best_company_unit.similarity.toFixed(2)}</span>
            </div>
            <p className="text-body-sm text-cream-700 mt-1 line-clamp-2">
              {brief.best_company_unit.snippet}
            </p>
          </CardContent>
        </Card>

        {/* Top Exemplars */}
        <div>
          <span className="text-caption font-sans font-semibold text-cream-600 uppercase tracking-wide">
            Top Citation Exemplars
          </span>
          <div className="space-y-2 mt-2">
            {brief.top_exemplars.slice(0, 3).map((exemplar, i) => (
              <Card key={i} accent="ocean" hoverable>
                <CardContent className="p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-caption font-sans font-medium text-ocean-500">
                      {exemplar.domain}
                    </span>
                    <span className="text-caption font-sans tabular-nums text-cream-700">
                      {exemplar.similarity.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-body-sm text-cream-700 line-clamp-2">
                    {exemplar.snippet}
                  </p>
                  <a
                    href={exemplar.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-caption text-ocean-400 hover:text-ocean-500 mt-1"
                  >
                    View source <ExternalLink className="h-3 w-3" />
                  </a>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Link to full brief */}
        <a
          href={`/signal-analysis/briefs/${brief.query_id}`}
          className="block"
        >
          <Button variant="secondary" size="sm" className="w-full">
            View Full Brief Detail
          </Button>
        </a>
      </div>
    </div>
  );
}

export { QueryDrillDown };
export type { QueryDrillDownProps };
