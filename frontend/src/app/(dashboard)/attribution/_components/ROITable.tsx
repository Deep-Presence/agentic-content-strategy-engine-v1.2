'use client';

import { useState, useMemo, Fragment } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronUp, ArrowUpDown, ChevronRight } from 'lucide-react';
import { Sparkline } from '@/components/ui';
import type { ContentROIRow } from './data';
import { platformLabels } from './data';
import type { Platform } from '@/types';

type SortKey = 'title' | 'citations' | 'aiSessions' | 'conversions' | 'revenue' | 'cpsPredicted' | 'cpsActual' | 'revPerCitation' | 'roiMultiplier';

interface ROITableProps {
  data: ContentROIRow[];
}

const ESTIMATED_CONTENT_COST = 1200;

const columns: { key: SortKey; header: string; align?: string }[] = [
  { key: 'title', header: 'Title' },
  { key: 'citations', header: 'Citations', align: 'text-right' },
  { key: 'aiSessions', header: 'AI Sessions', align: 'text-right' },
  { key: 'conversions', header: 'Conv.', align: 'text-right' },
  { key: 'revenue', header: 'Revenue', align: 'text-right' },
  { key: 'revPerCitation', header: 'Rev/Citation', align: 'text-right' },
  { key: 'roiMultiplier', header: 'ROI', align: 'text-right' },
  { key: 'cpsActual', header: 'CPS', align: 'text-right' },
];

function getComputedValue(row: ContentROIRow, key: SortKey): number | string {
  if (key === 'revPerCitation') return row.citations > 0 ? row.revenue / row.citations : 0;
  if (key === 'roiMultiplier') return row.revenue / ESTIMATED_CONTENT_COST;
  return row[key as keyof ContentROIRow] as number | string;
}

export function ROITable({ data }: ROITableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('revenue');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const sorted = useMemo(() => {
    return [...data].sort((a, b) => {
      const aVal = getComputedValue(a, sortKey);
      const bVal = getComputedValue(b, sortKey);
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
  }, [data, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className="w-6 py-[6px] px-1 border-b border-border" />
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className={cn(
                  'text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary text-left',
                  'py-[6px] px-[10px] border-b border-border bg-transparent cursor-pointer select-none',
                  'hover:text-text-secondary transition-colors',
                  col.align
                )}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {sortKey === col.key ? (
                    sortDir === 'asc' ? <ChevronUp size={10} strokeWidth={1.5} /> : <ChevronDown size={10} strokeWidth={1.5} />
                  ) : (
                    <ArrowUpDown size={10} strokeWidth={1.5} className="opacity-30" />
                  )}
                </span>
              </th>
            ))}
            <th className="text-[11px] font-medium tracking-[0.06em] uppercase text-text-tertiary py-[6px] px-[10px] border-b border-border">
              Trend
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const revPerCitation = row.citations > 0 ? row.revenue / row.citations : 0;
            const roiMultiplier = row.revenue / ESTIMATED_CONTENT_COST;
            const isExpanded = expandedRow === row.id;

            return (
              <Fragment key={row.id}>
                <tr
                  onClick={() => setExpandedRow(isExpanded ? null : row.id)}
                  className="cursor-pointer hover:bg-accent-subtle transition-colors duration-100 ease-out"
                >
                  <td className="py-[8px] px-1 border-b border-border-subtle">
                    <ChevronRight
                      size={12}
                      strokeWidth={1.5}
                      className={cn(
                        'text-text-tertiary transition-transform duration-150',
                        isExpanded && 'rotate-90'
                      )}
                    />
                  </td>
                  <td className="py-[8px] px-[10px] text-[13px] text-text-primary border-b border-border-subtle font-medium">{row.title}</td>
                  <td className="py-[8px] px-[10px] text-[13px] text-text-primary border-b border-border-subtle text-right">{row.citations}</td>
                  <td className="py-[8px] px-[10px] text-[13px] text-text-primary border-b border-border-subtle text-right">{row.aiSessions.toLocaleString()}</td>
                  <td className="py-[8px] px-[10px] text-[13px] text-text-primary border-b border-border-subtle text-right">{row.conversions}</td>
                  <td className="py-[8px] px-[10px] text-[13px] text-text-primary border-b border-border-subtle text-right font-medium">${row.revenue.toLocaleString()}</td>
                  <td className="py-[8px] px-[10px] text-[13px] text-text-secondary border-b border-border-subtle text-right">${Math.round(revPerCitation).toLocaleString()}</td>
                  <td className="py-[8px] px-[10px] text-[13px] border-b border-border-subtle text-right">
                    <span className={cn(
                      'font-medium',
                      roiMultiplier >= 10 ? 'text-success' : roiMultiplier >= 5 ? 'text-accent' : 'text-text-secondary'
                    )}>
                      {roiMultiplier.toFixed(1)}x
                    </span>
                  </td>
                  <td className="py-[8px] px-[10px] text-[13px] text-text-primary border-b border-border-subtle text-right">{row.cpsActual.toFixed(2)}</td>
                  <td className="py-[8px] px-[10px] border-b border-border-subtle">
                    <Sparkline data={row.citationTrend} className="w-[60px] h-[20px]" />
                  </td>
                </tr>
                {isExpanded && (
                  <tr>
                    <td colSpan={10} className="py-3 px-[10px] bg-surface border-b border-border-subtle">
                      <div className="text-[11px] font-medium text-text-tertiary uppercase tracking-[0.06em] mb-2">
                        Platform Breakdown
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                        {(Object.keys(row.platformBreakdown) as Platform[]).map((p) => {
                          const bd = row.platformBreakdown[p];
                          return (
                            <div key={p} className="bg-surface border border-border rounded-sm p-2.5">
                              <div className="text-[11px] font-medium text-text-primary mb-1">
                                {platformLabels[p]}
                              </div>
                              <div className="space-y-0.5">
                                <div className="flex justify-between text-[12px]">
                                  <span className="text-text-tertiary">Citations</span>
                                  <span className="text-text-primary">{bd.citations}</span>
                                </div>
                                <div className="flex justify-between text-[12px]">
                                  <span className="text-text-tertiary">Sessions</span>
                                  <span className="text-text-primary">{bd.sessions.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between text-[12px]">
                                  <span className="text-text-tertiary">Revenue</span>
                                  <span className="text-text-primary font-medium">${bd.revenue.toLocaleString()}</span>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
