'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowUpDown, ArrowRight } from 'lucide-react';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { cn } from '@/lib/utils/cn';
import type { GapBrief } from '@/types/gap-analysis';

interface GapBriefTableProps {
  briefs: GapBrief[];
  clusters: { cluster_id: string; cluster_name: string }[];
  selectedCluster?: string | null;
  onClusterChange?: (cluster: string | null) => void;
  className?: string;
}

const CLASSIFICATION_BADGE = {
  significant_gap: { variant: 'error' as const, label: 'Significant Gap' },
  gap_to_close: { variant: 'warning' as const, label: 'Gap to Close' },
  roughly_equal: { variant: 'default' as const, label: 'Roughly Equal' },
  company_wins: { variant: 'green' as const, label: 'Company Wins' },
} as const;

type SortField = 'gap_score' | 'avg_citation_similarity' | 'best_company_sim' | 'cluster';
type SortDirection = 'asc' | 'desc';

export function GapBriefTable({
  briefs,
  clusters,
  selectedCluster,
  onClusterChange,
  className,
}: GapBriefTableProps) {
  const router = useRouter();
  const [classFilter, setClassFilter] = useState('all');
  const [sortField, setSortField] = useState<SortField>('gap_score');
  const [sortDir, setSortDir] = useState<SortDirection>('desc');

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  }

  const filtered = useMemo(() => {
    let result = [...briefs];

    if (selectedCluster) {
      result = result.filter((b) => b.cluster_id === selectedCluster);
    }

    if (classFilter !== 'all') {
      result = result.filter((b) => b.gap_classification === classFilter);
    }

    result.sort((a, b) => {
      let aVal: number | string;
      let bVal: number | string;

      switch (sortField) {
        case 'gap_score':
          aVal = a.gap_score;
          bVal = b.gap_score;
          break;
        case 'avg_citation_similarity':
          aVal = a.avg_citation_similarity;
          bVal = b.avg_citation_similarity;
          break;
        case 'best_company_sim':
          aVal = a.best_company_unit.similarity;
          bVal = b.best_company_unit.similarity;
          break;
        case 'cluster':
          aVal = a.cluster;
          bVal = b.cluster;
          break;
        default:
          return 0;
      }

      if (typeof aVal === 'string') {
        return sortDir === 'asc'
          ? aVal.localeCompare(bVal as string)
          : (bVal as string).localeCompare(aVal);
      }
      return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });

    return result;
  }, [briefs, selectedCluster, classFilter, sortField, sortDir]);

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <Tabs defaultValue="all" onValueChange={setClassFilter}>
          <TabsList>
            <TabsTrigger value="all">All ({briefs.length})</TabsTrigger>
            <TabsTrigger value="significant_gap">
              Significant Gap ({briefs.filter((b) => b.gap_classification === 'significant_gap').length})
            </TabsTrigger>
            <TabsTrigger value="gap_to_close">
              Gap to Close ({briefs.filter((b) => b.gap_classification === 'gap_to_close').length})
            </TabsTrigger>
            <TabsTrigger value="roughly_equal">
              Equal ({briefs.filter((b) => b.gap_classification === 'roughly_equal').length})
            </TabsTrigger>
            <TabsTrigger value="company_wins">
              Wins ({briefs.filter((b) => b.gap_classification === 'company_wins').length})
            </TabsTrigger>
          </TabsList>
          {/* TabsContent not needed - we use filtering instead */}
          <TabsContent value="all"><span /></TabsContent>
          <TabsContent value="significant_gap"><span /></TabsContent>
          <TabsContent value="gap_to_close"><span /></TabsContent>
          <TabsContent value="roughly_equal"><span /></TabsContent>
          <TabsContent value="company_wins"><span /></TabsContent>
        </Tabs>

        {selectedCluster && (
          <button
            onClick={() => onClusterChange?.(null)}
            className="text-body-sm font-sans text-ocean-500 hover:text-ocean-600 transition-colors"
          >
            Clear cluster filter
          </button>
        )}
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">#</TableHead>
            <TableHead className="min-w-[280px]">Query</TableHead>
            <TableHead>
              <SortButton field="cluster" current={sortField} direction={sortDir} onClick={toggleSort}>
                Cluster
              </SortButton>
            </TableHead>
            <TableHead>
              <SortButton field="gap_score" current={sortField} direction={sortDir} onClick={toggleSort}>
                Gap Score
              </SortButton>
            </TableHead>
            <TableHead>Classification</TableHead>
            <TableHead>
              <SortButton field="best_company_sim" current={sortField} direction={sortDir} onClick={toggleSort}>
                Best Company Sim
              </SortButton>
            </TableHead>
            <TableHead>
              <SortButton field="avg_citation_similarity" current={sortField} direction={sortDir} onClick={toggleSort}>
                Avg Citation Sim
              </SortButton>
            </TableHead>
            <TableHead className="w-12" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="text-center py-8 text-cream-600 text-body-sm">
                No briefs match the current filters.
              </TableCell>
            </TableRow>
          ) : (
            filtered.map((brief, index) => {
              const classification = CLASSIFICATION_BADGE[brief.gap_classification];
              return (
                <TableRow
                  key={brief.query_id}
                  className="cursor-pointer"
                  onClick={() => router.push(`/signal-analysis/briefs/${brief.query_id}`)}
                >
                  <TableCell className="font-sans text-cream-600 tabular-nums">
                    {index + 1}
                  </TableCell>
                  <TableCell>
                    <span className="text-body font-body text-cream-900 line-clamp-2">
                      {brief.query_text}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="blue">{brief.cluster}</Badge>
                  </TableCell>
                  <TableCell className="font-sans tabular-nums font-medium text-cream-950">
                    {brief.gap_score.toFixed(3)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={classification.variant}>{classification.label}</Badge>
                  </TableCell>
                  <TableCell className="font-sans tabular-nums text-cream-800">
                    {brief.best_company_unit.similarity.toFixed(3)}
                  </TableCell>
                  <TableCell className="font-sans tabular-nums text-cream-800">
                    {brief.avg_citation_similarity.toFixed(3)}
                  </TableCell>
                  <TableCell>
                    <ArrowRight className="h-4 w-4 text-cream-500" />
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>

      <p className="text-caption font-sans text-cream-600">
        Showing {filtered.length} of {briefs.length} briefs
      </p>
    </div>
  );
}

interface SortButtonProps {
  field: SortField;
  current: SortField;
  direction: SortDirection;
  onClick: (field: SortField) => void;
  children: React.ReactNode;
}

function SortButton({ field, current, direction, onClick, children }: SortButtonProps) {
  const isActive = current === field;
  return (
    <button
      className="flex items-center gap-1 hover:text-cream-950 transition-colors"
      onClick={(e) => {
        e.stopPropagation();
        onClick(field);
      }}
    >
      {children}
      <ArrowUpDown
        className={cn(
          'h-3 w-3',
          isActive ? 'text-ocean-400' : 'text-cream-500'
        )}
      />
    </button>
  );
}
