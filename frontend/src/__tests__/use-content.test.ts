import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { SWRConfig } from 'swr';
import { useContentBriefs, useContentBriefDetail, useContentStage } from '@/lib/hooks/useContent';

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

describe('Content hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useContentBriefs', () => {
    it('fetches briefs for a slug', async () => {
      const mockBriefs = {
        briefs: [
          { id: 'b-1', title: 'Test Brief', status: 'suggested', content_type: 'blog', cluster: 'seo' },
          { id: 'b-2', title: 'Second Brief', status: 'approved', content_type: 'article', cluster: 'seo' },
        ],
        total: 2,
      };
      mockApiGet.mockResolvedValueOnce(mockBriefs);

      const { result } = renderHook(() => useContentBriefs('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockBriefs);
      expect(mockApiGet).toHaveBeenCalledWith(
        '/api/v1/companies/test-co/content/briefs',
      );
    });

    it('skips fetch when slug is undefined', () => {
      const { result } = renderHook(() => useContentBriefs(undefined), { wrapper });
      expect(result.current.data).toBeNull();
      expect(mockApiGet).not.toHaveBeenCalled();
    });
  });

  describe('useContentBriefDetail', () => {
    it('fetches detail for slug + briefId', async () => {
      const mockDetail = {
        id: 'b-1', title: 'Test', status: 'suggested',
        available_stages: ['outline', 'draft'],
        eval_history: [],
      };
      mockApiGet.mockResolvedValueOnce(mockDetail);

      const { result } = renderHook(() => useContentBriefDetail('test-co', 'b-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockDetail);
      });
    });

    it('skips when briefId is null', () => {
      const { result } = renderHook(() => useContentBriefDetail('test-co', null), { wrapper });
      expect(result.current.data).toBeNull();
      expect(mockApiGet).not.toHaveBeenCalled();
    });
  });

  describe('useContentStage', () => {
    it('fetches stage content', async () => {
      const mockStage = { brief_id: 'b-1', stage: 'outline', content_type: 'text/markdown', content: '# Outline' };
      mockApiGet.mockResolvedValueOnce(mockStage);

      const { result } = renderHook(() => useContentStage('test-co', 'b-1', 'outline'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockStage);
      });
    });

    it('skips when stage is null', () => {
      const { result } = renderHook(() => useContentStage('test-co', 'b-1', null), { wrapper });
      expect(result.current.data).toBeNull();
    });
  });
});
