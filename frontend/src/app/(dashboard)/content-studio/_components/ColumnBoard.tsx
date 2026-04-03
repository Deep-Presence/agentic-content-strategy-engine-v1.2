'use client';

import type { ContentCard } from './types';
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
              background: badgeColor === 'neutral' ? 'var(--border)' : badgeColor === 'teal' ? 'var(--accent-subtle)' : 'var(--warning-subtle)',
              color: badgeColor === 'neutral' ? 'var(--text-secondary)' : badgeColor === 'teal' ? 'var(--accent)' : 'var(--warning)',
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

interface ColumnBoardProps {
  cards: ContentCard[];
  onCardClick: (card: ContentCard) => void;
}

export function ColumnBoard({ cards, onCardClick }: ColumnBoardProps) {
  const queueCards = cards.filter((c) => c.column === 'queue');
  const humanCards = cards.filter((c) => c.column === 'human');
  const agentCards = cards.filter((c) => c.column === 'agent');

  return (
    <div
      className="flex-1 grid min-h-0 overflow-hidden"
      style={{
        gridTemplateColumns: '22% 39% 39%',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        background: 'var(--bg)',
      }}
    >
      <Column
        title="Queue"
        subtitle="Items from Content Planner"
        count={queueCards.length}
        badgeColor="neutral"
        cards={queueCards}
        onCardClick={onCardClick}
      />
      <Column
        title="Your review"
        subtitle="Approve or send back"
        count={humanCards.length}
        badgeColor="teal"
        cards={humanCards}
        onCardClick={onCardClick}
      />
      <Column
        title="Agent work"
        subtitle="Automated generation in progress"
        count={agentCards.length}
        badgeColor="amber"
        cards={agentCards}
        onCardClick={onCardClick}
      />
    </div>
  );
}
