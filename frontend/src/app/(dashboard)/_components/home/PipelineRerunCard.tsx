'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Play,
  Loader2,
  Check,
  AlertCircle,
  BookOpen,
  Users,
  Pen,
  Search,
  Lightbulb,
} from 'lucide-react';
import { apiPost } from '@/lib/api/client';
import {
  KNOWLEDGE_BASE,
  AUDIENCE_PERSONA,
  VOICE_STYLE_GUIDE,
  GAP_ANALYSIS,
  TOPIC_DISCOVERY,
} from '@/lib/api/endpoints';

type RunStatus = 'idle' | 'starting' | 'running' | 'done' | 'error';

interface PipelineConfig {
  key: string;
  label: string;
  description: string;
  endpoint: string;
  icon: React.ReactNode;
  buildPayload: (companyName: string, domain: string) => Record<string, unknown>;
}

const PIPELINES: PipelineConfig[] = [
  {
    key: 'kb',
    label: 'Knowledge Base',
    description: 'Company research & synthesis',
    endpoint: KNOWLEDGE_BASE.start,
    icon: <BookOpen size={14} strokeWidth={1.5} />,
    buildPayload: (companyName, domain) => ({
      company_name: companyName,
      domain,
      force_rerun: true,
      express_mode: true,
    }),
  },
  {
    key: 'ap',
    label: 'Audience Persona',
    description: 'ICP persona generation',
    endpoint: AUDIENCE_PERSONA.start,
    icon: <Users size={14} strokeWidth={1.5} />,
    buildPayload: (companyName, domain) => ({
      company_name: companyName,
      domain,
      force_rerun: true,
      auto_approve_checkpoints: [1, 2],
    }),
  },
  {
    key: 'vsg',
    label: 'Voice Style Guide',
    description: 'Brand voice & tone synthesis',
    endpoint: VOICE_STYLE_GUIDE.start,
    icon: <Pen size={14} strokeWidth={1.5} />,
    buildPayload: (companyName, domain) => ({
      company_name: companyName,
      domain,
      force_rerun: true,
      auto_approve_checkpoints: [1],
    }),
  },
  {
    key: 'gap',
    label: 'Gap Analysis',
    description: 'AI citation gap discovery',
    endpoint: GAP_ANALYSIS.start,
    icon: <Search size={14} strokeWidth={1.5} />,
    buildPayload: (companyName, domain) => ({
      company_name: companyName,
      domain,
      force_rerun: true,
    }),
  },
  {
    key: 'td',
    label: 'Topic Discovery',
    description: 'Topic generation & CPS scoring',
    endpoint: TOPIC_DISCOVERY.start,
    icon: <Lightbulb size={14} strokeWidth={1.5} />,
    buildPayload: (companyName, domain) => ({
      company_name: companyName,
      domain,
      force_rerun: true,
      auto_approve_checkpoints: [1, 2, 3],
    }),
  },
];

interface PipelineRerunCardProps {
  companyName: string;
  companyDomain: string;
}

export function PipelineRerunCard({ companyName, companyDomain }: PipelineRerunCardProps) {
  const [statuses, setStatuses] = useState<Record<string, RunStatus>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const mountedRef = useRef(true);
  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      Object.values(timersRef.current).forEach(clearTimeout);
    };
  }, []);

  const handleRun = useCallback(
    async (pipeline: PipelineConfig) => {
      const current = statuses[pipeline.key];
      if (current === 'starting' || current === 'running') return;

      setStatuses((prev) => ({ ...prev, [pipeline.key]: 'starting' }));
      setErrors((prev) => {
        const next = { ...prev };
        delete next[pipeline.key];
        return next;
      });

      try {
        await apiPost<{ run_id: string }>(
          pipeline.endpoint,
          pipeline.buildPayload(companyName, companyDomain),
        );
        if (!mountedRef.current) return;
        setStatuses((prev) => ({ ...prev, [pipeline.key]: 'running' }));
        timersRef.current[pipeline.key] = setTimeout(() => {
          if (mountedRef.current) {
            setStatuses((prev) => ({ ...prev, [pipeline.key]: 'done' }));
          }
        }, 3000);
      } catch (err) {
        if (!mountedRef.current) return;
        const msg = err instanceof Error ? err.message : 'Failed to start';
        setErrors((prev) => ({ ...prev, [pipeline.key]: msg }));
        setStatuses((prev) => ({ ...prev, [pipeline.key]: 'error' }));
      }
    },
    [companyName, companyDomain, statuses],
  );

  const disabled = !companyName || !companyDomain;

  return (
    <div className="border border-border rounded-sm bg-bg">
      <div className="px-3 py-2.5 border-b border-border">
        <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          Re-run Pipelines
        </p>
      </div>
      <div className="divide-y divide-border">
        {PIPELINES.map((pipeline) => {
          const status = statuses[pipeline.key] ?? 'idle';
          const error = errors[pipeline.key];

          return (
            <div
              key={pipeline.key}
              className="flex items-center justify-between px-3 py-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-text-tertiary flex-shrink-0">{pipeline.icon}</span>
                <div className="min-w-0">
                  <p className="text-[12px] font-medium text-text-primary truncate">
                    {pipeline.label}
                  </p>
                  <p className="text-[10px] text-text-tertiary truncate">
                    {pipeline.description}
                  </p>
                </div>
              </div>

              <div className="flex-shrink-0 ml-3">
                {(status === 'idle' || status === 'error') && (
                  <div className="flex items-center gap-1.5">
                    {status === 'error' && (
                      <span
                        className="text-[10px] text-error truncate max-w-[80px]"
                        title={error ?? ''}
                      >
                        <AlertCircle size={10} className="inline mr-0.5" />
                        Failed
                      </span>
                    )}
                    <button
                      onClick={() => handleRun(pipeline)}
                      disabled={disabled}
                      title={`Re-run ${pipeline.label}`}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-sm border border-border text-[11px] font-medium text-text-secondary hover:border-accent hover:text-accent hover:bg-accent-subtle transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    >
                      <Play size={10} strokeWidth={2} />
                      Re-run
                    </button>
                  </div>
                )}
                {status === 'starting' && (
                  <span className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] font-medium text-text-tertiary">
                    <Loader2 size={12} className="animate-spin" />
                    Starting...
                  </span>
                )}
                {status === 'running' && (
                  <span className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] font-medium text-accent">
                    <Loader2 size={12} className="animate-spin" />
                    Running
                  </span>
                )}
                {status === 'done' && (
                  <span className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] font-medium text-success">
                    <Check size={12} strokeWidth={2} />
                    Started
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
