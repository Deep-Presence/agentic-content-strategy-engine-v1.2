'use client';

import { useState, useMemo } from 'react';
import { TabBar, Skeleton } from '@/components/ui';
import { useAuthStore } from '@/stores/auth';
import { useEmbeddings, useGapClusters } from '@/lib/hooks/useGapAnalysis';
import type { EmbeddingPoint } from '@/types';
import { SpaceOverview } from './_components/SpaceOverview';
import { ClusterDeepDive } from './_components/ClusterDeepDive';
import { QueryMicroscope } from './_components/QueryMicroscope';
import { Simulation } from './_components/Simulation';

const TABS = [
  { id: 'overview', label: 'Space Overview', closable: false },
  { id: 'cluster', label: 'Cluster Deep-Dive', closable: false },
  { id: 'microscope', label: 'Query Microscope', closable: false },
  { id: 'simulation', label: 'Simulation', closable: false },
];

export default function EmbeddingLabPage() {
  const slug = useAuthStore((s) => s.company?.slug);
  const { data: tsneData, isLoading: tsneLoading } = useEmbeddings(slug, 'tsne');
  const { data: umapData, isLoading: umapLoading } = useEmbeddings(slug, 'umap');
  const { data: clustersData } = useGapClusters(slug);

  const [activeView, setActiveView] = useState('overview');

  const tsnePoints = useMemo<EmbeddingPoint[] | null>(() => {
    if (!tsneData?.points) return null;
    return tsneData.points.map((p) => ({
      id: p.id ?? '',
      type: p.type as EmbeddingPoint['type'],
      x: p.x,
      y: p.y,
      cluster: p.cluster ?? '',
      label: p.label ?? '',
      url: p.type === 'citation' ? p.label : undefined,
      similarity: p.similarity,
    }));
  }, [tsneData]);

  const umapPoints = useMemo<EmbeddingPoint[] | null>(() => {
    if (!umapData?.points) return null;
    return umapData.points.map((p) => ({
      id: p.id ?? '',
      type: p.type as EmbeddingPoint['type'],
      x: p.x,
      y: p.y,
      cluster: p.cluster ?? '',
      label: p.label ?? '',
      url: p.type === 'citation' ? p.label : undefined,
      similarity: p.similarity,
    }));
  }, [umapData]);

  const clusters = useMemo(() => {
    return (clustersData?.clusters ?? []).map((c) => c.cluster_name);
  }, [clustersData]);

  const clusterStats = useMemo(() => {
    const map: Record<string, {
      queryCount: number;
      avgWordCount: number | null;
      faqRate: number;
      tableRate: number;
      dominantContentType: string;
    }> = {};
    (clustersData?.clusters ?? []).forEach((s) => {
      map[s.cluster_name] = {
        queryCount: s.query_count,
        avgWordCount: s.avg_word_count,
        faqRate: s.faq_rate,
        tableRate: s.table_rate,
        dominantContentType: s.dominant_content_type ?? '',
      };
    });
    return map;
  }, [clustersData]);

  const loading = tsneLoading || umapLoading;

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
            queries={[]}
          />
        )}
        {activeView === 'simulation' && (
          <Simulation queries={[]} />
        )}
      </div>
    </div>
  );
}
