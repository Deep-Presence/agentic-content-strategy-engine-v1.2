import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from '@/lib/api/client';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// Mock localStorage
const store: Record<string, string> = {};
const mockLocalStorage = {
  getItem: vi.fn((key: string) => store[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
  removeItem: vi.fn((key: string) => { delete store[key]; }),
};
Object.defineProperty(globalThis, 'localStorage', { value: mockLocalStorage });

// Mock window.location
const mockLocation = { href: '' };
Object.defineProperty(globalThis, 'window', {
  value: { location: mockLocation },
  writable: true,
});

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocation.href = '';
    Object.keys(store).forEach(k => delete store[k]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('apiGet sends GET request with auth header when token exists', async () => {
    store['dp_token'] = 'test-token-123';
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' }),
    });

    const result = await apiGet('/health');

    expect(mockFetch).toHaveBeenCalledWith('/health', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-token-123',
      },
      body: undefined,
      signal: undefined,
    });
    expect(result).toEqual({ status: 'ok' });
  });

  it('apiGet sends GET request without auth header when no token', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ data: 'public' }),
    });

    await apiGet('/health');

    expect(mockFetch).toHaveBeenCalledWith('/health', expect.objectContaining({
      headers: expect.not.objectContaining({
        Authorization: expect.any(String),
      }),
    }));
  });

  it('apiPost sends JSON body', async () => {
    store['dp_token'] = 'tok';
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ access_token: 'abc' }),
    });

    const result = await apiPost('/api/v1/auth/login', { email: 'a@b.com', password: 'pass' });

    expect(mockFetch).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ email: 'a@b.com', password: 'pass' }),
    }));
    expect(result).toEqual({ access_token: 'abc' });
  });

  it('apiPut sends PUT request', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ updated: true }),
    });

    await apiPut('/api/v1/test', { name: 'new' });

    expect(mockFetch).toHaveBeenCalledWith('/api/v1/test', expect.objectContaining({
      method: 'PUT',
    }));
  });

  it('apiDelete sends DELETE request', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ deleted: true }),
    });

    await apiDelete('/api/v1/test/1');

    expect(mockFetch).toHaveBeenCalledWith('/api/v1/test/1', expect.objectContaining({
      method: 'DELETE',
    }));
  });

  it('throws ApiError on non-2xx response', async () => {
    store['dp_token'] = 'tok';
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Domain already taken' }),
    });

    await expect(apiPost('/api/v1/auth/register', {})).rejects.toThrow(ApiError);
    try {
      await apiPost('/api/v1/auth/register', {});
    } catch {
      // Already tested above
    }
  });

  it('clears auth and redirects on 401', async () => {
    store['dp_token'] = 'expired-token';
    store['dp_user'] = '{}';
    store['dp_company'] = '{}';
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Unauthorized' }),
    });

    await expect(apiGet('/api/v1/auth/me')).rejects.toThrow(ApiError);

    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('dp_token');
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('dp_user');
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('dp_company');
    expect(mockLocation.href).toBe('/login');
  });

  it('handles 204 No Content', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
    });

    const result = await apiDelete('/api/v1/test/1');
    expect(result).toBeUndefined();
  });
});
