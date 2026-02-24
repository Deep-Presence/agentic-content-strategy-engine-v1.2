'use client';

import Link from 'next/link';
import { CheckCircle, ArrowRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { PIPELINE_LABELS } from '@/lib/utils/constants';
import type { Cycle } from '@/types/content';

interface TaskItem {
  id: string;
  pipeline: 'gap_analysis' | 'research' | 'content';
  company_slug: string;
  status: string;
  current_step: string | null;
}

interface PipelineStatusPanelProps {
  tasks: TaskItem[];
  activeCycle: Cycle;
  statusCounts: { published: number; review: number; inProgress: number; evaluating: number; queued: number };
}

const STATUS_ROWS = [
  { key: 'published', label: 'Published', color: 'bg-sage-400' },
  { key: 'review', label: 'In Review', color: 'bg-ocean-400' },
  { key: 'inProgress', label: 'In Progress', color: 'bg-ocean-400' },
  { key: 'evaluating', label: 'Evaluating', color: 'bg-warning' },
  { key: 'queued', label: 'Queued', color: 'bg-cream-500' },
] as const;

export function PipelineStatusPanel({ tasks, activeCycle, statusCounts }: PipelineStatusPanelProps) {
  const runningTasks = tasks.filter((t) => t.status === 'running');
  const total = Object.values(statusCounts).reduce((a, b) => a + b, 0);

  return (
    <Card className="animate-fade-in-up" style={{ animationDelay: '0.15s' }}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Pipeline Status</CardTitle>
          <Badge variant="blue">
            <span className="h-1.5 w-1.5 rounded-full bg-ocean-400 animate-pulse inline-block mr-1" />
            Live
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status breakdown */}
        <div className="space-y-2">
          {STATUS_ROWS.map(({ key, label, color }) => {
            const count = statusCounts[key];
            const pct = total > 0 ? (count / total) * 100 : 0;
            return (
              <div key={key} className="flex items-center gap-3">
                <span className={`h-2 w-2 rounded-full shrink-0 ${color} ${key === 'inProgress' ? 'animate-pulse' : ''}`} />
                <span className="text-body-sm font-sans text-cream-800 w-20">{label}</span>
                <div className="flex-1 h-1.5 bg-cream-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${color}`}
                    style={{ width: `${pct}%`, transition: 'width 0.6s ease-out' }}
                  />
                </div>
                <span className="text-caption font-sans font-semibold text-cream-700 w-5 text-right">{count}</span>
              </div>
            );
          })}
          <p className="text-caption text-cream-600 text-right">{total} total content pieces</p>
        </div>

        <Separator />

        {/* Running tasks */}
        {runningTasks.length > 0 ? (
          <div className="space-y-2">
            {runningTasks.map((task) => (
              <div key={task.id} className="flex items-center gap-2 p-2 bg-ocean-50 rounded-md">
                <span className="h-2 w-2 rounded-full bg-ocean-400 animate-pulse" />
                <div className="flex-1 min-w-0">
                  <p className="text-body-sm font-sans font-medium text-cream-900 truncate">
                    {PIPELINE_LABELS[task.pipeline]} — {task.company_slug}
                  </p>
                  <p className="text-caption text-cream-600">{task.current_step || 'starting'}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center gap-2 py-1">
            <CheckCircle className="h-4 w-4 text-sage-400" />
            <span className="text-body-sm text-cream-600">All pipelines idle</span>
          </div>
        )}

        <Separator />

        {/* Active cycle */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-body-sm font-sans font-medium text-cream-900">
              {activeCycle.name}
            </span>
            <span className="text-caption font-sans text-cream-600">
              {activeCycle.completed_count}/{activeCycle.total_count} briefs
            </span>
          </div>
          <Progress value={activeCycle.completed_count} max={activeCycle.total_count} color="sage" />
          <Link href="/content-pipeline" className="inline-flex items-center gap-1 text-caption font-sans text-terracotta-400 hover:text-terracotta-500 mt-2">
            View Pipeline
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
