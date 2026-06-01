/**
 * useStreamToken — SSE stream token acquisition hook.
 *
 * Foundation for future SSE pages (pipeline progress, HITL, etc.).
 * Acquires a short-lived stream token from the backend for EventSource connections.
 */

import { useState, useCallback } from 'react';
import { api, workspaceQueryParams } from '@/lib/api-client';
import type { StreamTokenResponse } from '@/lib/auth/types';

export function useStreamToken(taskId: string) {
  const [streamToken, setStreamToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const acquire = useCallback(async (): Promise<string | null> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.post<StreamTokenResponse>(
        `/api/v1/tasks/${taskId}/stream-token`,
        undefined,
        { params: workspaceQueryParams() },
      );
      setStreamToken(res.stream_token);
      return res.stream_token;
    } catch {
      setError('Failed to acquire stream token');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [taskId]);

  return { streamToken, acquire, isLoading, error };
}
