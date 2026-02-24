'use client';

import { useState, useMemo, useCallback, Fragment } from 'react';
import { ChevronDown, ChevronUp, ChevronsUpDown, AlertCircle, TrendingUp, BarChart3 } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';

import { SAMPLE_QUERIES, CLUSTER_COLORS, type QueryData } from '../data/sample-data';
import { WEBFLOW_CLUSTERS } from '@/lib/data/webflow-fixtures';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ClusterPerformanceHeatmapProps {
  queries: QueryData[];
}

type SortKey =
  | 'cluster'
  | 'queries'
  | 'citations'
  | 'avg_gap'
  | 'faq_rate'
  | 'table_rate'
  | 'headers'
  | 'lists'
  | 'stats'
  | 'avg_wc'
  | 'top_domain'
  | 'health';

type SortDirection = 'asc' | 'desc';

interface ComputedClusterRow {
  id: string;
  name: string;
  queries: number;
  citations: number;
  avg_gap: number;
  faq_rate: number;
  table_rate: number;
  headers: number;
  lists: number;
  stats: number;
  avg_wc: number;
  top_domain: string;
  health: 'green' | 'yellow' | 'red';
  dominant_type: string;
  themes: string[];
  top_gap_queries: QueryData[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function computeTopDomain(clusterQueries: QueryData[]): string {
  const freq: Record<string, number> = {};
  for (const q of clusterQueries) {
    const d = q.top_domain;
    if (d) {
      freq[d] = (freq[d] || 0) + 1;
    }
  }
  let best = '';
  let bestCount = 0;
  for (const [domain, count] of Object.entries(freq)) {
    if (count > bestCount) {
      best = domain;
      bestCount = count;
    }
  }
  return best || '—';
}

function computeAvgGap(clusterQueries: QueryData[]): number {
  if (clusterQueries.length === 0) return 0;
  const sum = clusterQueries.reduce((acc, q) => acc + q.gap_score, 0);
  return sum / clusterQueries.length;
}

function healthFromGap(avgGap: number): 'green' | 'yellow' | 'red' {
  if (avgGap >= 0.18) return 'red';
  if (avgGap >= 0.10) return 'yellow';
  return 'green';
}

/** Interpolates from white to a target color based on a 0-1 value. */
function rateBackground(value: number, maxValue: number = 0.5): string {
  const t = Math.min(value / maxValue, 1);
  // Blend from white (#ffffff) to ocean blue (#6a9bcc)
  const r = Math.round(255 - t * (255 - 106));
  const g = Math.round(255 - t * (255 - 155));
  const b = Math.round(255 - t * (255 - 204));
  return `rgb(${r}, ${g}, ${b})`;
}

/** Interpolates from green (low gap) to red (high gap). */
function gapBackground(value: number, min: number = 0, max: number = 0.35): string {
  const t = Math.min(Math.max((value - min) / (max - min), 0), 1);
  // green (#788c5d) → yellow (#d4a843) → red (#c75c3a)
  let r: number, g: number, b: number;
  if (t < 0.5) {
    const s = t / 0.5;
    r = Math.round(120 + s * (212 - 120));
    g = Math.round(140 + s * (168 - 140));
    b = Math.round(93 + s * (67 - 93));
  } else {
    const s = (t - 0.5) / 0.5;
    r = Math.round(212 + s * (199 - 212));
    g = Math.round(168 + s * (92 - 168));
    b = Math.round(67 + s * (58 - 67));
  }
  return `rgb(${r}, ${g}, ${b})`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function formatNumber(value: number): string {
  return value.toLocaleString();
}

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

interface ColumnDef {
  key: SortKey;
  label: string;
  shortLabel?: string;
  width: string;
  align: 'left' | 'center' | 'right';
}

const COLUMNS: ColumnDef[] = [
  { key: 'cluster', label: 'Cluster', width: 'min-w-[180px]', align: 'left' },
  { key: 'queries', label: 'Queries', width: 'w-[80px]', align: 'center' },
  { key: 'citations', label: 'Citations', width: 'w-[90px]', align: 'center' },
  { key: 'avg_gap', label: 'Avg Gap', width: 'w-[85px]', align: 'center' },
  { key: 'faq_rate', label: 'FAQ%', width: 'w-[70px]', align: 'center' },
  { key: 'table_rate', label: 'Table%', width: 'w-[75px]', align: 'center' },
  { key: 'headers', label: 'Headers%', width: 'w-[85px]', align: 'center' },
  { key: 'lists', label: 'Lists%', width: 'w-[70px]', align: 'center' },
  { key: 'stats', label: 'Stats%', width: 'w-[70px]', align: 'center' },
  { key: 'avg_wc', label: 'Avg WC', width: 'w-[85px]', align: 'center' },
  { key: 'top_domain', label: 'Top Domain', width: 'min-w-[130px]', align: 'left' },
  { key: 'health', label: 'Health', width: 'w-[75px]', align: 'center' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ClusterPerformanceHeatmap({ queries }: ClusterPerformanceHeatmapProps) {
  const [sortKey, setSortKey] = useState<SortKey>('avg_gap');
  const [sortDir, setSortDir] = useState<SortDirection>('desc');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  // Build computed rows from WEBFLOW_CLUSTERS + queries
  const rows = useMemo<ComputedClusterRow[]>(() => {
    return WEBFLOW_CLUSTERS.map((cluster) => {
      const clusterQueries = queries.filter((q) => q.cluster_id === cluster.id);
      const avgGap = computeAvgGap(clusterQueries);
      const topDomain = computeTopDomain(clusterQueries);
      const health = healthFromGap(avgGap);

      // Top 5 gap queries sorted by gap_score descending
      const topGapQueries = [...clusterQueries]
        .sort((a, b) => b.gap_score - a.gap_score)
        .slice(0, 5);

      return {
        id: cluster.id,
        name: cluster.name,
        queries: cluster.queries,
        citations: cluster.citations,
        avg_gap: avgGap,
        faq_rate: cluster.faq_rate,
        table_rate: cluster.table_rate,
        headers: cluster.headers,
        lists: cluster.lists,
        stats: cluster.stats,
        avg_wc: cluster.avg_word_count,
        top_domain: topDomain,
        health,
        dominant_type: cluster.dominant_type,
        themes: cluster.themes,
        top_gap_queries: topGapQueries,
      };
    });
  }, [queries]);

  // Sort rows
  const sortedRows = useMemo(() => {
    const sorted = [...rows].sort((a, b) => {
      let aVal: string | number;
      let bVal: string | number;

      switch (sortKey) {
        case 'cluster':
          aVal = a.name;
          bVal = b.name;
          break;
        case 'top_domain':
          aVal = a.top_domain;
          bVal = b.top_domain;
          break;
        case 'health': {
          const healthOrder = { green: 0, yellow: 1, red: 2 };
          aVal = healthOrder[a.health];
          bVal = healthOrder[b.health];
          break;
        }
        default:
          aVal = a[sortKey] as number;
          bVal = b[sortKey] as number;
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
    return sorted;
  }, [rows, sortKey, sortDir]);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortKey(key);
        setSortDir('desc');
      }
    },
    [sortKey],
  );

  const toggleExpand = useCallback((id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  // Summary stats
  const avgGapOverall = useMemo(() => {
    if (rows.length === 0) return 0;
    return rows.reduce((s, r) => s + r.avg_gap, 0) / rows.length;
  }, [rows]);

  const worstCluster = useMemo(() => {
    return rows.reduce((worst, r) => (r.avg_gap > worst.avg_gap ? r : worst), rows[0]);
  }, [rows]);

  const bestCluster = useMemo(() => {
    return rows.reduce((best, r) => (r.avg_gap < best.avg_gap ? r : best), rows[0]);
  }, [rows]);

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  function renderSortIcon(key: SortKey) {
    if (sortKey !== key) {
      return <ChevronsUpDown className="ml-1 h-3 w-3 text-[#141413]/30" />;
    }
    return sortDir === 'asc' ? (
      <ChevronUp className="ml-1 h-3 w-3 text-[#d97757]" />
    ) : (
      <ChevronDown className="ml-1 h-3 w-3 text-[#d97757]" />
    );
  }

  function renderHealthIndicator(health: 'green' | 'yellow' | 'red') {
    const colorMap = {
      green: 'bg-[#788c5d]',
      yellow: 'bg-amber-400',
      red: 'bg-red-500',
    };
    const labelMap = {
      green: 'Healthy',
      yellow: 'At Risk',
      red: 'Critical',
    };
    return (
      <div className="flex items-center justify-center gap-1.5">
        <span
          className={cn('inline-block h-3 w-3 rounded-full', colorMap[health])}
          title={labelMap[health]}
        />
        <span className="text-xs font-sans text-[#141413]/60">{labelMap[health]}</span>
      </div>
    );
  }

  function renderCell(row: ComputedClusterRow, key: SortKey) {
    switch (key) {
      case 'cluster':
        return (
          <div className="flex items-center gap-2.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{
                backgroundColor:
                  CLUSTER_COLORS[row.id as keyof typeof CLUSTER_COLORS] || '#6a9bcc',
              }}
            />
            <div className="min-w-0">
              <p className="font-sans text-sm font-semibold text-[#141413] truncate">
                {row.id} {row.name}
              </p>
              <p className="font-sans text-[11px] text-[#141413]/50 truncate">
                {row.dominant_type}
              </p>
            </div>
          </div>
        );
      case 'queries':
        return (
          <span className="font-sans text-sm tabular-nums text-[#141413]">
            {row.queries}
          </span>
        );
      case 'citations':
        return (
          <span className="font-sans text-sm tabular-nums text-[#141413]">
            {formatNumber(row.citations)}
          </span>
        );
      case 'avg_gap':
        return (
          <span
            className="inline-flex items-center justify-center rounded px-2 py-0.5 font-sans text-sm font-medium tabular-nums"
            style={{
              backgroundColor: gapBackground(row.avg_gap),
              color: row.avg_gap >= 0.22 ? '#fff' : '#141413',
            }}
          >
            {row.avg_gap.toFixed(3)}
          </span>
        );
      case 'faq_rate':
        return (
          <span
            className="inline-flex items-center justify-center rounded px-2 py-0.5 font-sans text-sm tabular-nums"
            style={{
              backgroundColor: rateBackground(row.faq_rate),
              color: row.faq_rate >= 0.35 ? '#fff' : '#141413',
            }}
          >
            {formatPercent(row.faq_rate)}
          </span>
        );
      case 'table_rate':
        return (
          <span
            className="inline-flex items-center justify-center rounded px-2 py-0.5 font-sans text-sm tabular-nums"
            style={{
              backgroundColor: rateBackground(row.table_rate),
              color: row.table_rate >= 0.35 ? '#fff' : '#141413',
            }}
          >
            {formatPercent(row.table_rate)}
          </span>
        );
      case 'headers':
        return (
          <span
            className="inline-flex items-center justify-center rounded px-2 py-0.5 font-sans text-sm tabular-nums"
            style={{
              backgroundColor: rateBackground(row.headers, 1.0),
              color: row.headers >= 0.7 ? '#fff' : '#141413',
            }}
          >
            {formatPercent(row.headers)}
          </span>
        );
      case 'lists':
        return (
          <span
            className="inline-flex items-center justify-center rounded px-2 py-0.5 font-sans text-sm tabular-nums"
            style={{
              backgroundColor: rateBackground(row.lists, 1.0),
              color: row.lists >= 0.7 ? '#fff' : '#141413',
            }}
          >
            {formatPercent(row.lists)}
          </span>
        );
      case 'stats':
        return (
          <span
            className="inline-flex items-center justify-center rounded px-2 py-0.5 font-sans text-sm tabular-nums"
            style={{
              backgroundColor: rateBackground(row.stats, 1.0),
              color: row.stats >= 0.7 ? '#fff' : '#141413',
            }}
          >
            {formatPercent(row.stats)}
          </span>
        );
      case 'avg_wc':
        return (
          <span className="font-sans text-sm tabular-nums text-[#141413]">
            {formatNumber(row.avg_wc)}
          </span>
        );
      case 'top_domain':
        return (
          <span className="font-sans text-xs text-[#141413]/70 truncate block max-w-[130px]">
            {row.top_domain}
          </span>
        );
      case 'health':
        return renderHealthIndicator(row.health);
      default:
        return null;
    }
  }

  function renderExpandedRow(row: ComputedClusterRow) {
    if (row.top_gap_queries.length === 0) {
      return (
        <div className="px-6 py-4 text-sm font-sans text-[#141413]/50">
          No queries available for this cluster.
        </div>
      );
    }

    return (
      <div className="px-6 py-4 space-y-2">
        <div className="flex items-center gap-2 mb-3">
          <AlertCircle className="h-3.5 w-3.5 text-[#d97757]" />
          <span className="font-sans text-xs font-semibold text-[#141413]/70 uppercase tracking-wider">
            Top {row.top_gap_queries.length} Gap Queries
          </span>
        </div>
        <div className="space-y-1.5">
          {row.top_gap_queries.map((q, idx) => (
            <div
              key={idx}
              className="flex items-center gap-3 rounded-md bg-white/80 border border-[#141413]/5 px-4 py-2.5"
            >
              <span className="font-sans text-[11px] text-[#141413]/40 w-4 flex-shrink-0 tabular-nums">
                {idx + 1}
              </span>
              <span className="font-sans text-sm text-[#141413] flex-1 min-w-0 truncate">
                {q.text}
              </span>
              <Badge
                variant={
                  q.gap_score >= 0.25
                    ? 'error'
                    : q.gap_score >= 0.15
                      ? 'warning'
                      : 'success'
                }
                className="flex-shrink-0"
              >
                Gap: {q.gap_score.toFixed(3)}
              </Badge>
              <span
                className="inline-flex items-center justify-center rounded px-2 py-0.5 font-sans text-[11px] tabular-nums flex-shrink-0"
                style={{
                  backgroundColor: rateBackground(q.company_sim, 1.0),
                  color: q.company_sim >= 0.7 ? '#fff' : '#141413',
                }}
              >
                Sim: {q.company_sim.toFixed(2)}
              </span>
              <span className="font-sans text-[11px] text-[#141413]/50 flex-shrink-0 w-[100px] text-right truncate">
                {q.top_domain}
              </span>
            </div>
          ))}
        </div>
        {row.themes.length > 0 && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[#141413]/5">
            <span className="font-sans text-[11px] text-[#141413]/50 flex-shrink-0">
              Themes:
            </span>
            <div className="flex flex-wrap gap-1">
              {row.themes.map((theme) => (
                <Badge key={theme} variant="default" className="text-[11px]">
                  {theme}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------------------

  return (
    <Card className="border-[#141413]/[0.06]">
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="font-serif text-lg text-[#141413] flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-[#d97757]" />
              Cluster Performance Heatmap
            </CardTitle>
            <CardDescription className="font-sans text-sm text-[#141413]/60 mt-1">
              Comparative view of structural signals, gap severity, and content patterns across all
              clusters. Click a row to inspect top gap queries.
            </CardDescription>
          </div>
          <div className="flex items-center gap-4 text-xs font-sans">
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-8 rounded-sm bg-gradient-to-r from-[#788c5d] via-[#d4a843] to-[#c75c3a]" />
              <span className="text-[#141413]/50">Gap severity</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-8 rounded-sm bg-gradient-to-r from-white to-[#6a9bcc] border border-[#141413]/10" />
              <span className="text-[#141413]/50">Rate intensity</span>
            </div>
          </div>
        </div>

        {/* Summary strip */}
        <div className="flex items-center gap-6 mt-4 pt-3 border-t border-[#141413]/[0.06]">
          <div className="flex items-center gap-2">
            <span className="font-sans text-xs text-[#141413]/50">Avg Gap:</span>
            <span
              className="inline-flex items-center rounded px-2 py-0.5 font-sans text-xs font-semibold tabular-nums"
              style={{
                backgroundColor: gapBackground(avgGapOverall),
                color: avgGapOverall >= 0.22 ? '#fff' : '#141413',
              }}
            >
              {avgGapOverall.toFixed(3)}
            </span>
          </div>
          {worstCluster && (
            <div className="flex items-center gap-2">
              <span className="font-sans text-xs text-[#141413]/50">Worst:</span>
              <span className="font-sans text-xs font-semibold text-red-600">
                {worstCluster.id} {worstCluster.name}
              </span>
              <span className="font-sans text-[11px] tabular-nums text-[#141413]/40">
                ({worstCluster.avg_gap.toFixed(3)})
              </span>
            </div>
          )}
          {bestCluster && (
            <div className="flex items-center gap-2">
              <span className="font-sans text-xs text-[#141413]/50">Best:</span>
              <span className="font-sans text-xs font-semibold text-[#788c5d]">
                {bestCluster.id} {bestCluster.name}
              </span>
              <span className="font-sans text-[11px] tabular-nums text-[#141413]/40">
                ({bestCluster.avg_gap.toFixed(3)})
              </span>
            </div>
          )}
          <div className="flex items-center gap-2 ml-auto">
            <TrendingUp className="h-3.5 w-3.5 text-[#141413]/40" />
            <span className="font-sans text-xs text-[#141413]/50">
              {rows.filter((r) => r.health === 'red').length} critical,{' '}
              {rows.filter((r) => r.health === 'yellow').length} at risk,{' '}
              {rows.filter((r) => r.health === 'green').length} healthy
            </span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            {/* Sticky header */}
            <thead className="sticky top-0 z-10">
              <tr className="bg-[#faf9f5] border-y border-[#141413]/[0.06]">
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className={cn(
                      'px-4 py-2.5 font-sans text-[11px] font-semibold uppercase tracking-wider text-[#141413]/50 cursor-pointer select-none hover:text-[#141413]/80 transition-colors',
                      col.width,
                      col.align === 'left'
                        ? 'text-left'
                        : col.align === 'right'
                          ? 'text-right'
                          : 'text-center',
                    )}
                    onClick={() => handleSort(col.key)}
                  >
                    <span className="inline-flex items-center whitespace-nowrap">
                      {col.label}
                      {renderSortIcon(col.key)}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row, rowIdx) => {
                const isExpanded = expandedRows.has(row.id);
                return (
                  <Fragment key={row.id}>
                    <tr
                      className={cn(
                        'cursor-pointer transition-colors group',
                        rowIdx % 2 === 0 ? 'bg-white' : 'bg-[#faf9f5]/50',
                        isExpanded
                          ? 'bg-[#d97757]/[0.04] hover:bg-[#d97757]/[0.06]'
                          : 'hover:bg-[#6a9bcc]/[0.04]',
                      )}
                      onClick={() => toggleExpand(row.id)}
                    >
                      {COLUMNS.map((col) => (
                        <td
                          key={col.key}
                          className={cn(
                            'px-4 py-3 border-b border-[#141413]/[0.04]',
                            col.width,
                            col.align === 'left'
                              ? 'text-left'
                              : col.align === 'right'
                                ? 'text-right'
                                : 'text-center',
                          )}
                        >
                          {renderCell(row, col.key)}
                        </td>
                      ))}
                    </tr>
                    {isExpanded && (
                      <tr className="bg-[#faf9f5]/70">
                        <td colSpan={COLUMNS.length} className="border-b border-[#141413]/[0.06]">
                          {renderExpandedRow(row)}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer legend */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-[#141413]/[0.06]">
          <div className="flex items-center gap-4 font-sans text-[11px] text-[#141413]/40">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#788c5d]" />
              Healthy (&lt;0.10)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-400" />
              At Risk (0.10-0.18)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
              Critical (&ge;0.18)
            </span>
          </div>
          <span className="font-sans text-[11px] text-[#141413]/40">
            Click any row to view top gap queries
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

