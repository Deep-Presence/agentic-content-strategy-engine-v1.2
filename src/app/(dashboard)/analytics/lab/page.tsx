'use client';

import { useState, useEffect, useMemo } from 'react';
import { TabBar, Skeleton } from '@/components/ui';
import { getGapReport } from '@/data/gap-report';
import type { EmbeddingPoint } from '@/types';
import { SpaceOverview } from './_components/SpaceOverview';
import { ClusterDeepDive } from './_components/ClusterDeepDive';
import { QueryMicroscope } from './_components/QueryMicroscope';
import { Simulation } from './_components/Simulation';
import genSpecRaw from '../../../../../data/artifacts/gap_analysis/lovable/generation_spec.json';

const TABS = [
  { id: 'overview', label: 'Space Overview', closable: false },
  { id: 'cluster', label: 'Cluster Deep-Dive', closable: false },
  { id: 'microscope', label: 'Query Microscope', closable: false },
  { id: 'simulation', label: 'Simulation', closable: false },
];

interface GenSpecData {
  cluster_specs: Array<{
    cluster_name: string;
    query_count: number;
    avg_word_count: number | null;
    faq_rate: number;
    table_rate: number;
    dominant_content_type: string;
  }>;
}

export default function EmbeddingLabPage() {
  const report = useMemo(() => getGapReport(), []);
  const [activeView, setActiveView] = useState('overview');
  const [tsnePoints, setTsnePoints] = useState<EmbeddingPoint[] | null>(null);
  const [umapPoints, setUmapPoints] = useState<EmbeddingPoint[] | null>(null);
  const [loading, setLoading] = useState(true);

  // Load embedding data on client side to avoid large JSON at module scope
  useEffect(() => {
    let cancelled = false;
    async function loadData() {
      const [tsne, umap] = await Promise.all([
        import('../../../../../data/artifacts/gap_analysis/lovable/visualizations/embedding_projections_tsne.json'),
        import('../../../../../data/artifacts/gap_analysis/lovable/visualizations/embedding_projections_umap.json'),
      ]);

      if (cancelled) return;

      const parse = (data: { points: Array<{ id: string; type: string; x: number; y: number; cluster: string; label: string; similarity?: number }> }) =>
        data.points.map((p) => ({
          id: p.id,
          type: p.type as EmbeddingPoint['type'],
          x: p.x,
          y: p.y,
          cluster: p.cluster,
          label: p.label,
          url: p.type === 'citation' ? p.label : undefined,
          similarity: p.similarity,
        }));

      setTsnePoints(parse(tsne.default as typeof tsne.default));
      setUmapPoints(parse(umap.default as typeof umap.default));
      setLoading(false);
    }
    loadData();
    return () => { cancelled = true; };
  }, []);

  const clusters = useMemo(() => {
    return Array.from(new Set(report.queries.map((q) => q.cluster)));
  }, [report.queries]);

  const clusterStats = useMemo(() => {
    const specs = (genSpecRaw as unknown as GenSpecData).cluster_specs;
    const map: Record<string, {
      queryCount: number;
      avgWordCount: number | null;
      faqRate: number;
      tableRate: number;
      dominantContentType: string;
    }> = {};
    specs.forEach((s) => {
      map[s.cluster_name] = {
        queryCount: s.query_count,
        avgWordCount: s.avg_word_count,
        faqRate: s.faq_rate,
        tableRate: s.table_rate,
        dominantContentType: s.dominant_content_type,
      };
    });
    return map;
  }, []);

  if (loading || !tsnePoints || !umapPoints) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="text-[20px] font-semibold text-text-primary tracking-[-0.02em]">
            Deep Embedding Lab
          </h2>
        </div>
        <Skeleton variant="rectangular" height="500px" width="100%" />
        <div className="grid grid-cols-3 gap-4">
          <Skeleton variant="rectangular" height="200px" />
          <Skeleton variant="rectangular" height="200px" />
          <Skeleton variant="rectangular" height="200px" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <h2 className="text-[20px] font-semibold text-text-primary tracking-[-0.02em]">
          Deep Embedding Lab
        </h2>
        <span className="text-[10px] font-mono text-text-tertiary">
          {tsnePoints.length} points
        </span>
      </div>

      <TabBar
        tabs={TABS}
        activeTab={activeView}
        onTabClick={setActiveView}
      />

      <div className="mt-2">
        {activeView === 'overview' && (
          <SpaceOverview
            tsnePoints={tsnePoints}
            umapPoints={umapPoints}
            clusters={clusters}
          />
        )}
        {activeView === 'cluster' && (
          <ClusterDeepDive
            points={tsnePoints}
            clusters={clusters}
            clusterStats={clusterStats}
          />
        )}
        {activeView === 'microscope' && (
          <QueryMicroscope
            points={tsnePoints}
            queries={report.queries}
          />
        )}
        {activeView === 'simulation' && (
          <Simulation queries={report.queries} />
        )}
      </div>
    </div>
  );
}
