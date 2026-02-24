'use client';

import { useEffect } from 'react';
import { FlaskConical, CheckCircle, Loader2, Circle, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useEventStream } from '@/lib/hooks/use-event-stream';
import { tasks } from '@/lib/api/tasks';
import { useToast } from '@/components/ui/toast';
import { useBrandStore } from '@/stores/brand-store';
import { cn } from '@/lib/utils/cn';
import type { ResearchEvent } from '@/types/research';

interface ResearchProgressProps {
  runId: string;
  onDraftReady?: (stage: string, data: Record<string, unknown>) => void;
  onComplete?: () => void;
  onCancel?: () => void;
}

interface StageState {
  key: string;
  label: string;
  status: 'waiting' | 'running' | 'draft' | 'approved' | 'failed';
}

function getStageStates(events: Array<{ event: string }>): StageState[] {
  const stages: StageState[] = [
    { key: 'company', label: 'Company Context', status: 'waiting' },
    { key: 'persona', label: 'Persona Research', status: 'waiting' },
    { key: 'style', label: 'Style Guide', status: 'waiting' },
  ];

  for (const { event } of events) {
    const e = event as ResearchEvent;
    if (e === 'company_start') stages[0].status = 'running';
    if (e === 'company_draft') stages[0].status = 'draft';
    if (e === 'company_approved') stages[0].status = 'approved';
    if (e === 'persona_start') stages[1].status = 'running';
    if (e === 'persona_draft') stages[1].status = 'draft';
    if (e === 'persona_approved') stages[1].status = 'approved';
    if (e === 'style_start') stages[2].status = 'running';
    if (e === 'style_draft') stages[2].status = 'draft';
    if (e === 'style_approved') stages[2].status = 'approved';
    if (e === 'failed') {
      const running = stages.find((s) => s.status === 'running');
      if (running) running.status = 'failed';
    }
  }

  return stages;
}

const STAGE_ICONS = {
  waiting: Circle,
  running: Loader2,
  draft: Circle,
  approved: CheckCircle,
  failed: XCircle,
} as const;

export function ResearchProgress({
  runId,
  onDraftReady,
  onComplete,
  onCancel,
}: ResearchProgressProps) {
  const { toast } = useToast();
  const clearResearchRun = useBrandStore((s) => s.clearResearchRun);
  const setApprovalPayload = useBrandStore((s) => s.setApprovalPayload);

  const { events, lastEvent, connected } = useEventStream(runId, {
    onEvent: (event, data) => {
      if (event === 'company_draft' || event === 'persona_draft' || event === 'style_draft') {
        onDraftReady?.(event.replace('_draft', ''), data);
        setApprovalPayload(data);
      }
      if (event === 'completed') {
        toast('Research pipeline completed', 'success');
        clearResearchRun();
        onComplete?.();
      }
      if (event === 'failed') {
        toast('Research pipeline failed', 'error');
        clearResearchRun();
      }
      if (event === 'cancelled') {
        toast('Research pipeline cancelled', 'info');
        clearResearchRun();
      }
    },
  });

  const stages = getStageStates(events);
  const isTerminal = lastEvent === 'completed' || lastEvent === 'failed' || lastEvent === 'cancelled';

  const handleCancel = async () => {
    try {
      await tasks.cancel(runId);
      toast('Pipeline cancellation requested', 'info');
      onCancel?.();
    } catch {
      toast('Failed to cancel pipeline', 'error');
    }
  };

  if (isTerminal) return null;

  return (
    <div className="bg-white rounded-md border border-[var(--border-default)] shadow-[var(--shadow-sm)] p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-terracotta-400" />
          <h4 className="font-sans text-heading-4 font-semibold text-cream-950">
            Research Pipeline Running
          </h4>
          {connected && (
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-sage-400 animate-pulse" />
              <span className="text-micro font-sans text-cream-600">Live</span>
            </span>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={handleCancel}>
          Cancel
        </Button>
      </div>

      <div className="space-y-3">
        {stages.map((stage) => {
          const Icon = STAGE_ICONS[stage.status];
          return (
            <div key={stage.key} className="flex items-center gap-3">
              <Icon
                className={cn(
                  'h-4 w-4 shrink-0',
                  stage.status === 'approved' && 'text-sage-400',
                  stage.status === 'running' && 'text-terracotta-400 animate-spin',
                  stage.status === 'draft' && 'text-warning fill-warning/20',
                  stage.status === 'waiting' && 'text-cream-400',
                  stage.status === 'failed' && 'text-error'
                )}
              />
              <span
                className={cn(
                  'font-sans text-body-sm flex-1',
                  stage.status === 'waiting' ? 'text-cream-500' : 'text-cream-800'
                )}
              >
                {stage.label}
              </span>
              <span
                className={cn(
                  'font-sans text-caption',
                  stage.status === 'approved' && 'text-sage-400',
                  stage.status === 'running' && 'text-terracotta-400',
                  stage.status === 'draft' && 'text-warning',
                  stage.status === 'waiting' && 'text-cream-500',
                  stage.status === 'failed' && 'text-error'
                )}
              >
                {stage.status === 'waiting' && 'Waiting'}
                {stage.status === 'running' && 'In progress...'}
                {stage.status === 'draft' && 'Draft ready'}
                {stage.status === 'approved' && 'Approved'}
                {stage.status === 'failed' && 'Failed'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
