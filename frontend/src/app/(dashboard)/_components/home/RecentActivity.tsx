'use client';

import { Badge, Skeleton } from '@/components/ui';
import { Clock } from 'lucide-react';
import { useApiQuery } from '@/lib/hooks/useApiQuery';
import { BRAND_DATA } from '@/lib/api/endpoints';
import { useAuthStore } from '@/stores/auth';

interface RunHistoryItem {
  id: string;
  pipeline: string;
  company: string;
  status: string;
  started: string;
  duration: string;
  queries: number;
  citations: number;
  spa_score: number;
  steps_completed: number;
  total_steps: number;
}

const PIPELINE_LABELS: Record<string, string> = {
  onboarding: 'Onboarding',
  knowledge_base: 'Knowledge Base',
  audience_persona: 'Audience Personas',
  voice_style_guide: 'Voice Style Guide',
  gap_analysis: 'Gap Analysis',
  content: 'Content',
  topic_discovery: 'Topic Discovery',
  site_audit: 'Site Audit',
  research: 'Research',
};

const STATUS_VARIANT: Record<string, 'success' | 'error' | 'info' | 'warning' | 'neutral'> = {
  completed: 'success',
  running: 'info',
  failed: 'error',
};

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return 'just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function RecentActivity() {
  const slug = useAuthStore((s) => s.company?.slug);
  const { data, isLoading } = useApiQuery<{ runs: RunHistoryItem[]; total: number }>(
    slug ? `${BRAND_DATA.runs(slug)}?limit=10` : null,
  );
  const runs = data?.runs ?? [];

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Clock size={16} strokeWidth={1.5} className="text-text-secondary" />
        <h2 className="text-[18px] font-semibold text-text-primary">Recent Activity</h2>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[44px]" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="border border-border rounded-md p-4">
          <p className="text-[13px] text-text-tertiary text-center">No recent activity</p>
        </div>
      ) : (
        <div className="border border-border rounded-md overflow-hidden">
          {runs.map((run, i) => (
            <div
              key={run.id}
              className={`flex items-center gap-3 px-3.5 py-3 bg-surface ${
                i < runs.length - 1 ? 'border-b border-border' : ''
              }`}
            >
              <Badge variant={STATUS_VARIANT[run.status] ?? 'neutral'}>{run.status}</Badge>
              <p className="flex-1 text-[13px] text-text-primary leading-[1.5]">
                {PIPELINE_LABELS[run.pipeline] ?? run.pipeline}
                {run.duration ? ` — ${run.duration}` : ''}
                {run.queries > 0 ? ` — ${run.queries} queries, ${run.citations} citations` : ''}
              </p>
              <span className="text-[12px] text-text-tertiary flex-shrink-0">
                {timeAgo(run.started)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
