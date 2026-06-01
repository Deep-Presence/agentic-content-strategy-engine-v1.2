'use client';

/**
 * AuthProvider — root auth initializer.
 * No localStorage, no storage events — token is httpOnly cookie.
 * Cross-tab sync via BroadcastChannel only.
 * Session expiry from store's sessionExpiresAt (set by BFF).
 */

import { useEffect, useRef } from 'react';
import { useAuthStore, type AuthState } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { AUTH_CHANNEL, SESSION_EXPIRY_WARNING_MS } from '@/lib/auth/constants';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const initialized = useRef(false);
  const expiryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Initialize auth on mount
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      void (async () => {
        await useAuthStore.getState().initialize();
        const authState = useAuthStore.getState();
        if (authState.user) {
          await useWorkspaceStore.getState().fetchWorkspaces();
        }
      })();
    }
  }, []);

  // Cross-tab sync: BroadcastChannel only (no storage event — no localStorage)
  useEffect(() => {
    let bc: BroadcastChannel | null = null;
    if (typeof BroadcastChannel !== 'undefined') {
      bc = new BroadcastChannel(AUTH_CHANNEL);
      bc.onmessage = (event: MessageEvent) => {
        const { type } = event.data ?? {};
        if (type === 'logout') {
          useAuthStore.setState({ user: null, company: null, sessionExpiresAt: null });
          useWorkspaceStore.getState().reset();
          window.location.href = '/login';
        } else if (type === 'login') {
          void (async () => {
            await useAuthStore.getState().initialize();
            await useWorkspaceStore.getState().fetchWorkspaces();
          })();
        }
      };
    }
    return () => {
      bc?.close();
    };
  }, []);

  // Session expiry warning timer
  useEffect(() => {
    const unsubscribe = useAuthStore.subscribe((state: AuthState) => {
      if (expiryTimerRef.current) {
        clearTimeout(expiryTimerRef.current);
        expiryTimerRef.current = null;
      }

      if (!state.sessionExpiresAt) return;

      const expiresAt = new Date(state.sessionExpiresAt).getTime();
      if (isNaN(expiresAt)) return;

      const warningAt = expiresAt - SESSION_EXPIRY_WARNING_MS;
      const delay = warningAt - Date.now();

      if (delay > 0) {
        expiryTimerRef.current = setTimeout(() => {
          if (useAuthStore.getState().user) {
            console.warn('[Auth] Session will expire in 30 minutes. Please save your work.');
          }
        }, delay);
      }
    });

    return () => {
      unsubscribe();
      if (expiryTimerRef.current) clearTimeout(expiryTimerRef.current);
    };
  }, []);

  return <>{children}</>;
}
