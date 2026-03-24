'use client';

import { useState, useMemo } from 'react';
import { Badge } from '@/components/ui';
import { CitationDrillDown } from './CitationDrillDown';
import type { Query, Platform } from '@/types';

interface CitationsTabProps {
  queries: Query[];
}

const PLATFORM_LABELS: Record<Platform, string> = {
  chatgpt: 'GPT',
  claude: 'CL',
  perplexity: 'PX',
  google_ai_overview: 'GAI',
  gemini: 'GEM',
};

const PLATFORM_ORDER: Platform[] = ['chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini'];

export function CitationsTab({ queries }: CitationsTabProps) {
  const [selectedQuery, setSelectedQuery] = useState<Query | null>(null);
  const [sortField, setSortField] = useState<'gap' | 'text' | 'cluster'>('gap');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [classFilter, setClassFilter] = useState('all');
  const [clusterFilter, setClusterFilter] = useState('all');

  // Summary stats from real data
  const stats = useMemo(() => {
    const sigGaps = queries.filter((q) => q.classification === 'significant_gap').length;
    const companyCited = queries.filter((q) => q.companyCited).length;
    const avgGap = queries.reduce((s, q) => s + q.gap, 0) / queries.length;
    return { sigGaps, companyCited, avgGap };
  }, [queries]);

  const clusters = useMemo(() => Array.from(new Set(queries.map((q) => q.cluster))), [queries]);

  const filtered = useMemo(() => {
    return queries.filter((q) => {
      if (classFilter !== 'all' && q.classification !== classFilter) return false;
      if (clusterFilter !== 'all' && q.cluster !== clusterFilter) return false;
      return true;
    });
  }, [queries, classFilter, clusterFilter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const dir = sortDir === 'asc' ? 1 : -1;
      if (sortField === 'gap') return (a.gap - b.gap) * dir;
      if (sortField === 'text') return a.text.localeCompare(b.text) * dir;
      return a.cluster.localeCompare(b.cluster) * dir;
    });
  }, [filtered, sortField, sortDir]);

  const handleSort = (field: 'gap' | 'text' | 'cluster') => {
    if (sortField === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortField(field); setSortDir('desc'); }
  };

  const arrow = (field: string) => sortField !== field ? '' : sortDir === 'asc' ? ' \u25B2' : ' \u25BC';

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
            All Queries ({filtered.length})
          </h3>
          <div className="flex items-center gap-2">
            <select
              value={classFilter}
              onChange={(e) => setClassFilter(e.target.value)}
              className="h-[24px] px-1.5 rounded-sm border border-border bg-surface text-[10px] text-text-primary outline-none cursor-pointer"
            >
              <option value="all">All Classes</option>
              <option value="significant_gap">Significant Gap</option>
              <option value="gap_to_close">Gap to Close</option>
              <option value="roughly_equal">Roughly Equal</option>
              <option value="company_wins">Company Wins</option>
            </select>
            <select
              value={clusterFilter}
              onChange={(e) => setClusterFilter(e.target.value)}
              className="h-[24px] px-1.5 rounded-sm border border-border bg-surface text-[10px] text-text-primary outline-none cursor-pointer"
            >
              <option value="all">All Clusters</option>
              {clusters.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <span className="text-[10px] text-text-tertiary">Click row for drill-down</span>
          </div>
        </div>
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
              {sorted.map((q) => (
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
      </div>

      <CitationDrillDown query={selectedQuery} onClose={() => setSelectedQuery(null)} />
    </>
  );
}
