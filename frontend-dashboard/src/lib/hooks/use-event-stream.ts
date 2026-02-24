'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { createEventStream } from '@/lib/api/sse';

interface EventStreamState {
  connected: boolean;
  events: Array<{ event: string; data: Record<string, unknown>; timestamp: number }>;
  lastEvent: string | null;
  error: string | null;
}

interface UseEventStreamOptions {
  onEvent?: (event: string, data: Record<string, unknown>) => void;
  autoConnect?: boolean;
}

export function useEventStream(taskId: string | null, options: UseEventStreamOptions = {}) {
  const { onEvent, autoConnect = true } = options;
  const [state, setState] = useState<EventStreamState>({
    connected: false,
    events: [],
    lastEvent: null,
    error: null,
  });
  const cleanupRef = useRef<(() => void) | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    if (!taskId) return;

    cleanupRef.current?.();

    setState((prev) => ({ ...prev, connected: true, error: null }));

    const cleanup = createEventStream(
      taskId,
      (event, data) => {
        setState((prev) => ({
          ...prev,
          events: [...prev.events, { event, data, timestamp: Date.now() }],
          lastEvent: event,
        }));
        onEventRef.current?.(event, data);
      },
      () => {
        setState((prev) => ({
          ...prev,
          connected: false,
          error: 'Connection lost. Attempting to reconnect...',
        }));
      }
    );

    cleanupRef.current = cleanup;
  }, [taskId]);

  const disconnect = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setState((prev) => ({ ...prev, connected: false }));
  }, []);

  useEffect(() => {
    if (autoConnect && taskId) {
      connect();
    }
    return () => {
      cleanupRef.current?.();
      cleanupRef.current = null;
    };
  }, [taskId, autoConnect, connect]);

  return { ...state, connect, disconnect };
}
