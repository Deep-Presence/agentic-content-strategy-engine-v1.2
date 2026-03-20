/**
 * useTaskStream — SSE hook for real-time pipeline progress.
 *
 * Opens an EventSource connection to the backend's /tasks/{taskId}/events endpoint
 * using a stream token. Accumulates events and extracts progress metadata.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { apiPost } from '@/lib/api/client';
import { TASKS } from '@/lib/api/endpoints';

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
  id?: number;
}

export type StreamStatus = 'idle' | 'connecting' | 'connected' | 'completed' | 'error';

interface TaskStreamState {
  status: StreamStatus;
  events: SSEEvent[];
  currentStep: string | null;
  progressPct: number;
  error: string | null;
}

const TERMINAL_EVENTS = new Set(['completed', 'failed', 'cancelled']);

// All event types the backend may emit during onboarding or pipeline runs
const KNOWN_EVENT_TYPES = [
  'started',
  'progress',
  'step_start',
  'step_complete',
  'stage_started',
  'stage_complete',
  'pipeline_complete',
  'pending_approval',
  'completed',
  'failed',
  'cancelled',
  'onboarding_start',
  'onboarding_phase_start',
  'onboarding_phase_complete',
  'onboarding_phase_skipped',
  'onboarding_sub_start',
  'onboarding_sub_complete',
  'onboarding_sub_failed',
  'onboarding_sub_cancelled',
  'onboarding_sa_progress',
  'log',
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? '';

export function useTaskStream(taskId: string | null): TaskStreamState {
  const [state, setState] = useState<TaskStreamState>({
    status: 'idle',
    events: [],
    currentStep: null,
    progressPct: 0,
    error: null,
  });

  const esRef = useRef<EventSource | null>(null);
  const taskIdRef = useRef<string | null>(null);

  const handleEvent = useCallback((type: string, data: Record<string, unknown>) => {
    setState((prev) => {
      const event: SSEEvent = { type, data };
      const events = [...prev.events, event];

      let { currentStep, progressPct, error, status } = prev;

      // Extract progress metadata from common event shapes
      if (data.step && typeof data.step === 'string') {
        currentStep = data.step;
      }
      if (data.current_step && typeof data.current_step === 'string') {
        currentStep = data.current_step;
      }
      if (typeof data.progress_pct === 'number') {
        progressPct = data.progress_pct;
      }
      if (data.pipeline && typeof data.pipeline === 'string' && type === 'onboarding_sub_start') {
        currentStep = data.pipeline;
      }
      if (data.message && typeof data.message === 'string' && type === 'log') {
        currentStep = data.message;
      }

      // Terminal events
      if (type === 'completed') {
        status = 'completed';
        progressPct = 100;
      } else if (type === 'failed') {
        status = 'error';
        error = (data.error as string) ?? (data.message as string) ?? 'Pipeline failed';
      } else if (type === 'cancelled') {
        status = 'error';
        error = 'Pipeline was cancelled';
      }

      return { status, events, currentStep, progressPct, error };
    });
  }, []);

  useEffect(() => {
    // Prevent re-connecting if taskId hasn't changed
    if (taskId === taskIdRef.current) return;
    taskIdRef.current = taskId;

    // Close any existing connection
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    if (!taskId) {
      setState({ status: 'idle', events: [], currentStep: null, progressPct: 0, error: null });
      return;
    }

    setState((prev) => ({ ...prev, status: 'connecting', events: [], error: null }));

    let cancelled = false;

    const connect = async () => {
      try {
        // Get a stream token (5-minute validity)
        const { stream_token } = await apiPost<{ stream_token: string; expires_in: number }>(
          TASKS.streamToken(taskId),
          {},
        );

        if (cancelled) return;

        // Open EventSource with stream token in query param
        const url = `${API_BASE}${TASKS.events(taskId)}?stream_token=${stream_token}`;
        const es = new EventSource(url);
        esRef.current = es;

        // Mark as connected immediately — EventSource handles reconnection internally.
        // The onerror handler below will catch actual connection failures.
        if (!cancelled) {
          setState((prev) => ({ ...prev, status: 'connected' }));
        }

        // Listen to all known event types as named events
        for (const eventType of KNOWN_EVENT_TYPES) {
          es.addEventListener(eventType, (e: MessageEvent) => {
            if (cancelled) return;
            try {
              const data = JSON.parse(e.data);
              handleEvent(eventType, data);
            } catch {
              handleEvent(eventType, { raw: e.data });
            }

            // Close after terminal events
            if (TERMINAL_EVENTS.has(eventType)) {
              es.close();
            }
          });
        }

        // Also listen to generic messages (unnamed events)
        es.onmessage = (e: MessageEvent) => {
          if (cancelled) return;
          try {
            const data = JSON.parse(e.data);
            const type = data.type ?? 'message';
            handleEvent(type, data);
          } catch {
            // ignore unparseable messages
          }
        };

        es.onerror = () => {
          if (cancelled) return;
          // EventSource auto-reconnects on transient errors.
          // Only set error if the connection was permanently closed.
          if (es.readyState === EventSource.CLOSED) {
            setState((prev) => {
              if (prev.status === 'completed' || prev.status === 'error') return prev;
              return { ...prev, status: 'error', error: 'Connection lost' };
            });
          }
        };
      } catch (err) {
        if (!cancelled) {
          setState((prev) => ({
            ...prev,
            status: 'error',
            error: err instanceof Error ? err.message : 'Failed to connect',
          }));
        }
      }
    };

    connect();

    return () => {
      cancelled = true;
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [taskId, handleEvent]);

  return state;
}
