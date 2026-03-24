'use client';

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

const DELIVERABLES = [
  { icon: Search, title: 'Site Audit', description: 'Crawl and score your site for AI readiness', time: '~15s' },
  { icon: BookOpen, title: 'Knowledge Base', description: 'Extract brand, competitor, and market data', time: '~20s' },
  { icon: BarChart3, title: 'Gap Analysis', description: 'Benchmark citations vs. competitors across AI platforms', time: '~12s' },
  { icon: Compass, title: 'Topic Discovery', description: 'Identify content opportunities from query clusters', time: '~8s' },
  { icon: Mic, title: 'Voice Style Guide', description: 'Analyze and codify your brand voice', time: '~10s' },
  { icon: Users, title: 'Audience Personas', description: 'Generate data-driven audience profiles', time: '~10s' },
];

interface ScreenBriefingProps {
  onStart: () => void;
}

export function ScreenBriefing({ onStart }: ScreenBriefingProps) {
  return (
    <div className="max-w-[560px] mx-auto">
      <h1 className="font-display text-[24px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
        Pipeline briefing
      </h1>
      <p className="text-[14px] text-text-secondary mb-8 leading-[1.6]">
        We&apos;ll generate 6 deliverables for your brand. Here&apos;s what to expect.
      </p>
      <div className="space-y-2">
        {DELIVERABLES.map((d, i) => {
          const Icon = d.icon;
          return (
            <motion.div
              key={d.title}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.15, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="flex items-center gap-3 bg-surface border border-border rounded-md p-3.5 hover:border-border-strong transition-[border-color] duration-150"
            >
              <div className="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-sm bg-accent-subtle text-accent">
                <Icon size={18} strokeWidth={1.5} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-medium text-text-primary">{d.title}</p>
                <p className="text-[13px] text-text-secondary leading-[1.5]">{d.description}</p>
              </div>
              <Badge variant="neutral">{d.time}</Badge>
            </motion.div>
          );
        })}
      </div>
      <Button variant="primary" className="w-full mt-6 h-[36px] text-[14px]" onClick={onStart}>
        Start Pipeline &rarr;
      </Button>
    </div>
  );
}
