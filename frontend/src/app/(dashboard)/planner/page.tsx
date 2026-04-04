'use client';

import { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Plus, RotateCcw, X } from 'lucide-react';
import { BRAND_PREFIX } from './_components/planner-data';
import type { Assignment, RejectedItem } from './_components/planner-data';
import { usePlannerData } from './_hooks/usePlannerData';
import type { CreateCustomAssignmentData } from './_hooks/usePlannerData';
import { PriorityQueue } from './_components/PriorityQueue';
import { ClusterExplorer } from './_components/ClusterExplorer';
import { DetailDrawer } from './_components/DetailDrawer';
import { CustomTopicModal } from './_components/CustomTopicModal';
import { InitiativesSidebar } from './_components/InitiativesSidebar';

type ViewMode = 'queue' | 'explorer' | 'rejected';
type StageFilter = 'all' | 'TOFU' | 'MOFU' | 'BOFU';
type PersonaFilter = 'all' | 'sf' | 'pm' | 'da' | 'te';
type SourceFilter = 'all' | 'gap' | 'strategic' | 'custom';
type IntentFilter = 'all' | 'Informational' | 'Commercial' | 'Navigational' | 'Transactional';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error';
}

export default function ContentPlannerPage() {
  const plannerData = usePlannerData();
  const { assignments, rejected, clusters, isLoading, isEmpty, error, refetch } = plannerData;

  const [view, setView] = useState<ViewMode>('queue');

  // Filters
  const [stageFilter, setStageFilter] = useState<StageFilter>('all');
  const [personaFilter, setPersonaFilter] = useState<PersonaFilter>('all');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [intentFilter, setIntentFilter] = useState<IntentFilter>('all');

  // UI state
  const [drawerAssignment, setDrawerAssignment] = useState<Assignment | null>(null);
  const [customTopicOpen, setCustomTopicOpen] = useState(false);
  const [initiativesOpen, setInitiativesOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3000);
  }, []);

  const filtered = useMemo(() => {
    return assignments.filter(a => {
      if (stageFilter !== 'all' && a.stage !== stageFilter) return false;
      if (personaFilter !== 'all' && a.persona !== personaFilter) return false;
      if (sourceFilter !== 'all' && a.source !== sourceFilter) return false;
      if (intentFilter !== 'all' && a.intent !== intentFilter) return false;
      return true;
    });
  }, [assignments, stageFilter, personaFilter, sourceFilter, intentFilter]);

  const hasActiveFilters = stageFilter !== 'all' || personaFilter !== 'all' || sourceFilter !== 'all' || intentFilter !== 'all';

  const clearFilters = () => {
    setStageFilter('all');
    setPersonaFilter('all');
    setSourceFilter('all');
    setIntentFilter('all');
  };

  const handleApprove = useCallback(async (ids: string[]) => {
    showToast(`✓ ${ids.length} topic${ids.length > 1 ? 's' : ''} approved → Content Studio`);
    setDrawerAssignment(null);
    try {
      await plannerData.approveAssignments(ids);
    } catch {
      showToast('Failed to update status', 'error');
    }
  }, [plannerData, showToast]);

  const handleReject = useCallback(async (ids: string[]) => {
    showToast(`✗ ${ids.length} topic${ids.length > 1 ? 's' : ''} rejected`);
    setDrawerAssignment(null);
    try {
      await plannerData.rejectAssignments(ids);
    } catch {
      showToast('Failed to update status', 'error');
    }
  }, [plannerData, showToast]);

  const handleRestore = useCallback(async (id: string) => {
    const item = rejected.find(r => r.id === id);
    if (!item) return;
    showToast(`✓ ${item.title.slice(0, 30)}... restored to queue`);
    try {
      await plannerData.restoreAssignment(id);
    } catch {
      showToast('Failed to restore assignment', 'error');
    }
  }, [plannerData, rejected, showToast]);

  const handleAddCustom = useCallback(async (data: CreateCustomAssignmentData) => {
    showToast('✓ Custom topic added to Priority Queue');
    try {
      await plannerData.createAssignment(data);
    } catch {
      showToast('Failed to create topic', 'error');
    }
  }, [plannerData, showToast]);

  const handleInitiativeComplete = useCallback((count: number) => {
    setInitiativesOpen(false);
    setView('queue');
    setSourceFilter('strategic');
    showToast(`✓ ${count} topics generated from initiative`);
  }, [showToast]);

  const nextId = `${BRAND_PREFIX}-${String(assignments.length + rejected.length + 1).padStart(3, '0')}`;

  const personaLabels: Record<string, string> = {
    all: 'All', sf: 'Solo Founder', pm: 'Product Manager', da: 'Agency Owner', te: 'Technical Engineer',
  };

  return (
    <div className="flex flex-col h-full -m-4 overflow-hidden">
      {/* Page Header */}
      <div className="flex items-center justify-between px-6 pt-5 pb-2 shrink-0">
        <div>
          <h1 className="text-[24px] font-semibold text-text-primary tracking-[-0.02em]">Content Planner</h1>
          <p className="text-[14px] text-text-secondary">Well-researched content recommendations ranked by citation potential</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setInitiativesOpen(true)}
            className="flex items-center gap-1.5 h-[32px] px-4 text-[13px] font-semibold rounded transition-colors duration-150"
            style={{ background: 'rgba(147,51,234,0.08)', color: '#9333ea', border: '1px solid rgba(147,51,234,0.3)' }}
          >
            <Sparkles size={14} /> Initiatives
          </button>
          <button
            onClick={() => setCustomTopicOpen(true)}
            className="flex items-center gap-1.5 h-[32px] px-4 text-[13px] font-semibold rounded transition-colors duration-150"
            style={{ border: '1px solid var(--border)', color: 'var(--text-primary)' }}
          >
            <Plus size={14} /> Custom Topic
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center h-10 px-6 shrink-0 gap-0 overflow-x-hidden" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-0 flex-1">
          {/* Stage */}
          <div className="flex items-center gap-2 pr-3" style={{ borderRight: '1px solid var(--border)' }}>
            <span className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Stage</span>
            <select value={stageFilter} onChange={e => setStageFilter(e.target.value as StageFilter)}
              className="h-[26px] px-2 text-[13px] rounded border bg-transparent text-text-primary cursor-pointer outline-none"
              style={{ borderColor: 'var(--border)' }}>
              <option value="all">All</option>
              <option value="TOFU">TOFU</option>
              <option value="MOFU">MOFU</option>
              <option value="BOFU">BOFU</option>
            </select>
          </div>
          {/* Persona */}
          <div className="flex items-center gap-2 px-3" style={{ borderRight: '1px solid var(--border)' }}>
            <span className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Persona</span>
            <select value={personaFilter} onChange={e => setPersonaFilter(e.target.value as PersonaFilter)}
              className="h-[26px] px-2 text-[13px] rounded border bg-transparent text-text-primary cursor-pointer outline-none"
              style={{ borderColor: 'var(--border)' }}>
              {Object.entries(personaLabels).map(([k, v]) => (<option key={k} value={k}>{v}</option>))}
            </select>
          </div>
          {/* Source */}
          <div className="flex items-center gap-2 px-3" style={{ borderRight: '1px solid var(--border)' }}>
            <span className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Source</span>
            <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value as SourceFilter)}
              className="h-[26px] px-2 text-[13px] rounded border bg-transparent text-text-primary cursor-pointer outline-none"
              style={{ borderColor: 'var(--border)' }}>
              <option value="all">All</option>
              <option value="gap">Gap Analysis</option>
              <option value="strategic">Strategic</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          {/* Intent (Fix 4) */}
          <div className="flex items-center gap-2 px-3">
            <span className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Intent</span>
            <select value={intentFilter} onChange={e => setIntentFilter(e.target.value as IntentFilter)}
              className="h-[26px] px-2 text-[13px] rounded border bg-transparent text-text-primary cursor-pointer outline-none"
              style={{ borderColor: 'var(--border)' }}>
              <option value="all">All</option>
              <option value="Informational">Informational</option>
              <option value="Commercial">Commercial</option>
              <option value="Navigational">Navigational</option>
              <option value="Transactional">Transactional</option>
            </select>
          </div>
          {/* Clear */}
          {hasActiveFilters && (
            <button onClick={clearFilters} className="flex items-center gap-1 ml-3 text-[13px] text-text-secondary hover:text-text-primary transition-colors">
              <X size={13} /> Clear
            </button>
          )}
        </div>

        {/* View Toggle */}
        <div className="flex items-center rounded overflow-hidden" style={{ border: '1px solid var(--border)' }}>
          {([
            { id: 'queue', label: 'Priority Queue' },
            { id: 'explorer', label: 'Cluster Explorer' },
            { id: 'rejected', label: `Rejected (${rejected.length})` },
          ] as const).map(tab => (
            <button
              key={tab.id}
              onClick={() => setView(tab.id)}
              className="h-[28px] px-3 text-[13px] font-medium transition-colors duration-150"
              style={{
                background: view === tab.id ? 'var(--accent)' : 'transparent',
                color: view === tab.id ? 'white' : 'var(--text-secondary)',
                borderRight: tab.id !== 'rejected' ? '1px solid var(--border)' : undefined,
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 min-h-0 flex flex-col">
        {isLoading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-[14px] text-text-secondary">Loading topic data...</div>
          </div>
        )}
        {isEmpty && !isLoading && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <div className="text-[18px] font-semibold text-text-primary">No Topic Discovery Data</div>
            <div className="text-[14px] text-text-secondary">Run Topic Discovery to generate content recommendations.</div>
          </div>
        )}
        {error && !isLoading && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <div className="text-[14px] text-error">{error}</div>
            <button onClick={refetch} className="text-[13px] text-accent hover:underline">Try again</button>
          </div>
        )}
        {!isLoading && !isEmpty && !error && view === 'queue' && (
          <PriorityQueue assignments={filtered} onRowClick={setDrawerAssignment} onApprove={handleApprove} onReject={handleReject} />
        )}
        {!isLoading && !isEmpty && !error && view === 'explorer' && (
          <ClusterExplorer assignments={filtered} clusters={clusters} onRowClick={setDrawerAssignment} onApprove={handleApprove} onReject={handleReject} />
        )}
        {!isLoading && !isEmpty && !error && view === 'rejected' && (
          <div className="flex-1 overflow-auto">
            <div className="px-6 py-4">
              {rejected.length > 0 ? (
                <div className="space-y-3">
                  {rejected.map((item, idx) => (
                    <motion.div
                      key={item.id}
                      className="rounded-md p-4"
                      style={{ border: '1px solid var(--border)' }}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.15, delay: idx * 0.04 }}
                    >
                      <div className="flex items-start gap-3">
                        {/* Timeline dot */}
                        <div className="flex flex-col items-center mt-1 shrink-0">
                          <div className="w-2.5 h-2.5 rounded-full bg-error shrink-0" />
                          {idx < rejected.length - 1 && <div className="w-px flex-1 mt-1" style={{ background: 'var(--border)', minHeight: 20 }} />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-mono text-[12px] text-text-tertiary">{item.id}</span>
                            {item.stage && (
                              <span className={`inline-flex items-center px-1.5 py-px text-[10px] font-semibold uppercase border rounded-full ${
                                item.stage === 'TOFU' ? 'bg-accent-subtle text-accent border-accent/30' :
                                item.stage === 'MOFU' ? 'bg-warning-subtle text-warning border-warning/30' :
                                'bg-success-subtle text-success border-success/30'
                              }`}>{item.stage}</span>
                            )}
                            <span className="text-[11px] text-text-tertiary">{item.cluster}</span>
                          </div>
                          <p className="text-[14px] font-medium text-text-primary">{item.title}</p>
                          <div className="flex items-center gap-2 mt-2 text-[12px] text-text-secondary">
                            <span className="text-error font-medium">Rejected</span>
                            <span className="text-text-tertiary">·</span>
                            <span>{item.date}</span>
                            <span className="text-text-tertiary">·</span>
                            <span>by {item.rejectedBy}</span>
                          </div>
                          <p className="text-[12px] text-text-secondary mt-1 italic">&ldquo;{item.reason}&rdquo;</p>
                        </div>
                        <button
                          onClick={() => handleRestore(item.id)}
                          className="flex items-center gap-1 h-[28px] px-3 rounded text-[12px] font-medium text-text-secondary hover:text-accent hover:bg-accent-subtle border border-border transition-colors duration-150 shrink-0"
                        >
                          <RotateCcw size={11} /> Restore
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-center py-16 text-[14px] text-text-secondary">
                  No rejected items
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Detail Drawer */}
      <DetailDrawer
        assignment={drawerAssignment}
        onClose={() => setDrawerAssignment(null)}
        onApprove={(id) => handleApprove([id])}
        onReject={(id) => handleReject([id])}
      />

      {/* Custom Topic Modal */}
      <CustomTopicModal open={customTopicOpen} onClose={() => setCustomTopicOpen(false)} onAdd={handleAddCustom} nextId={nextId} clusters={clusters} />

      {/* Initiatives Sidebar */}
      <InitiativesSidebar open={initiativesOpen} onClose={() => setInitiativesOpen(false)} onInitiativeComplete={handleInitiativeComplete} />

      {/* Toasts */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[70] flex flex-col gap-2">
        <AnimatePresence>
          {toasts.map(toast => (
            <motion.div
              key={toast.id}
              className="px-4 py-2.5 rounded-md text-[14px] font-medium whitespace-nowrap"
              style={{
                background: toast.type === 'success' ? 'var(--success-subtle)' : 'var(--error-subtle)',
                border: `1px solid ${toast.type === 'success' ? 'rgba(52,178,123,0.3)' : 'rgba(229,72,77,0.3)'}`,
                color: toast.type === 'success' ? 'var(--success)' : 'var(--error)',
              }}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={{ duration: 0.2 }}
            >
              {toast.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
