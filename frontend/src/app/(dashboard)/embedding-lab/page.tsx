'use client';

import { useState, useCallback, useMemo } from 'react';
import type { EmbeddingPoint } from './_components/data';
import { CLUSTER_COLORS } from './_components/data';
import { EmbeddingLabProvider, useEmbeddingLabContext } from './_components/embedding-lab-context';
import { useEmbeddingLabData } from './_hooks/useEmbeddingLabData';
import { useEmbeddingProjection } from './_hooks/useEmbeddingProjection';
import { TerritoryTab } from './_components/territory-tab';
import { ClusterScorecard } from './_components/cluster-scorecard';
import { ClusterDrawer } from './_components/cluster-drawer';
import { KnowledgeGraph } from './_components/knowledge-graph';
import { LayoutGrid, ScatterChart, BarChart3, Share2 } from 'lucide-react';

type Tab = 'territory' | 'analysis' | 'scatter' | 'knowledge';

const TABS: { id: Tab; label: string; icon: typeof LayoutGrid }[] = [
  { id: 'territory', label: 'Territory Map', icon: LayoutGrid },
  { id: 'analysis', label: 'Cluster Analysis', icon: BarChart3 },
  { id: 'scatter', label: 'Scatter Explorer', icon: ScatterChart },
  { id: 'knowledge', label: 'Knowledge Graph', icon: Share2 },
];

// ── Buyer Journey Stage Mapping ────────────────────────────
const JOURNEY_STAGES = [
  {
    stage: 'Awareness',
    description: 'Users discovering the problem space',
    color: '#EC4899',
    clusters: ['problem-awareness', 'definition'],
  },
  {
    stage: 'Consideration',
    description: 'Users evaluating solutions',
    color: '#F59E0B',
    clusters: ['category-comparison', 'best-of-consideration', 'mechanism', 'boundary'],
  },
  {
    stage: 'Decision',
    description: 'Users making final choices',
    color: '#10B981',
    clusters: ['decision-criteria', 'branded-evaluation', 'feature-verification'],
  },
];

export default function EmbeddingLabPage() {
  const data = useEmbeddingLabData();

  if (data.isLoading) {
    return (
      <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 200px)' }}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span className="text-[13px] text-text-secondary">Loading Embedding Lab...</span>
        </div>
      </div>
    );
  }

  if (data.error) {
    return (
      <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 200px)' }}>
        <div className="text-center space-y-2">
          <p className="text-[14px] text-text-secondary">{data.error}</p>
          <button
            onClick={data.refetch}
            className="px-4 h-[30px] text-[12px] font-medium rounded border border-border hover:bg-[var(--accent-subtle)] transition-colors cursor-pointer"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <EmbeddingLabProvider value={data}>
      <EmbeddingLabContent />
    </EmbeddingLabProvider>
  );
}

function EmbeddingLabContent() {
  const {
    totalTerritories,
    dangerZones,
    clustersWithPresence,
    spaResult,
    clusterProfiles,
  } = useEmbeddingLabContext();

  const [activeTab, setActiveTab] = useState<Tab>('territory');
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);

  const handleClusterClick = useCallback((clusterId: string) => {
    setSelectedCluster(clusterId);
  }, []);

  const handleDrawerClose = useCallback(() => {
    setSelectedCluster(null);
  }, []);

  const clusterData = selectedCluster ? clusterProfiles[selectedCluster] || null : null;

  const STATS = useMemo(() => [
    { value: String(totalTerritories), label: 'TERRITORIES', color: 'var(--text-primary)' },
    { value: `${clustersWithPresence} of ${totalTerritories}`, label: 'WITH PRESENCE', color: 'var(--accent)' },
    { value: String(dangerZones), label: 'DANGER ZONES', color: 'var(--error)' },
    { value: `t=${spaResult.tStat.toFixed(2)}`, label: 'SPA', color: 'var(--accent)' },
  ], [totalTerritories, clustersWithPresence, dangerZones, spaResult]);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[22px] font-semibold text-text-primary tracking-[-0.02em] font-display">
            Embedding Lab
          </h1>
          <p className="text-[13px] text-text-secondary mt-0.5">
            Territory intelligence powered by semantic analysis
          </p>
        </div>
        <div className="flex items-center gap-4">
          {STATS.map((stat) => (
            <div key={stat.label} className="text-right">
              <span className="text-[13px] font-mono font-semibold" style={{ color: stat.color }}>
                {stat.value}
              </span>
              <span className="text-[10px] uppercase tracking-[0.06em] text-text-tertiary ml-1">
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-0 border-b border-border">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 h-[36px] text-[13px] font-medium border-b-2 -mb-[1px] transition-colors cursor-pointer ${
                activeTab === tab.id
                  ? 'border-accent text-accent font-semibold'
                  : 'border-transparent text-text-secondary hover:text-text-primary'
              }`}
            >
              <Icon size={14} strokeWidth={1.5} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'territory' && (
        <TerritoryTab onClusterSelect={handleClusterClick} />
      )}

      {activeTab === 'analysis' && (
        <ClusterAnalysisTab onClusterClick={handleClusterClick} />
      )}

      {activeTab === 'scatter' && <ScatterExplorerTab />}

      {activeTab === 'knowledge' && <KnowledgeGraphTab />}

      {/* Cluster Deep Dive Drawer */}
      <ClusterDrawer cluster={clusterData} onClose={handleDrawerClose} />
    </div>
  );
}

// ── Tab 2: Cluster Analysis ──────────────────────────────
function ClusterAnalysisTab({ onClusterClick }: { onClusterClick: (id: string) => void }) {
  const {
    spaResult: SPA_RESULT,
    proximityStats: PROXIMITY_STATS,
    clusters: CLUSTERS,
    gapQueries: GAP_QUERIES,
    perClusterProximity: PER_CLUSTER_PROXIMITY,
    totalTerritories: TOTAL_TERRITORIES,
  } = useEmbeddingLabContext();

  return (
    <div className="space-y-6" style={{ animation: 'fadeIn 150ms ease-out' }}>
      {/* Section 1: SPA Headline + KPI Cards */}
      <div className="border border-border rounded-md p-4 border-l-[3px] border-l-accent">
        <h3 className="text-[13px] font-semibold text-text-primary font-display">
          Semantic Proximity Analysis
        </h3>
        <p className="text-[13px] text-text-secondary mt-1">
          Citation advantage is statistically significant{' '}
          <span className="font-mono font-semibold text-accent">(t={SPA_RESULT.tStat.toFixed(2)}, p&lt;0.001)</span>
        </p>
        <p className="text-[12px] text-text-tertiary mt-1">
          Cited content sits {PROXIMITY_STATS.similarityGap.toFixed(3)} closer to query centroids than company content,
          confirming a measurable embedding gap across all {TOTAL_TERRITORIES} clusters.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="border border-border rounded-md p-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-1">Citation Mean Similarity</div>
          <div className="text-[24px] font-mono font-semibold text-text-primary">{PROXIMITY_STATS.citationMean.toFixed(3)}</div>
          <div className="text-[11px] text-text-tertiary">median {PROXIMITY_STATS.citationMedian.toFixed(3)}</div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-1">Company Mean Similarity</div>
          <div className="text-[24px] font-mono font-semibold text-text-primary">{PROXIMITY_STATS.companyMean.toFixed(3)}</div>
          <div className="text-[11px] text-text-tertiary">median {PROXIMITY_STATS.companyMedian.toFixed(3)}</div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-1">Similarity Gap</div>
          <div className="text-[24px] font-mono font-semibold text-[var(--warning)]">{PROXIMITY_STATS.similarityGap.toFixed(3)}</div>
          <div className="text-[11px] text-text-tertiary">citations closer by this margin</div>
        </div>
      </div>

      {/* Section 2: Buyer Journey Cards */}
      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-3">
          Buyer Journey Coverage
        </h3>
        <div className="grid grid-cols-3 gap-3">
          {JOURNEY_STAGES.map((stage) => {
            const stageClusters = stage.clusters
              .map((cid) => CLUSTERS.find((c) => c.id === cid))
              .filter(Boolean) as typeof CLUSTERS;

            return (
              <div key={stage.stage} className="border border-border rounded-md p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: stage.color }} />
                  <span className="text-[14px] font-semibold text-text-primary font-display">{stage.stage}</span>
                </div>
                <p className="text-[12px] text-text-secondary mb-3">{stage.description}</p>

                <div className="space-y-2">
                  {stageClusters.map((cluster) => {
                    const queriesInCluster = GAP_QUERIES.filter((q) => q.clusterId === cluster.id);
                    const citedCount = queriesInCluster.filter((q) => q.companyCited).length;
                    const totalQueries = queriesInCluster.length;
                    const coveragePct = totalQueries > 0 ? Math.round((citedCount / totalQueries) * 100) : 0;

                    return (
                      <div
                        key={cluster.id}
                        className="flex items-center gap-2 py-1.5 px-2 -mx-2 rounded cursor-pointer hover:bg-[var(--accent-subtle)] transition-colors"
                        onClick={() => onClusterClick(cluster.id)}
                      >
                        <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: cluster.color }} />
                        <span className="text-[12px] text-text-primary flex-1 truncate">{cluster.name}</span>
                        <span className="text-[11px] font-mono text-text-tertiary">{cluster.totalCitations}</span>
                        <span
                          className="text-[11px] font-mono font-semibold w-10 text-right"
                          style={{
                            color: coveragePct >= 50 ? 'var(--success)' : coveragePct >= 25 ? 'var(--warning)' : 'var(--error)',
                          }}
                        >
                          {coveragePct}%
                        </span>
                        <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden flex-shrink-0">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${coveragePct}%`,
                              background: coveragePct >= 50 ? 'var(--success)' : coveragePct >= 25 ? 'var(--warning)' : 'var(--error)',
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 3: Per-Cluster Proximity Cards */}
      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-3">
          Per-Cluster Proximity: Citation vs Company
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {CLUSTERS.map((cluster) => {
            const prox = PER_CLUSTER_PROXIMITY[cluster.id];
            if (!prox) return null;
            const citMean = prox.mean;
            const clusterGaps = GAP_QUERIES.filter((g) => g.clusterId === cluster.id && g.companySimilarity != null);
            const compMean =
              clusterGaps.length > 0
                ? clusterGaps.reduce((s, g) => s + (g.companySimilarity || 0), 0) / clusterGaps.length
                : null;
            const gap = compMean != null ? citMean - compMean : null;
            const gapColor =
              gap != null
                ? gap > 0.08
                  ? 'var(--error)'
                  : gap > 0.05
                    ? 'var(--warning)'
                    : 'var(--success)'
                : 'var(--text-tertiary)';

            return (
              <div
                key={cluster.id}
                className="border border-border rounded-md p-3 cursor-pointer hover:border-[var(--border-strong)] transition-colors"
                onClick={() => onClusterClick(cluster.id)}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: cluster.color }} />
                  <span className="text-[13px] font-medium text-text-primary">{cluster.name}</span>
                  <span className="ml-auto text-[11px] font-mono font-semibold" style={{ color: gapColor }}>
                    {gap != null ? `+${gap.toFixed(3)}` : '---'}
                  </span>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-text-tertiary w-12">Citation</span>
                    <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-emerald-500" style={{ width: `${citMean * 100}%` }} />
                    </div>
                    <span className="text-[11px] font-mono text-text-primary w-10 text-right">{citMean.toFixed(3)}</span>
                  </div>
                  {compMean != null && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-text-tertiary w-12">Company</span>
                      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-accent" style={{ width: `${compMean * 100}%` }} />
                      </div>
                      <span className="text-[11px] font-mono text-text-primary w-10 text-right">{compMean.toFixed(3)}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 4: Cluster Scorecard */}
      <ClusterScorecard onClusterClick={onClusterClick} />
    </div>
  );
}

// ── Tab 3: Scatter Explorer ──────────────────────────────
function ScatterExplorerTab() {
  const { clusters: CLUSTERS } = useEmbeddingLabContext();
  const [projection, setProjection] = useState<'umap' | 'tsne'>('umap');
  const [colorBy, setColorBy] = useState<'cluster' | 'type'>('cluster');
  const { points, isLoading: loading } = useEmbeddingProjection(projection);
  const [selectedPoint, setSelectedPoint] = useState<(typeof points)[0] | null>(null);

  // Refetch when projection changes
  const switchProjection = useCallback((p: 'umap' | 'tsne') => {
    setProjection(p);
    setSelectedPoint(null);
  }, []);

  // Compute point type counts
  const typeCounts = useMemo(() => {
    const counts = { query: 0, citation: 0, company: 0 };
    for (const p of points) {
      if (p.type === 'query') counts.query++;
      else if (p.type === 'citation') counts.citation++;
      else if (p.type === 'company') counts.company++;
    }
    return counts;
  }, [points]);

  return (
    <div className="space-y-3" style={{ animation: 'fadeIn 150ms ease-out' }}>
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 border border-border rounded p-0.5">
            {(['umap', 'tsne'] as const).map((p) => (
              <button
                key={p}
                onClick={() => switchProjection(p)}
                className={`px-2.5 h-[26px] text-[11px] font-medium rounded transition-colors cursor-pointer ${
                  projection === p ? 'bg-accent text-text-on-accent' : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {p === 'umap' ? 'UMAP' : 't-SNE'}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-text-tertiary">Color by:</span>
            <select
              value={colorBy}
              onChange={(e) => setColorBy(e.target.value as 'cluster' | 'type')}
              className="h-[26px] px-2 text-[11px] border border-border rounded bg-surface text-text-primary cursor-pointer"
            >
              <option value="cluster">Cluster</option>
              <option value="type">Point Type</option>
            </select>
          </div>
        </div>
        <span className="text-[11px] font-mono text-text-tertiary">{points.length.toLocaleString()} points</span>
      </div>

      {/* Scatter Plot + Side Panel */}
      {loading ? (
        <div className="border border-border rounded-md flex items-center justify-center" style={{ height: 'calc(100vh - 280px)', minHeight: 400 }}>
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span className="text-[12px] text-text-tertiary">Loading embedding points...</span>
          </div>
        </div>
      ) : (
        <div className="relative" style={{ height: 'calc(100vh - 280px)', minHeight: 400 }}>
          <div
            className="border border-border rounded-md overflow-hidden bg-surface transition-all"
            style={{ height: '100%', marginRight: selectedPoint ? 284 : 0 }}
          >
            <ScatterCanvas points={points} colorBy={colorBy} onSelect={setSelectedPoint} />
          </div>

          {selectedPoint && (
            <div
              className="absolute top-0 right-0 w-[280px] h-full border border-border rounded-md bg-surface overflow-y-auto p-3"
              style={{ animation: 'slideInRight 200ms ease-out' }}
            >
              {/* Point detail header */}
              <div className="flex items-center justify-between mb-2">
                <span
                  className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${
                    selectedPoint.type === 'query'
                      ? 'bg-blue-100 text-blue-700'
                      : selectedPoint.type === 'citation'
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-accent-subtle text-accent'
                  }`}
                >
                  {selectedPoint.type}
                </span>
                <button
                  onClick={() => setSelectedPoint(null)}
                  className="text-text-tertiary hover:text-text-primary cursor-pointer text-[14px]"
                >
                  &times;
                </button>
              </div>
              <p className="text-[12px] text-text-primary break-all mb-2">{selectedPoint.label}</p>
              <span className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded border border-border text-text-secondary mb-3">
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: CLUSTER_COLORS[selectedPoint.clusterId] || '#888' }}
                />
                {selectedPoint.cluster}
              </span>

              {/* Nearest neighbors */}
              <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2 mt-3">
                6 Nearest Points
              </div>
              {computeNearestNeighbors(selectedPoint, points, 6).map((n, i) => (
                <div key={i} className="flex items-center gap-1.5 py-1 text-[11px]">
                  <span className="font-mono text-text-tertiary w-3">{i + 1}</span>
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      n.type === 'query' ? 'bg-blue-500' : n.type === 'citation' ? 'bg-emerald-500' : 'bg-accent'
                    }`}
                  />
                  <span className="text-text-secondary truncate flex-1">{n.label.slice(0, 40)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Bottom Legend Panel */}
      <div className="border border-border rounded-md p-3">
        <div className="flex items-center justify-between">
          {/* Left: Shape legend */}
          <div className="flex items-center gap-4 text-[11px] text-text-secondary">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              Query <span className="font-mono text-text-tertiary">({typeCounts.query.toLocaleString()})</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-emerald-500" />
              Citation <span className="font-mono text-text-tertiary">({typeCounts.citation.toLocaleString()})</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="w-0 h-0"
                style={{
                  borderLeft: '4px solid transparent',
                  borderRight: '4px solid transparent',
                  borderBottom: '6px solid var(--accent)',
                }}
              />
              Company <span className="font-mono text-text-tertiary">({typeCounts.company.toLocaleString()})</span>
            </span>
          </div>

          {/* Right: Cluster colors */}
          <div className="flex items-center gap-2">
            {CLUSTERS.slice(0, 9).map((c) => (
              <span key={c.id} className="flex items-center gap-1 text-[10px] text-text-tertiary">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: c.color }} />
                {c.name.length > 12 ? c.name.slice(0, 10) + '...' : c.name}
              </span>
            ))}
          </div>
        </div>

        {/* How to read */}
        <div className="mt-2 pt-2 border-t border-border text-[11px] text-text-tertiary">
          <span className="font-semibold text-text-secondary">How to read:</span> Points closer together are
          semantically similar. Color groups show topic clusters. Triangles are your company&apos;s content — their
          position relative to citation squares shows how well-aligned your content is with what AI engines cite. Click
          any point for details.
        </div>
      </div>
    </div>
  );
}

// ── Nearest Neighbors Helper ─────────────────────────────
function computeNearestNeighbors(
  target: EmbeddingPoint,
  allPoints: EmbeddingPoint[],
  k: number
) {
  return allPoints
    .filter((p) => p.id !== target.id)
    .map((p) => ({ ...p, dist: Math.sqrt((p.x - target.x) ** 2 + (p.y - target.y) ** 2) }))
    .sort((a, b) => a.dist - b.dist)
    .slice(0, k);
}

// ── Simple SVG Scatter (no D3 dependency) ────────────────
function ScatterCanvas({
  points,
  colorBy,
  onSelect,
}: {
  points: EmbeddingPoint[];
  colorBy: 'cluster' | 'type';
  onSelect: (p: EmbeddingPoint) => void;
}) {
  const allColors: Record<string, string> = { ...CLUSTER_COLORS, company: '#5BA4C4' };
  const typeColors: Record<string, string> = { query: '#3B82F6', citation: '#10B981', company: '#5BA4C4' };

  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-[13px] text-text-tertiary">
        No embedding points available
      </div>
    );
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(...xs),
    xMax = Math.max(...xs);
  const yMin = Math.min(...ys),
    yMax = Math.max(...ys);
  const xPad = (xMax - xMin) * 0.05 || 1;
  const yPad = (yMax - yMin) * 0.05 || 1;

  const W = 1100,
    H = 520;
  const M = { top: 10, right: 10, bottom: 10, left: 10 };
  const w = W - M.left - M.right;
  const h = H - M.top - M.bottom;

  const sx = (x: number) => M.left + ((x - xMin + xPad) / (xMax - xMin + 2 * xPad)) * w;
  const sy = (y: number) => M.top + h - ((y - yMin + yPad) / (yMax - yMin + 2 * yPad)) * h;

  const getColor = (p: (typeof points)[0]) => {
    if (colorBy === 'type') return typeColors[p.type] || '#888';
    return allColors[p.clusterId] || '#888';
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full">
      {points.map((p) => {
        const cx = sx(p.x);
        const cy = sy(p.y);
        const color = getColor(p);
        const isCompany = p.type === 'company';

        if (p.type === 'query') {
          return (
            <circle key={p.id} cx={cx} cy={cy} r={3} fill={color} opacity={0.7} className="cursor-pointer" onClick={() => onSelect(p)}>
              <title>{p.label}</title>
            </circle>
          );
        }
        if (p.type === 'citation') {
          return (
            <rect key={p.id} x={cx - 2} y={cy - 2} width={4} height={4} fill={color} opacity={0.5} className="cursor-pointer" onClick={() => onSelect(p)}>
              <title>{p.label}</title>
            </rect>
          );
        }
        return (
          <g key={p.id} className="cursor-pointer" onClick={() => onSelect(p)}>
            {isCompany && <circle cx={cx} cy={cy} r={6} fill={color} opacity={0.15} />}
            <polygon points={`${cx},${cy - 4} ${cx + 3.5},${cy + 3} ${cx - 3.5},${cy + 3}`} fill={color} opacity={0.85} />
            <title>{p.label}</title>
          </g>
        );
      })}
    </svg>
  );
}

// ── Tab 4: Knowledge Graph ──────────────────────────────
function KnowledgeGraphTab() {
  return <KnowledgeGraph />;
}
