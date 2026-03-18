import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { SWRConfig } from 'swr';
import { useTaxonomy, useScoredSubdomains, usePersonaAffinity, useMatrix } from '@/lib/hooks/useTopicDiscovery';

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

function wrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(SWRConfig, {
    value: { provider: () => new Map(), dedupingInterval: 0, fetcher: (key: string) => apiGet(key) },
  }, children);
}

describe('Topic Discovery hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useTaxonomy fetches taxonomy for slug', async () => {
    const mockTax = { slug: 'test-co', taxonomy: { root: [] }, version: 2, total_subdomains: 50, coverage_score: 0.85 };
    mockApiGet.mockResolvedValueOnce(mockTax);

    const { result } = renderHook(() => useTaxonomy('test-co'), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockTax);
    });

    expect(mockApiGet).toHaveBeenCalledWith(
      '/api/v1/topic-discovery/test-co/taxonomy',
    );
  });

  it('useScoredSubdomains fetches scores', async () => {
    const mockScored = { slug: 'test-co', scored_subdomains: {}, version: 1, total_scored: 30, signals_used: ['citation'] };
    mockApiGet.mockResolvedValueOnce(mockScored);

    const { result } = renderHook(() => useScoredSubdomains('test-co'), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockScored);
    });
  });

  it('usePersonaAffinity fetches persona data', async () => {
    const mockAffinity = { slug: 'test-co', persona_entries: {}, total_personas: 3, total_subdomains: 50 };
    mockApiGet.mockResolvedValueOnce(mockAffinity);

    const { result } = renderHook(() => usePersonaAffinity('test-co'), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockAffinity);
    });
  });

  it('useMatrix fetches assignment matrix', async () => {
    const mockMatrix = { slug: 'test-co', matrix: { assignments: [] }, version: 2, total_assignments: 100 };
    mockApiGet.mockResolvedValueOnce(mockMatrix);

    const { result } = renderHook(() => useMatrix('test-co'), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockMatrix);
    });
  });

  it('skips fetch when slug is undefined', () => {
    const { result } = renderHook(() => useTaxonomy(undefined), { wrapper });
    expect(result.current.data).toBeNull();
    expect(mockApiGet).not.toHaveBeenCalled();
  });
});
