/**
 * Role mapping between backend (superuser/member/viewer) and
 * frontend display labels (Admin/Editor/Viewer).
 */

import type { BackendRole, FrontendRole } from './types';

const BACKEND_TO_FRONTEND: Record<BackendRole, FrontendRole> = {
  superuser: 'admin',
  member: 'editor',
  viewer: 'viewer',
};

const FRONTEND_TO_BACKEND: Record<FrontendRole, BackendRole> = {
  admin: 'superuser',
  editor: 'member',
  viewer: 'viewer',
};

export function backendRoleToDisplay(role: BackendRole): FrontendRole {
  return BACKEND_TO_FRONTEND[role] ?? 'viewer';
}

export function displayRoleToBackend(role: FrontendRole): BackendRole {
  return FRONTEND_TO_BACKEND[role] ?? 'viewer';
}

export const ROLE_OPTIONS: { value: FrontendRole; label: string; description: string }[] = [
  { value: 'admin', label: 'Admin', description: 'Full access to all settings and data' },
  { value: 'editor', label: 'Editor', description: 'Can create and edit content, view analytics' },
  { value: 'viewer', label: 'Viewer', description: 'Read-only access to dashboards' },
];

/** Roles available for invites (cannot invite superusers). */
export const INVITE_ROLE_OPTIONS: { value: 'member' | 'viewer'; label: string }[] = [
  { value: 'member', label: 'Editor' },
  { value: 'viewer', label: 'Viewer' },
];

export const ROLE_DESCRIPTIONS: Record<FrontendRole, string> = {
  admin: 'Full access to all settings and data',
  editor: 'Can create and edit content, view analytics',
  viewer: 'Read-only access to dashboards',
};
