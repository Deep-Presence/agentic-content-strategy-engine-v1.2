import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import React from 'react';
import { SWRConfig } from 'swr';
import {
  useCMSConnection,
  useCMSSyncedPosts,
  useCMSStaleActions,
  useCMSStaleToTriage,
} from '@/lib/hooks/useCMS';

vi.mock('@/lib/api/client', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
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

import { apiGet, apiPost } from '@/lib/api/client';
const mockApiGet = apiGet as ReturnType<typeof vi.fn>;
const mockApiPost = apiPost as ReturnType<typeof vi.fn>;

function wrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(SWRConfig, {
    value: {
      provider: () => new Map(),
      dedupingInterval: 0,
      fetcher: (key: string) => apiGet(key),
    },
  }, children);
}

describe('CMS hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useCMSConnection', () => {
    it('returns connection info when CMS is connected', async () => {
      const mockConnection = {
        provider: 'wordpress',
        site_url: 'https://blog.ramp.com',
        site_name: 'Ramp Blog',
        cms_version: '6.7',
        user_display_name: 'Admin',
        is_active: true,
        last_sync_at: '2026-03-26T10:00:00Z',
        sync_post_count: 142,
      };
      mockApiGet.mockResolvedValueOnce(mockConnection);

      const { result } = renderHook(() => useCMSConnection(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockConnection);
      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/cms/connection');
    });

    it('returns null when no CMS is connected', async () => {
      mockApiGet.mockResolvedValueOnce(null);

      const { result } = renderHook(() => useCMSConnection(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeNull();
    });
  });

  describe('useCMSSyncedPosts', () => {
    it('fetches synced posts with default params', async () => {
      const mockPosts = [
        {
          id: 'p-1',
          cms_post_id: '101',
          title: 'Test Post',
          slug: 'test-post',
          url: 'https://blog.ramp.com/test-post',
          word_count: 1200,
          published_at: '2026-01-15T12:00:00Z',
          modified_at: '2026-02-01T12:00:00Z',
          is_stale: true,
          staleness_days: 53,
          categories: ['Finance'],
          queued_for_refresh: false,
        },
      ];
      mockApiGet.mockResolvedValueOnce(mockPosts);

      const { result } = renderHook(() => useCMSSyncedPosts(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockPosts);
      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/cms/synced-posts');
    });

    it('passes staleOnly query param', async () => {
      mockApiGet.mockResolvedValueOnce([]);

      const { result } = renderHook(
        () => useCMSSyncedPosts({ staleOnly: true }),
        { wrapper },
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockApiGet).toHaveBeenCalledWith(
        '/api/v1/cms/synced-posts?stale_only=true',
      );
    });

    it('passes limit and offset params', async () => {
      mockApiGet.mockResolvedValueOnce([]);

      const { result } = renderHook(
        () => useCMSSyncedPosts({ limit: 50, offset: 10 }),
        { wrapper },
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockApiGet).toHaveBeenCalledWith(
        '/api/v1/cms/synced-posts?limit=50&offset=10',
      );
    });
  });

  describe('useCMSStaleActions', () => {
    it('returns stale actions list', async () => {
      const mockActions = [
        {
          cms_synced_post_id: 'sp-1',
          cms_post_id: '101',
          title: 'Stale Post',
          url: 'https://blog.ramp.com/stale',
          staleness_days: 47,
          description: 'Last updated 47 days ago.',
          queued_for_refresh: false,
        },
      ];
      mockApiGet.mockResolvedValueOnce(mockActions);

      const { result } = renderHook(() => useCMSStaleActions(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockActions);
      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/cms/stale-actions');
    });

    it('returns empty array when no stale content', async () => {
      mockApiGet.mockResolvedValueOnce([]);

      const { result } = renderHook(() => useCMSStaleActions(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual([]);
    });
  });

  describe('useCMSStaleToTriage', () => {
    it('queues a post for refresh', async () => {
      const mockResult = {
        brief_id: 'b-refresh-1',
        title: 'Stale Post',
        status: 'triage',
      };
      mockApiPost.mockResolvedValueOnce(mockResult);

      const { result } = renderHook(() => useCMSStaleToTriage(), { wrapper });

      let response: typeof mockResult | null = null;
      await act(async () => {
        response = await result.current.queueForRefresh('sp-1');
      });

      expect(response).toEqual(mockResult);
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/v1/cms/stale-to-triage',
        { cms_synced_post_id: 'sp-1' },
      );
    });

    it('returns null on error', async () => {
      const { ApiError } = await import('@/lib/api/client');
      mockApiPost.mockRejectedValueOnce(new ApiError(500, 'Server error'));

      const { result } = renderHook(() => useCMSStaleToTriage(), { wrapper });

      let response: unknown = undefined;
      await act(async () => {
        response = await result.current.queueForRefresh('sp-1');
      });

      expect(response).toBeNull();
      expect(result.current.error).toBeTruthy();
    });
  });
});
