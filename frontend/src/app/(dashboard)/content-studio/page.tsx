'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { ChevronDown, Plus } from 'lucide-react';
import type { ContentCard, Column, ContentStage } from './_components/types';
import { INITIAL_CARDS, MOCK_CYCLE, PAST_CYCLES, generateMockBrief, generateMockArticle } from './_components/mock-data';
import { ColumnBoard } from './_components/ColumnBoard';
import { FullPageView } from './_components/FullPageView';

type SortKey = 'priority' | 'newest' | 'gap';
type FilterKey = 'all' | 'briefs' | 'articles' | 'cluster';

function KPICard({ label, value, subtitle, color }: { label: string; value: string; subtitle: string; color: string }) {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: '10px 14px',
      }}
    >
      <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontFamily: 'var(--font-mono)', fontWeight: 600, color, marginTop: 2 }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>{subtitle}</div>
    </div>
  );
}

export default function ContentStudioPage() {
  const [cards, setCards] = useState<ContentCard[]>(INITIAL_CARDS);
  const [selectedCard, setSelectedCard] = useState<ContentCard | null>(null);
  const [cycleOpen, setCycleOpen] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('priority');
  const [filterKey, setFilterKey] = useState<FilterKey>('all');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Agent progress simulation
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setCards((prev) =>
        prev.map((card) => {
          if (card.column !== 'agent' || !card.agentProgress) return card;

          const newPct = Math.min(card.agentProgress.pct + Math.floor(Math.random() * 8) + 2, 100);
          const updated = {
            ...card,
            agentProgress: {
              ...card.agentProgress,
              pct: newPct,
              wordsCurrent: card.agentProgress.wordsCurrent
                ? Math.round(card.agentProgress.wordsCurrent + ((card.agentProgress.wordsTarget || 3000) - card.agentProgress.wordsCurrent) * 0.1)
                : undefined,
            },
          };

          // Move card when progress hits 100%
          if (newPct >= 100) {
            if (card.stage === 'planning' || card.stage === 'brief_generation') {
              return {
                ...updated,
                column: 'human' as Column,
                stage: 'brief_review' as ContentStage,
                stageLabel: 'Brief ready for review',
                agentProgress: undefined,
                briefContent: generateMockBrief(),
              };
            }
            if (card.stage === 'writing' || card.stage === 'evaluating') {
              return {
                ...updated,
                column: 'human' as Column,
                stage: 'article_review' as ContentStage,
                stageLabel: 'Article ready for review',
                agentProgress: undefined,
                articleContent: generateMockArticle(),
              };
            }
          }

          return updated;
        })
      );
    }, 3000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Handle card actions from full-page view
  const handleAction = useCallback((action: 'start' | 'approve_brief' | 'approve_article' | 'publish' | 'send_back' | 'cancel') => {
    if (!selectedCard) return;

    setCards((prev) =>
      prev.map((card) => {
        if (card.id !== selectedCard.id) return card;

        switch (action) {
          case 'start':
            return {
              ...card,
              column: 'agent' as Column,
              stage: 'planning' as ContentStage,
              stageLabel: 'Planning — analyzing queries',
              agentProgress: { pct: 0, currentTask: 'Analyzing query scorecards' },
            };
          case 'approve_brief':
            return {
              ...card,
              column: 'agent' as Column,
              stage: 'writing' as ContentStage,
              stageLabel: 'Writing — section 1',
              agentProgress: { pct: 0, currentTask: 'Writing introduction section', wordsCurrent: 0, wordsTarget: 3000, sectionsComplete: 0, sectionsTotal: 7 },
            };
          case 'approve_article':
          case 'publish':
            return {
              ...card,
              column: 'human' as Column,
              stage: 'published' as ContentStage,
              stageLabel: 'Published',
              agentProgress: undefined,
            };
          case 'send_back':
            return {
              ...card,
              column: 'agent' as Column,
              stage: card.stage === 'brief_review' ? 'brief_generation' as ContentStage : 'writing' as ContentStage,
              stageLabel: card.stage === 'brief_review' ? 'Revising brief' : 'Revising article',
              agentProgress: { pct: 0, currentTask: 'Incorporating feedback' },
            };
          case 'cancel':
            return {
              ...card,
              column: 'queue' as Column,
              stage: 'queue' as ContentStage,
              stageLabel: 'From content planner',
              agentProgress: undefined,
            };
          default:
            return card;
        }
      })
    );
    setSelectedCard(null);
  }, [selectedCard]);

  // Filter and sort cards (excluding published)
  const displayCards = cards
    .filter((c) => c.stage !== 'published')
    .filter((c) => {
      if (filterKey === 'all') return true;
      if (filterKey === 'briefs') return c.stage === 'brief_review' || c.stage === 'brief_generation';
      if (filterKey === 'articles') return c.stage === 'article_review' || c.stage === 'writing' || c.stage === 'evaluating';
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

  const queueCount = cards.filter((c) => c.column === 'queue').length;
  const publishedCount = cards.filter((c) => c.stage === 'published').length;
  const stats = MOCK_CYCLE.stats;

  return (
    <>
      <div className="flex flex-col h-full -m-4">
        {/* Header bar */}
        <div
          className="flex items-center justify-between px-6 flex-shrink-0"
          style={{ height: 48, borderBottom: '1px solid var(--border)' }}
        >
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>Content Studio</span>

          {/* Cycle selector */}
          <div className="relative">
            <button
              onClick={() => setCycleOpen(!cycleOpen)}
              className="flex items-center gap-1"
              style={{
                height: 30,
                padding: '0 10px',
                fontSize: 12,
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              Week of March 10 — Cycle 12
              <ChevronDown size={12} strokeWidth={1.5} />
            </button>

            {cycleOpen && (
              <div
                className="absolute top-full mt-1 right-0 z-20"
                style={{
                  width: 280,
                  background: 'var(--surface-raised)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  boxShadow: 'var(--shadow-float)',
                  overflow: 'hidden',
                }}
              >
                <div
                  className="px-3 py-2 cursor-pointer"
                  style={{
                    fontSize: 12,
                    color: 'var(--text-primary)',
                    background: 'var(--accent-subtle)',
                    borderBottom: '1px solid var(--border)',
                  }}
                  onClick={() => setCycleOpen(false)}
                >
                  <div style={{ fontWeight: 500 }}>Week of March 10 — Cycle 12</div>
                  <div style={{ fontSize: 10, color: 'var(--accent)', marginTop: 1 }}>Active</div>
                </div>
                {PAST_CYCLES.map((cycle) => (
                  <div
                    key={cycle.id}
                    className="px-3 py-2 cursor-pointer"
                    style={{
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      borderBottom: '1px solid var(--border)',
                    }}
                    onClick={() => setCycleOpen(false)}
                  >
                    <div>Week of {cycle.weekOf} — {cycle.name}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 1 }}>
                      {cycle.stats.published} published · Score {cycle.stats.avgCitationScore}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <button
            style={{
              height: 30,
              padding: '0 12px',
              fontSize: 12,
              fontWeight: 500,
              background: 'transparent',
              border: '1px solid var(--accent)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--accent)',
              cursor: 'pointer',
            }}
          >
            <Plus size={12} strokeWidth={1.5} className="inline mr-1" style={{ verticalAlign: '-1px' }} />
            New Cycle
          </button>
        </div>

        {/* KPI Strip */}
        <div
          className="grid grid-cols-4 gap-3 px-6 py-3 flex-shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <KPICard label="In Queue" value={String(queueCount)} subtitle="items" color="var(--text-primary)" />
          <KPICard label="Published" value={String(publishedCount + stats.published)} subtitle="this cycle" color="var(--success)" />
          <KPICard label="Avg. Citation Score" value={String(stats.avgCitationScore)} subtitle="across engines" color="var(--accent)" />
          <KPICard label="Cycle Progress" value={`${stats.completionPct}%`} subtitle="completion" color="var(--warning)" />
        </div>

        {/* Filter bar */}
        <div
          className="flex items-center justify-between px-6 py-2 flex-shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            Mar 10, 2026 – Mar 16, 2026
          </div>
          <div className="flex items-center gap-2">
            {(['all', 'briefs', 'articles'] as FilterKey[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilterKey(f)}
                style={{
                  height: 26,
                  padding: '0 10px',
                  fontSize: 11,
                  fontWeight: filterKey === f ? 500 : 400,
                  background: filterKey === f ? 'var(--accent-subtle)' : 'transparent',
                  color: filterKey === f ? 'var(--accent)' : 'var(--text-secondary)',
                  border: filterKey === f ? 'none' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-full)',
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {f}
              </button>
            ))}

            <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 4px' }} />

            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              style={{
                height: 26,
                padding: '0 8px',
                fontSize: 11,
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              <option value="priority">Priority</option>
              <option value="newest">Newest</option>
              <option value="gap">Gap score</option>
            </select>
          </div>
        </div>

        {/* Board */}
        <div className="flex-1 min-h-0 px-6 py-3 flex flex-col">
          <ColumnBoard cards={displayCards} onCardClick={setSelectedCard} />
        </div>
      </div>

      {/* Full-page view */}
      {selectedCard && (
        <FullPageView
          card={selectedCard}
          onClose={() => setSelectedCard(null)}
          onAction={handleAction}
        />
      )}
    </>
  );
}
