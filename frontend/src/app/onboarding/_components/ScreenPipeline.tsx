'use client';

import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { ProgressBar } from '@/components/ui';
import { Check, AlertCircle } from 'lucide-react';
import { useTaskStream } from '@/lib/hooks/useTaskStream';

// Maps sub-pipeline names to display labels
const PIPELINE_LABELS: Record<string, string> = {
  site_audit: 'Site Audit',
  kb: 'Knowledge Base',
  knowledge_base: 'Knowledge Base',
  ap: 'Audience Personas',
  audience_persona: 'Audience Personas',
  vsg: 'Voice Style Guide',
  voice_style_guide: 'Voice Style Guide',
  ga: 'Gap Analysis',
  gap_analysis: 'Gap Analysis',
  td: 'Topic Discovery',
  topic_discovery: 'Topic Discovery',
};

const PHASE_PIPELINES: Record<string, string[]> = {
  phase_a: ['site_audit', 'kb'],
  phase_b: ['ap'],
  phase_c: ['vsg', 'ga', 'td'],
};

// Ordered phases for display
const PHASES = [
  { id: 'site_audit', label: 'Site Audit' },
  { id: 'kb', label: 'Knowledge Base' },
  { id: 'ap', label: 'Audience Personas' },
  { id: 'vsg', label: 'Voice Style Guide' },
  { id: 'ga', label: 'Gap Analysis' },
  { id: 'td', label: 'Topic Discovery' },
];

interface ScreenPipelineProps {
  taskId: string | null;
  onComplete: () => void;
}

export function ScreenPipeline({ taskId, onComplete }: ScreenPipelineProps) {
  const { status, events, progressPct, error } = useTaskStream(taskId);
  const [feedItems, setFeedItems] = useState<string[]>([]);
  const [completedPipelines, setCompletedPipelines] = useState<Set<string>>(new Set());
  const [activePipelines, setActivePipelines] = useState<Set<string>>(new Set());
  const feedRef = useRef<HTMLDivElement>(null);
  const completedRef = useRef(false);
  const processedRef = useRef(0);

  // Process ALL new SSE events since last render (not just the last one)
  useEffect(() => {
    if (events.length <= processedRef.current) return;

    const newEvents = events.slice(processedRef.current);
    processedRef.current = events.length;

    const newFeedMsgs: string[] = [];

    for (const event of newEvents) {
      const { type, data } = event;
      let feedMsg = '';

      if (type === 'onboarding_sub_start') {
        const pipeline = data.pipeline as string;
        const label = PIPELINE_LABELS[pipeline] ?? pipeline;
        feedMsg = `Starting ${label}...`;
        setActivePipelines((prev) => new Set(prev).add(pipeline));
      } else if (type === 'onboarding_sub_complete') {
        const pipeline = data.pipeline as string;
        const label = PIPELINE_LABELS[pipeline] ?? pipeline;
        const timeS = data.time_s ? ` (${Math.round(data.time_s as number)}s)` : '';
        feedMsg = `${label} completed${timeS}`;
        setCompletedPipelines((prev) => new Set(prev).add(pipeline));
        setActivePipelines((prev) => {
          const next = new Set(prev);
          next.delete(pipeline);
          return next;
        });
      } else if (type === 'onboarding_sub_failed') {
        const pipeline = data.pipeline as string;
        const label = PIPELINE_LABELS[pipeline] ?? pipeline;
        feedMsg = `${label} failed: ${(data.error as string) ?? 'unknown error'}`;
        setActivePipelines((prev) => {
          const next = new Set(prev);
          next.delete(pipeline);
          return next;
        });
      } else if (type === 'onboarding_phase_start') {
        const phase = data.phase as string;
        feedMsg = `Phase ${phase.replace('phase_', '').toUpperCase()} started`;
        const pipelines = PHASE_PIPELINES[phase] ?? [];
        setActivePipelines((prev) => {
          const next = new Set(prev);
          pipelines.forEach((p) => next.add(p));
          return next;
        });
      } else if (type === 'onboarding_phase_complete') {
        const phase = data.phase as string;
        feedMsg = `Phase ${phase.replace('phase_', '').toUpperCase()} completed`;
      } else if (type === 'onboarding_phase_skipped') {
        const phase = data.phase as string;
        feedMsg = `Phase ${phase.replace('phase_', '').toUpperCase()} skipped: ${(data.reason as string) ?? ''}`;
      } else if (type === 'onboarding_sa_progress' && data.message) {
        feedMsg = data.message as string;
      } else if (type === 'progress' && data.message) {
        feedMsg = data.message as string;
      } else if (type === 'log' && data.message) {
        feedMsg = data.message as string;
      } else if (type === 'step_start' && data.step) {
        feedMsg = `Running ${data.step as string}...`;
      } else if (type === 'step_complete' && data.step) {
        feedMsg = `${data.step as string} done`;
      } else if (type === 'onboarding_start') {
        feedMsg = 'Onboarding pipeline started';
      }

      if (feedMsg) {
        newFeedMsgs.push(feedMsg);
      }
    }

    if (newFeedMsgs.length > 0) {
      setFeedItems((prev) => [...prev, ...newFeedMsgs]);
    }
  }, [events]);

  // Auto-scroll feed
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [feedItems]);

  // Transition to complete screen when pipeline finishes
  useEffect(() => {
    if (status === 'completed' && !completedRef.current) {
      completedRef.current = true;
      setTimeout(onComplete, 1500);
    }
  }, [status, onComplete]);

  // Compute progress — use SSE progress_pct or estimate from completed phases
  const displayProgress = progressPct > 0
    ? progressPct
    : Math.round((completedPipelines.size / PHASES.length) * 100);

  return (
    <div className="max-w-[640px] mx-auto">
      <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
        Analyzing your brand
      </h1>
      <p className="text-[14px] text-text-secondary mb-6 leading-[1.6]">
        Running deep analysis pipeline. This may take several minutes.
      </p>

      {/* Error banner */}
      {status === 'error' && (
        <div className="mb-4 flex items-start gap-2 bg-error/10 border border-error/30 text-error text-[13px] rounded-md px-3 py-2">
          <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
          <span>{error ?? 'An error occurred during analysis'}</span>
        </div>
      )}

      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[13px] font-medium text-text-secondary">Overall progress</span>
          <span className="text-[13px] font-mono text-text-tertiary">{Math.round(displayProgress)}%</span>
        </div>
        <ProgressBar value={displayProgress} className="h-[8px]" />
      </div>

      {/* Phase chips */}
      <div className="flex flex-wrap gap-2 mb-6">
        {PHASES.map(({ id, label }) => {
          const isComplete = completedPipelines.has(id);
          const isActive = activePipelines.has(id) && !isComplete;
          return (
            <div
              key={id}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm border text-[12px] font-medium transition-all duration-300 ${
                isComplete
                  ? 'border-success bg-success-subtle text-success'
                  : isActive
                  ? 'border-accent bg-accent-subtle text-accent'
                  : 'border-border bg-surface text-text-tertiary'
              }`}
              style={isActive ? { animation: 'phasePulse 2s ease-in-out infinite' } : undefined}
            >
              {isComplete && <Check size={13} strokeWidth={2} />}
              {label}
            </div>
          );
        })}
      </div>

      {/* Live research feed */}
      <div className="border border-border rounded-md overflow-hidden">
        <div className="px-3 py-2.5 border-b border-border bg-surface">
          <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
            Live Research Feed
          </p>
        </div>
        <div
          ref={feedRef}
          className="h-[220px] overflow-y-auto p-3 space-y-2 bg-bg"
        >
          {feedItems.length === 0 && (status === 'connecting' || status === 'connected') && (
            <div className="flex items-center gap-2 text-text-tertiary">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              <span className="text-[12px]">Connecting to pipeline...</span>
            </div>
          )}
          {feedItems.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="flex items-start gap-2.5"
            >
              <span className="text-[11px] font-mono text-text-tertiary mt-[1px] flex-shrink-0">
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="text-[13px] text-text-secondary leading-[1.5]">{msg}</span>
            </motion.div>
          ))}
          {feedItems.length > 0 && status === 'connected' && (
            <div className="flex items-center gap-2 text-text-tertiary">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              <span className="text-[12px]">Processing...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
