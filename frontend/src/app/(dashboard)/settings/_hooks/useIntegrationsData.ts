'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api-client';
import {
  fetchCMSConnection,
  connectCMS,
  disconnectCMS,
  fetchGA4Connection,
  startGA4OAuth,
  disconnectGA4,
  fetchGA4Properties,
  selectGA4Property,
  triggerGA4Sync,
  fetchTaskStatus,
} from '../_lib/api';
import type {
  CMSConnectionInfoAPI,
  CMSConnectRequestAPI,
  GA4ConnectionResponseAPI,
  GA4PropertyItemAPI,
  GA4SelectPropertyRequestAPI,
  GA4SyncRequestAPI,
  GA4SyncResponseAPI,
  TaskStatusAPI,
} from '../_lib/types';

interface UseIntegrationsDataReturn {
  cmsConnection: CMSConnectionInfoAPI | null;
  ga4Connection: GA4ConnectionResponseAPI | null;
  ga4Properties: GA4PropertyItemAPI[];
  isLoading: boolean;
  error: string | null;
  // CMS mutations
  connectWordPress: (body: CMSConnectRequestAPI) => Promise<{ success: boolean; error?: string }>;
  disconnectWordPress: () => Promise<void>;
  // GA4 mutations
  startGA4Connect: () => Promise<void>;
  disconnectGA4Connection: (purgeData: boolean) => Promise<void>;
  loadGA4Properties: () => Promise<void>;
  selectProperty: (body: GA4SelectPropertyRequestAPI) => Promise<void>;
  syncGA4: (days?: number) => Promise<GA4SyncResponseAPI>;
  refetch: () => void;
}

export function useIntegrationsData(): UseIntegrationsDataReturn {
  const { isInitialized } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [cmsConnection, setCmsConnection] = useState<CMSConnectionInfoAPI | null>(null);
  const [ga4Connection, setGa4Connection] = useState<GA4ConnectionResponseAPI | null>(null);
  const [ga4Properties, setGa4Properties] = useState<GA4PropertyItemAPI[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const buildBackfillRequest = useCallback((days: number): GA4SyncRequestAPI => {
    const end = new Date();
    end.setDate(end.getDate() - 1);
    const start = new Date(end);
    start.setDate(start.getDate() - (days - 1));

    const formatDate = (value: Date) => {
      const year = value.getFullYear();
      const month = String(value.getMonth() + 1).padStart(2, '0');
      const day = String(value.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    };

    return {
      start_date: formatDate(start),
      end_date: formatDate(end),
    };
  }, []);

  const waitForTaskCompletion = useCallback(async (taskId: string): Promise<TaskStatusAPI> => {
    const startedAt = Date.now();
    const timeoutMs = 5 * 60 * 1000;

    while (Date.now() - startedAt < timeoutMs) {
      const status = await fetchTaskStatus(taskId);
      if (status.status === 'completed') return status;
      if (status.status === 'failed') {
        throw new Error(status.error || 'GA4 sync failed');
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }

    throw new Error('GA4 sync timed out');
  }, []);

  const loadData = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const [cmsResult, ga4Result] = await Promise.allSettled([
        fetchCMSConnection(controller.signal),
        fetchGA4Connection(controller.signal),
      ]);

      if (controller.signal.aborted) return;

      setCmsConnection(
        cmsResult.status === 'fulfilled' ? cmsResult.value : null,
      );
      setGa4Connection(
        ga4Result.status === 'fulfilled' ? ga4Result.value : null,
      );

      // If GA4 connected but no property selected, auto-fetch properties
      if (
        ga4Result.status === 'fulfilled' &&
        ga4Result.value?.is_active &&
        !ga4Result.value.ga4_property_id
      ) {
        try {
          const propsRes = await fetchGA4Properties(controller.signal);
          if (!controller.signal.aborted) {
            setGa4Properties(propsRes.properties);
          }
        } catch {
          // Non-critical — user can retry
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      const msg = err instanceof ApiError ? err.detail : 'Failed to load integrations';
      setError(msg);
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
    }
  }, []);

  // Initial load + handle OAuth redirect params
  useEffect(() => {
    if (!isInitialized) return;
    loadData();

    // Clean up OAuth redirect params from URL
    const analyticsConnected = searchParams.get('analytics_connected');
    const oauthError = searchParams.get('error');
    if (analyticsConnected || oauthError) {
      // Remove query params without triggering navigation
      const url = new URL(window.location.href);
      url.searchParams.delete('analytics_connected');
      url.searchParams.delete('error');
      // Preserve the tab param
      router.replace(url.pathname + url.search, { scroll: false });
    }

    return () => { abortRef.current?.abort(); };
  }, [isInitialized, loadData, searchParams, router]);

  const refetch = useCallback(() => {
    loadData();
  }, [loadData]);

  // ── CMS mutations ──────────────────────────────────────

  const connectWordPress = useCallback(async (body: CMSConnectRequestAPI) => {
    try {
      const res = await connectCMS(body);
      if (res.connected) {
        refetch();
        return { success: true };
      }
      return { success: false, error: res.error || 'Connection failed' };
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to connect WordPress';
      setError(msg);
      return { success: false, error: msg };
    }
  }, [refetch]);

  const disconnectWordPress = useCallback(async () => {
    try {
      await disconnectCMS();
      setCmsConnection(null);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to disconnect WordPress';
      setError(msg);
      throw err;
    }
  }, []);

  // ── GA4 mutations ──────────────────────────────────────

  const startGA4Connect = useCallback(async () => {
    try {
      const returnUrl = window.location.href;
      const res = await startGA4OAuth(returnUrl);
      // Redirect browser to Google OAuth consent screen
      window.location.href = res.authorization_url;
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to start Google Analytics connection';
      setError(msg);
    }
  }, []);

  const disconnectGA4Connection = useCallback(async (purgeData: boolean) => {
    try {
      await disconnectGA4(purgeData);
      setGa4Connection(null);
      setGa4Properties([]);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to disconnect Google Analytics';
      setError(msg);
      throw err;
    }
  }, []);

  const loadGA4Properties = useCallback(async () => {
    try {
      const res = await fetchGA4Properties();
      setGa4Properties(res.properties);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to load GA4 properties';
      setError(msg);
    }
  }, []);

  const selectProperty = useCallback(async (body: GA4SelectPropertyRequestAPI) => {
    try {
      await selectGA4Property(body);
      const sync = await triggerGA4Sync(buildBackfillRequest(30));
      await waitForTaskCompletion(sync.run_id);
      refetch();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Failed to select property';
      setError(msg);
      throw err;
    }
  }, [buildBackfillRequest, refetch, waitForTaskCompletion]);

  const syncGA4 = useCallback(async (days?: number): Promise<GA4SyncResponseAPI> => {
    try {
      const res = await triggerGA4Sync(
        days ? buildBackfillRequest(days) : undefined,
      );
      await waitForTaskCompletion(res.run_id);
      refetch();
      return res;
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Failed to trigger sync';
      setError(msg);
      throw err;
    }
  }, [buildBackfillRequest, refetch, waitForTaskCompletion]);

  return {
    cmsConnection,
    ga4Connection,
    ga4Properties,
    isLoading,
    error,
    connectWordPress,
    disconnectWordPress,
    startGA4Connect,
    disconnectGA4Connection,
    loadGA4Properties,
    selectProperty,
    syncGA4,
    refetch,
  };
}
