'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, Check, Upload, FileText, ChevronDown, ChevronRight, Pencil, Eye } from 'lucide-react';
import { INITIATIVES, formatPersonaName, ASSIGNMENTS } from './planner-data';
import type { Initiative } from './planner-data';

interface InitiativesSidebarProps {
  open: boolean;
  onClose: () => void;
  onInitiativeComplete: (count: number) => void;
}

interface UploadedFile { name: string; size: string; }

const PERSONAS = [
  { id: 'sf', label: 'Solo Founder' },
  { id: 'pm', label: 'Product Manager' },
  { id: 'da', label: 'Agency Owner' },
  { id: 'te', label: 'Technical Engineer' },
] as const;
const STAGES = ['TOFU', 'MOFU', 'BOFU'] as const;
const RESEARCH_STEPS = [
  'Analyzing AI citations in target space',
  'Mapping competitor content landscape',
  'Identifying underserved topics',
  'Scoring citation opportunities',
  'Generating content recommendations',
];
const stageStyles: Record<string, string> = {
  TOFU: 'bg-accent-subtle text-accent border-accent/30',
  MOFU: 'bg-warning-subtle text-warning border-warning/30',
  BOFU: 'bg-success-subtle text-success border-success/30',
};

function NewInitiativeModal({ open, onClose, onComplete }: { open: boolean; onClose: () => void; onComplete: (count: number) => void }) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [direction, setDirection] = useState('');
  const [personas, setPersonas] = useState<Set<string>>(new Set());
  const [stages, setStages] = useState<Set<string>>(new Set());
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [resultCount] = useState(() => Math.round(4 + Math.random() * 4));

  const reset = useCallback(() => { setStep(1); setName(''); setDirection(''); setPersonas(new Set()); setStages(new Set()); setCompletedSteps([]); setFiles([]); }, []);
  const handleClose = useCallback(() => { onClose(); setTimeout(reset, 200); }, [onClose, reset]);

  useEffect(() => { const h = (e: KeyboardEvent) => { if (e.key === 'Escape') handleClose(); }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [handleClose]);

  useEffect(() => {
    if (step !== 2) return;
    setCompletedSteps([]);
    const timers: ReturnType<typeof setTimeout>[] = [];
    RESEARCH_STEPS.forEach((_, i) => { timers.push(setTimeout(() => { setCompletedSteps(prev => [...prev, i]); if (i === RESEARCH_STEPS.length - 1) timers.push(setTimeout(() => setStep(3), 400)); }, 350 * (i + 1))); });
    return () => timers.forEach(clearTimeout);
  }, [step]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[60] flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={handleClose}>
          <motion.div className="w-[560px] max-h-[80vh] overflow-y-auto rounded-lg"
            style={{ background: 'var(--surface-raised)', border: '1px solid var(--border)' }}
            initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
              <h2 className="text-[18px] font-semibold text-text-primary">{step === 1 ? 'New Initiative' : step === 2 ? 'Researching...' : 'Research Complete'}</h2>
              <button onClick={handleClose} className="flex items-center justify-center w-[28px] h-[28px] rounded text-text-secondary hover:text-text-primary transition-colors"><X size={15} /></button>
            </div>

            {step === 1 && (
              <div className="px-5 py-4 space-y-3.5">
                <div>
                  <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Initiative Name</label>
                  <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g., Enterprise Security Push"
                    className="w-full h-[34px] px-3 text-[14px] rounded border bg-transparent text-text-primary placeholder:text-text-tertiary focus:border-[#9333ea] focus:ring-0 outline-none" style={{ borderColor: 'var(--border)' }} />
                </div>
                <div>
                  <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Strategic Direction</label>
                  <textarea value={direction} onChange={e => setDirection(e.target.value)} placeholder="Describe the audience, topics, and goals..." rows={3}
                    className="w-full px-3 py-2 text-[14px] rounded border bg-transparent text-text-primary placeholder:text-text-tertiary focus:border-[#9333ea] focus:ring-0 outline-none resize-none" style={{ borderColor: 'var(--border)' }} />
                </div>
                <div>
                  <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Supporting Documents (optional)</label>
                  <div className="flex items-center justify-center h-[64px] rounded-md cursor-pointer transition-colors hover:border-border-strong"
                    style={{ border: '1px dashed var(--border)', background: 'var(--surface)' }}
                    onClick={() => setFiles(prev => [...prev, { name: `doc-${prev.length + 1}.pdf`, size: `${(Math.random() * 3 + 0.5).toFixed(1)} MB` }])}>
                    <div className="flex items-center gap-2 text-text-secondary"><Upload size={14} /><span className="text-[13px]">Upload files or drag &amp; drop</span></div>
                  </div>
                  {files.length > 0 && <div className="mt-2 space-y-1">{files.map((f, i) => (
                    <div key={i} className="flex items-center gap-2 py-1 text-[12px]"><FileText size={13} className="text-text-tertiary" /><span className="text-text-primary flex-1">{f.name}</span><span className="text-text-tertiary">{f.size}</span>
                      <button onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))} className="text-text-tertiary hover:text-error"><X size={12} /></button></div>))}</div>}
                </div>
                <div>
                  <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Target Personas</label>
                  <div className="flex flex-wrap gap-1.5">{PERSONAS.map(p => (
                    <button key={p.id} onClick={() => setPersonas(prev => { const n = new Set(prev); if (n.has(p.id)) n.delete(p.id); else n.add(p.id); return n; })}
                      className={`h-[28px] px-3 text-[12px] font-medium rounded border transition-colors ${personas.has(p.id) ? 'bg-[rgba(147,51,234,0.08)] text-[#9333ea] border-[rgba(147,51,234,0.5)]' : 'bg-transparent text-text-secondary border-border hover:border-border-strong'}`}>{p.label}</button>
                  ))}</div>
                </div>
                <div>
                  <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Target Stages</label>
                  <div className="flex gap-1.5">{STAGES.map(s => (
                    <button key={s} onClick={() => setStages(prev => { const n = new Set(prev); if (n.has(s)) n.delete(s); else n.add(s); return n; })}
                      className={`h-[28px] px-3 text-[12px] font-semibold uppercase rounded border transition-colors ${stages.has(s) ? stageStyles[s] : 'bg-transparent text-text-secondary border-border hover:border-border-strong'}`}>{s}</button>
                  ))}</div>
                </div>
                <div className="flex items-center justify-end gap-2 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                  <button onClick={handleClose} className="h-[32px] px-4 text-[13px] font-semibold text-text-secondary hover:text-text-primary">Cancel</button>
                  <button onClick={() => setStep(2)} disabled={!name.trim()} className="h-[32px] px-4 text-[13px] font-semibold rounded text-white disabled:opacity-40" style={{ background: '#9333ea' }}>Research This Space</button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="px-5 py-6 space-y-3">{RESEARCH_STEPS.map((text, i) => {
                const done = completedSteps.includes(i);
                return (<motion.div key={i} className="flex items-center gap-2.5" initial={{ opacity: 0.4 }} animate={{ opacity: done ? 1 : 0.4 }}>
                  <div className="w-4 h-4 flex items-center justify-center">{done ? <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}><Check size={14} className="text-[#9333ea]" strokeWidth={2.5} /></motion.div> : <div className="w-2.5 h-2.5 rounded-full border-2 border-text-tertiary" />}</div>
                  <span className={`text-[13px] ${done ? 'text-text-primary font-medium' : 'text-text-tertiary'}`}>{text}</span>
                </motion.div>);
              })}</div>
            )}

            {step === 3 && (
              <div className="px-5 py-4 space-y-3">
                <div className="flex items-center gap-2 p-3 rounded-md" style={{ background: 'rgba(147,51,234,0.08)', border: '1px solid rgba(147,51,234,0.2)' }}>
                  <Check size={14} className="text-[#9333ea]" strokeWidth={2.5} />
                  <span className="text-[13px] font-semibold text-[#9333ea]">Found {resultCount} high-potential topics</span>
                </div>
                <p className="text-[13px] text-text-secondary">{resultCount} recommendations will appear in Priority Queue tagged as Strategic.</p>
                <div className="flex items-center justify-end gap-2 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                  <button onClick={() => { onComplete(resultCount); handleClose(); }} className="h-[32px] px-4 text-[13px] font-semibold rounded text-white" style={{ background: '#9333ea' }}>View in Priority Queue</button>
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function InitiativesSidebar({ open, onClose, onInitiativeComplete }: InitiativesSidebarProps) {
  const [showNewModal, setShowNewModal] = useState(false);
  const [expandedInit, setExpandedInit] = useState<string | null>(null);

  useEffect(() => { const h = (e: KeyboardEvent) => { if (e.key === 'Escape' && !showNewModal) onClose(); }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [onClose, showNewModal]);

  // Get assignments belonging to each initiative
  const getInitAssignments = (initName: string) => ASSIGNMENTS.filter(a => a.initiative === initName);

  return (
    <>
      <AnimatePresence>
        {open && (
          <>
            <motion.div className="fixed inset-0 z-40" style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
            <motion.div className="fixed top-0 left-0 bottom-0 z-50 w-[380px] flex flex-col"
              style={{ background: 'var(--surface)', borderRight: '1px solid var(--border)', boxShadow: 'var(--shadow-float)' }}
              initial={{ x: '-100%', opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: '-100%', opacity: 0 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}>

              <div className="flex items-center justify-between px-4 py-3 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
                <h2 className="text-[16px] font-semibold text-text-primary">Strategic Initiatives</h2>
                <button onClick={onClose} className="flex items-center justify-center w-[28px] h-[28px] rounded text-text-secondary hover:text-text-primary transition-colors"><X size={15} /></button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-3">
                <p className="text-[13px] text-text-secondary leading-relaxed mb-3">Define strategic content directions. The AI researches your target space and generates ranked recommendations.</p>

                <button onClick={() => setShowNewModal(true)}
                  className="w-full flex items-center justify-center gap-1.5 h-[36px] rounded text-[13px] font-semibold transition-colors"
                  style={{ border: '1px dashed rgba(147,51,234,0.5)', color: '#9333ea' }}>
                  <Plus size={14} /> New Initiative
                </button>

                <div className="mt-4 space-y-2">
                  {INITIATIVES.map((init) => {
                    const isExpanded = expandedInit === init.id;
                    const initAssignments = getInitAssignments(init.name);
                    return (
                      <motion.div key={init.id} className="rounded-md overflow-hidden"
                        style={{ border: '1px solid var(--border)', borderLeft: '3px solid #9333ea' }}
                        initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
                        {/* Initiative header */}
                        <div className="p-3">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <h3 className="text-[13px] font-semibold text-text-primary">{init.name}</h3>
                              <p className="text-[12px] text-text-secondary mt-0.5">{init.description}</p>
                            </div>
                            <button className="flex items-center justify-center w-6 h-6 rounded text-text-tertiary hover:text-text-primary hover:bg-[var(--surface-raised)] transition-colors ml-2 shrink-0">
                              <Pencil size={12} />
                            </button>
                          </div>
                          <div className="flex flex-wrap gap-1 mt-2">
                            {init.personas.map(pid => (
                              <span key={pid} className="inline-flex items-center px-2 py-0.5 text-[11px] font-medium rounded-full bg-[rgba(147,51,234,0.08)] text-[#9333ea] border border-[rgba(147,51,234,0.3)]">
                                {formatPersonaName(pid)}
                              </span>
                            ))}
                          </div>
                          <div className="flex items-center justify-between mt-2">
                            <p className="text-[11px] text-text-tertiary">
                              <span className="font-mono">{init.assignmentCount}</span> assignments · Created {init.created}
                            </p>
                            <button onClick={() => setExpandedInit(isExpanded ? null : init.id)}
                              className="flex items-center gap-1 text-[11px] text-accent hover:underline">
                              <Eye size={11} /> {isExpanded ? 'Hide' : 'Preview'}
                              {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                            </button>
                          </div>
                        </div>

                        {/* Expandable assignment preview */}
                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.2 }}
                              style={{ overflow: 'hidden' }}
                            >
                              <div style={{ borderTop: '1px solid var(--border)' }}>
                                {initAssignments.length > 0 ? initAssignments.map((a, i) => (
                                  <div key={a.id} className="flex items-center gap-2 px-3 py-2 text-[12px]"
                                    style={{ borderBottom: i < initAssignments.length - 1 ? '1px solid var(--border)' : undefined, background: 'var(--surface)' }}>
                                    <span className="font-mono text-[11px] text-text-tertiary shrink-0">{a.displayId}</span>
                                    <span className="text-text-primary flex-1 truncate">{a.title}</span>
                                    <span className={`inline-flex items-center px-1.5 py-px text-[10px] font-semibold uppercase border rounded-full ${stageStyles[a.stage]}`}>{a.stage}</span>
                                    <span className="font-mono text-[11px] text-accent">{Math.round(a.citationOpp * 100)}%</span>
                                  </div>
                                )) : (
                                  <div className="px-3 py-3 text-[12px] text-text-tertiary" style={{ background: 'var(--surface)' }}>No assignments yet</div>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
      <NewInitiativeModal open={showNewModal} onClose={() => setShowNewModal(false)} onComplete={onInitiativeComplete} />
    </>
  );
}
