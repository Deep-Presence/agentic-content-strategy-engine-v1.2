'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { fetchGapSummary } from '../_lib/api';
import type { GapSummaryResponseAPI } from '../_lib/types';

/**
 * Fetches gap analysis summary for the gap metrics display.
 * Used in the GA-complete center view and the right sidebar gap section.
 *
 * @param enabled  Only fetch when true (card is in GA-complete or later)
 * @param productSlug  Optional product slug parsed from effectiveSlug
 * @param gaRunId  When provided, loads topic-scoped GA results instead of company-wide
 */
export function useGapSummary(enabled: boolean, productSlug?: string, gaRunId?: string) {
  const { companySlug } = useAuth();
  const [data, setData] = useState<GapSummaryResponseAPI | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Track the params that produced the current data so we invalidate on change
  const dataKeyRef = useRef<string>('');

  useEffect(() => {
    if (!enabled || !companySlug) {
      return;
    }

    // Invalidate cached data when key params change (Codex finding #2)
    const currentKey = `${companySlug}:${productSlug ?? ''}:${gaRunId ?? ''}`;
    if (data && dataKeyRef.current === currentKey) return;
    if (dataKeyRef.current !== currentKey) {
      setData(null);
      dataKeyRef.current = currentKey;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    (async () => {
      try {
        const result = await fetchGapSummary(
          companySlug,
          productSlug,
          controller.signal,
          gaRunId,
        );
        if (!controller.signal.aborted) {
          setData(result);
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error ? err.message : 'Failed to load gap summary',
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    })();

    return () => controller.abort();
  }, [enabled, companySlug, productSlug, gaRunId, data]);

  return { data, isLoading, error };
}
