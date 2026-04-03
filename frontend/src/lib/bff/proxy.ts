/**
 * BFF proxy utilities — server-side only.
 * Handles httpOnly cookie operations, token decode, and backend forwarding.
 */

import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

const AUTH_COOKIE = 'dp_session';
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const COOKIE_MAX_AGE = 86400; // 24h, matches backend token TTL

// ── Token decode (server-side, no verification) ──────────

export function decodeTokenPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 2) return null;
    const base64 = parts[0].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const json = Buffer.from(padded, 'base64').toString('utf-8');
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function getSessionExpiresAt(token: string): string | null {
  const payload = decodeTokenPayload(token);
  if (!payload?.exp) return null;
  return String(payload.exp); // ISO8601 string from backend
}

// ── Cookie operations ────────────────────────────────────

export function setSessionCookie(response: NextResponse, token: string): void {
  response.cookies.set(AUTH_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: COOKIE_MAX_AGE,
  });
}

export function clearSessionCookie(response: NextResponse): void {
  response.cookies.set(AUTH_COOKIE, '', {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 0,
  });
}

export function getSessionToken(): string | null {
  const cookieStore = cookies();
  return cookieStore.get(AUTH_COOKIE)?.value ?? null;
}

// ── Backend proxy ────────────────────────────────────────

export async function proxyToBackend(
  backendPath: string,
  options: {
    method: string;
    body?: unknown;
    token?: string | null;
  },
): Promise<Response> {
  const { method, body, token } = options;
  const url = `${BACKEND_URL}${backendPath}`;

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  return fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  } as RequestInit);
}

export { AUTH_COOKIE, BACKEND_URL };
