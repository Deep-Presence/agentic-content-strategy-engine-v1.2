'use client';

import { useState, useCallback, useMemo } from 'react';
import { ChevronDown, Plus } from 'lucide-react';
import type { ContentCard, BriefPipelineStatus } from './_components/types';
import { getDisplay, isTerminal } from './_lib/status-adapter';
import { useContentBriefs } from './_hooks/useContentBriefs';
import { useContentPipeline } from './_hooks/useContentPipeline';
import { useCompanyStream } from './_hooks/useCompanyStream';
import type { SSEPendingApprovalData, SSEPipelineCompleteData } from './_lib/types';
import {
  startPipeline,
  startProduction,
  approveBrief,
  approveContent,
  cancelTask,
} from './_lib/api';
import { useAuth } from '@/hooks/useAuth';
import { MOCK_CYCLE, PAST_CYCLES } from './_components/mock-data';
import { ColumnBoard } from './_components/ColumnBoard';
import { FullPageView } from './_components/FullPageView';

type SortKey = 'priority' | 'newest' | 'gap';
type FilterKey = 'all' | 'briefs' | 'articles' | 'cluster';

function KPICard({ label, value, subtitle, color }: { label: string; value: string; subtitle: string; color: string }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '10px 14px' }}>
      <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>{label}</div>
      <div style={{ fontSize: 22, fontFamily: 'var(--font-mono)', fontWeight: 600, color, marginTop: 2 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>{subtitle}</div>
    </div>
  );
}

const BRIEF_STATUSES: BriefPipelineStatus[] = ['briefing', 'brief_review', 'pending_brief_approval'];
const ARTICLE_STATUSES: BriefPipelineStatus[] = [
  'approved', 'outlining', 'drafting', 'linking', 'enriching',
  'evaluating', 'revising', 'review', 'pending_content_approval',
];

export default function ContentStudioPage() {
  const { companyName, companySlug } = useAuth();
  const { cards, isLoading, error, isEmpty, refetch, updateCard } = useContentBriefs();
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  // Derive selectedCard from live cards array so it stays in sync after polls
  const selectedCard = useMemo(
    () => (selectedCardId ? cards.find((c) => c.id === selectedCardId) ?? null : null),
    [selectedCardId, cards],
  );
  const [cycleOpen, setCycleOpen] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('priority');
  const [filterKey, setFilterKey] = useState<FilterKey>('all');

  // Find the active task ID — prefer GA-active tasks (shorter lifecycle)
  const activeTaskId = useMemo(() => {
    const gaActive = cards.find(c => c.taskId && c.status === 'gap_analysis');
    if (gaActive) return gaActive.taskId!;
    for (const card of cards) {
      if (card.taskId && getDisplay(card.status).isAgentActive) return card.taskId;
    }
    return null;
  }, [cards]);

  // Company-wide SSE stream — triggers re-poll on any pipeline state change.
  // This is the primary mechanism for keeping the kanban in sync.
  useCompanyStream(companySlug ?? null, {
    onStateChanged: () => {
      console.debug(`[CompanyStream] state_changed -> refetch @${new Date().toISOString()}`);
      refetch();
    },
    // onNotification can be wired to a toast system later
  });

  // Per-task SSE — provides real-time progress for detail/drawer view only.
  // Does NOT write card status — the kanban reads status from polls triggered
  // by the company stream above. Only writes agentProgress metadata.
  useContentPipeline(activeTaskId, {
    onStatusChange: (_briefId, _status) => {
      // No-op: card status is driven by poll (via company SSE trigger).
      // The version-aware merge in useContentBriefs handles the rest.
    },
    onProgress: (briefId, progress) => {
      if (briefId) {
        updateCard(briefId, {
          agentProgress: {
            pct: progress.pct ?? 0,
            currentTask: progress.currentTask ?? '',
            gaStepName: progress.gaStepName,
            gaStepNum: progress.gaStepNum,
            gaTotalSteps: progress.gaTotalSteps,
          },
        });
      } else {
        // GA event — update ALL cards with matching task_id (multi-topic batch)
        const gaCards = cards.filter(
          c => c.taskId === activeTaskId && (c.status === 'gap_analysis' || c.status === 'gap_analysis_pending'),
        );
        for (const gc of gaCards) {
          updateCard(gc.id, {
            agentProgress: {
              pct: progress.pct ?? 0,
              currentTask: progress.currentTask ?? '',
              gaStepName: progress.gaStepName,
              gaStepNum: progress.gaStepNum,
              gaTotalSteps: progress.gaTotalSteps,
            },
          });
        }
      }
    },
    onApprovalNeeded: (_briefId: string, _stage: string, _data: SSEPendingApprovalData) => {
      // Status will update via next poll (company SSE triggers it).
      // Could show a toast notification here.
    },
    onBriefCompleted: (briefId) => {
      updateCard(briefId, { agentProgress: undefined });
    },
    onBriefRejected: (briefId) => {
      updateCard(briefId, { agentProgress: undefined });
    },
    onCPSScores: (_scores) => {
      // CPS scores are loaded on demand via useBriefDetail
    },
    onComplete: (_data: SSEPipelineCompleteData) => {
      refetch();
    },
    onError: (_error) => {
      refetch();
    },
    onCancelled: () => {
      refetch();
    },
  });

  // Domain from company slug (used for pipeline start)
  const domain = companySlug ? `${companySlug}.com` : '';

  const handleAction = useCallback(
    async (action: 'start' | 'start_production' | 'approve_brief' | 'approve_article' | 'publish' | 'send_back' | 'cancel' | 'retry', data?: { editorNotes?: string }) => {
      if (!selectedCard || !companyName) return;

      try {
        switch (action) {
          case 'start': {
            const result = await startPipeline(companyName, domain, {
              entry_mode: 'manual',
              manual_prompt: selectedCard.title,
              auto_approve: true,
              brief_id_hint: selectedCard.id,
            });
            updateCard(selectedCard.id, {
              taskId: result.run_id,
              status: 'briefing',
              agentProgress: { pct: 0, currentTask: 'Starting pipeline...' },
            });
            break;
          }
          case 'start_production': {
            if (!selectedCard.gaRunId || !selectedCard.topicAssignmentId) break;
            const prodResult = await startProduction(
              companyName,
              domain,
              selectedCard.effectiveSlug || companySlug,
              [selectedCard.topicAssignmentId],
              selectedCard.gaRunId,
            );
            updateCard(selectedCard.id, {
              taskId: prodResult.run_id,
              status: 'briefing',
              agentProgress: { pct: 0, currentTask: 'Starting content production...' },
            });
            break;
          }
          case 'approve_brief': {
            if (!selectedCard.taskId) return;
            await approveBrief(selectedCard.taskId, selectedCard.id, 'approve');
            updateCard(selectedCard.id, {
              status: 'outlining',
              agentProgress: { pct: 0, currentTask: 'Generating outline...' },
            });
            break;
          }
          case 'approve_article':
          case 'publish': {
            if (!selectedCard.taskId) return;
            await approveContent(selectedCard.taskId, selectedCard.id, 'approve');
            updateCard(selectedCard.id, { status: 'completed', agentProgress: undefined });
            break;
          }
          case 'send_back': {
            if (!selectedCard.taskId) return;
            const isBrief = selectedCard.status === 'brief_review' || selectedCard.status === 'pending_brief_approval';
            if (isBrief) {
              await approveBrief(selectedCard.taskId, selectedCard.id, 'feedback', 'Needs revision');
              updateCard(selectedCard.id, {
                status: 'briefing',
                agentProgress: { pct: 0, currentTask: 'Incorporating feedback...' },
              });
            } else {
              await approveContent(selectedCard.taskId, selectedCard.id, 'edit', data?.editorNotes || 'Needs revision');
              updateCard(selectedCard.id, {
                status: 'revising',
                agentProgress: { pct: 0, currentTask: 'Revising article...' },
              });
            }
            break;
          }
          case 'cancel': {
            if (!selectedCard.taskId) return;
            await cancelTask(selectedCard.taskId);
            updateCard(selectedCard.id, { status: 'suggested', agentProgress: undefined, taskId: undefined });
            break;
          }
          case 'retry': {
            const result = await startPipeline(companyName, domain, {
              entry_mode: 'manual',
              manual_prompt: selectedCard.title,
              auto_approve: true,
              brief_id_hint: selectedCard.id,
            });
            updateCard(selectedCard.id, {
              taskId: result.run_id,
              status: 'briefing',
              agentProgress: { pct: 0, currentTask: 'Retrying pipeline...' },
            });
            break;
          }
        }
      } catch (err) {
        // API error — could show toast
        console.error(`Action "${action}" failed:`, err);
      }
      // Close detail view for most actions. For approvals, keep it open so the
      // user sees the card transition — closing immediately invites re-clicks
      // on the stale Kanban card which triggers 409 errors.
      const keepOpen = action === 'approve_brief' || action === 'approve_article' || action === 'publish';
      if (!keepOpen) {
        setSelectedCardId(null);
      }
    },
    [selectedCard, companyName, companySlug, domain, updateCard],
  );

  // Filter and sort
  const displayCards = cards
    .filter((c) => {
      if (filterKey === 'all') return true;
      if (filterKey === 'briefs') return BRIEF_STATUSES.includes(c.status);
      if (filterKey === 'articles') return ARTICLE_STATUSES.includes(c.status);
      return true;
    })
    .sort((a, b) => {
      if (sortKey === 'priority') {
        const pOrder = { P0: 0, P1: 1, P2: 2 };
        return pOrder[a.priority] - pOrder[b.priority];
      }
      if (sortKey === 'gap') return b.gap - a.gap;
      return 0;
    });

  // KPI calculations from real data
  const triageCount = cards.filter((c) => c.status === 'suggested').length;
  const doneCount = cards.filter((c) => isTerminal(c.status)).length;
  const avgCitability = (() => {
    const scores = cards.map((c) => c.score).filter((s) => s > 0);
    return scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  })();
  const completionPct = cards.length > 0 ? Math.round((doneCount / cards.length) * 100) : 0;

  // Cycle stats (dummy — kept per user decision)
  const stats = MOCK_CYCLE.stats;

  return (
    <>
      <div className="flex flex-col h-full -m-4">
        {/* Header bar */}
        <div className="flex items-center justify-between px-6 flex-shrink-0" style={{ height: 48, borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>Content Studio</span>

          {/* Cycle selector (dummy) */}
          <div className="relative">
            <button
              onClick={() => setCycleOpen(!cycleOpen)}
              className="flex items-center gap-1"
              style={{ height: 30, padding: '0 10px', fontSize: 12, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-secondary)', cursor: 'pointer' }}
            >
              Week of March 10 — Cycle 12
              <ChevronDown size={12} strokeWidth={1.5} />
            </button>
            {cycleOpen && (
              <div className="absolute top-full mt-1 right-0 z-20" style={{ width: 280, background: 'var(--surface-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-float)', overflow: 'hidden' }}>
                <div className="px-3 py-2 cursor-pointer" style={{ fontSize: 12, color: 'var(--text-primary)', background: 'var(--accent-subtle)', borderBottom: '1px solid var(--border)' }} onClick={() => setCycleOpen(false)}>
                  <div style={{ fontWeight: 500 }}>Week of March 10 — Cycle 12</div>
                  <div style={{ fontSize: 10, color: 'var(--accent)', marginTop: 1 }}>Active</div>
                </div>
                {PAST_CYCLES.map((cycle) => (
                  <div key={cycle.id} className="px-3 py-2 cursor-pointer" style={{ fontSize: 12, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }} onClick={() => setCycleOpen(false)}>
                    <div>Week of {cycle.weekOf} — {cycle.name}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 1 }}>{cycle.stats.published} published · Score {cycle.stats.avgCitationScore}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <button style={{ height: 30, padding: '0 12px', fontSize: 12, fontWeight: 500, background: 'transparent', border: '1px solid var(--accent)', borderRadius: 'var(--radius-sm)', color: 'var(--accent)', cursor: 'pointer' }}>
            <Plus size={12} strokeWidth={1.5} className="inline mr-1" style={{ verticalAlign: '-1px' }} />
            New Cycle
          </button>
        </div>

        {/* KPI Strip */}
        <div className="grid grid-cols-4 gap-3 px-6 py-3 flex-shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
          <KPICard label="In Queue" value={String(triageCount)} subtitle="items" color="var(--text-primary)" />
          <KPICard label="Completed" value={String(doneCount)} subtitle="this cycle" color="var(--success)" />
          <KPICard label="Avg. Citation Score" value={avgCitability > 0 ? String(avgCitability) : String(stats.avgCitationScore)} subtitle="across engines" color="var(--accent)" />
          <KPICard label="Cycle Progress" value={`${completionPct > 0 ? completionPct : stats.completionPct}%`} subtitle="completion" color="var(--warning)" />
        </div>

        {/* Filter bar */}
        <div className="flex items-center justify-between px-6 py-2 flex-shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            {cards.length > 0 ? `${cards.length} briefs total` : 'No briefs yet'}
          </div>
          <div className="flex items-center gap-2">
            {(['all', 'briefs', 'articles'] as FilterKey[]).map((f) => (
              <button key={f} onClick={() => setFilterKey(f)} style={{ height: 26, padding: '0 10px', fontSize: 11, fontWeight: filterKey === f ? 500 : 400, background: filterKey === f ? 'var(--accent-subtle)' : 'transparent', color: filterKey === f ? 'var(--accent)' : 'var(--text-secondary)', border: filterKey === f ? 'none' : '1px solid var(--border)', borderRadius: 'var(--radius-full)', cursor: 'pointer', textTransform: 'capitalize' }}>
                {f}
              </button>
            ))}
            <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 4px' }} />
            <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)} style={{ height: 26, padding: '0 8px', fontSize: 11, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-secondary)', cursor: 'pointer', outline: 'none' }}>
              <option value="priority">Priority</option>
              <option value="newest">Newest</option>
              <option value="gap">Gap score</option>
            </select>
          </div>
        </div>

        {/* Board */}
        <div className="flex-1 min-h-0 px-6 py-3 flex flex-col">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
              Loading briefs...
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2" style={{ color: 'var(--error)', fontSize: 13 }}>
              <div>{error}</div>
              <button onClick={refetch} style={{ fontSize: 12, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
                Try again
              </button>
            </div>
          ) : isEmpty ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2" style={{ color: 'var(--text-tertiary)' }}>
              <div style={{ fontSize: 18, fontWeight: 600 }}>No briefs yet</div>
              <div style={{ fontSize: 13 }}>Start by adding topics from the Content Planner or create a brief manually.</div>
            </div>
          ) : (
            <ColumnBoard cards={displayCards} onCardClick={(card) => setSelectedCardId(card.id)} />
          )}
        </div>
      </div>

      {selectedCard && (
        <FullPageView
          card={selectedCard}
          onClose={() => setSelectedCardId(null)}
          onAction={handleAction}
        />
      )}
    </>
  );
}
