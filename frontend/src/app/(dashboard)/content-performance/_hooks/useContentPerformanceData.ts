/**
 * Data hook for the Content Performance page.
 *
 * Fetches content table + velocity insights in parallel,
 * adapts backend responses to frontend display types.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import { fetchContentTable, fetchVelocityInsights } from '../_lib/api';
import { toContentPiece, toVelocityDatum } from '../_lib/adapters';
import type { ContentPiece, VelocityDatum } from '../_components/data';

export interface ContentPerformanceData {
  pieces: ContentPiece[];
  velocityData: VelocityDatum[];
  periodStart: string;
  periodEnd: string;
  totalItems: number;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useContentPerformanceData(
  dateParams?: { days?: number },
): ContentPerformanceData {
  const { companySlug, isInitialized } = useAuth();
  const [pieces, setPieces] = useState<ContentPiece[]>([]);
  const [velocityData, setVelocityData] = useState<VelocityDatum[]>([]);
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');
  const [totalItems, setTotalItems] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const days = dateParams?.days ?? 28;

  const loadData = useCallback(
    async (slug: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const signal = controller.signal;

      setIsLoading(true);
      setError(null);

      try {
        const [tableResp, velocityResp] = await Promise.all([
          fetchContentTable({ days }, signal),
          fetchVelocityInsights({ days }, signal),
        ]);

        if (signal.aborted) return;

        setPieces(tableResp.items.map(toContentPiece));
        setVelocityData(velocityResp.items.map(toVelocityDatum));
        setPeriodStart(tableResp.period_start);
        setPeriodEnd(tableResp.period_end);
        setTotalItems(tableResp.total_items);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        const msg =
          err instanceof ApiError
            ? err.detail
            : 'Failed to load content performance data';
        setError(msg);
      } finally {
        if (!signal.aborted) setIsLoading(false);
      }
    },
    [days],
  );

  useEffect(() => {
    if (!isInitialized || !companySlug) return;
    loadData(companySlug);
    return () => {
      abortRef.current?.abort();
    };
  }, [isInitialized, companySlug, loadData]);

  const refetch = useCallback(() => {
    if (companySlug) loadData(companySlug);
  }, [companySlug, loadData]);

  return {
    pieces,
    velocityData,
    periodStart,
    periodEnd,
    totalItems,
    isLoading,
    error,
    refetch,
  };
}
