'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useStreamToken } from '@/hooks/useStreamToken';
import { createSSEConnection } from '@/lib/api-client';
import type { BriefPipelineStatus, AgentProgress } from '../_components/types';
import type {
  SSEWorkerProgressData,
  SSEPendingApprovalData,
  SSEBriefCompletedData,
  SSEPipelineCompleteData,
  SSEPipelineErrorData,
  SSECPSScoringData,
  SSEGAStepData,
} from '../_lib/types';

// Map SSE worker step names to BriefPipelineStatus values
const STEP_TO_STATUS: Record<string, BriefPipelineStatus> = {
  outlining: 'outlining',
  drafting: 'drafting',
  linking: 'linking',
  enriching: 'enriching',
  evaluating: 'evaluating',
  revising: 'revising',
  briefing: 'briefing',
};

// Derive approximate progress % from worker step
const STEP_PROGRESS: Record<string, number> = {
  briefing: 5,
  outlining: 15,
  drafting: 35,
  linking: 55,
  enriching: 70,
  evaluating: 85,
  revising: 90,
};

export interface PipelineCallbacks {
  onStatusChange: (briefId: string, status: BriefPipelineStatus) => void;
  onProgress: (briefId: string, progress: Partial<AgentProgress>) => void;
  onApprovalNeeded: (briefId: string, stage: string, data: SSEPendingApprovalData) => void;
  onBriefCompleted: (briefId: string) => void;
  onBriefRejected: (briefId: string) => void;
  onCPSScores: (scores: Record<string, number>) => void;
  onComplete: (data: SSEPipelineCompleteData) => void;
  onError: (error: string) => void;
  onCancelled: () => void;
}

/**
 * SSE subscription hook for real-time pipeline progress.
 *
 * Given a taskId, acquires a stream token and opens an EventSource.
 * Parses SSE events and dispatches callbacks to update card state.
 */
export function useContentPipeline(
  taskId: string | null,
  callbacks: PipelineCallbacks,
) {
  const { streamToken, acquire } = useStreamToken(taskId ?? '');
  const [isConnected, setIsConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  const disconnect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
      setIsConnected(false);
    }
  }, []);

  useEffect(() => {
    if (!taskId) {
      disconnect();
      return;
    }

    let cancelled = false;

    async function connect() {
      try {
        const token = streamToken || (await acquire());
        if (cancelled || !token) return;

        const source = createSSEConnection(
          taskId!,
          token,
          (event: MessageEvent) => {
            try {
              const parsed = JSON.parse(event.data);
              const eventType: string = parsed.event_type || parsed.type || '';
              const data = parsed.data || parsed;

              handleEvent(eventType, data, callbacksRef.current);
            } catch {
              // Non-JSON event (e.g., heartbeat)
            }
          },
          () => {
            // On error — EventSource auto-reconnects
            setIsConnected(false);
          },
        );

        sourceRef.current = source;
        setIsConnected(true);
      } catch {
        // Token acquisition failed — will retry on next render
      }
    }

    connect();

    return () => {
      cancelled = true;
      disconnect();
    };
  }, [taskId, streamToken, acquire, disconnect]);

  return { isConnected, disconnect };
}

function handleEvent(
  eventType: string,
  data: Record<string, unknown>,
  cb: PipelineCallbacks,
) {
  switch (eventType) {
    case 'worker_progress': {
      const d = data as unknown as SSEWorkerProgressData;
      const status = STEP_TO_STATUS[d.step];
      if (status && d.brief_id) {
        cb.onStatusChange(d.brief_id, status);
        cb.onProgress(d.brief_id, {
          pct: STEP_PROGRESS[d.step] ?? 50,
          currentTask: `${d.step.charAt(0).toUpperCase() + d.step.slice(1)}...`,
        });
      }
      break;
    }

    case 'pending_approval': {
      const d = data as unknown as SSEPendingApprovalData;
      const briefId = d.brief_id || '';
      const stage = d.stage || '';

      if (stage.toLowerCase().includes('brief')) {
        cb.onStatusChange(briefId, 'pending_brief_approval');
      } else if (stage.toLowerCase().includes('content')) {
        cb.onStatusChange(briefId, 'pending_content_approval');
      }
      cb.onApprovalNeeded(briefId, stage, d);
      break;
    }

    case 'approval_received': {
      // Pipeline resumes — status will be updated by next worker_progress event
      break;
    }

    case 'brief_completed': {
      const d = data as unknown as SSEBriefCompletedData;
      if (d.brief_id) {
        cb.onStatusChange(d.brief_id, 'completed');
        cb.onBriefCompleted(d.brief_id);
      }
      break;
    }

    case 'brief_rejected': {
      const d = data as unknown as SSEBriefCompletedData;
      if (d.brief_id) {
        cb.onStatusChange(d.brief_id, 'rejected');
        cb.onBriefRejected(d.brief_id);
      }
      break;
    }

    case 'cps_scoring_complete': {
      const d = data as unknown as SSECPSScoringData;
      if (d.scores) {
        cb.onCPSScores(d.scores);
      }
      break;
    }

    case 'completed':
    case 'pipeline_complete': {
      const d = data as unknown as SSEPipelineCompleteData;
      cb.onComplete(d);
      break;
    }

    case 'failed':
    case 'pipeline_error':
    case 'pipeline_failed': {
      const d = data as unknown as SSEPipelineErrorData;
      cb.onError(d.error || 'Pipeline failed');
      break;
    }

    case 'ga_step_start': {
      const d = data as unknown as SSEGAStepData;
      // GA events don't carry brief_id — briefs don't exist yet during GA.
      // Pass empty briefId; page.tsx resolves via activeTaskId match.
      cb.onProgress('', {
        pct: Math.round(((d.step_num - 1) / d.total_steps) * 100),
        currentTask: d.name || d.step,
        gaStepName: d.name,
        gaStepNum: d.step_num,
        gaTotalSteps: d.total_steps,
      });
      break;
    }

    case 'ga_step_complete': {
      const d = data as unknown as SSEGAStepData;
      cb.onProgress('', {
        pct: Math.round((d.step_num / (d.total_steps || 8)) * 100),
        currentTask: `${d.name || d.step} complete`,
      });
      break;
    }

    case 'cancelled': {
      cb.onCancelled();
      break;
    }

    // stage_started, stage_complete — informational, no card update needed
    default:
      break;
  }
}
