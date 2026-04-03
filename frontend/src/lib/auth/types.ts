/**
 * Auth types — mirrors backend api/auth/models.py exactly.
 * Do NOT modify without checking backend model shapes.
 */

// ── Request types ────────────────────────────────────────

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  company_name: string;
  company_domain: string;
}

export interface JoinPayload {
  invite_code: string;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}

export interface InvitePayload {
  role: 'member' | 'viewer';
}

// ── Response types ───────────────────────────────────────

export type UserRole = 'superuser' | 'member' | 'viewer';

export interface AuthUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  company_id: string;
  is_active: boolean;
}

export interface AuthCompany {
  id: string;
  slug: string;
  name: string;
  domain: string;
  industry?: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
  company: AuthCompany;
}

export interface MeResponse {
  user: AuthUser;
  company: AuthCompany;
}

export interface InviteResponse {
  invite_code: string;
  company_slug: string;
  role: string;
}

// ── Error shape ──────────────────────────────────────────

export interface ApiErrorResponse {
  detail: string;
  code?: string;
}

// ── SSE (foundation) ─────────────────────────────────────

export interface StreamTokenResponse {
  stream_token: string;
  expires_in: number;
}

// ── BFF response types (no token exposed) ────────────────

export interface BFFAuthResponse {
  user: AuthUser;
  company: AuthCompany;
  session_expires_at: string | null; // ISO8601
}

export interface BFFMeResponse extends MeResponse {
  session_expires_at: string | null; // ISO8601
}

// ── Token payload (decoded server-side, not trusted) ─────

export interface TokenPayload {
  user_id?: string;
  company_slug?: string;
  exp?: string; // ISO8601 datetime string (NOT Unix timestamp)
  stream_only?: boolean;
}
