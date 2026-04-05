'use client';

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, Check, X, Zap } from 'lucide-react';
import type { Assignment, Cluster } from './planner-data';
import { getAssignmentsForSubcluster } from './planner-data';

interface ClusterExplorerProps {
  assignments: Assignment[];
  clusters: Cluster[];
  onRowClick: (assignment: Assignment) => void;
  onApprove: (ids: string[]) => void;
  onReject: (ids: string[]) => void;
  onExpandSubdomain?: (subdomainId: string) => Promise<{ runId: string }>;
}

type SortOption = 'score' | 'opportunity' | 'effort';

const stageStyles: Record<string, string> = {
  TOFU: 'bg-accent-subtle text-accent border-accent/30',
  MOFU: 'bg-warning-subtle text-warning border-warning/30',
  BOFU: 'bg-success-subtle text-success border-success/30',
};
const intentStyles: Record<string, string> = {
  Informational: 'bg-info-subtle text-info border-info/30',
  Commercial: 'bg-warning-subtle text-warning border-warning/30',
  Navigational: 'bg-[var(--surface)] text-text-secondary border-border',
  Transactional: 'bg-success-subtle text-success border-success/30',
};

const effortOrder: Record<string, number> = { high: 3, medium: 2, low: 1 };

// Grid: ID, Title, Stage, Intent, Opp%, Format, Score, Actions
const CE_GRID = '72px 1fr 52px 80px 50px 76px 50px 48px';

export function ClusterExplorer({ assignments, clusters, onRowClick, onApprove, onReject, onExpandSubdomain }: ClusterExplorerProps) {
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(() => new Set(clusters[0]?.id ? [clusters[0].id] : []));
  const [selectedSubcluster, setSelectedSubcluster] = useState<string | null>(() => clusters[0]?.subclusters[0]?.id ?? null);
  const [sortBy, setSortBy] = useState<SortOption>('score');
  const [isExpanding, setIsExpanding] = useState(false);
  const [expandResult, setExpandResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const toggleCluster = (id: string) => {
    setExpandedClusters(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  };

  const subclusterAssignments = useMemo(() => {
    if (!selectedSubcluster) return [];
    const list = getAssignmentsForSubcluster(assignments, selectedSubcluster, clusters);
    return [...list].sort((a, b) => {
      switch (sortBy) {
        case 'score': return b.priorityScore - a.priorityScore;
        case 'opportunity': return b.citationOpp - a.citationOpp;
        case 'effort': return (effortOrder[b.effort ?? ''] ?? 0) - (effortOrder[a.effort ?? ''] ?? 0);
      }
    });
  }, [assignments, selectedSubcluster, sortBy, clusters]);

  const selectedCluster = clusters.find(c => c.subclusters.some(sc => sc.id === selectedSubcluster));
  const selectedSC = selectedCluster?.subclusters.find(sc => sc.id === selectedSubcluster);
  const avgCitOpp = subclusterAssignments.length > 0 ? subclusterAssignments.reduce((s, a) => s + a.citationOpp, 0) / subclusterAssignments.length : 0;
  const avgScore = subclusterAssignments.length > 0 ? subclusterAssignments.reduce((s, a) => s + a.priorityScore, 0) / subclusterAssignments.length : 0;

  function getSubclusterCount(scId: string): number { return getAssignmentsForSubcluster(assignments, scId, clusters).length; }
  function getClusterCount(cluster: Cluster): number { return cluster.subclusters.reduce((sum, sc) => sum + getSubclusterCount(sc.id), 0); }

  return (
    <div className="flex flex-1 min-h-0">
      {/* Left Panel */}
      <div className="w-[230px] shrink-0 overflow-y-auto" style={{ borderRight: '1px solid var(--border)' }}>
        <div className="py-2">
          {clusters.map(cluster => {
            const isExpanded = expandedClusters.has(cluster.id);
            return (
              <div key={cluster.id}>
                <button className="w-full flex items-center gap-1.5 px-3 py-2 hover:bg-[var(--surface-raised)] transition-colors duration-150"
                  onClick={() => toggleCluster(cluster.id)}>
                  <motion.div animate={{ rotate: isExpanded ? 90 : 0 }} transition={{ duration: 0.2 }}>
                    <ChevronRight size={13} className="text-text-tertiary" />
                  </motion.div>
                  <span className="text-[13px] font-semibold text-text-primary flex-1 text-left">{cluster.name}</span>
                  <span className="font-mono text-[12px] text-text-tertiary">{getClusterCount(cluster)}</span>
                </button>
                <AnimatePresence initial={false}>
                  {isExpanded && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }} style={{ overflow: 'hidden' }}>
                      {cluster.subclusters.map(sc => {
                        const isActive = selectedSubcluster === sc.id;
                        return (
                          <button key={sc.id} className="w-full flex items-center gap-1 py-2 transition-colors duration-150"
                            style={{ paddingLeft: 34, paddingRight: 12, background: isActive ? 'var(--accent-subtle)' : undefined,
                              borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent', color: isActive ? 'var(--accent)' : 'var(--text-secondary)' }}
                            onClick={() => setSelectedSubcluster(sc.id)}
                            onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--surface-raised)'; }}
                            onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = ''; }}>
                            <span className="text-[12px] flex-1 text-left">{sc.name}</span>
                            <span className="font-mono text-[11px]">{getSubclusterCount(sc.id)}</span>
                          </button>
                        );
                      })}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden">
        {selectedSC && selectedCluster ? (
          <motion.div key={selectedSubcluster} className="p-6" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}>
            {/* Header */}
            <div className="flex items-start justify-between mb-2">
              <div className="flex-1 min-w-0">
                <span className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary">{selectedCluster.name}</span>
                <h2 className="text-[18px] font-semibold text-text-primary">{selectedSC.name}</h2>
                {selectedSC.description && (
                  <p className="text-[13px] text-text-secondary mt-1 leading-relaxed">{selectedSC.description}</p>
                )}
              </div>
              <div className="flex items-center gap-3 shrink-0 ml-4">
                {onExpandSubdomain && selectedSubcluster && (
                  <button
                    onClick={async () => {
                      if (!selectedSubcluster) return;
                      setIsExpanding(true);
                      setExpandResult(null);
                      try {
                        const { runId } = await onExpandSubdomain(selectedSubcluster);
                        setExpandResult({
                          type: 'success',
                          message: `Topic expansion started (run: ${runId.slice(0, 8)}...). New recommendations will appear after the pipeline completes.`,
                        });
                      } catch (err) {
                        setExpandResult({
                          type: 'error',
                          message: err instanceof Error ? err.message : 'Failed to start topic expansion.',
                        });
                      } finally {
                        setIsExpanding(false);
                      }
                    }}
                    disabled={isExpanding}
                    className="flex items-center gap-1.5 h-[28px] px-3 text-[12px] font-medium rounded transition-colors duration-150"
                    style={{
                      background: 'var(--accent-subtle)',
                      color: 'var(--accent)',
                      border: '1px solid var(--accent)',
                      opacity: isExpanding ? 0.6 : 1,
                      cursor: isExpanding ? 'wait' : 'pointer',
                    }}
                  >
                    <Zap size={13} strokeWidth={1.5} className={isExpanding ? 'animate-pulse' : ''} />
                    {isExpanding ? 'Expanding...' : 'Expand Topic'}
                  </button>
                )}
                <div className="flex items-center gap-1.5">
                  <span className="text-[12px] text-text-secondary uppercase tracking-[0.05em] font-semibold">Sort:</span>
                  <select value={sortBy} onChange={e => setSortBy(e.target.value as SortOption)}
                    className="h-[28px] px-2 text-[13px] rounded border bg-transparent text-text-primary cursor-pointer" style={{ borderColor: 'var(--border)' }}>
                    <option value="score">Highest Score</option>
                    <option value="opportunity">Citation Opp.</option>
                    <option value="effort">Highest Effort</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Expand result banner */}
            {expandResult && (
              <div className={`mb-4 px-3 py-2 rounded-md text-[13px] ${
                expandResult.type === 'success'
                  ? 'bg-success-subtle text-success border border-success/30'
                  : 'bg-error-subtle text-error border border-error/30'
              }`}>
                {expandResult.message}
              </div>
            )}

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3 mb-5 mt-4">
              <div className="px-3 py-2.5 rounded-md" style={{ border: '1px solid var(--border)' }}>
                <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Topics</span>
                <p className="font-mono text-[22px] font-semibold text-text-primary mt-0.5">{subclusterAssignments.length}</p>
              </div>
              <div className="px-3 py-2.5 rounded-md" style={{ border: '1px solid var(--border)' }}>
                <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Avg Citation Opp.</span>
                <p className="font-mono text-[22px] font-semibold text-text-primary mt-0.5">{Math.round(avgCitOpp * 100)}%</p>
              </div>
              <div className="px-3 py-2.5 rounded-md" style={{ border: '1px solid var(--border)' }}>
                <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Avg Priority Score</span>
                <p className="font-mono text-[22px] font-semibold text-text-primary mt-0.5">{Math.round(avgScore * 100)}</p>
              </div>
            </div>

            {/* Table header */}
            {subclusterAssignments.length > 0 ? (
              <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                <div className="grid items-center py-1.5" style={{ gridTemplateColumns: CE_GRID, borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
                  <div className="px-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">ID</div>
                  <div className="px-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Title</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Stage</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Intent</div>
                  <div className="px-1 text-right text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Opp.</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Format</div>
                  <div className="px-1 text-right text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Score</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary"></div>
                </div>

                {subclusterAssignments.map((a, idx) => (
                  <motion.div key={a.id} className="grid items-center cursor-pointer transition-colors duration-150"
                    style={{ gridTemplateColumns: CE_GRID, borderBottom: idx < subclusterAssignments.length - 1 ? '1px solid var(--border)' : undefined, minHeight: 44 }}
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15, delay: idx * 0.04 }}
                    onClick={() => onRowClick(a)}
                    onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface-raised)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                    <div className="px-2"><span className="font-mono text-[11px] text-text-tertiary">{a.displayId}</span></div>
                    <div className="px-2 min-w-0 overflow-hidden"><span className="text-[13px] font-medium text-text-primary truncate block">{a.title}</span></div>
                    <div className="px-1"><span className={`inline-flex items-center px-1.5 py-px text-[10px] font-semibold uppercase border rounded-full ${stageStyles[a.stage]}`}>{a.stage}</span></div>
                    <div className="px-1"><span className={`inline-flex items-center px-1.5 py-px text-[10px] font-medium border rounded-full whitespace-nowrap ${intentStyles[a.intent]}`}>{a.intent}</span></div>
                    <div className="px-1 text-right"><span className="font-mono text-[13px] text-accent font-semibold">{Math.round(a.citationOpp * 100)}%</span></div>
                    <div className="px-1 overflow-hidden">
                      {a.format ? (
                        <span className="inline-flex items-center px-1.5 py-px text-[10px] font-medium border rounded-full whitespace-nowrap bg-[var(--surface)] text-text-secondary border-border truncate">{a.format}</span>
                      ) : <span className="text-[11px] text-text-tertiary">&mdash;</span>}
                    </div>
                    <div className="px-1 text-right"><span className="font-mono text-[12px] text-text-primary">{(a.priorityScore * 100).toFixed(0)}</span></div>
                    <div className="flex items-center gap-0.5 px-1" onClick={e => e.stopPropagation()}>
                      <button onClick={() => onApprove([a.id])} className="flex items-center justify-center w-[20px] h-[20px] rounded text-success hover:bg-success-subtle transition-colors"><Check size={12} strokeWidth={2} /></button>
                      <button onClick={() => onReject([a.id])} className="flex items-center justify-center w-[20px] h-[20px] rounded text-text-tertiary hover:text-error hover:bg-error-subtle transition-colors"><X size={12} strokeWidth={2} /></button>
                    </div>
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center py-12 text-[13px] text-text-secondary">No recommendations for this subcluster</div>
            )}
          </motion.div>
        ) : (
          <div className="flex items-center justify-center h-full text-[13px] text-text-secondary">Select a subcluster to view assignments</div>
        )}
      </div>
    </div>
  );
}
