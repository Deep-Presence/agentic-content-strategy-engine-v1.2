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
