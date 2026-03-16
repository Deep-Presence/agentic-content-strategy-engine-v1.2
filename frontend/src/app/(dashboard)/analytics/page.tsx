'use client';

import { useState, useMemo } from 'react';
import { TabBar } from '@/components/ui';
import { getGapReport } from '@/data/gap-report';
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
  const report = useMemo(() => getGapReport(), []);
  const [activeTab, setActiveTab] = useState('performance');

  // Compute KPI values from real data
  const companyCitedCount = report.queries.filter((q) => q.companyCited).length;
  const citationPresence = ((companyCitedCount / report.summary.totalQueries) * 100).toFixed(1);

  return (
    <div className="space-y-4">
      {/* Top KPI Row — Full Width, Big Numbers */}
      <div className="w-full px-0">
        <div className="grid grid-cols-5 bg-surface border border-border rounded-md overflow-hidden">
          <KPICell
            label="SOV %"
            value="12.4%"
            delta="+2.1%"
            deltaType="positive"
          />
          <KPICell
            label="Citation Presence"
            value={`${citationPresence}%`}
            delta="+4.2%"
            deltaType="positive"
            border
          />
          <KPICell
            label="SPA Score"
            value={report.summary.spaScore.toFixed(3)}
            border
          />
          <KPICell
            label="Queries Tracked"
            value={String(report.summary.totalQueries)}
            border
          />
          <KPICell
            label="Published"
            value="7"
            delta="+3 this week"
            deltaType="positive"
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

      {/* Tab Content — NO global filter bar. Each chart has its own. */}
      <div>
        {activeTab === 'performance' && (
          <PerformanceTab queries={report.queries} clusters={report.clusters} />
        )}
        {activeTab === 'sov' && (
          <ShareOfVoiceTab queries={report.queries} />
        )}
        {activeTab === 'citations' && (
          <CitationsTab queries={report.queries} />
        )}
        {activeTab === 'competitors' && (
          <CompetitorsTab queries={report.queries} />
        )}
        {activeTab === 'brand-health' && (
          <BrandHealthTab />
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
