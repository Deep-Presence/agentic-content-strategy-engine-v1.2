'use client';

import { useState, useMemo } from 'react';
import { Badge, Skeleton } from '@/components/ui';
import { CitationDrillDown } from './CitationDrillDown';
import { useGapSummary } from '@/lib/hooks/useGapAnalysis';
import { usePaginatedQuery } from '@/lib/hooks/usePaginatedQuery';
import { GAP_DATA } from '@/lib/api/endpoints';
import { toQuery } from '@/lib/api/transforms';
import type { QueryListResponse } from '@/lib/api/types';
import type { Query, Platform } from '@/types';

interface CitationsTabProps {
  slug: string;
}

const PLATFORM_LABELS: Record<Platform, string> = {
  chatgpt: 'GPT',
  claude: 'CL',
  perplexity: 'PX',
  google_ai_overview: 'GAI',
  gemini: 'GEM',
};

const PLATFORM_ORDER: Platform[] = ['chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini'];

export function CitationsTab({ slug }: CitationsTabProps) {
  const [selectedQuery, setSelectedQuery] = useState<Query | null>(null);
  const [sortBy, setSortBy] = useState('gap_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [classFilter, setClassFilter] = useState('');
  const [clusterFilter, setClusterFilter] = useState('');

  const { data: summary } = useGapSummary(slug);

  const { data: queryData, isLoading, page, setPage, totalPages } = usePaginatedQuery<QueryListResponse>(
    GAP_DATA.queries(slug),
    {
      sort_by: sortBy,
      sort_dir: sortDir,
      ...(classFilter ? { classification: classFilter } : {}),
      ...(clusterFilter ? { cluster: clusterFilter } : {}),
    },
  );

  const queries = useMemo(() => {
    return (queryData?.queries ?? []).map(toQuery);
  }, [queryData]);

  const clusters = useMemo(() => {
    if (!queryData?.queries) return [];
    return Array.from(new Set(queryData.queries.map((q) => q.cluster_name).filter(Boolean) as string[]));
  }, [queryData]);

  // Summary stats from gap summary API
  const stats = useMemo(() => ({
    sigGaps: summary?.classification_counts?.significant_gap ?? 0,
    companyCited: summary?.classification_counts?.company_wins ?? 0,
    avgGap: summary?.average_gap ?? 0,
  }), [summary]);

  const handleSort = (field: string) => {
    const apiField = field === 'text' ? 'query_text' : field === 'cluster' ? 'cluster_name' : 'gap_score';
    if (sortBy === apiField) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortBy(apiField); setSortDir('desc'); }
  };

  const arrow = (field: string) => {
    const apiField = field === 'text' ? 'query_text' : field === 'cluster' ? 'cluster_name' : 'gap_score';
    return sortBy !== apiField ? '' : sortDir === 'asc' ? ' \u25B2' : ' \u25BC';
  };

  return (
    <>
      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-surface border border-border rounded-md p-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-error-subtle flex items-center justify-center">
            <span className="text-error text-[14px] font-semibold">{'\u26A0'}</span>
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Significant Gaps</p>
            <p className="font-display text-[20px] font-semibold text-text-primary">{stats.sigGaps}</p>
          </div>
        </div>
        <div className="bg-surface border border-border rounded-md p-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-success-subtle flex items-center justify-center">
            <span className="text-success text-[14px] font-semibold">{'\u2713'}</span>
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Company Cited</p>
            <p className="font-display text-[20px] font-semibold text-text-primary">{stats.companyCited} queries</p>
          </div>
        </div>
        <div className="bg-surface border border-border rounded-md p-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-info-subtle flex items-center justify-center">
            <span className="text-info text-[14px] font-semibold">{'\u0394'}</span>
          </div>
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Avg Gap Score</p>
            <p className="font-display text-[20px] font-semibold text-text-primary">{stats.avgGap.toFixed(4)}</p>
          </div>
        </div>
      </div>

      {/* Query Table */}
      <div className="bg-surface border border-border rounded-md overflow-hidden">
        <div className="p-3 border-b border-border flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em]">
            All Queries ({queryData?.total ?? 0})
          </h3>
          <div className="flex items-center gap-2">
            <select
              value={classFilter}
              onChange={(e) => { setClassFilter(e.target.value); setPage(1); }}
              className="h-[24px] px-1.5 rounded-sm border border-border bg-surface text-[10px] text-text-primary outline-none cursor-pointer"
            >
              <option value="">All Classes</option>
              <option value="significant_gap">Significant Gap</option>
              <option value="gap_to_close">Gap to Close</option>
              <option value="roughly_equal">Roughly Equal</option>
              <option value="company_wins">Company Wins</option>
            </select>
            <select
              value={clusterFilter}
              onChange={(e) => { setClusterFilter(e.target.value); setPage(1); }}
              className="h-[24px] px-1.5 rounded-sm border border-border bg-surface text-[10px] text-text-primary outline-none cursor-pointer"
            >
              <option value="">All Clusters</option>
              {clusters.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <span className="text-[10px] text-text-tertiary">Click row for drill-down</span>
          </div>
        </div>

        {isLoading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full rounded-sm" />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary cursor-pointer hover:text-text-secondary select-none" onClick={() => handleSort('text')}>
                    Query{arrow('text')}
                  </th>
                  <th className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary cursor-pointer hover:text-text-secondary select-none" onClick={() => handleSort('cluster')}>
                    Cluster{arrow('cluster')}
                  </th>
                  <th className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Classification</th>
                  <th className="text-center p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Cited</th>
                  <th className="text-right p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary cursor-pointer hover:text-text-secondary select-none" onClick={() => handleSort('gap')}>
                    Gap{arrow('gap')}
                  </th>
                  <th className="text-center p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Platforms</th>
                </tr>
              </thead>
              <tbody>
                {queries.map((q) => (
                  <tr key={q.id} className="hover:bg-accent-subtle cursor-pointer border-b border-border-subtle transition-colors" onClick={() => setSelectedQuery(q)}>
                    <td className="p-[6px_10px] text-[12px] text-text-primary truncate max-w-[300px]">{q.text}</td>
                    <td className="p-[6px_10px]"><Badge variant="info">{q.cluster}</Badge></td>
                    <td className="p-[6px_10px]">
                      <Badge variant={q.classification === 'significant_gap' ? 'error' : q.classification === 'company_wins' ? 'success' : q.classification === 'gap_to_close' ? 'warning' : 'neutral'}>
                        {q.classification.replace(/_/g, ' ')}
                      </Badge>
                    </td>
                    <td className="p-[6px_10px] text-center text-[12px]">
                      {q.companyCited ? <span className="text-success">{'\u2713'}</span> : <span className="text-text-tertiary">{'\u2014'}</span>}
                    </td>
                    <td className="p-[6px_10px] text-right text-[12px] font-mono text-text-primary">{q.gap.toFixed(4)}</td>
                    <td className="p-[6px_10px]">
                      <div className="flex justify-center gap-1">
                        {PLATFORM_ORDER.map((p) => (
                          <span key={p} className={`text-[8px] font-mono w-5 h-4 flex items-center justify-center rounded-sm ${q.platforms.includes(p) ? 'bg-accent-subtle text-accent' : 'bg-transparent text-text-tertiary/40'}`} title={p}>
                            {PLATFORM_LABELS[p]}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between p-3 border-t border-border">
            <span className="text-[11px] text-text-tertiary">
              Page {page} of {totalPages}
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="h-[26px] px-2 text-[11px] border border-border rounded-sm bg-surface hover:bg-accent-subtle disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Prev
              </button>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="h-[26px] px-2 text-[11px] border border-border rounded-sm bg-surface hover:bg-accent-subtle disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      <CitationDrillDown query={selectedQuery} onClose={() => setSelectedQuery(null)} />
    </>
  );
}
