'use client';

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Card, Badge, Button } from '@/components/ui';
import { ChevronRight, X, Send, Pencil, Trash2 } from 'lucide-react';
import {
  type Assignment,
  type SubdomainNode,
  PERSONA_MAP,
  FORMAT_LABELS,
} from './topic-data';

interface AssignmentsViewProps {
  subdomain: SubdomainNode;
  assignments: Assignment[];
  onSendToContentEngine?: (assignment: Assignment) => void;
  sendingAssignmentId?: string | null;
}

type StageFilter = 'tofu' | 'mofu' | 'bofu';
type IntentFilter = 'informational' | 'commercial' | 'transactional' | 'navigational';
type StatusFilter = 'not_started' | 'in_gap_analysis' | 'content_produced' | 'published';
type SortMode = 'priority' | 'stage' | 'status';

const STAGE_STYLES: Record<StageFilter, { label: string; className: string }> = {
  tofu: { label: 'TOFU', className: 'bg-accent-subtle text-accent' },
  mofu: { label: 'MOFU', className: 'bg-warning-subtle text-warning' },
  bofu: { label: 'BOFU', className: 'bg-success-subtle text-success' },
};

const INTENT_STYLES: Record<IntentFilter, { label: string; className: string }> = {
  informational: { label: 'Informational', className: 'text-text-secondary' },
  commercial: { label: 'Commercial', className: 'text-warning' },
  navigational: { label: 'Navigational', className: 'text-accent' },
  transactional: { label: 'Transactional', className: 'text-success' },
};

const STATUS_STYLES: Record<StatusFilter, { label: string; variant: 'neutral' | 'info' | 'warning' | 'success' }> = {
  not_started: { label: 'Not Started', variant: 'neutral' },
  in_gap_analysis: { label: 'In Gap Analysis', variant: 'info' },
  content_produced: { label: 'Content Produced', variant: 'warning' },
  published: { label: 'Published', variant: 'success' },
};

export function AssignmentsView({ subdomain, assignments, onSendToContentEngine, sendingAssignmentId }: AssignmentsViewProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [stageFilters, setStageFilters] = useState<Set<StageFilter>>(new Set());
  const [intentFilters, setIntentFilters] = useState<Set<IntentFilter>>(new Set());
  const [statusFilters, setStatusFilters] = useState<Set<StatusFilter>>(new Set());
  const [personaFilters, setPersonaFilters] = useState<Set<string>>(new Set());
  const [sortMode, setSortMode] = useState<SortMode>('priority');

  const activeFilterCount =
    stageFilters.size + intentFilters.size + statusFilters.size + personaFilters.size;

  const clearFilters = () => {
    setStageFilters(new Set());
    setIntentFilters(new Set());
    setStatusFilters(new Set());
    setPersonaFilters(new Set());
  };

  const toggleFilter = <T,>(set: Set<T>, setFn: (s: Set<T>) => void, val: T) => {
    const next = new Set(set);
    if (next.has(val)) next.delete(val);
    else next.add(val);
    setFn(next);
  };

  // Filter + sort
  const filtered = useMemo(() => {
    let result = assignments;
    if (stageFilters.size > 0) {
      result = result.filter((a) => stageFilters.has(a.buyer_stage));
    }
    if (intentFilters.size > 0) {
      result = result.filter((a) => intentFilters.has(a.intent_type));
    }
    if (statusFilters.size > 0) {
      result = result.filter((a) => statusFilters.has(a.status));
    }
    if (personaFilters.size > 0) {
      result = result.filter((a) => personaFilters.has(a.persona_id));
    }

    // Sort
    result = [...result].sort((a, b) => {
      switch (sortMode) {
        case 'priority':
          return b.priority_score - a.priority_score;
        case 'stage': {
          const order = { tofu: 0, mofu: 1, bofu: 2 };
          return order[a.buyer_stage] - order[b.buyer_stage];
        }
        case 'status': {
          const order = { not_started: 0, in_gap_analysis: 1, content_produced: 2, published: 3 };
          return order[a.status] - order[b.status];
        }
      }
    });

    return result;
  }, [assignments, stageFilters, intentFilters, statusFilters, personaFilters, sortMode]);

  // Stage breakdown counts
  const stageCounts = useMemo(() => {
    const counts = { tofu: 0, mofu: 0, bofu: 0 };
    for (const a of assignments) {
      counts[a.buyer_stage]++;
    }
    return counts;
  }, [assignments]);

  // Unique personas in assignments
  const personaIds = useMemo(() => {
    const ids = new Set<string>();
    for (const a of assignments) {
      ids.add(a.persona_id);
    }
    return Array.from(ids);
  }, [assignments]);

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {/* Context Bar */}
      <div className="px-4 py-2.5 border-b border-border shrink-0">
        <p className="text-[12px] text-text-secondary truncate mb-1">
          {subdomain.description}
        </p>
        <div className="flex items-center gap-2">
          <span className="text-[14px] font-semibold text-text-primary font-mono">
            {assignments.length}
          </span>
          <span className="text-[11px] text-text-tertiary">assignments</span>
          <span className="text-[10px] text-text-tertiary mx-1">·</span>
          <span className="text-[10px] font-medium text-accent">
            TOFU {stageCounts.tofu}
          </span>
          <span className="text-[10px] text-text-tertiary">·</span>
          <span className="text-[10px] font-medium text-warning">
            MOFU {stageCounts.mofu}
          </span>
          <span className="text-[10px] text-text-tertiary">·</span>
          <span className="text-[10px] font-medium text-success">
            BOFU {stageCounts.bofu}
          </span>
        </div>
      </div>

      {/* Filter Row */}
      <div className="px-4 py-2 border-b border-border shrink-0">
        <div className="flex items-center gap-1 flex-wrap">
          {/* Stage chips */}
          {(Object.keys(STAGE_STYLES) as StageFilter[]).map((stage) => (
            <FilterChip
              key={stage}
              label={STAGE_STYLES[stage].label}
              active={stageFilters.has(stage)}
              className={STAGE_STYLES[stage].className}
              onClick={() => toggleFilter(stageFilters, setStageFilters, stage)}
            />
          ))}
          <span className="w-px h-[16px] bg-border mx-1" />

          {/* Intent chips */}
          {(Object.keys(INTENT_STYLES) as IntentFilter[]).map((intent) => (
            <FilterChip
              key={intent}
              label={INTENT_STYLES[intent].label}
              active={intentFilters.has(intent)}
              className={INTENT_STYLES[intent].className}
              onClick={() => toggleFilter(intentFilters, setIntentFilters, intent)}
            />
          ))}
          <span className="w-px h-[16px] bg-border mx-1" />

          {/* Persona chips */}
          {personaIds.map((pid) => (
            <FilterChip
              key={pid}
              label={PERSONA_MAP[pid]?.short ?? pid}
              active={personaFilters.has(pid)}
              onClick={() => toggleFilter(personaFilters, setPersonaFilters, pid)}
            />
          ))}
          <span className="w-px h-[16px] bg-border mx-1" />

          {/* Sort */}
          {(['priority', 'stage', 'status'] as SortMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setSortMode(mode)}
              className={cn(
                'px-1.5 h-[20px] text-[9px] font-medium rounded-sm capitalize transition-colors cursor-pointer',
                sortMode === mode
                  ? 'bg-accent-subtle text-accent'
                  : 'text-text-tertiary hover:text-text-secondary'
              )}
            >
              {mode}
            </button>
          ))}

          {/* Clear */}
          {activeFilterCount > 0 && (
            <button
              onClick={clearFilters}
              className="ml-1 px-1.5 h-[20px] text-[9px] font-medium rounded-sm bg-error-subtle text-error cursor-pointer flex items-center gap-0.5"
            >
              <X size={8} strokeWidth={2} />
              Clear ({activeFilterCount})
            </button>
          )}
        </div>
      </div>

      {/* Result Count */}
      <div className="px-4 py-1.5 text-[10px] text-text-tertiary shrink-0">
        Showing{' '}
        <span className="text-text-primary font-medium">{filtered.length}</span>{' '}
        of {assignments.length}
      </div>

      {/* Assignment Rows */}
      <div className="flex-1 overflow-y-auto">
        {filtered.map((a) => {
          const isExpanded = expandedId === a.id;
          const stageStyle = STAGE_STYLES[a.buyer_stage];
          const intentStyle = INTENT_STYLES[a.intent_type];
          const statusStyle = STATUS_STYLES[a.status];
          const priorityPct = a.priority_score * 100;
          const format = FORMAT_LABELS[a.metadata?.content_format ?? ''] ?? a.metadata?.content_format ?? '';

          return (
            <div key={a.id}>
              {/* Collapsed Row */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : a.id)}
                className={cn(
                  'w-full flex items-center gap-2 px-4 py-[6px] text-left transition-colors cursor-pointer',
                  'border-b border-border-subtle',
                  'hover:bg-surface',
                  isExpanded && 'bg-surface'
                )}
              >
                <ChevronRight
                  size={11}
                  strokeWidth={1.5}
                  className={cn(
                    'text-text-tertiary transition-transform duration-150 shrink-0',
                    isExpanded && 'rotate-90'
                  )}
                />

                {/* Priority bar */}
                <div className="flex items-center gap-1 shrink-0 w-[60px]">
                  <div className="w-[44px] h-[4px] bg-border rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full',
                        priorityPct >= 85
                          ? 'bg-success'
                          : priorityPct >= 70
                          ? 'bg-accent'
                          : 'bg-text-tertiary'
                      )}
                      style={{ width: `${priorityPct}%` }}
                    />
                  </div>
                  <span className="text-[9px] font-mono text-text-tertiary">
                    {(a.priority_score * 100).toFixed(0)}
                  </span>
                </div>

                {/* Stage tag */}
                <span
                  className={cn(
                    'text-[9px] font-medium px-1.5 py-[1px] rounded-full shrink-0',
                    stageStyle.className
                  )}
                >
                  {stageStyle.label}
                </span>

                {/* Query text */}
                <span className="text-[12px] font-medium text-text-primary truncate flex-1">
                  {a.topic_text}
                </span>

                {/* Intent */}
                <span
                  className={cn(
                    'text-[9px] font-medium shrink-0',
                    intentStyle.className
                  )}
                >
                  {intentStyle.label}
                </span>

                {/* Persona */}
                <span className="text-[10px] text-text-tertiary shrink-0 w-[24px] text-center">
                  {PERSONA_MAP[a.persona_id]?.short ?? a.persona_name}
                </span>

                {/* Format */}
                {format && (
                  <span className="text-[9px] font-medium px-1.5 py-[1px] rounded-sm bg-surface border border-border text-text-secondary shrink-0">
                    {format}
                  </span>
                )}

                {/* Status */}
                <Badge variant={statusStyle.variant} className="text-[9px] h-[18px] shrink-0">
                  {statusStyle.label}
                </Badge>
              </button>

              {/* Expanded Detail */}
              {isExpanded && (
                <div className="px-4 py-3 pl-[42px] bg-bg border-b border-border">
                  <Card hoverable={false} className="p-3">
                    <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1.5">
                      RATIONALE
                    </span>
                    <p className="text-[12px] text-text-secondary leading-[1.5] mb-3">
                      {a.metadata?.description ??
                        `Content targeting "${a.topic_text}" — ${stageStyle.label} stage ${intentStyle.label.toLowerCase()} content for ${a.persona_name}. Priority score: ${(a.priority_score * 100).toFixed(0)}.`}
                    </p>

                    {/* Metadata row */}
                    <div className="flex items-center gap-4 text-[10px] text-text-tertiary mb-3">
                      <span>
                        Type:{' '}
                        <span className="text-text-secondary">{a.audience_segment_type}</span>
                      </span>
                      {format && (
                        <span>
                          Format: <span className="text-text-secondary">{format}</span>
                        </span>
                      )}
                      <span>
                        Priority:{' '}
                        <span className="text-text-secondary font-mono">
                          {(a.priority_score * 100).toFixed(0)}
                        </span>
                      </span>
                      {a.metadata?.estimated_word_count && (
                        <span>
                          Words:{' '}
                          <span className="text-text-secondary font-mono">
                            ~{a.metadata.estimated_word_count}
                          </span>
                        </span>
                      )}
                      {a.metadata?.ai_citation_potential && (
                        <span>
                          AI Citation:{' '}
                          <span className={cn(
                            'font-medium',
                            a.metadata.ai_citation_potential === 'HIGH' ? 'text-success' :
                            a.metadata.ai_citation_potential === 'MEDIUM' ? 'text-warning' : 'text-text-secondary'
                          )}>
                            {a.metadata.ai_citation_potential}
                          </span>
                        </span>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        disabled={!!sendingAssignmentId}
                        onClick={() => onSendToContentEngine?.(a)}
                      >
                        <Send size={10} strokeWidth={1.5} className="mr-1" />
                        {sendingAssignmentId === a.id ? 'Sending...' : 'Send to Content Engine'}
                      </Button>
                      <Button variant="secondary" size="sm">
                        <Pencil size={10} strokeWidth={1.5} className="mr-1" />
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-error hover:bg-error-subtle"
                      >
                        <Trash2 size={10} strokeWidth={1.5} className="mr-1" />
                        Remove
                      </Button>
                    </div>
                  </Card>
                </div>
              )}
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="px-4 py-12 text-center">
            <p className="text-[13px] text-text-tertiary">No assignments match current filters</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Filter Chip ─────────────────────────────────────────

function FilterChip({
  label,
  active,
  className,
  onClick,
}: {
  label: string;
  active: boolean;
  className?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-1.5 h-[20px] text-[9px] font-medium rounded-full transition-colors cursor-pointer',
        active
          ? cn('ring-1 ring-accent', className)
          : 'text-text-tertiary hover:text-text-secondary bg-surface',
        className
      )}
    >
      {label}
    </button>
  );
}
