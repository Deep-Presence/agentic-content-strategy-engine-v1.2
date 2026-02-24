'use client';

import { useEffect, useMemo } from 'react';
import { PageHeader } from '@/components/layout/page-header';
import { useContentStore } from '@/stores/content-store';
import { CycleList } from '../components/cycle-list';
import { WEBFLOW_ACTIVE_CYCLE, WEBFLOW_PAST_CYCLES } from '@/lib/data/webflow-fixtures';

export default function CyclesPage() {
  const { activeCycle, pastCycles, setCycles } = useContentStore();

  useEffect(() => {
    if (!activeCycle) {
      setCycles(WEBFLOW_ACTIVE_CYCLE, WEBFLOW_PAST_CYCLES);
    }
  }, [activeCycle, setCycles]);

  const velocityAvg = useMemo(() => {
    const all = [
      ...(activeCycle ? [activeCycle] : []),
      ...pastCycles,
    ];
    if (all.length === 0) return 0;
    const total = all.reduce((sum, c) => sum + c.completed_count, 0);
    return (total / all.length).toFixed(1);
  }, [activeCycle, pastCycles]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Content Cycles"
        description={`Weekly sprint velocity: ${velocityAvg} briefs/week`}
      />
      <CycleList
        activeCycle={activeCycle ?? WEBFLOW_ACTIVE_CYCLE}
        pastCycles={pastCycles.length > 0 ? pastCycles : WEBFLOW_PAST_CYCLES}
      />
    </div>
  );
}
