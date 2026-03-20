import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { SWRConfig } from 'swr';
import { useTeam, useProfile, usePipelineDefaults } from '@/lib/hooks/useSettings';

vi.mock('@/lib/api/client', () => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  apiPost: vi.fn(),
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

describe('Settings hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useTeam', () => {
    it('fetches team members', async () => {
      const mockTeam = {
        members: [
          { id: 'u-1', email: 'admin@test.com', first_name: 'Admin', last_name: 'User', role: 'superuser', is_active: true, created_at: '2026-01-01' },
        ],
        total: 1,
      };
      mockApiGet.mockResolvedValueOnce(mockTeam);

      const { result } = renderHook(() => useTeam('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockTeam);
      });

      expect(mockApiGet).toHaveBeenCalledWith(
        '/api/v1/companies/test-co/settings/team',
      );
    });

    it('skips when slug is undefined', () => {
      const { result } = renderHook(() => useTeam(undefined), { wrapper });
      expect(result.current.data).toBeNull();
      expect(mockApiGet).not.toHaveBeenCalled();
    });
  });

  describe('useProfile', () => {
    it('fetches company profile', async () => {
      const mockProfile = {
        slug: 'test-co', name: 'Test Co', domain: 'test.com',
        additional_domains: [], industry: 'Tech',
        created_at: '2026-01-01', updated_at: '2026-03-01',
      };
      mockApiGet.mockResolvedValueOnce(mockProfile);

      const { result } = renderHook(() => useProfile('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockProfile);
      });
    });
  });

  describe('usePipelineDefaults', () => {
    it('fetches pipeline defaults', async () => {
      const mockDefaults = {
        max_crawl_pages: 200, max_crawl_depth: 4, max_queries: 150,
        platforms: ['perplexity', 'openai'], max_personas: 5,
        auto_approve_research: false, max_briefs: 20,
        max_revision_cycles: 2, auto_approve_content: false,
      };
      mockApiGet.mockResolvedValueOnce(mockDefaults);

      const { result } = renderHook(() => usePipelineDefaults('test-co'), { wrapper });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockDefaults);
      });
    });
  });
});
