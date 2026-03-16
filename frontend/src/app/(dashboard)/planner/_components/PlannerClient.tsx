'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { TabBar } from '@/components/ui';
import type { Query } from '@/types';
import type { EnrichedTopic } from '@/data/topics';
import type { EnrichedQuery } from '@/data/gap-report';
import { DiscoverTab } from './DiscoverTab';
import { HistoryTab } from './HistoryTab';

interface PlannerClientProps {
  topics: EnrichedTopic[];
  queries: Query[];
  enrichedQueries: EnrichedQuery[];
}

const TABS = [
  { id: 'discover', label: 'Discover' },
  { id: 'history', label: 'History' },
];

export function PlannerClient({ topics, queries, enrichedQueries }: PlannerClientProps) {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') || 'discover';
  const [activeTab, setActiveTab] = useState(initialTab);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-display text-[20px] font-semibold tracking-[-0.02em] text-text-primary">
          Content Planner
        </h1>
      </div>
      <TabBar tabs={TABS} activeTab={activeTab} onTabClick={setActiveTab} className="mb-4" />
      {activeTab === 'discover' && (
        <DiscoverTab topics={topics} queries={queries} enrichedQueries={enrichedQueries} />
      )}
      {activeTab === 'history' && <HistoryTab />}
    </div>
  );
}
