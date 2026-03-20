import useSWR, { SWRConfiguration } from 'swr';
import useSWRImmutable from 'swr/immutable';
import type { ApiError } from '@/lib/api/client';

export interface UseApiQueryResult<T> {
  data: T | null;
  isLoading: boolean;
  error: ApiError | null;
  refetch: () => void;
}

export interface UseApiQueryOptions {
  /** Dedup interval in ms (default: inherit from provider) */
  dedupingInterval?: number;
  /** Polling interval in ms (0 = disabled) */
  refreshInterval?: number;
  /** Whether to revalidate stale data (default: true) */
  revalidateIfStale?: boolean;
  /** If true, never revalidate automatically (ideal for immutable data) */
  immutable?: boolean;
}

/**
 * Generic data-fetching hook backed by SWR.
 * Pass `null` as path to skip the fetch (conditional loading).
 */
export function useApiQuery<T>(
  path: string | null,
  options?: UseApiQueryOptions,
): UseApiQueryResult<T> {
  const swrOptions: SWRConfiguration = {};
  if (options?.dedupingInterval !== undefined) swrOptions.dedupingInterval = options.dedupingInterval;
  if (options?.refreshInterval !== undefined) swrOptions.refreshInterval = options.refreshInterval;
  if (options?.revalidateIfStale !== undefined) swrOptions.revalidateIfStale = options.revalidateIfStale;

  const hook = options?.immutable ? useSWRImmutable : useSWR;
  const { data, error, mutate } = hook<T, ApiError>(path, swrOptions);

  return {
    data: data ?? null,
    isLoading: data === undefined && !error && path !== null,
    error: error ?? null,
    refetch: () => { mutate(); },
  };
}
