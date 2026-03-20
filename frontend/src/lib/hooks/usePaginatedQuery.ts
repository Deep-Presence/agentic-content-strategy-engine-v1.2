import { useState, useCallback, useMemo } from 'react';
import useSWR from 'swr';
import type { ApiError } from '@/lib/api/client';

export interface PaginatedQueryResult<T> {
  data: T | null;
  isLoading: boolean;
  error: ApiError | null;
  page: number;
  setPage: (n: number) => void;
  pageSize: number;
  setPageSize: (n: number) => void;
  totalPages: number;
  refetch: () => void;
}

/**
 * Data-fetching hook with server-side pagination support, backed by SWR.
 * Builds query string from page/pageSize/extra params.
 * Pass `null` as basePath to skip fetch.
 */
export function usePaginatedQuery<T extends { total_pages?: number }>(
  basePath: string | null,
  extraParams: Record<string, string | number | undefined> = {},
): PaginatedQueryResult<T> {
  const [page, setPageState] = useState(1);
  const [pageSize, setPageSizeState] = useState(15);

  const setPage = useCallback((n: number) => setPageState(n), []);
  const setPageSize = useCallback((n: number) => {
    setPageSizeState(n);
    setPageState(1);
  }, []);

  // Serialize extra params for stable dependency tracking
  const extraParamsKey = JSON.stringify(extraParams);

  const key = useMemo(() => {
    if (!basePath) return null;
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    for (const [k, v] of Object.entries(extraParams)) {
      if (v !== undefined && v !== '') params.set(k, String(v));
    }
    return `${basePath}?${params.toString()}`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basePath, page, pageSize, extraParamsKey]);

  const { data, error, mutate } = useSWR<T, ApiError>(key);

  const totalPages = data && typeof data === 'object' && 'total_pages' in data
    ? (data as Record<string, unknown>).total_pages as number ?? 0
    : 0;

  return {
    data: data ?? null,
    isLoading: data === undefined && !error && key !== null,
    error: error ?? null,
    page,
    setPage,
    pageSize,
    setPageSize,
    totalPages,
    refetch: () => { mutate(); },
  };
}
