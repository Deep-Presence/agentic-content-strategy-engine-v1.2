import { NextResponse } from 'next/server';
import { clearSessionCookie } from '@/lib/bff/proxy';

export async function POST() {
  const response = NextResponse.json({ ok: true });
  clearSessionCookie(response);
  return response;
}
