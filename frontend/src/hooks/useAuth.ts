/**
 * useAuth — primary interface for all components.
 * No token in client state — isAuthenticated = !!user.
 */

import { useAuthStore, type AuthState } from '@/stores/auth';
import { ROLE_HIERARCHY } from '@/lib/auth/constants';
import type { UserRole } from '@/lib/auth/types';

export function useAuth() {
  const user = useAuthStore((s: AuthState) => s.user);
  const company = useAuthStore((s: AuthState) => s.company);
  const sessionExpiresAt = useAuthStore((s: AuthState) => s.sessionExpiresAt);
  const isInitialized = useAuthStore((s: AuthState) => s.isInitialized);
  const isLoading = useAuthStore((s: AuthState) => s.isLoading);

  return {
    isAuthenticated: !!user,
    isInitialized,
    isLoading,
    user,
    company,
    sessionExpiresAt,

    companySlug: company?.slug ?? '',
    companyName: company?.name ?? '',
    companyDomain: company?.domain ?? '',
    userId: user?.id ?? '',
    fullName: user ? `${user.first_name} ${user.last_name}`.trim() : '',
    email: user?.email ?? '',
    role: (user?.role ?? 'viewer') as UserRole,

    isSuperuser: user?.role === 'superuser',
    isMember: user?.role === 'member' || user?.role === 'superuser',
    isViewer: user?.role === 'viewer',
    hasRole: (minRole: UserRole): boolean => {
      const userLevel = ROLE_HIERARCHY[user?.role ?? 'viewer'] ?? 0;
      const requiredLevel = ROLE_HIERARCHY[minRole] ?? 0;
      return userLevel >= requiredLevel;
    },

    login: useAuthStore.getState().login,
    register: useAuthStore.getState().register,
    join: useAuthStore.getState().join,
    logout: useAuthStore.getState().logout,
  };
}
