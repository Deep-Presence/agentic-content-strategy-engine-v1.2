/**
 * API service layer for Settings page.
 * All calls go through BFF proxy via same-origin fetch.
 */

import { api, workspaceQueryParams } from '@/lib/api-client';
import type {
  CMSConnectRequestAPI,
  CMSConnectResponseAPI,
  CMSConnectionInfoAPI,
  GA4AuthorizeResponseAPI,
  GA4ConnectionResponseAPI,
  GA4PropertiesResponseAPI,
  GA4SelectPropertyRequestAPI,
  GA4DisconnectResponseAPI,
  GA4SyncRequestAPI,
  GA4SyncResponseAPI,
  TaskStatusAPI,
  UpdateWorkspaceMemberRequestAPI,
  WorkspaceInviteResponseAPI,
  WorkspaceMembersResponseAPI,
  WorkspaceMemberAPI,
} from './types';

// ── Team (workspace memberships) ────────────────────────

export function fetchTeamMembers(
  workspaceSlug: string,
  signal?: AbortSignal,
): Promise<WorkspaceMembersResponseAPI> {
  return api.get<WorkspaceMembersResponseAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/members`,
    workspaceQueryParams(),
    signal,
  );
}

export function updateTeamMember(
  workspaceSlug: string,
  userId: string,
  body: UpdateWorkspaceMemberRequestAPI,
): Promise<WorkspaceMemberAPI> {
  return api.patch<WorkspaceMemberAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/members/${encodeURIComponent(userId)}`,
    body,
    { params: workspaceQueryParams() },
  );
}

export function generateWorkspaceInvite(
  workspaceSlug: string,
  role: 'member' | 'viewer',
): Promise<WorkspaceInviteResponseAPI> {
  return api.post<WorkspaceInviteResponseAPI>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceSlug)}/invites`,
    { role },
    { params: workspaceQueryParams() },
  );
}

// ── CMS (WordPress) ─────────────────────────────────────

export function connectCMS(
  body: CMSConnectRequestAPI,
): Promise<CMSConnectResponseAPI> {
  return api.post<CMSConnectResponseAPI>(
    '/api/v1/cms/connect',
    body,
    { params: workspaceQueryParams() },
  );
}

export function fetchCMSConnection(
  signal?: AbortSignal,
): Promise<CMSConnectionInfoAPI | null> {
  return api.get<CMSConnectionInfoAPI | null>(
    '/api/v1/cms/connection',
    workspaceQueryParams(),
    signal,
  );
}

export function disconnectCMS(): Promise<{ disconnected: boolean }> {
  return api.del<{ disconnected: boolean }>(
    '/api/v1/cms/connection',
    workspaceQueryParams(),
  );
}

// ── GA4 Analytics ───────────────────────────────────────

export function startGA4OAuth(
  returnUrl: string,
): Promise<GA4AuthorizeResponseAPI> {
  return api.get<GA4AuthorizeResponseAPI>(
    '/api/v1/analytics/google/authorize',
    workspaceQueryParams({ return_url: returnUrl }),
  );
}

export function fetchGA4Connection(
  signal?: AbortSignal,
): Promise<GA4ConnectionResponseAPI | null> {
  return api.get<GA4ConnectionResponseAPI | null>(
    '/api/v1/analytics/google/connection',
    workspaceQueryParams(),
    signal,
  );
}

export function disconnectGA4(
  purgeData: boolean,
): Promise<GA4DisconnectResponseAPI> {
  return api.del<GA4DisconnectResponseAPI>(
    '/api/v1/analytics/google/connection',
    workspaceQueryParams({ purge_data: purgeData }),
  );
}

export function fetchGA4Properties(
  signal?: AbortSignal,
): Promise<GA4PropertiesResponseAPI> {
  return api.get<GA4PropertiesResponseAPI>(
    '/api/v1/analytics/google/properties',
    workspaceQueryParams(),
    signal,
  );
}

export function selectGA4Property(
  body: GA4SelectPropertyRequestAPI,
): Promise<{ selected: boolean }> {
  return api.post<{ selected: boolean }>(
    '/api/v1/analytics/google/select-property',
    body,
    { params: workspaceQueryParams() },
  );
}

export function triggerGA4Sync(
  body?: GA4SyncRequestAPI,
): Promise<GA4SyncResponseAPI> {
  return api.post<GA4SyncResponseAPI>(
    '/api/v1/analytics/google/sync',
    body,
    { params: workspaceQueryParams() },
  );
}

export function fetchTaskStatus(taskId: string): Promise<TaskStatusAPI> {
  return api.get<TaskStatusAPI>(`/api/v1/tasks/${taskId}`, workspaceQueryParams());
}
