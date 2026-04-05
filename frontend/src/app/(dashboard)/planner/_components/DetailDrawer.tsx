'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Link2, Check, Settings, Search, Tag } from 'lucide-react';
import type { Assignment } from './planner-data';
import { formatPersonaName } from './planner-data';

interface DetailDrawerProps {
  assignment: Assignment | null;
  onClose: () => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

function UserAvatar({ name, size = 20 }: { name: string; size?: number }) {
  const initials = name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  return (
    <div className="flex items-center justify-center rounded-full text-white font-semibold shrink-0"
      style={{ width: size, height: size, fontSize: size * 0.4, background: 'var(--accent)' }}>{initials}</div>
  );
}

function ChevronIcon() {
  return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mx-0.5" style={{ verticalAlign: 'middle' }}><polyline points="9 18 15 12 9 6" /></svg>;
}

const stageStyles: Record<string, string> = {
  TOFU: 'bg-accent-subtle text-accent border-accent/30',
  MOFU: 'bg-warning-subtle text-warning border-warning/30',
  BOFU: 'bg-success-subtle text-success border-success/30',
};
const effortStyles: Record<string, string> = {
  low: 'bg-success-subtle text-success border-success/30',
  medium: 'bg-warning-subtle text-warning border-warning/30',
  high: 'bg-error-subtle text-error border-error/30',
};
const intentStyles: Record<string, string> = {
  Informational: 'bg-info-subtle text-info border-info/30',
  Commercial: 'bg-warning-subtle text-warning border-warning/30',
  Navigational: 'bg-[var(--surface)] text-text-secondary border-border',
  Transactional: 'bg-success-subtle text-success border-success/30',
};

export function DetailDrawer({ assignment, onClose, onApprove, onReject }: DetailDrawerProps) {
  const [copied, setCopied] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const handleShare = () => {
    navigator.clipboard.writeText(`https://app.deeppresence.com/planner/${assignment?.id}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <AnimatePresence>
      {assignment && (
        <>
          <motion.div className="fixed inset-0 z-40" style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} onClick={onClose} />
          <motion.div ref={drawerRef} className="fixed top-0 right-0 bottom-0 z-50 w-1/2 flex flex-col"
            style={{ background: 'var(--surface)', borderLeft: '1px solid var(--border)', boxShadow: 'var(--shadow-float)' }}
            initial={{ x: '100%', opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: '100%', opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}>

            {/* ═══ FIXED TOP: Buttons → Title → Path ═══ */}
            <div className="shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
              {/* Row 1: Action buttons + share/close */}
              <div className="flex items-center justify-between px-5 pt-4 pb-2">
                <div className="flex items-center gap-2">
                  <button onClick={() => onApprove(assignment.id)}
                    className="flex items-center gap-1.5 h-[32px] px-4 rounded text-[13px] font-semibold text-white transition-colors duration-150"
                    style={{ background: 'var(--accent)' }}>
                    <Check size={14} strokeWidth={2} /> Approve &amp; Send to Studio
                  </button>
                  <button onClick={() => onReject(assignment.id)}
                    className="flex items-center gap-1.5 h-[32px] px-4 rounded text-[13px] font-semibold transition-colors duration-150"
                    style={{ color: 'var(--error)', border: '1px solid var(--error)', background: 'transparent' }}>
                    <X size={14} strokeWidth={2} /> Reject
                  </button>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={handleShare} className="relative flex items-center justify-center w-[30px] h-[30px] rounded text-text-secondary hover:text-text-primary hover:bg-[var(--surface-raised)] transition-all duration-150">
                    <Link2 size={14} strokeWidth={1.5} />
                    {copied && (
                      <motion.span className="absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium px-2 py-1 rounded"
                        style={{ background: 'var(--surface-raised)', border: '1px solid var(--border)', color: 'var(--success)' }}
                        initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <Check size={10} className="inline mr-0.5" /> Copied
                      </motion.span>
                    )}
                  </button>
                  <button onClick={onClose} className="flex items-center justify-center w-[30px] h-[30px] rounded text-text-secondary hover:text-text-primary hover:bg-[var(--surface-raised)] transition-all duration-150">
                    <X size={14} strokeWidth={1.5} />
                  </button>
                </div>
              </div>

              {/* Row 2: Title + cluster path + description */}
              <div className="px-5 pb-4">
                <h2 className="text-[18px] font-semibold text-text-primary leading-snug">{assignment.title}</h2>
                <p className="text-[13px] text-text-secondary mt-1">{assignment.cluster} <ChevronIcon /> {assignment.subcluster}</p>
                {assignment.description && (
                  <p className="text-[13px] text-text-secondary mt-2 leading-relaxed">{assignment.description}</p>
                )}
              </div>
            </div>

            {/* ═══ SCROLLABLE: Pills → All content sections ═══ */}
            <div className="flex-1 overflow-y-auto">
              {/* Pills row */}
              <div className="px-5 pt-4 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="font-mono text-[12px] text-text-secondary">{assignment.displayId}</span>
                  <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-semibold uppercase border rounded-full ${stageStyles[assignment.stage]}`}>{assignment.stage}</span>
                  {assignment.format && (
                    <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-semibold uppercase border border-border text-text-secondary rounded-full">{assignment.format}</span>
                  )}
                  <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-medium border rounded-full ${intentStyles[assignment.intent]}`}>{assignment.intent}</span>
                  {assignment.effort && (
                    <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-semibold uppercase border rounded-full ${effortStyles[assignment.effort]}`}>{assignment.effort} effort</span>
                  )}
                  {assignment.estDays != null && (
                    <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-medium border border-border text-text-secondary rounded-full" title={assignment.wordCount ? `Based on ~600 words/day at ${assignment.wordCount} words` : undefined}>
                      ~{assignment.estDays}d
                    </span>
                  )}
                </div>
                {assignment.initiative && (
                  <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 text-[11px] font-semibold uppercase bg-[rgba(147,51,234,0.08)] text-[#9333ea] border border-[rgba(147,51,234,0.3)] rounded-full">
                    Initiative: {assignment.initiative}
                  </span>
                )}
              </div>

              <div className="px-5 py-5">
                {/* ─── Why We Recommend ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mb-3">Why We Recommend This</h3>
                {assignment.reasons.length > 0 ? (
                  <div className={`grid gap-2 ${assignment.reasons.length >= 3 ? 'grid-cols-3' : assignment.reasons.length === 2 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                    {assignment.reasons.map((r, i) => (
                      <div key={i} className="p-3 rounded-md" style={{ border: '1px solid var(--border)', borderTop: '2px solid var(--warning)', background: 'var(--surface)' }}>
                        <p className="text-[13px] font-semibold text-text-primary leading-snug">{r.title}</p>
                        <p className="text-[12px] text-text-secondary leading-[1.5] mt-1">{r.text}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 rounded-md text-[13px] text-text-secondary" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
                    Analysis pending
                  </div>
                )}

                {/* ─── Target Keywords ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">Target Keywords</h3>
                {assignment.targetKeywords.primary || assignment.targetKeywords.secondary.length > 0 ? (
                  <div className="space-y-2">
                    {assignment.targetKeywords.primary && (
                      <div className="flex items-start gap-2.5 p-2.5 rounded-md" style={{ border: '1px solid var(--accent)', background: 'var(--accent-subtle)' }}>
                        <Search size={14} className="text-accent mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[13px] font-medium text-text-primary">{assignment.targetKeywords.primary}</p>
                          <span className="text-[11px] font-semibold text-accent uppercase">Primary keyword</span>
                        </div>
                      </div>
                    )}
                    {assignment.targetKeywords.secondary.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {assignment.targetKeywords.secondary.map((kw, i) => (
                          <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 text-[12px] text-text-secondary rounded-full" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
                            <Tag size={10} className="text-text-tertiary" />
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-3 rounded-md text-[13px] text-text-secondary" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
                    No target keywords available. Run gap analysis for keyword intelligence.
                  </div>
                )}

                {/* ─── Target Persona ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">Target Persona</h3>
                {assignment.persona ? (
                  <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--accent)' }}>
                    {/* Persona header */}
                    <div className="flex items-center gap-3 px-4 py-3" style={{ background: 'var(--accent-subtle)', borderBottom: '1px solid var(--accent)' }}>
                      <UserAvatar name={formatPersonaName(assignment.persona)} size={32} />
                      <div>
                        <p className="text-[14px] font-semibold text-text-primary">{formatPersonaName(assignment.persona)}</p>
                        <span className="text-[11px] font-semibold text-accent uppercase">Primary audience for this content</span>
                      </div>
                    </div>
                    {/* Reasons */}
                    <div className="px-4 py-3 space-y-2.5">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Why this persona</p>
                      {(() => {
                        const personaReasons: Array<{ icon: string; text: string }> = [];
                        // Stage alignment
                        if (assignment.stage === 'BOFU') {
                          personaReasons.push({ icon: '🎯', text: `Decision-stage content directly addresses ${formatPersonaName(assignment.persona)}'s buying criteria and vendor evaluation needs` });
                        } else if (assignment.stage === 'MOFU') {
                          personaReasons.push({ icon: '🔍', text: `Consideration-stage content helps ${formatPersonaName(assignment.persona)} evaluate approaches and build selection criteria` });
                        } else {
                          personaReasons.push({ icon: '💡', text: `Educational content builds awareness and trust with ${formatPersonaName(assignment.persona)} around this topic` });
                        }
                        // Intent alignment
                        if (assignment.intent === 'Commercial') {
                          personaReasons.push({ icon: '📊', text: `Commercial intent matches ${formatPersonaName(assignment.persona)}'s active comparison and evaluation behavior` });
                        } else if (assignment.intent === 'Informational') {
                          personaReasons.push({ icon: '📚', text: `Informational intent aligns with ${formatPersonaName(assignment.persona)}'s knowledge-seeking and research patterns` });
                        } else if (assignment.intent === 'Transactional') {
                          personaReasons.push({ icon: '⚡', text: `Action-oriented content enables ${formatPersonaName(assignment.persona)} to take immediate next steps` });
                        }
                        // Affinity score
                        const affinityScore = assignment.personaScores[assignment.persona];
                        if (affinityScore != null && affinityScore > 0) {
                          personaReasons.push({ icon: '📈', text: `${affinityScore}% subdomain affinity — this topic area strongly resonates with ${formatPersonaName(assignment.persona)}'s professional concerns` });
                        }
                        return personaReasons.map((r, i) => (
                          <div key={i} className="flex items-start gap-2">
                            <span className="text-[13px] shrink-0 mt-px">{r.icon}</span>
                            <p className="text-[13px] text-text-secondary leading-relaxed">{r.text}</p>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>
                ) : (
                  <div className="p-3 rounded-md text-[13px] text-text-secondary" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
                    No target persona assigned
                  </div>
                )}

                {/* ─── Related Queries (from target keywords) ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">
                  Queries This Content Would Answer{assignment.relatedQueries.length > 0 ? ` (${assignment.relatedQueries.length})` : ''}
                </h3>
                {assignment.relatedQueries.length > 0 ? (
                  <>
                    <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                      <table className="w-full">
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--border)' }}>
                            <th className="text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary px-3 py-2">Query</th>
                            <th className="text-right text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary px-3 py-2 w-28">Intent</th>
                          </tr>
                        </thead>
                        <tbody>
                          {assignment.relatedQueries.map((q, i) => (
                            <tr key={i} style={{ borderBottom: i < assignment.relatedQueries.length - 1 ? '1px solid var(--border)' : undefined }}>
                              <td className="text-[13px] text-text-primary px-3 py-2">&ldquo;{q.query}&rdquo;</td>
                              <td className="text-right px-3 py-2">
                                <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-medium border border-border text-text-secondary rounded-full">{q.intent}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="text-[12px] text-text-secondary mt-2">
                      These queries are tracked in <a href="/prompt-tracking" className="text-accent hover:underline">Prompt Tracking</a> after publishing
                    </p>
                  </>
                ) : (
                  <div className="p-3 rounded-md text-[13px] text-text-secondary" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
                    No queries tracked yet
                  </div>
                )}

                {/* ─── Priority Factors ─── */}
                {Object.keys(assignment.priorityFactors).length > 0 && (
                  <>
                    <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">Priority Signals</h3>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(assignment.priorityFactors).map(([key, val]) => (
                        <div key={key} className="flex items-center justify-between p-2.5 rounded-md" style={{ border: '1px solid var(--border)' }}>
                          <span className="text-[12px] text-text-secondary capitalize">{key.replace(/_/g, ' ')}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-[3px] rounded-full bg-border overflow-hidden">
                              <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(val * 100)}%` }} />
                            </div>
                            <span className="font-mono text-[12px] font-semibold text-text-primary w-8 text-right">{Math.round(val * 100)}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {/* ─── Activity ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">Activity</h3>
                <div className="space-y-2.5">
                  {(assignment.activityLog.length > 0 ? assignment.activityLog : [{ action: 'Created by pipeline', date: assignment.createdAt, by: 'System' }]).map((entry, i) => (
                    <div key={i} className="flex items-center gap-2.5">
                      {entry.by === 'System' || entry.by === 'Pipeline' ? (
                        <div className="flex items-center justify-center w-5 h-5 rounded-full shrink-0" style={{ background: 'var(--surface-raised)', border: '1px solid var(--border)' }}>
                          <Settings size={10} className="text-text-tertiary" />
                        </div>
                      ) : (<UserAvatar name={entry.by} size={20} />)}
                      <div className="flex-1">
                        {entry.date && <span className="text-[12px] text-text-tertiary mr-2">{entry.date}</span>}
                        <span className="text-[12px] text-text-secondary">{entry.action}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
