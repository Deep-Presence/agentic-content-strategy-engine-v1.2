'use client';

import { useState, useMemo } from 'react';
import { ChevronRight, ArrowUpDown } from 'lucide-react';
import { CLUSTERS, CLUSTER_COLORS, GAP_QUERIES, PER_CLUSTER_PROXIMITY } from './data';
import type { ClusterProfile } from './data';

interface ClusterScorecardProps {
  onClusterClick: (clusterId: string) => void;
}

type SortKey = 'name' | 'totalCitations' | 'companyShare' | 'uniqueDomains' | 'similarity' | 'coverage' | 'companyRank';
type SortDir = 'asc' | 'desc';

const PRESENCE_BADGE: Record<string, { label: string; className: string }> = {
  strong:   { label: 'STRONG',   className: 'text-[var(--success)] bg-[var(--success-subtle)]' },
  moderate: { label: 'MODERATE', className: 'text-[var(--accent)] bg-[var(--accent-subtle)]' },
  low:      { label: 'LOW',      className: 'text-[var(--warning)] bg-[var(--warning-subtle)]' },
  minimal:  { label: 'MINIMAL',  className: 'text-[var(--warning)] bg-[var(--warning-subtle)]' },
  none:     { label: 'NONE',     className: 'text-[var(--error)] bg-[var(--error-subtle)]' },
};

function getCoverage(clusterId: string): { cited: number; total: number } {
  const queriesInCluster = GAP_QUERIES.filter(q => q.clusterId === clusterId);
  const cited = queriesInCluster.filter(q => q.companyCited === true).length;
  return { cited, total: queriesInCluster.length };
}

export function ClusterScorecard({ onClusterClick }: ClusterScorecardProps) {
  const [sortKey, setSortKey] = useState<SortKey>('totalCitations');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortedClusters = useMemo(() => {
    const arr = [...CLUSTERS];
    const dir = sortDir === 'asc' ? 1 : -1;

    arr.sort((a, b) => {
      switch (sortKey) {
        case 'name':
          return dir * a.name.localeCompare(b.name);
        case 'totalCitations':
          return dir * (a.totalCitations - b.totalCitations);
        case 'companyShare':
          return dir * (a.companyShare - b.companyShare);
        case 'uniqueDomains':
          return dir * (a.uniqueDomains - b.uniqueDomains);
        case 'similarity': {
          const aMean = PER_CLUSTER_PROXIMITY[a.id]?.mean ?? 0;
          const bMean = PER_CLUSTER_PROXIMITY[b.id]?.mean ?? 0;
          return dir * (aMean - bMean);
        }
        case 'coverage': {
          const aCov = getCoverage(a.id);
          const bCov = getCoverage(b.id);
          const aRatio = aCov.total > 0 ? aCov.cited / aCov.total : 0;
          const bRatio = bCov.total > 0 ? bCov.cited / bCov.total : 0;
          return dir * (aRatio - bRatio);
        }
        case 'companyRank': {
          const aRank = a.companyRank ?? 999;
          const bRank = b.companyRank ?? 999;
          return dir * (aRank - bRank);
        }
        default:
          return 0;
      }
    });

    return arr;
  }, [sortKey, sortDir]);

  return (
    <div>
      {/* Section header */}
      <div className="mb-3">
        <span className="text-[10px] uppercase tracking-[0.06em] text-text-tertiary font-semibold">
          CLUSTER SCORECARD
        </span>
        <span className="text-[13px] text-text-secondary ml-3">
          {CLUSTERS.length} semantic territories analyzed
        </span>
      </div>

      {/* Table container */}
      <div className="border border-border rounded-md overflow-hidden">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border bg-surface">
              <SortableHeader
                label="Cluster"
                sortKey="name"
                currentSortKey={sortKey}
                sortDir={sortDir}
                onClick={handleSort}
                width="22%"
              />
              <SortableHeader
                label="Citations"
                sortKey="totalCitations"
                currentSortKey={sortKey}
                sortDir={sortDir}
                onClick={handleSort}
                width="10%"
              />
              <SortableHeader
                label="Your Share"
                sortKey="companyShare"
                currentSortKey={sortKey}
                sortDir={sortDir}
                onClick={handleSort}
                width="10%"
              />
              <SortableHeader
                label="Domains"
                sortKey="uniqueDomains"
                currentSortKey={sortKey}
                sortDir={sortDir}
                onClick={handleSort}
                width="10%"
              />
              <SortableHeader
                label="Similarity"
                sortKey="similarity"
                currentSortKey={sortKey}
                sortDir={sortDir}
                onClick={handleSort}
                width="12%"
              />
              <SortableHeader
                label="Coverage"
                sortKey="coverage"
                currentSortKey={sortKey}
                sortDir={sortDir}
                onClick={handleSort}
                width="18%"
              />
              <SortableHeader
                label="Rank"
                sortKey="companyRank"
                currentSortKey={sortKey}
                sortDir={sortDir}
                onClick={handleSort}
                width="8%"
              />
              <th style={{ width: '5%' }} className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {sortedClusters.map((cluster) => (
              <ClusterRow
                key={cluster.id}
                cluster={cluster}
                onClick={() => onClusterClick(cluster.id)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SortableHeader({
  label,
  sortKey,
  currentSortKey,
  sortDir,
  onClick,
  width,
}: {
  label: string;
  sortKey: SortKey;
  currentSortKey: SortKey;
  sortDir: SortDir;
  onClick: (key: SortKey) => void;
  width: string;
}) {
  const isActive = currentSortKey === sortKey;
  return (
    <th
      style={{ width }}
      className="px-3 py-2 text-left cursor-pointer select-none group"
      onClick={() => onClick(sortKey)}
    >
      <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.06em] text-text-tertiary font-semibold">
        {label}
        <ArrowUpDown
          size={10}
          className={`transition-colors ${
            isActive ? 'text-text-primary' : 'text-text-tertiary opacity-0 group-hover:opacity-100'
          }`}
          style={isActive ? { transform: sortDir === 'asc' ? 'scaleY(-1)' : undefined } : undefined}
        />
      </span>
    </th>
  );
}

function ClusterRow({ cluster, onClick }: { cluster: ClusterProfile; onClick: () => void }) {
  const badge = PRESENCE_BADGE[cluster.presence] || PRESENCE_BADGE.none;
  const proximity = PER_CLUSTER_PROXIMITY[cluster.id];
  const similarityMean = proximity?.mean ?? 0;
  const coverage = getCoverage(cluster.id);
  const coverageRatio = coverage.total > 0 ? coverage.cited / coverage.total : 0;
  const isNone = cluster.presence === 'none';

  const shareColor =
    cluster.companyShare > 5
      ? 'text-[var(--success)]'
      : cluster.companyShare > 0
      ? 'text-[var(--warning)]'
      : 'text-[var(--error)]';

  return (
    <tr
      onClick={onClick}
      className={`h-[44px] border-b border-border cursor-pointer transition-colors hover:bg-surface ${
        isNone ? 'bg-[var(--error-subtle)]' : ''
      }`}
    >
      {/* Cluster name + presence badge */}
      <td className="px-3 py-1.5" style={{ width: '22%' }}>
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: CLUSTER_COLORS[cluster.id] || '#888' }}
          />
          <span className="text-[13px] font-medium text-text-primary truncate">
            {cluster.name}
          </span>
          <span
            className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold leading-none ${badge.className}`}
          >
            {badge.label}
          </span>
        </div>
      </td>

      {/* Citations */}
      <td className="px-3 py-1.5 font-mono text-[13px] text-text-primary" style={{ width: '10%' }}>
        {cluster.totalCitations}
      </td>

      {/* Your Share */}
      <td className={`px-3 py-1.5 font-mono text-[12px] ${shareColor}`} style={{ width: '10%' }}>
        {cluster.companyShare}%
      </td>

      {/* Domains */}
      <td className="px-3 py-1.5 font-mono text-[12px] text-text-primary" style={{ width: '10%' }}>
        {cluster.uniqueDomains}
      </td>

      {/* Similarity */}
      <td className="px-3 py-1.5" style={{ width: '12%' }}>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[12px] text-text-primary">
            {similarityMean.toFixed(3)}
          </span>
          <div className="w-[40px] h-[6px] rounded-full bg-border overflow-hidden">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.min(similarityMean * 100, 100)}%` }}
            />
          </div>
        </div>
      </td>

      {/* Coverage */}
      <td className="px-3 py-1.5" style={{ width: '18%' }}>
        <div className="flex items-center gap-2">
          <div className="w-[60px] h-[6px] rounded-full bg-border overflow-hidden flex-shrink-0">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${coverageRatio * 100}%` }}
            />
          </div>
          <span className="font-mono text-[11px] text-text-secondary whitespace-nowrap">
            {coverage.cited}/{coverage.total}
          </span>
        </div>
      </td>

      {/* Rank */}
      <td className="px-3 py-1.5 font-mono text-[12px] text-text-primary" style={{ width: '8%' }}>
        {cluster.companyRank != null ? `#${cluster.companyRank}` : '—'}
      </td>

      {/* Chevron */}
      <td className="px-3 py-1.5 text-right" style={{ width: '5%' }}>
        <ChevronRight size={14} className="text-text-tertiary" />
      </td>
    </tr>
  );
}
