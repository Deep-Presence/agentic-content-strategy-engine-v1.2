'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  Search,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  ChevronDownIcon,
  FileText,
  Target,
  BookOpen,
  Layers,
  ExternalLink,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import { CLUSTER_COLORS, CLUSTER_NAMES, type QueryData } from '../data/sample-data';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SortField =
  | 'gap_score'
  | 'text'
  | 'cluster_name'
  | 'classification'
  | 'company_sim'
  | 'citation_sim'
  | 'delta'
  | 'target_words'
  | 'patterns';

type SortDir = 'asc' | 'desc';

type ClassificationFilter =
  | 'all'
  | 'significant_gap'
  | 'gap_to_close'
  | 'roughly_equal'
  | 'company_wins';

interface QueryMasterTableProps {
  queries: QueryData[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CLASSIFICATION_LABELS: Record<string, string> = {
  significant_gap: 'Significant Gap',
  gap_to_close: 'Gap to Close',
  roughly_equal: 'Roughly Equal',
  company_wins: 'Company Wins',
};

const CLASSIFICATION_BADGE_VARIANT: Record<string, string> = {
  significant_gap: 'terracotta',
  gap_to_close: 'warning',
  roughly_equal: 'default',
  company_wins: 'green',
};

const ITEMS_PER_PAGE = 15;

function gapScoreBg(score: number): string {
  // Interpolate from sage green (low) to terracotta (high >= 0.25)
  const t = Math.min(score / 0.3, 1);
  // low: rgba(120,140,93,0.06)  high: rgba(217,119,87,0.15)
  const r = Math.round(120 + (217 - 120) * t);
  const g = Math.round(140 + (119 - 140) * t);
  const b = Math.round(93 + (87 - 93) * t);
  const a = 0.06 + (0.15 - 0.06) * t;
  return `rgba(${r},${g},${b},${a.toFixed(3)})`;
}

function deltaColor(delta: number): string {
  if (delta > 0.001) return 'text-red-600';
  if (delta < -0.001) return 'text-green-700';
  return 'text-[#141413]/60';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function QueryMasterTable({ queries }: QueryMasterTableProps) {
  // --- State ---------------------------------------------------------------
  const [sortField, setSortField] = useState<SortField>('gap_score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [classFilter, setClassFilter] = useState<ClassificationFilter>('all');
  const [clusterFilter, setClusterFilter] = useState<string>('all');
  const [searchText, setSearchText] = useState('');
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // --- Derived data --------------------------------------------------------

  // Unique clusters present in data
  const clusterOptions = useMemo(() => {
    const seen = new Map<string, string>();
    queries.forEach((q) => {
      if (!seen.has(q.cluster_id)) {
        seen.set(q.cluster_id, q.cluster_name);
      }
    });
    return Array.from(seen.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([id, name]) => ({ id, name }));
  }, [queries]);

  // Filtered queries
  const filtered = useMemo(() => {
    let result = [...queries];

    if (classFilter !== 'all') {
      result = result.filter((q) => q.classification === classFilter);
    }

    if (clusterFilter !== 'all') {
      result = result.filter((q) => q.cluster_id === clusterFilter);
    }

    if (searchText.trim()) {
      const lower = searchText.trim().toLowerCase();
      result = result.filter((q) => q.text.toLowerCase().includes(lower));
    }

    return result;
  }, [queries, classFilter, clusterFilter, searchText]);

  // Sorted queries
  const sorted = useMemo(() => {
    const arr = [...filtered];
    const dir = sortDir === 'asc' ? 1 : -1;

    arr.sort((a, b) => {
      switch (sortField) {
        case 'gap_score':
          return (a.gap_score - b.gap_score) * dir;
        case 'text':
          return a.text.localeCompare(b.text) * dir;
        case 'cluster_name':
          return a.cluster_name.localeCompare(b.cluster_name) * dir;
        case 'classification':
          return a.classification.localeCompare(b.classification) * dir;
        case 'company_sim':
          return (a.company_sim - b.company_sim) * dir;
        case 'citation_sim':
          return (a.citation_sim - b.citation_sim) * dir;
        case 'delta':
          return (
            (a.citation_sim - a.company_sim - (b.citation_sim - b.company_sim)) *
            dir
          );
        case 'target_words':
          return (a.target_words.min - b.target_words.min) * dir;
        case 'patterns':
          return (a.patterns.length - b.patterns.length) * dir;
        default:
          return 0;
      }
    });

    return arr;
  }, [filtered, sortField, sortDir]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(sorted.length / ITEMS_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const paginatedQueries = sorted.slice(
    (safePage - 1) * ITEMS_PER_PAGE,
    safePage * ITEMS_PER_PAGE
  );

  // Ranking based on full sorted list (gap_score desc by default for rank)
  const rankMap = useMemo(() => {
    const ranked = [...filtered].sort((a, b) => b.gap_score - a.gap_score);
    const map = new Map<string, number>();
    ranked.forEach((q, i) => map.set(q.id, i + 1));
    return map;
  }, [filtered]);

  // --- Callbacks -----------------------------------------------------------

  const handleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortField(field);
        setSortDir(field === 'text' || field === 'cluster_name' ? 'asc' : 'desc');
      }
      setPage(1);
    },
    [sortField]
  );

  const handleFilterChange = useCallback((f: ClassificationFilter) => {
    setClassFilter(f);
    setPage(1);
  }, []);

  const handleClusterChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setClusterFilter(e.target.value);
      setPage(1);
    },
    []
  );

  const handleSearch = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchText(e.target.value);
      setPage(1);
    },
    []
  );

  const toggleRow = useCallback(
    (id: string) => {
      setExpandedId((prev) => (prev === id ? null : id));
    },
    []
  );

  // --- Sort indicator ------------------------------------------------------

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field)
      return <ChevronsUpDown className="ml-1 inline h-3.5 w-3.5 text-[#141413]/30" />;
    return sortDir === 'asc' ? (
      <ChevronUp className="ml-1 inline h-3.5 w-3.5 text-[#d97757]" />
    ) : (
      <ChevronDown className="ml-1 inline h-3.5 w-3.5 text-[#d97757]" />
    );
  }

  // --- Classification filter tabs ------------------------------------------

  const classificationTabs: { key: ClassificationFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'significant_gap', label: 'Significant Gap' },
    { key: 'gap_to_close', label: 'Gap to Close' },
    { key: 'roughly_equal', label: 'Roughly Equal' },
    { key: 'company_wins', label: 'Company Wins' },
  ];

  // --- Render --------------------------------------------------------------

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="font-serif text-lg">Query Intelligence Table</CardTitle>
        <p className="text-sm text-[#141413]/60 font-sans">
          All {queries.length} queries ranked by gap severity — click any row for
          full content brief specs
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ---- Toolbar ---- */}
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          {/* Classification filter tabs */}
          <div className="flex flex-wrap gap-1">
            {classificationTabs.map((tab) => (
              <Button
                key={tab.key}
                variant={classFilter === tab.key ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => handleFilterChange(tab.key)}
                className={cn(
                  'text-xs',
                  classFilter === tab.key && 'shadow-sm'
                )}
              >
                {tab.label}
              </Button>
            ))}
          </div>

          {/* Search + cluster filter */}
          <div className="flex gap-2 items-center">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#141413]/40" />
              <input
                type="text"
                placeholder="Search queries..."
                value={searchText}
                onChange={handleSearch}
                className="h-8 w-56 rounded-md border border-[#141413]/10 bg-[#faf9f5] pl-8 pr-3 text-xs font-sans placeholder:text-[#141413]/40 focus:outline-none focus:ring-1 focus:ring-[#d97757]/40"
              />
            </div>

            <div className="relative">
              <select
                value={clusterFilter}
                onChange={handleClusterChange}
                className="h-8 appearance-none rounded-md border border-[#141413]/10 bg-[#faf9f5] pl-3 pr-7 text-xs font-sans focus:outline-none focus:ring-1 focus:ring-[#d97757]/40 cursor-pointer"
              >
                <option value="all">All Clusters</option>
                {clusterOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id}: {c.name}
                  </option>
                ))}
              </select>
              <ChevronDownIcon className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#141413]/40" />
            </div>
          </div>
        </div>

        {/* Results count */}
        <div className="text-xs text-[#141413]/50 font-sans">
          Showing {paginatedQueries.length} of {sorted.length} queries
          {sorted.length !== queries.length && ` (filtered from ${queries.length})`}
        </div>

        {/* ---- Table ---- */}
        <div className="overflow-x-auto rounded-lg border border-[#141413]/8">
          <table className="w-full text-xs font-sans">
            {/* Sticky header */}
            <thead className="sticky top-0 z-10 bg-[#f0efe9]">
              <tr>
                <Th field="gap_score" label="#" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-10 text-center" />
                <Th field="text" label="Query" currentSort={sortField} dir={sortDir} onSort={handleSort} className="min-w-[240px]" />
                <Th field="cluster_name" label="Cluster" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-28" />
                <Th field="gap_score" label="Gap Score" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-24 text-right" />
                <Th field="classification" label="Classification" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-32" />
                <Th field="company_sim" label="Co. Sim" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-20 text-right" />
                <Th field="citation_sim" label="Cit. Sim" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-20 text-right" />
                <Th field="delta" label="Delta" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-20 text-right" />
                <Th field="target_words" label="Words" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-20 text-center" />
                <Th field="patterns" label="Patterns" currentSort={sortField} dir={sortDir} onSort={handleSort} className="w-36" />
              </tr>
            </thead>

            <tbody>
              {paginatedQueries.length === 0 && (
                <tr>
                  <td
                    colSpan={10}
                    className="py-12 text-center text-sm text-[#141413]/40"
                  >
                    No queries match the current filters.
                  </td>
                </tr>
              )}

              {paginatedQueries.map((q, idx) => {
                const rank = rankMap.get(q.id) ?? idx + 1;
                const delta = q.citation_sim - q.company_sim;
                const isExpanded = expandedId === q.id;
                const rowBg = idx % 2 === 0 ? 'bg-white' : 'bg-[#faf9f5]/60';

                return (
                  <TableRowGroup key={q.id}>
                    {/* Main row */}
                    <tr
                      onClick={() => toggleRow(q.id)}
                      className={cn(
                        rowBg,
                        'cursor-pointer transition-colors hover:bg-[#d97757]/5',
                        isExpanded && 'bg-[#d97757]/5'
                      )}
                    >
                      {/* Rank */}
                      <td className="py-2.5 px-3 text-center font-medium text-[#141413]/50">
                        {rank}
                      </td>

                      {/* Query text */}
                      <td className="py-2.5 px-3" title={q.text}>
                        <span className="line-clamp-2 leading-snug text-[#141413]">
                          {q.text}
                        </span>
                      </td>

                      {/* Cluster */}
                      <td className="py-2.5 px-3">
                        <span
                          className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium text-white whitespace-nowrap"
                          style={{
                            backgroundColor:
                              CLUSTER_COLORS[q.cluster_id] ?? '#888',
                          }}
                        >
                          {q.cluster_id}
                        </span>
                      </td>

                      {/* Gap score */}
                      <td
                        className="py-2.5 px-3 text-right font-mono font-semibold"
                        style={{ backgroundColor: gapScoreBg(q.gap_score) }}
                      >
                        {q.gap_score.toFixed(4)}
                      </td>

                      {/* Classification */}
                      <td className="py-2.5 px-3">
                        <Badge
                          variant={
                            CLASSIFICATION_BADGE_VARIANT[q.classification] as
                              | 'terracotta'
                              | 'warning'
                              | 'default'
                              | 'green'
                          }
                          className="text-[10px]"
                        >
                          {CLASSIFICATION_LABELS[q.classification]}
                        </Badge>
                      </td>

                      {/* Company sim */}
                      <td className="py-2.5 px-3 text-right font-mono text-[#141413]/70">
                        {q.company_sim.toFixed(4)}
                      </td>

                      {/* Citation sim */}
                      <td className="py-2.5 px-3 text-right font-mono text-[#141413]/70">
                        {q.citation_sim.toFixed(4)}
                      </td>

                      {/* Delta */}
                      <td
                        className={cn(
                          'py-2.5 px-3 text-right font-mono font-medium',
                          deltaColor(delta)
                        )}
                      >
                        {delta > 0 ? '+' : ''}
                        {delta.toFixed(4)}
                      </td>

                      {/* Target words */}
                      <td className="py-2.5 px-3 text-center text-[#141413]/70">
                        {q.target_words.min}–{q.target_words.max}
                      </td>

                      {/* Patterns */}
                      <td className="py-2.5 px-3">
                        <div className="flex flex-wrap gap-1">
                          {q.patterns.slice(0, 3).map((p) => (
                            <span
                              key={p}
                              className="inline-block rounded bg-[#141413]/5 px-1.5 py-0.5 text-[10px] text-[#141413]/60"
                            >
                              {p}
                            </span>
                          ))}
                          {q.patterns.length > 3 && (
                            <span className="inline-block rounded bg-[#141413]/5 px-1.5 py-0.5 text-[10px] text-[#141413]/40">
                              +{q.patterns.length - 3}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>

                    {/* Expanded detail row */}
                    {isExpanded && (
                      <tr className="bg-[#faf9f5]">
                        <td colSpan={10} className="px-6 py-4">
                          <ExpandedDetail query={q} />
                        </td>
                      </tr>
                    )}
                  </TableRowGroup>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* ---- Pagination ---- */}
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-[#141413]/50 font-sans">
            Page {safePage} of {totalPages}
          </span>
          <div className="flex gap-1.5">
            <Button
              variant="ghost"
              size="sm"
              disabled={safePage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="h-7 w-7 p-0"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="h-7 w-7 p-0"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Wrapper that allows <tbody> fragment for expanded rows */
function TableRowGroup({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

/** Sortable table header cell */
function Th({
  field,
  label,
  currentSort,
  dir,
  onSort,
  className,
}: {
  field: SortField;
  label: string;
  currentSort: SortField;
  dir: SortDir;
  onSort: (f: SortField) => void;
  className?: string;
}) {
  const isActive = currentSort === field;
  return (
    <th
      onClick={() => onSort(field)}
      className={cn(
        'py-2.5 px-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[#141413]/60 cursor-pointer select-none whitespace-nowrap',
        isActive && 'text-[#d97757]',
        className
      )}
    >
      {label}
      {isActive ? (
        dir === 'asc' ? (
          <ChevronUp className="ml-0.5 inline h-3 w-3" />
        ) : (
          <ChevronDown className="ml-0.5 inline h-3 w-3" />
        )
      ) : (
        <ChevronsUpDown className="ml-0.5 inline h-3 w-3 opacity-30" />
      )}
    </th>
  );
}

/** Expanded row detail panel */
function ExpandedDetail({ query }: { query: QueryData }) {
  const delta = query.citation_sim - query.company_sim;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* Column 1: Content Brief */}
      <div className="space-y-3">
        <h4 className="font-serif text-sm font-semibold text-[#141413] flex items-center gap-1.5">
          <FileText className="h-3.5 w-3.5 text-[#d97757]" />
          Content Brief Specs
        </h4>
        <div className="space-y-2 text-xs text-[#141413]/70">
          <div className="flex justify-between">
            <span>Target Word Count</span>
            <span className="font-mono font-medium text-[#141413]">
              {query.target_words.min}–{query.target_words.max}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Reading Level</span>
            <span className="font-mono font-medium text-[#141413]">
              {query.reading_level.min}–{query.reading_level.max}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Recommended Headers</span>
            <span className="font-mono font-medium text-[#141413]">
              {query.headers}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Top Domain</span>
            <span className="font-medium text-[#6a9bcc] flex items-center gap-1">
              {query.top_domain}
              <ExternalLink className="h-2.5 w-2.5" />
            </span>
          </div>
          <div className="flex justify-between">
            <span>Top Exemplar Similarity</span>
            <span className="font-mono font-medium text-[#141413]">
              {query.top_exemplar_sim.toFixed(4)}
            </span>
          </div>
        </div>
      </div>

      {/* Column 2: Patterns & Signals */}
      <div className="space-y-3">
        <h4 className="font-serif text-sm font-semibold text-[#141413] flex items-center gap-1.5">
          <Target className="h-3.5 w-3.5 text-[#788c5d]" />
          Content Patterns
        </h4>
        <div className="flex flex-wrap gap-1.5">
          {query.patterns.map((p) => (
            <Badge key={p} variant="default" className="text-[10px]">
              {p}
            </Badge>
          ))}
        </div>

        <h4 className="font-serif text-sm font-semibold text-[#141413] flex items-center gap-1.5 pt-2">
          <Layers className="h-3.5 w-3.5 text-[#6a9bcc]" />
          Similarity Analysis
        </h4>
        <div className="space-y-1.5 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-20 text-[#141413]/60">Company</span>
            <div className="flex-1 h-2 rounded-full bg-[#141413]/5 overflow-hidden">
              <div
                className="h-full rounded-full bg-[#6a9bcc]"
                style={{ width: `${query.company_sim * 100}%` }}
              />
            </div>
            <span className="font-mono w-14 text-right text-[#141413]">
              {query.company_sim.toFixed(4)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-20 text-[#141413]/60">Citation</span>
            <div className="flex-1 h-2 rounded-full bg-[#141413]/5 overflow-hidden">
              <div
                className="h-full rounded-full bg-[#d97757]"
                style={{ width: `${query.citation_sim * 100}%` }}
              />
            </div>
            <span className="font-mono w-14 text-right text-[#141413]">
              {query.citation_sim.toFixed(4)}
            </span>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <span className="w-20 text-[#141413]/60">Delta</span>
            <span
              className={cn(
                'font-mono font-semibold text-sm',
                deltaColor(delta)
              )}
            >
              {delta > 0 ? '+' : ''}
              {delta.toFixed(4)}
              {delta > 0.001
                ? ' (citations ahead)'
                : delta < -0.001
                ? ' (company ahead)'
                : ' (parity)'}
            </span>
          </div>
        </div>
      </div>

      {/* Column 3: Platform Citations */}
      <div className="space-y-3">
        <h4 className="font-serif text-sm font-semibold text-[#141413] flex items-center gap-1.5">
          <BookOpen className="h-3.5 w-3.5 text-[#d97757]" />
          Platform Citations
        </h4>
        <div className="space-y-2">
          {(
            [
              { key: 'chatgpt' as const, label: 'ChatGPT', color: '#10a37f' },
              { key: 'claude' as const, label: 'Claude', color: '#d97757' },
              { key: 'perplexity' as const, label: 'Perplexity', color: '#6a9bcc' },
              { key: 'gemini' as const, label: 'Gemini', color: '#788c5d' },
            ] as const
          ).map(({ key, label, color }) => (
            <div key={key} className="flex items-center gap-2 text-xs">
              <span
                className="h-2 w-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: color }}
              />
              <span className="w-20 text-[#141413]/60">{label}</span>
              <div className="flex-1 h-2 rounded-full bg-[#141413]/5 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    backgroundColor: color,
                    width: `${Math.min(query.platform_citations[key] * 10, 100)}%`,
                  }}
                />
              </div>
              <span className="font-mono w-6 text-right text-[#141413]">
                {query.platform_citations[key]}
              </span>
            </div>
          ))}
        </div>

        {/* Cluster badge */}
        <div className="pt-3 border-t border-[#141413]/8">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-[#141413]/60">Cluster</span>
            <span
              className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium text-white"
              style={{
                backgroundColor:
                  CLUSTER_COLORS[query.cluster_id] ?? '#888',
              }}
            >
              {query.cluster_id}: {query.cluster_name}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
