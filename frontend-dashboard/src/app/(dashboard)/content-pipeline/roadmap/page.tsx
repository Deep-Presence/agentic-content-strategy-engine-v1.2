'use client';

import { PageHeader } from '@/components/layout/page-header';
import { useContentStore } from '@/stores/content-store';
import { RoadmapTimeline } from '../components/roadmap-timeline';

export default function RoadmapPage() {
  const { briefs } = useContentStore();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Content Roadmap"
        description="Plan and track content across weeks and content types"
      />
      <RoadmapTimeline briefs={briefs} />
    </div>
  );
}
