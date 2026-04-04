/**
 * Types for the Prompt Tracking page.
 *
 * API types (snake_case) mirror backend Pydantic schemas exactly.
 * Frontend display types (camelCase) are consumed by components.
 */

import type { Platform } from '@/types';

// ── API Response Types (mirror backend) ─────────────────────────

export interface EnrichedPromptAPI {
  id: string;
  text: string;
  category: string | null;
  tags: string[];
  source: string;
  active: boolean;
  created_at: string | null;
  mention_rate: number;
  mention_delta: number;
  citation_rate: number;
  citation_delta: number;
  daily_volume: number[];
  fanout_count: number;
  total_responses: number;
}

export interface EnrichedPromptListResponseAPI {
  prompts: EnrichedPromptAPI[];
  total: number;
  period_days: number;
  period_start: string;
  period_end: string;
}

export interface CompetitorMetricsAPI {
  name: string;
  mention_rate: number;
  mention_count: number;
  share_of_voice: number;
  rank: number;
  mention_delta: number;
}

export interface PerPromptPlatformMetricsAPI {
  engine: string;
  response_count: number;
  mention_count: number;
  mention_rate: number;
}

export interface PromptAnalyticsResponseAPI {
  prompt_id: string;
  period_days: number;
  mention_rate: number;
  citation_rate: number;
  competitors: CompetitorMetricsAPI[];
  platforms: PerPromptPlatformMetricsAPI[];
}

export interface FanoutQueryResponseAPI {
  id: string;
  parent_prompt_id: string;
  axis: string;
  query_text: string;
  reasoning: string;
  pinned: boolean;
  active: boolean;
  observation_count: number;
  created_at: string | null;
}

export interface FanoutListResponseAPI {
  parent_prompt_id: string;
  parent_text: string;
  fanouts: FanoutQueryResponseAPI[];
  total: number;
}

export interface AnswerRecordAPI {
  id: string;
  run_id: string;
  engine: string;
  response_text: string;
  brand_mentioned: boolean;
  brand_mention_count: number;
  competitor_mentions: Record<string, number>;
  citations: string[];
  citation_rank: number | null;
  persona: string;
  created_at: string | null;
}

export interface AnswerHistoryResponseAPI {
  prompt_id: string;
  responses: AnswerRecordAPI[];
  total: number;
}

// ── Frontend Display Types (consumed by components) ─────────────

export interface PromptRow {
  id: string;
  text: string;
  topic: string;
  topicColor: string;
  tags: string[];
  queryFanouts: number;
  mentionRate: number;
  mentionDelta: number;
  citationRate: number;
  citationDelta: number;
  volume: number[];
}

export interface CompetitorMention {
  rank: number;
  brand: string;
  domain: string;
  mentions: number;
  mentionRate: number;
  mentionDelta: number;
  isYou: boolean;
}

export interface PlatformMentionRate {
  platform: Platform;
  label: string;
  domain: string;
  mentionRate: number;
}

export interface QueryFanout {
  query: string;
  observations: number;
}

export interface AnswerHistoryRow {
  id: string;
  date: string;
  persona: string;
  platform: Platform;
  platformLabel: string;
  platformDomain: string;
  answerPreview: string;
  cited: boolean;
  mentioned: boolean;
  competitorDomains: string[];
  fullAnswer: string | null;
  citations: string[];
  mentionedBrands: { domain: string; name: string; checked: boolean }[];
}

export interface Topic {
  name: string;
  color: string;
  count: number;
  avgMentionRate: number;
  avgCitationRate: number;
}
