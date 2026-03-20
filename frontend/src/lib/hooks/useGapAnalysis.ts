/**
 * Gap Analysis data-fetching hooks.
 * Each hook wraps useApiQuery for a specific gap data endpoint.
 * Long cache (60s dedup, no stale revalidation) — data only changes when a pipeline runs.
 */

import { useApiQuery, type UseApiQueryOptions } from './useApiQuery';
import { GAP_DATA } from '@/lib/api/endpoints';
import type {
  GapSummaryResponse,
  ClusterListResponse,
  PlatformListResponse,
  SignalAveragesResponse,
  HeatmapResponse,
  SPATrendResponse,
  EmbeddingProjectionResponse,
} from '@/lib/api/types';

const GAP_CACHE: UseApiQueryOptions = { dedupingInterval: 60_000, revalidateIfStale: false };

export function useGapSummary(slug: string | undefined) {
  return useApiQuery<GapSummaryResponse>(slug ? GAP_DATA.summary(slug) : null, GAP_CACHE);
}

export function useGapClusters(slug: string | undefined) {
  return useApiQuery<ClusterListResponse>(slug ? GAP_DATA.clusters(slug) : null, GAP_CACHE);
}

export function useGapPlatforms(slug: string | undefined) {
  return useApiQuery<PlatformListResponse>(slug ? GAP_DATA.platforms(slug) : null, GAP_CACHE);
}

export function useGapSignals(slug: string | undefined) {
  return useApiQuery<SignalAveragesResponse>(slug ? GAP_DATA.signals(slug) : null, GAP_CACHE);
}

export function useGapHeatmap(slug: string | undefined) {
  return useApiQuery<HeatmapResponse>(slug ? GAP_DATA.heatmap(slug) : null, GAP_CACHE);
}

export function useSpaTrend(slug: string | undefined) {
  return useApiQuery<SPATrendResponse>(slug ? GAP_DATA.trend(slug) : null, GAP_CACHE);
}

export function useEmbeddings(slug: string | undefined, method: 'umap' | 'tsne' = 'umap') {
  const path = slug ? `${GAP_DATA.embeddings(slug)}?method=${method}` : null;
  return useApiQuery<EmbeddingProjectionResponse>(path, GAP_CACHE);
}
