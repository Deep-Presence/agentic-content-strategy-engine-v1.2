'use client';

import { useMemo } from 'react';
import { Activity } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/page-header';
import {
  WEBFLOW_CITABILITY_SCORE,
  WEBFLOW_SPA_SCORE,
  WEBFLOW_CLUSTERS,
  WEBFLOW_TOP_GAPS,
  WEBFLOW_PIPELINE_BRIEFS,
  WEBFLOW_ACTIVE_CYCLE,
  WEBFLOW_TASKS,
  WEBFLOW_COMPANIES,
  CITABILITY_TREND_DATA,
  VELOCITY_TREND_DATA,
} from '@/lib/data/webflow-fixtures';
import { HeroHealthBar } from './components/hero-health-bar';
import { VisibilityTrendPanel } from './components/visibility-trend-panel';
import { PipelineStatusPanel } from './components/pipeline-status-panel';
import { PlatformPerformanceGrid } from './components/platform-performance-grid';
import { ClusterHealthMatrix } from './components/cluster-health-matrix';
import { PriorityActionsPanel } from './components/priority-actions-panel';
import { ActivityFeedPanel } from './components/activity-feed-panel';
import { ContentPerformanceRow } from './components/content-performance-row';
import { CompetitiveSnapshotPanel } from './components/competitive-snapshot-panel';
import { QuickLinksFooter } from './components/quick-links-footer';
import type { PlatformData } from './components/platform-performance-grid';
import type { ActivityEvent } from './components/activity-feed-panel';
import type { CompetitorRow } from './components/competitive-snapshot-panel';

// ─── 12-week visibility trend (Dec → Feb) ────────────────────────────────────
const VISIBILITY_TREND_12W = [
  { week: 'Dec 2', score: 18 },
  { week: 'Dec 9', score: 20 },
  { week: 'Dec 16', score: 22 },
  { week: 'Dec 23', score: 21 },
  { week: 'Dec 30', score: 24 },
  { week: 'Jan 6', score: 28 },
  { week: 'Jan 13', score: 30 },
  { week: 'Jan 20', score: 29 },
  { week: 'Jan 27', score: 31 },
  { week: 'Feb 3', score: 32 },
  { week: 'Feb 10', score: 33 },
  { week: 'Feb 17', score: 34 },
];

// ─── Platform performance (hardcoded — not in fixtures) ──────────────────────
const PLATFORM_DATA: PlatformData[] = [
  {
    name: 'ChatGPT',
    icon: '⬛',
    citationShare: 0.28,
    trend: 'up',
    trendPct: 0.04,
    color: '#141413',
    sparklineData: [
      { week: 'Jan 6', value: 22 }, { week: 'Jan 13', value: 24 },
      { week: 'Jan 20', value: 23 }, { week: 'Jan 27', value: 25 },
      { week: 'Feb 3', value: 26 }, { week: 'Feb 10', value: 27 },
      { week: 'Feb 17', value: 28 }, { week: 'Feb 24', value: 28 },
    ],
  },
  {
    name: 'Claude',
    icon: '◈',
    citationShare: 0.31,
    trend: 'up',
    trendPct: 0.06,
    color: '#d97757',
    sparklineData: [
      { week: 'Jan 6', value: 25 }, { week: 'Jan 13', value: 26 },
      { week: 'Jan 20', value: 27 }, { week: 'Jan 27', value: 28 },
      { week: 'Feb 3', value: 29 }, { week: 'Feb 10', value: 30 },
      { week: 'Feb 17', value: 30 }, { week: 'Feb 24', value: 31 },
    ],
  },
  {
    name: 'Perplexity',
    icon: '◎',
    citationShare: 0.22,
    trend: 'flat',
    trendPct: 0.01,
    color: '#6a9bcc',
    sparklineData: [
      { week: 'Jan 6', value: 21 }, { week: 'Jan 13', value: 22 },
      { week: 'Jan 20', value: 21 }, { week: 'Jan 27', value: 22 },
      { week: 'Feb 3', value: 23 }, { week: 'Feb 10', value: 22 },
      { week: 'Feb 17', value: 22 }, { week: 'Feb 24', value: 22 },
    ],
  },
  {
    name: 'Gemini',
    icon: '✦',
    citationShare: 0.19,
    trend: 'down',
    trendPct: -0.02,
    color: '#788c5d',
    sparklineData: [
      { week: 'Jan 6', value: 21 }, { week: 'Jan 13', value: 20 },
      { week: 'Jan 20', value: 21 }, { week: 'Jan 27', value: 20 },
      { week: 'Feb 3', value: 19 }, { week: 'Feb 10', value: 19 },
      { week: 'Feb 17', value: 19 }, { week: 'Feb 24', value: 19 },
    ],
  },
];

// ─── Activity events (hardcoded — derived from fixture timestamps) ───────────
const ACTIVITY_EVENTS: ActivityEvent[] = [
  { id: 'ev-01', timestamp: '2026-02-23T08:15:00Z', type: 'pipeline_complete', title: 'Content pipeline started', detail: 'Webflow — drafting "Core Web Vitals Guide"', href: '/content-pipeline' },
  { id: 'ev-02', timestamp: '2026-02-22T16:00:00Z', type: 'review_ready', title: 'Brief ready for review', detail: 'No-Code vs Headless CMS vs Next.js — C3: Category Comparison', href: '/content-pipeline/brief-004' },
  { id: 'ev-03', timestamp: '2026-02-20T11:00:00Z', type: 'review_ready', title: 'Brief ready for review', detail: 'Headless CMS for Marketing Teams — Score: 78', href: '/content-pipeline/brief-003' },
  { id: 'ev-04', timestamp: '2026-02-18T23:46:00Z', type: 'pipeline_complete', title: 'Gap analysis completed', detail: 'Webflow — 72 queries, 1,422 citations, 25 gaps', href: '/signal-analysis' },
  { id: 'ev-05', timestamp: '2026-02-18T20:00:00Z', type: 'gap_identified', title: 'Gap analysis started', detail: 'Webflow — 9 clusters, 4 AI platforms' },
  { id: 'ev-06', timestamp: '2026-02-17T15:00:00Z', type: 'published', title: 'Article published', detail: 'Webflow vs Framer vs HubSpot CMS — Score: 89', href: '/content-pipeline/brief-011' },
  { id: 'ev-07', timestamp: '2026-02-15T12:30:00Z', type: 'pipeline_complete', title: 'Research pipeline completed', detail: 'Webflow — company context, personas, style guide', href: '/brand-brain' },
  { id: 'ev-08', timestamp: '2026-02-14T09:00:00Z', type: 'published', title: 'Article published', detail: 'Product Page Optimization — Score: 74', href: '/content-pipeline/brief-009' },
  { id: 'ev-09', timestamp: '2026-02-13T11:00:00Z', type: 'published', title: 'Article published', detail: 'What Is a Design System? — Score: 82', href: '/content-pipeline/brief-002' },
  { id: 'ev-10', timestamp: '2026-02-12T14:00:00Z', type: 'published', title: 'Article published', detail: 'Webflow vs WordPress for Enterprise — Score: 87', href: '/content-pipeline/brief-001' },
];

export default function CommandCenterPage() {
  const reviewBriefs = useMemo(
    () => WEBFLOW_PIPELINE_BRIEFS.filter((b) => b.status === 'review'),
    []
  );
  const publishedBriefs = useMemo(
    () => WEBFLOW_PIPELINE_BRIEFS.filter((b) => b.status === 'published'),
    []
  );
  const runningTasks = useMemo(
    () => WEBFLOW_TASKS.filter((t) => t.status === 'running'),
    []
  );

  const statusCounts = useMemo(() => {
    const counts = { published: 0, review: 0, inProgress: 0, evaluating: 0, queued: 0 };
    for (const b of WEBFLOW_PIPELINE_BRIEFS) {
      if (b.status === 'published') counts.published++;
      else if (b.status === 'review') counts.review++;
      else if (b.status === 'drafting' || b.status === 'enriching' || b.status === 'formatting') counts.inProgress++;
      else if (b.status === 'evaluating') counts.evaluating++;
      else if (b.status === 'suggested' || b.status === 'approved') counts.queued++;
    }
    return counts;
  }, []);

  const competitors: CompetitorRow[] = useMemo(() => {
    const domainMap = new Map<string, CompetitorRow>();
    for (const g of WEBFLOW_TOP_GAPS) {
      const existing = domainMap.get(g.top_domain);
      if (!existing) {
        domainMap.set(g.top_domain, {
          domain: g.top_domain,
          cluster: g.cluster,
          gap: g.gap,
          exemplarSim: g.top_exemplar_sim,
          topQueries: 1,
        });
      } else {
        existing.topQueries += 1;
        if (g.gap > existing.gap) {
          existing.gap = g.gap;
          existing.cluster = g.cluster;
          existing.exemplarSim = g.top_exemplar_sim;
        }
      }
    }
    return Array.from(domainMap.values())
      .sort((a, b) => b.exemplarSim - a.exemplarSim)
      .slice(0, 8);
  }, []);

  const gapItems = useMemo(
    () => WEBFLOW_TOP_GAPS.map((g) => ({
      id: g.id,
      query: g.query,
      cluster: g.cluster,
      gap: g.gap,
    })),
    []
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mission Control"
        description="AI Visibility Intelligence · Webflow"
        actions={
          <Link href="/signal-analysis/run">
            <Button variant="primary" size="md">
              <Activity className="h-4 w-4" />
              Run Analysis
            </Button>
          </Link>
        }
      />

      {/* Section 1: Hero Health Bar */}
      <HeroHealthBar
        citabilityScore={WEBFLOW_CITABILITY_SCORE}
        spaScore={WEBFLOW_SPA_SCORE.score}
        totalQueries={WEBFLOW_SPA_SCORE.total_queries}
        totalCitations={WEBFLOW_SPA_SCORE.total_citations}
        publishedCount={publishedBriefs.length}
        gapCount={WEBFLOW_TOP_GAPS.length}
      />

      {/* Section 2: Visibility Trend + Pipeline Status */}
      <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-6">
        <VisibilityTrendPanel data={VISIBILITY_TREND_12W} />
        <PipelineStatusPanel
          tasks={WEBFLOW_TASKS}
          activeCycle={WEBFLOW_ACTIVE_CYCLE}
          statusCounts={statusCounts}
        />
      </div>

      {/* Section 3: Platform Performance */}
      <PlatformPerformanceGrid platforms={PLATFORM_DATA} />

      {/* Section 4: Cluster Health Matrix */}
      <ClusterHealthMatrix clusters={WEBFLOW_CLUSTERS} />

      {/* Section 5: Priority Actions + Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PriorityActionsPanel
          reviewBriefs={reviewBriefs}
          runningTasks={runningTasks}
          topGaps={gapItems}
          publishedBriefs={publishedBriefs}
        />
        <ActivityFeedPanel events={ACTIVITY_EVENTS} />
      </div>

      {/* Section 6: Content Performance */}
      <ContentPerformanceRow
        citabilityTrend={CITABILITY_TREND_DATA}
        velocityTrend={VELOCITY_TREND_DATA}
        briefs={WEBFLOW_PIPELINE_BRIEFS}
      />

      {/* Section 7: Competitive Snapshot */}
      <CompetitiveSnapshotPanel competitors={competitors} />

      {/* Section 8: Quick Links */}
      <QuickLinksFooter />
    </div>
  );
}
