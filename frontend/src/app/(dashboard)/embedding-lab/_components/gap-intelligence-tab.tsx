'use client';

import { useState, useMemo } from 'react';
import { GAP_QUERIES, CLUSTERS, ENGINE_KEYS, ENGINE_META } from './data';
import type { GapQuery } from './data';
import { BrandLogo } from './brand-logo';
import { ArrowRight, ChevronRight } from 'lucide-react';

const CLASSIFICATION_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  significant_gap: { label: 'Significant gap', color: 'var(--error)', bg: 'var(--error-subtle)' },
  gap_to_close: { label: 'Gap to close', color: 'var(--warning)', bg: 'var(--warning-subtle)' },
  roughly_equal: { label: 'Roughly equal', color: 'var(--success)', bg: 'var(--success-subtle)' },
  company_wins: { label: 'Company wins', color: 'var(--accent)', bg: 'var(--accent-subtle)' },
};

export function GapIntelligenceTab() {
  const [clusterFilter, setClusterFilter] = useState<string>('all');
  const [classFilter, setClassFilter] = useState<string>('all');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let gaps = [...GAP_QUERIES];
    if (clusterFilter !== 'all') gaps = gaps.filter(g => g.clusterId === clusterFilter);
    if (classFilter !== 'all') gaps = gaps.filter(g => g.classification === classFilter);
    return gaps.sort((a, b) => b.opportunityScore - a.opportunityScore);
  }, [clusterFilter, classFilter]);

  const totalGaps = GAP_QUERIES.length;
  const criticalGaps = GAP_QUERIES.filter(g => g.classification === 'significant_gap').length;
  const avgGap = GAP_QUERIES.reduce((s, g) => s + g.gap, 0) / GAP_QUERIES.length;

  return (
    <div className="space-y-4" style={{ animation: 'fadeIn 150ms ease-out' }}>
      {/* KPI Strip */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'TOTAL GAPS', value: totalGaps.toString(), sub: `across ${CLUSTERS.length} clusters`, color: 'var(--text-primary)' },
          { label: 'CRITICAL GAPS', value: criticalGaps.toString(), sub: 'gap > 0.15', color: 'var(--error)' },
          { label: 'AVG GAP SCORE', value: avgGap.toFixed(2), sub: 'lower = closer to cited content', color: 'var(--text-primary)' },
        ].map((kpi) => (
          <div key={kpi.label} className="border border-border rounded-md p-3">
            <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-1">{kpi.label}</div>
            <div className="text-[24px] font-mono font-semibold" style={{ color: kpi.color }}>{kpi.value}</div>
            <div className="text-[11px] text-text-tertiary">{kpi.sub}</div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <select
          value={clusterFilter}
          onChange={(e) => setClusterFilter(e.target.value)}
          className="h-[30px] px-2 text-[12px] border border-border rounded bg-surface text-text-primary cursor-pointer"
        >
          <option value="all">All Clusters</option>
          {CLUSTERS.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          className="h-[30px] px-2 text-[12px] border border-border rounded bg-surface text-text-primary cursor-pointer"
        >
          <option value="all">All Classifications</option>
          <option value="significant_gap">Significant gap</option>
          <option value="gap_to_close">Gap to close</option>
          <option value="roughly_equal">Roughly equal</option>
          <option value="company_wins">Company wins</option>
        </select>
        <span className="text-[11px] text-text-tertiary">{filtered.length} results</span>
      </div>

      {/* Gap Priority Table */}
      <div className="border border-border rounded-md overflow-hidden">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border bg-surface">
              {['Query', 'Gap', 'Classification', 'Your Content', 'Top Cited', 'Engines', 'Opportunity', 'Action'].map(h => (
                <th key={h} className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((gap, idx) => {
              const cls = CLASSIFICATION_LABELS[gap.classification];
              const cluster = CLUSTERS.find(c => c.id === gap.clusterId);
              const isExpanded = expandedRow === gap.id;
              return (
                <GapRow
                  key={gap.id}
                  gap={gap}
                  cls={cls}
                  cluster={cluster}
                  isExpanded={isExpanded}
                  onToggle={() => setExpandedRow(isExpanded ? null : gap.id)}
                  idx={idx}
                />
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Coverage Radar */}
      <CoverageRadar />

      {/* White Spaces */}
      <WhiteSpaces />
    </div>
  );
}

function GapRow({
  gap, cls, cluster, isExpanded, onToggle, idx,
}: {
  gap: GapQuery;
  cls: { label: string; color: string; bg: string };
  cluster: typeof CLUSTERS[0] | undefined;
  isExpanded: boolean;
  onToggle: () => void;
  idx: number;
}) {
  const gapColor = gap.gap > 0.15 ? 'var(--error)' : gap.gap > 0.05 ? 'var(--warning)' : 'var(--success)';

  return (
    <>
      <tr
        className="border-b border-border-subtle hover:bg-surface cursor-pointer transition-colors"
        onClick={onToggle}
        style={{ animation: `fadeUp 300ms ease-out ${idx * 25}ms both` }}
      >
        {/* Query */}
        <td className="px-3 py-1.5 max-w-[240px]">
          <div className="text-[13px] font-medium text-text-primary leading-tight truncate">{gap.query}</div>
          {cluster && (
            <span className="inline-flex items-center gap-1 mt-0.5 text-[10px] text-text-tertiary">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: cluster.color }} />
              {cluster.name}
            </span>
          )}
        </td>
        {/* Gap */}
        <td className="px-3 py-1.5">
          <span className="font-mono text-[12px] font-semibold" style={{ color: gapColor }}>
            {(gap.gap * 100).toFixed(1)}%
          </span>
        </td>
        {/* Classification */}
        <td className="px-3 py-1.5">
          <span
            className="text-[10px] font-semibold px-2 py-0.5 rounded"
            style={{ color: cls.color, background: cls.bg }}
          >
            {cls.label}
          </span>
        </td>
        {/* Your Content */}
        <td className="px-3 py-1.5 max-w-[140px]">
          {gap.yourContent ? (
            <div className="flex items-center gap-1.5 truncate">
              <BrandLogo domain="insighthealth.ai" size={12} />
              <span className="text-[12px] text-text-secondary truncate">{gap.yourContent.url.replace('insighthealth.ai/', '')}</span>
            </div>
          ) : (
            <span className="text-[12px] text-[var(--error)] font-medium">No content</span>
          )}
        </td>
        {/* Top Cited */}
        <td className="px-3 py-1.5 max-w-[140px]">
          <div className="flex items-center gap-1.5 truncate">
            <BrandLogo domain={gap.topCited.domain} size={12} />
            <span className="text-[12px] text-text-secondary truncate">{gap.topCited.domain}</span>
          </div>
        </td>
        {/* Engines */}
        <td className="px-3 py-1.5">
          <div className="flex items-center gap-1">
            {ENGINE_KEYS.map((key) => (
              <div key={key} style={{ opacity: gap.engines[key] ? 1 : 0.2 }}>
                <BrandLogo domain={ENGINE_META[key].domain} size={12} />
              </div>
            ))}
          </div>
        </td>
        {/* Opportunity */}
        <td className="px-3 py-1.5">
          <span className="font-mono text-[12px] font-semibold text-[var(--success)]">
            {gap.opportunityScore.toFixed(2)}
          </span>
        </td>
        {/* Action */}
        <td className="px-3 py-1.5">
          <a
            href="/planner"
            className="inline-flex items-center h-[26px] px-2.5 text-[11px] font-medium rounded border border-border text-text-primary hover:border-border-strong transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            {gap.yourContent ? <>Improve <ChevronRight size={12} /></> : <>Create <ChevronRight size={12} /></>}
          </a>
        </td>
      </tr>

      {/* Expanded row */}
      {isExpanded && gap.topCitedSignals && (
        <tr>
          <td colSpan={8} className="px-3 py-3 bg-surface border-b border-border">
            <StructuralComparison gap={gap} />
          </td>
        </tr>
      )}
    </>
  );
}

function StructuralComparison({ gap }: { gap: GapQuery }) {
  const yours = gap.yourSignals;
  const cited = gap.topCitedSignals;
  if (!cited) return null;

  const signals = [
    { label: 'Word count', yours: yours?.wordCount ?? '—', cited: cited.wordCount },
    { label: 'Headers', yours: yours?.headers ?? '—', cited: cited.headers },
    { label: 'FAQ sections', yours: yours?.hasFaq ? 'Yes' : 'No', cited: cited.hasFaq ? 'Yes' : 'No' },
    { label: 'Tables', yours: yours?.hasTables ? 'Yes' : 'No', cited: cited.hasTables ? 'Yes' : 'No' },
    { label: 'Lists', yours: yours?.lists ?? '—', cited: cited.lists },
    { label: 'External citations', yours: yours?.externalCitations ?? '—', cited: cited.externalCitations },
    { label: 'Reading level', yours: yours?.readingLevel?.toFixed(1) ?? '—', cited: cited.readingLevel.toFixed(1) },
    { label: 'Schema markup', yours: yours?.hasSchema ? 'Yes' : 'No', cited: cited.hasSchema ? 'Yes' : 'No' },
  ];

  return (
    <div className="max-w-lg">
      <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
        Structural Signals Comparison
      </div>
      <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-[12px]">
        <div className="text-text-tertiary font-medium">Signal</div>
        <div className="text-text-tertiary font-medium">{yours ? 'Your content' : '—'}</div>
        <div className="text-text-tertiary font-medium">Top cited ({gap.topCited.domain})</div>
        {signals.map(s => (
          <div key={s.label} className="contents">
            <div className="text-text-secondary">{s.label}</div>
            <div className="font-mono text-text-primary">{String(s.yours)}</div>
            <div className="font-mono text-text-primary">{String(s.cited)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CoverageRadar() {
  return (
    <div className="border border-border rounded-md p-4">
      <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-3">
        Cluster Coverage — How many queries you cover vs total
      </h3>
      <div className="space-y-2">
        {CLUSTERS.map(c => {
          const pct = c.queriesTotal > 0 ? (c.queriesCovered / c.queriesTotal) * 100 : 0;
          const isZero = pct === 0;
          return (
            <div key={c.id} className="flex items-center gap-3">
              <span className="text-[12px] text-text-primary w-[160px] truncate font-medium">{c.name}</span>
              <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, background: isZero ? 'var(--error)' : 'var(--accent)' }}
                />
              </div>
              <span className={`text-[12px] font-mono w-[100px] text-right ${isZero ? 'text-[var(--error)] font-semibold' : 'text-text-secondary'}`}>
                {c.queriesCovered}/{c.queriesTotal} ({pct.toFixed(0)}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WhiteSpaces() {
  const whiteSpaces = CLUSTERS.filter(c => c.presence === 'none');
  if (whiteSpaces.length === 0) return null;

  return (
    <div className="border border-border rounded-md p-4">
      <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-3">
        White Spaces — Territories with zero presence
      </h3>
      <div className="space-y-4">
        {whiteSpaces.map(c => {
          const topGap = GAP_QUERIES
            .filter(g => g.clusterId === c.id)
            .sort((a, b) => b.gap - a.gap)[0];
          const authorityDomains = c.competitors
            .filter(comp => comp.type === 'authority')
            .map(comp => comp.domain)
            .slice(0, 2)
            .join(', ');

          return (
            <div key={c.id} className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[var(--error)]" />
                <span className="text-[14px] font-semibold text-text-primary font-display">{c.name}</span>
              </div>
              <p className="text-[12px] text-text-secondary pl-4">
                {c.citations} citations from {c.domains} competitors
                {authorityDomains && <> · Dominated by {authorityDomains}</>}
              </p>
              {topGap && (
                <p className="text-[12px] text-text-secondary pl-4">
                  Top query: &ldquo;{topGap.query.slice(0, 60)}...&rdquo; —{' '}
                  <span className="font-mono text-[var(--error)]">{(topGap.gap * 100).toFixed(1)}% gap</span>
                </p>
              )}
              <div className="pl-4">
                <a
                  href="/planner"
                  className="inline-flex items-center h-[26px] px-2.5 text-[11px] font-medium rounded bg-accent text-text-on-accent hover:bg-accent-hover transition-colors"
                >
                  Enter this territory <ArrowRight size={12} className="inline" /> Content Planner
                </a>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
