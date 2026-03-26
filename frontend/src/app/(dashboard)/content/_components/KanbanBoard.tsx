'use client';

import { cn } from '@/lib/utils';
import { StatusDot, Badge } from '@/components/ui';
import { stageColumns, type StageId, type ExtendedBrief } from './content-data';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useState } from 'react';
import { Clock, Upload, ExternalLink } from 'lucide-react';
import { isSafeUrl } from '@/lib/utils';

// --- Content Card ---

function ContentCard({
  brief,
  onClick,
  isDragging,
  isCMSConnected,
  onPublishClick,
}: {
  brief: ExtendedBrief;
  onClick: () => void;
  isDragging?: boolean;
  isCMSConnected?: boolean;
  onPublishClick?: (briefId: string) => void;
}) {
  const daysAgo = Math.floor(
    (Date.now() - new Date(brief.createdAt).getTime()) / (1000 * 60 * 60 * 24)
  );
  const showGapScore = brief.stage === 'triage' || brief.stage === 'brief';
  const showWordCount = brief.stage === 'generating' || brief.stage === 'review' || brief.stage === 'approved';

  return (
    <div
      onClick={onClick}
      className={cn(
        'bg-surface border border-border rounded-sm p-[10px] cursor-grab hover:border-border-strong transition-[border-color] duration-150',
        isDragging && 'opacity-50'
      )}
    >
      <h4 className="text-[13px] font-semibold text-text-primary leading-tight mb-1.5 line-clamp-2">
        {brief.title}
      </h4>

      {/* Sub-step badge — real-time pipeline status */}
      {(() => {
        const badgeText: Record<string, string> = {
          suggested: 'Awaiting approval',
          briefing: 'Generating brief',
          brief_review: 'Approve brief',
          approved: 'Brief approved',
          outlining: 'Outlining',
          drafting: 'Drafting',
          linking: 'Linking',
          enriching: 'Enriching',
          evaluating: 'Evaluating',
          revising: 'Revising',
          review: 'Final review',
          completed: 'Published',
          published: 'Published',
        };
        const isHitl = ['suggested', 'brief_review', 'review'].includes(brief.status);
        const isDone = ['completed', 'published'].includes(brief.status);
        const label = badgeText[brief.status];
        if (!label) return null;
        return (
          <span
            className={cn(
              'inline-block text-[10px] font-medium px-1.5 py-0.5 rounded mb-1.5',
              isHitl && 'bg-warning/10 text-warning',
              !isHitl && !isDone && 'bg-accent/10 text-accent',
              isDone && 'bg-success/10 text-success',
            )}
          >
            {label}
          </span>
        );
      })()}

      {/* Content type + cluster badges */}
      <div className="flex items-center gap-1 mb-2 flex-wrap">
        <Badge variant="neutral">{brief.contentFormat}</Badge>
        <Badge variant="info">{brief.targetCluster}</Badge>
      </div>

      {/* Gap score or word count */}
      <div className="flex items-center justify-between mb-1.5">
        {showGapScore && (
          <span className="text-[10px] font-medium text-warning">
            Gap {brief.gapScore.toFixed(3)}
          </span>
        )}
        {showWordCount && brief.currentWordCount && (
          <span className="text-[10px] text-text-secondary">
            {brief.currentWordCount.toLocaleString()} words · ~{brief.readMinutes}min
          </span>
        )}
        {!showGapScore && !showWordCount && <span />}
        <span className="text-[10px] font-medium text-text-secondary">
          {(brief.priorityScore * 100).toFixed(0)}
        </span>
      </div>

      {/* Persona dots + publish + time */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          {brief.personas.slice(0, 3).map((p, i) => (
            <StatusDot key={`${p}-${i}`} color="info" />
          ))}
          {brief.personas.length > 3 && (
            <span className="text-[9px] text-text-tertiary">+{brief.personas.length - 3}</span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {/* Published badge */}
          {brief.publishedUrl && isSafeUrl(brief.publishedUrl) && (
            <a
              href={brief.publishedUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-0.5 text-success"
              title="View on CMS"
            >
              <ExternalLink size={9} strokeWidth={1.5} />
            </a>
          )}
          {/* Publish to CMS icon — only on approved briefs when CMS connected */}
          {brief.stage === 'approved' && isCMSConnected && onPublishClick && !brief.publishedUrl && (
            <button
              onClick={(e) => { e.stopPropagation(); onPublishClick(brief.id); }}
              className="p-0.5 text-accent hover:bg-accent/10 rounded transition-colors"
              title="Publish to CMS"
            >
              <Upload size={11} strokeWidth={1.5} />
            </button>
          )}
          <div className="flex items-center gap-0.5 text-text-tertiary">
            <Clock size={9} strokeWidth={1.5} />
            <span className="text-[10px]">{daysAgo}d</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Sortable Card Wrapper ---

function SortableCard({
  brief,
  onClick,
  isCMSConnected,
  onPublishClick,
}: {
  brief: ExtendedBrief;
  onClick: () => void;
  isCMSConnected?: boolean;
  onPublishClick?: (briefId: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: brief.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <ContentCard brief={brief} onClick={onClick} isDragging={isDragging} isCMSConnected={isCMSConnected} onPublishClick={onPublishClick} />
    </div>
  );
}

// --- Column ---

function KanbanColumn({
  stage,
  items,
  onCardClick,
  isCMSConnected,
  onPublishClick,
}: {
  stage: (typeof stageColumns)[number];
  items: ExtendedBrief[];
  onCardClick: (id: string) => void;
  isCMSConnected?: boolean;
  onPublishClick?: (briefId: string) => void;
}) {
  return (
    <div className="flex flex-col min-w-[200px] flex-1">
      <div className="flex items-center gap-2 mb-2 px-1">
        <StatusDot color={stage.color} />
        <span className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
          {stage.label}
        </span>
        <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-full bg-surface border border-border text-[10px] font-medium text-text-secondary ml-auto">
          {items.length}
        </span>
      </div>
      <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
        <div className="flex flex-col gap-2 flex-1 min-h-[100px] p-1 rounded-sm">
          {items.map((item) => (
            <SortableCard key={item.id} brief={item} onClick={() => onCardClick(item.id)} isCMSConnected={isCMSConnected} onPublishClick={onPublishClick} />
          ))}
        </div>
      </SortableContext>
    </div>
  );
}

// --- Board ---

interface KanbanBoardProps {
  items: ExtendedBrief[];
  onItemsChange: (items: ExtendedBrief[]) => void;
  onCardClick: (id: string) => void;
  isCMSConnected?: boolean;
  onPublishClick?: (briefId: string) => void;
}

export function KanbanBoard({ items, onItemsChange, onCardClick, isCMSConnected, onPublishClick }: KanbanBoardProps) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  );

  const getColumnItems = (stageId: StageId) => items.filter((i) => i.stage === stageId);

  const findContainer = (id: string): StageId | undefined => {
    const item = items.find((i) => i.id === id);
    return item?.stage as StageId | undefined;
  };

  function handleDragStart(event: DragStartEvent) {
    setActiveId(event.active.id as string);
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event;
    if (!over) return;

    const activeContainer = findContainer(active.id as string);
    const overItem = items.find((i) => i.id === over.id);
    const overContainer = overItem?.stage as StageId | undefined;

    if (!activeContainer || !overContainer || activeContainer === overContainer) return;

    onItemsChange(
      items.map((item) =>
        item.id === active.id ? { ...item, stage: overContainer } : item
      )
    );
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveId(null);
    if (!over) return;

    const activeContainer = findContainer(active.id as string);
    const overStage = stageColumns.find((s) => s.id === (over.id as string));
    if (overStage && activeContainer !== overStage.id) {
      onItemsChange(
        items.map((item) =>
          item.id === active.id ? { ...item, stage: overStage.id } : item
        )
      );
    }
  }

  const activeItem = activeId ? items.find((i) => i.id === activeId) : null;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-3 h-full overflow-x-auto p-1">
        {stageColumns.map((stage) => (
          <KanbanColumn
            key={stage.id}
            stage={stage}
            items={getColumnItems(stage.id)}
            onCardClick={onCardClick}
            isCMSConnected={isCMSConnected}
            onPublishClick={onPublishClick}
          />
        ))}
      </div>
      <DragOverlay>
        {activeItem && (
          <div className="opacity-80 rotate-2">
            <ContentCard brief={activeItem} onClick={() => {}} />
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}
