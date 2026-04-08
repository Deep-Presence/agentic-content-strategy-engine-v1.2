'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { fetchBriefs } from '../_lib/api';
import { adaptBriefList } from '../_lib/adapters';
import { isAgentProcessing } from '../_lib/status-adapter';
import type { ContentCard } from '../_components/types';

const POLL_FAST_MS = 5_000;
const POLL_SLOW_MS = 60_000;
/** How long optimistic updates are protected from poll overwrite (ms). */
const OPTIMISTIC_GRACE_MS = 15_000;

/**
 * Fetches briefs from GET /companies/{slug}/content/briefs and adapts
 * them into ContentCard[]. Uses adaptive polling: 5s when any card is
 * agent-active or HITL-waiting, 60s when all terminal/idle, no polling
 * when zero cards.
 *
 * Optimistic grace: after updateCard() is called (user action), the
 * affected card's status is protected from poll overwrite for 15s.
 * This prevents stale server responses from reverting the UI while
 * the pipeline processes the approval.
 */
export function useContentBriefs() {
  const { companySlug, isInitialized } = useAuth();
  const [cards, setCards] = useState<ContentCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevHasActiveRef = useRef<boolean | null>(null);
  /** Map of cardId → timestamp when optimistic update was applied. */
  const optimisticRef = useRef<Map<string, number>>(new Map());

  const doFetch = useCallback(async () => {
    if (!companySlug) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const data = await fetchBriefs(companySlug, undefined, controller.signal);
      if (!controller.signal.aborted) {
        // Debug: log status values from API for kanban sync diagnosis
        if (data.briefs.length > 0) {
          console.debug(`[useContentBriefs] poll @${new Date().toISOString()}:`, data.briefs.map(b => `${b.id}:${b.status}`).join(', '));
        }
        setCards((prevCards) => {
          const incoming = adaptBriefList(data.briefs);
          // On first load (no existing cards), skip merge overhead
          if (prevCards.length === 0) return incoming;

          const prevMap = new Map(prevCards.map((c) => [c.id, c]));
          const merged: ContentCard[] = [];
          const now = Date.now();
          const ts = new Date().toISOString();

          for (const card of incoming) {
            const existing = prevMap.get(card.id);
            if (!existing) {
              console.debug(`[useContentBriefs] merge @${ts}: NEW ${card.id} status=${card.status}`);
              merged.push(card); // new card from server
              continue;
            }

            // Check optimistic grace period: if the card was recently
            // updated by a user action, keep the local status and don't
            // let the (potentially stale) server response overwrite it.
            const optimisticTs = optimisticRef.current.get(card.id);
            if (optimisticTs && now - optimisticTs < OPTIMISTIC_GRACE_MS) {
              if (existing.status !== card.status) {
                console.info(`[useContentBriefs] OPTIMISTIC PROTECTED @${ts}: ${card.id} keeping local=${existing.status} (server=${card.status}, grace=${Math.round((OPTIMISTIC_GRACE_MS - (now - optimisticTs)) / 1000)}s left)`);
              }
              // Take server data for non-status fields, but keep local status + agentProgress
              merged.push({ ...card, status: existing.status, agentProgress: existing.agentProgress });
              continue;
            }

            // Grace period expired or no optimistic update — normal merge
            if (optimisticTs) {
              optimisticRef.current.delete(card.id);
            }

            if ((card.updatedAt ?? '') >= (existing.updatedAt ?? '')) {
              if (existing.status !== card.status) {
                console.info(`[useContentBriefs] STATUS CHANGE @${ts}: ${card.id} ${existing.status} -> ${card.status} (server wins, updatedAt: ${existing.updatedAt} -> ${card.updatedAt})`);
              }
              merged.push(existing.agentProgress
                ? { ...card, agentProgress: existing.agentProgress }
                : card,
              );
            } else {
              console.debug(`[useContentBriefs] merge @${ts}: LOCAL KEPT ${card.id} status=${existing.status} (server=${card.status}, local updatedAt=${existing.updatedAt} > server=${card.updatedAt})`);
              merged.push(existing); // keep local (SSE was ahead)
            }
          }

          // Don't keep local cards the server no longer returns
          return merged;
        });
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

  // Derive stable booleans so the polling effect doesn't re-run on every fetch
  const cardCount = cards.length;
  const hasActive = useMemo(
    () => cards.some((c) =>
      isAgentProcessing(c.status)
      || c.status === 'gap_analysis_pending'
      // HITL-waiting statuses still have an active pipeline behind them —
      // poll fast so the UI catches auto-approvals and user actions quickly
      || c.status === 'pending_brief_approval'
      || c.status === 'pending_content_approval'
      || c.status === 'brief_review'
      || c.status === 'review'
    ),
    [cards],
  );

  // Adaptive polling: 5s when active/HITL, 60s when all terminal, none when empty
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    if (cardCount === 0) return;

    if (prevHasActiveRef.current !== null && prevHasActiveRef.current !== hasActive) {
      console.info(`[useContentBriefs] polling speed @${new Date().toISOString()}: ${hasActive ? 'FAST (5s) — active cards detected' : 'SLOW (60s) — all idle'}`);
    }
    prevHasActiveRef.current = hasActive;

    const interval = hasActive ? POLL_FAST_MS : POLL_SLOW_MS;
    pollRef.current = setInterval(doFetch, interval);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [hasActive, cardCount, doFetch]);

  // Imperative card update (for SSE-driven status changes and user actions).
  // Marks the card as "optimistically updated" so polls don't overwrite it
  // for OPTIMISTIC_GRACE_MS.
  const updateCard = useCallback((cardId: string, updates: Partial<ContentCard>) => {
    if (updates.status) {
      optimisticRef.current.set(cardId, Date.now());
    }
    setCards((prev) =>
      prev.map((c) => (c.id === cardId
        ? { ...c, ...updates, updatedAt: new Date().toISOString() }
        : c)),
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
