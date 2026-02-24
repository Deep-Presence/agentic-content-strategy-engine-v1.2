'use client';

import { useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/stores/app-store';
import { useArtifactContent } from '@/lib/hooks/use-artifacts';
import { ResultsOverview } from './components/results-overview';
import { WEBFLOW_GAP_REPORT } from '@/lib/data/webflow-fixtures';
import type { GapReport } from '@/types/gap-analysis';

export default function SignalAnalysisPage() {
  const router = useRouter();
  const currentCompany = useAppStore((s) => s.currentCompany);
  const slug = currentCompany || 'webflow';

  const { data: apiReport, loading, error } = useArtifactContent<GapReport>(
    'gap_analysis',
    slug,
    'gap_report.json'
  );

  // Use API data when available, fall back to fixture data for Webflow
  const report = useMemo(() => {
    if (apiReport) return apiReport;
    if (slug === 'webflow' && (error || !loading)) return WEBFLOW_GAP_REPORT;
    return null;
  }, [apiReport, slug, error, loading]);

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

      <div className="mt-6">
        {loading && !report && <SignalAnalysisSkeleton />}

        {report && (
          <ResultsOverview report={report} companySlug={slug} />
        )}
      </div>
    </div>
  );
}

function SignalAnalysisSkeleton() {
  return (
    <div className="space-y-8">
      {/* SPA Score skeleton */}
      <Skeleton className="h-48 w-full rounded-md" />

      {/* Cluster grid skeleton */}
      <div>
        <Skeleton className="h-7 w-48 mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <Skeleton key={i} className="h-44 rounded-md" />
          ))}
        </div>
      </div>

      {/* Table skeleton */}
      <div>
        <Skeleton className="h-7 w-40 mb-4" />
        <Skeleton className="h-10 w-full mb-2" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full mb-1" />
        ))}
      </div>
    </div>
  );
}
