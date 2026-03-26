'use client';

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button, Skeleton } from '@/components/ui';
import { Plus, LayoutGrid, List, ChevronDown } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useContentBriefs } from '@/lib/hooks/useContent';
import { useTaskStream } from '@/lib/hooks/useTaskStream';
import { useCMSConnection, useCMSCategories, useCMSPublish } from '@/lib/hooks/useCMS';
import { toBrief, toBriefStage } from '@/lib/api/transforms';
import { type ExtendedBrief } from './_components/content-data';
import { CyclesSidebar } from './_components/CyclesSidebar';
import { KanbanBoard } from './_components/KanbanBoard';
import { DetailView } from './_components/DetailView';
import { ContentView } from './_components/ContentView';
import { PublishDrawer } from './_components/PublishDrawer';
import type { CMSPublishResponse } from '@/lib/api/types';


export default function ContentStudioPage() {
  const slug = useAuthStore((s) => s.company?.slug);
  const { data: briefsData, isLoading, refetch } = useContentBriefs(slug);

  // Pipeline progress tracking: prefer URL param, fall back to auto-discovery from brief data
  const searchParams = useSearchParams();
  const urlTaskId = searchParams.get('pipeline_task') ?? null;

  // Auto-discover active task IDs from brief data (briefs with task_id have a running pipeline)
  const discoveredTaskId = useMemo(() => {
    if (urlTaskId) return urlTaskId;
    if (!briefsData?.briefs) return null;
    // Find the first brief with an active task_id (status not completed/rejected/failed)
    const activeBrief = briefsData.briefs.find(
      (b) => b.task_id && !['completed', 'published', 'rejected', 'failed'].includes(b.status),
    );
    return activeBrief?.task_id ?? null;
  }, [urlTaskId, briefsData]);

  const pipelineTaskId = discoveredTaskId;
  const stream = useTaskStream(pipelineTaskId);

  // SSE-driven status overlay: real-time sub-step status from worker_progress events
  // Takes priority over the GET /briefs polling data during pipeline execution
  const [briefStatusOverrides, setBriefStatusOverrides] = useState<
    Map<string, { status: string; substep?: string }>
  >(new Map());

  // Force refetch on pipeline completion and stage transitions (Kanban sync)
  const lastEventCount = useRef(0);
  // Reset counter when task ID changes (new pipeline run resets stream.events)
  useEffect(() => {
    lastEventCount.current = 0;
    setBriefStatusOverrides(new Map());
  }, [pipelineTaskId]);

  useEffect(() => {
    if (stream.status === 'completed' || stream.status === 'error') {
      setBriefStatusOverrides(new Map());
      refetch();
      return;
    }
    // Process new SSE events for direct Kanban state updates
    if (stream.events.length > lastEventCount.current) {
      const newEvents = stream.events.slice(lastEventCount.current);
      lastEventCount.current = stream.events.length;

      let shouldRefetch = false;
      // Batch all override updates into a single setState call
      const overrideUpdates = new Map<string, { status: string; substep?: string }>();

      for (const e of newEvents) {
        const briefId = typeof e.data?.brief_id === 'string' ? e.data.brief_id : '';
        const step = typeof e.data?.step === 'string' ? e.data.step : '';
        const stage = typeof e.data?.stage === 'string' ? e.data.stage : '';

        if (e.type === 'worker_progress' && briefId && step) {
          overrideUpdates.set(briefId, { status: step, substep: step });
        }
        if (e.type === 'pending_approval' && briefId && stage) {
          const statusVal = stage === 'content_review' ? 'review' : 'brief_review';
          overrideUpdates.set(briefId, { status: statusVal });
          shouldRefetch = true;
        }
        if (e.type === 'brief_completed' && briefId) {
          overrideUpdates.set(briefId, { status: 'completed' });
          shouldRefetch = true;
        }
        if (e.type === 'brief_rejected' && briefId) {
          overrideUpdates.set(briefId, { status: 'rejected' });
          shouldRefetch = true;
        }
        if (
          e.type === 'stage_started' ||
          e.type === 'stage_complete' ||
          e.type === 'pipeline_complete'
        ) {
          shouldRefetch = true;
        }
      }

      // Apply batched override updates in one setState
      if (overrideUpdates.size > 0) {
        const lastEvent = newEvents[newEvents.length - 1];
        const clearAll = lastEvent?.type === 'pipeline_complete';
        setBriefStatusOverrides((prev) => {
          if (clearAll) return new Map();
          const next = new Map(prev);
          overrideUpdates.forEach((v, k) => next.set(k, v));
          return next;
        });
      }

      if (shouldRefetch) refetch();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.status, stream.events, refetch]);

  // Transform API briefs to ExtendedBrief for the kanban board
  const apiBriefs = useMemo<ExtendedBrief[]>(() => {
    if (!briefsData?.briefs) return [];
    return briefsData.briefs.map((item) => {
      const base = toBrief(item);
      const gc = item.gap_context;

      // Apply SSE-driven status override if available (real-time sub-step)
      const override = briefStatusOverrides.get(item.id);
      if (override) {
        base.status = override.status;
        base.stage = toBriefStage(override.status);
      }

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
  }, [briefsData, briefStatusOverrides]);

  // Use API data directly; localItems only for optimistic DnD reorder within a session
  // Reset local overrides when API data refreshes
  const items = apiBriefs;

  // CMS publish integration
  const { data: cmsConnection } = useCMSConnection();
  const isCMSConnected = cmsConnection?.is_active ?? false;
  const { data: cmsCategories, isLoading: categoriesLoading } = useCMSCategories(isCMSConnected);
  const { publish, isPublishing, error: publishError } = useCMSPublish();
  const [publishBriefId, setPublishBriefId] = useState<string | null>(null);
  const [publishResult, setPublishResult] = useState<CMSPublishResponse | null>(null);

  const publishBrief = publishBriefId ? items.find((i) => i.id === publishBriefId) ?? null : null;

  const handlePublish = useCallback(async (data: { brief_id: string; status: 'draft' | 'publish'; slug_override: string; categories: string[] }) => {
    const result = await publish(data);
    if (result) {
      setPublishResult(result);
      refetch(); // Refresh briefs to get updated published_url
    }
  }, [publish, refetch]);

  const handleClosePublishDrawer = useCallback(() => {
    setPublishBriefId(null);
    setPublishResult(null);
  }, []);

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
              isCMSConnected={isCMSConnected}
              onPublishClick={setPublishBriefId}
            />
          </div>
        </div>
      </div>

      {detailBrief && (
        <DetailView
          brief={detailBrief}
          onClose={() => setDetailBriefId(null)}
          onOpenFullEditor={handleOpenFullEditor}
          onBriefApproved={refetch}
        />
      )}

      {fullEditorBrief && (
        <ContentView
          brief={fullEditorBrief}
          onClose={() => setFullEditorBriefId(null)}
        />
      )}

      {publishBrief && (
        <PublishDrawer
          open={!!publishBriefId}
          onClose={handleClosePublishDrawer}
          brief={{ id: publishBrief.id, title: publishBrief.title }}
          categories={cmsCategories ?? []}
          categoriesLoading={categoriesLoading}
          onPublish={handlePublish}
          isPublishing={isPublishing}
          publishResult={publishResult}
          publishError={publishError?.detail ?? null}
        />
      )}
    </>
  );
}
