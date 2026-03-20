/**
 * Topic Discovery data-fetching hooks.
 * Long cache (60s dedup, no stale revalidation) — taxonomies are stable.
 */

import { useApiQuery, type UseApiQueryOptions } from './useApiQuery';
import { TOPIC_DISCOVERY } from '@/lib/api/endpoints';
import type { TaxonomyReadResponse, MatrixReadResponse, ScoredSubdomainsResponse, PersonaAffinityResponse } from '@/lib/api/types';

const TOPIC_CACHE: UseApiQueryOptions = { dedupingInterval: 60_000, revalidateIfStale: false };

export function useTaxonomy(slug: string | undefined) {
  return useApiQuery<TaxonomyReadResponse>(slug ? TOPIC_DISCOVERY.taxonomy(slug) : null, TOPIC_CACHE);
}

export function useScoredSubdomains(slug: string | undefined) {
  return useApiQuery<ScoredSubdomainsResponse>(slug ? TOPIC_DISCOVERY.scoredSubdomains(slug) : null, TOPIC_CACHE);
}

export function usePersonaAffinity(slug: string | undefined) {
  return useApiQuery<PersonaAffinityResponse>(slug ? TOPIC_DISCOVERY.personas(slug) : null, TOPIC_CACHE);
}

export function useMatrix(slug: string | undefined) {
  return useApiQuery<MatrixReadResponse>(slug ? TOPIC_DISCOVERY.matrix(slug) : null, TOPIC_CACHE);
}
