'use client';

import { cn } from '@/lib/utils';
import { Button, Badge, StatusDot, Toast } from '@/components/ui';
import {
  X, Check, ChevronRight, Lightbulb,
  Target, Eye, AlertTriangle, Compass,
  SkipForward, ExternalLink, Loader2,
} from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ExtendedBrief } from './content-data';
import { agentActivities } from './content-data';
import { apiPost } from '@/lib/api/client';
import { CONTENT_ENGINE } from '@/lib/api/endpoints';
import { useContentBriefDetail, useContentStage } from '@/lib/hooks/useContent';
import { useAuthStore } from '@/stores/auth';

// --- Phase Progress Bar ---

const phases = [
  { id: 'planner', label: 'Planner' },
  { id: 'brief', label: 'Brief Builder' },
  { id: 'writer', label: 'Writer' },
  { id: 'evaluator', label: 'Evaluator' },
  { id: 'review', label: 'Human Review' },
];

function phaseIndex(stage: string): number {
  switch (stage) {
    case 'triage': return -1;
    case 'brief': return 1;
    case 'generating': return 2;
    case 'review': return 4;
    case 'approved': return 5;
    default: return 0;
  }
}

function PhaseBar({ stage }: { stage: string }) {
  const active = phaseIndex(stage);
  return (
    <div className="flex items-center gap-1">
      {phases.map((p, i) => (
        <div key={p.id} className="flex items-center gap-1">
          <div
            className={cn(
              'flex items-center gap-1 px-2 py-1 rounded-sm text-[10px] font-medium uppercase tracking-[0.06em] transition-colors',
              i < active && 'bg-accent-subtle text-accent',
              i === active && 'bg-accent text-text-on-accent',
              i > active && 'bg-surface text-text-tertiary border border-border'
            )}
          >
            {p.label}
          </div>
          {i < phases.length - 1 && (
            <ChevronRight size={10} strokeWidth={1.5} className="text-text-tertiary" />
          )}
        </div>
      ))}
    </div>
  );
}

// ===== SUGGESTED PHASE VIEW =====

function SuggestedView({
  brief,
  onApprove,
  onSkip,
  onBriefApproved,
}: {
  brief: ExtendedBrief;
  onApprove: () => void;
  onSkip: () => void;
  onBriefApproved?: () => void;
}) {
  // Manual mode: pipeline already started, no approval needed from Triage.
  // Autonomous mode: no taskId yet, user must approve to start the pipeline.
  const pipelineAlreadyRunning = !!brief.taskId;

  const handleApprove = useCallback(() => {
    if (pipelineAlreadyRunning) return;
    onApprove();
    onBriefApproved?.();
  }, [pipelineAlreadyRunning, onApprove, onBriefApproved]);

  const hasWhyPicked = brief.whyPicked && brief.whyPicked.length > 0;
  const hasIndicators = brief.successIndicators && brief.successIndicators.length > 0;
  const hasExemplars = brief.exemplars && brief.exemplars.length > 0;

  return (
    <div className="space-y-5 max-w-full">
      {/* Pipeline status banner — shown when pipeline is already running (manual mode) */}
      {pipelineAlreadyRunning && (
        <div className="flex items-center gap-2 p-3 bg-accent-subtle border border-accent/20 rounded-sm">
          <Loader2 size={14} strokeWidth={1.5} className="text-accent animate-spin" />
          <span className="text-[12px] font-medium text-accent">
            Pipeline starting — generating brief...
          </span>
        </div>
      )}

      {/* Gap Score Badge */}
      {brief.gapScore > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Gap Score</span>
          <span className="font-mono text-[16px] font-semibold text-text-primary">{brief.gapScore.toFixed(4)}</span>
        </div>
      )}

      {/* Why we picked this */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb size={14} strokeWidth={1.5} className="text-accent" />
          <h3 className="text-[12px] font-semibold text-text-primary uppercase tracking-[0.04em]">
            Why We Picked This
          </h3>
        </div>
        {hasWhyPicked ? (
          <div className="space-y-2">
            {brief.whyPicked!.map((reason, i) => (
              <div key={i} className="flex items-start gap-2 p-2 bg-surface border border-border rounded-sm">
                <span className="text-[10px] text-accent font-medium mt-0.5">{i + 1}</span>
                <span className="text-[12px] text-text-secondary leading-relaxed">{reason}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[12px] text-text-tertiary">Gap analysis context not available for this brief.</p>
        )}
      </section>

      {/* Key Success Indicators — 2x2 grid */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <Target size={14} strokeWidth={1.5} className="text-accent" />
          <h3 className="text-[12px] font-semibold text-text-primary uppercase tracking-[0.04em]">
            Key Success Indicators
          </h3>
        </div>
        {hasIndicators ? (
          <div className="grid grid-cols-2 gap-2">
            {brief.successIndicators!.map((ind, i) => (
              <div key={i} className="bg-surface border border-border rounded-sm p-3">
                <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary block mb-1">
                  {ind.label}
                </span>
                <span className="text-[20px] font-semibold text-text-primary tracking-[-0.02em] block">
                  {ind.value}
                </span>
                <span className="text-[10px] text-text-tertiary">{ind.sub}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[12px] text-text-tertiary">Run gap analysis to see success metrics.</p>
        )}
      </section>

      {/* Top Cited Exemplars */}
      {hasExemplars && (
        <section>
          <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
            Top Cited Exemplars
          </h3>
          <div className="border border-border rounded-sm overflow-hidden">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_10px] border-b border-border">Domain</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">Words</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">Sim</th>
                </tr>
              </thead>
              <tbody>
                {brief.exemplars!.map((ex, i) => (
                  <tr key={i} className="hover:bg-accent-subtle">
                    <td className="text-[12px] text-accent p-[6px_10px] border-b border-border-subtle truncate max-w-[200px]">{ex.domain || ex.url}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{ex.words > 0 ? ex.words.toLocaleString() : '\u2014'}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{(ex as unknown as { similarity?: number }).similarity?.toFixed(4) ?? '\u2014'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Actions — hidden when pipeline is already running (manual mode) */}
      {!pipelineAlreadyRunning && (
        <div className="flex items-center gap-2 pt-2">
          <Button variant="primary" onClick={handleApprove}>
            <Check size={12} strokeWidth={1.5} className="mr-1.5" />
            Approve Brief
          </Button>
          <Button variant="secondary" onClick={onSkip}>
            <SkipForward size={12} strokeWidth={1.5} className="mr-1.5" />
            Next Cycle
          </Button>
        </div>
      )}
    </div>
  );
}

// ===== APPROVED / IN PROGRESS VIEW (agent feed) =====

function InProgressView({ brief }: { brief: ExtendedBrief }) {
  return (
    <div className="space-y-5 max-w-full">
      {/* Sources discovered */}
      {brief.sources && brief.sources.length > 0 && (
        <section>
          <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
            Sources Discovered Across AI Engines
          </h3>
          <div className="space-y-1.5">
            {brief.sources.map((s, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-surface border border-border rounded-sm">
                <div>
                  <span className="text-[12px] text-text-primary block">{s.name}</span>
                  <span className="text-[10px] text-text-tertiary">{s.domain}</span>
                </div>
                <Badge variant="info">{s.engines} ENGINE{s.engines > 1 ? 'S' : ''}</Badge>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Citation share bar */}
      {brief.citationShare && (
        <section>
          <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
            Current Citation Share
          </h3>
          <div className="flex h-[24px] rounded-sm overflow-hidden border border-border">
            {brief.citationShare.map((s, i) => (
              <div
                key={i}
                className="relative flex items-center justify-center"
                style={{ width: `${s.pct}%`, backgroundColor: s.color, opacity: 0.8 }}
                title={`${s.name}: ${s.pct}%`}
              >
                {s.pct >= 12 && (
                  <span className="text-[9px] font-medium text-white truncate px-1">
                    {s.name} {s.pct}%
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Exemplar analysis */}
      {brief.exemplars && brief.exemplars.length > 0 && (
        <section>
          <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
            Exemplar Analysis
          </h3>
          <div className="border border-border rounded-sm overflow-hidden">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_10px] border-b border-border">URL</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">Words</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">H</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">Stats</th>
                </tr>
              </thead>
              <tbody>
                {brief.exemplars.map((ex, i) => (
                  <tr key={i} className="hover:bg-accent-subtle">
                    <td className="text-[12px] text-accent p-[6px_10px] border-b border-border-subtle truncate max-w-[300px]">{ex.url}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{ex.words.toLocaleString()}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{ex.headers}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{ex.stats}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Agent timeline */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Agent Activity
        </h3>
        <div className="border border-border rounded-sm divide-y divide-border-subtle">
          {agentActivities.slice(0, 8).map((a) => (
            <div key={a.id} className="flex items-start gap-2 px-3 py-2">
              <StatusDot
                color={a.type === 'writer' ? 'info' : a.type === 'strategy' ? 'warning' : a.type === 'eval' ? 'neutral' : 'success'}
                className="mt-1.5 flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <span className="text-[11px] font-medium text-text-primary">{a.agent}</span>
                <span className="text-[11px] text-text-secondary block leading-snug">{a.action}</span>
              </div>
              <span className="text-[10px] text-text-tertiary flex-shrink-0 mt-0.5">{a.time}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ===== BRIEF APPROVAL VIEW (HITL-2 — user reviews generated brief) =====

function BriefApprovalView({
  brief,
  onApprove,
  onRevise,
  onReject,
  onBriefApproved,
  onError,
}: {
  brief: ExtendedBrief;
  onApprove: () => void;
  onRevise: () => void;
  onReject: () => void;
  onBriefApproved?: () => void;
  onError?: (msg: string) => void;
}) {
  const slug = useAuthStore((s) => s.company?.slug);
  const { data: detail } = useContentBriefDetail(slug, brief.id);
  const [feedback, setFeedback] = useState('');
  const [submitting, setSubmitting] = useState<'approve' | 'feedback' | 'reject' | null>(null);

  const handleDecision = useCallback(async (decision: 'approve' | 'feedback' | 'reject') => {
    const taskId = brief.taskId;
    if (!taskId) {
      onError?.('No active pipeline — cannot submit approval.');
      return;
    }
    if (decision === 'feedback' && !feedback.trim()) {
      onError?.('Please provide feedback for the revision.');
      return;
    }
    setSubmitting(decision);
    try {
      await apiPost(CONTENT_ENGINE.approveBriefs(taskId), {
        brief_id: brief.id,
        decision,
        ...(decision === 'feedback' ? { feedback: feedback.trim() } : {}),
      });
      if (decision === 'approve') onApprove();
      else if (decision === 'feedback') onRevise();
      else onReject();
      onBriefApproved?.();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Submission failed.';
      onError?.(message);
    } finally {
      setSubmitting(null);
    }
  }, [brief.taskId, brief.id, feedback, onApprove, onRevise, onReject, onBriefApproved, onError]);

  const keyTopics = detail?.key_topics ?? [];
  const keyAngles = detail?.key_angles ?? [];
  const wordCount = detail?.target_word_count ?? { min: 0, max: 0 };
  const exemplars = detail?.exemplars ?? [];

  return (
    <div className="space-y-5 max-w-full">
      {/* Brief Summary Card */}
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[14px] font-semibold text-text-primary leading-tight mb-2">
          {brief.title}
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="neutral">{brief.contentFormat || 'blog'}</Badge>
          <Badge variant="info">{brief.targetCluster}</Badge>
          {wordCount.max > 0 && (
            <span className="text-[10px] text-text-tertiary font-mono">
              {wordCount.min.toLocaleString()}–{wordCount.max.toLocaleString()} words
            </span>
          )}
        </div>
      </div>

      {/* Key Topics */}
      {keyTopics.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <Target size={14} strokeWidth={1.5} className="text-accent" />
            <h3 className="text-[12px] font-semibold text-text-primary uppercase tracking-[0.04em]">
              Key Topics
            </h3>
          </div>
          <div className="space-y-1.5">
            {keyTopics.map((topic, i) => (
              <div key={i} className="flex items-start gap-2 p-2 bg-surface border border-border rounded-sm">
                <span className="text-[10px] text-accent font-medium mt-0.5">{i + 1}</span>
                <span className="text-[12px] text-text-secondary leading-relaxed">{topic}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Key Angles */}
      {keyAngles.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <Compass size={14} strokeWidth={1.5} className="text-accent" />
            <h3 className="text-[12px] font-semibold text-text-primary uppercase tracking-[0.04em]">
              Key Angles
            </h3>
          </div>
          <div className="space-y-1.5">
            {keyAngles.map((angle, i) => (
              <div key={i} className="flex items-start gap-2 p-2 bg-surface border border-border rounded-sm">
                <span className="text-[10px] text-text-tertiary mt-0.5">│</span>
                <span className="text-[12px] text-text-secondary leading-relaxed">{angle}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Exemplars */}
      {exemplars.length > 0 && (
        <section>
          <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
            Cited Exemplars to Beat
          </h3>
          <div className="border border-border rounded-sm overflow-hidden">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_10px] border-b border-border">URL</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">Words</th>
                </tr>
              </thead>
              <tbody>
                {exemplars.map((ex, i) => (
                  <tr key={i} className="hover:bg-accent-subtle">
                    <td className="text-[12px] text-accent p-[6px_10px] border-b border-border-subtle truncate max-w-[300px]">{ex.url}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{ex.word_count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Loading state for detail */}
      {!detail && (
        <div className="flex items-center gap-2 p-3">
          <Loader2 size={14} strokeWidth={1.5} className="text-accent animate-spin" />
          <span className="text-[12px] text-text-tertiary">Loading brief details...</span>
        </div>
      )}

      {/* Feedback */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Feedback (optional for approve, required for revise)
        </h3>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="e.g. 'Focus more on enterprise use cases, add comparison with Contentful...'"
          className="w-full h-[80px] p-2 bg-surface border border-border rounded-sm text-[12px] text-text-primary placeholder:text-text-tertiary resize-none outline-none focus:border-accent focus:ring-1 focus:ring-accent-subtle"
        />
      </section>

      {/* HITL Actions */}
      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="primary"
          disabled={submitting !== null}
          onClick={() => handleDecision('approve')}
        >
          {submitting === 'approve' ? (
            <Loader2 size={12} strokeWidth={1.5} className="mr-1.5 animate-spin" />
          ) : (
            <Check size={12} strokeWidth={1.5} className="mr-1.5" />
          )}
          {submitting === 'approve' ? 'Approving...' : 'Approve Brief'}
        </Button>
        <Button
          variant="secondary"
          disabled={submitting !== null}
          onClick={() => handleDecision('feedback')}
        >
          {submitting === 'feedback' ? 'Sending...' : 'Revise'}
        </Button>
        <Button
          variant="destructive"
          disabled={submitting !== null}
          onClick={() => handleDecision('reject')}
        >
          {submitting === 'reject' ? 'Rejecting...' : 'Reject'}
        </Button>
      </div>
    </div>
  );
}

// ===== REVIEW PHASE VIEW (HITL checkpoint) =====

function ReviewView({
  brief,
  onApprove,
  onRevise,
  onOpenFullView,
  onBriefApproved,
  onError,
}: {
  brief: ExtendedBrief;
  onApprove: () => void;
  onRevise: () => void;
  onOpenFullView: () => void;
  onBriefApproved?: () => void;
  onError?: (msg: string) => void;
}) {
  const [feedback, setFeedback] = useState('');
  const [approving, setApproving] = useState(false);
  const [revising, setRevising] = useState(false);

  return (
    <div className="space-y-5 max-w-full">
      {/* Brief card */}
      <div className="bg-surface border border-border rounded-md p-4">
        <h3 className="text-[14px] font-semibold text-text-primary leading-tight mb-2">
          {brief.title}
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="neutral">{brief.contentFormat}</Badge>
          <Badge variant="info">{brief.funnelStage}</Badge>
          <span className="text-[11px] font-medium text-warning">
            PRIORITY {(brief.priorityScore * 100).toFixed(0)}
          </span>
        </div>
      </div>

      {/* Outline */}
      {brief.outlineSections && (
        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
              Outline ({brief.outlineSections.length} sections · {brief.structuralTargets.words.toLocaleString()} words target)
            </h3>
          </div>
          <div className="border border-border rounded-sm divide-y divide-border-subtle">
            {brief.outlineSections.map((sec, i) => (
              <div key={i} className="flex items-center justify-between px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={cn(
                    'text-[10px] text-text-tertiary w-2',
                    sec.level === 3 && 'ml-4'
                  )}>
                    {sec.level === 2 ? '│' : '└'}
                  </span>
                  <span className="text-[12px] text-text-primary truncate">{sec.heading}</span>
                </div>
                <span className="text-[10px] text-text-tertiary flex-shrink-0 ml-2">
                  {sec.targetWords}w
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Must-Hit Checklist */}
      {brief.mustHitChecklist && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={12} strokeWidth={1.5} className="text-warning" />
            <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
              Must-Hit Checklist
            </h3>
          </div>
          <div className="space-y-1">
            {brief.mustHitChecklist.map((item, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-surface border border-border rounded-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 border border-border-strong rounded-sm" />
                  <span className="text-[12px] text-text-primary">{item.label}</span>
                </div>
                <Badge variant={item.priority === 'critical' ? 'error' : item.priority === 'high' ? 'warning' : 'neutral'}>
                  {item.priority.toUpperCase()}
                </Badge>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Key Angles */}
      {brief.keyAngles && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <Compass size={12} strokeWidth={1.5} className="text-accent" />
            <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
              Key Angles
            </h3>
          </div>
          <div className="space-y-1">
            {brief.keyAngles.map((angle, i) => (
              <div key={i} className="flex items-start gap-2 p-2 bg-surface border border-border rounded-sm">
                <span className="text-[10px] text-text-tertiary mt-0.5">│</span>
                <span className="text-[12px] text-text-secondary">{angle}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Exemplars */}
      {brief.exemplars && brief.exemplars.length > 0 && (
        <section>
          <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
            Exemplar Analysis
          </h3>
          <div className="border border-border rounded-sm overflow-hidden">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_10px] border-b border-border">URL</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">Words</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">H</th>
                  <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-right p-[6px_10px] border-b border-border">Stats</th>
                </tr>
              </thead>
              <tbody>
                {brief.exemplars.map((ex, i) => (
                  <tr key={i} className="hover:bg-accent-subtle">
                    <td className="text-[12px] text-accent p-[6px_10px] border-b border-border-subtle truncate max-w-[300px]">{ex.url}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{ex.words.toLocaleString()}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{ex.headers}</td>
                    <td className="text-[12px] text-text-primary p-[6px_10px] border-b border-border-subtle text-right font-mono">{ex.stats}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Feedback to Agent */}
      <section>
        <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Feedback to Agent
        </h3>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="e.g. 'Emphasize ROI angle in section 3, add Divvy to comparison...'"
          className="w-full h-[80px] p-2 bg-surface border border-border rounded-sm text-[12px] text-text-primary placeholder:text-text-tertiary resize-none outline-none focus:border-accent focus:ring-1 focus:ring-accent-subtle"
        />
      </section>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="primary"
          disabled={approving}
          onClick={async () => {
            const taskId = brief.taskId;
            if (!taskId) {
              onError?.('No active pipeline for this brief.');
              return;
            }
            setApproving(true);
            try {
              await apiPost(CONTENT_ENGINE.approveContent(taskId), {
                brief_id: brief.id,
                decision: 'approve',
              });
              onApprove();
              onBriefApproved?.();
            } catch (err: unknown) {
              const message = err instanceof Error ? err.message : 'Approval failed.';
              onError?.(message);
            } finally {
              setApproving(false);
            }
          }}
        >
          {approving ? (
            <Loader2 size={12} strokeWidth={1.5} className="mr-1.5 animate-spin" />
          ) : (
            <Check size={12} strokeWidth={1.5} className="mr-1.5" />
          )}
          {approving ? 'Approving...' : 'Approve & Publish'}
        </Button>
        <Button
          variant="secondary"
          disabled={revising}
          onClick={async () => {
            const taskId = brief.taskId;
            if (!taskId) {
              onError?.('No active pipeline for this brief.');
              return;
            }
            if (!feedback.trim()) {
              onError?.('Please provide feedback for the revision.');
              return;
            }
            setRevising(true);
            try {
              await apiPost(CONTENT_ENGINE.approveContent(taskId), {
                brief_id: brief.id,
                decision: 'edit',
                editor_notes: feedback.trim(),
              });
              onRevise();
              onBriefApproved?.();
            } catch (err: unknown) {
              const message = err instanceof Error ? err.message : 'Revision request failed.';
              onError?.(message);
            } finally {
              setRevising(false);
            }
          }}
        >
          {revising ? 'Revising...' : 'Revise'}
        </Button>
        <Button variant="ghost" onClick={onOpenFullView} className="ml-auto">
          <ExternalLink size={12} strokeWidth={1.5} className="mr-1.5" />
          Open Full View
        </Button>
      </div>
    </div>
  );
}

// ===== APPROVED VIEW (completed content) =====

function ApprovedView({
  brief,
  onOpenFullView,
}: {
  brief: ExtendedBrief;
  onOpenFullView: () => void;
}) {
  const slug = useAuthStore((s) => s.company?.slug);
  const { data: detail } = useContentBriefDetail(slug, brief.id);
  const { data: finalStage } = useContentStage(slug ?? undefined, brief.id, 'final');

  const finalContent = typeof finalStage?.content === 'string' ? finalStage.content : '';
  const wordCount = finalContent.split(/\s+/).filter(Boolean).length;
  const evalHistory = detail?.eval_history ?? [];
  const lastCycle = evalHistory.length > 0 ? evalHistory[evalHistory.length - 1] : null;

  return (
    <div className="space-y-5 max-w-full">
      {/* Published banner */}
      <div className="bg-success-subtle border border-success rounded-sm p-4">
        <div className="flex items-center gap-2 mb-1">
          <Check size={14} strokeWidth={1.5} className="text-success" />
          <span className="text-[12px] font-medium text-success">Content Approved</span>
        </div>
        <span className="text-[11px] text-text-secondary">
          {brief.createdAt ? new Date(brief.createdAt).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : ''}
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-surface border border-border rounded-sm p-3 text-center">
          <span className="text-[18px] font-semibold text-text-primary block">{wordCount > 0 ? wordCount.toLocaleString() : '\u2014'}</span>
          <span className="text-[10px] text-text-tertiary uppercase tracking-[0.06em]">Words</span>
        </div>
        <div className="bg-surface border border-border rounded-sm p-3 text-center">
          <span className="text-[18px] font-semibold text-text-primary block">
            {detail?.citability_score != null ? detail.citability_score.toFixed(0) : '\u2014'}
          </span>
          <span className="text-[10px] text-text-tertiary uppercase tracking-[0.06em]">Citability</span>
        </div>
        <div className="bg-surface border border-border rounded-sm p-3 text-center">
          <span className="text-[18px] font-semibold text-text-primary block">{evalHistory.length}</span>
          <span className="text-[10px] text-text-tertiary uppercase tracking-[0.06em]">Eval Cycles</span>
        </div>
      </div>

      {/* Eval scores from last cycle */}
      {lastCycle && lastCycle.dimensions && lastCycle.dimensions.length > 0 && (
        <section>
          <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
            Final Evaluation Scores
          </h3>
          <div className="space-y-1.5">
            {lastCycle.dimensions.map((d, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-[11px] text-text-secondary w-[100px] capitalize">{d.dimension}</span>
                <div className="flex-1 h-[6px] bg-border rounded-sm overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-sm transition-all',
                      d.passed ? 'bg-success' : 'bg-warning',
                    )}
                    style={{ width: `${Math.min(100, d.score * 100)}%` }}
                  />
                </div>
                <span className="text-[10px] font-mono text-text-primary w-[32px] text-right">
                  {(d.score * 100).toFixed(0)}%
                </span>
                <span className={cn('text-[9px] font-medium', d.passed ? 'text-success' : 'text-warning')}>
                  {d.passed ? 'PASS' : 'FAIL'}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Content preview */}
      {finalContent && (
        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
              Content Preview
            </h3>
            <Button variant="ghost" size="sm" onClick={onOpenFullView}>
              <Eye size={11} strokeWidth={1.5} className="mr-1" />
              Open Full View
            </Button>
          </div>
          <div className="bg-surface border border-border rounded-sm p-3 max-h-[300px] overflow-y-auto">
            <pre className="text-[11px] text-text-secondary whitespace-pre-wrap font-body leading-relaxed">
              {finalContent.slice(0, 2000)}{finalContent.length > 2000 ? '\n\n...' : ''}
            </pre>
          </div>
        </section>
      )}

      {!finalContent && !finalStage && (
        <div className="flex items-center gap-2 p-3">
          <Loader2 size={14} strokeWidth={1.5} className="text-accent animate-spin" />
          <span className="text-[12px] text-text-tertiary">Loading content...</span>
        </div>
      )}
    </div>
  );
}

// ===== MAIN DETAIL VIEW =====

interface DetailViewProps {
  brief: ExtendedBrief;
  onClose: () => void;
  onOpenFullEditor: () => void;
  onBriefApproved?: () => void;
}

export function DetailView({ brief, onClose, onOpenFullEditor, onBriefApproved }: DetailViewProps) {
  const [toast, setToast] = useState<{ open: boolean; message: string; variant: 'success' | 'error' | 'info' }>({
    open: false, message: '', variant: 'info',
  });

  const showToast = useCallback((msg: string, variant: 'success' | 'error' | 'info' = 'info') => {
    setToast({ open: true, message: msg, variant });
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const stageLabel =
    brief.stage === 'triage' ? 'Suggested' :
    brief.stage === 'brief' ? 'Generating Brief' :
    brief.stage === 'generating' ? 'In Progress' :
    brief.stage === 'review' ? 'Brief Ready — Review' :
    'Published';

  return (
    <AnimatePresence>
      {/* Backdrop — click to close */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.3 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-40 bg-black"
        onClick={onClose}
      />
      {/* Sidebar panel — right-aligned, 40% width */}
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 28, stiffness: 300 }}
        className="fixed right-0 top-0 h-full w-[48%] min-w-[400px] max-w-[720px] z-50 bg-bg border-l border-border flex flex-col shadow-float"
      >
        {/* Top Bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={onClose}
              className="p-1 rounded-sm text-text-tertiary hover:text-text-primary hover:bg-surface transition-colors cursor-pointer"
            >
              <X size={16} strokeWidth={1.5} />
            </button>
            <div className="min-w-0">
              <h2 className="text-[14px] font-semibold text-text-primary truncate">{brief.title}</h2>
              <div className="flex items-center gap-2 mt-0.5">
                <Badge variant="neutral">{brief.contentFormat}</Badge>
                <Badge variant="info">{brief.targetCluster}</Badge>
                <span className="text-[10px] text-text-tertiary">·</span>
                <span className="text-[10px] text-text-secondary">{stageLabel}</span>
              </div>
            </div>
          </div>
          {(brief.stage === 'generating' || brief.stage === 'review' || brief.stage === 'approved') && (
            <Button variant="ghost" size="sm" onClick={onOpenFullEditor}>
              <Eye size={11} strokeWidth={1.5} className="mr-1" />
              Open Full View
            </Button>
          )}
        </div>

        {/* Phase bar */}
        {brief.stage !== 'triage' && (
          <div className="px-4 py-2 border-b border-border bg-surface shrink-0 overflow-x-auto">
            <PhaseBar stage={brief.stage} />
          </div>
        )}

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-4">
          {brief.stage === 'triage' && (
            <SuggestedView
              brief={brief}
              onApprove={() => showToast('Brief approved — content generation starting', 'success')}
              onSkip={() => showToast('Moved to next cycle', 'info')}
              onBriefApproved={onBriefApproved}
            />
          )}
          {brief.stage === 'brief' && (brief.status === 'brief_review' || brief.status === 'approved') && (
            <BriefApprovalView
              brief={brief}
              onApprove={() => showToast('Brief approved — workers starting', 'success')}
              onRevise={() => showToast('Revision feedback sent — brief rebuilding', 'info')}
              onReject={() => showToast('Brief rejected', 'info')}
              onBriefApproved={onBriefApproved}
              onError={(msg) => showToast(msg, 'error')}
            />
          )}
          {((brief.stage === 'brief' && brief.status !== 'brief_review' && brief.status !== 'approved') || brief.stage === 'generating') && (
            <InProgressView brief={brief} />
          )}
          {brief.stage === 'review' && (
            <ReviewView
              brief={brief}
              onApprove={() => showToast('Content approved — publishing', 'success')}
              onRevise={() => showToast('Revision requested — agents notified', 'info')}
              onOpenFullView={onOpenFullEditor}
              onBriefApproved={onBriefApproved}
              onError={(msg) => showToast(msg, 'error')}
            />
          )}
          {brief.stage === 'approved' && (
            <ApprovedView brief={brief} onOpenFullView={onOpenFullEditor} />
          )}
        </div>

        <Toast
          open={toast.open}
          onClose={() => setToast((t) => ({ ...t, open: false }))}
          variant={toast.variant}
          message={toast.message}
        />
      </motion.div>  {/* end sidebar panel */}
    </AnimatePresence>
  );
}
