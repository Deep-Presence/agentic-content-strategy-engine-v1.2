import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuthStore } from '@/stores/auth';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  },
}));

import { apiGet, apiPost } from '@/lib/api/client';

// Mock localStorage
const store: Record<string, string> = {};
Object.defineProperty(globalThis, 'localStorage', {
  value: {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
  },
});

const mockUser = {
  id: 'user-1',
  email: 'test@example.com',
  first_name: 'Test',
  last_name: 'User',
  role: 'superuser',
  company_id: 'comp-1',
  is_active: true,
};

const mockCompany = {
  id: 'comp-1',
  slug: 'test-co',
  name: 'Test Co',
  domain: 'test.com',
};

const loginResponse = {
  access_token: 'jwt-token-abc',
  user: mockUser,
  company: mockCompany,
};

describe('Auth Store', () => {
  beforeEach(() => {
    // Reset store state
    useAuthStore.setState({
      token: null,
      user: null,
      company: null,
      isLoading: false,
      error: null,
    });
    Object.keys(store).forEach(k => delete store[k]);
    vi.clearAllMocks();
  });

  it('starts with null state', () => {
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
    expect(state.company).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('login sets token, user, company and persists to localStorage', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce(loginResponse);

    await useAuthStore.getState().login('test@example.com', 'password123');

    const state = useAuthStore.getState();
    expect(state.token).toBe('jwt-token-abc');
    expect(state.user).toEqual(mockUser);
    expect(state.company).toEqual(mockCompany);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();

    expect(store['dp_token']).toBe('jwt-token-abc');
    expect(JSON.parse(store['dp_user'])).toEqual(mockUser);
    expect(JSON.parse(store['dp_company'])).toEqual(mockCompany);
  });

  it('login sets error on failure', async () => {
    const { ApiError } = await import('@/lib/api/client');
    vi.mocked(apiPost).mockRejectedValueOnce(new ApiError(401, 'Invalid credentials'));

    await expect(useAuthStore.getState().login('bad@email.com', 'wrong')).rejects.toThrow();

    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.error).toBe('Invalid credentials');
    expect(state.isLoading).toBe(false);
  });

  it('register sets auth state and persists', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce(loginResponse);

    await useAuthStore.getState().register({
      first_name: 'Test',
      last_name: 'User',
      email: 'test@example.com',
      password: 'password123',
      company_name: 'Test Co',
      company_domain: 'test.com',
    });

    const state = useAuthStore.getState();
    expect(state.token).toBe('jwt-token-abc');
    expect(state.company?.slug).toBe('test-co');
  });

  it('join sets auth state', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce(loginResponse);

    await useAuthStore.getState().join({
      invite_code: 'ABC-123',
      first_name: 'Test',
      last_name: 'User',
      email: 'test@example.com',
      password: 'password123',
    });

    const state = useAuthStore.getState();
    expect(state.token).toBe('jwt-token-abc');
  });

  it('fetchMe validates token and updates state', async () => {
    store['dp_token'] = 'valid-token';
    useAuthStore.setState({ token: 'valid-token' });

    vi.mocked(apiGet).mockResolvedValueOnce({
      user: mockUser,
      company: mockCompany,
    });

    const valid = await useAuthStore.getState().fetchMe();

    expect(valid).toBe(true);
    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(useAuthStore.getState().company).toEqual(mockCompany);
  });

  it('fetchMe returns false and clears state on invalid token', async () => {
    store['dp_token'] = 'expired-token';
    useAuthStore.setState({ token: 'expired-token' });

    vi.mocked(apiGet).mockRejectedValueOnce(new Error('401'));

    const valid = await useAuthStore.getState().fetchMe();

    expect(valid).toBe(false);
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('checkOnboardingNeeded returns true when no research artifacts', async () => {
    useAuthStore.setState({ company: mockCompany });
    vi.mocked(apiGet).mockResolvedValueOnce({
      slug: 'test-co',
      has_research: false,
      has_gap_analysis: false,
      has_content: false,
    });

    const needed = await useAuthStore.getState().checkOnboardingNeeded();
    expect(needed).toBe(true);
  });

  it('checkOnboardingNeeded returns false when research artifacts exist', async () => {
    useAuthStore.setState({ company: mockCompany });
    vi.mocked(apiGet).mockResolvedValueOnce({
      slug: 'test-co',
      has_research: true,
      has_gap_analysis: true,
      has_content: false,
    });

    const needed = await useAuthStore.getState().checkOnboardingNeeded();
    expect(needed).toBe(false);
  });

  it('logout clears all state and localStorage', () => {
    useAuthStore.setState({
      token: 'tok',
      user: mockUser,
      company: mockCompany,
    });
    store['dp_token'] = 'tok';
    store['dp_user'] = JSON.stringify(mockUser);
    store['dp_company'] = JSON.stringify(mockCompany);

    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
    expect(state.company).toBeNull();
    expect(store['dp_token']).toBeUndefined();
  });

  it('hydrateFromStorage restores state from localStorage', () => {
    store['dp_token'] = 'stored-token';
    store['dp_user'] = JSON.stringify(mockUser);
    store['dp_company'] = JSON.stringify(mockCompany);

    useAuthStore.getState().hydrateFromStorage();

    const state = useAuthStore.getState();
    expect(state.token).toBe('stored-token');
    expect(state.user).toEqual(mockUser);
    expect(state.company).toEqual(mockCompany);
  });
});
