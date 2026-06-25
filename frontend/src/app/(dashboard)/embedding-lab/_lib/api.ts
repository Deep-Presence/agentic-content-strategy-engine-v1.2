/**
 * API functions for the Embedding Lab page.
 * All calls go through the BFF proxy (same-origin, httpOnly cookie auth).
 */
import { api } from '@/lib/api-client';
import type {
  ClusterProfileListAPI,
  EmbeddingProjectionAPI,
  TerritoryGapsResponseAPI,
} from './types';

export function fetchClusterProfiles(
  slug: string,
  signal?: AbortSignal,
): Promise<ClusterProfileListAPI> {
  return api.get<ClusterProfileListAPI>(
    `/api/v1/companies/${slug}/gap-analysis/cluster-profiles`,
    undefined,
    signal,
  );
}

export function fetchTerritoryGaps(
  slug: string,
  signal?: AbortSignal,
): Promise<TerritoryGapsResponseAPI> {
  return api.get<TerritoryGapsResponseAPI>(
    `/api/v1/companies/${slug}/gap-analysis/territory-gaps`,
    undefined,
    signal,
  );
}

export function fetchEmbeddingProjection(
  slug: string,
  method: 'umap' | 'tsne' = 'umap',
  signal?: AbortSignal,
): Promise<EmbeddingProjectionAPI> {
  return api.get<EmbeddingProjectionAPI>(
    `/api/v1/companies/${slug}/gap-analysis/embeddings`,
    { method },
    signal,
  );
}
