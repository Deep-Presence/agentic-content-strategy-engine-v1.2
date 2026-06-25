'use client';

import { useState, useMemo, type CSSProperties } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowDown, ArrowUp, Check, X } from 'lucide-react';
import type { Assignment } from './planner-data';

interface PriorityQueueProps {
  assignments: Assignment[];
  onRowClick: (assignment: Assignment) => void;
  onApprove: (ids: string[]) => void;
  onReject: (ids: string[]) => void;
}

function UserAvatar({ name, size = 22 }: { name: string; size?: number }) {
  const initials = name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  return (
    <div className="flex items-center justify-center rounded-full text-white font-semibold shrink-0"
      style={{ width: size, height: size, fontSize: size * 0.4, background: 'var(--accent)' }}>
      {initials}
    </div>
  );
}

type SortKey = 'score' | 'opportunity';
type SortDir = 'asc' | 'desc';

// 9 columns: checkbox, rank, title, stage, intent, format, opp%, keyword, score
const GRID_COLS = '32px 28px 1fr 56px 90px 76px 56px 120px 48px';

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
const formatStyles = 'bg-[var(--surface)] text-text-secondary border-border';

function getCannibalizationLevel(
  assignment: Assignment,
): 'none' | 'low' | 'medium' | 'high' | null {
  if (assignment.cannibalizationRiskLevel) return assignment.cannibalizationRiskLevel;
  if (assignment.cannibalizationRisk == null) return null;
  if (assignment.cannibalizationRisk >= 0.90) return 'high';
  if (assignment.cannibalizationRisk >= 0.80) return 'medium';
  if (assignment.cannibalizationRisk > 0) return 'low';
  return 'none';
}

function getCannibalizationBadge(
  assignment: Assignment,
): { label: string; title: string; style: CSSProperties } | null {
  const level = getCannibalizationLevel(assignment);
  const overlap = assignment.cannibalizationRisk != null
    ? `${Math.round(assignment.cannibalizationRisk * 100)}% overlap with existing content`
    : 'Cannibalization signal detected';

  if (level === 'high') {
    return {
      label: 'High Risk',
      title: overlap,
      style: {
        background: 'rgba(229,72,77,0.08)',
        color: '#E5484D',
        border: '1px solid rgba(229,72,77,0.25)',
      },
    };
  }
  if (level === 'medium') {
    return {
      label: 'Overlap',
      title: overlap,
      style: {
        background: 'rgba(245,166,35,0.08)',
        color: '#F5A623',
        border: '1px solid rgba(245,166,35,0.25)',
      },
    };
  }
  return null;
}

export function PriorityQueue({ assignments, onRowClick, onApprove, onReject }: PriorityQueueProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const sorted = useMemo(() => {
    const list = [...assignments];
    list.sort((a, b) => {
      const va = sortKey === 'score' ? a.priorityScore : a.citationOpp;
      const vb = sortKey === 'score' ? b.priorityScore : b.citationOpp;
      return sortDir === 'desc' ? vb - va : va - vb;
    });
    return list;
  }, [assignments, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const allSelected = assignments.length > 0 && selected.size === assignments.length;
  const toggleAll = () => { if (allSelected) setSelected(new Set()); else setSelected(new Set(assignments.map(a => a.id))); };
  const toggleOne = (id: string) => { setSelected(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; }); };

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return null;
    return sortDir === 'desc' ? <ArrowDown size={11} /> : <ArrowUp size={11} />;
  };

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      {/* Bulk Actions */}
      <AnimatePresence>
        {selected.size > 0 && (
          <motion.div className="flex items-center gap-3 px-6 py-2 shrink-0"
            style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-raised)' }}
            initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.15 }}>
            <UserAvatar name="Shank Keshri" size={22} />
            <span className="text-[13px] font-medium text-text-secondary">{selected.size} selected</span>
            <button onClick={() => { onApprove(Array.from(selected)); setSelected(new Set()); }}
              className="flex items-center gap-1 h-[28px] px-3 rounded text-[13px] font-semibold text-white" style={{ background: 'var(--accent)' }}>
              <Check size={13} strokeWidth={2} /> Approve &amp; Send to Studio
            </button>
            <button onClick={() => { onReject(Array.from(selected)); setSelected(new Set()); }}
              className="flex items-center gap-1 h-[28px] px-3 rounded text-[13px] font-semibold"
              style={{ color: 'var(--error)', border: '1px solid var(--error)' }}>
              <X size={13} strokeWidth={2} /> Reject
            </button>
            <button onClick={() => setSelected(new Set())} className="text-[13px] text-text-secondary hover:text-text-primary transition-colors">Cancel</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Table */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden px-6">
        {/* Header */}
        <div className="sticky top-0 z-10 grid items-center py-2"
          style={{ gridTemplateColumns: GRID_COLS, background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
          <div className="px-1"><input type="checkbox" checked={allSelected} onChange={toggleAll} className="w-3.5 h-3.5 rounded accent-accent cursor-pointer" /></div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">#</div>
          <div className="px-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Title</div>
          <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Stage</div>
          <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Intent</div>
          <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Format</div>
          <div className={`px-1 text-right text-[11px] font-semibold uppercase tracking-[0.05em] cursor-pointer select-none transition-colors ${sortKey === 'opportunity' ? 'text-accent' : 'text-text-tertiary'}`}
            onClick={() => toggleSort('opportunity')}>
            <span className="inline-flex items-center gap-0.5">Opp. <SortIcon col="opportunity" /></span>
          </div>
          <div className="px-1 text-[11px] font-semibold uppercase tracking-[0.05em] text-text-tertiary">Keyword</div>
          <div className={`px-1 text-right text-[11px] font-semibold uppercase tracking-[0.05em] cursor-pointer select-none transition-colors ${sortKey === 'score' ? 'text-accent' : 'text-text-tertiary'}`}
            onClick={() => toggleSort('score')}>
            <span className="inline-flex items-center gap-0.5">Score <SortIcon col="score" /></span>
          </div>
        </div>

        {/* Rows */}
        {sorted.map((a, idx) => {
          const cannibalBadge = getCannibalizationBadge(a);
          return (
          <motion.div key={a.id} className="grid items-center cursor-pointer transition-colors duration-150"
            style={{ gridTemplateColumns: GRID_COLS, borderBottom: '1px solid var(--border)', background: selected.has(a.id) ? 'var(--accent-subtle)' : undefined, height: 48 }}
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15, delay: idx * 0.03 }}
            onClick={() => onRowClick(a)}
            onMouseEnter={(e) => { if (!selected.has(a.id)) e.currentTarget.style.background = 'var(--surface-raised)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = selected.has(a.id) ? 'var(--accent-subtle)' : ''; }}>
            <div className="px-1" onClick={e => e.stopPropagation()}>
              <input type="checkbox" checked={selected.has(a.id)} onChange={() => toggleOne(a.id)} className="w-3.5 h-3.5 rounded accent-accent cursor-pointer" />
            </div>
            <div><span className="font-mono text-[11px] text-text-tertiary">{idx + 1}</span></div>
            <div className="px-2 min-w-0 overflow-hidden">
              <div className="flex items-center gap-1.5">
                <span className="text-[13px] font-medium text-text-primary truncate">{a.title}</span>
                {cannibalBadge && (
                  <span className="shrink-0 inline-flex items-center px-1.5 py-px text-[9px] font-semibold uppercase rounded-full"
                    style={cannibalBadge.style}
                    title={cannibalBadge.title}>
                    {cannibalBadge.label}
                  </span>
                )}
              </div>
              <div className="text-[11px] text-text-secondary truncate">
                <span className="font-mono">{a.displayId}</span><span className="text-text-tertiary mx-1">·</span><span>{a.cluster}</span>
              </div>
            </div>
            <div className="px-1">
              <span className={`inline-flex items-center px-1.5 py-px text-[10px] font-semibold uppercase border rounded-full ${stageStyles[a.stage]}`}>{a.stage}</span>
            </div>
            <div className="px-1">
              <span className={`inline-flex items-center px-1.5 py-px text-[10px] font-medium border rounded-full whitespace-nowrap ${intentStyles[a.intent]}`}>{a.intent}</span>
            </div>
            <div className="px-1">
              <span className={`inline-flex items-center px-1.5 py-px text-[10px] font-medium border rounded-full whitespace-nowrap ${formatStyles}`}>{a.format ?? '\u2014'}</span>
            </div>
            <div className="px-1 text-right">
              <span className="font-mono text-[13px] font-semibold text-accent">{Math.round(a.citationOpp * 100)}%</span>
            </div>
            <div className="px-1 overflow-hidden">
              {a.targetKeywords.primary ? (
                <span className="text-[11px] text-text-secondary truncate block">{a.targetKeywords.primary}</span>
              ) : (
                <span className="text-[11px] text-text-tertiary">&mdash;</span>
              )}
            </div>
            <div className="px-1 text-right">
              <span className="font-mono text-[13px] text-text-primary">{(a.priorityScore * 100).toFixed(0)}</span>
            </div>
          </motion.div>
          );
        })}
      </div>

      <div className="px-6 py-2 shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
        <span className="text-[13px] text-text-secondary">{assignments.length} recommendations pending</span>
      </div>
    </div>
  );
}
