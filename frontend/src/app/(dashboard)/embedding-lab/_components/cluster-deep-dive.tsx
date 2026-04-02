'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';
import { ChevronDown, ChevronUp, ArrowUpDown } from 'lucide-react';
import { BrandLogo } from './brand-logo';
import { GapBadge, gapClassificationFromScore } from './gap-badge';
import { useThemeColors } from './use-theme-colors';
import type { QueryRow } from './embedding-lab-data';
import { CLUSTERS, CLUSTER_FINGERPRINTS, getQueriesForCluster } from './embedding-lab-data';

type SortField = 'gapScore' | 'companySimilarity' | 'citationSimilarity' | 'text';
type SortDir = 'asc' | 'desc';

// ─── Component ──────────────────────────────────────────────────────────────

export function ClusterDeepDive({ initialClusterId }: { initialClusterId?: string }) {
  const colors = useThemeColors();
  const [selectedClusterId, setSelectedClusterId] = useState(initialClusterId || CLUSTERS[0].id);
  const [sortField, setSortField] = useState<SortField>('gapScore');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [expandedQuery, setExpandedQuery] = useState<string | null>(null);

  const cluster = useMemo(
    () => CLUSTERS.find(c => c.id === selectedClusterId) ?? CLUSTERS[0],
    [selectedClusterId],
  );
  const queries = useMemo(() => getQueriesForCluster(selectedClusterId), [selectedClusterId]);
  const fingerprint = useMemo(
    () => CLUSTER_FINGERPRINTS.find(f => f.clusterId === selectedClusterId),
    [selectedClusterId],
  );

  const sortedQueries = useMemo(() => {
    const sorted = [...queries];
    sorted.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'gapScore': cmp = a.gapScore - b.gapScore; break;
        case 'companySimilarity': cmp = a.companySimilarity - b.companySimilarity; break;
        case 'citationSimilarity': cmp = a.citationSimilarity - b.citationSimilarity; break;
        case 'text': cmp = a.text.localeCompare(b.text); break;
      }
      return sortDir === 'desc' ? -cmp : cmp;
    });
    return sorted;
  }, [queries, sortField, sortDir]);

  const toggleSort = useCallback((field: SortField) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  }, [sortField]);

  const citationBarData = useMemo(() =>
    [...cluster.brands].sort((a, b) => b.citationCount - a.citationCount),
    [cluster],
  );

  const radarData = useMemo(() => {
    if (!fingerprint) return [];
    const axes = [
      { key: 'faqRate', label: 'FAQ' },
      { key: 'definitionOpening', label: 'Def. Opening' },
      { key: 'keyTakeaways', label: 'Takeaways' },
      { key: 'comparisonTable', label: 'Comp. Table' },
      { key: 'stepByStep', label: 'Step-by-Step' },
      { key: 'researchRefs', label: 'Research' },
    ] as const;
    return axes.map(a => ({
      axis: a.label,
      topCited: Math.round(fingerprint.topCited[a.key] * 100),
      company: Math.round(fingerprint.company[a.key] * 100),
    }));
  }, [fingerprint]);

  const companyRank = useMemo(() => {
    const sorted = [...cluster.brands].sort((a, b) => b.citationCount - a.citationCount);
    return sorted.findIndex(b => b.isCompany) + 1;
  }, [cluster]);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center gap-3">
        <select
          value={selectedClusterId}
          onChange={e => setSelectedClusterId(e.target.value)}
          className="h-[28px] px-2 text-[11px] bg-surface border border-border rounded-md text-text-primary cursor-pointer font-body"
        >
          {CLUSTERS.map(c => (<option key={c.id} value={c.id}>{c.name}</option>))}
        </select>
        <GapBadge classification={cluster.gapClassification} />
        <span className="text-[10px] text-text-tertiary font-mono">{cluster.queryCount} queries</span>
        <span className="text-[10px] text-text-tertiary">
          Rank <span className="font-mono text-text-secondary">{companyRank}</span>/{cluster.brands.length}
        </span>
      </div>

      {/* 2-col: Citation Share + Radar */}
      <div className="grid grid-cols-2 gap-3">
        {/* Citation Share */}
        <div className="bg-surface border border-border rounded-md p-3">
          <h4 className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-3">Citation Share</h4>
          <div className="space-y-1">
            {citationBarData.map(b => {
              const maxCit = citationBarData[0]?.citationCount || 1;
              const pct = (b.citationCount / maxCit) * 100;
              return (
                <div key={b.domain} className="flex items-center gap-2 h-[22px]">
                  <BrandLogo domain={b.domain} size={14} isCompany={b.isCompany} />
                  <span className={`text-[10px] w-[90px] truncate ${b.isCompany ? 'text-accent font-medium' : 'text-text-tertiary'}`}>
                    {b.domain}
                  </span>
                  <div className="flex-1 h-[7px] bg-bg rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-[width] duration-500 ease-out"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: b.isCompany ? colors.accent : colors.borderStrong,
                      }}
                    />
                  </div>
                  <span className="text-[9px] font-mono text-text-tertiary w-5 text-right">{b.citationCount}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Radar */}
        <div className="bg-surface border border-border rounded-md p-3">
          <h4 className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">Structural Fingerprint</h4>
          <div className="flex items-center gap-3 mb-1">
            <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: colors.accent }} /><span className="text-[9px] text-text-tertiary">Top Cited</span></div>
            <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: colors.warning }} /><span className="text-[9px] text-text-tertiary">Company</span></div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData} cx="50%" cy="52%" outerRadius="68%">
              <PolarGrid stroke={colors.border} />
              <PolarAngleAxis dataKey="axis" tick={{ fontSize: 9, fill: colors.textTertiary }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 8, fill: colors.textTertiary }} axisLine={false} />
              <Radar name="Top Cited" dataKey="topCited" stroke={colors.accent} fill={colors.accent} fillOpacity={0.15} strokeWidth={1.5} />
              <Radar name="Company" dataKey="company" stroke={colors.warning} fill={colors.warning} fillOpacity={0.1} strokeWidth={1.5} strokeDasharray="4 3" />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Query Table */}
      <div className="bg-surface border border-border rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <SortHeader label="Query" field="text" current={sortField} dir={sortDir} onSort={toggleSort} className="text-left w-[40%]" />
              <SortHeader label="Gap" field="gapScore" current={sortField} dir={sortDir} onSort={toggleSort} />
              <SortHeader label="Co. Sim" field="companySimilarity" current={sortField} dir={sortDir} onSort={toggleSort} />
              <SortHeader label="Cit. Sim" field="citationSimilarity" current={sortField} dir={sortDir} onSort={toggleSort} />
              <th className="px-2 py-[5px] text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left">Top Domain</th>
            </tr>
          </thead>
          <tbody>
            {sortedQueries.map(q => (
              <QueryRow
                key={q.id}
                query={q}
                expanded={expandedQuery === q.id}
                onToggle={() => setExpandedQuery(expandedQuery === q.id ? null : q.id)}
                colors={colors}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function SortHeader({ label, field, current, dir, onSort, className = '' }: {
  label: string; field: SortField; current: SortField; dir: SortDir;
  onSort: (f: SortField) => void; className?: string;
}) {
  const active = current === field;
  return (
    <th className={`px-2 py-[5px] text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary cursor-pointer hover:text-text-secondary select-none ${className}`} onClick={() => onSort(field)}>
      <div className="inline-flex items-center gap-0.5">
        {label}
        {active ? (dir === 'desc' ? <ChevronDown size={9} /> : <ChevronUp size={9} />) : <ArrowUpDown size={9} className="opacity-20" />}
      </div>
    </th>
  );
}

function QueryRow({ query, expanded, onToggle, colors }: {
  query: QueryRow; expanded: boolean; onToggle: () => void;
  colors: ReturnType<typeof useThemeColors>;
}) {
  const gapColor =
    query.gapScore > 0.12 ? colors.error :
    query.gapScore > 0.05 ? colors.warning :
    query.gapScore > -0.02 ? colors.textTertiary :
    colors.success;

  return (
    <>
      <tr className="border-b border-border-subtle hover:bg-accent-subtle/50 transition-colors duration-100 cursor-pointer" onClick={onToggle}>
        <td className="px-2 py-[5px] text-[11px] text-text-primary max-w-0">
          <div className="flex items-center gap-1">
            {expanded ? <ChevronUp size={10} className="text-text-tertiary shrink-0" /> : <ChevronDown size={10} className="text-text-tertiary shrink-0" />}
            <span className="truncate">{query.text}</span>
          </div>
        </td>
        <td className="px-2 py-[5px] text-[11px] font-mono" style={{ color: gapColor }}>{query.gapScore.toFixed(3)}</td>
        <td className="px-2 py-[5px] text-[11px] font-mono text-text-tertiary">{query.companySimilarity.toFixed(3)}</td>
        <td className="px-2 py-[5px] text-[11px] font-mono text-text-tertiary">{query.citationSimilarity.toFixed(3)}</td>
        <td className="px-2 py-[5px] text-[11px]">
          <div className="flex items-center gap-1.5">
            <BrandLogo domain={query.topDomain} size={13} />
            <span className="text-text-tertiary truncate max-w-[80px] text-[10px]">{query.topDomain}</span>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border-subtle">
          <td colSpan={5} className="px-3 py-2 bg-surface-raised">
            <div className="grid grid-cols-3 gap-3 text-[10px]">
              <div>
                <span className="text-text-tertiary uppercase tracking-[0.06em] text-[9px]">Classification</span>
                <div className="mt-0.5"><GapBadge classification={gapClassificationFromScore(query.gapScore)} /></div>
              </div>
              <div>
                <span className="text-text-tertiary uppercase tracking-[0.06em] text-[9px]">Platforms</span>
                <div className="mt-0.5 flex items-center gap-0.5 flex-wrap">
                  {query.platforms.map(p => (
                    <span key={p} className="inline-flex px-1 py-0.5 bg-bg border border-border rounded text-[8px] text-text-tertiary">{p}</span>
                  ))}
                </div>
              </div>
              <div>
                <span className="text-text-tertiary uppercase tracking-[0.06em] text-[9px]">Company Cited</span>
                <div className={`mt-0.5 font-medium text-[10px] ${query.companyCited ? 'text-success' : 'text-error'}`}>
                  {query.companyCited ? 'Yes' : 'No'}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
