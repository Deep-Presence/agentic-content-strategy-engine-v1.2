'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Link2, ExternalLink, Check, Flag, Settings } from 'lucide-react';
import type { Assignment } from './planner-data';
import { PERSONA_MAP } from './planner-data';

interface DetailDrawerProps {
  assignment: Assignment | null;
  onClose: () => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

function BrandLogo({ domain, size = 16 }: { domain: string; size?: number }) {
  return (
    <img src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`} alt={domain} width={size} height={size}
      style={{ borderRadius: 3 }}
      onError={(e) => { const t = e.target as HTMLImageElement; if (!t.dataset.fallback) { t.dataset.fallback = '1'; t.src = `https://logo.clearbit.com/${domain}`; } }} />
  );
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

const sourceStyles: Record<string, string> = {
  gap: 'bg-accent-subtle text-accent border-accent/30',
  strategic: 'bg-[rgba(147,51,234,0.08)] text-[#9333ea] border-[rgba(147,51,234,0.3)]',
  custom: 'bg-[var(--surface)] text-text-secondary border-border',
};
const sourceLabels: Record<string, string> = { gap: 'GAP ANALYSIS', strategic: 'STRATEGIC', custom: 'CUSTOM' };
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

              {/* Row 2: Title + cluster path */}
              <div className="px-5 pb-4">
                <h2 className="text-[18px] font-semibold text-text-primary leading-snug">{assignment.title}</h2>
                <p className="text-[13px] text-text-secondary mt-1">{assignment.cluster} <ChevronIcon /> {assignment.subcluster}</p>
              </div>
            </div>

            {/* ═══ SCROLLABLE: Pills → All content sections ═══ */}
            <div className="flex-1 overflow-y-auto">
              {/* Pills row */}
              <div className="px-5 pt-4 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="font-mono text-[12px] text-text-secondary">{assignment.id}</span>
                  <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.05em] border rounded-full ${sourceStyles[assignment.source]}`}>{sourceLabels[assignment.source]}</span>
                  <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-semibold uppercase border rounded-full ${stageStyles[assignment.stage]}`}>{assignment.stage}</span>
                  {assignment.format && (
                    <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-semibold uppercase border border-border text-text-secondary rounded-full">{assignment.format}</span>
                  )}
                  <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-medium border rounded-full ${intentStyles[assignment.intent]}`}>{assignment.intent}</span>
                  {assignment.effort && (
                    <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-semibold uppercase border rounded-full ${effortStyles[assignment.effort]}`}>{assignment.effort} effort</span>
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
                  <div className="grid grid-cols-3 gap-2">
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

                {/* ─── Competitors ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">Who Currently Owns This Space</h3>
                {assignment.competitors.length > 0 ? (
                  <div className="space-y-2">
                    {assignment.competitors.slice(0, 3).map((c) => (
                      <div key={c.rank} className="p-2.5 rounded-md flex items-start gap-2" style={{ border: '1px solid var(--border)' }}>
                        <span className="font-mono text-[11px] text-text-tertiary mt-0.5">#{c.rank}</span>
                        <BrandLogo domain={c.domain} size={16} />
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] font-medium text-text-primary truncate">{c.title}</p>
                          <a href={`https://${c.url}`} target="_blank" rel="noopener noreferrer" className="text-[11px] text-accent hover:underline inline-flex items-center gap-0.5">
                            {c.url} <ExternalLink size={9} />
                          </a>
                        </div>
                        <div className="flex items-center gap-2 shrink-0 text-[11px] text-text-secondary">
                          <span>{c.words.toLocaleString()} words</span>
                          <span className={c.faq ? 'text-success' : 'text-error'}>FAQ {c.faq ? '✓' : '✗'}</span>
                          <span className={c.tables ? 'text-success' : 'text-error'}>Tables {c.tables ? '✓' : '✗'}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 rounded-md" style={{ background: 'var(--success-subtle)', border: '1px solid rgba(52,178,123,0.2)' }}>
                    <div className="flex items-center gap-2">
                      <Flag size={14} className="text-success" />
                      <span className="text-[13px] font-semibold text-success">New Territory — No Competition</span>
                    </div>
                    <p className="text-[12px] text-text-secondary mt-1">No competitor data yet. First-mover opportunity.</p>
                  </div>
                )}

                {/* ─── Persona Affinity ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">Persona Affinity</h3>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(assignment.personaScores).map(([key, score]) => {
                    const isPrimary = assignment.persona === key;
                    return (
                      <div key={key} className="p-2.5 rounded-md" style={{
                        border: isPrimary ? '1px solid var(--accent)' : '1px solid var(--border)',
                        background: isPrimary ? 'var(--accent-subtle)' : 'var(--surface)',
                      }}>
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[15px] font-semibold text-text-primary">{score}%</span>
                          <div className="w-12 h-[3px] rounded-full bg-border overflow-hidden">
                            <motion.div className="h-full rounded-full bg-accent" initial={{ width: 0 }} animate={{ width: `${score}%` }}
                              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }} />
                          </div>
                        </div>
                        <p className="text-[12px] font-medium text-text-primary mt-0.5">{PERSONA_MAP[key]?.full}</p>
                        {isPrimary && <span className="text-[11px] font-semibold text-accent uppercase">Primary target</span>}
                      </div>
                    );
                  })}
                </div>

                {/* ─── Queries ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">
                  Queries This Content Would Answer{assignment.relatedQueries.length > 0 ? ` (${assignment.relatedQueries.length} queries, ${assignment.relatedQueries.reduce((sum, q) => sum + q.fanouts, 0)} total fanouts)` : ''}
                </h3>
                {assignment.relatedQueries.length > 0 ? (
                  <>
                    <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                      <table className="w-full">
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--border)' }}>
                            <th className="text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary px-3 py-2">Query</th>
                            <th className="text-right text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary px-3 py-2 w-16">Fanouts</th>
                            <th className="text-right text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary px-3 py-2 w-28">Intent</th>
                          </tr>
                        </thead>
                        <tbody>
                          {assignment.relatedQueries.map((q, i) => (
                            <tr key={i} style={{ borderBottom: i < assignment.relatedQueries.length - 1 ? '1px solid var(--border)' : undefined }}>
                              <td className="text-[13px] text-text-primary px-3 py-2">&ldquo;{q.query}&rdquo;</td>
                              <td className="text-right font-mono text-[13px] text-text-primary px-3 py-2">{q.fanouts}</td>
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

                {/* ─── Activity ─── */}
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-secondary mt-6 mb-3">Activity</h3>
                <div className="space-y-2.5">
                  {(assignment.activityLog.length > 0 ? assignment.activityLog : [{ action: 'Created by pipeline', date: assignment.createdAt, by: 'System' }]).map((entry, i) => (
                    <div key={i} className="flex items-center gap-2.5">
                      {entry.by === 'System' ? (
                        <div className="flex items-center justify-center w-5 h-5 rounded-full shrink-0" style={{ background: 'var(--surface-raised)', border: '1px solid var(--border)' }}>
                          <Settings size={10} className="text-text-tertiary" />
                        </div>
                      ) : (<UserAvatar name={entry.by} size={20} />)}
                      <div className="flex-1">
                        <span className="text-[12px] text-text-tertiary mr-2">{entry.date}</span>
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
