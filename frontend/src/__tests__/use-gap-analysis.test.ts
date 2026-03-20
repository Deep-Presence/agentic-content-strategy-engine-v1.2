import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { SWRConfig } from 'swr';
import {
  useGapSummary,
  useGapClusters,
  useGapPlatforms,
  useGapSignals,
  useGapHeatmap,
  useSpaTrend,
  useEmbeddings,
} from '@/lib/hooks/useGapAnalysis';

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

describe('Gap Analysis hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useGapSummary', () => {
    it('fetches gap summary for a slug', async () => {
      const mockSummary = {
        spa_score: { t_stat: 2.5, p_value: 0.01, effect: 'medium' },
        total_queries: 100,
        total_citations: 500,
        classification_counts: { significant_gap: 40, gap_to_close: 30, roughly_equal: 20, company_wins: 10 },
        cluster_performance: [],
      };
      mockApiGet.mockResolvedValueOnce(mockSummary);

      const { result } = renderHook(() => useGapSummary('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockSummary);
      expect(mockApiGet).toHaveBeenCalledWith(
        '/api/v1/companies/test-co/gap-analysis/summary',
      );
    });

    it('skips fetch when slug is undefined', () => {
      const { result } = renderHook(() => useGapSummary(undefined), { wrapper });
      expect(result.current.data).toBeNull();
      expect(result.current.isLoading).toBe(false);
      expect(mockApiGet).not.toHaveBeenCalled();
    });

    it('handles 404 error', async () => {
      const { ApiError } = await import('@/lib/api/client');
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockApiGet.mockRejectedValue(new (ApiError as any)(404, 'No gap data'));

      const { result } = renderHook(() => useGapSummary('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.error).toBeTruthy();
      });

      expect(result.current.data).toBeNull();
    });
  });

  describe('useGapClusters', () => {
    it('fetches clusters for a slug', async () => {
      const mockClusters = { clusters: [{ cluster_id: 'c-1', cluster_name: 'SEO', query_count: 20 }] };
      mockApiGet.mockResolvedValueOnce(mockClusters);

      const { result } = renderHook(() => useGapClusters('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockClusters);
      });

      expect(mockApiGet).toHaveBeenCalledWith(
        '/api/v1/companies/test-co/gap-analysis/clusters',
      );
    });
  });

  describe('useGapPlatforms', () => {
    it('fetches platform data', async () => {
      const mockPlatforms = {
        platforms: [{ name: 'perplexity', total_citations: 150 }],
        agreement: {},
        citation_exclusivity: {},
      };
      mockApiGet.mockResolvedValueOnce(mockPlatforms);

      const { result } = renderHook(() => useGapPlatforms('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockPlatforms);
      });
    });
  });

  describe('useGapSignals', () => {
    it('fetches signal averages', async () => {
      const mockSignals = { signals: [], correlations: [], cluster_patterns: [], cluster_fingerprints: {} };
      mockApiGet.mockResolvedValueOnce(mockSignals);

      const { result } = renderHook(() => useGapSignals('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockSignals);
      });
    });
  });

  describe('useGapHeatmap', () => {
    it('fetches heatmap data', async () => {
      const mockHeatmap = { clusters: [], min_gap: 0, max_gap: 1 };
      mockApiGet.mockResolvedValueOnce(mockHeatmap);

      const { result } = renderHook(() => useGapHeatmap('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockHeatmap);
      });
    });
  });

  describe('useSpaTrend', () => {
    it('fetches SPA trend data', async () => {
      const mockTrend = { data_points: [{ date: '2026-03-01', value: 0.85 }] };
      mockApiGet.mockResolvedValueOnce(mockTrend);

      const { result } = renderHook(() => useSpaTrend('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockTrend);
      });
    });
  });

  describe('useEmbeddings', () => {
    it('fetches embedding projections with method param', async () => {
      const mockEmbeddings = { points: [{ x: 1, y: 2, type: 'query' }], method: 'umap' };
      mockApiGet.mockResolvedValueOnce(mockEmbeddings);

      const { result } = renderHook(() => useEmbeddings('test-co', 'umap'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockEmbeddings);
      });

      expect(mockApiGet).toHaveBeenCalledWith(
        '/api/v1/companies/test-co/gap-analysis/embeddings?method=umap',
      );
    });

    it('defaults to umap when no method specified', async () => {
      mockApiGet.mockResolvedValueOnce({ points: [], method: 'umap' });

      renderHook(() => useEmbeddings('test-co'), { wrapper });

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledWith(
          expect.stringContaining('method=umap'),
        );
      });
    });
  });
});
