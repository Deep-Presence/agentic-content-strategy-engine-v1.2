import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import React from 'react';
import { SWRConfig } from 'swr';
import { useApiQuery } from '@/lib/hooks/useApiQuery';

// Mock the api client module — SWR fetcher delegates to apiGet
vi.mock('@/lib/api/client', () => ({
  apiGet: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.name = 'ApiError';
      this.status = status;
      this.detail = detail;
    }
  },
}));

import { apiGet } from '@/lib/api/client';
const mockApiGet = apiGet as ReturnType<typeof vi.fn>;

// Fresh SWR cache per test — prevents cross-test contamination
function wrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(SWRConfig, {
    value: {
      provider: () => new Map(),
      dedupingInterval: 0,
      fetcher: (key: string) => apiGet(key),
    },
  }, children);
}

describe('useApiQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns idle state when path is null', () => {
    const { result } = renderHook(() => useApiQuery(null), { wrapper });

    expect(result.current.data).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it('fetches data on mount and returns loading then success', async () => {
    const mockData = { total_queries: 100, spa_score: 0.85 };
    mockApiGet.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useApiQuery('/api/v1/test'), { wrapper });

    // Initially loading
    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeNull();

    // After fetch completes
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBeNull();
    expect(mockApiGet).toHaveBeenCalledWith('/api/v1/test');
  });

  it('handles API errors', async () => {
    const { ApiError } = await import('@/lib/api/client');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const error = new (ApiError as any)(404, 'Not found');
    mockApiGet.mockRejectedValue(error);

    const { result } = renderHook(() => useApiQuery('/api/v1/missing'), { wrapper });

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error!.message).toBe('Not found');
  });

  it('refetches data when refetch is called', async () => {
    const data1 = { count: 1 };
    const data2 = { count: 2 };
    mockApiGet.mockResolvedValueOnce(data1).mockResolvedValueOnce(data2);

    const { result } = renderHook(() => useApiQuery('/api/v1/test'), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(data1);
    });

    // Trigger refetch
    act(() => {
      result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(data2);
    });
  });

  it('refetches when path changes', async () => {
    const data1 = { slug: 'a' };
    const data2 = { slug: 'b' };
    mockApiGet.mockResolvedValueOnce(data1).mockResolvedValueOnce(data2);

    const { result, rerender } = renderHook(
      ({ path }) => useApiQuery(path),
      { initialProps: { path: '/api/v1/a' as string | null }, wrapper },
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(data1);
    });

    // Change path
    rerender({ path: '/api/v1/b' });

    await waitFor(() => {
      expect(result.current.data).toEqual(data2);
    });
  });

  it('skips fetch when path changes from string to null', async () => {
    mockApiGet.mockResolvedValueOnce({ ok: true });

    const { result, rerender } = renderHook(
      ({ path }) => useApiQuery(path),
      { initialProps: { path: '/api/v1/test' as string | null }, wrapper },
    );

    await waitFor(() => {
      expect(result.current.data).toEqual({ ok: true });
    });

    // Change to null
    rerender({ path: null });

    await waitFor(() => {
      expect(result.current.data).toBeNull();
    });
    expect(result.current.isLoading).toBe(false);
  });
});
