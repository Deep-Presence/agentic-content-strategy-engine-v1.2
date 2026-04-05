'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Check, Upload, FileText } from 'lucide-react';
import type { Assignment, Cluster } from './planner-data';
import type { CreateCustomAssignmentData } from '../_hooks/usePlannerData';

interface CustomTopicModalProps {
  open: boolean;
  onClose: () => void;
  onAdd: (data: CreateCustomAssignmentData) => void;
  nextId: string;
  clusters: Cluster[];
}

interface UploadedFile {
  name: string;
  size: string;
}

const FORMATS = ['Guide', 'Comparison', 'Tutorial', 'Listicle', 'Case Study'] as const;
const STAGES = ['TOFU', 'MOFU', 'BOFU'] as const;
const PERSONAS = [
  { id: 'sf', label: 'Solo Founder' },
  { id: 'pm', label: 'Product Manager' },
  { id: 'da', label: 'Agency Owner' },
  { id: 'te', label: 'Technical Engineer' },
] as const;
const INTENTS = ['Informational', 'Commercial', 'Navigational', 'Transactional'] as const;

const RESEARCH_STEPS = [
  'Scanning AI citations for related topics',
  'Identifying competitors in this space',
  'Calculating citation opportunity',
  'Matching persona affinity',
  'Generating recommendation',
];

export function CustomTopicModal({ open, onClose, onAdd, nextId, clusters }: CustomTopicModalProps) {
  const [step, setStep] = useState(1);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [cluster, setCluster] = useState('');
  const [format, setFormat] = useState<typeof FORMATS[number]>('Guide');
  const [stage, setStage] = useState<typeof STAGES[number]>('TOFU');
  const [persona, setPersona] = useState('sf');
  const [intent, setIntent] = useState<typeof INTENTS[number]>('Informational');
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [files, setFiles] = useState<UploadedFile[]>([]);

  const [resultCitOpp] = useState(() => Math.round(55 + Math.random() * 30));
  const [resultEstCit] = useState(() => Math.round(6 + Math.random() * 12));

  const reset = useCallback(() => {
    setStep(1); setTitle(''); setDescription(''); setCluster('');
    setFormat('Guide'); setStage('TOFU'); setPersona('sf');
    setIntent('Informational'); setCompletedSteps([]); setFiles([]);
  }, []);

  const handleClose = useCallback(() => { onClose(); setTimeout(reset, 200); }, [onClose, reset]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') handleClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [handleClose]);

  useEffect(() => {
    if (step !== 2) return;
    setCompletedSteps([]);
    const timers: ReturnType<typeof setTimeout>[] = [];
    RESEARCH_STEPS.forEach((_, i) => {
      timers.push(setTimeout(() => {
        setCompletedSteps(prev => [...prev, i]);
        if (i === RESEARCH_STEPS.length - 1) timers.push(setTimeout(() => setStep(3), 400));
      }, 350 * (i + 1)));
    });
    return () => timers.forEach(clearTimeout);
  }, [step]);

  const handleAdd = () => {
    const selectedCluster = clusters.find(c => c.id === cluster);
    const subdomainName = selectedCluster?.subclusters[0]?.name || undefined;
    const data: CreateCustomAssignmentData = {
      topic_text: title,
      subdomain_name: subdomainName,
      buyer_stage: stage.toLowerCase(),
      intent_type: intent.toLowerCase(),
      persona_id: persona,
      persona_name: PERSONAS.find(p => p.id === persona)?.label,
      priority_score: resultCitOpp / 100,
    };
    onAdd(data);
    handleClose();
  };

  const handleSimulateUpload = () => {
    setFiles(prev => [...prev, { name: `reference-doc-${prev.length + 1}.pdf`, size: `${(Math.random() * 3 + 0.5).toFixed(1)} MB` }]);
  };

  const stageColors: Record<string, string> = {
    TOFU: 'bg-accent-subtle text-accent border-accent/50',
    MOFU: 'bg-warning-subtle text-warning border-warning/50',
    BOFU: 'bg-success-subtle text-success border-success/50',
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center"
            style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
          >
            <motion.div
              className="w-[560px] max-h-[80vh] overflow-y-auto rounded-lg"
              style={{ background: 'var(--surface-raised)', border: '1px solid var(--border)' }}
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
                <h2 className="text-[18px] font-semibold text-text-primary">
                  {step === 1 ? 'Custom Topic' : step === 2 ? 'Analyzing...' : 'Analysis Complete'}
                </h2>
                <button onClick={handleClose} className="flex items-center justify-center w-[28px] h-[28px] rounded text-text-secondary hover:text-text-primary hover:bg-[var(--surface)] transition-colors">
                  <X size={15} />
                </button>
              </div>

              {/* Step 1 */}
              {step === 1 && (
                <div className="px-5 py-4 space-y-3.5">
                  <div>
                    <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Topic Title</label>
                    <input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g., How to Migrate from Bubble to Lovable"
                      className="w-full h-[34px] px-3 text-[14px] rounded border bg-transparent text-text-primary placeholder:text-text-tertiary focus:border-accent focus:ring-0 outline-none transition-colors"
                      style={{ borderColor: 'var(--border)' }} />
                  </div>
                  <div>
                    <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">What should this content cover?</label>
                    <textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe the angle, audience, or specific need..." rows={3}
                      className="w-full px-3 py-2 text-[14px] rounded border bg-transparent text-text-primary placeholder:text-text-tertiary focus:border-accent focus:ring-0 outline-none resize-none transition-colors"
                      style={{ borderColor: 'var(--border)' }} />
                  </div>

                  {/* Document Upload */}
                  <div>
                    <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Reference Materials (optional)</label>
                    <p className="text-[12px] text-text-tertiary mb-2">Upload existing content, research, or briefs that relate to this topic.</p>
                    <div
                      className="flex items-center justify-center h-[72px] rounded-md cursor-pointer transition-colors duration-150 hover:border-border-strong"
                      style={{ border: '1px dashed var(--border)', background: 'var(--surface)' }}
                      onClick={handleSimulateUpload}
                    >
                      <div className="flex items-center gap-2 text-text-secondary">
                        <Upload size={14} />
                        <span className="text-[13px]">Upload files or drag &amp; drop here</span>
                      </div>
                    </div>
                    <p className="text-[11px] text-text-tertiary mt-1">Supported: PDF, DOCX, TXT, MD — max 10MB per file</p>
                    {files.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {files.map((f, i) => (
                          <div key={i} className="flex items-center gap-2 py-1 text-[12px]">
                            <FileText size={13} className="text-text-tertiary" />
                            <span className="text-text-primary flex-1">{f.name}</span>
                            <span className="text-text-tertiary">{f.size}</span>
                            <button onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))} className="text-text-tertiary hover:text-error transition-colors">
                              <X size={12} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Target Cluster</label>
                    <select value={cluster} onChange={e => setCluster(e.target.value)}
                      className="w-full h-[34px] px-3 text-[14px] rounded border bg-transparent text-text-primary cursor-pointer focus:border-accent outline-none"
                      style={{ borderColor: 'var(--border)' }}>
                      <option value="">Select cluster...</option>
                      {clusters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                      <option value="new">+ New cluster</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Format</label>
                    <div className="flex flex-wrap gap-1.5">
                      {FORMATS.map(f => (
                        <button key={f} onClick={() => setFormat(f)}
                          className={`h-[28px] px-3 text-[12px] font-medium rounded border transition-colors duration-150 ${format === f ? 'bg-accent text-white border-accent' : 'bg-transparent text-text-secondary border-border hover:border-border-strong'}`}>{f}</button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Funnel Stage</label>
                    <div className="flex gap-1.5">
                      {STAGES.map(s => (
                        <button key={s} onClick={() => setStage(s)}
                          className={`h-[28px] px-3 text-[12px] font-semibold uppercase rounded border transition-colors duration-150 ${stage === s ? stageColors[s] : 'bg-transparent text-text-secondary border-border hover:border-border-strong'}`}>{s}</button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Primary Persona</label>
                    <div className="flex flex-wrap gap-1.5">
                      {PERSONAS.map(p => (
                        <button key={p.id} onClick={() => setPersona(p.id)}
                          className={`h-[28px] px-3 text-[12px] font-medium rounded border transition-colors duration-150 ${persona === p.id ? 'bg-accent text-white border-accent' : 'bg-transparent text-text-secondary border-border hover:border-border-strong'}`}>{p.label}</button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary block mb-1">Intent</label>
                    <div className="flex flex-wrap gap-1.5">
                      {INTENTS.map(i => (
                        <button key={i} onClick={() => setIntent(i)}
                          className={`h-[28px] px-3 text-[12px] font-medium rounded border transition-colors duration-150 ${intent === i ? 'bg-accent text-white border-accent' : 'bg-transparent text-text-secondary border-border hover:border-border-strong'}`}>{i}</button>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                    <button onClick={handleClose} className="h-[32px] px-4 text-[13px] font-semibold text-text-secondary hover:text-text-primary transition-colors">Cancel</button>
                    <button onClick={() => setStep(2)} disabled={!title.trim()}
                      className="h-[32px] px-4 text-[13px] font-semibold rounded text-white transition-colors disabled:opacity-40"
                      style={{ background: 'var(--accent)' }}>Analyze Citation Potential</button>
                  </div>
                </div>
              )}

              {/* Step 2 */}
              {step === 2 && (
                <div className="px-5 py-6 space-y-3">
                  {RESEARCH_STEPS.map((text, i) => {
                    const done = completedSteps.includes(i);
                    return (
                      <motion.div key={i} className="flex items-center gap-2.5" initial={{ opacity: 0.4 }} animate={{ opacity: done ? 1 : 0.4 }} transition={{ duration: 0.2 }}>
                        <div className="w-4 h-4 flex items-center justify-center">
                          {done ? (
                            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}>
                              <Check size={14} className="text-success" strokeWidth={2.5} />
                            </motion.div>
                          ) : (<div className="w-2.5 h-2.5 rounded-full border-2 border-text-tertiary" />)}
                        </div>
                        <span className={`text-[13px] transition-colors duration-200 ${done ? 'text-text-primary font-medium' : 'text-text-tertiary'}`}>{text}</span>
                      </motion.div>
                    );
                  })}
                </div>
              )}

              {/* Step 3 */}
              {step === 3 && (
                <div className="px-5 py-4 space-y-3">
                  <div className="flex items-center gap-2 p-3 rounded-md" style={{ background: 'var(--success-subtle)', border: '1px solid rgba(52,178,123,0.2)' }}>
                    <Check size={14} className="text-success" strokeWidth={2.5} />
                    <span className="text-[13px] font-semibold text-success">Strong citation potential detected</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-md" style={{ border: '1px solid var(--border)' }}>
                      <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Citation Opportunity</span>
                      <p className="font-mono text-[24px] font-semibold text-accent mt-1">{resultCitOpp}%</p>
                    </div>
                    <div className="p-3 rounded-md" style={{ border: '1px solid var(--border)' }}>
                      <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Est. Citations</span>
                      <p className="font-mono text-[24px] font-semibold text-accent mt-1">~{resultEstCit}</p>
                    </div>
                  </div>
                  <div className="p-3 rounded-md flex items-center gap-2" style={{ border: '1px solid var(--border)' }}>
                    <img src="https://www.google.com/s2/favicons?domain=bolt.new&sz=32" alt="bolt.new" width={16} height={16} style={{ borderRadius: 3 }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-medium text-text-primary">Related Content — bolt.new</p>
                      <p className="text-[12px] text-text-secondary">1,800 words · FAQ ✗ · Tables ✗</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-2 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                    <button onClick={handleClose} className="h-[32px] px-4 text-[13px] font-semibold text-text-secondary hover:text-text-primary transition-colors">Cancel</button>
                    <button onClick={handleAdd} className="flex items-center gap-1 h-[32px] px-4 text-[13px] font-semibold rounded text-white transition-colors" style={{ background: 'var(--success)' }}>
                      <Check size={14} strokeWidth={2} /> Add to Priority Queue
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
