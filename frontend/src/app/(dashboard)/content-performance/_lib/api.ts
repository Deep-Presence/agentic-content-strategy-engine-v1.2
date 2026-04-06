/**
 * API service layer for Content Performance.
 * All calls go through BFF proxy via same-origin fetch.
 */

import { api } from '@/lib/api-client';
import type { ContentDetailAPI, SignalAveragesAPI } from './types';

// ── Content Performance Detail ─────────────────────────

export function fetchContentDetail(
  inventoryId: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<ContentDetailAPI> {
  return api.get<ContentDetailAPI>(
    `/api/v1/content-performance/${inventoryId}`,
    params,
    signal,
  );
}

// ── Gap Analysis Signal Averages ───────────────────────

export function fetchSignalAverages(
  slug: string,
  signal?: AbortSignal,
): Promise<SignalAveragesAPI> {
  return api.get<SignalAveragesAPI>(
    `/api/v1/companies/${slug}/gap-analysis/signals`,
    undefined,
    signal,
  );
}
