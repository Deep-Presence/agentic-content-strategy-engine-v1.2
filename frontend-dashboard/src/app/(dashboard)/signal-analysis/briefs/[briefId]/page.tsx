'use client';

import { useMemo } from 'react';
import { useParams } from 'next/navigation';
import { Search } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { useAppStore } from '@/stores/app-store';
import { useArtifactContent } from '@/lib/hooks/use-artifacts';
import { GapBriefDetail } from '../../components/gap-brief-detail';
import type { GapReport } from '@/types/gap-analysis';

export default function BriefDetailPage() {
  const params = useParams<{ briefId: string }>();
  const briefId = params.briefId;
  const currentCompany = useAppStore((s) => s.currentCompany);
  const slug = currentCompany || 'webflow';

  const { data: report, loading, error } = useArtifactContent<GapReport>(
    'gap_analysis',
    slug,
    'gap_report.json'
  );

  const brief = useMemo(() => {
    if (!report) return null;
    return report.top_gaps.find((b) => b.query_id === briefId) ?? null;
  }, [report, briefId]);

  if (loading) {
    return (
      <div>
        <Skeleton className="h-6 w-32 mb-4" />
        <Skeleton className="h-10 w-3/4 mb-2" />
        <Skeleton className="h-6 w-1/2 mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-96 rounded-md" />
          <div className="lg:col-span-2 space-y-4">
            <Skeleton className="h-48 rounded-md" />
            <Skeleton className="h-48 rounded-md" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !brief) {
    return (
      <div>
        <PageHeader title="Gap Brief" />
        <Card className="mt-6">
          <CardContent className="p-12 text-center">
            <Search className="h-12 w-12 text-cream-500 mx-auto mb-4" />
            <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-2">
              Brief not found
            </h3>
            <p className="text-body-sm text-cream-600">
              The requested gap brief could not be found. It may have been removed or the analysis
              needs to be re-run.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <GapBriefDetail brief={brief} />;
}
