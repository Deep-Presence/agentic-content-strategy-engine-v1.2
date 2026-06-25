'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { fetchEmbeddingProjection } from '../_lib/api';
import { toEmbeddingPoints } from '../_lib/adapters';
import type { EmbeddingPoint } from '../_components/data';

export interface EmbeddingProjectionData {
  points: EmbeddingPoint[];
  pointCount: number;
  isLoading: boolean;
  error: string | null;
}

export function useEmbeddingProjection(
  method: 'umap' | 'tsne',
): EmbeddingProjectionData {
  const { companySlug, isInitialized } = useAuth();
  const abortRef = useRef<AbortController | null>(null);

  const [points, setPoints] = useState<EmbeddingPoint[]>([]);
  const [pointCount, setPointCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(
    async (slug: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const { signal } = controller;

      setIsLoading(true);
      setError(null);

      try {
        const data = await fetchEmbeddingProjection(slug, method, signal);
        if (signal.aborted) return;
        setPoints(toEmbeddingPoints(data.points));
        setPointCount(data.point_count);
      } catch (err) {
        if (signal.aborted) return;
        setError(err instanceof Error ? err.message : 'Failed to load embedding projection');
      } finally {
        if (!signal.aborted) setIsLoading(false);
      }
    },
    [method],
  );

  useEffect(() => {
    if (!isInitialized || !companySlug) return;
    loadData(companySlug);
  }, [isInitialized, companySlug, loadData]);

  return { points, pointCount, isLoading, error };
}
