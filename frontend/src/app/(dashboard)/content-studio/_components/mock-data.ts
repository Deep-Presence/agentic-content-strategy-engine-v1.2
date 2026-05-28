/**
 * Mock data for Content Studio — kept ONLY for cycle UI (deferred to separate sprint).
 * Brief card data now comes from useContentBriefs hook (real API).
 */

import type { Cycle } from './types';

export const MOCK_CYCLE: Cycle = {
  id: 'cycle-012',
  name: 'Cycle 12',
  weekOf: '2026-03-10',
  status: 'active',
  stats: {
    total: 58,
    queue: 2,
    humanReview: 2,
    agentWork: 4,
    published: 14,
    avgCitationScore: 61,
    completionPct: 24,
  },
};

export const PAST_CYCLES: Cycle[] = [
  {
    id: 'cycle-011',
    name: 'Cycle 11',
    weekOf: '2026-03-03',
    status: 'archived',
    stats: { total: 48, queue: 0, humanReview: 0, agentWork: 0, published: 12, avgCitationScore: 67, completionPct: 100 },
  },
  {
    id: 'cycle-010',
    name: 'Cycle 10',
    weekOf: '2026-02-24',
    status: 'archived',
    stats: { total: 42, queue: 0, humanReview: 0, agentWork: 0, published: 10, avgCitationScore: 59, completionPct: 100 },
  },
];
