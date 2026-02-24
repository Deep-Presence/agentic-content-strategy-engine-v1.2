'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import { Plus, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { PageHeader } from '@/components/layout/page-header';
import { useAppStore } from '@/stores/app-store';
import { useContentStore } from '@/stores/content-store';
import { artifacts } from '@/lib/api/artifacts';
import { WEBFLOW_PIPELINE_BRIEFS } from '@/lib/data/webflow-fixtures';
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

export default function ContentPipelinePage() {
  const { currentCompany } = useAppStore();
  const { activeView, briefs, setBriefs, statusFilter, typeFilter, clusterFilter, searchQuery, activeCycle, pastCycles } = useContentStore();
  const { toast } = useToast();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [triggerPanelOpen, setTriggerPanelOpen] = useState(false);

  const loadBriefs = useCallback(async () => {
    if (!currentCompany) {
      setBriefs(WEBFLOW_PIPELINE_BRIEFS);
      return;
    }
    try {
      const data = await artifacts.getContent<ContentBriefItem[]>('content', currentCompany, 'briefs.json');
      setBriefs(data);
    } catch {
      setBriefs(WEBFLOW_PIPELINE_BRIEFS);
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
