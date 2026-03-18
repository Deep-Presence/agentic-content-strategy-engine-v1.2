'use client';

import { useState } from 'react';
import { TabBar, Skeleton } from '@/components/ui';
import { useAuthStore } from '@/stores/auth';
import { useGapSummary } from '@/lib/hooks/useGapAnalysis';
import { PerformanceTab } from './_components/PerformanceTab';
import { ShareOfVoiceTab } from './_components/ShareOfVoiceTab';
import { CitationsTab } from './_components/CitationsTab';
import { CompetitorsTab } from './_components/CompetitorsTab';
import { BrandHealthTab } from './_components/BrandHealthTab';

const TABS = [
  { id: 'performance', label: 'Performance', closable: false },
  { id: 'sov', label: 'Share of Voice', closable: false },
  { id: 'citations', label: 'Citations', closable: false },
  { id: 'competitors', label: 'Competitors', closable: false },
  { id: 'brand-health', label: 'Brand Health', closable: false },
];

export default function AnalyticsPage() {
  const slug = useAuthStore((s) => s.company?.slug);
  const { data: summary, isLoading, error } = useGapSummary(slug);
  const [activeTab, setActiveTab] = useState('performance');

  // Compute KPI values from API data
  const counts = summary?.classification_counts;
  const totalQueries = summary?.total_queries ?? 0;
  const companyWins = counts?.company_wins ?? 0;
  const citationPresence = totalQueries > 0 ? ((companyWins / totalQueries) * 100).toFixed(1) : '—';
  const spaScore = summary?.spa_score?.t_stat?.toFixed(3) ?? '—';

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="w-full"><Skeleton className="h-[80px] w-full rounded-md" /></div>
        <Skeleton className="h-[36px] w-full rounded-md" />
        <Skeleton className="h-[400px] w-full rounded-md" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-[14px] text-error mb-2">Failed to load analytics data</p>
        <p className="text-[12px] text-text-tertiary">{error.detail}</p>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-[14px] text-text-secondary mb-2">No gap analysis data yet</p>
        <p className="text-[12px] text-text-tertiary">Run a gap analysis pipeline to see performance metrics here.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top KPI Row — Full Width, Big Numbers */}
      <div className="w-full px-0">
        <div className="grid grid-cols-5 bg-surface border border-border rounded-md overflow-hidden">
          <KPICell
            label="SOV %"
            value="—"
            delta="Coming Soon"
          />
          <KPICell
            label="Citation Presence"
            value={`${citationPresence}%`}
            border
          />
          <KPICell
            label="SPA Score"
            value={spaScore}
            border
          />
          <KPICell
            label="Queries Tracked"
            value={String(totalQueries)}
            border
          />
          <KPICell
            label="Total Citations"
            value={String(summary.total_citations)}
            border
          />
        </div>
      </div>

      {/* Tab Bar */}
      <TabBar
        tabs={TABS}
        activeTab={activeTab}
        onTabClick={setActiveTab}
      />

      {/* Tab Content — each tab fetches its own data via slug */}
      <div>
        {activeTab === 'performance' && slug && (
          <PerformanceTab slug={slug} />
        )}
        {activeTab === 'sov' && slug && (
          <ShareOfVoiceTab slug={slug} />
        )}
        {activeTab === 'citations' && slug && (
          <CitationsTab slug={slug} />
        )}
        {activeTab === 'competitors' && slug && (
          <CompetitorsTab slug={slug} />
        )}
        {activeTab === 'brand-health' && slug && (
          <BrandHealthTab slug={slug} />
        )}
      </div>
    </div>
  );
}

/* ── KPI Cell with proper sizing ────────────────────────────────── */
function KPICell({
  label,
  value,
  delta,
  deltaType,
  border,
}: {
  label: string;
  value: string;
  delta?: string;
  deltaType?: 'positive' | 'negative';
  border?: boolean;
}) {
  return (
    <div
      className={`p-4 min-h-[80px] flex flex-col justify-center ${
        border ? 'border-l border-border' : ''
      }`}
    >
      <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary leading-[1.4]">
        {label}
      </p>
      <div className="flex items-baseline gap-2 mt-1">
        <p className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary leading-none">
          {value}
        </p>
        {delta && (
          <p
            className={`text-[12px] font-medium ${
              deltaType === 'positive'
                ? 'text-success'
                : deltaType === 'negative'
                  ? 'text-error'
                  : 'text-text-tertiary'
            }`}
          >
            {delta}
          </p>
        )}
      </div>
    </div>
  );
}
