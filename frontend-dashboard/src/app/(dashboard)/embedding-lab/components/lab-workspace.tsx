'use client';

import { useState, useEffect, useMemo } from 'react';
import { Dna, AlertCircle } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/stores/app-store';
import { artifacts } from '@/lib/api/artifacts';
import { EmbeddingScatter } from './embedding-scatter';
import { ClusterRadarChart } from './cluster-radar-chart';
import { GapHeatmapChart } from './gap-heatmap-chart';
import { CitationTreemapChart } from './citation-treemap-chart';
import { SignalInspectorPanel } from './signal-inspector-panel';
import { CitationSourceExplorer } from './citation-source-explorer';
import { SimilarityHistogramPanel } from './similarity-histogram';
import { CompanyVsCitationPanel } from './company-vs-citation';
import {
  SAMPLE_CLUSTERS,
  SAMPLE_EMBEDDING_POINTS,
  SAMPLE_GAP_BRIEFS,
  SAMPLE_EXEMPLARS,
  SAMPLE_HEATMAP_DATA,
  SAMPLE_DOMAIN_CITATIONS,
  SAMPLE_PLATFORM_DATA,
  SAMPLE_SIMILARITY_DATA,
  SAMPLE_COMPANY_VS_CITATION,
  CLUSTER_COLOR_MAP,
} from '../data/webflow-sample';
import type { ClusterSpec, GapBrief, GapReport } from '@/types/gap-analysis';

function LabWorkspace() {
  const currentCompany = useAppStore((s) => s.currentCompany);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gapReport, setGapReport] = useState<GapReport | null>(null);
  const [activeTab, setActiveTab] = useState('embedding');

  // Load data from API with fallback to sample data
  useEffect(() => {
    if (!currentCompany) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    async function loadData() {
      try {
        const report = await artifacts.getContent<GapReport>(
          'gap_analysis',
          currentCompany,
          'gap_report.json',
        );
        if (!cancelled) {
          setGapReport(report);
        }
      } catch {
        if (!cancelled) {
          setGapReport(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, [currentCompany]);

  // Use API data or fall back to sample data
  const clusters: ClusterSpec[] = gapReport?.clusters ?? SAMPLE_CLUSTERS;
  const gapBriefs: GapBrief[] = gapReport?.top_gaps ?? SAMPLE_GAP_BRIEFS;
  const clusterNames = clusters.map((c) => c.cluster_name);

  const heatmapData = useMemo(() => {
    if (gapReport) {
      return gapReport.top_gaps.flatMap((brief) =>
        clusters.map((cluster) => ({
          query_id: brief.query_id,
          query_text: brief.query_text,
          cluster: cluster.cluster_name,
          cluster_id: cluster.cluster_id,
          gap_score: brief.cluster_id === cluster.cluster_id ? brief.gap_score : brief.gap_score * 0.3,
          classification: brief.gap_classification,
        })),
      );
    }
    return SAMPLE_HEATMAP_DATA;
  }, [gapReport, clusters]);

  const exemplars = useMemo(() => {
    if (gapReport) {
      return gapReport.top_gaps.flatMap((brief) => brief.top_exemplars);
    }
    return SAMPLE_EXEMPLARS;
  }, [gapReport]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-1 border-b border-[var(--border-default)] pb-0">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-28" />
          ))}
        </div>
        <Skeleton className="h-[500px] w-full rounded-md" />
      </div>
    );
  }

  if (!currentCompany) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Dna className="h-12 w-12 text-cream-500 mb-4" />
        <h2 className="font-serif text-heading-3 text-cream-800 mb-2">No Company Selected</h2>
        <p className="text-body text-cream-600 max-w-md">
          Select a company from the sidebar to explore its embedding data and citation patterns.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-0">
      {!gapReport && (
        <div className="flex items-center gap-2 px-3 py-2 mb-4 bg-ocean-50 border border-ocean-200 rounded-md">
          <AlertCircle className="h-4 w-4 text-ocean-400 shrink-0" />
          <span className="text-body-sm font-sans text-ocean-500">
            Showing sample data for demonstration. Run a gap analysis on &quot;{currentCompany}&quot; to see real results.
          </span>
        </div>
      )}

      <Tabs defaultValue="embedding" onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="embedding">Embedding Space</TabsTrigger>
          <TabsTrigger value="clusters">Clusters</TabsTrigger>
          <TabsTrigger value="gap-map">Gap Map</TabsTrigger>
          <TabsTrigger value="citations">Citations</TabsTrigger>
          <TabsTrigger value="signals">Signals</TabsTrigger>
          <TabsTrigger value="platforms">Platform Breakdown</TabsTrigger>
        </TabsList>

        <TabsContent value="embedding" className="pt-6">
          <EmbeddingScatter
            points={SAMPLE_EMBEDDING_POINTS}
            clusters={clusters}
            gapBriefs={gapBriefs}
            clusterColors={CLUSTER_COLOR_MAP}
          />
        </TabsContent>

        <TabsContent value="clusters" className="pt-6">
          <ClusterRadarChart
            clusters={clusters}
            clusterColors={CLUSTER_COLOR_MAP}
          />
        </TabsContent>

        <TabsContent value="gap-map" className="pt-6">
          <GapHeatmapChart
            data={heatmapData}
            clusters={clusterNames}
            gapBriefs={gapBriefs}
          />
        </TabsContent>

        <TabsContent value="citations" className="pt-6">
          <div className="space-y-8">
            <CitationTreemapChart data={SAMPLE_DOMAIN_CITATIONS} />
            <SimilarityHistogramPanel
              histogramData={SAMPLE_SIMILARITY_DATA}
              comparisonData={SAMPLE_COMPANY_VS_CITATION}
            />
          </div>
        </TabsContent>

        <TabsContent value="signals" className="pt-6">
          <SignalInspectorPanel
            exemplars={exemplars}
            clusters={clusters}
          />
        </TabsContent>

        <TabsContent value="platforms" className="pt-6">
          <div className="space-y-8">
            <CitationSourceExplorer data={SAMPLE_PLATFORM_DATA} />
            <CompanyVsCitationPanel data={SAMPLE_COMPANY_VS_CITATION} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export { LabWorkspace };
