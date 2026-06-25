import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend, getSessionToken, clearSessionCookie } from '@/lib/bff/proxy';

export async function POST(request: NextRequest) {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: 'Not authenticated' }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: 'Invalid request body' }, { status: 400 });
  }

  let backendRes: Response;
  try {
    backendRes = await proxyToBackend('/api/v1/auth/invite', { method: 'POST', body, token });
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }

  if (backendRes.status === 401) {
    const response = NextResponse.json({ detail: 'Session expired' }, { status: 401 });
    clearSessionCookie(response);
    return response;
  }

  const responseBody = await backendRes.text();
  return new NextResponse(responseBody, {
    status: backendRes.status,
    headers: { 'Content-Type': 'application/json' },
  });
}
