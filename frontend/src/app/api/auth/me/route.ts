import { NextResponse } from 'next/server';
import { proxyToBackend, getSessionToken, clearSessionCookie, getSessionExpiresAt } from '@/lib/bff/proxy';

export async function GET() {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: 'Not authenticated' }, { status: 401 });
  }

  let backendRes: Response;
  try {
    backendRes = await proxyToBackend('/api/v1/auth/me', { method: 'GET', token });
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }

  if (backendRes.status === 401) {
    const response = NextResponse.json({ detail: 'Session expired' }, { status: 401 });
    clearSessionCookie(response);
    return response;
  }

  if (!backendRes.ok) {
    const errorBody = await backendRes.text();
    return new NextResponse(errorBody, {
      status: backendRes.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const data = await backendRes.json();
  return NextResponse.json({
    ...data,
    session_expires_at: getSessionExpiresAt(token),
  });
}
