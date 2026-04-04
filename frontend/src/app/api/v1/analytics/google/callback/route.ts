/**
 * BFF route for GA4 OAuth callback — NO AUTH REQUIRED.
 *
 * Google OAuth redirects the browser here with ?code=...&state=...
 * The catch-all BFF proxy at [...path]/route.ts requires auth,
 * but this dedicated route takes precedence (Next.js specificity)
 * and forwards to the backend without any auth token.
 *
 * The backend callback returns a RedirectResponse (307) to the
 * frontend settings page with ?analytics_connected=true or ?error=...
 */

import { NextRequest, NextResponse } from 'next/server';
import { BACKEND_URL } from '@/lib/bff/proxy';

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code');
  const state = request.nextUrl.searchParams.get('state');

  // Google may also send an error parameter on consent denial
  const error = request.nextUrl.searchParams.get('error');
  if (error) {
    return NextResponse.redirect(
      new URL(`/settings?tab=integrations&error=${encodeURIComponent(error)}`, request.url),
    );
  }

  if (!code || !state) {
    return NextResponse.redirect(
      new URL('/settings?tab=integrations&error=missing_params', request.url),
    );
  }

  // Forward to backend without auth token
  const backendUrl = new URL('/api/v1/analytics/google/callback', BACKEND_URL);
  backendUrl.searchParams.set('code', code);
  backendUrl.searchParams.set('state', state);

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl.toString(), {
      method: 'GET',
      redirect: 'manual', // Don't follow — we capture the Location header
      cache: 'no-store',
    });
  } catch {
    return NextResponse.redirect(
      new URL('/settings?tab=integrations&error=backend_unavailable', request.url),
    );
  }

  // Backend returns a 307 RedirectResponse — extract Location and redirect browser
  if (backendRes.status === 307 || backendRes.status === 302) {
    const location = backendRes.headers.get('Location');
    if (location) {
      // The backend redirects to the frontend settings URL with query params
      // e.g., https://app.deeppresence.ai/settings?tab=integrations&analytics_connected=true
      return NextResponse.redirect(location);
    }
  }

  // Unexpected response from backend
  return NextResponse.redirect(
    new URL('/settings?tab=integrations&error=oauth_failed', request.url),
  );
}
