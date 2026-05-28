/**
 * API service layer for Prompt Tracking.
 * All calls go through BFF proxy via same-origin fetch.
 */

import { api } from '@/lib/api-client';
import type {
  EnrichedPromptListResponseAPI,
  PromptAnalyticsResponseAPI,
  FanoutListResponseAPI,
  AnswerHistoryResponseAPI,
} from './types';

// ── Enriched Prompt List (main table) ───────────────────────────

export interface EnrichedPromptParams {
  days?: number;
  start_date?: string;
  end_date?: string;
  category?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export function fetchEnrichedPrompts(
  params: EnrichedPromptParams = {},
  signal?: AbortSignal,
): Promise<EnrichedPromptListResponseAPI> {
  return api.get<EnrichedPromptListResponseAPI>(
    '/api/v1/daily-tracker/prompts/enriched',
    params as Record<string, string | number | boolean | undefined>,
    signal,
  );
}

// ── Per-Prompt Analytics (drawer) ───────────────────────────────

export interface PromptAnalyticsParams {
  days?: number;
  start_date?: string;
  end_date?: string;
}

export function fetchPromptAnalytics(
  promptId: string,
  params: PromptAnalyticsParams = {},
  signal?: AbortSignal,
): Promise<PromptAnalyticsResponseAPI> {
  return api.get<PromptAnalyticsResponseAPI>(
    `/api/v1/daily-tracker/prompts/${promptId}/analytics`,
    params as Record<string, string | number | boolean | undefined>,
    signal,
  );
}

// ── Fanout Queries (drawer) ─────────────────────────────────────

export function fetchPromptFanouts(
  promptId: string,
  signal?: AbortSignal,
): Promise<FanoutListResponseAPI> {
  return api.get<FanoutListResponseAPI>(
    `/api/v1/daily-tracker/prompts/${promptId}/fanouts`,
    undefined,
    signal,
  );
}

// ── Answer History (drawer) ─────────────────────────────────────

export interface AnswerHistoryParams {
  engine?: string;
  days?: number;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export function fetchPromptAnswers(
  promptId: string,
  params: AnswerHistoryParams = {},
  signal?: AbortSignal,
): Promise<AnswerHistoryResponseAPI> {
  return api.get<AnswerHistoryResponseAPI>(
    `/api/v1/daily-tracker/prompts/${promptId}/answers`,
    params as Record<string, string | number | boolean | undefined>,
    signal,
  );
}

// ── Create Prompt ───────────────────────────────────────────────

export interface CreatePromptPayload {
  text: string;
  category?: string;
  tags?: string[];
  generate_fanout?: boolean;
  brand_name?: string;
  brand_category?: string;
  competitors?: string[];
}

export interface CreatePromptResponseAPI {
  prompt: {
    id: string;
    text: string;
    category: string | null;
    tags: string[];
    active: boolean;
    created_at: string;
  };
  fanout_task_id: string | null;
}

export function createPrompt(
  payload: CreatePromptPayload,
): Promise<CreatePromptResponseAPI> {
  return api.post<CreatePromptResponseAPI>(
    '/api/v1/daily-tracker/prompts',
    payload,
  );
}

// ── Trigger Daily Run ───────────────────────────────────────────

export interface TriggerRunPayload {
  engines?: string[];
  prompt_ids?: string[];
  brand?: string;
  competitors?: string[];
  concurrency?: number;
}

export interface TriggerRunResponseAPI {
  run_id: string;
  pipeline: string;
  company_slug: string;
  status: string;
  created_at: string;
}

export function triggerDailyRun(
  payload: TriggerRunPayload = {},
): Promise<TriggerRunResponseAPI> {
  return api.post<TriggerRunResponseAPI>(
    '/api/v1/daily-tracker/runs',
    payload,
  );
}

// ── Run Status ──────────────────────────────────────────────────

export interface RunStatusResponseAPI {
  run_id: string;
  company_id: string;
  status: string;
  prompt_count: number;
  engine_count: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export function fetchRunStatus(
  runId: string,
  signal?: AbortSignal,
): Promise<RunStatusResponseAPI> {
  return api.get<RunStatusResponseAPI>(
    `/api/v1/daily-tracker/runs/${runId}`,
    undefined,
    signal,
  );
}
