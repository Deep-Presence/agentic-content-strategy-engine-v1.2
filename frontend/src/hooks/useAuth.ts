/**
 * useAuth — primary interface for all components.
 * No token in client state — isAuthenticated = !!user.
 */

import { useAuthStore, type AuthState } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  ROLE_HIERARCHY,
  WORKSPACE_MIN_FOR_USER_ROLE,
  WORKSPACE_ROLE_HIERARCHY,
} from '@/lib/auth/constants';
import type { UserRole } from '@/lib/auth/types';

function effectiveRoleLevel(workspaceRole: string | undefined, jwtRole: UserRole): number {
  if (workspaceRole) {
    return WORKSPACE_ROLE_HIERARCHY[workspaceRole] ?? 0;
  }
  return ROLE_HIERARCHY[jwtRole] ?? 0;
}

export function useAuth() {
  const user = useAuthStore((s: AuthState) => s.user);
  const company = useAuthStore((s: AuthState) => s.company);
  const sessionExpiresAt = useAuthStore((s: AuthState) => s.sessionExpiresAt);
  const isInitialized = useAuthStore((s: AuthState) => s.isInitialized);
  const isLoading = useAuthStore((s: AuthState) => s.isLoading);
  const activeWorkspaceSlug = useWorkspaceStore((s) => s.activeWorkspaceSlug);
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const activeWorkspace =
    workspaces.find((workspace) => workspace.slug === activeWorkspaceSlug) ?? null;

  const resolvedWorkspaceSlug = activeWorkspaceSlug || company?.slug || '';
  const workspaceRole = activeWorkspace?.role;
  const jwtRole = (user?.role ?? 'viewer') as UserRole;
  const roleLevel = effectiveRoleLevel(workspaceRole, jwtRole);

  return {
    isAuthenticated: !!user,
    isInitialized,
    isLoading,
    user,
    company,
    sessionExpiresAt,

    companySlug: resolvedWorkspaceSlug,
    activeWorkspaceSlug: resolvedWorkspaceSlug,
    activeWorkspace,
    companyName: activeWorkspace?.name ?? company?.name ?? '',
    companyDomain: activeWorkspace?.primaryDomain ?? company?.domain ?? '',
    userId: user?.id ?? '',
    fullName: user ? `${user.first_name} ${user.last_name}`.trim() : '',
    email: user?.email ?? '',
    role: jwtRole,
    workspaceRole: workspaceRole ?? null,

    isSuperuser: roleLevel >= WORKSPACE_MIN_FOR_USER_ROLE.superuser,
    isMember: roleLevel >= WORKSPACE_MIN_FOR_USER_ROLE.member,
    isViewer: roleLevel >= WORKSPACE_MIN_FOR_USER_ROLE.viewer,
    hasRole: (minRole: UserRole): boolean => {
      const requiredLevel = WORKSPACE_MIN_FOR_USER_ROLE[minRole] ?? 0;
      return roleLevel >= requiredLevel;
    },

    login: useAuthStore.getState().login,
    register: useAuthStore.getState().register,
    join: useAuthStore.getState().join,
    logout: useAuthStore.getState().logout,
  };
}
