import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import React from 'react';
import { SWRConfig } from 'swr';
import { usePaginatedQuery } from '@/lib/hooks/usePaginatedQuery';

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

interface MockResponse {
  items: string[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

function wrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(SWRConfig, {
    value: { provider: () => new Map(), dedupingInterval: 0, fetcher: (key: string) => apiGet(key) },
  }, children);
}

describe('usePaginatedQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns idle state when basePath is null', () => {
    const { result } = renderHook(() => usePaginatedQuery<MockResponse>(null), { wrapper });

    expect(result.current.data).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.page).toBe(1);
    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it('fetches with default pagination params', async () => {
    const mockData: MockResponse = {
      items: ['a', 'b'],
      total: 50,
      page: 1,
      page_size: 15,
      total_pages: 4,
    };
    mockApiGet.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() =>
      usePaginatedQuery<MockResponse>('/api/v1/test'),
    { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    const calledUrl = mockApiGet.mock.calls[0][0] as string;
    expect(calledUrl).toContain('page=1');
    expect(calledUrl).toContain('page_size=15');
  });

  it('builds query string with extra params', async () => {
    mockApiGet.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 15, total_pages: 0 });

    const { result } = renderHook(() =>
      usePaginatedQuery<MockResponse>('/api/v1/queries', {
        cluster: 'seo',
        sort_by: 'gap_score',
        sort_dir: 'desc',
      }),
    { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const calledUrl = mockApiGet.mock.calls[0][0] as string;
    expect(calledUrl).toContain('page=1');
    expect(calledUrl).toContain('page_size=15');
    expect(calledUrl).toContain('cluster=seo');
    expect(calledUrl).toContain('sort_by=gap_score');
    expect(calledUrl).toContain('sort_dir=desc');
  });

  it('refetches when page changes', async () => {
    const page1: MockResponse = { items: ['a'], total: 30, page: 1, page_size: 15, total_pages: 2 };
    const page2: MockResponse = { items: ['b'], total: 30, page: 2, page_size: 15, total_pages: 2 };
    mockApiGet.mockResolvedValueOnce(page1).mockResolvedValueOnce(page2);

    const { result } = renderHook(() =>
      usePaginatedQuery<MockResponse>('/api/v1/test'),
    { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(page1);
    });

    act(() => {
      result.current.setPage(2);
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(page2);
    });

    expect(result.current.page).toBe(2);
  });

  it('refetches when pageSize changes and resets to page 1', async () => {
    const resp1: MockResponse = { items: ['a'], total: 50, page: 1, page_size: 15, total_pages: 4 };
    const resp2: MockResponse = { items: ['a', 'b'], total: 50, page: 1, page_size: 50, total_pages: 1 };
    mockApiGet.mockResolvedValueOnce(resp1).mockResolvedValueOnce(resp2);

    const { result } = renderHook(() =>
      usePaginatedQuery<MockResponse>('/api/v1/test'),
    { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(resp1);
    });

    act(() => {
      result.current.setPageSize(50);
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(resp2);
    });

    expect(result.current.page).toBe(1);
    expect(result.current.pageSize).toBe(50);
  });

  it('handles API errors', async () => {
    const { ApiError } = await import('@/lib/api/client');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mockApiGet.mockRejectedValue(new (ApiError as any)(500, 'Server error'));

    const { result } = renderHook(() =>
      usePaginatedQuery<MockResponse>('/api/v1/test'),
    { wrapper });

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    expect(result.current.data).toBeNull();
  });
});
