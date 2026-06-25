'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertCircle, Check, Loader2, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { Badge, Button, ProgressBar } from '@/components/ui';
import { useStreamToken } from '@/hooks/useStreamToken';
import { ApiError } from '@/lib/api-client';
import {
  fetchOnboardingStatus,
  startOnboarding,
  type OnboardingStartRequestAPI,
} from '../_lib/api';

const PIPELINE_ORDER = ['site_audit', 'kb', 'ap', 'vsg', 'ga', 'td'];

const PIPELINE_LABELS: Record<string, string> = {
  site_audit: 'Site Audit',
  kb: 'Knowledge Base',
  ap: 'Audience Personas',
  vsg: 'Voice Style Guide',
  ga: 'Gap Analysis',
  td: 'Topic Discovery',
};

const PHASE_LABELS: Record<string, string> = {
  phase_a: 'Phase A',
  phase_b: 'Phase B',
  phase_c: 'Phase C',
};

const SSE_EVENTS = [
  'onboarding_start',
  'onboarding_phase_start',
  'onboarding_phase_complete',
  'onboarding_phase_skipped',
  'onboarding_sub_start',
  'onboarding_sub_complete',
  'onboarding_sub_failed',
  'onboarding_sa_progress',
  'progress',
  'completed',
  'failed',
];

type PipelineState = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
type RunState = 'idle' | 'starting' | 'running' | 'completed' | 'failed';

interface FeedItem {
  id: number;
  message: string;
  variant: 'info' | 'success' | 'error';
}

interface ScreenPipelineProps {
  workspaceSlug: string;
  startPayload: OnboardingStartRequestAPI;
  onComplete: () => void;
  onBackToConfig: () => void;
}

function storageKey(workspaceSlug: string): string {
  return `dp_onboarding_task:${workspaceSlug}`;
}

function initialPipelineStates(): Record<string, PipelineState> {
  return Object.fromEntries(PIPELINE_ORDER.map((key) => [key, 'pending']));
}

function readablePipeline(key: string): string {
  return PIPELINE_LABELS[key] ?? key;
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    const detail = (err as unknown as { detail?: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === 'string') return message;
    }
  }
  return fallback;
}

export function ScreenPipeline({
  workspaceSlug,
  startPayload,
  onComplete,
  onBackToConfig,
}: ScreenPipelineProps) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState>('idle');
  const [progress, setProgress] = useState(0);
  const [activePhase, setActivePhase] = useState<string | null>(null);
  const [pipelineStates, setPipelineStates] = useState<Record<string, PipelineState>>(
    initialPipelineStates,
  );
  const [feedItems, setFeedItems] = useState<FeedItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [launchNonce, setLaunchNonce] = useState(0);
  const terminalHandledRef = useRef(false);
  const feedIdRef = useRef(0);
  const sourceRef = useRef<EventSource | null>(null);
  const payloadJson = useMemo(() => JSON.stringify(startPayload), [startPayload]);
  const { acquire } = useStreamToken(taskId ?? '');

  const appendFeed = useCallback((message: string, variant: FeedItem['variant'] = 'info') => {
    feedIdRef.current += 1;
    setFeedItems((current) => [
      ...current.slice(-60),
      { id: feedIdRef.current, message, variant },
    ]);
  }, []);

  const finishCompleted = useCallback(() => {
    if (terminalHandledRef.current) return;
    terminalHandledRef.current = true;
    setRunState('completed');
    setProgress(100);
    setPipelineStates((current) => {
      const next = { ...current };
      for (const key of PIPELINE_ORDER) {
        if (next[key] === 'pending' || next[key] === 'running') next[key] = 'completed';
      }
      return next;
    });
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem(storageKey(workspaceSlug));
    }
    setTimeout(onComplete, 900);
  }, [onComplete, workspaceSlug]);

  const failRun = useCallback((message: string) => {
    if (terminalHandledRef.current) return;
    terminalHandledRef.current = true;
    setRunState('failed');
    setError(message);
    appendFeed(message, 'error');
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem(storageKey(workspaceSlug));
    }
  }, [appendFeed, workspaceSlug]);

  const handleEvent = useCallback((eventType: string, data: Record<string, unknown>) => {
    switch (eventType) {
      case 'onboarding_start': {
        setRunState('running');
        appendFeed('Onboarding pipeline started');
        break;
      }
      case 'onboarding_phase_start': {
        const phase = String(data.phase ?? '');
        setActivePhase(phase);
        appendFeed(`${PHASE_LABELS[phase] ?? phase} started`);
        break;
      }
      case 'onboarding_phase_complete': {
        const phase = String(data.phase ?? '');
        appendFeed(`${PHASE_LABELS[phase] ?? phase} complete`, 'success');
        break;
      }
      case 'onboarding_phase_skipped': {
        const phase = String(data.phase ?? '');
        appendFeed(`${PHASE_LABELS[phase] ?? phase} skipped`);
        break;
      }
      case 'onboarding_sub_start': {
        const pipeline = String(data.pipeline ?? '');
        setPipelineStates((current) => ({ ...current, [pipeline]: 'running' }));
        appendFeed(`${readablePipeline(pipeline)} started`);
        break;
      }
      case 'onboarding_sub_complete': {
        const pipeline = String(data.pipeline ?? '');
        setPipelineStates((current) => ({ ...current, [pipeline]: 'completed' }));
        appendFeed(`${readablePipeline(pipeline)} complete`, 'success');
        break;
      }
      case 'onboarding_sub_failed': {
        const pipeline = String(data.pipeline ?? '');
        const message = typeof data.error === 'string' ? data.error : `${readablePipeline(pipeline)} failed`;
        setPipelineStates((current) => ({ ...current, [pipeline]: 'failed' }));
        appendFeed(message, 'error');
        break;
      }
      case 'onboarding_sa_progress': {
        if (typeof data.message === 'string') appendFeed(data.message);
        break;
      }
      case 'progress': {
        const pct = Number(data.progress_pct ?? 0);
        if (Number.isFinite(pct)) setProgress(Math.max(0, Math.min(100, pct)));
        if (typeof data.message === 'string') appendFeed(data.message);
        break;
      }
      case 'completed': {
        appendFeed('Onboarding pipeline complete', 'success');
        finishCompleted();
        break;
      }
      case 'failed': {
        failRun(typeof data.error === 'string' ? data.error : 'Onboarding pipeline failed');
        break;
      }
      default:
        break;
    }
  }, [appendFeed, failRun, finishCompleted]);

  useEffect(() => {
    if (!workspaceSlug) return;
    terminalHandledRef.current = false;
    setError(null);
    setRunState('starting');
    setProgress(0);
    setPipelineStates(initialPipelineStates());
    setFeedItems([]);

    if (typeof window !== 'undefined') {
      const existingTaskId = window.sessionStorage.getItem(storageKey(workspaceSlug));
      if (existingTaskId) {
        setTaskId(existingTaskId);
        setRunState('running');
        appendFeed('Resuming existing onboarding run');
        return;
      }
    }

    let cancelled = false;
    const parsedPayload = JSON.parse(payloadJson) as OnboardingStartRequestAPI;

    async function launch() {
      try {
        const response = await startOnboarding({
          ...parsedPayload,
          workspace_slug: workspaceSlug,
        });
        if (cancelled) return;
        setTaskId(response.run_id);
        setRunState('running');
        appendFeed('Background onboarding task queued');
        if (typeof window !== 'undefined') {
          window.sessionStorage.setItem(storageKey(workspaceSlug), response.run_id);
        }
      } catch (err) {
        if (cancelled) return;
        failRun(errorMessage(err, 'Failed to start onboarding'));
      }
    }

    void launch();
    return () => {
      cancelled = true;
    };
  }, [appendFeed, failRun, launchNonce, payloadJson, workspaceSlug]);

  useEffect(() => {
    if (!taskId || terminalHandledRef.current) return;

    const controller = new AbortController();
    let cancelled = false;

    async function poll() {
      try {
        const status = await fetchOnboardingStatus(taskId!, controller.signal);
        if (cancelled) return;
        if (status.current_step) setActivePhase(status.current_step);
        if (status.status === 'completed') {
          finishCompleted();
        } else if (status.status === 'failed' || status.status === 'failed_restart') {
          failRun(status.error || 'Onboarding pipeline failed');
        }
      } catch {
        // SSE is primary; polling is a best-effort fallback.
      }
    }

    void poll();
    const interval = window.setInterval(() => void poll(), 5000);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(interval);
    };
  }, [failRun, finishCompleted, taskId]);

  useEffect(() => {
    if (!taskId || terminalHandledRef.current) return;

    let cancelled = false;

    async function connect() {
      const token = await acquire();
      if (cancelled || !token) return;

      const source = new EventSource(
        `/api/v1/tasks/${taskId}/events?stream_token=${encodeURIComponent(token)}`,
      );
      sourceRef.current = source;

      const listener = (event: Event) => {
        try {
          const message = event as MessageEvent<string>;
          const data = JSON.parse(message.data) as Record<string, unknown>;
          handleEvent(event.type, data);
        } catch {
          // Ignore heartbeats or malformed events.
        }
      };

      for (const name of SSE_EVENTS) {
        source.addEventListener(name, listener);
      }
      source.onopen = () => setIsConnected(true);
      source.onerror = () => setIsConnected(false);
    }

    void connect();

    return () => {
      cancelled = true;
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
      setIsConnected(false);
    };
  }, [acquire, handleEvent, taskId]);

  const retry = () => {
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem(storageKey(workspaceSlug));
    }
    terminalHandledRef.current = false;
    setTaskId(null);
    setRunState('idle');
    setLaunchNonce((value) => value + 1);
  };

  return (
    <div className="mx-auto w-full max-w-[760px]">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
            Analyzing your brand
          </h1>
          <p className="max-w-[560px] text-[14px] text-text-secondary leading-[1.6]">
            Running the onboarding pipeline in the background for workspace{' '}
            <span className="font-mono text-[12px] text-text-primary">{workspaceSlug}</span>.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Badge variant="success"><Wifi size={12} strokeWidth={1.5} /> Live</Badge>
          ) : (
            <Badge variant="neutral"><WifiOff size={12} strokeWidth={1.5} /> Polling</Badge>
          )}
          {runState === 'starting' && <Badge variant="info">Starting</Badge>}
          {runState === 'failed' && <Badge variant="error">Failed</Badge>}
        </div>
      </div>

      <div className="mb-5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[13px] font-medium text-text-secondary">
            {activePhase ? PHASE_LABELS[activePhase] ?? activePhase : 'Overall progress'}
          </span>
          <span className="font-mono text-[13px] text-text-tertiary">{Math.round(progress)}%</span>
        </div>
        <ProgressBar value={progress} className="h-[8px]" />
      </div>

      <div className="mb-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {PIPELINE_ORDER.map((pipeline) => {
          const state = pipelineStates[pipeline] ?? 'pending';
          const isComplete = state === 'completed';
          const isRunning = state === 'running';
          const isFailed = state === 'failed';
          return (
            <div
              key={pipeline}
              className={[
                'flex min-h-[54px] items-center gap-2 rounded-sm border px-3 py-2 transition-colors',
                isComplete ? 'border-success bg-success-subtle text-success' : '',
                isRunning ? 'border-accent bg-accent-subtle text-accent' : '',
                isFailed ? 'border-error bg-error-subtle text-error' : '',
                state === 'pending' ? 'border-border bg-surface text-text-secondary' : '',
              ].join(' ')}
            >
              {isComplete && <Check size={14} strokeWidth={2} />}
              {isRunning && <Loader2 size={14} strokeWidth={1.5} className="animate-spin" />}
              {isFailed && <AlertCircle size={14} strokeWidth={1.5} />}
              {!isComplete && !isRunning && !isFailed && (
                <span className="h-2 w-2 rounded-full bg-border-strong" />
              )}
              <span className="text-[13px] font-medium">{readablePipeline(pipeline)}</span>
            </div>
          );
        })}
      </div>

      {error && (
        <div className="mb-5 rounded-sm border border-error bg-error-subtle px-3 py-2 text-[13px] text-error">
          <div className="flex items-start gap-2">
            <AlertCircle size={14} strokeWidth={1.5} className="mt-[2px] flex-shrink-0" />
            <span>{error}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={onBackToConfig}>
              Model setup
            </Button>
            <Button size="sm" onClick={retry}>
              <RefreshCw size={12} strokeWidth={1.5} className="mr-1" />
              Retry
            </Button>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-md border border-border">
        <div className="border-b border-border bg-surface px-3 py-2.5">
          <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
            Pipeline Events
          </p>
        </div>
        <div className="h-[260px] overflow-y-auto bg-bg p-3">
          {feedItems.length === 0 && (
            <div className="flex items-center gap-2 text-[13px] text-text-tertiary">
              <Loader2 size={14} strokeWidth={1.5} className="animate-spin" />
              Starting background task...
            </div>
          )}
          <div className="space-y-2">
            {feedItems.map((item, index) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2 }}
                className="flex items-start gap-2.5"
              >
                <span className="mt-[1px] flex-shrink-0 font-mono text-[11px] text-text-tertiary">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span
                  className={[
                    'text-[13px] leading-[1.5]',
                    item.variant === 'success' ? 'text-success' : '',
                    item.variant === 'error' ? 'text-error' : '',
                    item.variant === 'info' ? 'text-text-secondary' : '',
                  ].join(' ')}
                >
                  {item.message}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
