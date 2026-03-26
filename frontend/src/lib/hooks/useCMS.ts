/**
 * CMS integration data-fetching and mutation hooks.
 *
 * Read hooks (SWR-backed):
 *   useCMSConnection()      — connection info
 *   useCMSCategories()      — category list for publish UI (immutable)
 *   useCMSSyncedPosts()     — synced post list
 *   useCMSStaleActions()    — stale content action cards for Home
 *   useCMSPublishHistory()  — publish audit trail
 *
 * Mutation hooks:
 *   useCMSConnect()         — POST /connect
 *   useCMSDisconnect()      — DELETE /connection
 *   useCMSSync()            — POST /sync (returns run_id for SSE)
 *   useCMSPublish()         — POST /publish
 *   useCMSStaleToTriage()   — POST /stale-to-triage
 */

import { useState, useCallback, useRef } from 'react';
import { useSWRConfig } from 'swr';
import { useApiQuery } from './useApiQuery';
import { apiPost, apiDelete, ApiError } from '@/lib/api/client';
import { CMS } from '@/lib/api/endpoints';
import type {
  CMSConnectionInfo,
  CMSConnectPayload,
  CMSConnectResponse,
  CMSCategoryItem,
  CMSSyncedPostSummary,
  StaleContentAction,
  CMSPublishHistoryItem,
  CMSPublishPayload,
  CMSPublishResponse,
  CMSSyncTriggerResponse,
  StaleToTriageResponse,
} from '@/lib/api/types';

// ── Read Hooks ──────────────────────────────────────────────────────────

export function useCMSConnection() {
  return useApiQuery<CMSConnectionInfo | null>(CMS.connection);
}

export function useCMSCategories(enabled: boolean) {
  return useApiQuery<CMSCategoryItem[]>(
    enabled ? CMS.categories : null,
    { immutable: true },
  );
}

export function useCMSSyncedPosts(opts?: {
  staleOnly?: boolean;
  limit?: number;
  offset?: number;
}) {
  const params = new URLSearchParams();
  if (opts?.staleOnly) params.set('stale_only', 'true');
  if (opts?.limit) params.set('limit', String(opts.limit));
  if (opts?.offset) params.set('offset', String(opts.offset));
  const qs = params.toString();
  const path = qs ? `${CMS.syncedPosts}?${qs}` : CMS.syncedPosts;
  return useApiQuery<CMSSyncedPostSummary[]>(path);
}

export function useCMSStaleActions() {
  return useApiQuery<StaleContentAction[]>(CMS.staleActions);
}

export function useCMSPublishHistory(opts?: { limit?: number; offset?: number }) {
  const params = new URLSearchParams();
  if (opts?.limit) params.set('limit', String(opts.limit));
  if (opts?.offset) params.set('offset', String(opts.offset));
  const qs = params.toString();
  const path = qs ? `${CMS.publishHistory}?${qs}` : CMS.publishHistory;
  return useApiQuery<CMSPublishHistoryItem[]>(path);
}

// ── Helpers ─────────────────────────────────────────────────────────────

/** Invalidate all SWR keys starting with `prefix` (handles parameterized variants). */
function mutatePrefix(mutate: ReturnType<typeof useSWRConfig>['mutate'], prefix: string) {
  mutate(
    (key: string) => typeof key === 'string' && key.startsWith(prefix),
    undefined,
    { revalidate: true },
  );
}

// ── Mutation Hooks ──────────────────────────────────────────────────────
// All mutation hooks use `inFlightRef` (synchronous ref) as the primary
// concurrency guard instead of `useState` to avoid stale-closure races.

export function useCMSConnect() {
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);
  const inFlightRef = useRef(false);
  const { mutate } = useSWRConfig();

  const connect = useCallback(async (
    data: CMSConnectPayload,
  ): Promise<CMSConnectResponse | null> => {
    if (inFlightRef.current) return null;
    inFlightRef.current = true;
    const id = ++reqIdRef.current;
    setIsConnecting(true);
    setError(null);
    try {
      const result = await apiPost<CMSConnectResponse>(CMS.connect, data);
      mutate(CMS.connection);
      return result;
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
      return null;
    } finally {
      if (id === reqIdRef.current) setIsConnecting(false);
      inFlightRef.current = false;
    }
  }, [mutate]);

  return { connect, isConnecting, error };
}

export function useCMSDisconnect() {
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);
  const inFlightRef = useRef(false);
  const { mutate } = useSWRConfig();

  const disconnect = useCallback(async (): Promise<boolean> => {
    if (inFlightRef.current) return false;
    inFlightRef.current = true;
    const id = ++reqIdRef.current;
    setIsDisconnecting(true);
    setError(null);
    try {
      await apiDelete(CMS.connection);
      mutate(CMS.connection);
      mutatePrefix(mutate, CMS.syncedPosts);
      mutatePrefix(mutate, CMS.staleActions);
      mutate(CMS.categories);
      return true;
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
      return false;
    } finally {
      if (id === reqIdRef.current) setIsDisconnecting(false);
      inFlightRef.current = false;
    }
  }, [mutate]);

  return { disconnect, isDisconnecting, error };
}

export function useCMSSync() {
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncRunId, setSyncRunId] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);
  const inFlightRef = useRef(false);

  const triggerSync = useCallback(async (): Promise<string | null> => {
    if (inFlightRef.current) return null;
    inFlightRef.current = true;
    const id = ++reqIdRef.current;
    setIsSyncing(true);
    setError(null);
    try {
      const result = await apiPost<CMSSyncTriggerResponse>(CMS.sync);
      if (id === reqIdRef.current) {
        setSyncRunId(result.run_id);
      }
      return result.run_id;
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
      return null;
    } finally {
      if (id === reqIdRef.current) setIsSyncing(false);
      inFlightRef.current = false;
    }
  }, []);

  /** Call when SSE stream completes to invalidate caches. */
  const onSyncComplete = useCallback(() => {
    setSyncRunId(null);
  }, []);

  return { triggerSync, isSyncing, syncRunId, onSyncComplete, error };
}

export function useCMSPublish() {
  const [isPublishing, setIsPublishing] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);
  const inFlightRef = useRef(false);
  const { mutate } = useSWRConfig();

  const publish = useCallback(async (
    data: CMSPublishPayload,
  ): Promise<CMSPublishResponse | null> => {
    if (inFlightRef.current) return null;
    inFlightRef.current = true;
    const id = ++reqIdRef.current;
    setIsPublishing(true);
    setError(null);
    try {
      const result = await apiPost<CMSPublishResponse>(CMS.publish, data);
      mutatePrefix(mutate, CMS.publishHistory);
      return result;
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
      return null;
    } finally {
      if (id === reqIdRef.current) setIsPublishing(false);
      inFlightRef.current = false;
    }
  }, [mutate]);

  return { publish, isPublishing, error };
}

export function useCMSStaleToTriage() {
  const [isQueuing, setIsQueuing] = useState(false);
  const [queuingId, setQueuingId] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const reqIdRef = useRef(0);
  const inFlightRef = useRef(false);
  const { mutate } = useSWRConfig();

  const queueForRefresh = useCallback(async (
    cmsSyncedPostId: string,
  ): Promise<StaleToTriageResponse | null> => {
    if (inFlightRef.current) return null;
    inFlightRef.current = true;
    const id = ++reqIdRef.current;
    setIsQueuing(true);
    setQueuingId(cmsSyncedPostId);
    setError(null);
    try {
      const result = await apiPost<StaleToTriageResponse>(
        CMS.staleToTriage,
        { cms_synced_post_id: cmsSyncedPostId },
      );
      mutatePrefix(mutate, CMS.staleActions);
      return result;
    } catch (err) {
      if (id === reqIdRef.current) {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
      }
      return null;
    } finally {
      if (id === reqIdRef.current) {
        setIsQueuing(false);
        setQueuingId(null);
      }
      inFlightRef.current = false;
    }
  }, [mutate]);

  return { queueForRefresh, isQueuing, queuingId, error };
}
