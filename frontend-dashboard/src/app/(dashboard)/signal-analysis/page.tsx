'use client';

import { useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, BarChart3, Search, Layers, Globe, FileText, Clock } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppStore } from '@/stores/app-store';
import { useArtifactContent } from '@/lib/hooks/use-artifacts';
import { WEBFLOW_GAP_REPORT } from '@/lib/data/webflow-fixtures';
import { SAMPLE_QUERIES } from './data/sample-data';
import type { GapReport } from '@/types/gap-analysis';

// Tab 1: Overview
import { SPAScoreHero } from './components/spa-score-hero';
import { GapClassificationCards } from './components/gap-classification-cards';
import ClusterPerformanceHeatmap from './components/cluster-performance-heatmap';
import { CitationAdvantageChart } from './components/citation-advantage-chart';
import { PlatformCitationDonuts } from './components/platform-citation-donuts';

// Tab 2: Query Intelligence
import QueryMasterTable from './components/query-master-table';
import GapDistributionCharts from './components/gap-distribution-charts';

// Tab 3: Structural Signals
import SignalCategoryCards from './components/signal-category-cards';
import SignalImportanceRanking from './components/signal-importance-ranking';
import ClusterSignalFingerprints from './components/cluster-signal-fingerprints';
import ContentPatternMatrix from './components/content-pattern-matrix';

// Tab 4: Platform Intelligence
import PlatformComparisonDashboard from './components/platform-comparison-dashboard';
import PlatformAgreementMatrix from './components/platform-agreement-matrix';
import PlatformTrendChart from './components/platform-trend-chart';

// Tab 5: Content Briefs
import BriefPriorityMatrix from './components/brief-priority-matrix';
import BriefCards from './components/brief-cards';
import ClusterRecommendations from './components/cluster-recommendations';

// Tab 6: Run History
import { RunHistoryTable } from './components/run-history-table';

export default function SignalAnalysisPage() {
  const router = useRouter();
  const currentCompany = useAppStore((s) => s.currentCompany);
  const slug = currentCompany || 'webflow';

  const { data: apiReport, loading, error } = useArtifactContent<GapReport>(
    'gap_analysis',
    slug,
    'gap_report.json'
  );

  const report = useMemo(() => {
    if (apiReport) return apiReport;
    if (slug === 'webflow' && (error || !loading)) return WEBFLOW_GAP_REPORT;
    return null;
  }, [apiReport, slug, error, loading]);

  const queries = SAMPLE_QUERIES;

  return (
    <div>
      <PageHeader
        title="Deep Signal Analysis"
        description={`AI Citation Intelligence for ${slug.charAt(0).toUpperCase() + slug.slice(1)}`}
        actions={
          <Button onClick={() => router.push('/signal-analysis/run')}>
            <Plus className="h-4 w-4" />
            Run New Analysis
          </Button>
        }
      />

      <Tabs defaultValue="overview" className="mt-6">
        <TabsList className="gap-1 overflow-x-auto">
          <TabsTrigger value="overview" className="gap-1.5">
            <BarChart3 className="h-3.5 w-3.5" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="queries" className="gap-1.5">
            <Search className="h-3.5 w-3.5" />
            Query Intelligence
          </TabsTrigger>
          <TabsTrigger value="signals" className="gap-1.5">
            <Layers className="h-3.5 w-3.5" />
            Structural Signals
          </TabsTrigger>
          <TabsTrigger value="platforms" className="gap-1.5">
            <Globe className="h-3.5 w-3.5" />
            Platform Intelligence
          </TabsTrigger>
          <TabsTrigger value="briefs" className="gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            Content Briefs
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            Run History
          </TabsTrigger>
        </TabsList>

        {/* ── Tab 1: Overview ── */}
        <TabsContent value="overview">
          <div className="space-y-6">
            <SPAScoreHero />
            <GapClassificationCards queries={queries} />
            <ClusterPerformanceHeatmap queries={queries} />
            <CitationAdvantageChart queries={queries} />
            <PlatformCitationDonuts />

            {/* Quick Actions */}
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => router.push('/signal-analysis/run')}>
                <Plus className="h-4 w-4" />
                Run New Analysis
              </Button>
              <Button variant="secondary" onClick={() => router.push('/embedding-lab')}>
                View in Embedding Lab
              </Button>
              <Button variant="secondary" onClick={() => router.push('/content-pipeline')}>
                Generate Content Briefs
              </Button>
            </div>
          </div>
        </TabsContent>

        {/* ── Tab 2: Query Intelligence ── */}
        <TabsContent value="queries">
          <div className="space-y-6">
            <QueryMasterTable queries={queries} />
            <GapDistributionCharts queries={queries} />
          </div>
        </TabsContent>

        {/* ── Tab 3: Structural Signals ── */}
        <TabsContent value="signals">
          <div className="space-y-6">
            <SignalCategoryCards />
            <SignalImportanceRanking />
            <ClusterSignalFingerprints />
            <ContentPatternMatrix />
          </div>
        </TabsContent>

        {/* ── Tab 4: Platform Intelligence ── */}
        <TabsContent value="platforms">
          <div className="space-y-6">
            <PlatformComparisonDashboard />
            <PlatformAgreementMatrix />
            <PlatformTrendChart />
          </div>
        </TabsContent>

        {/* ── Tab 5: Content Briefs ── */}
        <TabsContent value="briefs">
          <div className="space-y-6">
            <BriefPriorityMatrix queries={queries} />
            <BriefCards queries={queries} />
            <ClusterRecommendations />
          </div>
        </TabsContent>

        {/* ── Tab 6: Run History ── */}
        <TabsContent value="history">
          <div className="space-y-6">
            <RunHistoryTable />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
