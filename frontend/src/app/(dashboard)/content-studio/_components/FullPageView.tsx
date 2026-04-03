'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { ArrowLeft, Play, CheckCircle, RotateCcw, Send, XCircle, Upload } from 'lucide-react';
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
        letterSpacing: '0.04em',
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
      {/* Top Bar with actions */}
      <div
        className="flex items-center justify-between px-4 flex-shrink-0"
        style={{
          height: 52,
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        {/* Left: Back + title */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <button
            onClick={onClose}
            className="flex items-center gap-1 flex-shrink-0"
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
          <div className="min-w-0">
            <div className="truncate" style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
              {card.title}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              {TYPE_LABELS[card.type]} · {card.cluster} · Score {card.score} · Gap ~{Math.round(card.gap * 100)}
            </div>
          </div>
        </div>

        {/* Right: stage badge + action buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {stageBadge(card)}

          <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 4px' }} />

          {card.stage === 'queue' && (
            <button
              onClick={() => onAction('start')}
              className="flex items-center gap-1.5"
              style={{
                height: 30,
                padding: '0 14px',
                fontSize: 12,
                fontWeight: 500,
                background: 'var(--accent)',
                color: 'var(--text-on-accent)',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              <Play size={11} strokeWidth={2} />
              Start Production
            </button>
          )}

          {card.stage === 'brief_review' && (
            <>
              <button
                onClick={() => onAction('send_back')}
                className="flex items-center gap-1.5"
                style={{
                  height: 30,
                  padding: '0 12px',
                  fontSize: 12,
                  fontWeight: 500,
                  background: 'transparent',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                <RotateCcw size={11} strokeWidth={1.5} />
                Send back
              </button>
              <button
                onClick={() => onAction('approve_brief')}
                className="flex items-center gap-1.5"
                style={{
                  height: 30,
                  padding: '0 14px',
                  fontSize: 12,
                  fontWeight: 500,
                  background: 'var(--accent)',
                  color: 'var(--text-on-accent)',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                }}
              >
                <CheckCircle size={11} strokeWidth={2} />
                Approve Brief
              </button>
            </>
          )}

          {card.stage === 'article_review' && (
            <>
              <button
                onClick={() => onAction('send_back')}
                className="flex items-center gap-1.5"
                style={{
                  height: 30,
                  padding: '0 12px',
                  fontSize: 12,
                  fontWeight: 500,
                  background: 'transparent',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                <Send size={11} strokeWidth={1.5} />
                Send back
              </button>
              <button
                onClick={() => onAction('approve_article')}
                className="flex items-center gap-1.5"
                style={{
                  height: 30,
                  padding: '0 14px',
                  fontSize: 12,
                  fontWeight: 500,
                  background: 'var(--accent)',
                  color: 'var(--text-on-accent)',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                }}
              >
                <CheckCircle size={11} strokeWidth={2} />
                Approve
              </button>
              <button
                onClick={() => onAction('publish')}
                className="flex items-center gap-1.5"
                style={{
                  height: 30,
                  padding: '0 14px',
                  fontSize: 12,
                  fontWeight: 500,
                  background: 'var(--success)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                }}
              >
                <Upload size={11} strokeWidth={2} />
                Publish
              </button>
            </>
          )}

          {card.column === 'agent' && (
            <button
              onClick={() => onAction('cancel')}
              className="flex items-center gap-1.5"
              style={{
                height: 30,
                padding: '0 12px',
                fontSize: 12,
                fontWeight: 500,
                background: 'transparent',
                border: '1px solid var(--error)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--error)',
                cursor: 'pointer',
              }}
            >
              <XCircle size={11} strokeWidth={1.5} />
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Agent working banner */}
      {card.column === 'agent' && card.agentProgress && (
        <div
          className="flex items-center gap-3 px-4 flex-shrink-0"
          style={{
            height: 40,
            background: 'var(--warning-subtle)',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'var(--warning)',
              animation: 'pulse 1.5s ease-in-out infinite',
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--warning)' }}>Agent working:</span>
          <span style={{ fontSize: 11, color: 'var(--text-primary)', animation: 'typing 1.8s ease-in-out infinite' }}>
            {card.agentProgress.currentTask}
          </span>
          <div className="flex-1" />
          <div style={{ width: 200, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
            <div
              style={{
                width: `${card.agentProgress.pct}%`,
                height: '100%',
                background: 'var(--warning)',
                borderRadius: 2,
                animation: 'progressPulse 2.5s ease-in-out infinite',
                transition: 'width 0.6s ease',
              }}
            />
          </div>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--warning)' }}>
            {card.agentProgress.pct}%
          </span>
        </div>
      )}

      {/* Main content area */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <LeftSidebar card={card} activeSection={activeSection} onSectionClick={setActiveSection} />

        <div className="flex-1 overflow-y-auto">
          {card.stage === 'queue' && <QueueContent card={card} />}
          {card.stage === 'brief_review' && <BriefContent card={card} />}
          {card.stage === 'article_review' && card.articleContent && (
            <ArticleEditor sections={card.articleContent.sections} />
          )}
          {card.column === 'agent' && <AgentContent card={card} />}
        </div>

        <RightSidebar
          card={card}
          metadata={metadata}
          onMetadataChange={setMetadata}
          onPublish={() => onAction('publish')}
        />
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

      <div className="grid grid-cols-2 gap-3">
        {[
          { label: 'Gap Score', value: `~${Math.round(card.gap * 100)}`, color: 'var(--error)' },
          { label: 'Priority', value: card.priority, color: 'var(--warning)' },
          { label: 'Read Time', value: `${card.readTime} min`, color: 'var(--text-primary)' },
          { label: 'Competitor', value: card.competitor, color: 'var(--accent)', icon: true },
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
            <div className="flex items-center gap-2">
              {'icon' in item && item.icon && (
                <img
                  src={`https://www.google.com/s2/favicons?domain=${card.competitor}&sz=32`}
                  alt={card.competitor}
                  width={16}
                  height={16}
                  style={{ borderRadius: 3 }}
                />
              )}
              <span style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: item.color }}>
                {item.value}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Opportunity details */}
      <div className="mt-6 p-4" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 10 }}>
          What the agent will do
        </div>
        <div className="space-y-3">
          {[
            { step: '1', label: 'Analyze query scorecards', desc: 'Review 200+ queries across 5 AI engines for gap patterns' },
            { step: '2', label: 'Research exemplars', desc: 'Study top-cited content from competitors for structural patterns' },
            { step: '3', label: 'Generate content brief', desc: 'Create section outline, target metrics, and citation strategy' },
            { step: '4', label: 'Submit for review', desc: 'Brief moves to Your Review for approval before writing begins' },
          ].map((item) => (
            <div key={item.step} className="flex items-start gap-3">
              <span style={{
                width: 20,
                height: 20,
                borderRadius: '50%',
                background: 'var(--accent-subtle)',
                color: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                flexShrink: 0,
              }}>
                {item.step}
              </span>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>{item.label}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.4 }}>{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
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

      <div className="flex gap-3 mb-6">
        <div className="flex-1 p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>
            Target Words
          </div>
          <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
            {brief.targetWords.toLocaleString()}
          </div>
        </div>
        <div className="flex-1 p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>
            Exemplars
          </div>
          <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
            {brief.exemplarCount}
          </div>
        </div>
      </div>

      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
          Proposed Sections
        </div>
        <div className="space-y-1">
          {brief.sections.map((section, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-2"
              style={{ borderLeft: '2px solid var(--accent-subtle)', fontSize: 13, color: 'var(--text-primary)' }}
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

// Agent activity log messages for simulation
const AGENT_LOGS: Record<string, string[]> = {
  planning: [
    'Fetching query scorecards from gap analysis...',
    'Analyzing 200 queries across 5 AI engines',
    'Clustering queries by intent and topic affinity',
    'Identifying citation patterns in competitor content',
    'Scoring content opportunity by gap severity',
    'Mapping competitor exemplar structures',
    'Generating content angle recommendations',
    'Finalizing planning analysis...',
  ],
  brief_generation: [
    'Loading exemplar content for structural analysis...',
    'Parsing 3 top-performing exemplars',
    'Extracting header patterns and section flow',
    'Analyzing citation density per section',
    'Computing optimal word count distribution',
    'Generating section-by-section outline',
    'Adding source attribution targets',
    'Compiling brief document...',
  ],
  writing: [
    'Initializing content generation engine...',
    'Loading voice style guide parameters',
    'Writing introduction with hook and thesis',
    'Integrating citation anchors for AI engines',
    'Cross-referencing claims with source material',
    'Optimizing header hierarchy for scannability',
    'Adding statistical evidence and data points',
    'Inserting internal link opportunities',
    'Writing conclusion with actionable takeaways',
    'Running structural compliance pre-check...',
  ],
  evaluating: [
    'Running structural evaluation (pass 1)...',
    'Checking header-to-content ratio: 0.82',
    'Analyzing semantic density per paragraph',
    'Evaluating citation placement patterns',
    'Computing E-E-A-T signal strength',
    'Running voice compliance check: 78%',
    'Checking stat/data point density',
    'Running final scoring algorithm...',
  ],
};

function AgentContent({ card }: { card: ContentCard }) {
  const progress = card.agentProgress;
  const [logs, setLogs] = useState<string[]>([]);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const stageLogs = AGENT_LOGS[card.stage] || AGENT_LOGS.writing;

  useEffect(() => {
    const pct = progress?.pct || 0;
    const logsToShow = Math.max(1, Math.ceil((pct / 100) * stageLogs.length));
    setLogs(stageLogs.slice(0, logsToShow));
  }, [progress?.pct, stageLogs]);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const stageSteps = [
    { key: 'planning', label: 'Planning', desc: 'Analyzing queries & exemplars' },
    { key: 'brief_generation', label: 'Brief Generation', desc: 'Creating content brief' },
    { key: 'writing', label: 'Writing', desc: 'Generating article content' },
    { key: 'evaluating', label: 'Evaluation', desc: 'Scoring & compliance check' },
  ];

  const stageOrder = ['planning', 'brief_generation', 'writing', 'evaluating'];
  const currentIdx = stageOrder.indexOf(card.stage);

  return (
    <div className="p-6" style={{ maxWidth: 760, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 20 }}>
        {card.title}
      </h1>

      {/* Progress header */}
      <div
        className="p-4 mb-4"
        style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: 'var(--warning)',
                animation: 'pulse 1.5s ease-in-out infinite',
              }}
            />
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
              {card.stageLabel}
            </span>
          </div>
          <span style={{ fontSize: 22, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
            {progress?.pct}%
          </span>
        </div>
        <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', marginBottom: 10 }}>
          <div
            style={{
              width: `${progress?.pct}%`,
              height: '100%',
              background: (progress?.pct || 0) > 80 ? 'var(--success)' : (progress?.pct || 0) >= 50 ? 'var(--accent)' : 'var(--warning)',
              borderRadius: 3,
              animation: 'progressPulse 2.5s ease-in-out infinite',
              transition: 'width 0.6s ease',
            }}
          />
        </div>
        {progress?.wordsCurrent !== undefined && (
          <div className="flex items-center gap-4" style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
            <span>{progress.wordsCurrent.toLocaleString()} / {progress.wordsTarget?.toLocaleString()} words</span>
            {progress.sectionsComplete !== undefined && (
              <span>{progress.sectionsComplete}/{progress.sectionsTotal} sections</span>
            )}
          </div>
        )}
      </div>

      {/* Pipeline stages */}
      <div
        className="p-4 mb-4"
        style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
      >
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 12 }}>
          Pipeline Progress
        </div>
        <div className="flex items-start gap-0">
          {stageSteps.map((step, i) => {
            const idx = stageOrder.indexOf(step.key);
            const done = idx < currentIdx;
            const active = idx === currentIdx;
            const upcoming = idx > currentIdx;

            return (
              <div key={step.key} className="flex-1 flex flex-col items-center text-center" style={{ position: 'relative' }}>
                {/* Connector line */}
                {i > 0 && (
                  <div style={{
                    position: 'absolute',
                    top: 12,
                    right: '50%',
                    width: '100%',
                    height: 2,
                    background: done || active ? 'var(--accent)' : 'var(--border)',
                    zIndex: 0,
                  }} />
                )}
                {/* Circle */}
                <div style={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  background: done ? 'var(--success)' : active ? 'var(--warning)' : 'var(--border)',
                  border: active ? '2px solid var(--warning)' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 10,
                  fontWeight: 600,
                  color: done || active ? '#fff' : 'var(--text-tertiary)',
                  position: 'relative',
                  zIndex: 1,
                  animation: active ? 'pulse 2s ease-in-out infinite' : undefined,
                }}>
                  {done ? '\u2713' : i + 1}
                </div>
                <div style={{ fontSize: 11, fontWeight: active ? 500 : 400, color: active ? 'var(--text-primary)' : upcoming ? 'var(--text-tertiary)' : 'var(--text-primary)', marginTop: 6 }}>
                  {step.label}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>
                  {step.desc}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Agent activity log */}
      <div
        className="p-4"
        style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
      >
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 10 }}>
          Agent Activity
        </div>
        <div
          ref={logContainerRef}
          className="space-y-1.5"
          style={{ maxHeight: 240, overflowY: 'auto' }}
        >
          {logs.map((log, i) => {
            const isLatest = i === logs.length - 1;
            return (
              <div key={i} className="flex items-start gap-2" style={{ animation: isLatest ? 'fadeUp 300ms ease' : undefined }}>
                <span style={{
                  width: 4,
                  height: 4,
                  borderRadius: '50%',
                  background: isLatest ? 'var(--warning)' : 'var(--success)',
                  marginTop: 5,
                  flexShrink: 0,
                  animation: isLatest ? 'pulse 1.5s ease-in-out infinite' : undefined,
                }} />
                <span style={{
                  fontSize: 11,
                  fontFamily: 'var(--font-mono)',
                  color: isLatest ? 'var(--text-primary)' : 'var(--text-tertiary)',
                  lineHeight: 1.5,
                  animation: isLatest ? 'typing 1.8s ease-in-out infinite' : undefined,
                }}>
                  {log}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
