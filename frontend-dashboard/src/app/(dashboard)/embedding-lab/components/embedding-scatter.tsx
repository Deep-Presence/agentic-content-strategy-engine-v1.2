'use client';

import { useState, useMemo, useCallback } from 'react';
import { Search } from 'lucide-react';
import { UmapScatter, type ScatterPoint } from '@/components/charts/umap-scatter';
import { TsneScatter } from '@/components/charts/tsne-scatter';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Card, CardContent } from '@/components/ui/card';
import { ChartLegend } from './chart-legend';
import { QueryDrillDown } from './query-drill-down';
import { cn } from '@/lib/utils/cn';
import type { EmbeddingPoint } from '../data/webflow-sample';
import type { GapBrief } from '@/types/gap-analysis';

interface EmbeddingScatterProps {
  points: EmbeddingPoint[];
  clusters: Array<{ cluster_id: string; cluster_name: string }>;
  gapBriefs: GapBrief[];
  clusterColors: Record<string, string>;
  className?: string;
}

type ReductionMethod = 'umap' | 'tsne';
type ColorMode = 'type' | 'cluster' | 'gap_score';

function EmbeddingScatter({
  points,
  clusters,
  gapBriefs,
  clusterColors,
  className,
}: EmbeddingScatterProps) {
  const [method, setMethod] = useState<ReductionMethod>('umap');
  const [colorBy, setColorBy] = useState<ColorMode>('type');
  const [selectedCluster, setSelectedCluster] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedBrief, setSelectedBrief] = useState<GapBrief | null>(null);

  const scatterPoints: ScatterPoint[] = useMemo(
    () =>
      points.map((p) => ({
        x: p.x,
        y: p.y,
        type: p.type,
        id: p.id,
        label: p.label,
        cluster: p.cluster,
        similarity: p.similarity,
        gapScore: p.gapScore,
      })),
    [points],
  );

  const clusterColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    clusters.forEach((c) => {
      map[c.cluster_name] = clusterColors[c.cluster_id] || '#b0aea5';
    });
    return map;
  }, [clusters, clusterColors]);

  const highlightedIds = useMemo(() => {
    if (!searchQuery.trim()) return undefined;
    const q = searchQuery.toLowerCase();
    return points
      .filter((p) => p.label.toLowerCase().includes(q))
      .map((p) => p.id);
  }, [searchQuery, points]);

  const handlePointClick = useCallback(
    (point: ScatterPoint) => {
      if (point.type === 'query') {
        const clusterId = points.find((p) => p.id === point.id)?.clusterId;
        const brief = gapBriefs.find(
          (b) => b.cluster_id === clusterId || b.query_text.includes(point.label),
        );
        if (brief) setSelectedBrief(brief);
      }
    },
    [points, gapBriefs],
  );

  const filterClusters = useMemo(
    () => [
      { label: 'All Clusters', value: '' },
      ...clusters.map((c) => ({ label: `${c.cluster_name} (${c.cluster_id})`, value: c.cluster_name })),
    ],
    [clusters],
  );

  const pointCounts = useMemo(() => {
    const counts = { query: 0, citation: 0, company: 0 };
    points.forEach((p) => counts[p.type]++);
    return counts;
  }, [points]);

  const ScatterComponent = method === 'umap' ? UmapScatter : TsneScatter;

  return (
    <div className={cn('flex gap-4', className)}>
      {/* Main scatter area */}
      <div className="flex-1 space-y-3">
        {/* Controls row */}
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="reduction"
                value="umap"
                checked={method === 'umap'}
                onChange={() => setMethod('umap')}
                className="accent-terracotta-400"
              />
              <span className="text-body-sm font-sans text-cream-800">UMAP</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="reduction"
                value="tsne"
                checked={method === 'tsne'}
                onChange={() => setMethod('tsne')}
                className="accent-terracotta-400"
              />
              <span className="text-body-sm font-sans text-cream-800">t-SNE</span>
            </label>
          </div>

          <Select
            value={colorBy}
            onChange={(e) => setColorBy(e.target.value as ColorMode)}
            label="Color by"
          >
            <option value="type">Embedding Type</option>
            <option value="cluster">Cluster</option>
            <option value="gap_score">Gap Score</option>
          </Select>

          <Select
            value={selectedCluster}
            onChange={(e) => setSelectedCluster(e.target.value)}
            label="Filter cluster"
          >
            {filterClusters.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </Select>

          <div className="relative flex-1 min-w-[180px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-cream-600 pointer-events-none" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search embeddings..."
              className="pl-8"
            />
          </div>
        </div>

        {/* Legend */}
        <ChartLegend
          items={[
            { label: `Queries (${pointCounts.query})`, color: '#6a9bcc', shape: 'circle' },
            { label: `Citations (${pointCounts.citation})`, color: '#d97757', shape: 'triangle' },
            { label: `Company (${pointCounts.company})`, color: '#788c5d', shape: 'square' },
          ]}
        />

        {/* Scatter plot */}
        <ScatterComponent
          points={scatterPoints}
          colorBy={colorBy}
          selectedCluster={selectedCluster || undefined}
          highlightedIds={highlightedIds}
          onPointClick={handlePointClick}
          clusterColors={clusterColorMap}
          width={selectedBrief ? 600 : 800}
          height={500}
        />
      </div>

      {/* Drill-down panel */}
      {selectedBrief && (
        <QueryDrillDown
          brief={selectedBrief}
          onClose={() => setSelectedBrief(null)}
          className="w-[340px] shrink-0"
        />
      )}
    </div>
  );
}

export { EmbeddingScatter };
export type { EmbeddingScatterProps };
