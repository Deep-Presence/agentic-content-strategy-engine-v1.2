'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { ArrowLeft, Play, CheckCircle, RotateCcw, Send, XCircle, Upload, RefreshCw } from 'lucide-react';
import type { ContentCard, ContentMetadata, ReviewComment } from './types';
import { getColumn, getDisplay, getHITLActions, getWorkerStepIndex } from '../_lib/status-adapter';
import { useBriefDetail } from '../_hooks/useBriefDetail';
import { useGapSummary } from '../_hooks/useGapSummary';
import { useCardActivity } from '../_hooks/useCardActivity';
import type { GapSummaryResponseAPI } from '../_lib/types';
import { fetchReviewDraftContent, saveReviewDraftContent } from '../_lib/api';
import { LeftSidebar } from './LeftSidebar';
import { RightSidebar } from './RightSidebar';
import { ArticleEditor } from './ArticleEditor';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/hooks/useAuth';

const TYPE_LABELS: Record<string, string> = {
  HOW_TO: 'HOW-TO',
  COMPARISON: 'COMPARISON',
  GUIDE: 'GUIDE',
  LONG_BLOG: 'LONG BLOG',
  PILLAR_PAGE: 'PILLAR PAGE',
};

function stageBadge(card: ContentCard) {
  const display = getDisplay(card.status);

  const variantMap: Record<string, { bg: string; color: string }> = {
    neutral: { bg: 'var(--border)', color: 'var(--text-secondary)' },
    teal: { bg: 'var(--accent-subtle)', color: 'var(--accent)' },
    amber: { bg: 'var(--warning-subtle)', color: 'var(--warning)' },
    success: { bg: 'var(--success-subtle)', color: 'var(--success)' },
    error: { bg: 'var(--error-subtle, var(--border))', color: 'var(--error)' },
  };

  const { bg, color } = variantMap[display.badgeVariant] || variantMap.neutral;

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
        animation: display.isAgentActive ? 'pulse 2s ease-in-out infinite' : undefined,
        letterSpacing: '0.04em',
      }}
    >
      {display.label}
    </span>
  );
}

type ActionType = 'start' | 'start_production' | 'approve_brief' | 'approve_article' | 'publish' | 'send_back' | 'cancel' | 'retry';

interface FullPageViewProps {
  card: ContentCard;
  onClose: () => void;
  onAction: (action: ActionType, data?: { editorNotes?: string; contentMarkdown?: string }) => void | Promise<void>;
}

function compileEditorNotes(comments: ReviewComment[], overall: string): string {
  const parts: string[] = [];
  if (comments.length > 0) {
    parts.push('## Inline Comments\n');
    comments.forEach((c, i) => {
      const snippet = c.selectedText.length > 100 ? c.selectedText.slice(0, 100) + '...' : c.selectedText;
      parts.push(`[${i + 1}] "${snippet}" → Change: ${c.feedback}`);
    });
  }
  if (overall.trim()) {
    parts.push('\n## Overall Review\n');
    parts.push(overall.trim());
  }
  return parts.length > 0 ? parts.join('\n') : 'Needs revision';
}

function draftStorageKey(companySlug: string, briefId: string, runId: string): string {
  return `content-studio:draft:${companySlug}:${briefId}:${runId}`;
}

export function FullPageView({ card, onClose, onAction }: FullPageViewProps) {
  const { companySlug } = useAuth();
  const [activeSection, setActiveSection] = useState(0);
  const [reviewComments, setReviewComments] = useState<ReviewComment[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleActionGuarded = useCallback(
    async (action: ActionType, data?: { editorNotes?: string; contentMarkdown?: string }) => {
      if (isSubmitting) return;
      setIsSubmitting(true);
      try {
        await onAction(action, data);
      } finally {
        setIsSubmitting(false);
      }
    },
    [isSubmitting, onAction],
  );
  const [overallReview, setOverallReview] = useState('');
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
  const [articleDraftMarkdown, setArticleDraftMarkdown] = useState<string | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isDraftLoading, setIsDraftLoading] = useState(false);
  const lastSavedDraftRef = useRef<string | null>(null);

  // Guard: GA-phase cards use ta-{uuid} IDs — no brief detail endpoint exists
  const isGAPhase = card.status === 'gap_analysis_pending' || card.status === 'gap_analysis' || card.status === 'gap_analysis_complete' || card.status === 'content_queued';
  const briefIdForDetail = isGAPhase ? null : card.id;

  // Load brief detail + article content on demand
  const {
    briefContent: loadedBrief,
    articleContent: loadedArticle,
    isLoading: detailLoading,
    error: detailError,
  } = useBriefDetail(briefIdForDetail);

  // Use loaded data, falling back to card-level data (from SSE/mock)
  const briefContent = loadedBrief || card.briefContent || null;
  const articleContent = loadedArticle || card.articleContent || null;

  // Load gap analysis summary (for gap metrics display)
  const productSlug = card.effectiveSlug?.includes('__')
    ? card.effectiveSlug.split('__')[1]
    : undefined;
  const shouldFetchGapSummary = !card.gapContext && (
    card.status === 'gap_analysis_complete' || card.status === 'content_queued' || !isGAPhase
  );
  const {
    data: gapSummary,
    isLoading: gapSummaryLoading,
  } = useGapSummary(
    shouldFetchGapSummary,
    productSlug,
    card.gaRunId,
  );
  const {
    items: activityItems,
    isLoading: activityLoading,
    sourceKind: activitySourceKind,
  } = useCardActivity(card.effectiveSlug ?? null, card.topicRunId ?? null);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  }, [onClose]);

  const column = getColumn(card.status);
  const display = getDisplay(card.status);
  const hitl = getHITLActions(card.status);

  // Determine which content view to show
  const showGAPhase = isGAPhase;
  const showQueue = !isGAPhase && card.status === 'suggested';
  const showBrief = card.status === 'brief_review' || card.status === 'pending_brief_approval';
  const showReview = card.status === 'review' || card.status === 'pending_content_approval';
  const showArticle = showReview && articleContent;
  const showReviewFallback = showReview && !articleContent;
  const showAgent = !isGAPhase && column === 'agent';
  const showDone = column === 'done';
  const currentReviewMarkdown = articleDraftMarkdown ?? articleContent?.markdown ?? null;
  const isDraftDirty = !!(
    showReview &&
    currentReviewMarkdown &&
    currentReviewMarkdown !== lastSavedDraftRef.current
  );

  useEffect(() => {
    if (!showReview || !articleContent?.markdown || !card.taskId || !companySlug) {
      setArticleDraftMarkdown(null);
      setDraftError(null);
      setIsDraftLoading(false);
      lastSavedDraftRef.current = articleContent?.markdown ?? null;
      return;
    }

    const controller = new AbortController();
    const taskId = card.taskId;
    const storageKey = draftStorageKey(companySlug, card.id, taskId);
    let isActive = true;

    setIsDraftLoading(true);
    setDraftError(null);

    (async () => {
      try {
        const localDraft = window.localStorage.getItem(storageKey);
        let remoteDraft: string | null = null;
        try {
          const remote = await fetchReviewDraftContent(taskId, card.id, controller.signal);
          remoteDraft = remote.content_markdown;
        } catch (err) {
          if (!(err instanceof ApiError) || err.status !== 404) {
            throw err;
          }
        }
        if (!isActive || controller.signal.aborted) return;

        const initialDraft = localDraft || remoteDraft || articleContent.markdown;
        setArticleDraftMarkdown(initialDraft);
        lastSavedDraftRef.current = remoteDraft || articleContent.markdown;
      } catch (err) {
        if (!isActive || (err instanceof DOMException && err.name === 'AbortError')) return;
        const message = err instanceof Error ? err.message : 'Failed to load saved review draft.';
        setDraftError(message);
        setArticleDraftMarkdown(articleContent.markdown);
        lastSavedDraftRef.current = articleContent.markdown;
      } finally {
        if (isActive && !controller.signal.aborted) {
          setIsDraftLoading(false);
        }
      }
    })();

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [showReview, articleContent?.markdown, card.id, card.taskId, companySlug]);

  useEffect(() => {
    if (!showReview || !articleDraftMarkdown || !card.taskId || !companySlug) return;
    window.localStorage.setItem(
      draftStorageKey(companySlug, card.id, card.taskId),
      articleDraftMarkdown,
    );
  }, [showReview, articleDraftMarkdown, card.id, card.taskId, companySlug]);

  useEffect(() => {
    if (!showReview || !articleDraftMarkdown || !card.taskId || !isDraftDirty) return;

    const intervalId = window.setInterval(async () => {
      try {
        await saveReviewDraftContent(card.taskId!, card.id, articleDraftMarkdown);
        lastSavedDraftRef.current = articleDraftMarkdown;
        setDraftError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to autosave review draft.';
        setDraftError(message);
      }
    }, 5 * 60 * 1000);

    return () => window.clearInterval(intervalId);
  }, [showReview, articleDraftMarkdown, card.id, card.taskId, isDraftDirty]);

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

          {hitl.canStart && (
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

          {hitl.canStartProduction && (
            <button
              onClick={() => onAction('start_production')}
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

          {hitl.canApproveBrief && (
            <>
              <button
                onClick={() => handleActionGuarded('send_back')}
                disabled={isSubmitting}
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
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  opacity: isSubmitting ? 0.5 : undefined,
                }}
              >
                <RotateCcw size={11} strokeWidth={1.5} />
                Send back
              </button>
              <button
                onClick={() => handleActionGuarded('approve_brief')}
                disabled={isSubmitting}
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
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  opacity: isSubmitting ? 0.5 : undefined,
                }}
              >
                <CheckCircle size={11} strokeWidth={2} />
                Approve Brief
              </button>
            </>
          )}

          {hitl.canApproveContent && (
            <>
              <button
                onClick={() => {
                  const notes = compileEditorNotes(reviewComments, overallReview);
                  handleActionGuarded('send_back', {
                    editorNotes: notes,
                    contentMarkdown: currentReviewMarkdown ?? undefined,
                  });
                }}
                disabled={isSubmitting}
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
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  opacity: isSubmitting ? 0.5 : undefined,
                }}
              >
                <Send size={11} strokeWidth={1.5} />
                Send back
              </button>
              <button
                onClick={() => handleActionGuarded('approve_article', {
                  contentMarkdown: currentReviewMarkdown ?? undefined,
                })}
                disabled={isSubmitting}
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
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  opacity: isSubmitting ? 0.5 : undefined,
                }}
              >
                <CheckCircle size={11} strokeWidth={2} />
                Approve
              </button>
              <button
                onClick={() => onAction('publish', {
                  contentMarkdown: currentReviewMarkdown ?? undefined,
                })}
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

          {hitl.canRetry && (
            <button
              onClick={() => onAction('retry')}
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
              <RefreshCw size={11} strokeWidth={2} />
              Retry
            </button>
          )}

          {display.isAgentActive && (
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

      {/* Main content area */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <LeftSidebar
          card={{
            ...card,
            briefContent: briefContent ?? undefined,
            articleContent: articleContent ?? undefined,
          }}
          activeSection={activeSection}
          onSectionClick={setActiveSection}
        />

        <div className="flex-1 overflow-y-auto">
          {detailLoading && !showQueue && !showAgent && !showGAPhase && (
            <div className="flex items-center justify-center py-12" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
              Loading content...
            </div>
          )}
          {showGAPhase && <GapAnalysisView card={card} onAction={onAction} gapSummary={gapSummary} gapSummaryLoading={gapSummaryLoading} />}
          {showQueue && <QueueContent card={card} />}
          {showBrief && <BriefContent card={{ ...card, briefContent: briefContent ?? undefined }} />}
          {showArticle && articleContent && (
            <ArticleEditor
              sections={articleContent.sections}
              initialMarkdown={currentReviewMarkdown ?? articleContent.markdown}
              isReviewMode={hitl.canApproveContent}
              comments={reviewComments}
              onCommentsChange={setReviewComments}
              overallReview={overallReview}
              onOverallReviewChange={setOverallReview}
              onMarkdownChange={setArticleDraftMarkdown}
            />
          )}
          {showReviewFallback && (
            <ReviewContentFallback
              title={card.title}
              isLoading={detailLoading || isDraftLoading}
              error={draftError || detailError}
            />
          )}
          {showAgent && <AgentContent card={card} />}
          {showDone && <DoneContent card={card} />}
        </div>

        <RightSidebar
          card={{ ...card, articleContent: articleContent ?? undefined, briefContent: briefContent ?? undefined }}
          gapSummary={gapSummary ?? undefined}
          activityItems={activityItems}
          activityLoading={activityLoading}
          activitySourceKind={activitySourceKind}
          metadata={metadata}
          onMetadataChange={setMetadata}
          onPublish={() => onAction('publish', {
            contentMarkdown: currentReviewMarkdown ?? undefined,
          })}
          exportMarkdown={currentReviewMarkdown ?? articleContent?.markdown ?? null}
        />
      </div>
    </div>
  );
}

function ReviewContentFallback({
  title,
  isLoading,
  error,
}: {
  title: string;
  isLoading: boolean;
  error: string | null;
}) {
  return (
    <div className="p-6" style={{ maxWidth: 720, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
        {title}
      </h1>
      <div
        className="p-4"
        style={{
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--surface)',
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'var(--text-tertiary)',
            marginBottom: 8,
          }}
        >
          Final Review
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {isLoading
            ? 'Loading the final article for review...'
            : error || 'The article is ready for review, but the final content has not loaded yet.'}
        </div>
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
                width: 20, height: 20, borderRadius: '50%',
                background: 'var(--accent-subtle)', color: 'var(--accent)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 10, fontWeight: 600, fontFamily: 'var(--font-mono)', flexShrink: 0,
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
            <div key={i} className="flex items-start gap-2 p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)', flexShrink: 0 }}>{i + 1}</span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{reason}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-3 mb-6">
        <div className="flex-1 p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Target Words</div>
          <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{brief.targetWords.toLocaleString()}</div>
        </div>
        <div className="flex-1 p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Exemplars</div>
          <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{brief.exemplarCount}</div>
        </div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>Proposed Sections</div>
        <div className="space-y-1">
          {brief.sections.map((section, i) => (
            <div key={i} className="flex items-center gap-2 px-3 py-2" style={{ borderLeft: '2px solid var(--accent-subtle)', fontSize: 13, color: 'var(--text-primary)' }}>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', width: 20 }}>{i + 1}.</span>
              {section}
            </div>
          ))}
        </div>
      </div>

      {/* Exemplars — enriched sources with structural detail */}
      {brief.sources.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 8 }}>Exemplars</div>
          <div className="space-y-2">
            {brief.sources.map((src, i) => (
              <div key={i} className="flex items-start gap-3 p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
                {src.domain && (
                  <img
                    src={`https://www.google.com/s2/favicons?domain=${src.domain}&sz=32`}
                    alt={src.domain}
                    width={16}
                    height={16}
                    style={{ borderRadius: 2, marginTop: 1, flexShrink: 0 }}
                  />
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate" style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 2 }}>
                    {src.domain || src.name}
                  </div>
                  {src.url && (
                    <div className="truncate" style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                      {src.url}
                    </div>
                  )}
                  <div className="flex items-center gap-2 flex-wrap">
                    {src.authorityType && (
                      <span style={{
                        fontSize: 9, fontWeight: 600, textTransform: 'capitalize',
                        padding: '1px 6px', borderRadius: 'var(--radius-full)',
                        border: '1px solid var(--border)', color: 'var(--text-secondary)',
                      }}>
                        {src.authorityType.replace(/_/g, ' ')}
                      </span>
                    )}
                    {src.wordCount != null && src.wordCount > 0 && (
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>
                        {src.wordCount.toLocaleString()} words
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Pipeline step definitions for agent view — aligned with backend worker chain
const PIPELINE_STEPS = [
  { key: 'briefing', label: 'Brief', desc: 'Building brief' },
  { key: 'outlining', label: 'Outline', desc: 'Section structure' },
  { key: 'drafting', label: 'Draft', desc: 'Content creation' },
  { key: 'linking', label: 'Link', desc: 'Internal links' },
  { key: 'enriching', label: 'Enrich', desc: 'Fact checking' },
  { key: 'evaluating', label: 'Evaluate', desc: 'Quality scoring' },
] as const;

// Agent activity log messages for simulation
const AGENT_LOGS: Record<string, string[]> = {
  briefing: [
    'Loading exemplar content for structural analysis...',
    'Parsing top-performing exemplars',
    'Extracting header patterns and section flow',
    'Analyzing citation density per section',
    'Computing optimal word count distribution',
    'Generating section-by-section outline',
    'Adding source attribution targets',
    'Compiling brief document...',
  ],
  outlining: [
    'Analyzing brief requirements...',
    'Generating content outline from blueprint',
    'Structuring sections with target word counts',
    'Mapping key topics to sections',
    'Finalizing outline structure...',
  ],
  drafting: [
    'Initializing content generation engine...',
    'Loading voice style guide parameters',
    'Writing introduction with hook and thesis',
    'Integrating citation anchors for AI engines',
    'Cross-referencing claims with source material',
    'Optimizing header hierarchy for scannability',
    'Adding statistical evidence and data points',
    'Writing conclusion with actionable takeaways',
  ],
  linking: [
    'Scanning content for link opportunities...',
    'Resolving internal link targets',
    'Inserting external citation links',
    'Validating link relevance scores',
  ],
  enriching: [
    'Running fact verification pipeline...',
    'Cross-checking claims against sources',
    'Adding verified statistics and data points',
    'Enriching with additional citations...',
  ],
  evaluating: [
    'Running structural evaluation...',
    'Checking header-to-content ratio',
    'Analyzing semantic density per paragraph',
    'Evaluating citation placement patterns',
    'Computing E-E-A-T signal strength',
    'Running voice compliance check',
    'Running final scoring algorithm...',
  ],
  revising: [
    'Incorporating evaluation feedback...',
    'Revising failed dimensions',
    'Re-drafting targeted sections',
    'Running fact re-verification...',
  ],
  approved: [
    'Brief approved — queuing for worker chain...',
  ],
};

function AgentContent({ card }: { card: ContentCard }) {
  const progress = card.agentProgress;
  const stepIndex = getWorkerStepIndex(card.status);

  const currentLogs = AGENT_LOGS[card.status] || AGENT_LOGS.drafting;
  const pct = progress?.pct || 0;
  const logsToShow = Math.max(1, Math.ceil((pct / 100) * currentLogs.length));
  const logs = currentLogs.slice(0, logsToShow);

  return (
    <div className="p-6" style={{ maxWidth: 760, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 20 }}>
        {card.title}
      </h1>

      {/* Pipeline stages — aligned with backend worker chain */}
      <div className="p-4 mb-4" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 12 }}>
          Pipeline Progress
        </div>
        <div className="flex items-start gap-0">
          {PIPELINE_STEPS.map((step, i) => {
            const done = stepIndex > i + 1; // +1 because AGENT_STEPS starts with 'briefing' at 0
            const active = PIPELINE_STEPS[i].key === card.status;
            return (
              <div key={step.key} className="flex-1 flex flex-col items-center text-center" style={{ position: 'relative' }}>
                {i > 0 && (
                  <div style={{
                    position: 'absolute', top: 12, right: '50%', width: '100%', height: 2,
                    background: done || active ? 'var(--accent)' : 'var(--border)', zIndex: 0,
                  }} />
                )}
                <div style={{
                  width: 24, height: 24, borderRadius: '50%',
                  background: done ? 'var(--success)' : active ? 'var(--warning)' : 'var(--border)',
                  border: active ? '2px solid var(--warning)' : 'none',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 600, color: done || active ? '#fff' : 'var(--text-tertiary)',
                  position: 'relative', zIndex: 1,
                  animation: active ? 'pulse 2s ease-in-out infinite' : undefined,
                }}>
                  {done ? '\u2713' : i + 1}
                </div>
                <div style={{ fontSize: 11, fontWeight: active ? 500 : 400, color: active ? 'var(--text-primary)' : done ? 'var(--text-primary)' : 'var(--text-tertiary)', marginTop: 6 }}>
                  {step.label}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>{step.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Agent activity log */}
      <div className="p-4" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 10 }}>
          Agent Activity
        </div>
        <div className="space-y-1.5" style={{ maxHeight: 240, overflowY: 'auto' }}>
          {logs.map((log, i) => {
            const isLatest = i === logs.length - 1;
            return (
              <div key={i} className="flex items-start gap-2" style={{ animation: isLatest ? 'fadeUp 300ms ease' : undefined }}>
                <span style={{
                  width: 4, height: 4, borderRadius: '50%',
                  background: isLatest ? 'var(--warning)' : 'var(--success)',
                  marginTop: 5, flexShrink: 0,
                  animation: isLatest ? 'pulse 1.5s ease-in-out infinite' : undefined,
                }} />
                <span style={{
                  fontSize: 11, fontFamily: 'var(--font-mono)',
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

// ---------------------------------------------------------------------------
// GA analysis animation (abstract — no internal step names exposed)
// ---------------------------------------------------------------------------

function GapAnalysisView({ card, onAction, gapSummary, gapSummaryLoading }: {
  card: ContentCard;
  onAction: (action: 'start_production') => void;
  gapSummary: GapSummaryResponseAPI | null;
  gapSummaryLoading: boolean;
}) {
  const progress = card.agentProgress;
  const currentStepNum = progress?.gaStepNum ?? 0;
  const totalSteps = progress?.gaTotalSteps ?? 8;

  const buyerStageColors: Record<string, { bg: string; color: string; border: string }> = {
    tofu: { bg: 'var(--accent-subtle)', color: 'var(--accent)', border: 'rgba(91,164,196,0.3)' },
    mofu: { bg: 'var(--warning-subtle)', color: 'var(--warning)', border: 'rgba(245,166,35,0.3)' },
    bofu: { bg: 'var(--success-subtle)', color: 'var(--success)', border: 'rgba(52,178,123,0.3)' },
  };
  const stageStyle = card.buyerStage ? buyerStageColors[card.buyerStage.toLowerCase()] : null;

  return (
    <div className="p-6" style={{ maxWidth: 760, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
        {card.title}
      </h1>
      <div className="flex items-center gap-2 mb-6" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
        <span>{card.cluster}</span>
        {card.buyerStage && stageStyle && (
          <>
            <span style={{ color: 'var(--border)' }}>·</span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                textTransform: 'uppercase',
                padding: '1px 6px',
                borderRadius: 'var(--radius-full)',
                background: stageStyle.bg,
                color: stageStyle.color,
                border: `1px solid ${stageStyle.border}`,
              }}
            >
              {card.buyerStage.toUpperCase()}
            </span>
          </>
        )}
        {card.source && (
          <>
            <span style={{ color: 'var(--border)' }}>·</span>
            <span>Source: {card.source}</span>
          </>
        )}
      </div>

      {/* Pending state */}
      {card.status === 'gap_analysis_pending' && (
        <div className="p-6" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)', textAlign: 'center' }}>
          <div style={{ fontSize: 28, marginBottom: 12 }}>&#9202;</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>Queued for Analysis</div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 400, margin: '0 auto' }}>
            This topic is queued for gap analysis. We&apos;ll scan AI search platforms to identify
            content gaps before production begins.
          </p>
        </div>
      )}

      {/* Active analysis — 8-step stepper */}
      {card.status === 'gap_analysis' && (
        <>
          {/* Progress header */}
          {progress && (
            <div className="p-4 mb-4" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--warning)', animation: 'pulse 1.5s ease-in-out infinite' }} />
                  <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>Analyzing gaps</span>
                </div>
                <span style={{ fontSize: 22, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{progress.pct}%</span>
              </div>
              <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', marginBottom: 10 }}>
                <div style={{
                  width: `${progress.pct}%`, height: '100%',
                  background: progress.pct > 80 ? 'var(--success)' : progress.pct >= 50 ? 'var(--accent)' : 'var(--warning)',
                  borderRadius: 3, animation: 'progressPulse 2.5s ease-in-out infinite', transition: 'width 0.6s ease',
                }} />
              </div>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                {progress.currentTask}
              </div>
            </div>
          )}

          {/* Abstract analysis animation */}
          <div className="flex flex-col items-center justify-center py-10" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
            {/* Orbiting rings animation */}
            <div style={{ position: 'relative', width: 96, height: 96, marginBottom: 20 }}>
              {/* Outer ring */}
              <div style={{
                position: 'absolute', inset: 0, borderRadius: '50%',
                border: '2px solid var(--border)',
                borderTopColor: 'var(--accent)',
                animation: 'gaOrbitOuter 3s linear infinite',
              }} />
              {/* Middle ring */}
              <div style={{
                position: 'absolute', inset: 12, borderRadius: '50%',
                border: '2px solid var(--border)',
                borderTopColor: 'var(--warning)',
                animation: 'gaOrbitMiddle 2s linear infinite',
              }} />
              {/* Inner ring */}
              <div style={{
                position: 'absolute', inset: 24, borderRadius: '50%',
                border: '2px solid var(--border)',
                borderTopColor: 'var(--success)',
                animation: 'gaOrbitInner 1.5s linear infinite',
              }} />
              {/* Center dot */}
              <div style={{
                position: 'absolute', top: '50%', left: '50%',
                transform: 'translate(-50%, -50%)',
                width: 10, height: 10, borderRadius: '50%',
                background: 'var(--accent)',
                animation: 'pulse 2s ease-in-out infinite',
              }} />
            </div>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>
              Scanning AI platforms
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              Identifying content gaps across search engines
            </div>
          </div>

          {/* Keyframes for orbit animation */}
          <style>{`
            @keyframes gaOrbitOuter { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
            @keyframes gaOrbitMiddle { from { transform: rotate(0deg); } to { transform: rotate(-360deg); } }
            @keyframes gaOrbitInner { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
          `}</style>
        </>
      )}

      {/* Analysis complete — rich metrics view */}
      {(card.status === 'gap_analysis_complete' || card.status === 'content_queued') && (() => {
        const ctx = card.gapContext;
        const classificationLabels: Record<string, { label: string; color: string }> = {
          significant_gap: { label: 'Significant Gap', color: 'var(--error, #e53e3e)' },
          gap_to_close: { label: 'Gap to Close', color: 'var(--warning)' },
          roughly_equal: { label: 'Roughly Equal', color: 'var(--accent)' },
          company_wins: { label: 'Company Wins', color: 'var(--success)' },
        };
        const uniqueDomains = ctx?.exemplars
          ? Array.from(new Set(ctx.exemplars.map((e) => e.domain).filter(Boolean)))
          : [];
        const classification = ctx?.classification
          ? classificationLabels[ctx.classification] ?? {
              label: ctx.classification.replace(/_/g, ' '),
              color: 'var(--text-secondary)',
            }
          : null;

        return (
          <div className="space-y-4">
            {/* Description */}
            {card.description && (
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                {card.description}
              </p>
            )}

            {/* Gap Analysis: Complete header */}
            <div className="flex items-center gap-2" style={{ marginBottom: 4 }}>
              <div style={{
                width: 24, height: 24, borderRadius: '50%',
                background: 'var(--success-subtle)', display: 'flex',
                alignItems: 'center', justifyContent: 'center',
                fontSize: 13, color: 'var(--success)',
              }}>
                &#10003;
              </div>
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                {card.status === 'content_queued' ? 'Queued for Production' : 'Gap Analysis: Complete'}
              </span>
            </div>

            {/* KPI grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
              <div className="p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
                <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Gap Score</div>
                <div style={{ fontSize: 20, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {ctx ? `${Math.round(ctx.gap_score * 100)}%` : '—'}
                </div>
              </div>
              <div className="p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
                <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Classification</div>
                <div style={{ fontSize: 20, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {classification?.label ?? '—'}
                </div>
              </div>
              <div className="p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
                <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Exemplars</div>
                <div style={{ fontSize: 20, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {ctx?.exemplars?.length ?? 0}
                </div>
              </div>
            </div>

            {/* Topic-specific signals */}
            {ctx && (
              <div className="flex gap-3">
                <div className="flex-1 p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
                  <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Company Cited</div>
                  <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {ctx.company_cited ? 'Yes' : 'No'}
                  </div>
                </div>
                <div className="flex-1 p-3" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)' }}>
                  <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Best Company URL</div>
                  <div style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {ctx.company_best_url ? 'Available' : '—'}
                  </div>
                </div>
              </div>
            )}

            {/* Top competitors */}
            {uniqueDomains.length > 0 && (
              <div className="p-4" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
                <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 10 }}>
                  Top Competitors
                </div>
                <div className="flex flex-wrap gap-2">
                  {uniqueDomains.slice(0, 6).map((domain) => (
                    <div key={domain} className="flex items-center gap-1.5 px-2 py-1" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 11, color: 'var(--text-secondary)' }}>
                      <img
                        src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
                        alt={domain}
                        width={14}
                        height={14}
                        style={{ borderRadius: 2 }}
                      />
                      {domain}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Why this topic */}
            {ctx?.why_picked && ctx.why_picked.length > 0 && (
              <div className="p-4" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
                <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 10 }}>
                  Why This Topic
                </div>
                <div className="space-y-2">
                  {ctx.why_picked.map((reason, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', marginTop: 1 }}>{i + 1}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Success indicators from gap context */}
            {ctx?.success_indicators && ctx.success_indicators.length > 0 && (
              <div className="p-4" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}>
                <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', marginBottom: 10 }}>
                  Key Indicators
                </div>
                <div className="space-y-2">
                  {ctx.success_indicators.map((ind, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{ind.label}</span>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>{ind.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Start Production */}
            <div style={{ textAlign: 'center', paddingTop: 8 }}>
              <button
                onClick={() => onAction('start_production')}
                className="inline-flex items-center gap-1.5"
                style={{
                  height: 36,
                  padding: '0 24px',
                  fontSize: 13,
                  fontWeight: 500,
                  background: 'var(--accent)',
                  color: 'var(--text-on-accent)',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                }}
              >
                <Play size={13} strokeWidth={2} />
                Start Production
              </button>
            </div>
          </div>
        );
      })()}
    </div>
  );
}

function DoneContent({ card }: { card: ContentCard }) {
  const display = getDisplay(card.status);
  return (
    <div className="p-6 flex flex-col items-center justify-center" style={{ maxWidth: 720, margin: '0 auto', paddingTop: 48 }}>
      <div style={{
        width: 48, height: 48, borderRadius: '50%',
        background: display.badgeVariant === 'error' ? 'var(--error-subtle, var(--border))' : 'var(--success-subtle)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 22, marginBottom: 16,
        color: display.badgeVariant === 'error' ? 'var(--error)' : 'var(--success)',
      }}>
        {card.status === 'rejected' ? '\u2717' : '\u2713'}
      </div>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
        {card.title}
      </h1>
      <span style={{ fontSize: 13, color: display.badgeVariant === 'error' ? 'var(--error)' : 'var(--success)' }}>
        {display.label}
      </span>
    </div>
  );
}
