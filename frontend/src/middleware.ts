/**
 * Next.js edge middleware — auth + CSP nonces.
 *
 * 1. Generates per-request CSP nonce
 * 2. Reads httpOnly dp_session cookie, validates exp (ISO8601)
 * 3. Auth redirects (unauthenticated → /login, authenticated → away from auth pages)
 * 4. Sets Content-Security-Policy + x-nonce headers on ALL responses
 */

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const AUTH_COOKIE = 'dp_session';
const AUTH_ROUTES = ['/login', '/register', '/join'];
const PUBLIC_ROUTES = ['/login', '/register', '/join'];

// ── Token validation ─────────────────────────────────────

function isValidSession(cookieValue: string | undefined): boolean {
  if (!cookieValue) return false;
  try {
    const parts = cookieValue.split('.');
    if (parts.length !== 2) return false;
    // base64url → base64 (edge runtime has atob but not Buffer)
    const base64 = parts[0].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded));
    if (!payload.exp) return false;
    // exp is ISO8601 string (NOT Unix timestamp)
    const expiresAt = new Date(payload.exp).getTime();
    return !isNaN(expiresAt) && Date.now() < expiresAt;
  } catch {
    return false;
  }
}

// ── CSP nonce ────────────────────────────────────────────

function generateNonce(): string {
  return btoa(crypto.randomUUID());
}

function buildCSP(nonce: string): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' https://www.google.com https://logo.clearbit.com https://img.logo.dev data:",
    "font-src 'self' https://fonts.gstatic.com",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ');
}

// ── Middleware ────────────────────────────────────────────

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Auth validation
  const sessionCookie = request.cookies.get(AUTH_COOKIE);
  const hasValidSession = isValidSession(sessionCookie?.value);

  // Authenticated user on auth pages → redirect to /
  if (hasValidSession && AUTH_ROUTES.some((r) => pathname === r)) {
    const response = NextResponse.redirect(new URL('/', request.url));
    applyCSP(response);
    return response;
  }

  // Unauthenticated user on protected pages → redirect to /login
  const isPublic = PUBLIC_ROUTES.some(
    (r) => pathname === r || pathname.startsWith(r + '/'),
  );
  if (!hasValidSession && !isPublic) {
    const loginUrl = new URL('/login', request.url);
    if (pathname !== '/') {
      loginUrl.searchParams.set('redirect', pathname);
    }
    const response = NextResponse.redirect(loginUrl);
    applyCSP(response);
    return response;
  }

  // Pass through with CSP
  const response = NextResponse.next();
  applyCSP(response);
  return response;
}

function applyCSP(response: NextResponse): void {
  // Skip CSP in development — strict-dynamic blocks Next.js HMR/hydration scripts
  if (process.env.NODE_ENV === 'development') return;
  const nonce = generateNonce();
  response.headers.set('Content-Security-Policy', buildCSP(nonce));
  response.headers.set('x-nonce', nonce);
}

export const config = {
  matcher: [
    // Exclude: _next, static assets, API routes (BFF handles its own auth)
    '/((?!_next/static|_next/image|favicon\\.ico|api/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
};
