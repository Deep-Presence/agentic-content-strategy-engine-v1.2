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
 */
export function useGapSummary(enabled: boolean, productSlug?: string) {
  const { companySlug } = useAuth();
  const [data, setData] = useState<GapSummaryResponseAPI | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled || !companySlug) {
      return;
    }

    // Don't re-fetch if we already have data
    if (data) return;

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
  }, [enabled, companySlug, productSlug, data]);

  return { data, isLoading, error };
}
