'use client';

import { useState, useCallback } from 'react';
import { CitationFilterBar } from './_components/filter-bar';
import { KPIStrip } from './_components/kpi-strip';
import { CitationMomentum } from './_components/citation-momentum';
import { CompetitorLeaderboard } from './_components/competitor-leaderboard';
import { VisibilityPipeline } from './_components/visibility-pipeline';
import { SentimentSection } from './_components/sentiment-section';
import { PlatformIntelligence } from './_components/platform-intelligence';
import { CitationURLsTable } from './_components/citation-urls-table';
import { UncitedQueriesDrawer } from './_components/uncited-queries-drawer';

export default function AnalyticsPage() {
  const [platform, setPlatform] = useState('All Platforms');
  const [cluster, setCluster] = useState('All Clusters');
  const [uncitedDrawerOpen, setUncitedDrawerOpen] = useState(false);

  const openUncitedDrawer = useCallback(() => setUncitedDrawerOpen(true), []);
  const closeUncitedDrawer = useCallback(() => setUncitedDrawerOpen(false), []);

  return (
    <div className="-m-4">
      {/* Page Header */}
      <div className="px-6 pt-4 pb-0">
        <h1
          className="text-[22px] font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          Citation Intelligence
        </h1>
        <p className="text-[13px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Track how your brand is cited across AI platforms
        </p>
      </div>

      {/* Global Filter Bar */}
      <CitationFilterBar
        platform={platform}
        onPlatformChange={setPlatform}
        cluster={cluster}
        onClusterChange={setCluster}
      />

      {/* Page Content */}
      <div className="px-6 py-4 flex flex-col gap-4">
        {/* KPI Strip — 4 cards */}
        <KPIStrip onUncitedClick={openUncitedDrawer} />

        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0' }} />

        {/* Section 1: Citation Momentum + Leaderboard */}
        <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 280px' }}>
          <CitationMomentum />
          <CompetitorLeaderboard />
        </div>

        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0' }} />

        {/* Section 2: Visibility Pipeline */}
        <VisibilityPipeline onViewAll={openUncitedDrawer} />

        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0' }} />

        {/* Section 3: How AI Engines Talk About You */}
        <SentimentSection />

        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0' }} />

        {/* Section 4: Platform Intelligence Grid */}
        <PlatformIntelligence />

        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0' }} />

        {/* Section 5: Citation URLs Table */}
        <CitationURLsTable />
      </div>

      {/* Uncited Queries Drawer */}
      <UncitedQueriesDrawer open={uncitedDrawerOpen} onClose={closeUncitedDrawer} />
    </div>
  );
}
