'use client';

import { Card, Badge, Skeleton } from '@/components/ui';
import { useRouter } from 'next/navigation';
import { AlertCircle, FileText } from 'lucide-react';
import { useApiQuery } from '@/lib/hooks/useApiQuery';
import { TASKS } from '@/lib/api/endpoints';

interface PipelineTask {
  task_id: string;
  pipeline: string;
  status: string;
  current_step: string | null;
  company_slug: string;
  created_at: string;
}

const PIPELINE_LABELS: Record<string, string> = {
  knowledge_base: 'Knowledge Base',
  audience_persona: 'Audience Personas',
  voice_style_guide: 'Voice Style Guide',
  content: 'Content',
  topic_discovery: 'Topic Discovery',
};

export function HITLReviews() {
  const router = useRouter();
  const { data, isLoading } = useApiQuery<PipelineTask[]>(
    `${TASKS.list}?status=pending_approval`,
    { refreshInterval: 30000 },
  );
  const tasks = Array.isArray(data) ? data : [];

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle size={16} strokeWidth={1.5} className="text-warning" />
        <h2 className="text-[18px] font-semibold text-text-primary">HITL Reviews Pending</h2>
      </div>

      {!isLoading && tasks.length > 0 && (
        <div className="flex gap-2 mb-3">
          <Badge variant="warning">{tasks.length} pending</Badge>
        </div>
      )}

      <div className="space-y-2">
        {isLoading ? (
          <>
            <Skeleton className="h-[60px]" />
            <Skeleton className="h-[60px]" />
          </>
        ) : tasks.length === 0 ? (
          <Card>
            <p className="text-[13px] text-text-tertiary text-center py-4">No reviews pending</p>
          </Card>
        ) : (
          tasks.map((task) => (
            <Card
              key={task.task_id}
              hoverable
              className="cursor-pointer"
              onClick={() => router.push('/content')}
            >
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 text-text-tertiary">
                  <FileText size={16} strokeWidth={1.5} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[14px] text-text-primary leading-[1.4]">
                    {PIPELINE_LABELS[task.pipeline] ?? task.pipeline} — {task.current_step ?? 'Awaiting review'}
                  </p>
                </div>
                <Badge variant="warning">pending</Badge>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
