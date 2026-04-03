import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend, setSessionCookie, getSessionExpiresAt } from '@/lib/bff/proxy';

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: 'Invalid request body' }, { status: 400 });
  }

  let backendRes: Response;
  try {
    backendRes = await proxyToBackend('/api/v1/auth/login', { method: 'POST', body });
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }

  if (!backendRes.ok) {
    const errorBody = await backendRes.text();
    return new NextResponse(errorBody, {
      status: backendRes.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const data = await backendRes.json();
  const { access_token, user, company } = data;

  const response = NextResponse.json({
    user,
    company,
    session_expires_at: getSessionExpiresAt(access_token),
  });
  setSessionCookie(response, access_token);
  return response;
}
