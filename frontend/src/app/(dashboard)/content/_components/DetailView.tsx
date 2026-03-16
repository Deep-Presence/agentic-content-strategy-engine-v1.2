'use client';

import { cn } from '@/lib/utils';
import { Button, Badge, StatusDot, ProgressBar, Toast } from '@/components/ui';
import {
  X, Check, ChevronRight, Lightbulb,
  Target, Eye, AlertTriangle, Compass,
  SkipForward, ExternalLink,
} from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ExtendedBrief } from './content-data';
import { agentActivities, platformLabels } from './content-data';

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
}: {
  brief: ExtendedBrief;
  onApprove: () => void;
  onSkip: () => void;
}) {
  return (
    <div className="space-y-5 max-w-[720px]">
      {/* Why we picked this */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb size={14} strokeWidth={1.5} className="text-accent" />
          <h3 className="text-[12px] font-semibold text-text-primary uppercase tracking-[0.04em]">
            Why We Picked This
          </h3>
        </div>
        <div className="space-y-2">
          {brief.whyPicked?.map((reason, i) => (
            <div key={i} className="flex items-start gap-2 p-2 bg-surface border border-border rounded-sm">
              <span className="text-[10px] text-accent font-medium mt-0.5">{i + 1}</span>
              <span className="text-[12px] text-text-secondary leading-relaxed">{reason}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Key Success Indicators — 2x2 grid */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <Target size={14} strokeWidth={1.5} className="text-accent" />
          <h3 className="text-[12px] font-semibold text-text-primary uppercase tracking-[0.04em]">
            Key Success Indicators
          </h3>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {brief.successIndicators?.map((ind, i) => (
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
      </section>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2">
        <Button variant="primary" onClick={onApprove}>
          <Check size={12} strokeWidth={1.5} className="mr-1.5" />
          Approve Topic
        </Button>
        <Button variant="secondary" onClick={onSkip}>
          <SkipForward size={12} strokeWidth={1.5} className="mr-1.5" />
          Next Cycle
        </Button>
      </div>
    </div>
  );
}

// ===== APPROVED / IN PROGRESS VIEW (agent feed) =====

function InProgressView({ brief }: { brief: ExtendedBrief }) {
  return (
    <div className="space-y-5 max-w-[720px]">
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

// ===== REVIEW PHASE VIEW (HITL checkpoint) =====

function ReviewView({
  brief,
  onApprove,
  onRevise,
  onOpenFullView,
}: {
  brief: ExtendedBrief;
  onApprove: () => void;
  onRevise: () => void;
  onOpenFullView: () => void;
}) {
  const [feedback, setFeedback] = useState('');

  return (
    <div className="space-y-5 max-w-[720px]">
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
        <Button variant="primary" onClick={onApprove}>
          <Check size={12} strokeWidth={1.5} className="mr-1.5" />
          Approve &amp; Generate Content
        </Button>
        <Button variant="secondary" onClick={onRevise}>
          Revise
        </Button>
        <Button variant="ghost" onClick={onOpenFullView} className="ml-auto">
          <ExternalLink size={12} strokeWidth={1.5} className="mr-1.5" />
          Open Full View
        </Button>
      </div>
    </div>
  );
}

// ===== MAIN DETAIL VIEW =====

interface DetailViewProps {
  brief: ExtendedBrief;
  onClose: () => void;
  onOpenFullEditor: () => void;
}

export function DetailView({ brief, onClose, onOpenFullEditor }: DetailViewProps) {
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
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-40 bg-bg flex flex-col"
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
        <div className="flex-1 overflow-y-auto p-6">
          {brief.stage === 'triage' && (
            <SuggestedView
              brief={brief}
              onApprove={() => showToast('Topic approved — brief generation starting', 'success')}
              onSkip={() => showToast('Moved to next cycle', 'info')}
            />
          )}
          {(brief.stage === 'brief' || brief.stage === 'generating') && (
            <InProgressView brief={brief} />
          )}
          {brief.stage === 'review' && (
            <ReviewView
              brief={brief}
              onApprove={() => showToast('Brief approved — content generation starting', 'success')}
              onRevise={() => showToast('Revision requested — agents notified', 'info')}
              onOpenFullView={onOpenFullEditor}
            />
          )}
          {brief.stage === 'approved' && (
            <div className="space-y-4 max-w-[720px]">
              <div className="bg-success-subtle border border-success rounded-sm p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Check size={14} strokeWidth={1.5} className="text-success" />
                  <span className="text-[12px] font-medium text-success">Published</span>
                </div>
                <span className="text-[12px] text-text-secondary">
                  Published on {brief.publishedAt ? new Date(brief.publishedAt).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : 'N/A'}
                </span>
              </div>
              {/* CPS scores */}
              <section>
                <h3 className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">
                  Citation Prediction Scores
                </h3>
                <div className="space-y-1.5">
                  {(['chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini'] as const).map((p) => (
                    <div key={p} className="flex items-center gap-2">
                      <span className="text-[11px] text-text-secondary w-[130px]">{platformLabels[p]}</span>
                      <ProgressBar value={brief.cpsActual?.[p] || brief.cpsPredict[p]} className="flex-1" />
                      <span className="text-[11px] font-medium text-text-primary w-6 text-right">
                        {brief.cpsActual?.[p] || brief.cpsPredict[p]}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}
        </div>

        <Toast
          open={toast.open}
          onClose={() => setToast((t) => ({ ...t, open: false }))}
          variant={toast.variant}
          message={toast.message}
        />
      </motion.div>
    </AnimatePresence>
  );
}
