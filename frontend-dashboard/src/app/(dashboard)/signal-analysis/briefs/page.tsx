'use client';

import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { PageHeader } from '@/components/layout/page-header';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { useAppStore } from '@/stores/app-store';
import { useArtifactContent } from '@/lib/hooks/use-artifacts';
import { GapBriefTable } from '../components/gap-brief-table';
import type { GapReport } from '@/types/gap-analysis';

export default function BriefsListPage() {
  const currentCompany = useAppStore((s) => s.currentCompany);
  const slug = currentCompany || 'webflow';

  const { data: report, loading, error } = useArtifactContent<GapReport>(
    'gap_analysis',
    slug,
    'gap_report.json'
  );

  return (
    <div>
      <div className="mb-4">
        <Link
          href="/signal-analysis"
          className="inline-flex items-center gap-1 text-body-sm font-sans text-ocean-500 hover:text-ocean-600 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Signal Analysis
        </Link>
      </div>

      <PageHeader
        title="Gap Briefs"
        description={`All gap briefs for ${slug.charAt(0).toUpperCase() + slug.slice(1)}`}
      />

      <div className="mt-6">
        {loading && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        )}

        {error && !loading && (
          <Card>
            <CardContent className="p-8 text-center">
              <p className="text-body-sm text-cream-600">
                Failed to load gap briefs. Run a signal analysis first.
              </p>
            </CardContent>
          </Card>
        )}

        {report && !loading && (
          <GapBriefTable
            briefs={report.top_gaps}
            clusters={report.clusters.map((c) => ({
              cluster_id: c.cluster_id,
              cluster_name: c.cluster_name,
            }))}
          />
        )}
      </div>
    </div>
  );
}
