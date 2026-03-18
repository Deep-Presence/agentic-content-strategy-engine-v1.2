/**
 * API client — typed fetch wrapper with JWT injection and error handling.
 *
 * All frontend data fetching goes through these helpers.
 * Token is read from the auth Zustand store (localStorage-backed).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? '';

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// ---------------------------------------------------------------------------
// Token accessor (lazy import to avoid circular deps with auth store)
// ---------------------------------------------------------------------------

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('dp_token');
}

function clearAuthAndRedirect() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('dp_token');
  localStorage.removeItem('dp_user');
  localStorage.removeItem('dp_company');
  window.location.href = '/login';
}

// ---------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: { signal?: AbortSignal },
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: options?.signal,
  });

  if (res.status === 401) {
    clearAuthAndRedirect();
    throw new ApiError(401, 'Unauthorized');
  }

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, detail);
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  // Handle non-JSON responses (e.g., .md files return text/plain)
  const contentType = res.headers?.get?.('content-type') ?? '';
  if (contentType.includes('text/plain') || contentType.includes('text/html')) {
    return res.text() as Promise<T>;
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Public helpers
// ---------------------------------------------------------------------------

export function apiGet<T>(path: string, options?: { signal?: AbortSignal }): Promise<T> {
  return request<T>('GET', path, undefined, options);
}

export function apiPost<T>(path: string, body?: unknown, options?: { signal?: AbortSignal }): Promise<T> {
  return request<T>('POST', path, body, options);
}

export function apiPut<T>(path: string, body?: unknown, options?: { signal?: AbortSignal }): Promise<T> {
  return request<T>('PUT', path, body, options);
}

export function apiDelete<T = void>(path: string, options?: { signal?: AbortSignal }): Promise<T> {
  return request<T>('DELETE', path, undefined, options);
}
