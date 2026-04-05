'use client';

import type { ContentCard, KanbanColumn } from './types';
import { getColumn } from '../_lib/status-adapter';
import { ContentCardItem } from './ContentCardItem';

interface ColumnProps {
  title: string;
  subtitle: string;
  count: number;
  badgeColor: string;
  cards: ContentCard[];
  onCardClick: (card: ContentCard) => void;
}

function Column({ title, subtitle, count, badgeColor, cards, onCardClick }: ColumnProps) {
  const badgeBg =
    badgeColor === 'neutral' ? 'var(--border)' :
    badgeColor === 'teal' ? 'var(--accent-subtle)' :
    badgeColor === 'success' ? 'var(--success-subtle)' :
    'var(--warning-subtle)';
  const badgeFg =
    badgeColor === 'neutral' ? 'var(--text-secondary)' :
    badgeColor === 'teal' ? 'var(--accent)' :
    badgeColor === 'success' ? 'var(--success)' :
    'var(--warning)';

  return (
    <div className="flex flex-col min-h-0" style={{ borderRight: '1px solid var(--border)' }}>
      {/* Column header */}
      <div className="px-3 py-3 flex-shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              padding: '1px 6px',
              borderRadius: 'var(--radius-full)',
              background: badgeBg,
              color: badgeFg,
            }}
          >
            {count}
          </span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>{subtitle}</div>
      </div>

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {cards.map((card) => (
          <ContentCardItem key={card.id} card={card} onClick={() => onCardClick(card)} />
        ))}
        {cards.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
            <div style={{ fontSize: 18, marginBottom: 4 }}>&#10003;</div>
            All caught up
          </div>
        )}
      </div>
    </div>
  );
}

const COLUMNS: { key: KanbanColumn; title: string; subtitle: string; badgeColor: string }[] = [
  { key: 'triage', title: 'Queue', subtitle: 'Items from Content Planner', badgeColor: 'neutral' },
  { key: 'human', title: 'Your review', subtitle: 'Approve or send back', badgeColor: 'teal' },
  { key: 'agent', title: 'Agent work', subtitle: 'Automated generation in progress', badgeColor: 'amber' },
  { key: 'done', title: 'Completed', subtitle: 'Published & archived', badgeColor: 'success' },
];

interface ColumnBoardProps {
  cards: ContentCard[];
  onCardClick: (card: ContentCard) => void;
}

export function ColumnBoard({ cards, onCardClick }: ColumnBoardProps) {
  const cardsByColumn: Record<KanbanColumn, ContentCard[]> = {
    triage: [],
    human: [],
    agent: [],
    done: [],
  };

  for (const card of cards) {
    const col = getColumn(card.status);
    cardsByColumn[col].push(card);
  }

  return (
    <div
      className="flex-1 grid min-h-0 overflow-hidden"
      style={{
        gridTemplateColumns: '16% 34% 34% 16%',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        background: 'var(--bg)',
      }}
    >
      {COLUMNS.map((col) => (
        <Column
          key={col.key}
          title={col.title}
          subtitle={col.subtitle}
          count={cardsByColumn[col.key].length}
          badgeColor={col.badgeColor}
          cards={cardsByColumn[col.key]}
          onCardClick={onCardClick}
        />
      ))}
    </div>
  );
}
