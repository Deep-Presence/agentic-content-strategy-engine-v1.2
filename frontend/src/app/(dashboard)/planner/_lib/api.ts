/**
 * API service layer for Content Planner / Topic Discovery.
 * All calls go through BFF proxy via same-origin fetch.
 */

import { api } from '@/lib/api-client';
import type {
  AssignmentListResponseAPI,
  AssignmentStatusUpdateResponseAPI,
  DiscoverySummaryResponseAPI,
  PersonaAffinityResponseAPI,
  PipelineRunResponseAPI,
  TaxonomyReadResponseAPI,
  TopicAssignmentAPI,
} from './types';

// ── Discovery Summary ───────────────────────────────────

export function fetchDiscoverySummary(
  slug: string,
  signal?: AbortSignal,
): Promise<DiscoverySummaryResponseAPI> {
  return api.get<DiscoverySummaryResponseAPI>(
    `/api/v1/topic-discovery/${slug}/summary`,
    undefined,
    signal,
  );
}

// ── Assignments ─────────────────────────────────────────

export function fetchAssignments(
  slug: string,
  params?: {
    buyer_stage?: string;
    intent_type?: string;
    persona_id?: string;
    status?: string;
    page?: number;
    page_size?: number;
  },
  signal?: AbortSignal,
): Promise<AssignmentListResponseAPI> {
  return api.get<AssignmentListResponseAPI>(
    `/api/v1/topic-discovery/${slug}/assignments`,
    params as Record<string, string>,
    signal,
  );
}

// ── Taxonomy ────────────────────────────────────────────

export function fetchTaxonomy(
  slug: string,
  signal?: AbortSignal,
): Promise<TaxonomyReadResponseAPI> {
  return api.get<TaxonomyReadResponseAPI>(
    `/api/v1/topic-discovery/${slug}/taxonomy`,
    undefined,
    signal,
  );
}

// ── Persona Affinity ────────────────────────────────────

export function fetchPersonaAffinity(
  slug: string,
  signal?: AbortSignal,
): Promise<PersonaAffinityResponseAPI> {
  return api.get<PersonaAffinityResponseAPI>(
    `/api/v1/topic-discovery/${slug}/personas`,
    undefined,
    signal,
  );
}

// ── Mutations ───────────────────────────────────────────

export function updateAssignmentStatus(
  slug: string,
  assignmentId: string,
  status: 'approved' | 'rejected' | 'not_started',
): Promise<AssignmentStatusUpdateResponseAPI> {
  return api.patch<AssignmentStatusUpdateResponseAPI>(
    `/api/v1/topic-discovery/${slug}/assignments/${assignmentId}`,
    { status },
  );
}

export function createCustomAssignment(
  slug: string,
  data: {
    topic_text: string;
    subdomain_name?: string;
    buyer_stage?: string;
    intent_type?: string;
    persona_id?: string;
    persona_name?: string;
    priority_score?: number;
  },
): Promise<TopicAssignmentAPI> {
  return api.post<TopicAssignmentAPI>(
    `/api/v1/topic-discovery/${slug}/assignments`,
    data,
  );
}

// ── Topic Expansion (Pipeline B) ───────────────────────

export function expandSubdomain(
  companyName: string,
  domain: string,
  subdomainIds: string[],
  options?: {
    auto_approve_checkpoints?: number[];
    taxonomy_version?: number;
  },
): Promise<PipelineRunResponseAPI> {
  return api.post<PipelineRunResponseAPI>(
    '/api/v1/topic-discovery/expand',
    {
      company_name: companyName,
      domain,
      subdomain_ids: subdomainIds,
      auto_approve_checkpoints: options?.auto_approve_checkpoints ?? [2],
      taxonomy_version: options?.taxonomy_version,
    },
  );
}

// ── GA-Only Pipeline (from Planner → Content Studio) ──

/** Launch GA-only pipeline for approved topic assignments */
export function startFromTopicsPipeline(
  companyName: string,
  domain: string,
  effectiveSlug: string,
  topicAssignmentIds: string[],
): Promise<PipelineRunResponseAPI> {
  return api.post<PipelineRunResponseAPI>('/api/v1/content/v13/from-topics/gap-analysis', {
    company_name: companyName,
    domain,
    effective_slug: effectiveSlug,
    topic_assignment_ids: topicAssignmentIds,
  });
}

// ── Task Status Polling ────────────────────────────────

export interface TaskStatusAPI {
  task_id: string;
  pipeline: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  current_step?: string;
  error?: string;
  created_at: string;
}

export function fetchTaskStatus(
  taskId: string,
  signal?: AbortSignal,
): Promise<TaskStatusAPI> {
  return api.get<TaskStatusAPI>(
    `/api/v1/tasks/${taskId}`,
    undefined,
    signal,
  );
}
