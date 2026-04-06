/**
 * Backend API response types for Content Studio.
 *
 * These mirror the Pydantic schemas in api/schemas/content_data.py and
 * api/schemas/content_v13.py. All fields use snake_case to match the
 * JSON wire format. Frontend display types live in _components/types.ts.
 */

// ---------------------------------------------------------------------------
// Gap context (nested in brief list item)
// ---------------------------------------------------------------------------

export interface GapContextSummaryAPI {
  gap_score: number;
  classification: string;
  company_similarity: number;
  citation_similarity: number;
  company_cited: boolean;
  company_best_url: string;
  why_picked: string[];
  success_indicators: Array<{ label: string; value: string; sub?: string }>;
  exemplars: Array<{
    url: string;
    domain: string;
    similarity?: number;
    word_count: number;
    authority_type: string;
    content_type?: string;
  }>;
}

// ---------------------------------------------------------------------------
// Gap analysis summary (GET /companies/{slug}/gap-analysis/summary)
// ---------------------------------------------------------------------------

export interface GapClassificationCountsAPI {
  significant_gap: number;
  gap_to_close: number;
  roughly_equal: number;
  company_wins: number;
}

export interface ClusterPerformanceRowAPI {
  cluster_id?: string;
  cluster_name: string;
  query_count: number;
  citation_count: number;
  avg_gap: number;
  avg_citation_sim: number;
  avg_company_sim: number;
}

export interface GapSummaryResponseAPI {
  classification_counts: GapClassificationCountsAPI;
  cluster_performance: ClusterPerformanceRowAPI[];
  total_queries: number;
  total_citations: number;
  company_cited_count: number;
  average_gap: number;
  executive_summary: string;
}

// ---------------------------------------------------------------------------
// Brief list (GET /companies/{slug}/content/briefs)
// ---------------------------------------------------------------------------

export interface ContentBriefListItemAPI {
  id: string;
  title: string;
  status: string;
  content_type: string;
  content_format: string;
  cluster: string;
  target_word_count: number;
  citability_score: number | null;
  priority_score: number;
  cycle_id: string | null;
  task_id: string | null;
  created_at: string;
  updated_at: string;
  gap_context: GapContextSummaryAPI | null;
  published_url: string;
  published_at: string | null;
  topic_assignment_id?: string;
  buyer_stage?: string;
  source?: string;
  ga_run_id?: string;
  effective_slug?: string;
  // Enriched topic assignment metadata (GA-phase cards)
  intent_type?: string;
  persona_name?: string;
  persona_id?: string;
  persona_affinity?: Record<string, number>;
  priority_factors?: Record<string, number>;
  estimated_word_count?: number;
  citation_opportunity?: number;
  description?: string;
  target_keywords?: { primary?: string; secondary?: string[] };
  content_angle?: string;
}

export interface ContentBriefListResponseAPI {
  briefs: ContentBriefListItemAPI[];
  total: number;
}

// ---------------------------------------------------------------------------
// Eval history (nested in brief detail)
// ---------------------------------------------------------------------------

export interface EvalDimensionAPI {
  dimension: string;
  passed: boolean;
  score: number;
  feedback: string;
  details: Record<string, unknown>;
}

export interface EvalCycleAPI {
  cycle: number;
  dimensions: EvalDimensionAPI[];
  overall_passed: boolean;
  overall_score: number;
}

// ---------------------------------------------------------------------------
// CPS (nested in brief detail)
// ---------------------------------------------------------------------------

export interface CPSDetailAPI {
  cps_score: number;
  per_engine: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Brief detail (GET /companies/{slug}/content/briefs/{briefId})
// ---------------------------------------------------------------------------

export interface BriefExemplarAPI {
  url: string;
  word_count: number;
  authority_type: string;
  content_type: string;
  snippet: string;
}

export interface ContentBriefDetailResponseAPI {
  id: string;
  title: string;
  status: string;
  content_type: string;
  cluster: string;
  target_word_count: { min: number; max: number };
  structural_targets: Record<string, unknown>;
  key_topics: string[];
  key_angles: string[];
  priority_score: number;
  citability_score: number | null;
  eval_history: EvalCycleAPI[];
  final_passed: boolean;
  exemplars: BriefExemplarAPI[];
  available_stages: string[];
  cps: CPSDetailAPI | null;
}

// ---------------------------------------------------------------------------
// Stage content (GET /companies/{slug}/content/briefs/{briefId}/{stage})
// ---------------------------------------------------------------------------

export interface StageContentResponseAPI {
  brief_id: string;
  stage: string;
  content_type: string;
  content: string | Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Pipeline start (POST /content/v13/start)
// ---------------------------------------------------------------------------

export interface PipelineRunResponseAPI {
  run_id: string;
  status: string;
  entry_mode: string;
  message?: string;
}

// ---------------------------------------------------------------------------
// HITL approval (POST /content/v13/{runId}/approve/*)
// ---------------------------------------------------------------------------

export interface ApprovalResponseAPI {
  status: string;
  stage: string;
  brief_id?: string;
  message?: string;
}

// ---------------------------------------------------------------------------
// Add brief (POST /companies/{slug}/content/briefs)
// ---------------------------------------------------------------------------

export interface AddBriefRequestAPI {
  title: string;
  cluster?: string;
  description?: string;
  source?: string;
  gap_query_id?: string;
}

// ---------------------------------------------------------------------------
// SSE event data shapes
// ---------------------------------------------------------------------------

export interface SSEStageStartedData {
  stage: number;
  name: string;
}

export interface SSEWorkerProgressData {
  brief_id: string;
  step: string;
  worker_num?: number;
  progress?: number;
}

export interface SSEPendingApprovalData {
  stage: string;
  checkpoint_nonce?: string;
  brief_id?: string;
  [key: string]: unknown;
}

export interface SSEApprovalReceivedData {
  stage: string;
  decision: string;
}

export interface SSEBriefCompletedData {
  brief_id: string;
  status?: string;
  decision?: string;
}

export interface SSECPSScoringData {
  scored: number;
  scores: Record<string, number>;
}

export interface SSEPipelineCompleteData {
  total_briefs: number;
  total_approved: number;
  total_rejected: number;
  duration?: number;
}

export interface SSEPipelineErrorData {
  error: string;
}

export interface SSECancelledData {
  reason: string;
}

// ---------------------------------------------------------------------------
// Gap Analysis SSE events (ga_step_start, ga_step_complete)
// ---------------------------------------------------------------------------

export interface SSEGAStepData {
  step: string;
  name: string;
  step_num: number;
  total_steps: number;
  elapsed_s?: number;
}
