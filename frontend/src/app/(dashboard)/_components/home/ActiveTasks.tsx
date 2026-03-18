'use client';

import { Card, Badge, ProgressBar, Skeleton } from '@/components/ui';
import { useRouter } from 'next/navigation';
import { Zap } from 'lucide-react';
import { useApiQuery } from '@/lib/hooks/useApiQuery';
import { TASKS } from '@/lib/api/endpoints';

interface PipelineTask {
  task_id: string;
  pipeline: string;
  status: string;
  current_step: string | null;
  progress_pct: number | null;
  company_slug: string;
  created_at: string;
}

const PIPELINE_LABELS: Record<string, string> = {
  onboarding: 'Onboarding',
  knowledge_base: 'Knowledge Base',
  audience_persona: 'Audience Personas',
  voice_style_guide: 'Voice Style Guide',
  gap_analysis: 'Gap Analysis',
  content: 'Content Generation',
  topic_discovery: 'Topic Discovery',
  site_audit: 'Site Audit',
};

export function ActiveTasks() {
  const router = useRouter();
  const { data, isLoading } = useApiQuery<PipelineTask[]>(
    `${TASKS.list}?status=running`,
    { refreshInterval: 15000 },
  );
  const tasks = Array.isArray(data) ? data : [];

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Zap size={16} strokeWidth={1.5} className="text-accent" />
        <h2 className="text-[18px] font-semibold text-text-primary">Active Agent Tasks</h2>
      </div>
      <div className="space-y-2">
        {isLoading ? (
          <>
            <Skeleton className="h-[80px]" />
            <Skeleton className="h-[80px]" />
          </>
        ) : tasks.length === 0 ? (
          <Card>
            <p className="text-[13px] text-text-tertiary text-center py-4">No active tasks</p>
          </Card>
        ) : (
          tasks.map((task) => (
            <Card
              key={task.task_id}
              hoverable
              className="cursor-pointer"
              onClick={() => router.push('/content')}
            >
              <div className="flex items-center justify-between mb-2">
                <p className="text-[14px] font-medium text-text-primary leading-[1.4]">
                  {PIPELINE_LABELS[task.pipeline] ?? task.pipeline}
                </p>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="info">{task.current_step ?? task.status}</Badge>
                <span className="text-[12px] text-text-tertiary">{task.pipeline}</span>
              </div>
              {task.progress_pct != null && (
                <>
                  <ProgressBar value={task.progress_pct} />
                  <p className="text-[12px] text-text-tertiary mt-1.5">{Math.round(task.progress_pct)}% complete</p>
                </>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
