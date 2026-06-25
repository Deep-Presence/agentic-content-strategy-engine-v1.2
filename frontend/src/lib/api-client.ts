/**
 * Central API client — every API call goes through same-origin BFF proxy.
 *
 * No token injection — httpOnly cookie is sent automatically by the browser.
 * No API_BASE_URL — all calls are relative (same-origin).
 */

import { getActiveWorkspaceSlug } from '@/stores/workspace';

import type {
  LoginPayload,
  RegisterPayload,
  JoinPayload,
  BFFAuthResponse,
  BFFMeResponse,
  InvitePayload,
  InviteResponse,
} from './auth/types';

/** Merge active workspace slug into query params for multi-tenant API routes. */
export function workspaceQueryParams(
  params?: Record<string, string | number | boolean | undefined>,
): Record<string, string | number | boolean | undefined> {
  const slug = getActiveWorkspaceSlug();
  if (!slug) return params ?? {};
  return { ...params, workspace_slug: slug };
}

// ── ApiError ─────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public code?: string,
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

// ── Single-flight 401 handler ────────────────────────────

let logoutPromise: Promise<void> | null = null;

function handleUnauthorized(): Promise<void> {
  if (!logoutPromise) {
    logoutPromise = (async () => {
      try {
        // Clear httpOnly cookie via BFF
        try {
          await fetch('/api/auth/logout', { method: 'POST' });
        } catch {
          // Best-effort
        }
        // Don't redirect if already on an auth page (prevents reload loop)
        if (typeof window !== 'undefined') {
          const path = window.location.pathname;
          if (path !== '/login' && path !== '/register' && path !== '/join') {
            window.location.href = '/login';
          }
        }
      } finally {
        // Reset so future 401s (after re-login) can trigger again
        logoutPromise = null;
      }
    })();
  }
  return logoutPromise;
}

// ── Core request function ────────────────────────────────

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function doFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const { method = 'GET', body, params, headers: customHeaders, signal } = options;

  // Build URL with query params — relative (same-origin)
  let url = path;
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        searchParams.set(key, String(value));
      }
    }
    const qs = searchParams.toString();
    if (qs) url += (url.includes('?') ? '&' : '?') + qs;
  }

  const headers: Record<string, string> = { ...customHeaders };
  // NO Authorization header — httpOnly cookie sent automatically
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
      credentials: 'same-origin',
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError(0, 'Network error — please check your connection.');
  }

  if (!res.ok) {
    let detail = 'An unexpected error occurred';
    let code: string | undefined;
    try {
      const errorBody = await res.json();
      const rawDetail = errorBody.detail;
      if (typeof rawDetail === 'string') {
        detail = rawDetail;
      } else if (rawDetail && typeof rawDetail === 'object') {
        const nested = rawDetail as Record<string, unknown>;
        detail = typeof nested.message === 'string' ? nested.message : detail;
        code = typeof nested.code === 'string' ? nested.code : undefined;
      }
      code = code ?? errorBody.code;
    } catch {
      // non-JSON error body
    }

    if (res.status === 401) {
      await handleUnauthorized();
      throw new ApiError(401, detail, code);
    }

    throw new ApiError(res.status, detail, code);
  }

  return res;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const res = await doFetch(path, options);
  return res.json() as Promise<T>;
}

async function requestText(path: string, options: RequestOptions = {}): Promise<string> {
  const res = await doFetch(path, options);
  return res.text();
}

// ── Convenience wrappers ─────────────────────────────────

export const api = {
  get: <T>(path: string, params?: RequestOptions['params'], signal?: AbortSignal) =>
    request<T>(path, { method: 'GET', params, signal }),

  getText: (path: string, params?: RequestOptions['params'], signal?: AbortSignal) =>
    requestText(path, { method: 'GET', params, signal }),

  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { method: 'POST', body, ...options }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body }),

  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { method: 'PATCH', body, ...options }),

  del: <T>(path: string, params?: RequestOptions['params']) =>
    request<T>(path, { method: 'DELETE', params }),
};

// ── Auth API (via BFF routes) ────────────────────────────

export const authApi = {
  login: (data: LoginPayload) =>
    request<BFFAuthResponse>('/api/auth/login', { method: 'POST', body: data }),

  register: (data: RegisterPayload) =>
    request<BFFAuthResponse>('/api/auth/register', { method: 'POST', body: data }),

  join: (data: JoinPayload) =>
    request<BFFAuthResponse>('/api/auth/join', { method: 'POST', body: data }),

  me: () => request<BFFMeResponse>('/api/auth/me'),

  logout: () => request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),

  invite: (data: InvitePayload) =>
    request<InviteResponse>('/api/auth/invite', { method: 'POST', body: data }),
};

// ── SSE (via catch-all proxy) ────────────────────────────

export function createSSEConnection(
  taskId: string,
  streamToken: string,
  onEvent: (event: MessageEvent) => void,
  onError?: (event: Event) => void,
): EventSource {
  const url = `/api/v1/tasks/${taskId}/events?stream_token=${encodeURIComponent(streamToken)}`;
  const source = new EventSource(url);
  source.onmessage = onEvent;
  if (onError) source.onerror = onError;
  return source;
}
