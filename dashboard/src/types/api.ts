/* TypeScript interfaces mirroring backend Pydantic models (api/schemas/common.py) */

export type PipelineType = "research" | "gap_analysis" | "content";

export type TaskStatus =
  | "running"
  | "pending_approval"
  | "completed"
  | "failed"
  | "cancelled"
  | "failed_restart";

export type ResearchStage = "company" | "persona" | "style_guide";

export type ApprovalDecision = "approve" | "revise" | "reject";
export type ContentApprovalDecision = "approve" | "edit" | "reject";

/* ── Response types ────────────────────────────────────────────── */

export interface PipelineRunResponse {
  run_id: string;
  pipeline: PipelineType;
  company_slug: string;
  status: string;
  created_at: string;
}

export interface TaskResponse {
  run_id: string;
  pipeline: PipelineType;
  company_slug: string;
  status: TaskStatus;
  current_step: string | null;
  progress_pct: number | null;
  created_at: string;
  updated_at: string;
  result: Record<string, any> | null;
  error: string | null;
  approval_payload: Record<string, any> | null;
}

export interface TaskSummary {
  run_id: string;
  pipeline: PipelineType;
  status: TaskStatus;
  company_slug: string;
  current_step: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  tasks: TaskSummary[];
}

export interface ApprovalResponse {
  run_id: string;
  decision: string;
  revision_note: string | null;
}

export interface ContentApprovalResponse {
  run_id: string;
  brief_id: string;
  decision: string;
  editor_notes: string | null;
}

export interface CancelResponse {
  run_id: string;
  status: string;
}

export interface ErrorResponse {
  detail: string;
  error_code?: string;
}

/* ── Request types ─────────────────────────────────────────────── */

export interface ResearchStartRequest {
  company_name: string;
  domain: string;
  seed_urls?: string[];
  stages?: ResearchStage[];
  auto_approve?: boolean;
  language?: string;
  region?: string;
  max_personas?: number;
  internal_sources?: string[];
  additional_constraints?: string;
}

export interface GapAnalysisStartRequest {
  company_name: string;
  domain: string;
  seed_urls?: string[];
  skip_steps?: number[];
  max_queries?: number;
  platforms?: string[];
  language?: string;
  region?: string;
  additional_constraints?: string;
  max_crawl_pages?: number;
  max_crawl_depth?: number;
}

export interface ContentStartRequest {
  company_name: string;
  domain: string;
  max_briefs?: number;
  auto_approve?: boolean;
}

export interface ApprovalRequest {
  decision: ApprovalDecision;
  revision_note?: string | null;
}

export interface ContentApprovalRequest {
  brief_id: string;
  decision: ContentApprovalDecision;
  editor_notes?: string | null;
}

/* ── Artifact types ────────────────────────────────────────────── */

export interface ArtifactFile {
  name: string;
  size: number;
}

export interface ArtifactListResponse {
  artifact_type: string;
  slug: string;
  files: ArtifactFile[];
}

export interface ProducedArtifact {
  type: string;
  slug: string;
}

/* ── SSE types ─────────────────────────────────────────────────── */

export type SSEEventType =
  | "pipeline_start"
  | "stage_start"
  | "pending_approval"
  | "approval_received"
  | "stage_complete"
  | "completed"
  | "failed"
  | "cancelled";

export interface SSEEvent {
  id: number;
  type: SSEEventType;
  data: Record<string, any>;
}
