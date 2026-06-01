/**
 * Role mapping between workspace membership roles and
 * frontend display labels (Admin/Editor/Viewer).
 */

import type { FrontendRole, WorkspaceRole } from './types';

const WORKSPACE_TO_FRONTEND: Record<WorkspaceRole, FrontendRole> = {
  owner: 'admin',
  admin: 'admin',
  member: 'editor',
  viewer: 'viewer',
};

const FRONTEND_TO_WORKSPACE: Record<FrontendRole, WorkspaceRole> = {
  admin: 'admin',
  editor: 'member',
  viewer: 'viewer',
};

export function workspaceRoleToDisplay(role: WorkspaceRole): FrontendRole {
  return WORKSPACE_TO_FRONTEND[role] ?? 'viewer';
}

export function displayRoleToWorkspace(role: FrontendRole): WorkspaceRole {
  return FRONTEND_TO_WORKSPACE[role] ?? 'viewer';
}

/** @deprecated Legacy JWT role mapping — prefer workspace roles. */
export function backendRoleToDisplay(role: string): FrontendRole {
  if (role === 'superuser') return 'admin';
  if (role === 'member') return 'editor';
  return 'viewer';
}

/** @deprecated Legacy JWT role mapping — prefer workspace roles. */
export function displayRoleToBackend(role: FrontendRole): string {
  return displayRoleToWorkspace(role) === 'admin' ? 'superuser' : displayRoleToWorkspace(role);
}

export const ROLE_OPTIONS: { value: FrontendRole; label: string; description: string }[] = [
  { value: 'admin', label: 'Admin', description: 'Full access to all settings and data' },
  { value: 'editor', label: 'Editor', description: 'Can create and edit content, view analytics' },
  { value: 'viewer', label: 'Viewer', description: 'Read-only access to dashboards' },
];

/** Roles available for invites (cannot invite owners). */
export const INVITE_ROLE_OPTIONS: { value: 'member' | 'viewer'; label: string }[] = [
  { value: 'member', label: 'Editor' },
  { value: 'viewer', label: 'Viewer' },
];

export const ROLE_DESCRIPTIONS: Record<FrontendRole, string> = {
  admin: 'Full access to all settings and data',
  editor: 'Can create and edit content, view analytics',
  viewer: 'Read-only access to dashboards',
};
