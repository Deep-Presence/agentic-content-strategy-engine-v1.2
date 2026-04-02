'use client';

import type { ContentCard } from './types';

function QueueSidebar({ card }: { card: ContentCard }) {
  return (
    <div className="p-4 space-y-4">
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>
        Opportunity Summary
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Gap score</span>
          <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--error)' }}>
            ~{Math.round(card.gap * 100)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Priority</span>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--warning)' }}>{card.priority}</span>
        </div>
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Read time</span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{card.readTime} min</span>
        </div>
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Competitor</span>
          <div className="flex items-center gap-1">
            <img
              src={`https://www.google.com/s2/favicons?domain=${card.competitor}&sz=32`}
              alt={card.competitor}
              width={12}
              height={12}
              style={{ borderRadius: 2 }}
            />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{card.competitor}</span>
          </div>
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Why this topic
        </div>
        <ul className="space-y-2">
          <li style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Competitors cited 3x more — significant gap opportunity
          </li>
          <li style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Topic trending across multiple AI engines
          </li>
          <li style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            High citation correlation for {card.type.replace('_', ' ').toLowerCase()} format
          </li>
        </ul>
      </div>
    </div>
  );
}

function BriefSidebar({ card }: { card: ContentCard }) {
  const brief = card.briefContent;
  if (!brief) return null;

  return (
    <div className="p-4 space-y-4">
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Brief Outline
        </div>
        <ol className="space-y-1" style={{ paddingLeft: 16 }}>
          {brief.sections.map((section, i) => (
            <li
              key={i}
              style={{
                fontSize: 12,
                color: 'var(--text-primary)',
                lineHeight: 1.6,
                cursor: 'pointer',
              }}
            >
              {section}
            </li>
          ))}
        </ol>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Sources Across AI Engines
        </div>
        <div className="space-y-2">
          {brief.sources.map((source) => (
            <div
              key={source.domain}
              className="flex items-center gap-2 p-2"
              style={{
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg)',
              }}
            >
              <img
                src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
                alt={source.domain}
                width={14}
                height={14}
                style={{ borderRadius: 2 }}
              />
              <div className="flex-1 min-w-0">
                <div className="truncate" style={{ fontSize: 11, color: 'var(--text-primary)' }}>{source.name}</div>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{source.domain}</div>
              </div>
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 600,
                  fontFamily: 'var(--font-mono)',
                  padding: '1px 5px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--accent-subtle)',
                  color: 'var(--accent)',
                }}
              >
                {source.engines} engines
              </span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Why We Picked This
        </div>
        <ul className="space-y-2">
          {brief.reasons.map((reason, i) => (
            <li key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {reason}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ArticleSidebar({ card, activeSection, onSectionClick }: {
  card: ContentCard;
  activeSection: number;
  onSectionClick: (index: number) => void;
}) {
  const sections = card.articleContent?.sections || [];

  return (
    <div className="p-4">
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
        Sections
      </div>
      <div className="space-y-0.5">
        {sections.map((section, i) => (
          <button
            key={i}
            onClick={() => onSectionClick(i)}
            className="w-full text-left"
            style={{
              padding: '6px 10px',
              fontSize: 12,
              color: activeSection === i ? 'var(--text-primary)' : 'var(--text-secondary)',
              fontWeight: activeSection === i ? 500 : 400,
              background: activeSection === i ? 'var(--accent-subtle)' : 'transparent',
              borderLeft: activeSection === i ? '2px solid var(--accent)' : '2px solid transparent',
              borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
              cursor: 'pointer',
              border: 'none',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              transition: 'all 0.15s',
            }}
          >
            <span className="truncate" style={{ marginRight: 8 }}>{section.heading}</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', flexShrink: 0 }}>
              {section.words}w
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function AgentSidebar({ card }: { card: ContentCard }) {
  const progress = card.agentProgress;
  if (!progress) return null;

  const stages = [
    { label: 'Planning', done: ['writing', 'evaluating', 'brief_generation'].includes(card.stage) || progress.pct > 0 },
    { label: 'Brief generation', done: ['writing', 'evaluating'].includes(card.stage) || (card.stage === 'brief_generation' && progress.pct === 100) },
    { label: 'Writing', done: card.stage === 'evaluating' || (card.stage === 'writing' && progress.pct === 100) },
    { label: 'Evaluation', done: card.stage === 'evaluating' && progress.pct === 100 },
  ];

  return (
    <div className="p-4 space-y-4">
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
        Agent Progress
      </div>

      <div className="space-y-2">
        {stages.map((stage) => (
          <div key={stage.label} className="flex items-center gap-2">
            <span
              style={{
                width: 14,
                height: 14,
                borderRadius: '50%',
                border: stage.done ? 'none' : '1px solid var(--border)',
                background: stage.done ? 'var(--success)' : 'transparent',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 8,
                color: '#fff',
                flexShrink: 0,
              }}
            >
              {stage.done && '\u2713'}
            </span>
            <span style={{ fontSize: 12, color: stage.done ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
              {stage.label}
            </span>
          </div>
        ))}
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>
          Current Task
        </div>
        <div style={{ fontSize: 12, color: 'var(--warning)', animation: 'typing 1.8s ease-in-out infinite' }}>
          {progress.currentTask}
        </div>
      </div>
    </div>
  );
}

interface LeftSidebarProps {
  card: ContentCard;
  activeSection: number;
  onSectionClick: (index: number) => void;
}

export function LeftSidebar({ card, activeSection, onSectionClick }: LeftSidebarProps) {
  return (
    <div
      className="overflow-y-auto h-full"
      style={{
        width: 260,
        borderRight: '1px solid var(--border)',
        background: 'var(--surface)',
        flexShrink: 0,
      }}
    >
      {card.stage === 'queue' && <QueueSidebar card={card} />}
      {card.stage === 'brief_review' && <BriefSidebar card={card} />}
      {card.stage === 'article_review' && (
        <ArticleSidebar card={card} activeSection={activeSection} onSectionClick={onSectionClick} />
      )}
      {card.column === 'agent' && <AgentSidebar card={card} />}
    </div>
  );
}
