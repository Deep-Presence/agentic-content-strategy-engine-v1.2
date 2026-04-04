/**
 * API service layer for Settings page.
 * All calls go through BFF proxy via same-origin fetch.
 */

import { api, authApi } from '@/lib/api-client';
import type { InviteResponse } from '@/lib/auth/types';
import type {
  TeamListResponseAPI,
  TeamMemberAPI,
  UpdateUserRequestAPI,
  CMSConnectRequestAPI,
  CMSConnectResponseAPI,
  CMSConnectionInfoAPI,
  GA4AuthorizeResponseAPI,
  GA4ConnectionResponseAPI,
  GA4PropertiesResponseAPI,
  GA4SelectPropertyRequestAPI,
  GA4DisconnectResponseAPI,
  GA4SyncResponseAPI,
} from './types';

// ── Team ────────────────────────────────────────────────

export function fetchTeamMembers(
  companySlug: string,
  signal?: AbortSignal,
): Promise<TeamListResponseAPI> {
  return api.get<TeamListResponseAPI>(
    `/api/v1/companies/${companySlug}/settings/team`,
    undefined,
    signal,
  );
}

export function updateTeamMember(
  companySlug: string,
  userId: string,
  body: UpdateUserRequestAPI,
): Promise<TeamMemberAPI> {
  return api.put<TeamMemberAPI>(
    `/api/v1/companies/${companySlug}/settings/team/${userId}`,
    body,
  );
}

export function generateInviteCode(
  role: 'member' | 'viewer',
): Promise<InviteResponse> {
  return authApi.invite({ role });
}

// ── CMS (WordPress) ─────────────────────────────────────

export function connectCMS(
  body: CMSConnectRequestAPI,
): Promise<CMSConnectResponseAPI> {
  return api.post<CMSConnectResponseAPI>('/api/v1/cms/connect', body);
}

export function fetchCMSConnection(
  signal?: AbortSignal,
): Promise<CMSConnectionInfoAPI | null> {
  return api.get<CMSConnectionInfoAPI | null>(
    '/api/v1/cms/connection',
    undefined,
    signal,
  );
}

export function disconnectCMS(): Promise<{ disconnected: boolean }> {
  return api.del<{ disconnected: boolean }>('/api/v1/cms/connection');
}

// ── GA4 Analytics ───────────────────────────────────────

export function startGA4OAuth(
  returnUrl: string,
): Promise<GA4AuthorizeResponseAPI> {
  return api.get<GA4AuthorizeResponseAPI>(
    '/api/v1/analytics/google/authorize',
    { return_url: returnUrl },
  );
}

export function fetchGA4Connection(
  signal?: AbortSignal,
): Promise<GA4ConnectionResponseAPI | null> {
  return api.get<GA4ConnectionResponseAPI | null>(
    '/api/v1/analytics/google/connection',
    undefined,
    signal,
  );
}

export function disconnectGA4(
  purgeData: boolean,
): Promise<GA4DisconnectResponseAPI> {
  return api.del<GA4DisconnectResponseAPI>(
    '/api/v1/analytics/google/connection',
    { purge_data: purgeData },
  );
}

export function fetchGA4Properties(
  signal?: AbortSignal,
): Promise<GA4PropertiesResponseAPI> {
  return api.get<GA4PropertiesResponseAPI>(
    '/api/v1/analytics/google/properties',
    undefined,
    signal,
  );
}

export function selectGA4Property(
  body: GA4SelectPropertyRequestAPI,
): Promise<{ selected: boolean }> {
  return api.post<{ selected: boolean }>(
    '/api/v1/analytics/google/select-property',
    body,
  );
}

export function triggerGA4Sync(): Promise<GA4SyncResponseAPI> {
  return api.post<GA4SyncResponseAPI>('/api/v1/analytics/google/sync');
}
