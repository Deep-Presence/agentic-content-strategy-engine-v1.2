'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { fetchBriefs } from '../_lib/api';
import { adaptBriefList } from '../_lib/adapters';
import { isAgentProcessing } from '../_lib/status-adapter';
import type { ContentCard } from '../_components/types';

const POLL_INTERVAL_MS = 15_000;

/**
 * Fetches briefs from GET /companies/{slug}/content/briefs and adapts
 * them into ContentCard[]. Polls every 15s when any card is in an
 * agent-active state. Stops polling when all cards are idle.
 */
export function useContentBriefs() {
  const { companySlug, isInitialized } = useAuth();
  const [cards, setCards] = useState<ContentCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const doFetch = useCallback(async () => {
    if (!companySlug) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const data = await fetchBriefs(companySlug, undefined, controller.signal);
      if (!controller.signal.aborted) {
        setCards(adaptBriefList(data.briefs));
        setError(null);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      const message = err instanceof Error ? err.message : 'Failed to load briefs';
      setError(message);
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, [companySlug]);

  // Initial fetch
  useEffect(() => {
    if (!isInitialized || !companySlug) return;
    setIsLoading(true);
    doFetch();

    return () => {
      abortRef.current?.abort();
    };
  }, [isInitialized, companySlug, doFetch]);

  // Polling: re-fetch every 15s when any card is agent-active
  useEffect(() => {
    const hasActive = cards.some(
      (c) => isAgentProcessing(c.status) || c.status === 'gap_analysis_pending',
    );

    if (hasActive) {
      if (!pollRef.current) {
        pollRef.current = setInterval(doFetch, POLL_INTERVAL_MS);
      }
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [cards, doFetch]);

  // Imperative card update (for SSE-driven status changes)
  const updateCard = useCallback((cardId: string, updates: Partial<ContentCard>) => {
    setCards((prev) =>
      prev.map((c) => (c.id === cardId ? { ...c, ...updates } : c)),
    );
  }, []);

  // Add a new card to the list (for optimistic UI after addBrief)
  const addCard = useCallback((card: ContentCard) => {
    setCards((prev) => [card, ...prev]);
  }, []);

  return {
    cards,
    isLoading,
    error,
    isEmpty: !isLoading && cards.length === 0,
    refetch: doFetch,
    updateCard,
    addCard,
  };
}
