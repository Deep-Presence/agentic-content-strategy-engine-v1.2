'use client';

import { useEffect, useRef, useState } from 'react';
import { fetchTopicRunEvents } from '../_lib/api';
import {
  adaptTopicRunEventsToCardActivity,
  type CardActivityItem,
  type CardActivitySourceKind,
} from '../_lib/card-activity';

export function useCardActivity(
  effectiveSlug: string | null,
  topicRunId: string | null,
) {
  const [items, setItems] = useState<CardActivityItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sourceKind: CardActivitySourceKind = effectiveSlug && topicRunId
    ? 'topic_run'
    : 'unavailable';

  useEffect(() => {
    if (sourceKind !== 'topic_run') {
      setItems([]);
      setIsLoading(false);
      setError(null);
      return;
    }
    if (!effectiveSlug || !topicRunId) {
      setItems([]);
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
        setItems(adaptTopicRunEventsToCardActivity(response.items));
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to load card activity');
        setItems([]);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, [effectiveSlug, topicRunId, sourceKind]);

  return { items, isLoading, error, sourceKind };
}
