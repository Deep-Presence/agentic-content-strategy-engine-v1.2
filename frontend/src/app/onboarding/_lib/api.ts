import { api, workspaceQueryParams } from '@/lib/api-client';

export interface OnboardingStartRequestAPI {
  workspace_slug?: string;
  industry?: string | null;
  seed_personas?: string[];
  seed_urls?: string[];
  max_pages?: number;
  max_depth?: number;
  max_personas?: number;
  max_authors?: number;
  max_queries?: number;
  platforms?: string[];
  language?: string;
  region?: string | null;
  force_rerun?: boolean;
}

export interface OnboardingStartResponseAPI {
  run_id: string;
  pipeline: string;
  company_slug: string;
  workspace_id?: string;
  product_slug?: string | null;
  effective_slug?: string;
  status: string;
  created_at: string;
}

export interface OnboardingTaskStatusAPI {
  run_id: string;
  pipeline: string;
  company_slug: string;
  product_slug?: string | null;
  effective_slug?: string;
  status: string;
  current_step?: string | null;
  created_at?: string;
  updated_at?: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
}

export interface TaskSummaryAPI {
  run_id: string;
  pipeline: string;
  status: string;
  company_slug: string;
  product_slug?: string | null;
  effective_slug?: string | null;
  current_step?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponseAPI {
  tasks: TaskSummaryAPI[];
  total: number;
}

export function startOnboarding(
  body: OnboardingStartRequestAPI,
): Promise<OnboardingStartResponseAPI> {
  return api.post<OnboardingStartResponseAPI>(
    '/api/v1/onboarding/start',
    body,
    { params: workspaceQueryParams() },
  );
}
export function fetchOnboardingStatus(
  runId: string,
  signal?: AbortSignal,
): Promise<OnboardingTaskStatusAPI> {
  return api.get<OnboardingTaskStatusAPI>(
    `/api/v1/onboarding/${encodeURIComponent(runId)}/status`,
    workspaceQueryParams(),
    signal,
  );
}

export function fetchOnboardingTasks(
  workspaceSlug: string,
  signal?: AbortSignal,
): Promise<TaskListResponseAPI> {
  return api.get<TaskListResponseAPI>(
    '/api/v1/tasks',
    {
      ...workspaceQueryParams(),
      workspace_slug: workspaceSlug,
      pipeline: 'onboarding',
    },
    signal,
  );
}
