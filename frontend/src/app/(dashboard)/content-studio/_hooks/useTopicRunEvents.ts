'use client';

import { useEffect, useRef, useState } from 'react';
import { fetchTopicRunEvents } from '../_lib/api';
import type { TopicRunEventAPI } from '../_lib/types';

export function useTopicRunEvents(
  effectiveSlug: string | null,
  topicRunId: string | null,
) {
  const [events, setEvents] = useState<TopicRunEventAPI[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!effectiveSlug || !topicRunId) {
      setEvents([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsLoading(true);
    setError(null);

    (async () => {
      try {
        const response = await fetchTopicRunEvents(
          effectiveSlug,
          topicRunId,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setEvents(response.items);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to load topic activity');
        setEvents([]);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, [effectiveSlug, topicRunId]);

  return { events, isLoading, error };
}
