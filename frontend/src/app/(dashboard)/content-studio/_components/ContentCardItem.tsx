'use client';

import { Clock } from 'lucide-react';
import type { ContentCard } from './types';

const TYPE_LABELS: Record<string, string> = {
  HOW_TO: 'HOW-TO',
  COMPARISON: 'COMPARISON',
  GUIDE: 'GUIDE',
  LONG_BLOG: 'LONG BLOG',
  PILLAR_PAGE: 'PILLAR PAGE',
};

function progressColor(pct: number) {
  if (pct > 80) return 'var(--success)';
  if (pct >= 50) return 'var(--accent)';
  return 'var(--warning)';
}

function leftBorderColor(card: ContentCard) {
  if (card.column === 'queue') return 'var(--text-tertiary)';
  if (card.stage === 'brief_review') return 'var(--warning)';
  if (card.stage === 'article_review') return 'var(--accent)';
  return 'var(--border)';
}

export function ContentCardItem({ card, onClick }: { card: ContentCard; onClick: () => void }) {
  const gapDisplay = Math.round(card.gap * 100);

  return (
    <div
      onClick={onClick}
      className="group cursor-pointer transition-all duration-150"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${leftBorderColor(card)}`,
        borderRadius: 'var(--radius-md)',
        padding: '12px 14px',
        animation: 'cardMove 300ms ease',
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-strong)'; (e.currentTarget as HTMLElement).style.borderLeftColor = leftBorderColor(card); }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'; (e.currentTarget as HTMLElement).style.borderLeftColor = leftBorderColor(card); }}
    >
      {/* Title */}
      <div
        className="line-clamp-2"
        style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', lineHeight: '1.4' }}
      >
        {card.title}
      </div>

      {/* ID + Cluster */}
      <div
        className="mt-1"
        style={{ fontSize: 11, color: 'var(--text-secondary)' }}
      >
        {card.id} · {card.cluster}
      </div>

      {/* Tags row */}
      <div className="flex items-center gap-1.5 flex-wrap mt-2">
        {/* Type pill */}
        <span
          style={{
            fontSize: 9,
            fontWeight: 600,
            textTransform: 'uppercase',
            padding: '1px 6px',
            borderRadius: 'var(--radius-full)',
            background: 'var(--accent-subtle)',
            color: 'var(--accent)',
          }}
        >
          {TYPE_LABELS[card.type]}
        </span>

        {/* Priority pill */}
        <span
          style={{
            fontSize: 9,
            fontWeight: 600,
            textTransform: 'uppercase',
            padding: '1px 6px',
            borderRadius: 'var(--radius-full)',
            background: 'var(--warning-subtle)',
            color: 'var(--warning)',
          }}
        >
          {card.priority}
        </span>

        {/* Gap */}
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            fontFamily: 'var(--font-mono)',
            color: 'var(--error)',
          }}
        >
          ~{gapDisplay}
        </span>

        {/* Read time */}
        <span className="flex items-center gap-0.5" style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
          <Clock size={10} strokeWidth={1.5} />
          {card.readTime}min
        </span>

        {/* Competitor */}
        <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
          {card.competitor}
        </span>

        {/* Score */}
        <span
          className="ml-auto"
          style={{
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            fontWeight: 500,
            color: 'var(--text-primary)',
          }}
        >
          {card.score}
        </span>
      </div>

      {/* Agent progress (agent column) */}
      {card.column === 'agent' && card.agentProgress && (
        <div className="mt-3">
          <div className="flex items-center justify-between">
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                color: 'var(--warning)',
                animation: 'typing 1.8s ease-in-out infinite',
              }}
            >
              {card.stageLabel}
            </span>
            <span
              style={{
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-tertiary)',
              }}
            >
              {card.agentProgress.pct}%
            </span>
          </div>
          <div
            className="mt-1"
            style={{
              width: '100%',
              height: 4,
              background: 'var(--border)',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${card.agentProgress.pct}%`,
                height: '100%',
                borderRadius: 2,
                background: progressColor(card.agentProgress.pct),
                animation: 'progressPulse 2.5s ease-in-out infinite',
                transition: 'width 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            />
          </div>
          {(card.agentProgress.wordsCurrent !== undefined || card.agentProgress.sectionsComplete !== undefined) && (
            <div
              className="mt-1"
              style={{
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-tertiary)',
              }}
            >
              {card.agentProgress.wordsCurrent !== undefined && (
                <span>{card.agentProgress.wordsCurrent.toLocaleString()} / {card.agentProgress.wordsTarget?.toLocaleString()} words</span>
              )}
              {card.agentProgress.sectionsComplete !== undefined && (
                <span> · {card.agentProgress.sectionsComplete}/{card.agentProgress.sectionsTotal} sections</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Human review indicator */}
      {card.column === 'human' && (
        <div className="flex items-center gap-1.5 mt-3">
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: card.stage === 'brief_review' ? 'var(--warning)' : 'var(--accent)',
              display: 'inline-block',
            }}
          />
          <span
            style={{
              fontSize: 11,
              color: card.stage === 'brief_review' ? 'var(--warning)' : 'var(--accent)',
            }}
          >
            {card.stageLabel}
          </span>
        </div>
      )}
    </div>
  );
}
