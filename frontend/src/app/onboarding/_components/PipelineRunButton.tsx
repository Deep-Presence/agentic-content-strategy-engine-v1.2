'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Play, Loader2, Check, AlertCircle, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { apiPost } from '@/lib/api/client';

type PipelineStatus = 'idle' | 'starting' | 'running' | 'done' | 'error';

interface PipelineRunButtonProps {
  label: string;
  endpoint: string;
  payload: Record<string, unknown>;
  disabled?: boolean;
}

export function PipelineRunButton({ label, endpoint, payload, disabled }: PipelineRunButtonProps) {
  const [status, setStatus] = useState<PipelineStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleRun = useCallback(async () => {
    if (status === 'starting' || status === 'running') return;
    setStatus('starting');
    setError(null);

    try {
      await apiPost<{ run_id: string }>(endpoint, payload);
      if (!mountedRef.current) return;
      setStatus('running');
      timerRef.current = setTimeout(() => {
        if (mountedRef.current) setStatus('done');
      }, 2000);
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err instanceof Error ? err.message : 'Failed to start';
      setError(msg);
      setStatus('error');
    }
  }, [endpoint, payload, status]);

  if (status === 'idle' || status === 'error') {
    return (
      <div className="flex items-center gap-1.5">
        {status === 'error' && (
          <span className="text-[11px] text-error truncate max-w-[100px]" title={error ?? ''}>
            <AlertCircle size={12} className="inline mr-0.5" />
            Failed
          </span>
        )}
        <button
          onClick={handleRun}
          disabled={disabled}
          title={`Run ${label} individually`}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-sm border border-border text-[11px] font-medium text-text-secondary hover:border-accent hover:text-accent hover:bg-accent-subtle transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          <Play size={11} strokeWidth={2} />
          Run
        </button>
      </div>
    );
  }

  if (status === 'starting') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] font-medium text-text-tertiary">
        <Loader2 size={12} className="animate-spin" />
        Starting...
      </span>
    );
  }

  if (status === 'running') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] font-medium text-accent">
        <Loader2 size={12} className="animate-spin" />
        Running
      </span>
    );
  }

  // done
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] font-medium text-success">
      <Check size={12} strokeWidth={2} />
      Started
      <Link href="/" title="View in dashboard" className="text-text-tertiary hover:text-accent">
        <ExternalLink size={10} />
      </Link>
    </span>
  );
}
