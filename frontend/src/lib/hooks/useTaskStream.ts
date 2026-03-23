/**
 * useTaskStream — SSE hook for real-time pipeline progress.
 *
 * Opens an EventSource connection to the backend's /tasks/{taskId}/events endpoint
 * using a stream token. Accumulates events and extracts progress metadata.
 *
 * Automatically reconnects with a fresh token when the connection drops
 * (e.g. due to proxy timeouts on Railway during long-running pipelines).
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
  'approval_received',
  'worker_progress',
  'worker_failed',
  'brief_completed',
  'brief_rejected',
  'cps_scoring_complete',
  'pipeline_started',
  'pipeline_error',
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

/** Max reconnection attempts before giving up. */
const MAX_RECONNECT_ATTEMPTS = 10;

/** Base delay (ms) between reconnection attempts — exponential backoff. */
const RECONNECT_BASE_DELAY_MS = 1_000;

/** Cap for backoff delay. */
const RECONNECT_MAX_DELAY_MS = 30_000;

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
  /** Tracks the highest event ID we've received so the server can replay missed events. */
  const lastEventIdRef = useRef<number>(0);
  /** Whether a terminal event has been received — stops reconnection. */
  const terminalRef = useRef(false);

  const handleEvent = useCallback((type: string, data: Record<string, unknown>, id?: number) => {
    if (id !== undefined) {
      lastEventIdRef.current = id;
    }

    if (TERMINAL_EVENTS.has(type)) {
      terminalRef.current = true;
    }

    setState((prev) => {
      const event: SSEEvent = { type, data, id };
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

    // Reset refs for a new task
    lastEventIdRef.current = 0;
    terminalRef.current = false;

    setState((prev) => ({ ...prev, status: 'connecting', events: [], error: null }));

    let cancelled = false;
    let reconnectAttempts = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    /**
     * Fetch a fresh stream token and open an EventSource.
     * Called on initial connect AND on every reconnection attempt.
     */
    const connect = async () => {
      if (cancelled || terminalRef.current) return;

      try {
        // Always fetch a fresh token — this is the key fix.
        // The old token may have expired during a long pipeline run.
        const { stream_token } = await apiPost<{ stream_token: string; expires_in: number }>(
          TASKS.streamToken(taskId),
          {},
        );

        if (cancelled || terminalRef.current) return;

        // Open EventSource with fresh stream token
        const url = `${API_BASE}${TASKS.events(taskId)}?stream_token=${stream_token}`;
        const es = new EventSource(url);
        esRef.current = es;

        // Mark connected immediately — EventSource will fire onerror if it can't connect.
        if (!cancelled) {
          setState((prev) => {
            if (prev.status === 'completed' || prev.status === 'error') return prev;
            return { ...prev, status: 'connected', error: null };
          });
        }

        es.onopen = () => {
          // Reset reconnection counter on successful (re)connection
          reconnectAttempts = 0;
        };

        // Listen to all known event types as named events
        for (const eventType of KNOWN_EVENT_TYPES) {
          es.addEventListener(eventType, (e: MessageEvent) => {
            if (cancelled) return;
            const eventId = e.lastEventId ? parseInt(e.lastEventId, 10) : undefined;
            try {
              const data = JSON.parse(e.data);
              handleEvent(eventType, data, eventId);
            } catch {
              handleEvent(eventType, { raw: e.data }, eventId);
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
          const eventId = e.lastEventId ? parseInt(e.lastEventId, 10) : undefined;
          try {
            const data = JSON.parse(e.data);
            const type = data.type ?? 'message';
            handleEvent(type, data, eventId);
          } catch {
            // ignore unparseable messages
          }
        };

        es.onerror = () => {
          if (cancelled || terminalRef.current) return;

          // EventSource is CLOSED — browser won't auto-reconnect.
          // We need to manually reconnect with a fresh token.
          if (es.readyState === EventSource.CLOSED) {
            es.close();
            esRef.current = null;
            scheduleReconnect();
          }
          // If readyState is CONNECTING, the browser is already retrying
          // the same URL (which will fail if the token expired).
          // Close it and do our own reconnect with a fresh token.
          if (es.readyState === EventSource.CONNECTING) {
            es.close();
            esRef.current = null;
            scheduleReconnect();
          }
        };
      } catch (err) {
        if (cancelled || terminalRef.current) return;

        // Token fetch or EventSource setup failed — try reconnecting
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          scheduleReconnect();
        } else {
          setState((prev) => ({
            ...prev,
            status: 'error',
            error: err instanceof Error ? err.message : 'Failed to connect',
          }));
        }
      }
    };

    /**
     * Schedule a reconnection with exponential backoff.
     */
    const scheduleReconnect = () => {
      if (cancelled || terminalRef.current) return;

      reconnectAttempts += 1;

      if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
        setState((prev) => {
          if (prev.status === 'completed') return prev;
          return {
            ...prev,
            status: 'error',
            error: 'Connection lost — max reconnection attempts reached',
          };
        });
        return;
      }

      // Update status to show we're reconnecting (keep existing events)
      setState((prev) => {
        if (prev.status === 'completed' || prev.status === 'error') return prev;
        return { ...prev, status: 'connecting' };
      });

      const delay = Math.min(
        RECONNECT_BASE_DELAY_MS * Math.pow(2, reconnectAttempts - 1),
        RECONNECT_MAX_DELAY_MS,
      );

      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, delay);
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [taskId, handleEvent]);

  return state;
}
