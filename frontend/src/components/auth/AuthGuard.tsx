'use client';

/**
 * AuthGuard — client-side auth gate for protected routes.
 *
 * State machine:
 *   !isInitialized          → loading skeleton
 *   isInitialized && !auth  → redirect to /login
 *   isInitialized && auth   → render children
 */

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { fetchWorkspaceModelConfig } from '@/lib/model-config';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { activeWorkspaceSlug, isAuthenticated, isInitialized } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [isCheckingModelConfig, setIsCheckingModelConfig] = useState(false);

  useEffect(() => {
    if (isInitialized && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isInitialized, isAuthenticated, router]);

  useEffect(() => {
    if (!isInitialized || !isAuthenticated || !activeWorkspaceSlug) return;
    if (pathname === '/onboarding' || pathname.startsWith('/settings')) return;

    let cancelled = false;
    setIsCheckingModelConfig(true);

    fetchWorkspaceModelConfig(activeWorkspaceSlug)
      .then((view) => {
        if (cancelled) return;
        const credential = view.credential;
        const active =
          credential.configured &&
          (credential.status === 'active' || credential.status === 'valid');
        if (!active) {
          router.replace('/onboarding');
        }
      })
      .catch(() => {
        // Do not block the app on transient model-config read errors.
      })
      .finally(() => {
        if (!cancelled) setIsCheckingModelConfig(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeWorkspaceSlug, isAuthenticated, isInitialized, pathname, router]);

  if (!isInitialized || isCheckingModelConfig) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent" />
          <span className="text-[13px] text-text-secondary">Loading...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
