import type {
  PipelineRunResponse,
  TaskResponse,
  TaskListResponse,
  ApprovalResponse,
  ContentApprovalResponse,
  CancelResponse,
  ArtifactListResponse,
  ResearchStartRequest,
  GapAnalysisStartRequest,
  ContentStartRequest,
  ApprovalRequest,
  ContentApprovalRequest,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* ── Error class ───────────────────────────────────────────────── */

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public errorCode?: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

/* ── Generic fetch wrapper ─────────────────────────────────────── */

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail, error.error_code);
  }
  return res.json();
}

/* ── Health ─────────────────────────────────────────────────────── */

export const checkHealth = () =>
  apiFetch<{ status: string }>("/health");

export const checkReadiness = () =>
  apiFetch<{ ready: boolean; missing_keys: string[] }>("/readiness");

/* ── Pipeline starters ─────────────────────────────────────────── */

export const startResearch = (body: ResearchStartRequest) =>
  apiFetch<PipelineRunResponse>("/api/v1/research/start", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const startGapAnalysis = (body: GapAnalysisStartRequest) =>
  apiFetch<PipelineRunResponse>("/api/v1/gap-analysis/start", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const startContent = (body: ContentStartRequest) =>
  apiFetch<PipelineRunResponse>("/api/v1/content/start", {
    method: "POST",
    body: JSON.stringify(body),
  });

/* ── Status polling ────────────────────────────────────────────── */

export const getResearchStatus = (runId: string) =>
  apiFetch<TaskResponse>(`/api/v1/research/${runId}/status`);

export const getGapAnalysisStatus = (runId: string) =>
  apiFetch<TaskResponse>(`/api/v1/gap-analysis/${runId}/status`);

export const getContentStatus = (runId: string) =>
  apiFetch<TaskResponse>(`/api/v1/content/${runId}/status`);

export const getTaskDetail = (taskId: string) =>
  apiFetch<TaskResponse>(`/api/v1/tasks/${taskId}`);

/* ── Approvals ─────────────────────────────────────────────────── */

export const submitResearchApproval = (runId: string, body: ApprovalRequest) =>
  apiFetch<ApprovalResponse>(`/api/v1/research/${runId}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const submitContentApproval = (runId: string, body: ContentApprovalRequest) =>
  apiFetch<ContentApprovalResponse>(`/api/v1/content/${runId}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });

/* ── Tasks ─────────────────────────────────────────────────────── */

export const listTasks = (params?: { pipeline?: string; status?: string }) => {
  const query = params
    ? new URLSearchParams(
        Object.fromEntries(
          Object.entries(params).filter(([, v]) => v !== undefined)
        ) as Record<string, string>
      ).toString()
    : "";
  return apiFetch<TaskListResponse>(`/api/v1/tasks${query ? `?${query}` : ""}`);
};

export const cancelTask = (taskId: string) =>
  apiFetch<CancelResponse>(`/api/v1/tasks/${taskId}/cancel`, { method: "POST" });

/* ── Artifacts ─────────────────────────────────────────────────── */

export const listCompanies = () =>
  apiFetch<{ companies: string[] }>("/api/v1/artifacts/companies");

export const listArtifacts = (type: string, slug: string) =>
  apiFetch<ArtifactListResponse>(`/api/v1/artifacts/${type}/${slug}`);

export async function getArtifactContent(
  type: string,
  slug: string,
  filename: string,
): Promise<string> {
  const res = await fetch(
    `${API_BASE}/api/v1/artifacts/${type}/${slug}/${filename}`,
  );
  if (!res.ok) throw new ApiError(res.status, `Failed to fetch artifact: ${res.statusText}`);
  return res.text();
}

export function getArtifactUrl(type: string, slug: string, filename: string): string {
  return `${API_BASE}/api/v1/artifacts/${type}/${slug}/${filename}`;
}
