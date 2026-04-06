'use client';

import { ENGINE_KEYS, ENGINE_META } from './data';
import type { ClusterData } from './data';
import { useEmbeddingLabContext } from './embedding-lab-context';
import { BrandLogo } from './brand-logo';
import { ArrowRight } from 'lucide-react';

interface IntelligencePanelProps {
  cluster: ClusterData | null;
}

export function IntelligencePanel({ cluster }: IntelligencePanelProps) {
  if (!cluster) return <DefaultPanel />;
  return <ClusterPanel cluster={cluster} />;
}

function DefaultPanel() {
  const { clusters: CLUSTERS, gapQueries: GAP_QUERIES } = useEmbeddingLabContext();
  const totalCitations = CLUSTERS.reduce((s, c) => s + c.totalCitations, 0);
  const totalDomains = CLUSTERS.reduce((s, c) => s + c.uniqueDomains, 0);
  const coveredClusters = CLUSTERS.filter(c => c.companyCitations > 0).length;
  const dangerZones = CLUSTERS.filter(c => c.presence === 'none');
  const topOpportunities = [...CLUSTERS]
    .filter(c => c.presence === 'none' || c.presence === 'minimal')
    .sort((a, b) => b.totalCitations - a.totalCitations)
    .slice(0, 3);

  return (
    <div className="h-full overflow-y-auto border-l border-border bg-surface p-4 space-y-5">
      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-3">
          Territory Overview
        </h3>
        <div className="space-y-1 text-[13px] text-text-secondary">
          <p><span className="font-mono font-semibold text-text-primary">{CLUSTERS.length}</span> clusters analyzed</p>
          <p><span className="font-mono font-semibold text-text-primary">{totalDomains}</span> unique competitors tracked</p>
          <p><span className="font-mono font-semibold text-text-primary">{totalCitations}</span> total citations mapped</p>
        </div>
      </div>

      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Your Coverage
        </h3>
        <div className="flex items-center gap-2 mb-1">
          <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full"
              style={{ width: `${(coveredClusters / CLUSTERS.length) * 100}%` }}
            />
          </div>
          <span className="text-[12px] font-mono font-semibold text-text-primary">
            {coveredClusters}/{CLUSTERS.length}
          </span>
        </div>
        <p className="text-[12px] text-text-secondary">
          You have presence in {coveredClusters} clusters. {CLUSTERS.length - coveredClusters} clusters have zero coverage.
        </p>
      </div>

      {dangerZones.length > 0 && (
        <div>
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--error)] mb-2">
            Danger Zones (0 citations)
          </h3>
          <div className="space-y-2">
            {dangerZones.map((z) => (
              <div key={z.id} className="text-[12px]">
                <span className="font-medium text-text-primary">{z.name}</span>
                <span className="text-text-tertiary ml-1">— {z.totalCitations} citations, {z.uniqueDomains} domains</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Top Opportunities
        </h3>
        <div className="space-y-2">
          {topOpportunities.map((c, i) => {
            const gaps = GAP_QUERIES.filter(g => g.clusterId === c.id && g.classification === 'significant_gap');
            return (
              <div key={c.id} className="text-[12px]">
                <span className="font-mono text-text-tertiary mr-1">{i + 1}.</span>
                <span className="font-medium text-text-primary">{c.name}</span>
                <span className="text-text-tertiary ml-1">
                  — {c.companyShare === 0 ? '0%' : `${(c.companyShare * 100).toFixed(1)}%`} share, {gaps.length} critical gaps
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ClusterPanel({ cluster }: { cluster: ClusterData }) {
  const { gapQueries: GAP_QUERIES } = useEmbeddingLabContext();
  const clusterGaps = GAP_QUERIES.filter(g => g.clusterId === cluster.id).slice(0, 5);
  const directCount = cluster.competitors.filter(c => c.type === 'direct').length;
  const mindshareCount = cluster.competitors.filter(c => c.type === 'mindshare').length;
  const authorityCount = cluster.competitors.filter(c => c.type === 'authority').length;
  const total = directCount + mindshareCount + authorityCount;

  const maxEngine = Math.max(...ENGINE_KEYS.map(k => cluster.engineBreakdown[k]));

  // Winning content profile
  const winningProfile = {
    avgWords: 1400,
    contentType: 'Blog or article',
    authority: cluster.competitors[0]?.type === 'authority' ? 'Government/edu' : 'Commercial/media',
    queries: cluster.queriesTotal,
    features: ['Headers', 'Lists', 'Statistics', 'FAQ', 'Tables'],
  };

  return (
    <div
      className="h-full overflow-y-auto border-l border-border bg-surface p-4 space-y-4"
      style={{ animation: 'slideInRight 200ms ease-out' }}
    >
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="w-2 h-2 rounded-full" style={{ background: cluster.color }} />
          <h3 className="text-[14px] font-semibold text-text-primary font-display">{cluster.name}</h3>
        </div>
        <p className="text-[12px] text-text-secondary">
          {cluster.citations} citations · {cluster.domains} unique domains · {cluster.presence === 'none' ? 'fragmented' : cluster.presence}
        </p>
        <div className={`text-[12px] font-semibold mt-1 ${cluster.yourCitations === 0 ? 'text-[var(--error)]' : 'text-accent'}`}>
          {cluster.yourCitations === 0
            ? 'No presence'
            : `Your presence: ${cluster.yourShare.toFixed(1)}% share (#${cluster.yourRank})`}
        </div>
      </div>

      {/* Domain Leaderboard */}
      <div>
        <h4 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Domain Leaderboard
        </h4>
        <div className="space-y-0">
          {cluster.competitors.slice(0, 8).map((comp, i) => {
            const isCompany = comp.domain === 'insighthealth.ai';
            return (
              <div
                key={comp.domain}
                className={`flex items-center gap-2 py-1 px-1.5 rounded ${isCompany ? 'bg-accent-subtle' : ''}`}
              >
                <span className="text-[11px] font-mono text-text-tertiary w-4 text-right">{i + 1}</span>
                <BrandLogo domain={comp.domain} size={14} />
                <span className={`text-[12px] flex-1 truncate ${isCompany ? 'text-accent font-medium' : 'text-text-primary'}`}>
                  {comp.domain}
                </span>
                <span className="text-[12px] font-mono font-medium text-text-primary w-6 text-right">
                  {comp.citations}
                </span>
                <span className="text-[11px] font-mono text-text-tertiary w-10 text-right">
                  {comp.share.toFixed(1)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Competitor Types */}
      <div>
        <h4 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Competitor Types
        </h4>
        <div className="space-y-1 text-[12px]">
          <div className="flex justify-between">
            <span className="text-text-secondary">Direct</span>
            <span className="font-mono text-text-primary">{directCount} brands ({total > 0 ? Math.round((directCount / total) * 100) : 0}%)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-secondary">Mind share</span>
            <span className="font-mono text-text-primary">{mindshareCount} brands ({total > 0 ? Math.round((mindshareCount / total) * 100) : 0}%)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-secondary">Authority</span>
            <span className="font-mono text-text-primary">{authorityCount} sources ({total > 0 ? Math.round((authorityCount / total) * 100) : 0}%)</span>
          </div>
        </div>
      </div>

      {/* AI Engine Breakdown */}
      <div>
        <h4 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
          AI Engine Breakdown
        </h4>
        <div className="space-y-1.5">
          {ENGINE_KEYS.map((key) => {
            const count = cluster.engineBreakdown[key];
            const pct = maxEngine > 0 ? (count / maxEngine) * 100 : 0;
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="text-[11px] text-text-secondary w-16 truncate">{ENGINE_META[key].label}</span>
                <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{ width: `${pct}%`, background: ENGINE_META[key].color }}
                  />
                </div>
                <span className="text-[11px] font-mono text-text-primary w-6 text-right">{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Content Gaps */}
      {clusterGaps.length > 0 && (
        <div>
          <h4 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
            Top Content Gaps ({clusterGaps.length} total)
          </h4>
          <div className="space-y-2">
            {clusterGaps.slice(0, 3).map((gap) => (
              <div key={gap.id} className="text-[12px]">
                <p className="text-text-primary leading-tight">{gap.query}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="font-mono text-[var(--error)] font-semibold">{(gap.gap * 100).toFixed(1)}%</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--error-subtle)] text-[var(--error)] font-medium">
                    Not cited
                  </span>
                </div>
              </div>
            ))}
          </div>
          <a
            href="/planner"
            className="inline-flex items-center gap-1 mt-2 text-[12px] font-medium text-accent hover:text-accent-hover transition-colors"
          >
            Create content for this cluster <ArrowRight size={12} />
          </a>
        </div>
      )}

      {/* Winning Content Profile */}
      <div>
        <h4 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
          Winning Content Profile
        </h4>
        <div className="grid grid-cols-2 gap-2 mb-2">
          {[
            { label: 'AVG WORDS', value: winningProfile.avgWords.toLocaleString() },
            { label: 'CONTENT TYPE', value: winningProfile.contentType },
            { label: 'AUTHORITY', value: winningProfile.authority },
            { label: 'QUERIES', value: winningProfile.queries.toString() },
          ].map((m) => (
            <div key={m.label} className="border border-border rounded p-2">
              <div className="text-[14px] font-mono font-semibold text-text-primary">{m.value}</div>
              <div className="text-[9px] uppercase tracking-[0.06em] text-text-tertiary">{m.label}</div>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-1">
          {winningProfile.features.map((f) => (
            <span key={f} className="text-[10px] px-2 py-0.5 rounded-full border border-border text-text-secondary">
              {f}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
