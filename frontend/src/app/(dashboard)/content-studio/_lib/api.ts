/**
 * API fetch functions for Content Studio.
 *
 * All calls go through the BFF proxy (same-origin /api/v1/...).
 * Auth is handled via httpOnly cookie — no token injection needed.
 */

import { api } from '@/lib/api-client';
import type {
  ContentBriefListResponseAPI,
  ContentBriefDetailResponseAPI,
  ContentBriefListItemAPI,
  StageContentResponseAPI,
  PipelineRunResponseAPI,
  ApprovalResponseAPI,
  GapSummaryResponseAPI,
} from './types';

// ---------------------------------------------------------------------------
// Brief list
// ---------------------------------------------------------------------------

export function fetchBriefs(
  slug: string,
  productSlug?: string,
  signal?: AbortSignal,
): Promise<ContentBriefListResponseAPI> {
  return api.get<ContentBriefListResponseAPI>(
    `/api/v1/companies/${encodeURIComponent(slug)}/content/briefs`,
    productSlug ? { product_slug: productSlug } : undefined,
    signal,
  );
}

// ---------------------------------------------------------------------------
// Brief detail
// ---------------------------------------------------------------------------

export function fetchBriefDetail(
  slug: string,
  briefId: string,
  productSlug?: string,
  signal?: AbortSignal,
): Promise<ContentBriefDetailResponseAPI> {
  return api.get<ContentBriefDetailResponseAPI>(
    `/api/v1/companies/${encodeURIComponent(slug)}/content/briefs/${encodeURIComponent(briefId)}`,
    productSlug ? { product_slug: productSlug } : undefined,
    signal,
  );
}

// ---------------------------------------------------------------------------
// Stage content (outline, draft, enriched, formatted, eval_history, final)
// ---------------------------------------------------------------------------

export function fetchStageContent(
  slug: string,
  briefId: string,
  stage: string,
  productSlug?: string,
  signal?: AbortSignal,
): Promise<StageContentResponseAPI> {
  return api.get<StageContentResponseAPI>(
    `/api/v1/companies/${encodeURIComponent(slug)}/content/briefs/${encodeURIComponent(briefId)}/${encodeURIComponent(stage)}`,
    productSlug ? { product_slug: productSlug } : undefined,
    signal,
  );
}

// ---------------------------------------------------------------------------
// Pipeline start (autonomous or manual)
// ---------------------------------------------------------------------------

export interface StartPipelineOptions {
  entry_mode?: 'autonomous' | 'manual';
  auto_approve?: boolean;
  max_topics?: number;
  manual_prompt?: string;
  manual_description?: string;
  manual_cluster?: string;
  gap_slug?: string;
  gap_query_id?: string;
  brief_id_hint?: string;
  product_slug?: string;
  product_name?: string;
  product_description?: string;
}

export function startPipeline(
  companyName: string,
  domain: string,
  options?: StartPipelineOptions,
): Promise<PipelineRunResponseAPI> {
  return api.post<PipelineRunResponseAPI>('/api/v1/content/v13/start', {
    company_name: companyName,
    domain,
    ...options,
  });
}

// ---------------------------------------------------------------------------
// HITL-2: Brief approval
// ---------------------------------------------------------------------------

export function approveBrief(
  runId: string,
  briefId: string,
  decision: 'approve' | 'feedback' | 'reject',
  feedback?: string,
): Promise<ApprovalResponseAPI> {
  return api.post<ApprovalResponseAPI>(
    `/api/v1/content/v13/${encodeURIComponent(runId)}/approve/briefs`,
    { brief_id: briefId, decision, feedback },
  );
}

// ---------------------------------------------------------------------------
// HITL-3: Content approval
// ---------------------------------------------------------------------------

export function approveContent(
  runId: string,
  briefId: string,
  decision: 'approve' | 'edit' | 'reject',
  editorNotes?: string,
  rethink?: boolean,
): Promise<ApprovalResponseAPI> {
  return api.post<ApprovalResponseAPI>(
    `/api/v1/content/v13/${encodeURIComponent(runId)}/approve/content`,
    { brief_id: briefId, decision, editor_notes: editorNotes, rethink },
  );
}

// ---------------------------------------------------------------------------
// Launch GA-only pipeline for approved topic assignments
// ---------------------------------------------------------------------------

export function startFromTopics(
  companyName: string,
  domain: string,
  effectiveSlug: string,
  topicAssignmentIds: string[],
  options?: {
    productSlug?: string;
    productName?: string;
    productDescription?: string;
    platforms?: string[];
  },
): Promise<PipelineRunResponseAPI> {
  return api.post<PipelineRunResponseAPI>('/api/v1/content/v13/from-topics/gap-analysis', {
    company_name: companyName,
    domain,
    effective_slug: effectiveSlug,
    topic_assignment_ids: topicAssignmentIds,
    product_slug: options?.productSlug,
    product_name: options?.productName,
    product_description: options?.productDescription,
    platforms: options?.platforms,
  });
}

// ---------------------------------------------------------------------------
// Start content production from pre-computed GA results
// ---------------------------------------------------------------------------

export function startProduction(
  companyName: string,
  domain: string,
  effectiveSlug: string,
  topicAssignmentIds: string[],
  gaRunId: string,
  options?: {
    productSlug?: string;
    productName?: string;
    productDescription?: string;
    autoApprove?: boolean;
  },
): Promise<PipelineRunResponseAPI> {
  return api.post<PipelineRunResponseAPI>('/api/v1/content/v13/from-topics/start-production', {
    company_name: companyName,
    domain,
    effective_slug: effectiveSlug,
    topic_assignment_ids: topicAssignmentIds,
    ga_run_id: gaRunId,
    product_slug: options?.productSlug,
    product_name: options?.productName,
    product_description: options?.productDescription,
    auto_approve: options?.autoApprove ?? false,
  });
}

// ---------------------------------------------------------------------------
// Cancel task (generic — works for any pipeline)
// ---------------------------------------------------------------------------

export function cancelTask(
  taskId: string,
): Promise<{ run_id: string; status: string }> {
  return api.post<{ run_id: string; status: string }>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/cancel`,
  );
}

// ---------------------------------------------------------------------------
// Add brief manually
// ---------------------------------------------------------------------------

export function addBrief(
  slug: string,
  title: string,
  cluster?: string,
  description?: string,
  source?: string,
  gapQueryId?: string,
): Promise<ContentBriefListItemAPI> {
  return api.post<ContentBriefListItemAPI>(
    `/api/v1/companies/${encodeURIComponent(slug)}/content/briefs`,
    {
      title,
      cluster: cluster ?? '',
      description: description ?? '',
      source: source ?? 'manual',
      gap_query_id: gapQueryId ?? '',
    },
  );
}

// ---------------------------------------------------------------------------
// Gap analysis summary (for gap metrics display in detail view)
// ---------------------------------------------------------------------------

export function fetchGapSummary(
  slug: string,
  productSlug?: string,
  signal?: AbortSignal,
  gaRunId?: string,
): Promise<GapSummaryResponseAPI> {
  const params: Record<string, string> = {};
  if (productSlug) params.product_slug = productSlug;
  if (gaRunId) params.ga_run_id = gaRunId;
  return api.get<GapSummaryResponseAPI>(
    `/api/v1/companies/${encodeURIComponent(slug)}/gap-analysis/summary`,
    Object.keys(params).length > 0 ? params : undefined,
    signal,
  );
}
