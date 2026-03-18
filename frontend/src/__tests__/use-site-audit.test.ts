import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { SWRConfig } from 'swr';
import { useSiteAuditLatest } from '@/lib/hooks/useSiteAudit';

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

describe('useSiteAuditLatest', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches latest audit: list then detail', async () => {
    const auditList = [
      { audit_id: 'a-2', domain: 'example.com', overall_score: 90, grade: 'A', status: 'completed', started_at: '2026-03-02' },
      { audit_id: 'a-1', domain: 'example.com', overall_score: 80, grade: 'B', status: 'completed', started_at: '2026-03-01' },
    ];
    const auditDetail = {
      audit_id: 'a-2',
      domain: 'example.com',
      overall_score: 90,
      grade: 'A',
      pages_crawled: 150,
      dimension_scores: [],
      ai_bot_access: { gptbot_allowed: true },
    };

    mockApiGet.mockImplementation((path: string) => {
      if (path.endsWith('/audits')) return Promise.resolve(auditList);
      if (path.endsWith('/a-2')) return Promise.resolve(auditDetail);
      return Promise.reject(new Error('unexpected path'));
    });

    const { result } = renderHook(() => useSiteAuditLatest('test-co'), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.audit).toEqual(auditDetail);
    expect(mockApiGet).toHaveBeenCalledTimes(2);
  });

  it('returns null audit when audit list is empty', async () => {
    mockApiGet.mockResolvedValueOnce([]);

    const { result } = renderHook(() => useSiteAuditLatest('test-co'), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.audit).toBeNull();
    expect(mockApiGet).toHaveBeenCalledTimes(1);
  });

  it('skips fetch when slug is undefined', () => {
    const { result } = renderHook(() => useSiteAuditLatest(undefined), { wrapper });
    expect(result.current.audit).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it('handles error on audit list fetch', async () => {
    const { ApiError } = await import('@/lib/api/client');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mockApiGet.mockRejectedValue(new (ApiError as any)(500, 'Server error'));

    const { result } = renderHook(() => useSiteAuditLatest('test-co'), { wrapper });

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    expect(result.current.audit).toBeNull();
  });
});
