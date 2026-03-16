import { Suspense } from 'react';
import { getTopics } from '@/data/topics';
import { getGapReport } from '@/data/gap-report';
import { PlannerClient } from './_components/PlannerClient';

export default function ContentPlannerPage() {
  const topics = getTopics();
  const report = getGapReport();

  return (
    <Suspense>
      <PlannerClient
        topics={topics}
        queries={report.queries}
        enrichedQueries={report.enrichedQueries}
      />
    </Suspense>
  );
}
