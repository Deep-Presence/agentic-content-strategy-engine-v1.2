export type TaskStatus =
  | 'pending' | 'running' | 'completed' | 'failed'
  | 'cancelled' | 'pending_approval' | 'failed_restart';

export type Pipeline = 'research' | 'gap_analysis' | 'content';

export interface PipelineRunResponse {
  run_id: string;
  pipeline: Pipeline;
  company_slug: string;
  status: string;
  created_at: string;
}

export interface TaskResponse {
  run_id: string;
  pipeline: Pipeline;
  company_slug: string;
  status: TaskStatus;
  current_step: string | null;
  progress_pct: number | null;
  created_at: string;
  updated_at: string;
  result: Record<string, unknown> | null;
  error: string | null;
  approval_payload: Record<string, unknown> | null;
}

export interface TaskListResponse {
  tasks: TaskResponse[];
  total: number;
}

export interface HealthResponse {
  status: string;
}

export interface ReadinessResponse {
  ready: boolean;
  missing_keys: string[];
}

export interface CompaniesResponse {
  companies: string[];
}

export interface ArtifactFilesResponse {
  type: string;
  slug: string;
  files: string[];
}

export interface ApiError {
  detail: string;
  error_code?: string;
}
