'use client';

import { useState, useCallback } from 'react';
import { CitationFilterBar } from './_components/FilterBar';
import { KPIStrip } from './_components/KPIStrip';
import { CitationMomentum } from './_components/CitationMomentum';
import { VisibilityBreakdown } from './_components/VisibilityBreakdown';
import { CompetitorLeaderboard } from './_components/CompetitorLeaderboard';
import { PlatformGrid } from './_components/PlatformGrid';
import { CitationTable } from './_components/CitationTable';
import { CitationDrawer } from './_components/CitationDrawer';
import { RevenueProxy } from './_components/RevenueProxy';
import { type CitationURL } from './_components/data';

export default function AnalyticsPage() {
  const [platform, setPlatform] = useState('All Platforms');
  const [cluster, setCluster] = useState('All Clusters');
  const [drawerUrl, setDrawerUrl] = useState<CitationURL | null>(null);

  const handleRowClick = useCallback((url: CitationURL) => {
    setDrawerUrl(url);
  }, []);

  const handleDrawerClose = useCallback(() => {
    setDrawerUrl(null);
  }, []);

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
        <p className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>
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
        {/* KPI Strip — 6 cards */}
        <KPIStrip />

        {/* Section 1: Citation Momentum Hero */}
        <CitationMomentum />

        {/* Section 2: Two-column — Visibility (55%) + Leaderboard (45%) */}
        <div className="grid gap-4" style={{ gridTemplateColumns: '55% 45%' }}>
          <VisibilityBreakdown />
          <CompetitorLeaderboard />
        </div>

        {/* Section 3: Platform Intelligence Grid */}
        <PlatformGrid />

        {/* Section 4: Citation URL Table */}
        <CitationTable onRowClick={handleRowClick} />

        {/* Section 5: Revenue Proxy */}
        <RevenueProxy />
      </div>

      {/* Side Drawer */}
      <CitationDrawer url={drawerUrl} onClose={handleDrawerClose} />
    </div>
  );
}
