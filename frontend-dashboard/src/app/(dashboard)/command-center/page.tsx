'use client';

import { useState, useEffect } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  FileText,
  Search,
  Layers,
  Building2,
  ArrowRight,
  AlertCircle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/components/layout/page-header';
import { useAppStore } from '@/stores/app-store';
import { tasks as tasksApi } from '@/lib/api/tasks';
import { artifacts } from '@/lib/api/artifacts';
import { scoreColor, scoreBgColor, formatPercent } from '@/lib/utils/format';
import type { TaskResponse } from '@/types/common';
import type { GapReport } from '@/types/gap-analysis';

export default function CommandCenterPage() {
  const { currentCompany } = useAppStore();
  const [taskList, setTaskList] = useState<TaskResponse[]>([]);
  const [gapReport, setGapReport] = useState<GapReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const [tasksResult] = await Promise.allSettled([
          tasksApi.list(),
        ]);
        if (tasksResult.status === 'fulfilled') {
          setTaskList(tasksResult.value.tasks);
        }
      } catch {
        // Backend unavailable
      }

      if (currentCompany) {
        try {
          const report = await artifacts.getContent<GapReport>(
            'gap_analysis',
            currentCompany,
            'gap_report.json'
          );
          setGapReport(report);
        } catch {
          // No report available
        }
      }

      setLoading(false);
    }

    fetchData();
  }, [currentCompany]);

  const runningTasks = taskList.filter((t) => t.status === 'running');
  const pendingApproval = taskList.filter((t) => t.status === 'pending_approval');
  const completedTasks = taskList.filter((t) => t.status === 'completed');

  // Derive citability score from SPA score
  const citabilityScore = gapReport?.spa_score
    ? Math.max(0, Math.min(1, 0.5 + gapReport.spa_score.company_advantage * 0.5))
    : null;

  const citationShift = gapReport?.spa_score?.citation_advantage ?? null;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Command Center"
        description={`Overview for ${currentCompany ? currentCompany.charAt(0).toUpperCase() + currentCompany.slice(1) : 'your company'}`}
        actions={
          <Button variant="primary" size="md">
            <Activity className="h-4 w-4" />
            Run Analysis
          </Button>
        }
      />

      {/* Row 1: Hero Metric */}
      <Card className="overflow-hidden">
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-2">
                Citability Score
              </p>
              {loading ? (
                <Skeleton className="h-14 w-32" />
              ) : citabilityScore !== null ? (
                <div className="flex items-baseline gap-3">
                  <span
                    className={`font-serif text-display font-semibold ${scoreColor(citabilityScore)}`}
                  >
                    {formatPercent(citabilityScore)}
                  </span>
                  {citationShift !== null && (
                    <span
                      className={`flex items-center gap-1 text-body-sm font-sans font-medium ${
                        citationShift > 0 ? 'text-sage-400' : 'text-error'
                      }`}
                    >
                      {citationShift > 0 ? (
                        <TrendingUp className="h-4 w-4" />
                      ) : (
                        <TrendingDown className="h-4 w-4" />
                      )}
                      {citationShift > 0 ? '+' : ''}
                      {(citationShift * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
              ) : (
                <p className="font-serif text-heading-1 text-cream-500">--</p>
              )}
              <p className="text-body-sm text-cream-600 mt-1">
                Aggregate visibility across AI platforms
              </p>
            </div>
            <div
              className={`h-20 w-20 rounded-lg flex items-center justify-center ${
                citabilityScore !== null ? scoreBgColor(citabilityScore) : 'bg-cream-200'
              }`}
            >
              <Activity className="h-10 w-10 text-cream-600" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Row 2: Three equal cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Citation Shift */}
        <Card>
          <CardContent className="p-4">
            <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-3">
              Citation Shift
            </p>
            {loading ? (
              <Skeleton className="h-8 w-24" />
            ) : gapReport ? (
              <div className="flex items-center gap-2">
                <span className="font-sans text-heading-2 font-semibold text-cream-950">
                  {gapReport.spa_score.citation_advantage > 0 ? '+' : ''}
                  {(gapReport.spa_score.citation_advantage * 100).toFixed(1)}%
                </span>
                <Badge
                  variant={
                    gapReport.spa_score.citation_advantage > 0 ? 'green' : 'error'
                  }
                >
                  {gapReport.spa_score.citation_advantage > 0
                    ? 'Improving'
                    : 'Declining'}
                </Badge>
              </div>
            ) : (
              <p className="text-heading-3 text-cream-500">No data</p>
            )}
            <p className="text-caption text-cream-600 mt-2">
              vs. competing citations
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
                Week of Feb 24
              </span>
            </div>
            <Progress value={3} max={8} color="sage" className="mb-1.5" />
            <p className="text-caption text-cream-600">3 / 8 briefs completed</p>
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
                  {pendingApproval.length} awaiting approval
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

      {/* Row 3: Two cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Priority Actions */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Priority Actions</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : pendingApproval.length > 0 ? (
              <div className="space-y-2">
                {pendingApproval.map((task) => (
                  <div
                    key={task.run_id}
                    className="flex items-center justify-between p-3 bg-terracotta-50 rounded-md border border-terracotta-200"
                  >
                    <div className="flex items-center gap-3">
                      <AlertCircle className="h-4 w-4 text-terracotta-400" />
                      <div>
                        <p className="text-body-sm font-sans font-medium text-cream-900">
                          {task.pipeline === 'research'
                            ? 'Research approval needed'
                            : task.pipeline === 'content'
                            ? 'Content review required'
                            : 'Pipeline approval pending'}
                        </p>
                        <p className="text-caption text-cream-600">
                          {task.company_slug} &middot; {task.current_step || task.pipeline}
                        </p>
                      </div>
                    </div>
                    <Button variant="secondary" size="sm">
                      Review
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-3 p-4 text-center">
                <CheckCircle className="h-5 w-5 text-sage-400" />
                <p className="text-body-sm text-cream-600">
                  No items need attention right now
                </p>
              </div>
            )}

            {runningTasks.length > 0 && (
              <div className="mt-3 space-y-2">
                {runningTasks.map((task) => (
                  <div
                    key={task.run_id}
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
                    {task.progress_pct !== null && (
                      <span className="text-body-sm font-sans font-semibold text-ocean-500">
                        {Math.round(task.progress_pct)}%
                      </span>
                    )}
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
                  {gapReport?.top_gaps?.length || 25}
                </p>
                <p className="text-caption text-cream-600">Content Pieces</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <Search className="h-4 w-4 text-ocean-400 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">
                  {gapReport?.total_queries || 150}
                </p>
                <p className="text-caption text-cream-600">Queries Tracked</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <Layers className="h-4 w-4 text-terracotta-400 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">
                  {gapReport?.clusters?.length || 9}
                </p>
                <p className="text-caption text-cream-600">Active Clusters</p>
              </div>
              <div className="p-3 bg-cream-100 rounded-md">
                <Building2 className="h-4 w-4 text-cream-600 mb-1.5" />
                <p className="font-sans text-heading-3 font-semibold text-cream-950">
                  3
                </p>
                <p className="text-caption text-cream-600">Companies</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 4: Signal Summary */}
      {gapReport && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Signal Summary</CardTitle>
              <Button variant="ghost" size="sm">
                View full analysis
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
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
                    {gapReport.spa_score.t_statistic.toFixed(2)}
                  </span>
                  <span className="text-body-sm text-cream-600">t-statistic</span>
                </div>
                <p className="text-body-sm text-cream-600">
                  p-value: {gapReport.spa_score.p_value.toFixed(4)}
                </p>
              </div>

              {/* Top 3 Gaps */}
              <div>
                <p className="text-caption font-sans font-medium uppercase tracking-wider text-cream-600 mb-2">
                  Top Gaps
                </p>
                <div className="space-y-2">
                  {gapReport.top_gaps.slice(0, 3).map((gap, i) => (
                    <div
                      key={gap.query_id}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-caption font-sans font-semibold text-cream-500">
                          {i + 1}.
                        </span>
                        <span className="text-body-sm text-cream-800 truncate max-w-[250px]">
                          {gap.query_text}
                        </span>
                      </div>
                      <Badge
                        variant={
                          gap.gap_classification === 'significant_gap'
                            ? 'error'
                            : gap.gap_classification === 'gap_to_close'
                            ? 'warning'
                            : 'green'
                        }
                      >
                        {formatPercent(gap.gap_score)}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
