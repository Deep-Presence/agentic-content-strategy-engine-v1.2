'use client';

import { Badge } from '@/components/ui';
import { Clock } from 'lucide-react';

interface ActivityItem {
  id: string;
  message: string;
  timestamp: string;
  type: 'pipeline' | 'content' | 'citation' | 'system';
}

const DEMO_ACTIVITY: ActivityItem[] = [
  { id: '1', message: 'Pipeline completed — 6 deliverables generated for Lovable', timestamp: '2 hours ago', type: 'pipeline' },
  { id: '2', message: 'Brief-001 "International Equity Grants" moved to enrichment stage', timestamp: '3 hours ago', type: 'content' },
  { id: '3', message: 'New citation detected on Perplexity for "AI app builder"', timestamp: '4 hours ago', type: 'citation' },
  { id: '4', message: 'Voice Style Guide v1 generated — 3 registers, 42 lexicon entries', timestamp: '5 hours ago', type: 'content' },
  { id: '5', message: 'Gap analysis: 12 new significant gaps identified in "developer tools" cluster', timestamp: '6 hours ago', type: 'system' },
  { id: '6', message: 'Audience persona "Marcus — Technical Evaluator" created', timestamp: '7 hours ago', type: 'content' },
  { id: '7', message: 'Citation lost on ChatGPT for "no-code platform comparison"', timestamp: '9 hours ago', type: 'citation' },
  { id: '8', message: 'Site audit completed — AEO readiness score: 42/100', timestamp: '10 hours ago', type: 'system' },
];

const TYPE_VARIANT: Record<string, 'info' | 'success' | 'warning' | 'neutral'> = {
  pipeline: 'success',
  content: 'info',
  citation: 'warning',
  system: 'neutral',
};

export function RecentActivity() {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Clock size={16} strokeWidth={1.5} className="text-text-secondary" />
        <h2 className="text-[18px] font-semibold text-text-primary">Recent Activity</h2>
      </div>
      <div className="border border-border rounded-md overflow-hidden">
        {DEMO_ACTIVITY.map((item, i) => (
          <div
            key={item.id}
            className={`flex items-center gap-3 px-3.5 py-3 bg-surface ${
              i < DEMO_ACTIVITY.length - 1 ? 'border-b border-border' : ''
            }`}
          >
            <Badge variant={TYPE_VARIANT[item.type]}>{item.type}</Badge>
            <p className="flex-1 text-[13px] text-text-primary leading-[1.5]">{item.message}</p>
            <span className="text-[12px] text-text-tertiary flex-shrink-0">{item.timestamp}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
