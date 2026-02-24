'use client';

import { useRouter } from 'next/navigation';
import { Search, Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { useAppStore } from '@/stores/app-store';
import { useArtifactContent } from '@/lib/hooks/use-artifacts';
import { ResultsOverview } from './components/results-overview';
import type { GapReport } from '@/types/gap-analysis';

export default function SignalAnalysisPage() {
  const router = useRouter();
  const currentCompany = useAppStore((s) => s.currentCompany);
  const slug = currentCompany || 'webflow';

  const { data: report, loading, error } = useArtifactContent<GapReport>(
    'gap_analysis',
    slug,
    'gap_report.json'
  );

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
        {loading && <SignalAnalysisSkeleton />}

        {error && !loading && (
          <Card>
            <CardContent className="p-12 text-center">
              <Search className="h-12 w-12 text-cream-500 mx-auto mb-4" />
              <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-2">
                No analysis results yet
              </h3>
              <p className="text-body-sm text-cream-600 mb-4 max-w-md mx-auto">
                Run your first Deep Signal Analysis to understand how AI platforms cite your
                content and identify visibility gaps.
              </p>
              <Button onClick={() => router.push('/signal-analysis/run')}>
                <Plus className="h-4 w-4" />
                Run First Analysis
              </Button>
            </CardContent>
          </Card>
        )}

        {report && !loading && (
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
