import { api, workspaceQueryParams } from '@/lib/api-client';

export interface CredentialStatusAPI {
  provider: string;
  configured: boolean;
  status: string;
  masked_key: string;
  last_validated_at: string | null;
  last_validation_error: string;
}

export interface AgentCatalogItemAPI {
  agent_key: string;
  display_name: string;
  group: string;
  pipeline: string;
  pipeline_step: string;
  default_model: string;
  capabilities: string[];
  required: boolean;
  description: string;
}

export interface AgentModelConfigAPI {
  agent_key: string;
  model: string;
  provider: string;
  temperature: number | null;
  max_tokens: number | null;
  timeout_s: number | null;
  enabled: boolean;
  uses_default: boolean;
  updated_at: string | null;
}

export interface AgentUsageSummaryAPI {
  agent_key: string;
  call_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: number;
  last_used_at: string | null;
}

export interface WorkspaceModelConfigAPI {
  workspace_slug: string;
  credential: CredentialStatusAPI;
  catalog: AgentCatalogItemAPI[];
  configs: AgentModelConfigAPI[];
  missing_required_agent_keys: string[];
  usage_summary: AgentUsageSummaryAPI[];
}

export interface OpenRouterKeyUpsertRequestAPI {
  api_key: string;
}

export interface OpenRouterKeyTestRequestAPI {
  api_key?: string | null;
}

export interface CredentialTestResponseAPI {
  ok: boolean;
  provider: string;
  model: string;
  error: string;
}

export interface AgentModelConfigUpdateRequestAPI {
  model: string;
  temperature: number | null;
  max_tokens: number | null;
  timeout_s: number | null;
  enabled?: boolean | null;
}

export interface AgentConfigTestResponseAPI {
  ok: boolean;
  agent_key: string;
  model: string;
  error: string;
}

export interface DeleteOpenRouterKeyResponseAPI {
  deleted: boolean;
}

export interface ModelConfigPreflightResponseAPI {
  ok: boolean;
  missing_credential: boolean;
  invalid_credential: boolean;
  missing_agent_keys: string[];
  disabled_agent_keys: string[];
  errors: string[];
}

export function fetchWorkspaceModelConfig(
  workspaceSlug: string,
  signal?: AbortSignal,
): Promise<WorkspaceModelConfigAPI> {
  return api.get<WorkspaceModelConfigAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/model-config`,
    workspaceQueryParams(),
    signal,
  );
}
export function upsertOpenRouterKey(
  workspaceSlug: string,
  body: OpenRouterKeyUpsertRequestAPI,
): Promise<CredentialStatusAPI> {
  return api.put<CredentialStatusAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/model-config/openrouter-key`,
    body,
  );
}

export function deleteOpenRouterKey(
  workspaceSlug: string,
): Promise<DeleteOpenRouterKeyResponseAPI> {
  return api.del<DeleteOpenRouterKeyResponseAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/model-config/openrouter-key`,
    workspaceQueryParams(),
  );
}

export function testOpenRouterKey(
  workspaceSlug: string,
  body: OpenRouterKeyTestRequestAPI,
): Promise<CredentialTestResponseAPI> {
  return api.post<CredentialTestResponseAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/model-config/openrouter-key/test`,
    body,
    { params: workspaceQueryParams() },
  );
}

export function updateAgentModelConfig(
  workspaceSlug: string,
  agentKey: string,
  body: AgentModelConfigUpdateRequestAPI,
): Promise<AgentModelConfigAPI> {
  return api.patch<AgentModelConfigAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/model-config/agents/${encodeURIComponent(agentKey)}`,
    body,
    { params: workspaceQueryParams() },
  );
}

export function testAgentModelConfig(
  workspaceSlug: string,
  agentKey: string,
): Promise<AgentConfigTestResponseAPI> {
  return api.post<AgentConfigTestResponseAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/model-config/agents/${encodeURIComponent(agentKey)}/test`,
    {},
    { params: workspaceQueryParams() },
  );
}

export function preflightModelConfig(
  workspaceSlug: string,
  agentKeys: string[],
): Promise<ModelConfigPreflightResponseAPI> {
  return api.post<ModelConfigPreflightResponseAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/model-config/preflight`,
    { agent_keys: agentKeys },
    { params: workspaceQueryParams() },
  );
}
