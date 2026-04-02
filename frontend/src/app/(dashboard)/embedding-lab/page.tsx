'use client';

import { useState, useCallback } from 'react';
import { TabBar } from '@/components/ui';
import { TerritoryControl } from './_components/territory-control';
import { ScatterExplorer } from './_components/scatter-explorer';
import { ClusterDeepDive } from './_components/cluster-deep-dive';
import { CorrelationAnalysis } from './_components/correlation-analysis';
import {
  CLUSTERS, GAP_SUMMARY, UMAP_PROJECTION, TSNE_PROJECTION,
} from './_components/embedding-lab-data';

const TABS = [
  { id: 'territory', label: 'Territory Control', closable: false },
  { id: 'scatter', label: 'Scatter Explorer', closable: false },
  { id: 'cluster', label: 'Cluster Deep Dive', closable: false },
  { id: 'correlation', label: 'Correlation Analysis', closable: false },
];

export default function EmbeddingLabPage() {
  const [activeTab, setActiveTab] = useState('territory');
  const [deepDiveClusterId, setDeepDiveClusterId] = useState<string | undefined>();

  const handleClusterClick = useCallback((clusterId: string) => {
    setDeepDiveClusterId(clusterId);
    setActiveTab('cluster');
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 mb-1">
        <h2 className="text-[20px] font-semibold text-text-primary tracking-[-0.02em] font-display">
          Deep Embedding Lab
        </h2>
        <span className="text-[10px] font-mono text-text-tertiary">
          {UMAP_PROJECTION.pointCount} points &middot; {CLUSTERS.length} clusters
        </span>
      </div>

      <TabBar
        tabs={TABS}
        activeTab={activeTab}
        onTabClick={setActiveTab}
      />

      <div className="mt-2">
        {activeTab === 'territory' && (
          <TerritoryControl
            clusters={CLUSTERS}
            summary={GAP_SUMMARY}
            onClusterClick={handleClusterClick}
          />
        )}
        {activeTab === 'scatter' && (
          <ScatterExplorer
            umapData={UMAP_PROJECTION}
            tsneData={TSNE_PROJECTION}
          />
        )}
        {activeTab === 'cluster' && (
          <ClusterDeepDive initialClusterId={deepDiveClusterId} />
        )}
        {activeTab === 'correlation' && (
          <CorrelationAnalysis />
        )}
      </div>
    </div>
  );
}
