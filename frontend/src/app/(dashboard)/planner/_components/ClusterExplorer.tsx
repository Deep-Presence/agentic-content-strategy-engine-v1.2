'use client';

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, Check, X } from 'lucide-react';
import type { Assignment, Cluster } from './planner-data';
import { getAssignmentsForSubcluster } from './planner-data';

interface ClusterExplorerProps {
  assignments: Assignment[];
  clusters: Cluster[];
  onRowClick: (assignment: Assignment) => void;
  onApprove: (ids: string[]) => void;
  onReject: (ids: string[]) => void;
}

function BrandLogo({ domain, size = 14 }: { domain: string; size?: number }) {
  return (
    <img src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`} alt={domain} width={size} height={size}
      style={{ borderRadius: 3, flexShrink: 0 }}
      onError={(e) => { const t = e.target as HTMLImageElement; if (!t.dataset.fallback) { t.dataset.fallback = '1'; t.src = `https://logo.clearbit.com/${domain}`; } }} />
  );
}

type SortOption = 'score' | 'citations' | 'opportunity';

const sourceStyles: Record<string, string> = {
  gap: 'bg-accent-subtle text-accent border-accent/30',
  strategic: 'bg-[rgba(147,51,234,0.08)] text-[#9333ea] border-[rgba(147,51,234,0.3)]',
  custom: 'bg-[var(--surface)] text-text-secondary border-border',
};
const sourceLabels: Record<string, string> = { gap: 'Gap Analysis', strategic: 'Strategic', custom: 'Custom' };
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

// Grid for cluster explorer table rows
const CE_GRID = '56px 1fr 84px 52px 80px 50px 80px 50px 48px';

export function ClusterExplorer({ assignments, clusters, onRowClick, onApprove, onReject }: ClusterExplorerProps) {
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set(['cl1']));
  const [selectedSubcluster, setSelectedSubcluster] = useState<string | null>('sc1');
  const [sortBy, setSortBy] = useState<SortOption>('score');

  const toggleCluster = (id: string) => {
    setExpandedClusters(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  };

  const subclusterAssignments = useMemo(() => {
    if (!selectedSubcluster) return [];
    const list = getAssignmentsForSubcluster(assignments, selectedSubcluster, clusters);
    return [...list].sort((a, b) => {
      switch (sortBy) {
        case 'score': return b.priorityScore - a.priorityScore;
        case 'citations': return b.estCitations - a.estCitations;
        case 'opportunity': return b.citationOpp - a.citationOpp;
      }
    });
  }, [assignments, selectedSubcluster, sortBy, clusters]);

  const selectedCluster = clusters.find(c => c.subclusters.some(sc => sc.id === selectedSubcluster));
  const selectedSC = selectedCluster?.subclusters.find(sc => sc.id === selectedSubcluster);
  const avgCitOpp = subclusterAssignments.length > 0 ? subclusterAssignments.reduce((s, a) => s + a.citationOpp, 0) / subclusterAssignments.length : 0;
  const totalCitations = subclusterAssignments.reduce((s, a) => s + a.estCitations, 0);

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
            <div className="flex items-start justify-between mb-4">
              <div>
                <span className="text-[12px] font-semibold uppercase tracking-[0.05em] text-text-secondary">{selectedCluster.name}</span>
                <h2 className="text-[18px] font-semibold text-text-primary">{selectedSC.name}</h2>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[12px] text-text-secondary uppercase tracking-[0.05em] font-semibold">Sort:</span>
                <select value={sortBy} onChange={e => setSortBy(e.target.value as SortOption)}
                  className="h-[28px] px-2 text-[13px] rounded border bg-transparent text-text-primary cursor-pointer" style={{ borderColor: 'var(--border)' }}>
                  <option value="score">Highest Score</option>
                  <option value="citations">Most Citations</option>
                  <option value="opportunity">Opportunity</option>
                </select>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3 mb-5">
              <div className="px-3 py-2.5 rounded-md" style={{ border: '1px solid var(--border)' }}>
                <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Citation Opportunity</span>
                <p className="font-mono text-[22px] font-semibold text-text-primary mt-0.5">{Math.round(avgCitOpp * 100)}%</p>
              </div>
              <div className="px-3 py-2.5 rounded-md" style={{ border: '1px solid var(--border)' }}>
                <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Total Est. Citations</span>
                <p className="font-mono text-[22px] font-semibold text-text-primary mt-0.5">~{totalCitations}</p>
              </div>
            </div>

            {/* Table header */}
            {subclusterAssignments.length > 0 ? (
              <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                <div className="grid items-center py-1.5" style={{ gridTemplateColumns: CE_GRID, borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
                  <div className="px-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">ID</div>
                  <div className="px-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Title</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Source</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Stage</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Intent</div>
                  <div className="px-1 text-right text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Cit.</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Competitor</div>
                  <div className="px-1 text-right text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Score</div>
                  <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary"></div>
                </div>

                {subclusterAssignments.map((a, idx) => (
                  <motion.div key={a.id} className="grid items-center cursor-pointer transition-colors duration-150"
                    style={{ gridTemplateColumns: CE_GRID, borderBottom: idx < subclusterAssignments.length - 1 ? '1px solid var(--border)' : undefined, height: 44 }}
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15, delay: idx * 0.04 }}
                    onClick={() => onRowClick(a)}
                    onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface-raised)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                    <div className="px-2"><span className="font-mono text-[11px] text-text-tertiary">{a.id}</span></div>
                    <div className="px-2 min-w-0 overflow-hidden"><span className="text-[13px] font-medium text-text-primary truncate block">{a.title}</span></div>
                    <div className="px-1"><span className={`inline-flex items-center px-1.5 py-px text-[10px] font-semibold uppercase tracking-[0.04em] border rounded-full whitespace-nowrap ${sourceStyles[a.source]}`}>{sourceLabels[a.source]}</span></div>
                    <div className="px-1"><span className={`inline-flex items-center px-1.5 py-px text-[10px] font-semibold uppercase border rounded-full ${stageStyles[a.stage]}`}>{a.stage}</span></div>
                    <div className="px-1"><span className={`inline-flex items-center px-1.5 py-px text-[10px] font-medium border rounded-full whitespace-nowrap ${intentStyles[a.intent]}`}>{a.intent}</span></div>
                    <div className="px-1 text-right"><span className="font-mono text-[13px] text-accent font-semibold">~{a.estCitations}</span></div>
                    <div className="px-1 overflow-hidden">
                      {a.competitors.length > 0 ? (
                        <div className="flex items-center gap-1 min-w-0">
                          <BrandLogo domain={a.competitors[0].domain} size={14} />
                          <span className="text-[11px] text-text-secondary truncate">{a.competitors[0].domain}</span>
                        </div>
                      ) : <span className="text-[11px] text-success font-medium">New</span>}
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
