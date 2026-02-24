'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import { Plus, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { PageHeader } from '@/components/layout/page-header';
import { useAppStore } from '@/stores/app-store';
import { useContentStore } from '@/stores/content-store';
import { artifacts } from '@/lib/api/artifacts';
import { ViewSwitcher } from './components/view-switcher';
import { FilterBar } from './components/filter-bar';
import { BoardView } from './components/board-view';
import { TableView } from './components/table-view';
import { CalendarView } from './components/calendar-view';
import { CycleList } from './components/cycle-list';
import { RoadmapTimeline } from './components/roadmap-timeline';
import { CreateBriefDialog } from './components/create-brief-dialog';
import { PipelineTriggerBar } from './components/pipeline-trigger-bar';
import type { ContentBriefItem } from '@/types/content';

// Realistic mock data for Webflow (used when API is offline)
const MOCK_BRIEFS: ContentBriefItem[] = [
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
    id: 'brief-2',
    title: 'What is a design system in the context of website building tools?',
    status: 'published',
    content_type: 'blog',
    cluster: 'C5: Definition',
    target_word_count: 950,
    citability_score: 91,
    created_at: '2026-02-18T09:00:00Z',
    updated_at: '2026-02-22T14:00:00Z',
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
    id: 'brief-5',
    title: 'How website builders handle Core Web Vitals performance',
    status: 'research',
    content_type: 'guide',
    cluster: 'C1: Mechanism',
    target_word_count: 1350,
    created_at: '2026-02-22T07:00:00Z',
    updated_at: '2026-02-23T07:00:00Z',
  },
  {
    id: 'brief-6',
    title: 'Evaluating website platforms for scalability and content velocity',
    status: 'evaluating',
    content_type: 'blog',
    cluster: 'C4: Decision Criteria',
    target_word_count: 1100,
    created_at: '2026-02-21T12:00:00Z',
    updated_at: '2026-02-23T05:00:00Z',
  },
  {
    id: 'brief-7',
    title: 'When to choose a visual editor vs a code-first CMS',
    status: 'suggested',
    content_type: 'blog',
    cluster: 'C4: Decision Criteria',
    target_word_count: 1000,
    created_at: '2026-02-22T15:00:00Z',
    updated_at: '2026-02-22T15:00:00Z',
  },
  {
    id: 'brief-8',
    title: 'Webflow case study: How Jasper scaled their marketing site',
    status: 'suggested',
    content_type: 'case_study',
    cluster: 'C8: Branded Evaluation',
    target_word_count: 1600,
    created_at: '2026-02-22T16:00:00Z',
    updated_at: '2026-02-22T16:00:00Z',
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
  {
    id: 'brief-10',
    title: 'What problems does no-code web design solve for growing teams?',
    status: 'enriching',
    content_type: 'blog',
    cluster: 'C6: Problem/Awareness',
    target_word_count: 1050,
    citability_score: 68,
    created_at: '2026-02-20T14:00:00Z',
    updated_at: '2026-02-23T04:00:00Z',
  },
  {
    id: 'brief-11',
    title: 'Product page optimization: Features that AI search engines highlight',
    status: 'published',
    content_type: 'product_page',
    cluster: 'C9: Feature Verification',
    target_word_count: 800,
    citability_score: 88,
    created_at: '2026-02-17T10:00:00Z',
    updated_at: '2026-02-21T09:00:00Z',
  },
  {
    id: 'brief-12',
    title: 'How Webflow compares to WordPress for enterprise marketing',
    status: 'published',
    content_type: 'blog',
    cluster: 'C3: Category Comparison',
    target_word_count: 1300,
    citability_score: 82,
    created_at: '2026-02-15T09:00:00Z',
    updated_at: '2026-02-20T11:00:00Z',
  },
  {
    id: 'brief-13',
    title: 'Understanding content velocity boundaries in website platforms',
    status: 'suggested',
    content_type: 'blog',
    cluster: 'C2: Boundary',
    target_word_count: 1150,
    created_at: '2026-02-23T08:00:00Z',
    updated_at: '2026-02-23T08:00:00Z',
  },
];

export default function ContentPipelinePage() {
  const { currentCompany } = useAppStore();
  const { activeView, briefs, setBriefs, statusFilter, typeFilter, clusterFilter, searchQuery, activeCycle, pastCycles } = useContentStore();
  const { toast } = useToast();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [triggerPanelOpen, setTriggerPanelOpen] = useState(false);

  const loadBriefs = useCallback(async () => {
    if (!currentCompany) {
      setBriefs(MOCK_BRIEFS);
      return;
    }
    try {
      const data = await artifacts.getContent<ContentBriefItem[]>('content', currentCompany, 'briefs.json');
      setBriefs(data);
    } catch {
      setBriefs(MOCK_BRIEFS);
    }
  }, [currentCompany, setBriefs]);

  useEffect(() => {
    loadBriefs();
  }, [loadBriefs]);

  const clusters = useMemo(() => {
    const set = new Set(briefs.map((b) => b.cluster));
    return Array.from(set).sort();
  }, [briefs]);

  const filteredBriefs = useMemo(() => {
    return briefs.filter((b) => {
      if (statusFilter !== 'all' && b.status !== statusFilter) return false;
      if (typeFilter !== 'all' && b.content_type !== typeFilter) return false;
      if (clusterFilter !== 'all' && b.cluster !== clusterFilter) return false;
      if (searchQuery && !b.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
  }, [briefs, statusFilter, typeFilter, clusterFilter, searchQuery]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Content Pipeline"
        description="Manage content from gap brief to published article"
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => setCreateDialogOpen(true)}>
              <Plus className="h-4 w-4" />
              New Brief
            </Button>
            <Button size="sm" onClick={() => setTriggerPanelOpen(true)} className="bg-sage-400 hover:bg-sage-500">
              <Zap className="h-4 w-4" />
              Generate from Gaps
            </Button>
          </div>
        }
      />

      <ViewSwitcher />

      <FilterBar clusters={clusters} />

      {/* Active View */}
      {activeView === 'board' && <BoardView briefs={filteredBriefs} />}
      {activeView === 'table' && <TableView briefs={filteredBriefs} />}
      {activeView === 'calendar' && <CalendarView briefs={filteredBriefs} />}
      {activeView === 'cycles' && <CycleList activeCycle={activeCycle} pastCycles={pastCycles} />}
      {activeView === 'roadmap' && <RoadmapTimeline briefs={filteredBriefs} />}

      {/* Dialogs */}
      <CreateBriefDialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} />
      <PipelineTriggerBar open={triggerPanelOpen} onClose={() => setTriggerPanelOpen(false)} />
    </div>
  );
}
