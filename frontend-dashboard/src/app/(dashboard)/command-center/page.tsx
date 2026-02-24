'use client';

import Link from 'next/link';
import {
  TrendingDown,
  Activity,
  FileText,
  Search,
  Layers,
  Building2,
  ArrowRight,
  AlertCircle,
  Clock,
  Eye,
} from 'lucide-react';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { PageHeader } from '@/components/layout/page-header';
import {
  WEBFLOW_CITABILITY_SCORE,
  WEBFLOW_CITATION_TREND,
  WEBFLOW_CYCLES,
  WEBFLOW_TASKS,
  WEBFLOW_CONTENT_BRIEFS,
  WEBFLOW_CLUSTERS,
  WEBFLOW_SPA_SCORE,
  WEBFLOW_TOP_GAPS,
  WEBFLOW_COMPANIES,
} from '@/lib/data/webflow-fixtures';
import { formatPercent } from '@/lib/utils/format';

export default function CommandCenterPage() {
  const citabilityScore = WEBFLOW_CITABILITY_SCORE;
  const trend = WEBFLOW_CITATION_TREND;
  const activeCycle = WEBFLOW_CYCLES.active;
  const tasks = WEBFLOW_TASKS;
  const briefsAwaitingReview = WEBFLOW_CONTENT_BRIEFS.filter(
    (b) => b.status === 'review'
  );

  const runningTasks = tasks.filter((t) => t.status === 'running');
  const completedTasks = tasks.filter((t) => t.status === 'completed');

  return (
    <div className="space-y-8">
      <PageHeader
        title="Command Center"
        description="Overview for Webflow"
        actions={
          <Button variant="primary" size="md">
            <Activity className="h-4 w-4" />
            Run Analysis
          </Button>
        }
      />

      {/* Row 1: Hero Citability Score */}
      <Card className="overflow-hidden border-error/30">
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-2">
                Citability Score
              </p>
              <div className="flex items-baseline gap-3">
                <span className="font-serif text-[3.5rem] leading-none font-semibold text-error">
                  {citabilityScore}%
                </span>
                <span className="flex items-center gap-1 text-body-sm font-sans font-medium text-error">
                  <TrendingDown className="h-4 w-4" />
                  Low
                </span>
              </div>
              <p className="text-body-sm text-cream-600 mt-2">
                Below threshold &mdash; significant gaps detected across {WEBFLOW_CLUSTERS.length} clusters
              </p>
            </div>
            <div className="h-20 w-20 rounded-lg flex items-center justify-center bg-error/10">
              <Activity className="h-10 w-10 text-error/60" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Row 2: Three equal cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Citation Trend Sparkline */}
        <Card>
          <CardContent className="p-4">
            <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-3">
              Citation Trend
            </p>
            <div className="flex items-end gap-3">
              <div>
                <span className="font-sans text-heading-2 font-semibold text-cream-950">
                  {trend[trend.length - 1].score}
                </span>
                <span className="text-body-sm text-cream-600 ml-1">
                  / 100
                </span>
              </div>
              <Badge variant="warning">Flat</Badge>
            </div>
            <div className="h-12 mt-3 -mx-1">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend}>
                  <YAxis domain={[20, 40]} hide />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="var(--color-terracotta-400, #d97757)"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-caption text-cream-600 mt-1">
              8-week trend &middot; {trend[0].week} &ndash; {trend[trend.length - 1].week}
            </p>
          </CardContent>
        </Card>

        {/* Active Cycle */}
        <Card>
          <CardContent className="p-4">
            <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-3">
              Active Cycle
            </p>
            <div className="flex items-center gap-2 mb-2">
              <span className="font-sans text-body-lg font-semibold text-cream-950">
                {activeCycle.name}
              </span>
            </div>
            <Progress
              value={activeCycle.completed}
              max={activeCycle.total}
              color="sage"
              className="mb-1.5"
            />
            <p className="text-caption text-cream-600">
              {activeCycle.completed} / {activeCycle.total} briefs completed
            </p>
          </CardContent>
        </Card>

        {/* Pipeline Status */}
        <Card>
          <CardContent className="p-4">
            <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-3">
              Pipeline Status
            </p>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-ocean-400 animate-pulse" />
                <span className="text-body-sm font-sans text-cream-800">
                  {runningTasks.length} running
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-terracotta-400" />
                <span className="text-body-sm font-sans text-cream-800">
                  0 awaiting approval
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-sage-400" />
                <span className="text-body-sm font-sans text-cream-800">
                  {completedTasks.length} completed
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 3: Priority Actions + Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Priority Actions */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Priority Actions</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Briefs awaiting review */}
            <div className="space-y-2">
              <div className="flex items-center justify-between p-3 bg-terracotta-50 rounded-md border border-terracotta-200">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-4 w-4 text-terracotta-400" />
                  <div>
                    <p className="text-body-sm font-sans font-medium text-cream-900">
                      {briefsAwaitingReview.length} briefs awaiting review
                    </p>
                    <p className="text-caption text-cream-600">
                      Content pipeline &middot; Week of Feb 17
                    </p>
                  </div>
                </div>
                <Link href="/content-pipeline">
                  <Button variant="secondary" size="sm">
                    Review
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </div>

              {briefsAwaitingReview.map((brief) => (
                <Link
                  key={brief.id}
                  href={`/content-pipeline/${brief.id}`}
                  className="flex items-center justify-between p-3 bg-cream-100 rounded-md hover:bg-cream-200 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Eye className="h-4 w-4 text-cream-500" />
                    <div>
                      <p className="text-body-sm font-sans font-medium text-cream-900">
                        {brief.title}
                      </p>
                      <p className="text-caption text-cream-600">
                        {brief.cluster} &middot; {brief.word_count.toLocaleString()} words
                        {brief.citability_score !== null && (
                          <> &middot; Score: {brief.citability_score}</>
                        )}
                      </p>
                    </div>
                  </div>
                  <Badge variant="warning">Review</Badge>
                </Link>
              ))}
            </div>

            {/* Running tasks */}
            {runningTasks.length > 0 && (
              <div className="mt-3 space-y-2">
                {runningTasks.map((task) => (
                  <div
                    key={task.id}
                    className="flex items-center justify-between p-3 bg-ocean-50 rounded-md border border-ocean-200"
                  >
                    <div className="flex items-center gap-3">
                      <Clock className="h-4 w-4 text-ocean-400 animate-spin" />
                      <div>
                        <p className="text-body-sm font-sans font-medium text-cream-900">
                          {task.pipeline} pipeline running
                        </p>
                        <p className="text-caption text-cream-600">
                          {task.company_slug} &middot; Step: {task.current_step || 'starting'}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Stats</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-cream-100 rounded-md">
                <FileText className="h-4 w-4 text-sage-400 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">
                  {WEBFLOW_TOP_GAPS.length + WEBFLOW_CONTENT_BRIEFS.length}
                </p>
                <p className="text-caption text-cream-600">Content Pieces</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <Search className="h-4 w-4 text-ocean-400 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">
                  {WEBFLOW_SPA_SCORE.total_queries}
                </p>
                <p className="text-caption text-cream-600">Queries Tracked</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <Layers className="h-4 w-4 text-terracotta-400 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">
                  {WEBFLOW_CLUSTERS.length}
                </p>
                <p className="text-caption text-cream-600">Active Clusters</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <Building2 className="h-4 w-4 text-cream-600 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">
                  {WEBFLOW_COMPANIES.length}
                </p>
                <p className="text-caption text-cream-600">Companies</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 4: Signal Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Signal Summary</CardTitle>
            <Link href="/signal-analysis">
              <Button variant="ghost" size="sm">
                View full analysis
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* SPA Score */}
            <div>
              <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-2">
                SPA Score
              </p>
              <div className="flex items-baseline gap-2 mb-1">
                <span className="font-sans text-heading-1 font-semibold text-terracotta-400">
                  {WEBFLOW_SPA_SCORE.score.toFixed(2)}
                </span>
                <span className="text-body-sm text-cream-600">t-statistic</span>
              </div>
              <p className="text-body-sm text-cream-600">
                p-value: {WEBFLOW_SPA_SCORE.p_value.toFixed(4)} &middot;{' '}
                {WEBFLOW_SPA_SCORE.total_citations.toLocaleString()} citations analyzed
              </p>
            </div>

            {/* Top 3 Gaps */}
            <div>
              <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-2">
                Top Gaps
              </p>
              <div className="space-y-2">
                {WEBFLOW_TOP_GAPS.slice(0, 3).map((gap, i) => (
                  <div
                    key={gap.id}
                    className="flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-caption font-sans font-semibold text-cream-500">
                        {i + 1}.
                      </span>
                      <span className="text-body-sm text-cream-800 truncate max-w-[250px]">
                        {gap.query}
                      </span>
                    </div>
                    <Badge variant="error">
                      {formatPercent(gap.gap)}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
