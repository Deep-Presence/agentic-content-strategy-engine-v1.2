'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { EMBEDDING_POINTS, CLUSTERS, CLUSTER_COLORS, ENGINE_META } from './data';
import type { EmbeddingPoint } from './data';
import { BrandLogo } from './brand-logo';

type SubTab = 'scatter' | 'proximity' | 'dna' | 'authority';
type Projection = 'umap' | 'tsne';
type ColorBy = 'cluster' | 'type' | 'gap';

export function EmbeddingSpaceTab() {
  const [subTab, setSubTab] = useState<SubTab>('scatter');

  const subTabs: { id: SubTab; label: string }[] = [
    { id: 'scatter', label: 'Scatter Explorer' },
    { id: 'proximity', label: 'Proximity Analysis' },
    { id: 'dna', label: 'Content DNA' },
    { id: 'authority', label: 'Authority & Similarity' },
  ];

  return (
    <div className="space-y-3" style={{ animation: 'fadeIn 150ms ease-out' }}>
      {/* Sub-tab nav */}
      <div className="flex items-center gap-0 border-b border-border">
        {subTabs.map(t => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id)}
            className={`px-4 h-[32px] text-[12px] font-medium border-b-2 -mb-[1px] transition-colors cursor-pointer ${
              subTab === t.id
                ? 'border-accent text-accent'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {subTab === 'scatter' && <ScatterExplorer />}
      {subTab === 'proximity' && <ProximityAnalysis />}
      {subTab === 'dna' && <ContentDNA />}
      {subTab === 'authority' && <AuthoritySimilarity />}
    </div>
  );
}

// ── Scatter Explorer ──────────────────────────────────────
function ScatterExplorer() {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [projection, setProjection] = useState<Projection>('umap');
  const [colorBy, setColorBy] = useState<ColorBy>('cluster');
  const [selected, setSelected] = useState<EmbeddingPoint | null>(null);
  const [dims, setDims] = useState({ width: 700, height: 500 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setDims({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    if (!svgRef.current || dims.width < 100) return;
    svg.selectAll('*').remove();

    const { width, height } = dims;
    const margin = { top: 20, right: 20, bottom: 30, left: 40 };
    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const getX = (p: EmbeddingPoint) => projection === 'umap' ? p.x : p.tsne_x;
    const getY = (p: EmbeddingPoint) => projection === 'umap' ? p.y : p.tsne_y;

    const xExtent = d3.extent(EMBEDDING_POINTS, getX) as [number, number];
    const yExtent = d3.extent(EMBEDDING_POINTS, getY) as [number, number];

    const xScale = d3.scaleLinear().domain([xExtent[0] - 1, xExtent[1] + 1]).range([0, w]);
    const yScale = d3.scaleLinear().domain([yExtent[0] - 1, yExtent[1] + 1]).range([h, 0]);

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${h})`)
      .call(d3.axisBottom(xScale).ticks(6))
      .selectAll('text')
      .attr('font-size', '10px')
      .attr('fill', 'var(--text-tertiary)')
      .attr('font-family', 'var(--font-display)');

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(6))
      .selectAll('text')
      .attr('font-size', '10px')
      .attr('fill', 'var(--text-tertiary)')
      .attr('font-family', 'var(--font-display)');

    // Style axis lines
    g.selectAll('.domain, .tick line')
      .attr('stroke', 'var(--border)');

    // Zoom
    const zoomG = g.append('g');
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 10])
      .on('zoom', (event) => zoomG.attr('transform', event.transform));
    (svg as d3.Selection<SVGSVGElement, unknown, null, undefined>).call(zoom);

    // Color function
    const getColor = (p: EmbeddingPoint): string => {
      if (colorBy === 'cluster') return CLUSTER_COLORS[p.clusterId] || 'var(--text-tertiary)';
      if (colorBy === 'type') {
        if (p.type === 'query') return '#3B82F6';
        if (p.type === 'citation') return '#10B981';
        return '#EF4444';
      }
      // gap score
      const gap = p.gapScore ?? 0;
      if (gap > 0.15) return '#EF4444';
      if (gap > 0.05) return '#F59E0B';
      return '#10B981';
    };

    // Draw points
    const shapes = zoomG.selectAll('.point')
      .data(EMBEDDING_POINTS)
      .join('g')
      .attr('class', 'point')
      .attr('transform', (d) => `translate(${xScale(getX(d))},${yScale(getY(d))})`)
      .attr('cursor', 'pointer')
      .on('click', (_event, d) => setSelected(d));

    // Query = circle, Citation = rect, Company = triangle
    shapes.each(function(d) {
      const el = d3.select(this);
      const fill = getColor(d);
      const isCompany = d.type === 'company' && d.domain === 'insighthealth.ai';

      if (d.type === 'query') {
        el.append('circle').attr('r', 4).attr('fill', fill).attr('opacity', 0.7);
      } else if (d.type === 'citation') {
        el.append('rect').attr('x', -3.5).attr('y', -3.5).attr('width', 7).attr('height', 7)
          .attr('fill', fill).attr('opacity', 0.7);
      } else {
        el.append('polygon')
          .attr('points', '0,-5 4.3,3.5 -4.3,3.5')
          .attr('fill', fill)
          .attr('opacity', 0.85)
          .attr('stroke', isCompany ? 'var(--accent)' : 'none')
          .attr('stroke-width', isCompany ? 1.5 : 0);
      }

      el.append('title').text(`${d.label}\n${d.type} · ${d.cluster}`);
    });
  }, [projection, colorBy, dims]);

  return (
    <div className="grid gap-0" style={{ gridTemplateColumns: selected ? '1fr 320px' : '1fr' }}>
      <div>
        {/* Controls */}
        <div className="flex items-center gap-3 mb-2">
          <div className="flex items-center gap-1 border border-border rounded p-0.5">
            {(['umap', 'tsne'] as Projection[]).map(p => (
              <button
                key={p}
                onClick={() => setProjection(p)}
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
              onChange={(e) => setColorBy(e.target.value as ColorBy)}
              className="h-[26px] px-2 text-[11px] border border-border rounded bg-surface text-text-primary cursor-pointer"
            >
              <option value="cluster">Cluster</option>
              <option value="type">Type</option>
              <option value="gap">Gap Score</option>
            </select>
          </div>
          {/* Legend */}
          <div className="flex items-center gap-3 ml-auto text-[10px] text-text-secondary">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500" /> Query
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-emerald-500" /> Citation
            </span>
            <span className="flex items-center gap-1">
              <span className="w-0 h-0 border-l-[4px] border-r-[4px] border-b-[7px] border-transparent border-b-red-500" /> Company
            </span>
          </div>
        </div>
        <div ref={containerRef} className="border border-border rounded-md overflow-hidden" style={{ height: 480 }}>
          <svg ref={svgRef} width={dims.width} height={dims.height} className="w-full h-full" />
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="border-l border-border bg-surface p-3 space-y-3 overflow-y-auto" style={{ animation: 'slideInRight 200ms ease-out' }}>
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">
              {selected.type.toUpperCase()}
            </span>
            <button onClick={() => setSelected(null)} className="text-text-tertiary hover:text-text-primary text-[14px] cursor-pointer">×</button>
          </div>
          {selected.domain && (
            <div className="flex items-center gap-2">
              <BrandLogo domain={selected.domain} size={16} />
              <span className="text-[13px] font-semibold text-text-primary">{selected.domain}</span>
            </div>
          )}
          <p className="text-[12px] text-text-secondary break-all">{selected.label}</p>
          <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border border-border text-text-secondary">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: CLUSTER_COLORS[selected.clusterId] }} />
            {selected.cluster}
          </span>

          <div>
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">Source Intelligence</h4>
            <div className="space-y-1 text-[12px]">
              {selected.engine && (
                <div className="flex justify-between">
                  <span className="text-text-secondary">AI Engine</span>
                  <span className="text-text-primary">{ENGINE_META[selected.engine]?.label || selected.engine}</span>
                </div>
              )}
              {selected.authorityType && (
                <div className="flex justify-between">
                  <span className="text-text-secondary">Authority</span>
                  <span className="text-text-primary capitalize">{selected.authorityType.replace(/_/g, ' ')}</span>
                </div>
              )}
              {selected.similarity !== undefined && (
                <div className="flex justify-between">
                  <span className="text-text-secondary">Similarity</span>
                  <span className="font-mono text-text-primary">{selected.similarity.toFixed(3)}</span>
                </div>
              )}
              {selected.gapScore !== undefined && (
                <div className="flex justify-between">
                  <span className="text-text-secondary">Gap score</span>
                  <span className="font-mono text-text-primary">{selected.gapScore.toFixed(3)}</span>
                </div>
              )}
            </div>
          </div>

          {(selected.wordCount || selected.headers !== undefined) && (
            <div>
              <h4 className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">Structural Signals</h4>
              <div className="grid grid-cols-3 gap-2">
                {selected.wordCount && (
                  <div className="border border-border rounded p-1.5 text-center">
                    <div className="text-[13px] font-mono font-semibold text-text-primary">{selected.wordCount}</div>
                    <div className="text-[9px] uppercase text-text-tertiary">Words</div>
                  </div>
                )}
                {selected.headers !== undefined && (
                  <div className="border border-border rounded p-1.5 text-center">
                    <div className="text-[13px] font-mono font-semibold text-text-primary">{selected.headers}</div>
                    <div className="text-[9px] uppercase text-text-tertiary">Headers</div>
                  </div>
                )}
                {selected.hasFaq !== undefined && (
                  <div className="border border-border rounded p-1.5 text-center">
                    <div className="text-[13px] font-mono font-semibold text-text-primary">{selected.hasFaq ? 'Yes' : 'No'}</div>
                    <div className="text-[9px] uppercase text-text-tertiary">FAQ</div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Proximity Analysis ────────────────────────────────────
function ProximityAnalysis() {
  const companyPoints = useMemo(() => EMBEDDING_POINTS.filter(p => p.type === 'company'), []);
  const [selectedPoint, setSelectedPoint] = useState<EmbeddingPoint | null>(companyPoints[0] || null);

  const neighbors = useMemo(() => {
    if (!selectedPoint) return [];
    return EMBEDDING_POINTS
      .filter(p => p.type === 'citation' && p.clusterId === selectedPoint.clusterId)
      .map(p => ({
        point: p,
        dist: Math.sqrt(Math.pow(p.x - selectedPoint.x, 2) + Math.pow(p.y - selectedPoint.y, 2)),
      }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, 8);
  }, [selectedPoint]);

  const companyNeighbors = useMemo(() => {
    if (!selectedPoint) return [];
    return companyPoints
      .filter(p => p.id !== selectedPoint.id)
      .map(p => ({
        point: p,
        dist: Math.sqrt(Math.pow(p.x - selectedPoint.x, 2) + Math.pow(p.y - selectedPoint.y, 2)),
      }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, 3);
  }, [selectedPoint, companyPoints]);

  const gapToCentroid = selectedPoint?.gapScore ?? 0.13;

  return (
    <div className="space-y-4">
      {/* Company content selector */}
      <div className="flex items-center gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">Select your content:</span>
        <select
          value={selectedPoint?.id || ''}
          onChange={(e) => setSelectedPoint(companyPoints.find(p => p.id === e.target.value) || null)}
          className="h-[30px] px-2 text-[12px] border border-border rounded bg-surface text-text-primary max-w-md truncate cursor-pointer"
        >
          {companyPoints.map(p => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
      </div>

      {selectedPoint && (
        <div className="grid grid-cols-2 gap-4">
          {/* Left: Selected content info */}
          <div className="border border-border rounded-md p-4 space-y-3">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-accent mb-1">Your Content</div>
              <div className="text-[13px] font-medium text-text-primary break-all">{selectedPoint.label}</div>
              <div className="flex items-center gap-2 mt-1">
                <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border border-border text-text-secondary">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: CLUSTER_COLORS[selectedPoint.clusterId] }} />
                  {selectedPoint.cluster}
                </span>
                {selectedPoint.similarity && (
                  <span className="text-[11px] text-text-tertiary">
                    Similarity to centroid: <span className="font-mono">{selectedPoint.similarity.toFixed(2)}</span>
                  </span>
                )}
              </div>
            </div>

            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-1">
                Gap to Citation Sweet Spot
              </div>
              <div className="text-[20px] font-mono font-semibold text-[var(--warning)]">{gapToCentroid.toFixed(2)}</div>
              <p className="text-[11px] text-text-secondary mt-1">
                Your content is {gapToCentroid.toFixed(2)} away from the citation centroid.
                To close this gap: add FAQ sections, increase to 2000+ words, add comparison tables.
              </p>
            </div>

            {/* Nearest company content (cannibalization) */}
            {companyNeighbors.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-2">
                  Nearest Company Content (potential cannibalization)
                </div>
                <div className="space-y-2">
                  {companyNeighbors.map((n, i) => {
                    const highOverlap = n.dist < 0.5;
                    return (
                      <div key={n.point.id} className="text-[12px]">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-text-tertiary">{i + 1}.</span>
                          <span className="text-text-primary truncate">{n.point.label}</span>
                          <span className="font-mono text-text-secondary ml-auto">sim: {(1 / (1 + n.dist)).toFixed(2)}</span>
                        </div>
                        {highOverlap && (
                          <p className="text-[11px] text-[var(--warning)] ml-5 mt-0.5">
                            ⚠ High overlap — consider differentiating or merging
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Right: Nearest citations */}
          <div className="border border-border rounded-md p-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-3">
              Nearest Citations (what AI engines cite for similar queries)
            </div>
            <div className="space-y-2">
              {neighbors.map((n, i) => (
                <div key={n.point.id} className="flex items-center gap-2 py-1">
                  <span className="text-[11px] font-mono text-text-tertiary w-4">{i + 1}.</span>
                  {n.point.domain && <BrandLogo domain={n.point.domain} size={14} />}
                  <span className="text-[12px] text-text-primary truncate flex-1">{n.point.domain || n.point.label}</span>
                  <span className="text-[11px] font-mono text-text-secondary">
                    sim: {(1 / (1 + n.dist)).toFixed(2)}
                  </span>
                  {n.point.engine && (
                    <BrandLogo domain={ENGINE_META[n.point.engine].domain} size={12} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Content DNA ───────────────────────────────────────────
function ContentDNA() {
  const companyPoints = useMemo(() => EMBEDDING_POINTS.filter(p => p.type === 'company'), []);
  const citationPoints = useMemo(() => EMBEDDING_POINTS.filter(p => p.type === 'citation'), []);
  const [pointA, setPointA] = useState<EmbeddingPoint | null>(companyPoints[0] || null);
  const [pointB, setPointB] = useState<EmbeddingPoint | null>(citationPoints[0] || null);

  const signals = [
    { label: 'Word count', a: pointA?.wordCount ?? '—', b: pointB?.wordCount ?? '—', max: 5000 },
    { label: 'Headers', a: pointA?.headers ?? '—', b: pointB?.headers ?? '—', max: 25 },
    { label: 'FAQ sections', a: pointA?.hasFaq ? 'Yes' : 'No', b: pointB?.hasFaq ? 'Yes' : 'No', max: 0 },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div>
          <span className="text-[11px] text-text-tertiary mr-1.5">Point A (yours):</span>
          <select
            value={pointA?.id || ''}
            onChange={(e) => setPointA(companyPoints.find(p => p.id === e.target.value) || null)}
            className="h-[30px] px-2 text-[12px] border border-border rounded bg-surface text-text-primary max-w-[280px] truncate cursor-pointer"
          >
            {companyPoints.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </div>
        <div>
          <span className="text-[11px] text-text-tertiary mr-1.5">Point B (cited):</span>
          <select
            value={pointB?.id || ''}
            onChange={(e) => setPointB(citationPoints.find(p => p.id === e.target.value) || null)}
            className="h-[30px] px-2 text-[12px] border border-border rounded bg-surface text-text-primary max-w-[280px] truncate cursor-pointer"
          >
            {citationPoints.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </div>
      </div>

      {pointA && pointB && (
        <div className="border border-border rounded-md p-4">
          <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary mb-3">
            Structural Signal Comparison
          </div>
          <div className="space-y-3">
            {signals.map(s => {
              const aVal = typeof s.a === 'number' ? s.a : 0;
              const bVal = typeof s.b === 'number' ? s.b : 0;
              const maxVal = Math.max(aVal, bVal, 1);
              const showBar = s.max > 0;

              return (
                <div key={s.label}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[12px] text-text-secondary">{s.label}</span>
                    <div className="flex items-center gap-4">
                      <span className="font-mono text-[12px] text-accent font-medium w-16 text-right">{String(s.a)}</span>
                      <span className="font-mono text-[12px] text-text-primary font-medium w-16 text-right">{String(s.b)}</span>
                    </div>
                  </div>
                  {showBar && (
                    <div className="flex gap-1 h-1.5">
                      <div className="flex-1 bg-border rounded-full overflow-hidden">
                        <div className="h-full bg-accent rounded-full" style={{ width: `${(aVal / maxVal) * 100}%` }} />
                      </div>
                      <div className="flex-1 bg-border rounded-full overflow-hidden">
                        <div className="h-full bg-text-secondary rounded-full" style={{ width: `${(bVal / maxVal) * 100}%` }} />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-4 mt-3 text-[10px] text-text-tertiary">
            <span className="flex items-center gap-1"><span className="w-2 h-1 rounded bg-accent" /> Your content</span>
            <span className="flex items-center gap-1"><span className="w-2 h-1 rounded bg-text-secondary" /> Top cited</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Authority & Similarity ────────────────────────────────
function AuthoritySimilarity() {
  const companyPointsByCluster = useMemo(() => {
    const map: Record<string, EmbeddingPoint[]> = {};
    for (const p of EMBEDDING_POINTS) {
      if (p.type === 'company') {
        if (!map[p.clusterId]) map[p.clusterId] = [];
        map[p.clusterId].push(p);
      }
    }
    return map;
  }, []);

  const clusterDistances = useMemo(() => {
    return CLUSTERS.map(c => {
      const points = companyPointsByCluster[c.id] || [];
      if (points.length === 0) return { cluster: c, distance: null, status: 'no_content' as const };

      // Average distance from center
      const citPoints = EMBEDDING_POINTS.filter(p => p.type === 'citation' && p.clusterId === c.id);
      if (citPoints.length === 0) return { cluster: c, distance: null, status: 'no_citations' as const };

      const centroidX = citPoints.reduce((s, p) => s + p.x, 0) / citPoints.length;
      const centroidY = citPoints.reduce((s, p) => s + p.y, 0) / citPoints.length;

      const avgDist = points.reduce((s, p) =>
        s + Math.sqrt(Math.pow(p.x - centroidX, 2) + Math.pow(p.y - centroidY, 2)), 0) / points.length;

      const normalized = Math.min(avgDist / 3, 1);
      const status = normalized < 0.1 ? 'excellent' as const
        : normalized < 0.2 ? 'good' as const
        : normalized < 0.35 ? 'needs_work' as const
        : 'far' as const;

      return { cluster: c, distance: normalized, status };
    });
  }, [companyPointsByCluster]);

  const statusConfig = {
    excellent: { icon: '✓', label: 'Excellent', color: 'var(--success)' },
    good: { icon: '✓', label: 'Well positioned', color: 'var(--success)' },
    needs_work: { icon: '⚠', label: 'Room to improve', color: 'var(--warning)' },
    far: { icon: '✗', label: 'Far from sweet spot', color: 'var(--error)' },
    no_content: { icon: '—', label: 'No content', color: 'var(--text-tertiary)' },
    no_citations: { icon: '—', label: 'No citations', color: 'var(--text-tertiary)' },
  };

  return (
    <div className="space-y-4">
      <p className="text-[13px] text-text-secondary">
        Distance from the citation centroid for each cluster. Closer = more likely to be cited by AI engines.
      </p>

      <div className="border border-border rounded-md overflow-hidden">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border bg-surface">
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">Cluster</th>
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">Distance</th>
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">Visual</th>
              <th className="text-left px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-tertiary">Status</th>
            </tr>
          </thead>
          <tbody>
            {clusterDistances.map(({ cluster, distance, status }) => {
              const cfg = statusConfig[status];
              return (
                <tr key={cluster.id} className="border-b border-border-subtle">
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-2 text-[13px] text-text-primary font-medium">
                      <span className="w-2 h-2 rounded-full" style={{ background: cluster.color }} />
                      {cluster.name}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-[12px] text-text-primary">
                      {distance !== null ? distance.toFixed(2) : '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2 w-[200px]">
                    {distance !== null && (
                      <div className="relative h-2 bg-border rounded-full overflow-hidden">
                        <div
                          className="absolute top-0 left-0 h-full rounded-full"
                          style={{
                            width: `${(1 - distance) * 100}%`,
                            background: cfg.color,
                          }}
                        />
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-[12px] font-medium" style={{ color: cfg.color }}>
                      {cfg.icon} {cfg.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
