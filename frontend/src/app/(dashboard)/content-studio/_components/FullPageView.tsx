'use client';

import { useState, useCallback } from 'react';
import { ArrowLeft } from 'lucide-react';
import type { ContentCard, ContentMetadata } from './types';
import { LeftSidebar } from './LeftSidebar';
import { RightSidebar } from './RightSidebar';
import { ArticleEditor } from './ArticleEditor';

const TYPE_LABELS: Record<string, string> = {
  HOW_TO: 'HOW-TO',
  COMPARISON: 'COMPARISON',
  GUIDE: 'GUIDE',
  LONG_BLOG: 'LONG BLOG',
  PILLAR_PAGE: 'PILLAR PAGE',
};

function stageBadge(card: ContentCard) {
  const stage = card.stage;
  let bg = 'var(--border)';
  let color = 'var(--text-secondary)';
  let pulse = false;

  if (stage === 'brief_review') { bg = 'var(--warning-subtle)'; color = 'var(--warning)'; }
  else if (stage === 'article_review') { bg = 'var(--accent-subtle)'; color = 'var(--accent)'; }
  else if (card.column === 'agent') { bg = 'var(--warning-subtle)'; color = 'var(--warning)'; pulse = true; }
  else if (stage === 'published') { bg = 'var(--success-subtle)'; color = 'var(--success)'; }

  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        textTransform: 'uppercase',
        padding: '2px 8px',
        borderRadius: 'var(--radius-full)',
        background: bg,
        color,
        animation: pulse ? 'pulse 2s ease-in-out infinite' : undefined,
      }}
    >
      {card.stageLabel}
    </span>
  );
}

interface FullPageViewProps {
  card: ContentCard;
  onClose: () => void;
  onAction: (action: 'start' | 'approve_brief' | 'approve_article' | 'publish' | 'send_back' | 'cancel') => void;
}

export function FullPageView({ card, onClose, onAction }: FullPageViewProps) {
  const [activeSection, setActiveSection] = useState(0);
  const [metadata, setMetadata] = useState<ContentMetadata>(
    card.metadata || {
      slug: '',
      metaTitle: card.title,
      metaDescription: '',
      canonicalUrl: '',
      schemaMarkup: false,
      tags: [],
    }
  );

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: 'var(--bg)', animation: 'slideUp 250ms ease' }}
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      {/* Top Bar */}
      <div
        className="flex items-center justify-between px-4 flex-shrink-0"
        style={{
          height: 52,
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="flex items-center gap-1"
            style={{
              height: 30,
              padding: '0 10px',
              fontSize: 12,
              fontWeight: 500,
              background: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
            }}
          >
            <ArrowLeft size={12} strokeWidth={1.5} />
            Back
          </button>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
              {card.title}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              {TYPE_LABELS[card.type]} · {card.cluster} · Score {card.score} · Gap ~{Math.round(card.gap * 100)}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {stageBadge(card)}
        </div>
      </div>

      {/* Agent working banner */}
      {card.column === 'agent' && card.agentProgress && (
        <div
          className="flex items-center gap-3 px-4 flex-shrink-0"
          style={{
            height: 44,
            background: 'var(--warning-subtle)',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--warning)' }}>Agent working:</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)', animation: 'typing 1.8s ease-in-out infinite' }}>
            {card.agentProgress.currentTask}
          </span>
          <div className="flex-1 max-w-[300px]" style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
            <div
              style={{
                width: `${card.agentProgress.pct}%`,
                height: '100%',
                background: 'var(--warning)',
                borderRadius: 3,
                animation: 'progressPulse 2.5s ease-in-out infinite',
              }}
            />
          </div>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
            {card.agentProgress.pct}%
          </span>
        </div>
      )}

      {/* Main content area */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left sidebar */}
        <LeftSidebar card={card} activeSection={activeSection} onSectionClick={setActiveSection} />

        {/* Center content */}
        <div className="flex-1 overflow-y-auto">
          {card.stage === 'queue' && <QueueContent card={card} />}
          {card.stage === 'brief_review' && <BriefContent card={card} />}
          {card.stage === 'article_review' && card.articleContent && (
            <ArticleEditor sections={card.articleContent.sections} />
          )}
          {card.column === 'agent' && <AgentContent card={card} />}
        </div>

        {/* Right sidebar */}
        <RightSidebar
          card={card}
          metadata={metadata}
          onMetadataChange={setMetadata}
          onPublish={() => onAction('publish')}
        />
      </div>

      {/* Bottom action bar */}
      <div
        className="flex items-center justify-end gap-2 px-4 flex-shrink-0"
        style={{
          height: 56,
          borderTop: '1px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        {card.stage === 'queue' && (
          <button
            onClick={() => onAction('start')}
            style={{
              height: 30,
              padding: '0 16px',
              fontSize: 12,
              fontWeight: 500,
              background: 'var(--accent)',
              color: 'var(--text-on-accent)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
            }}
          >
            Start Production
          </button>
        )}

        {card.stage === 'brief_review' && (
          <>
            <button
              onClick={() => onAction('send_back')}
              style={{
                height: 30,
                padding: '0 16px',
                fontSize: 12,
                fontWeight: 500,
                background: 'transparent',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              Send back
            </button>
            <button
              onClick={() => onAction('approve_brief')}
              style={{
                height: 30,
                padding: '0 16px',
                fontSize: 12,
                fontWeight: 500,
                background: 'var(--warning)',
                color: '#fff',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Approve brief
            </button>
          </>
        )}

        {card.stage === 'article_review' && (
          <>
            <button
              onClick={() => onAction('send_back')}
              style={{
                height: 30,
                padding: '0 16px',
                fontSize: 12,
                fontWeight: 500,
                background: 'transparent',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              Send back with feedback
            </button>
            <button
              onClick={() => onAction('approve_article')}
              style={{
                height: 30,
                padding: '0 16px',
                fontSize: 12,
                fontWeight: 500,
                background: 'var(--accent)',
                color: 'var(--text-on-accent)',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Approve
            </button>
            <button
              onClick={() => onAction('publish')}
              style={{
                height: 30,
                padding: '0 16px',
                fontSize: 12,
                fontWeight: 500,
                background: 'var(--success)',
                color: '#fff',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Publish
            </button>
          </>
        )}

        {card.column === 'agent' && (
          <button
            onClick={() => onAction('cancel')}
            style={{
              height: 30,
              padding: '0 16px',
              fontSize: 12,
              fontWeight: 500,
              background: 'transparent',
              border: '1px solid var(--error)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--error)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

function QueueContent({ card }: { card: ContentCard }) {
  return (
    <div className="p-6" style={{ maxWidth: 720, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
        {card.title}
      </h1>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 24 }}>
        This content opportunity was identified by the Content Planner based on gap analysis across AI engines.
        Starting production will begin the planning and brief generation phase.
      </p>

      <div
        className="grid grid-cols-2 gap-3"
      >
        {[
          { label: 'Gap Score', value: `~${Math.round(card.gap * 100)}`, color: 'var(--error)' },
          { label: 'Priority', value: card.priority, color: 'var(--warning)' },
          { label: 'Read Time', value: `${card.readTime} min`, color: 'var(--text-primary)' },
          { label: 'Competitor', value: card.competitor, color: 'var(--accent)' },
        ].map((item) => (
          <div
            key={item.label}
            className="p-3"
            style={{
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              background: 'var(--surface)',
            }}
          >
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>
              {item.label}
            </div>
            <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: item.color }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BriefContent({ card }: { card: ContentCard }) {
  const brief = card.briefContent;
  if (!brief) return null;

  return (
    <div className="p-6" style={{ maxWidth: 720, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
        {card.title}
      </h1>
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 24 }}>
        {card.id} · {card.cluster} · {TYPE_LABELS[card.type]}
      </div>

      {/* Why we picked this */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Why We Picked This
        </div>
        <div className="space-y-2">
          {brief.reasons.map((reason, i) => (
            <div
              key={i}
              className="flex items-start gap-2 p-3"
              style={{
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--surface)',
              }}
            >
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)', flexShrink: 0 }}>
                {i + 1}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {reason}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Key success indicators */}
      <div className="flex gap-3 mb-6">
        <div
          className="flex-1 p-3"
          style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}
        >
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>
            Target Words
          </div>
          <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
            {brief.targetWords.toLocaleString()}
          </div>
        </div>
        <div
          className="flex-1 p-3"
          style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}
        >
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>
            Exemplars
          </div>
          <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
            {brief.exemplarCount}
          </div>
        </div>
      </div>

      {/* Brief sections */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Proposed Sections
        </div>
        <div className="space-y-1">
          {brief.sections.map((section, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-2"
              style={{
                borderLeft: '2px solid var(--accent-subtle)',
                fontSize: 13,
                color: 'var(--text-primary)',
              }}
            >
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', width: 20 }}>
                {i + 1}.
              </span>
              {section}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AgentContent({ card }: { card: ContentCard }) {
  const progress = card.agentProgress;

  return (
    <div className="p-6" style={{ maxWidth: 720, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
        {card.title}
      </h1>

      <div
        className="p-4"
        style={{
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--surface)',
        }}
      >
        <div className="flex items-center justify-between mb-3">
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--warning)' }}>
            {card.stageLabel}
          </span>
          <span style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
            {progress?.pct}%
          </span>
        </div>

        <div style={{ height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden', marginBottom: 12 }}>
          <div
            style={{
              width: `${progress?.pct}%`,
              height: '100%',
              background: 'var(--warning)',
              borderRadius: 4,
              animation: 'progressPulse 2.5s ease-in-out infinite',
              transition: 'width 0.6s ease',
            }}
          />
        </div>

        {progress?.wordsCurrent !== undefined && (
          <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
            {progress.wordsCurrent.toLocaleString()} / {progress.wordsTarget?.toLocaleString()} words
            {progress.sectionsComplete !== undefined && (
              <span> · {progress.sectionsComplete}/{progress.sectionsTotal} sections</span>
            )}
          </div>
        )}

        <div className="mt-4 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', animation: 'typing 1.8s ease-in-out infinite' }}>
            {progress?.currentTask}
          </div>
        </div>
      </div>

      <div className="mt-6 text-center" style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>
        Content will be available for review once complete.
      </div>
    </div>
  );
}
