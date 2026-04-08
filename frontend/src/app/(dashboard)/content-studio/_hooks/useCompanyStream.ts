'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type { CompanyNotification } from '../_lib/types';

const DEBOUNCE_MS = 300;

export interface CompanyStreamCallbacks {
  /** Called (debounced) when one or more cards change status. Trigger a re-poll. */
  onStateChanged: () => void;
  /** Called for user-facing notifications (HITL review, completion, error). */
  onNotification?: (data: CompanyNotification) => void;
}

/**
 * Single EventSource subscription to the company-wide SSE stream.
 *
 * On `state_changed` events → debounced call to `onStateChanged` (coalesces
 * rapid events into one re-poll). On `notification` events → immediate
 * dispatch to `onNotification`.
 *
 * Auth is transparent: EventSource sends the httpOnly cookie through the
 * BFF catch-all proxy, which injects the Bearer token.
 */
export function useCompanyStream(
  companySlug: string | null,
  callbacks: CompanyStreamCallbacks,
): { isConnected: boolean } {
  const [isConnected, setIsConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const disconnect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
      setIsConnected(false);
    }
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!companySlug) {
      disconnect();
      return;
    }

    const url = `/api/v1/companies/${encodeURIComponent(companySlug)}/stream`;
    const source = new EventSource(url);
    sourceRef.current = source;

    source.addEventListener('state_changed', (ev: MessageEvent) => {
      console.info(`[useCompanyStream] state_changed @${new Date().toISOString()}`, ev.data ? JSON.parse(ev.data) : '(no data)');
      // Debounce: coalesce rapid state_changed events into one callback
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        callbacksRef.current.onStateChanged();
      }, DEBOUNCE_MS);
    });

    source.addEventListener('notification', (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as CompanyNotification;
        callbacksRef.current.onNotification?.(data);
      } catch {
        // Non-JSON or malformed — ignore
      }
    });

    source.onopen = () => {
      console.info(`[useCompanyStream] connected @${new Date().toISOString()} url=${url}`);
      setIsConnected(true);
      // Re-poll on reconnect to catch anything missed while disconnected
      callbacksRef.current.onStateChanged();
    };

    source.onerror = () => {
      console.info(`[useCompanyStream] error/disconnect @${new Date().toISOString()} readyState=${source.readyState}`);
      setIsConnected(false);
      // EventSource auto-reconnects — no manual retry needed
    };

    return () => {
      disconnect();
    };
  }, [companySlug, disconnect]);

  return { isConnected };
}
