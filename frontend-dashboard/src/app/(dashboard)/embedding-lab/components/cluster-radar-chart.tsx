'use client';

import { useState, useMemo } from 'react';
import { ClusterRadar, type ClusterRadarData } from '@/components/charts/cluster-radar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { cn } from '@/lib/utils/cn';
import { formatPercent } from '@/lib/utils/format';
import type { ClusterSpec } from '@/types/gap-analysis';

interface ClusterRadarChartProps {
  clusters: ClusterSpec[];
  clusterColors: Record<string, string>;
  className?: string;
}

function ClusterRadarChart({ clusters, clusterColors, className }: ClusterRadarChartProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    new Set(clusters.slice(0, 3).map((c) => c.cluster_id)),
  );

  function toggleCluster(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function selectAll() {
    setSelectedIds(new Set(clusters.map((c) => c.cluster_id)));
  }

  function clearAll() {
    setSelectedIds(new Set());
  }

  const radarData: ClusterRadarData[] = useMemo(
    () =>
      clusters
        .filter((c) => selectedIds.has(c.cluster_id))
        .map((c) => ({
          name: c.cluster_name,
          color: clusterColors[c.cluster_id] || '#b0aea5',
          metrics: {
            headers: c.structural_rates.headers,
            lists: c.structural_rates.lists,
            stats: c.structural_rates.stats,
            citations: c.structural_rates.citations,
            faq: c.faq_rate,
            tables: c.table_rate,
            key_takeaways: c.key_takeaways_rate,
          },
        })),
    [clusters, selectedIds, clusterColors],
  );

  return (
    <div className={cn('grid grid-cols-1 lg:grid-cols-3 gap-6', className)}>
      {/* Left: Cluster selector */}
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Clusters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {clusters.map((cluster) => (
                <label
                  key={cluster.cluster_id}
                  className="flex items-center gap-2 cursor-pointer py-1 px-2 rounded hover:bg-cream-100 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(cluster.cluster_id)}
                    onChange={() => toggleCluster(cluster.cluster_id)}
                    className="accent-terracotta-400 h-3.5 w-3.5"
                  />
                  <span
                    className="h-2.5 w-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: clusterColors[cluster.cluster_id] }}
                  />
                  <span className="text-body-sm font-sans text-cream-900">
                    {cluster.cluster_name}
                  </span>
                  <span className="text-caption font-sans text-cream-600 ml-auto">
                    {cluster.cluster_id}
                  </span>
                </label>
              ))}
            </div>
            <div className="flex gap-2 mt-3">
              <Button variant="ghost" size="sm" onClick={selectAll}>
                Select All
              </Button>
              <Button variant="ghost" size="sm" onClick={clearAll}>
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Cluster detail table */}
        <Card>
          <CardHeader>
            <CardTitle>Cluster Details</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Cluster</TableHead>
                  <TableHead className="text-right">Avg WC</TableHead>
                  <TableHead className="text-right">FAQ</TableHead>
                  <TableHead className="text-right">Table</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {clusters.map((c) => (
                  <TableRow
                    key={c.cluster_id}
                    className={cn(!selectedIds.has(c.cluster_id) && 'opacity-40')}
                  >
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-1.5">
                        <span
                          className="h-2 w-2 rounded-full shrink-0"
                          style={{ backgroundColor: clusterColors[c.cluster_id] }}
                        />
                        {c.cluster_id}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {c.avg_word_count.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatPercent(c.faq_rate)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatPercent(c.table_rate)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Right: Radar chart + themes */}
      <div className="lg:col-span-2 space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Structural Rate Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            {radarData.length > 0 ? (
              <ClusterRadar clusters={radarData} size={420} />
            ) : (
              <div className="h-[420px] flex items-center justify-center text-body text-cream-600">
                Select at least one cluster to view the radar chart
              </div>
            )}
          </CardContent>
        </Card>

        {/* Exemplar themes */}
        {selectedIds.size > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Exemplar Themes</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {clusters
                  .filter((c) => selectedIds.has(c.cluster_id))
                  .flatMap((c) =>
                    c.exemplar_themes.map((theme) => ({
                      theme,
                      color: clusterColors[c.cluster_id],
                      clusterId: c.cluster_id,
                    })),
                  )
                  .map(({ theme, color, clusterId }, i) => (
                    <span
                      key={`${clusterId}-${i}`}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-caption font-sans text-cream-900 bg-cream-100 border border-[var(--border-default)]"
                    >
                      <span
                        className="h-1.5 w-1.5 rounded-full shrink-0"
                        style={{ backgroundColor: color }}
                      />
                      {theme}
                    </span>
                  ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export { ClusterRadarChart };
export type { ClusterRadarChartProps };
