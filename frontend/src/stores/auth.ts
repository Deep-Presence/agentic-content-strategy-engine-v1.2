/**
 * Zustand auth store — no token in client state.
 * Token lives ONLY in httpOnly cookie (managed by BFF).
 */

import { create } from 'zustand';
import { authApi } from '@/lib/api-client';
import { AUTH_CHANNEL } from '@/lib/auth/constants';
import type {
  AuthUser,
  AuthCompany,
  LoginPayload,
  RegisterPayload,
  JoinPayload,
} from '@/lib/auth/types';

// ── State interface ──────────────────────────────────────

export interface AuthState {
  user: AuthUser | null;
  company: AuthCompany | null;
  sessionExpiresAt: string | null; // ISO8601
  isInitialized: boolean;
  isLoading: boolean;

  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  join: (payload: JoinPayload) => Promise<void>;
  initialize: () => Promise<void>;
  logout: () => void;
}

// ── BroadcastChannel ─────────────────────────────────────

let channel: BroadcastChannel | null = null;

function getChannel(): BroadcastChannel | null {
  if (typeof window === 'undefined') return null;
  if (typeof BroadcastChannel === 'undefined') return null;
  if (!channel) channel = new BroadcastChannel(AUTH_CHANNEL);
  return channel;
}

function broadcast(type: 'login' | 'logout'): void {
  try {
    getChannel()?.postMessage({ type });
  } catch {
    // non-critical
  }
}

// ── Store ────────────────────────────────────────────────

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  company: null,
  sessionExpiresAt: null,
  isInitialized: false,
  isLoading: false,

  login: async (payload) => {
    set({ isLoading: true });
    try {
      const res = await authApi.login(payload);
      set({
        user: res.user,
        company: res.company,
        sessionExpiresAt: res.session_expires_at,
        isInitialized: true,
      });
      broadcast('login');
    } finally {
      set({ isLoading: false });
    }
  },

  register: async (payload) => {
    set({ isLoading: true });
    try {
      const res = await authApi.register(payload);
      set({
        user: res.user,
        company: res.company,
        sessionExpiresAt: res.session_expires_at,
        isInitialized: true,
      });
      broadcast('login');
    } finally {
      set({ isLoading: false });
    }
  },

  join: async (payload) => {
    set({ isLoading: true });
    try {
      const res = await authApi.join(payload);
      set({
        user: res.user,
        company: res.company,
        sessionExpiresAt: res.session_expires_at,
        isInitialized: true,
      });
      broadcast('login');
    } finally {
      set({ isLoading: false });
    }
  },

  initialize: async () => {
    set({ isLoading: true });
    try {
      const data = await authApi.me();
      set({
        user: data.user,
        company: data.company,
        sessionExpiresAt: data.session_expires_at,
        isInitialized: true,
        isLoading: false,
      });
    } catch {
      set({
        user: null,
        company: null,
        sessionExpiresAt: null,
        isInitialized: true,
        isLoading: false,
      });
    }
  },

  logout: () => {
    authApi.logout().catch(() => {}); // fire-and-forget, clears httpOnly cookie
    set({ user: null, company: null, sessionExpiresAt: null });
    broadcast('logout');
  },
}));
