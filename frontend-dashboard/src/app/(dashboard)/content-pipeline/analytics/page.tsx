'use client';

import { useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/layout/page-header';
import { useContentStore } from '@/stores/content-store';
import { AnalyticsCharts } from '../components/analytics-charts';

export default function ContentAnalyticsPage() {
  const { briefs } = useContentStore();

  const stats = useMemo(() => {
    const published = briefs.filter((b) => b.status === 'published').length;
    const inProgress = briefs.filter((b) =>
      ['research', 'drafting', 'enriching', 'formatting', 'evaluating', 'review'].includes(b.status)
    ).length;
    const scores = briefs
      .filter((b) => b.citability_score != null)
      .map((b) => b.citability_score as number);
    const avgScore = scores.length > 0
      ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
      : 0;

    return { published, inProgress, avgScore, velocity: '6.5' };
  }, [briefs]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Content Analytics"
        description="Metrics and trends about content production"
      />

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="text-center py-5">
            <p className="text-caption font-sans font-semibold text-cream-600 uppercase tracking-wider mb-1">
              Published
            </p>
            <p className="font-serif text-display text-sage-400 tabular-nums">
              {stats.published}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-5">
            <p className="text-caption font-sans font-semibold text-cream-600 uppercase tracking-wider mb-1">
              In Progress
            </p>
            <p className="font-serif text-display text-ocean-400 tabular-nums">
              {stats.inProgress}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-5">
            <p className="text-caption font-sans font-semibold text-cream-600 uppercase tracking-wider mb-1">
              Avg Citability
            </p>
            <p className="font-serif text-display text-terracotta-400 tabular-nums">
              {stats.avgScore}%
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-5">
            <p className="text-caption font-sans font-semibold text-cream-600 uppercase tracking-wider mb-1">
              Velocity
            </p>
            <p className="font-serif text-display text-cream-800 tabular-nums">
              {stats.velocity}/wk
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <AnalyticsCharts briefs={briefs} />
    </div>
  );
}
