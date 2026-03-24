'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui';
import { Plus, LayoutGrid, List, ChevronDown } from 'lucide-react';
import { boardItems as initialItems, type ExtendedBrief } from './_components/content-data';
import { CyclesSidebar } from './_components/CyclesSidebar';
import { KanbanBoard } from './_components/KanbanBoard';
import { DetailView } from './_components/DetailView';
import { ContentView } from './_components/ContentView';

export default function ContentStudioPage() {
  const [items, setItems] = useState<ExtendedBrief[]>(initialItems);
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

  const detailBrief = detailBriefId ? items.find((i) => i.id === detailBriefId) ?? null : null;
  const fullEditorBrief = fullEditorBriefId ? items.find((i) => i.id === fullEditorBriefId) ?? null : null;

  return (
    <>
      <div className="flex h-full -m-4">
        {/* Left: Cycles Sidebar */}
        <CyclesSidebar
          items={items}
          selectedBriefId={selectedBriefId}
          onSelectBrief={handleSidebarSelect}
        />

        {/* Center: Board View — NO agent activity sidebar */}
        <div className="flex-1 min-w-0 overflow-hidden flex flex-col">
          {/* Cycle selector + view toggle */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
            <div className="flex items-center gap-3">
              <h1 className="text-[20px] font-semibold text-text-primary tracking-[-0.02em]">
                Content Studio
              </h1>
              <div className="flex items-center gap-1 px-2 py-1 bg-surface border border-border rounded-sm cursor-pointer hover:border-border-strong transition-colors">
                <span className="text-[11px] text-text-secondary">Week of March 10</span>
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

          {/* Board */}
          <div className="flex-1 overflow-hidden p-3">
            <KanbanBoard
              items={items}
              onItemsChange={setItems}
              onCardClick={handleCardClick}
            />
          </div>
        </div>
      </div>

      {/* Phase-dependent Detail View overlay */}
      {detailBrief && (
        <DetailView
          brief={detailBrief}
          onClose={() => setDetailBriefId(null)}
          onOpenFullEditor={handleOpenFullEditor}
        />
      )}

      {/* Full Editor overlay (with agent activity sidebar) */}
      {fullEditorBrief && (
        <ContentView
          brief={fullEditorBrief}
          onClose={() => setFullEditorBriefId(null)}
        />
      )}
    </>
  );
}
