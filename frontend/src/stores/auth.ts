/**
 * Auth Zustand store — manages JWT token, user, and company state.
 *
 * Persists token + user + company to localStorage so sessions survive refresh.
 * The dashboard layout uses this to gate access and redirect to /login or /onboarding.
 */
import { create } from 'zustand';
import { apiGet, apiPost, ApiError } from '@/lib/api/client';
import { AUTH, COMPANIES } from '@/lib/api/endpoints';

// ---------------------------------------------------------------------------
// Types (mirror backend response shapes)
// ---------------------------------------------------------------------------

export interface AuthUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  company_id: string;
  is_active: boolean;
}

export interface AuthCompany {
  id: string;
  slug: string;
  name: string;
  domain: string;
}

interface LoginResponse {
  access_token: string;
  user: AuthUser;
  company: AuthCompany;
}

interface MeResponse {
  user: AuthUser;
  company: AuthCompany;
}

export interface CompanyProfile {
  slug: string;
  name: string;
  domain: string;
  has_research: boolean;
  has_gap_analysis: boolean;
  has_content: boolean;
}

// ---------------------------------------------------------------------------
// Store shape
// ---------------------------------------------------------------------------

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  company: AuthCompany | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    first_name: string;
    last_name: string;
    email: string;
    password: string;
    company_name: string;
    company_domain: string;
  }) => Promise<void>;
  join: (data: {
    invite_code: string;
    first_name: string;
    last_name: string;
    email: string;
    password: string;
  }) => Promise<void>;
  fetchMe: () => Promise<boolean>;
  checkOnboardingNeeded: () => Promise<boolean>;
  logout: () => void;
  clearError: () => void;
  hydrateFromStorage: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function persistAuth(token: string, user: AuthUser, company: AuthCompany) {
  localStorage.setItem('dp_token', token);
  localStorage.setItem('dp_user', JSON.stringify(user));
  localStorage.setItem('dp_company', JSON.stringify(company));
}

function clearPersistedAuth() {
  localStorage.removeItem('dp_token');
  localStorage.removeItem('dp_user');
  localStorage.removeItem('dp_company');
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  company: null,
  isLoading: false,
  error: null,

  hydrateFromStorage: () => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('dp_token');
    if (!token) return;
    try {
      const user = JSON.parse(localStorage.getItem('dp_user') ?? 'null');
      const company = JSON.parse(localStorage.getItem('dp_company') ?? 'null');
      if (user && company) {
        set({ token, user, company });
      }
    } catch {
      clearPersistedAuth();
    }
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const res = await apiPost<LoginResponse>(AUTH.login, { email, password });
      persistAuth(res.access_token, res.user, res.company);
      set({ token: res.access_token, user: res.user, company: res.company, isLoading: false });
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Login failed';
      set({ isLoading: false, error: msg });
      throw err;
    }
  },

  register: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const res = await apiPost<LoginResponse>(AUTH.register, data);
      persistAuth(res.access_token, res.user, res.company);
      set({ token: res.access_token, user: res.user, company: res.company, isLoading: false });
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Registration failed';
      set({ isLoading: false, error: msg });
      throw err;
    }
  },

  join: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const res = await apiPost<LoginResponse>(AUTH.join, data);
      persistAuth(res.access_token, res.user, res.company);
      set({ token: res.access_token, user: res.user, company: res.company, isLoading: false });
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Join failed';
      set({ isLoading: false, error: msg });
      throw err;
    }
  },

  fetchMe: async () => {
    const token = get().token ?? localStorage.getItem('dp_token');
    if (!token) return false;
    try {
      const res = await apiGet<MeResponse>(AUTH.me);
      persistAuth(token, res.user, res.company);
      set({ token, user: res.user, company: res.company });
      return true;
    } catch {
      clearPersistedAuth();
      set({ token: null, user: null, company: null });
      return false;
    }
  },

  checkOnboardingNeeded: async () => {
    const company = get().company;
    if (!company?.slug) return true;
    try {
      const profile = await apiGet<CompanyProfile>(COMPANIES.profile(company.slug));
      return !profile.has_research;
    } catch {
      return true;
    }
  },

  logout: () => {
    clearPersistedAuth();
    set({ token: null, user: null, company: null, error: null });
  },

  clearError: () => set({ error: null }),
}));
