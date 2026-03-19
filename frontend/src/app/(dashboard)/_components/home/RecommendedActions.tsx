'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Lightbulb } from 'lucide-react';
import { Card, Badge, Button, Toast } from '@/components/ui';
import { apiPost } from '@/lib/api/client';
import { CONTENT_DATA, CONTENT_ENGINE } from '@/lib/api/endpoints';
import type { Recommendation } from '@/lib/api/types';
import type { QueryRow } from '@/lib/api/types';

interface RecommendedActionsProps {
  recommendations: Recommendation[];
  executiveSummary: string;
  slug: string;
  companyName: string;
  companyDomain: string;
  topGapQueries?: QueryRow[];
}

export function RecommendedActions({
  recommendations,
  executiveSummary,
  slug,
  companyName,
  companyDomain,
  topGapQueries = [],
}: RecommendedActionsProps) {
  const router = useRouter();
  const [approvingIndex, setApprovingIndex] = useState<number | null>(null);
  const [approvedIndices, setApprovedIndices] = useState<Set<number>>(new Set());
  const [approvingGapIndex, setApprovingGapIndex] = useState<number | null>(null);
  const [approvedGapIndices, setApprovedGapIndices] = useState<Set<number>>(new Set());
  const [toast, setToast] = useState<{
    open: boolean;
    variant: 'success' | 'error' | 'info';
    message: string;
    action?: { label: string; onClick: () => void };
  }>({ open: false, variant: 'success', message: '' });

  const goToStudio = useCallback(() => router.push('/content'), [router]);

  const handleApproveRec = useCallback(async (rec: Recommendation, index: number) => {
    if (!slug || !companyName || !companyDomain) return;
    setApprovingIndex(index);
    try {
      await apiPost(CONTENT_DATA.briefs(slug), {
        title: rec.title_idea,
        cluster: rec.target_cluster,
        description: rec.expected_impact,
        source: 'recommendation',
      });

      let pipelineStarted = false;
      try {
        await apiPost(CONTENT_ENGINE.start, {
          company_name: companyName,
          domain: companyDomain,
          entry_mode: 'manual',
          manual_prompt: rec.title_idea,
          manual_cluster: rec.target_cluster,
          auto_approve: true,
        });
        pipelineStarted = true;
      } catch {
        // Pipeline may fail but brief is already created
      }

      setApprovedIndices((prev) => new Set(prev).add(index));
      setToast({
        open: true,
        variant: pipelineStarted ? 'success' : 'info',
        message: pipelineStarted
          ? 'Topic added. Pipeline started.'
          : 'Topic added. Pipeline could not start — trigger from Content Studio.',
        action: { label: 'View in Studio \u2192', onClick: goToStudio },
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to add topic.';
      setToast({ open: true, variant: 'error', message });
    } finally {
      setApprovingIndex(null);
    }
  }, [slug, companyName, companyDomain, goToStudio]);

  const handleApproveGap = useCallback(async (query: QueryRow, index: number) => {
    if (!slug || !companyName || !companyDomain) return;
    setApprovingGapIndex(index);
    try {
      await apiPost(CONTENT_DATA.briefs(slug), {
        title: query.query_text,
        cluster: query.cluster_name ?? '',
        description: `Gap query (${query.classification.replace(/_/g, ' ')}). Gap score: ${query.gap_score.toFixed(4)}.`,
        source: 'citation',
      });

      let pipelineStarted = false;
      try {
        await apiPost(CONTENT_ENGINE.start, {
          company_name: companyName,
          domain: companyDomain,
          entry_mode: 'manual',
          manual_prompt: query.query_text,
          manual_cluster: query.cluster_name ?? '',
          gap_query_id: query.query_id,
          auto_approve: true,
        });
        pipelineStarted = true;
      } catch {
        // Pipeline may fail but brief is already created
      }

      setApprovedGapIndices((prev) => new Set(prev).add(index));
      setToast({
        open: true,
        variant: pipelineStarted ? 'success' : 'info',
        message: pipelineStarted
          ? 'Topic added. Pipeline started.'
          : 'Topic added. Pipeline could not start — trigger from Content Studio.',
        action: { label: 'View in Studio \u2192', onClick: goToStudio },
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to add topic.';
      setToast({ open: true, variant: 'error', message });
    } finally {
      setApprovingGapIndex(null);
    }
  }, [slug, companyName, companyDomain, goToStudio]);

  // Deduplicate gap queries against LLM recommendations by cluster
  const recClusters = new Set(recommendations.map((r) => r.target_cluster.toLowerCase()));
  const filteredGaps = topGapQueries
    .filter((q) => !recClusters.has((q.cluster_name ?? '').toLowerCase()))
    .slice(0, 5);

  const totalSuggestions = recommendations.length + filteredGaps.length;

  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb size={16} strokeWidth={1.5} className="text-accent" />
        <h2 className="text-[18px] font-semibold text-text-primary">Recommended Actions</h2>
        <Badge variant="info">{totalSuggestions} suggestions</Badge>
      </div>

      {executiveSummary && (
        <p className="text-[12px] text-text-secondary leading-[1.6] line-clamp-2 mb-3">
          {executiveSummary}
        </p>
      )}

      {/* LLM Recommendations */}
      <div className="space-y-2">
        {recommendations.slice(0, 5).map((rec, i) => {
          const isApproved = approvedIndices.has(i);
          const isApproving = approvingIndex === i;
          return (
            <Card key={i}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-[14px] font-semibold text-text-primary leading-[1.4] mb-1">
                    {rec.title_idea}
                  </p>
                  <div className="flex items-center gap-1.5 mb-1">
                    <Badge variant="info">{rec.target_cluster}</Badge>
                  </div>
                  <p className="text-[11px] text-text-secondary leading-[1.5] line-clamp-2 mb-0.5">
                    {rec.expected_impact}
                  </p>
                  <p className="text-[10px] text-text-tertiary leading-[1.4] truncate">
                    {rec.structural_signals}
                  </p>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={isApproved || isApproving}
                  onClick={() => handleApproveRec(rec, i)}
                >
                  {isApproving ? 'Starting...' : isApproved ? 'Added' : 'Approve & Generate'}
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Top Gap Queries */}
      {filteredGaps.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-[14px] font-semibold text-text-primary">Top Gaps to Address</h3>
            <span className="text-[10px] text-text-tertiary">{filteredGaps.length} queries</span>
          </div>
          <div className="bg-surface border border-border rounded-md overflow-hidden">
            {filteredGaps.map((q, i) => {
              const isApproved = approvedGapIndices.has(i);
              const isApproving = approvingGapIndex === i;
              return (
                <div
                  key={q.query_id}
                  className="flex items-center justify-between gap-2 px-3 py-2 border-b border-border-subtle last:border-b-0"
                >
                  <div className="flex-1 min-w-0 flex items-center gap-2">
                    <p className="text-[12px] text-text-primary truncate max-w-[300px]">
                      {q.query_text}
                    </p>
                    <Badge variant="info">{q.cluster_name}</Badge>
                    <span className="text-[11px] font-mono text-text-secondary whitespace-nowrap">
                      {q.gap_score.toFixed(4)}
                    </span>
                    <Badge
                      variant={
                        q.classification === 'significant_gap'
                          ? 'error'
                          : q.classification === 'gap_to_close'
                            ? 'warning'
                            : 'neutral'
                      }
                    >
                      {q.classification.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={isApproved || isApproving}
                    onClick={() => handleApproveGap(q, i)}
                  >
                    {isApproving ? 'Adding...' : isApproved ? 'Added' : 'Act on this'}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <Toast
        open={toast.open}
        onClose={() => setToast((t) => ({ ...t, open: false }))}
        variant={toast.variant}
        message={toast.message}
        action={toast.action}
      />
    </section>
  );
}
