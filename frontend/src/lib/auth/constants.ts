/**
 * Auth constants — routes, roles, BFF endpoints.
 * No more localStorage keys or API_BASE_URL (BFF handles everything server-side).
 */

export const PUBLIC_ROUTES = ['/login', '/register', '/join'] as const;

export const ROLE_HIERARCHY: Record<string, number> = {
  viewer: 0,
  member: 1,
  superuser: 2,
};

export const AUTH_CHANNEL = 'dp_auth_channel';

/** BFF route paths (same-origin, relative) */
export const BFF_ENDPOINTS = {
  login: '/api/auth/login',
  register: '/api/auth/register',
  join: '/api/auth/join',
  me: '/api/auth/me',
  logout: '/api/auth/logout',
  invite: '/api/auth/invite',
} as const;

export const SESSION_EXPIRY_WARNING_MS = 30 * 60 * 1000; // 30 minutes
