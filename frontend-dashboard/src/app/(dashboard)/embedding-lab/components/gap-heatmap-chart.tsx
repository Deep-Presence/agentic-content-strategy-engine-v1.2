'use client';

import { useState } from 'react';
import { GapHeatmap, type HeatmapCell } from '@/components/charts/gap-heatmap';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import type { GapBrief } from '@/types/gap-analysis';

interface GapHeatmapChartProps {
  data: HeatmapCell[];
  clusters: string[];
  gapBriefs: GapBrief[];
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

function GapHeatmapChart({ data, clusters, gapBriefs, className }: GapHeatmapChartProps) {
  const [selectedCell, setSelectedCell] = useState<{ queryId: string; cluster: string } | null>(null);

  const selectedBrief = selectedCell
    ? gapBriefs.find((b) => b.query_id === selectedCell.queryId)
    : null;

  return (
    <div className={cn('grid grid-cols-1 lg:grid-cols-3 gap-6', className)}>
      {/* Heatmap */}
      <div className="lg:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle>Gap Score Heatmap</CardTitle>
          </CardHeader>
          <CardContent>
            <GapHeatmap
              data={data}
              clusters={clusters}
              onCellClick={(queryId, cluster) => setSelectedCell({ queryId, cluster })}
              width={600}
              height={400}
            />
          </CardContent>
        </Card>
      </div>

      {/* Detail panel */}
      <div>
        <Card>
          <CardHeader>
            <CardTitle>
              {selectedBrief ? 'Query Detail' : 'Click a Cell'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {selectedBrief ? (
              <div className="space-y-3">
                <p className="text-body text-cream-900">{selectedBrief.query_text}</p>

                <div className="flex items-center gap-2">
                  <div className="text-heading-3 font-sans font-semibold tabular-nums text-terracotta-400">
                    {(selectedBrief.gap_score * 100).toFixed(0)}%
                  </div>
                  <Badge variant={classificationVariants[selectedBrief.gap_classification]}>
                    {classificationLabels[selectedBrief.gap_classification]}
                  </Badge>
                </div>

                <div className="space-y-2 text-body-sm font-sans">
                  <div className="flex justify-between">
                    <span className="text-cream-600">Cluster</span>
                    <span className="text-cream-900">{selectedBrief.cluster} ({selectedBrief.cluster_id})</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-cream-600">Avg Citation Sim.</span>
                    <span className="text-cream-900 tabular-nums">{selectedBrief.avg_citation_similarity.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-cream-600">Company Match</span>
                    <span className="text-cream-900 tabular-nums">{selectedBrief.best_company_unit.similarity.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-cream-600">Target Word Count</span>
                    <span className="text-cream-900 tabular-nums">
                      {selectedBrief.content_brief.target_word_count.min}–{selectedBrief.content_brief.target_word_count.max}
                    </span>
                  </div>
                </div>

                {selectedBrief.content_brief.content_patterns.length > 0 && (
                  <div>
                    <span className="text-caption font-sans font-semibold text-cream-600 uppercase tracking-wide">
                      Content Patterns
                    </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {selectedBrief.content_brief.content_patterns.map((pattern) => (
                        <Badge key={pattern} variant="blue">
                          {pattern.replace(/_/g, ' ')}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-body-sm text-cream-600">
                Click on any cell in the heatmap to see the query detail and gap brief information.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export { GapHeatmapChart };
export type { GapHeatmapChartProps };
