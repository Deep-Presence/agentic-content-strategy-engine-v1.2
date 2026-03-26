'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Button, Badge } from '@/components/ui';
import {
  Search,
  BookOpen,
  BarChart3,
  Compass,
  Mic,
  Users,
} from 'lucide-react';
import { PipelineRunButton } from './PipelineRunButton';
import {
  KNOWLEDGE_BASE,
  AUDIENCE_PERSONA,
  VOICE_STYLE_GUIDE,
  GAP_ANALYSIS,
  TOPIC_DISCOVERY,
} from '@/lib/api/endpoints';
import type { LucideIcon } from 'lucide-react';

interface PipelineEndpoint {
  endpoint: string;
  buildPayload: (companyName: string, domain: string, seedUrls: string[]) => Record<string, unknown>;
}

interface Deliverable {
  icon: LucideIcon;
  title: string;
  description: string;
  time: string;
  /** If set, this deliverable gets an individual "Run" button. */
  pipeline?: PipelineEndpoint;
}

const DELIVERABLES: Deliverable[] = [
  {
    icon: Search,
    title: 'Site Audit',
    description: 'Crawl and score your site for AI readiness',
    time: '~15s',
    // No individual run — site audit is deterministic and fast, always runs with onboarding
  },
  {
    icon: BookOpen,
    title: 'Knowledge Base',
    description: 'Extract brand, competitor, and market data',
    time: '~20s',
    pipeline: {
      endpoint: KNOWLEDGE_BASE.start,
      buildPayload: (companyName, domain) => ({
        company_name: companyName,
        domain,
        express_mode: true,
      }),
    },
  },
  {
    icon: Users,
    title: 'Audience Personas',
    description: 'Generate data-driven audience profiles',
    time: '~10s',
    pipeline: {
      endpoint: AUDIENCE_PERSONA.start,
      buildPayload: (companyName, domain) => ({
        company_name: companyName,
        domain,
        auto_approve_checkpoints: [1, 2],
      }),
    },
  },
  {
    icon: Mic,
    title: 'Voice Style Guide',
    description: 'Analyze and codify your brand voice',
    time: '~10s',
    pipeline: {
      endpoint: VOICE_STYLE_GUIDE.start,
      buildPayload: (companyName, domain) => ({
        company_name: companyName,
        domain,
        auto_approve_checkpoints: [1],
      }),
    },
  },
  {
    icon: BarChart3,
    title: 'Gap Analysis',
    description: 'Benchmark citations vs. competitors across AI platforms',
    time: '~12s',
    pipeline: {
      endpoint: GAP_ANALYSIS.start,
      buildPayload: (companyName, domain, seedUrls) => ({
        company_name: companyName,
        domain,
        seed_urls: seedUrls,
      }),
    },
  },
  {
    icon: Compass,
    title: 'Topic Discovery',
    description: 'Identify content opportunities from query clusters',
    time: '~8s',
    pipeline: {
      endpoint: TOPIC_DISCOVERY.start,
      buildPayload: (companyName, domain) => ({
        company_name: companyName,
        domain,
        auto_approve_checkpoints: [1, 2, 3],
      }),
    },
  },
];

interface ScreenBriefingProps {
  onStart: () => void;
  companyName: string;
  domain: string;
  seedUrls: string[];
}

export function ScreenBriefing({ onStart, companyName, domain, seedUrls }: ScreenBriefingProps) {
  // Memoize to avoid re-creating payload objects every render
  const pipelinePayloads = useMemo(() => {
    const map = new Map<string, Record<string, unknown>>();
    for (const d of DELIVERABLES) {
      if (d.pipeline) {
        map.set(d.title, d.pipeline.buildPayload(companyName, domain, seedUrls));
      }
    }
    return map;
  }, [companyName, domain, seedUrls]);

  const hasCompanyData = Boolean(companyName && domain);

  return (
    <div className="max-w-[640px] mx-auto">
      <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
        Pipeline briefing
      </h1>
      <p className="text-[14px] text-text-secondary mb-3 leading-[1.6]">
        We&apos;ll generate 6 deliverables for your brand. Here&apos;s what to expect.
      </p>
      <p className="text-[12px] text-text-tertiary mb-6 leading-[1.5]">
        Run all pipelines together, or launch individual ones with the <span className="font-semibold text-text-secondary">Run</span> buttons.
      </p>

      <div className="space-y-2">
        {DELIVERABLES.map((d, i) => {
          const Icon = d.icon;
          return (
            <motion.div
              key={d.title}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.12, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="flex items-center gap-3 bg-surface border border-border rounded-md p-3.5 hover:border-border-strong transition-[border-color] duration-150"
            >
              <div className="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-sm bg-accent-subtle text-accent">
                <Icon size={18} strokeWidth={1.5} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-medium text-text-primary">{d.title}</p>
                <p className="text-[13px] text-text-secondary leading-[1.5]">{d.description}</p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Badge variant="neutral">{d.time}</Badge>
                {d.pipeline && (
                  <PipelineRunButton
                    label={d.title}
                    endpoint={d.pipeline.endpoint}
                    payload={pipelinePayloads.get(d.title) ?? {}}
                    disabled={!hasCompanyData}
                  />
                )}
              </div>
            </motion.div>
          );
        })}
      </div>

      <div className="mt-6 flex items-center gap-3">
        <Button variant="primary" className="flex-1 h-[36px] text-[14px]" onClick={onStart}>
          Start All Pipelines &rarr;
        </Button>
      </div>
    </div>
  );
}
