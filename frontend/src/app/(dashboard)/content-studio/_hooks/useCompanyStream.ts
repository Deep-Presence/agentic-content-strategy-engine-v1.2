'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type {
  CompanyNotification,
  CompanyStateChangedData,
  CompanyTopicRunChangedData,
} from '../_lib/types';

const DEBOUNCE_MS = 300;

export interface CompanyStreamCallbacks {
  /** Called (debounced) for coarse compatibility status hints. */
  onStateChanged?: (data: CompanyStateChangedData) => void;
  /** Called immediately with authoritative durable topic-run deltas. */
  onTopicRunChanged?: (data: CompanyTopicRunChangedData) => void;
  /** Called for user-facing notifications (HITL review, completion, error). */
  onNotification?: (data: CompanyNotification) => void;
  /** Called on (re)connect so polling can reconcile anything missed while offline. */
  onReconnect?: () => void;
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
  const queuedStateChangesRef = useRef<CompanyStateChangedData[]>([]);

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
    queuedStateChangesRef.current = [];
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
      let data: CompanyStateChangedData | null = null;
      try {
        data = JSON.parse(ev.data) as CompanyStateChangedData;
      } catch {
        data = null;
      }
      console.info(`[useCompanyStream] state_changed @${new Date().toISOString()}`, data ?? '(no data)');
      if (!data) return;
      queuedStateChangesRef.current.push(data);
      if (debounceRef.current) return;
      debounceRef.current = setTimeout(() => {
        const pending = queuedStateChangesRef.current;
        queuedStateChangesRef.current = [];
        debounceRef.current = null;
        for (const stateChange of pending) {
          callbacksRef.current.onStateChanged?.(stateChange);
        }
      }, DEBOUNCE_MS);
    });

    source.addEventListener('topic_run_changed', (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as CompanyTopicRunChangedData;
        callbacksRef.current.onTopicRunChanged?.(data);
      } catch {
        // malformed payload — ignore
      }
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
      callbacksRef.current.onReconnect?.();
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
