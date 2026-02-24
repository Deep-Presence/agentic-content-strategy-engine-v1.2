'use client';

import Link from 'next/link';
import { FileText, AlertTriangle, Clock, CheckCircle, Sparkles, ArrowRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { ContentBriefItem } from '@/types/content';

interface GapItem {
  id: string;
  query: string;
  cluster: string;
  gap: number;
}

interface TaskItem {
  id: string;
  pipeline: string;
  company_slug: string;
  current_step: string | null;
}

interface PriorityActionsPanelProps {
  reviewBriefs: ContentBriefItem[];
  runningTasks: TaskItem[];
  topGaps: GapItem[];
  publishedBriefs: ContentBriefItem[];
}

type ActionItem = {
  id: string;
  icon: React.ReactNode;
  title: string;
  detail: string;
  badge?: { label: string; variant: 'error' | 'warning' | 'blue' | 'green' | 'default' };
  href?: string;
  bgColor: string;
};

export function PriorityActionsPanel({
  reviewBriefs,
  runningTasks,
  topGaps,
  publishedBriefs,
}: PriorityActionsPanelProps) {
  const actions: ActionItem[] = [];

  // Review briefs
  for (const brief of reviewBriefs) {
    actions.push({
      id: `review-${brief.id}`,
      icon: <FileText className="h-4 w-4 text-terracotta-400" />,
      title: brief.title,
      detail: `${brief.cluster} · ${brief.citability_score ? `Score: ${brief.citability_score}` : 'Awaiting score'}`,
      badge: { label: 'Review', variant: 'warning' },
      href: `/content-pipeline/${brief.id}`,
      bgColor: 'bg-terracotta-50',
    });
  }

  // Running tasks
  for (const task of runningTasks) {
    actions.push({
      id: `task-${task.id}`,
      icon: <Clock className="h-4 w-4 text-ocean-400 animate-spin" />,
      title: `${task.pipeline} pipeline running`,
      detail: `${task.company_slug} · Step: ${task.current_step || 'starting'}`,
      badge: { label: 'Running', variant: 'blue' },
      bgColor: 'bg-ocean-50',
    });
  }

  // Top gaps (first 3)
  for (const gap of topGaps.slice(0, 3)) {
    actions.push({
      id: `gap-${gap.id}`,
      icon: <AlertTriangle className="h-4 w-4 text-error" />,
      title: gap.query,
      detail: `${gap.cluster} · Gap: ${Math.round(gap.gap * 100)}%`,
      badge: { label: 'Gap', variant: 'error' },
      href: `/signal-analysis/briefs/${gap.id}`,
      bgColor: 'bg-cream-100',
    });
  }

  // Recent published (first 2)
  for (const brief of publishedBriefs.slice(0, 2)) {
    actions.push({
      id: `pub-${brief.id}`,
      icon: <CheckCircle className="h-4 w-4 text-sage-400" />,
      title: brief.title,
      detail: `${brief.cluster} · Score: ${brief.citability_score ?? '—'}`,
      badge: { label: 'Published', variant: 'green' },
      href: `/content-pipeline/${brief.id}`,
      bgColor: 'bg-cream-50',
    });
  }

  return (
    <Card className="animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Priority Actions</CardTitle>
          <div className="flex items-center gap-1 text-caption font-sans text-cream-600">
            <Sparkles className="h-3.5 w-3.5" />
            {actions.length} items
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-1.5 max-h-[420px] overflow-y-auto pr-1">
          {actions.map((action) => {
            const Row = (
              <div
                key={action.id}
                className={`flex items-center gap-3 p-2.5 rounded-md ${action.bgColor} hover:shadow-sm transition-shadow`}
              >
                <div className="shrink-0">{action.icon}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-body-sm font-sans font-medium text-cream-900 truncate">
                    {action.title}
                  </p>
                  <p className="text-caption text-cream-600 truncate">{action.detail}</p>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  {action.badge && <Badge variant={action.badge.variant}>{action.badge.label}</Badge>}
                  {action.href && <ArrowRight className="h-3.5 w-3.5 text-cream-500" />}
                </div>
              </div>
            );

            return action.href ? (
              <Link key={action.id} href={action.href} className="block">
                {Row}
              </Link>
            ) : (
              <div key={action.id}>{Row}</div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
