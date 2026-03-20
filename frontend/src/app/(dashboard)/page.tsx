'use client';

import { useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { EmptyState, Skeleton } from '@/components/ui';
import { ActiveTasks } from './_components/home/ActiveTasks';
import { HITLReviews } from './_components/home/HITLReviews';
import { RecentActivity } from './_components/home/RecentActivity';
import { RecommendedActions } from './_components/home/RecommendedActions';
import { useAuthStore } from '@/stores/auth';
import { useApiQuery } from '@/lib/hooks/useApiQuery';
import { useGapSummary } from '@/lib/hooks/useGapAnalysis';
import { GAP_DATA, CONTENT_DATA, SITE_AUDIT, TASKS } from '@/lib/api/endpoints';
import type { QueryListResponse } from '@/lib/api/types';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function formatDate(): string {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

interface KPI {
  label: string;
  value: string;
  delta: string;
  deltaType: 'positive' | 'negative' | 'neutral';
}

export default function HomePage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const company = useAuthStore((s) => s.company);
  const slug = company?.slug;

  const companyName = company?.name ?? '';
  const companyDomain = company?.domain ?? '';

  const { data: gapData, isLoading: gapLoading } = useGapSummary(slug);

  // Top gap queries for the recommendations section
  const { data: topGapsData } = useApiQuery<QueryListResponse>(
    slug ? `${GAP_DATA.queries(slug)}?classification=significant_gap&sort_by=gap_score&sort_dir=desc&page_size=10` : null,
  );

  const { data: briefsData, isLoading: briefsLoading } = useApiQuery<{
    briefs: { status: string }[];
    total: number;
  }>(slug ? CONTENT_DATA.briefs(slug) : null);

  const { data: auditsData, isLoading: auditsLoading } = useApiQuery<
    { id: string; result?: { overall_score?: number } }[]
  >(slug ? SITE_AUDIT.audits(slug) : null);

  const { data: tasksData, isLoading: tasksLoading } = useApiQuery<
    { task_id: string }[]
  >(`${TASKS.list}?status=running`);

  const loading = gapLoading || briefsLoading || auditsLoading || tasksLoading;

  const hasData = !!(
    gapData ||
    (briefsData && briefsData.total > 0) ||
    (auditsData && Array.isArray(auditsData) && auditsData.length > 0)
  );

  const kpis = useMemo<KPI[]>(() => {
    if (!hasData) return [];

    const publishedCount = briefsData?.briefs?.filter((b) => b.status === 'published').length ?? 0;
    const totalQueries = gapData?.total_queries ?? 0;
    const totalCitations = gapData?.total_citations ?? 0;
    const activeTaskCount = Array.isArray(tasksData) ? tasksData.length : 0;

    const result: KPI[] = [
      {
        label: 'Published',
        value: String(publishedCount),
        delta: briefsData ? `${briefsData.total} total briefs` : '',
        deltaType: 'neutral',
      },
      {
        label: 'Queries Tracked',
        value: totalQueries.toLocaleString(),
        delta: gapData ? `${gapData.spa_score?.t_stat?.toFixed(1) ?? '—'} SPA` : '',
        deltaType: 'neutral',
      },
      {
        label: 'Total Citations',
        value: totalCitations.toLocaleString(),
        delta: '',
        deltaType: 'neutral',
      },
      {
        label: 'Avg Gap',
        value: gapData?.average_gap?.toFixed(2) ?? '—',
        delta: '',
        deltaType: 'neutral',
      },
      {
        label: 'Active Tasks',
        value: String(activeTaskCount),
        delta: activeTaskCount > 0 ? 'running' : 'idle',
        deltaType: activeTaskCount > 0 ? 'positive' : 'neutral',
      },
      {
        label: 'AEO Score',
        value: '—',
        delta: '/100',
        deltaType: 'neutral',
      },
    ];

    // Try to get AEO score from latest audit
    if (auditsData && Array.isArray(auditsData) && auditsData.length > 0) {
      const latest = auditsData[0];
      const score = (latest as Record<string, unknown>).result;
      if (score && typeof score === 'object' && 'overall_score' in (score as Record<string, unknown>)) {
        const s = (score as Record<string, unknown>).overall_score;
        if (typeof s === 'number') {
          result[5] = { label: 'AEO Score', value: s.toFixed(1), delta: '/100', deltaType: 'neutral' };
        }
      }
    }

    return result;
  }, [gapData, briefsData, auditsData, tasksData, hasData]);

  if (loading) {
    return (
      <div className="max-w-[960px] mx-auto space-y-6">
        <Skeleton className="h-[60px] w-[300px]" />
        <div className="grid grid-cols-6 gap-[1px]">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[80px]" />
          ))}
        </div>
        <Skeleton className="h-[200px] rounded-md" />
        <div className="grid grid-cols-2 gap-6">
          <Skeleton className="h-[300px]" />
          <Skeleton className="h-[300px]" />
        </div>
      </div>
    );
  }

  if (!hasData) {
    return (
      <EmptyState
        title="Welcome to Deep Presence"
        description="Start by analyzing your brand to see how you're cited across AI platforms."
        action={{
          label: 'Begin Analysis',
          onClick: () => router.push('/onboarding'),
        }}
      />
    );
  }

  const firstName = user?.first_name ?? '';

  return (
    <div className="max-w-[960px] mx-auto space-y-6">
      {/* Welcome header */}
      <div>
        <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-0.5">
          {getGreeting()}{firstName ? `, ${firstName}` : ''}
        </h1>
        <p className="text-[14px] text-text-secondary leading-[1.6]">
          {formatDate()}
        </p>
      </div>

      {/* Outcomes Strip — KPIs */}
      {kpis.length > 0 && (
        <div
          className="grid gap-[1px] bg-border rounded-sm overflow-hidden"
          style={{ gridTemplateColumns: `repeat(${kpis.length}, 1fr)` }}
        >
          {kpis.map((kpi) => (
            <div key={kpi.label} className="bg-bg px-3 py-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary leading-[1.4]">
                {kpi.label}
              </p>
              <div className="flex items-baseline gap-1.5 mt-1">
                <p className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary">
                  {kpi.value}
                </p>
                {kpi.delta && (
                  <p className={`text-[11px] font-medium ${
                    kpi.deltaType === 'positive' ? 'text-success' : 'text-text-tertiary'
                  }`}>
                    {kpi.delta}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Recommended Actions from Gap Analysis */}
      {gapData?.recommendations && gapData.recommendations.length > 0 && slug && (
        <RecommendedActions
          recommendations={gapData.recommendations}
          executiveSummary={gapData.executive_summary ?? ''}
          slug={slug}
          companyName={companyName}
          companyDomain={companyDomain}
          topGapQueries={topGapsData?.queries}
        />
      )}

      {/* Two-column layout for tasks + reviews */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ActiveTasks />
        <HITLReviews />
      </div>

      {/* Recent Activity */}
      <RecentActivity />
    </div>
  );
}
