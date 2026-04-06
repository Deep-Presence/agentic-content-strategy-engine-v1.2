/**
 * API service layer for Content Performance.
 * All calls go through BFF proxy via same-origin fetch.
 */

import { api } from '@/lib/api-client';
import type {
  ContentDetailAPI,
  ContentPerformanceTableResponseAPI,
  SignalAveragesAPI,
  VelocityInsightsResponseAPI,
} from './types';

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

// ── Content Performance Table ─────────────────────────

export function fetchContentTable(
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<ContentPerformanceTableResponseAPI> {
  return api.get<ContentPerformanceTableResponseAPI>(
    '/api/v1/content-performance',
    params,
    signal,
  );
}

// ── Velocity Insights ─────────────────────────────────

export function fetchVelocityInsights(
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<VelocityInsightsResponseAPI> {
  return api.get<VelocityInsightsResponseAPI>(
    '/api/v1/content-performance/insights/velocity',
    params,
    signal,
  );
}

// ── Similar Content (Cannibalization) ────────────────

export interface SimilarContentItemAPI {
  inventory_id: string;
  url: string;
  title: string;
  similarity: number;
  word_count: number;
  content_type: string;
  content_preview: string;
}

export interface SimilarContentResponseAPI {
  page_id: string;
  similar_pages: SimilarContentItemAPI[];
  threshold: number;
  embeddings_ready: boolean;
}

export function fetchSimilarContent(
  inventoryId: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<SimilarContentResponseAPI> {
  return api.get<SimilarContentResponseAPI>(
    `/api/v1/content-performance/${inventoryId}/similar`,
    params,
    signal,
  );
}

// ── Generate Embeddings ──────────────────────────────

export interface GenerateEmbeddingsResponseAPI {
  generated: number;
  message: string;
}

export function generateEmbeddings(
  signal?: AbortSignal,
): Promise<GenerateEmbeddingsResponseAPI> {
  return api.post<GenerateEmbeddingsResponseAPI>(
    '/api/v1/content-inventory/generate-embeddings',
    undefined,
    signal ? { signal } : undefined,
  );
}

// ── CMS Connection Status ────────────────────────────

export interface CMSConnectionInfo {
  provider: string;
  site_url: string;
  site_name: string;
  is_active: boolean;
  last_sync_at: string | null;
  sync_post_count: number;
}

export function fetchCMSConnection(
  signal?: AbortSignal,
): Promise<CMSConnectionInfo | null> {
  return api.get<CMSConnectionInfo | null>(
    '/api/v1/cms/connection',
    undefined,
    signal,
  );
}

// ── CMS Sync Trigger ─────────────────────────────────

export interface SyncResponse {
  run_id: string;
  pipeline: string;
  status: string;
  company_slug: string;
}

export function triggerCMSSync(
  signal?: AbortSignal,
): Promise<SyncResponse> {
  return api.post<SyncResponse>('/api/v1/cms/sync', {}, signal ? { signal } : undefined);
}

// ── Content-to-Prompt Generate New Pages ──────────────

export interface GenerateNewResponse {
  generation_run_id: string;
  pages_processed: number;
  pages_succeeded: number;
  pages_failed: number;
  prompts_created: number;
  prompts_deduplicated: number;
}

export function generatePromptsForNewPages(
  signal?: AbortSignal,
): Promise<GenerateNewResponse> {
  return api.post<GenerateNewResponse>(
    '/api/v1/content-to-prompt/generate-new',
    undefined,
    signal ? { signal } : undefined,
  );
}

// ── Task Status Polling ──────────────────────────────

export interface TaskStatus {
  task_id: string;
  pipeline: string;
  status: string;
  error?: string;
}

export function fetchTaskStatus(
  taskId: string,
  signal?: AbortSignal,
): Promise<TaskStatus> {
  return api.get<TaskStatus>(`/api/v1/tasks/${taskId}`, undefined, signal);
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
