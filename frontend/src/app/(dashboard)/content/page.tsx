'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button, Skeleton } from '@/components/ui';
import { Plus, LayoutGrid, List, ChevronDown } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useContentBriefs } from '@/lib/hooks/useContent';
import { useTaskStream } from '@/lib/hooks/useTaskStream';
import { toBrief } from '@/lib/api/transforms';
import { type ExtendedBrief } from './_components/content-data';
import { CyclesSidebar } from './_components/CyclesSidebar';
import { KanbanBoard } from './_components/KanbanBoard';
import { DetailView } from './_components/DetailView';
import { ContentView } from './_components/ContentView';


export default function ContentStudioPage() {
  const slug = useAuthStore((s) => s.company?.slug);
  const { data: briefsData, isLoading, refetch } = useContentBriefs(slug);

  // Pipeline progress tracking via URL param
  const searchParams = useSearchParams();
  const pipelineTaskId = searchParams.get('pipeline_task') ?? null;
  const stream = useTaskStream(pipelineTaskId);

  // Force refetch when pipeline completes
  useEffect(() => {
    if (stream.status === 'completed') refetch();
  }, [stream.status, refetch]);

  // Transform API briefs to ExtendedBrief for the kanban board
  const apiBriefs = useMemo<ExtendedBrief[]>(() => {
    if (!briefsData?.briefs) return [];
    return briefsData.briefs.map((item) => {
      const base = toBrief(item);
      const gc = item.gap_context;
      return {
        ...base,
        contentFormat: item.content_type,
        funnelStage: '',
        priorityScore: 0,
        gapScore: gc?.gap_score ?? 0,
        whyPicked: gc?.why_picked,
        successIndicators: gc?.success_indicators,
        exemplars: gc?.exemplars?.map((e) => ({
          url: e.url,
          domain: e.domain,
          words: e.word_count,
          headers: 0,
          stats: 0,
        })),
      } as ExtendedBrief;
    });
  }, [briefsData]);

  // Use API data directly; localItems only for optimistic DnD reorder within a session
  // Reset local overrides when API data refreshes
  const items = apiBriefs;

  const [selectedBriefId, setSelectedBriefId] = useState<string | null>(null);
  const [detailBriefId, setDetailBriefId] = useState<string | null>(null);
  const [fullEditorBriefId, setFullEditorBriefId] = useState<string | null>(null);

  const handleCardClick = useCallback((id: string) => {
    setDetailBriefId(id);
    setSelectedBriefId(id);
  }, []);

  const handleSidebarSelect = useCallback((id: string) => {
    setSelectedBriefId(id);
    setDetailBriefId(id);
  }, []);

  const handleOpenFullEditor = useCallback(() => {
    if (detailBriefId) {
      setFullEditorBriefId(detailBriefId);
      setDetailBriefId(null);
    }
  }, [detailBriefId]);

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleItemsChange = useCallback((_items: ExtendedBrief[]) => {
    // DnD reorder is client-only; no persistence endpoint yet
  }, []);

  const detailBrief = detailBriefId ? items.find((i) => i.id === detailBriefId) ?? null : null;
  const fullEditorBrief = fullEditorBriefId ? items.find((i) => i.id === fullEditorBriefId) ?? null : null;

  if (isLoading) {
    return (
      <div className="flex h-full -m-4">
        <div className="w-[200px] border-r border-border p-3">
          <Skeleton className="h-full rounded-md" />
        </div>
        <div className="flex-1 p-4 space-y-3">
          <Skeleton className="h-10 w-full rounded-md" />
          <div className="grid grid-cols-5 gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-[400px] rounded-md" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (items.length === 0 && stream.status !== 'connected' && stream.status !== 'connecting') {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-[14px] text-text-secondary mb-2">No content briefs yet</p>
        <p className="text-[12px] text-text-tertiary">Run the content pipeline to generate briefs.</p>
      </div>
    );
  }

  return (
    <>
      <div className="flex h-full -m-4">
        {/* Left: Cycles Sidebar */}
        <CyclesSidebar
          items={items}
          selectedBriefId={selectedBriefId}
          onSelectBrief={handleSidebarSelect}
        />

        {/* Center: Board View */}
        <div className="flex-1 min-w-0 overflow-hidden flex flex-col">
          {/* Pipeline progress bar */}
          {(stream.status === 'connected' || stream.status === 'connecting') && (
            <div className="px-4 py-1.5 bg-accent-subtle border-b border-border flex items-center gap-2 shrink-0">
              <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              <span className="text-[11px] text-accent font-medium">
                Content pipeline running{stream.currentStep ? `: ${stream.currentStep}` : '...'}
              </span>
              {stream.progressPct > 0 && (
                <span className="text-[10px] text-text-tertiary font-mono ml-auto">
                  {stream.progressPct}%
                </span>
              )}
            </div>
          )}

          <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
            <div className="flex items-center gap-3">
              <h1 className="text-[20px] font-semibold text-text-primary tracking-[-0.02em]">
                Content Studio
              </h1>
              <div className="flex items-center gap-1 px-2 py-1 bg-surface border border-border rounded-sm cursor-pointer hover:border-border-strong transition-colors">
                <span className="text-[11px] text-text-secondary">{briefsData?.total ?? 0} briefs</span>
                <ChevronDown size={10} strokeWidth={1.5} className="text-text-tertiary" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm">
                <Plus size={11} strokeWidth={1.5} className="mr-1" />
                New Cycle
              </Button>
              <div className="flex items-center border border-border rounded-sm overflow-hidden">
                <button className="p-1.5 bg-accent-subtle text-accent cursor-pointer">
                  <LayoutGrid size={12} strokeWidth={1.5} />
                </button>
                <button className="p-1.5 text-text-tertiary hover:text-text-secondary cursor-pointer">
                  <List size={12} strokeWidth={1.5} />
                </button>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-hidden p-3">
            <KanbanBoard
              items={items}
              onItemsChange={handleItemsChange}
              onCardClick={handleCardClick}
            />
          </div>
        </div>
      </div>

      {detailBrief && (
        <DetailView
          brief={detailBrief}
          onClose={() => setDetailBriefId(null)}
          onOpenFullEditor={handleOpenFullEditor}
        />
      )}

      {fullEditorBrief && (
        <ContentView
          brief={fullEditorBrief}
          onClose={() => setFullEditorBriefId(null)}
        />
      )}
    </>
  );
}
