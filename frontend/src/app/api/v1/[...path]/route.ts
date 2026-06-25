/**
 * Catch-all BFF proxy — forwards all /api/v1/* requests to the backend.
 * Reads httpOnly cookie, injects Authorization header.
 * Clears cookie on 401. Streams SSE responses.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getSessionToken, clearSessionCookie, BACKEND_URL } from '@/lib/bff/proxy';

async function handleProxy(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const token = getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: 'Not authenticated' }, { status: 401 });
  }

  const backendPath = `/api/v1/${params.path.join('/')}`;
  const url = new URL(backendPath, BACKEND_URL);

  // Forward query parameters
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };

  const contentType = request.headers.get('content-type');
  if (contentType) {
    headers['Content-Type'] = contentType;
  }

  // Read body for non-GET/HEAD
  let body: ArrayBuffer | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    const buf = await request.arrayBuffer();
    if (buf.byteLength > 0) body = buf;
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(url.toString(), {
      method: request.method,
      headers,
      body,
      cache: 'no-store',
    } as RequestInit);
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }

  const backendContentType = backendRes.headers.get('content-type') ?? '';

  // SSE: stream through
  if (backendContentType.includes('text/event-stream') && backendRes.body) {
    return new Response(backendRes.body, {
      status: backendRes.status,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  }

  // On 401: clear cookie
  if (backendRes.status === 401) {
    const errorBody = await backendRes.text();
    const response = new NextResponse(errorBody, {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
    clearSessionCookie(response);
    return response;
  }

  // Forward response
  const responseBody = await backendRes.arrayBuffer();
  return new NextResponse(responseBody, {
    status: backendRes.status,
    headers: { 'Content-Type': backendContentType || 'application/json' },
  });
}

export const GET = handleProxy;
export const POST = handleProxy;
export const PUT = handleProxy;
export const PATCH = handleProxy;
export const DELETE = handleProxy;
