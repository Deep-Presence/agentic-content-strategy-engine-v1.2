'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { ProgressBar } from '@/components/ui';
import { Check } from 'lucide-react';

const PHASES = [
  'Site Audit',
  'Knowledge Base',
  'Gap Analysis',
  'Topic Discovery',
  'Voice Style Guide',
  'Audience Personas',
];

const PHASE_COMPLETE_TIMES = [10, 20, 35, 45, 52, 58];

const FEED_MESSAGES = [
  'Crawling lovable.dev... 847 pages discovered',
  'Analyzing page structure and metadata',
  'Checking robots.txt and bot access policies',
  'Scoring technical SEO dimensions',
  'Running AEO readiness assessment',
  'Extracting structured data from key pages',
  'Building company overview document',
  'Analyzing brand perception signals',
  'Scanning competitor landscape',
  'Aggregating customer review data',
  'Identifying weakness patterns',
  'Synthesizing knowledge base',
  'Querying 4 AI platforms across 99 queries...',
  'Collecting citations from ChatGPT',
  'Collecting citations from Claude',
  'Collecting citations from Perplexity',
  'Collecting citations from Gemini',
  'Computing embedding similarities',
  'Analyzing 1,816 citations...',
  'Classifying query gaps vs. wins',
  'Clustering topics by semantic similarity',
  'Identifying content opportunities',
  'Mapping coverage gaps',
  'Generating topic priority scores',
  'Analyzing voice patterns from top-cited pages',
  'Extracting stylistic registers',
  'Building lexicon recommendations',
  'Generating persona: Marcus — Technical Evaluator',
  'Generating persona: Elena — Growth Leader',
  'Generating persona: Arjun — Developer Builder',
  'Finalizing audience profiles',
  'Computing AI Presence Score...',
  'Pipeline complete — all deliverables generated',
];

interface AnimatedCounterProps {
  target: number;
  duration: number;
  label: string;
}

function AnimatedCounter({ target, duration, label }: AnimatedCounterProps) {
  const [count, setCount] = useState(0);
  const frameRef = useRef<number>(0);
  const startRef = useRef<number>(0);

  useEffect(() => {
    startRef.current = performance.now();
    const animate = (now: number) => {
      const elapsed = now - startRef.current;
      const progress = Math.min(elapsed / (duration * 1000), 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * target));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, duration]);

  return (
    <div className="text-center">
      <p className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary">
        {count.toLocaleString()}
      </p>
      <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary mt-0.5">
        {label}
      </p>
    </div>
  );
}

interface ScreenPipelineProps {
  onComplete: () => void;
}

export function ScreenPipeline({ onComplete }: ScreenPipelineProps) {
  const [progress, setProgress] = useState(0);
  const [feedItems, setFeedItems] = useState<string[]>([]);
  const [completedPhases, setCompletedPhases] = useState<boolean[]>(Array(6).fill(false));
  const feedRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const feedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const phaseTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef(Date.now());
  const feedIndexRef = useRef(0);

  const cleanup = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (feedTimerRef.current) clearInterval(feedTimerRef.current);
    if (phaseTimerRef.current) clearInterval(phaseTimerRef.current);
  }, []);

  useEffect(() => {
    startTimeRef.current = Date.now();

    // Progress bar: 0→100 over 60 seconds
    timerRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      const pct = Math.min((elapsed / 60) * 100, 100);
      setProgress(pct);
      if (pct >= 100) {
        cleanup();
        setTimeout(onComplete, 800);
      }
    }, 200);

    // Feed messages: every ~1.8 seconds
    feedTimerRef.current = setInterval(() => {
      if (feedIndexRef.current < FEED_MESSAGES.length) {
        setFeedItems((prev) => [...prev, FEED_MESSAGES[feedIndexRef.current]]);
        feedIndexRef.current++;
      }
    }, 1800);

    // Phase completion checkmarks
    phaseTimerRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      setCompletedPhases((prev) => {
        const next = [...prev];
        PHASE_COMPLETE_TIMES.forEach((t, i) => {
          if (elapsed >= t) next[i] = true;
        });
        return next;
      });
    }, 500);

    return cleanup;
  }, [onComplete, cleanup]);

  // Auto-scroll feed
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [feedItems]);

  const activePhaseIndex = completedPhases.filter(Boolean).length;

  return (
    <div className="max-w-[640px] mx-auto">
      <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
        Analyzing your brand
      </h1>
      <p className="text-[14px] text-text-secondary mb-6 leading-[1.6]">
        Running deep analysis pipeline. This takes about a minute.
      </p>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[13px] font-medium text-text-secondary">Overall progress</span>
          <span className="text-[13px] font-mono text-text-tertiary">{Math.round(progress)}%</span>
        </div>
        <ProgressBar value={progress} className="h-[8px]" />
      </div>

      {/* Phase chips */}
      <div className="flex flex-wrap gap-2 mb-6">
        {PHASES.map((phase, i) => {
          const isActive = i === activePhaseIndex;
          const isComplete = completedPhases[i];
          return (
            <div
              key={phase}
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
              {phase}
            </div>
          );
        })}
      </div>

      {/* Stats counters */}
      <div className="grid grid-cols-4 gap-[1px] bg-border rounded-sm overflow-hidden mb-6">
        <div className="bg-bg px-3 py-4">
          <AnimatedCounter target={847} duration={55} label="Pages" />
        </div>
        <div className="bg-bg px-3 py-4">
          <AnimatedCounter target={1816} duration={55} label="Citations" />
        </div>
        <div className="bg-bg px-3 py-4">
          <AnimatedCounter target={99} duration={45} label="Topics" />
        </div>
        <div className="bg-bg px-3 py-4">
          <AnimatedCounter target={9} duration={35} label="Clusters" />
        </div>
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
          {feedItems.length < FEED_MESSAGES.length && (
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
