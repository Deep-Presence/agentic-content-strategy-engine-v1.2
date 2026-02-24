'use client';

import { useEffect, useMemo } from 'react';
import { PageHeader } from '@/components/layout/page-header';
import { useContentStore } from '@/stores/content-store';
import { CycleList } from '../components/cycle-list';
import type { Cycle, ContentBriefItem } from '@/types/content';

// Mock cycle data with realistic Webflow content
const MOCK_ACTIVE_CYCLE: Cycle = {
  id: 'cycle-3',
  name: 'Week of Feb 24',
  start_date: '2026-02-24T00:00:00Z',
  end_date: '2026-03-02T00:00:00Z',
  briefs: [
    {
      id: 'brief-1',
      title: 'How do no-code builders compare to headless CMS and Next.js?',
      status: 'review',
      content_type: 'blog',
      cluster: 'C3: Category Comparison',
      target_word_count: 1090,
      citability_score: 85,
      created_at: '2026-02-20T10:00:00Z',
      updated_at: '2026-02-23T08:30:00Z',
    },
    {
      id: 'brief-3',
      title: 'Best platforms with enterprise SSO and role-based access control',
      status: 'review',
      content_type: 'guide',
      cluster: 'C7: Best-of/Consideration',
      target_word_count: 1450,
      citability_score: 78,
      created_at: '2026-02-19T11:00:00Z',
      updated_at: '2026-02-23T06:00:00Z',
    },
    {
      id: 'brief-4',
      title: 'No-code vs low-code for marketing team websites',
      status: 'drafting',
      content_type: 'blog',
      cluster: 'C3: Category Comparison',
      target_word_count: 1200,
      citability_score: 72,
      created_at: '2026-02-21T08:00:00Z',
      updated_at: '2026-02-23T09:00:00Z',
    },
    {
      id: 'brief-9',
      title: 'Complete guide to website internationalization without code',
      status: 'approved',
      content_type: 'guide',
      cluster: 'C9: Feature Verification',
      target_word_count: 1800,
      created_at: '2026-02-22T10:00:00Z',
      updated_at: '2026-02-23T01:00:00Z',
    },
  ],
  completed_count: 0,
  total_count: 4,
};

const MOCK_PAST_CYCLES: Cycle[] = [
  {
    id: 'cycle-2',
    name: 'Week of Feb 17',
    start_date: '2026-02-17T00:00:00Z',
    end_date: '2026-02-23T00:00:00Z',
    briefs: [],
    completed_count: 8,
    total_count: 8,
  },
  {
    id: 'cycle-1',
    name: 'Week of Feb 10',
    start_date: '2026-02-10T00:00:00Z',
    end_date: '2026-02-16T00:00:00Z',
    briefs: [],
    completed_count: 6,
    total_count: 8,
  },
];

export default function CyclesPage() {
  const { activeCycle, pastCycles, setCycles } = useContentStore();

  useEffect(() => {
    if (!activeCycle) {
      setCycles(MOCK_ACTIVE_CYCLE, MOCK_PAST_CYCLES);
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
      <CycleList activeCycle={activeCycle ?? MOCK_ACTIVE_CYCLE} pastCycles={pastCycles.length > 0 ? pastCycles : MOCK_PAST_CYCLES} />
    </div>
  );
}
