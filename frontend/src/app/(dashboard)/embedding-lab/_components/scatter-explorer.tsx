'use client';

import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import * as d3 from 'd3';
import { useThemeColors } from './use-theme-colors';
import type { ScatterPoint, EmbeddingProjectionResponse } from './embedding-lab-data';
import { CLUSTER_COLORS } from './embedding-lab-data';

// ─── Types ──────────────────────────────────────────────────────────────────

interface ScatterExplorerProps {
  umapData: EmbeddingProjectionResponse;
  tsneData: EmbeddingProjectionResponse;
}

type PointTypeFilter = 'query' | 'citation' | 'company';

interface HoveredPoint {
  point: ScatterPoint;
  screenX: number;
  screenY: number;
  nearestCitations: ScatterPoint[];
}

// ─── Point shapes ───────────────────────────────────────────────────────────

const SHAPES = {
  query: (ctx: CanvasRenderingContext2D, x: number, y: number, r: number) => {
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
  },
  citation: (ctx: CanvasRenderingContext2D, x: number, y: number, r: number) => {
    ctx.fillRect(x - r, y - r, r * 2, r * 2); ctx.strokeRect(x - r, y - r, r * 2, r * 2);
  },
  company: (ctx: CanvasRenderingContext2D, x: number, y: number, r: number) => {
    ctx.beginPath();
    ctx.moveTo(x, y - r * 1.2); ctx.lineTo(x + r, y + r * 0.7); ctx.lineTo(x - r, y + r * 0.7);
    ctx.closePath(); ctx.fill(); ctx.stroke();
  },
};

// ─── Component ──────────────────────────────────────────────────────────────

export function ScatterExplorer({ umapData, tsneData }: ScatterExplorerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const transformRef = useRef(d3.zoomIdentity);
  const colors = useThemeColors();
  const [dimensions, setDimensions] = useState({ width: 900, height: 560 });
  const [method, setMethod] = useState<'umap' | 'tsne'>('umap');
  const [filters, setFilters] = useState<Set<PointTypeFilter>>(() => new Set<PointTypeFilter>(['query', 'citation', 'company']));
  const [hovered, setHovered] = useState<HoveredPoint | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<ScatterPoint | null>(null);

  const data = method === 'umap' ? umapData : tsneData;
  const filteredPoints = useMemo(
    () => data.points.filter(p => filters.has(p.type as PointTypeFilter)),
    [data.points, filters],
  );

  const xScale = useMemo(() => {
    const ext = d3.extent(data.points, d => d.x) as [number, number];
    const pad = (ext[1] - ext[0]) * 0.1;
    return d3.scaleLinear().domain([ext[0] - pad, ext[1] + pad]).range([40, dimensions.width - 40]);
  }, [data.points, dimensions.width]);

  const yScale = useMemo(() => {
    const ext = d3.extent(data.points, d => d.y) as [number, number];
    const pad = (ext[1] - ext[0]) * 0.1;
    return d3.scaleLinear().domain([ext[0] - pad, ext[1] + pad]).range([dimensions.height - 40, 40]);
  }, [data.points, dimensions.height]);

  const clusterList = useMemo(() => {
    const seen = new Map<string, string>();
    data.points.forEach(p => { if (!seen.has(p.clusterId)) seen.set(p.clusterId, p.cluster); });
    return Array.from(seen.entries());
  }, [data.points]);

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      setDimensions({ width, height: Math.max(480, width * 0.55) });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Draw
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = dimensions.width * dpr;
    canvas.height = dimensions.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const transform = transformRef.current;

    // Dark background
    ctx.fillStyle = colors.bg;
    ctx.fillRect(0, 0, dimensions.width, dimensions.height);

    // Subtle grid lines
    ctx.strokeStyle = colors.border;
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.3;
    const gridStep = 60;
    for (let x = gridStep; x < dimensions.width; x += gridStep) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, dimensions.height); ctx.stroke();
    }
    for (let y = gridStep; y < dimensions.height; y += gridStep) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(dimensions.width, y); ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Proximity lines
    if (hovered) {
      ctx.save();
      ctx.strokeStyle = colors.accent;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.35;
      ctx.setLineDash([4, 4]);
      const hx = transform.applyX(xScale(hovered.point.x));
      const hy = transform.applyY(yScale(hovered.point.y));
      hovered.nearestCitations.forEach(c => {
        ctx.beginPath();
        ctx.moveTo(hx, hy);
        ctx.lineTo(transform.applyX(xScale(c.x)), transform.applyY(yScale(c.y)));
        ctx.stroke();
      });
      ctx.restore();
    }

    // Points — batch by type
    const types: PointTypeFilter[] = ['citation', 'query', 'company'];
    for (const type of types) {
      const pts = filteredPoints.filter(p => p.type === type);
      const baseR = type === 'company' ? 5 : type === 'query' ? 4 : 2.5;
      const shape = SHAPES[type];

      pts.forEach(p => {
        const sx = transform.applyX(xScale(p.x));
        const sy = transform.applyY(yScale(p.y));
        if (sx < -10 || sx > dimensions.width + 10 || sy < -10 || sy > dimensions.height + 10) return;

        const isComp = p.type === 'company';
        const clusterColor = CLUSTER_COLORS[p.clusterId] || colors.textTertiary;

        ctx.fillStyle = isComp ? colors.accent : clusterColor;
        ctx.strokeStyle = isComp ? colors.accent : `${clusterColor}40`;
        ctx.lineWidth = isComp ? 1.5 : 0.5;
        ctx.globalAlpha = hovered && hovered.point.clusterId !== p.clusterId ? 0.08 : (isComp ? 1 : 0.65);

        shape(ctx, sx, sy, baseR * transform.k);
      });
    }
    ctx.globalAlpha = 1;
  }, [filteredPoints, dimensions, xScale, yScale, hovered, colors]);

  // Zoom + initial draw
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const zoom = d3.zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.5, 8])
      .on('zoom', (event) => { transformRef.current = event.transform; draw(); });
    d3.select(canvas).call(zoom);
    draw();
    return () => { d3.select(canvas).on('.zoom', null); };
  }, [draw]);

  useEffect(() => { draw(); }, [draw]);

  // Hit detection
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const transform = transformRef.current;

    let closest: ScatterPoint | null = null;
    let closestDist = 15;
    filteredPoints.forEach(p => {
      const dist = Math.sqrt((transform.applyX(xScale(p.x)) - mx) ** 2 + (transform.applyY(yScale(p.y)) - my) ** 2);
      if (dist < closestDist) { closestDist = dist; closest = p; }
    });

    if (closest !== null) {
      const point: ScatterPoint = closest;
      const nearestCitations = filteredPoints
        .filter((p): p is ScatterPoint => p.type === 'citation' && p.clusterId === point.clusterId && p.id !== point.id)
        .map(p => ({ ...p, _dist: Math.sqrt((p.x - point.x) ** 2 + (p.y - point.y) ** 2) }))
        .sort((a, b) => a._dist - b._dist)
        .slice(0, 3);
      setHovered({ point, screenX: e.clientX, screenY: e.clientY, nearestCitations });
    } else {
      setHovered(null);
    }
  }, [filteredPoints, xScale, yScale]);

  const toggleFilter = useCallback((type: PointTypeFilter) => {
    setFilters(prev => {
      const next = new Set(prev);
      if (next.has(type)) { if (next.size > 1) next.delete(type); }
      else next.add(type);
      return next;
    });
  }, []);

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-surface border border-border rounded-md overflow-hidden">
            {(['umap', 'tsne'] as const).map(m => (
              <button
                key={m}
                onClick={() => setMethod(m)}
                className={`px-3 h-[28px] text-[10px] font-medium uppercase tracking-[0.06em] transition-colors cursor-pointer ${
                  method === m ? 'bg-accent-subtle text-accent' : 'text-text-tertiary hover:text-text-secondary'
                }`}
              >
                {m === 'tsne' ? 't-SNE' : 'UMAP'}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 ml-2">
            {([
              { type: 'query' as const, label: 'Queries', shape: '●' },
              { type: 'citation' as const, label: 'Citations', shape: '■' },
              { type: 'company' as const, label: 'Company', shape: '▲' },
            ]).map(({ type, label, shape }) => (
              <button
                key={type}
                onClick={() => toggleFilter(type)}
                className={`flex items-center gap-1 px-2 h-[26px] text-[10px] rounded-md border transition-colors cursor-pointer ${
                  filters.has(type) ? 'border-accent bg-accent-subtle text-accent' : 'border-border text-text-tertiary hover:text-text-secondary'
                }`}
              >
                <span className="text-[8px]">{shape}</span>{label}
              </button>
            ))}
          </div>
        </div>
        <span className="text-[10px] font-mono text-text-tertiary">{filteredPoints.length} pts</span>
      </div>

      {/* Canvas */}
      <div ref={containerRef} className="relative bg-bg border border-border rounded-md overflow-hidden">
        <canvas
          ref={canvasRef}
          style={{ width: dimensions.width, height: dimensions.height, cursor: hovered ? 'pointer' : 'grab' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHovered(null)}
          onClick={() => { if (hovered) setSelectedPoint(hovered.point); }}
        />

        {/* Tooltip */}
        {hovered && (
          <div className="fixed z-50 pointer-events-none" style={{ left: hovered.screenX + 12, top: hovered.screenY - 8 }}>
            <div className="bg-surface-raised border border-border rounded-md px-3 py-2 min-w-[180px] shadow-float">
              <div className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-0.5">{hovered.point.type}</div>
              <div className="text-[11px] text-text-primary font-medium mb-1 max-w-[220px] truncate">{hovered.point.label}</div>
              <div className="text-[10px] text-text-secondary">Cluster: {hovered.point.cluster}</div>
              {hovered.point.similarity !== undefined && (
                <div className="text-[10px] text-text-secondary">Sim: <span className="font-mono">{hovered.point.similarity.toFixed(3)}</span></div>
              )}
              <div className="text-[9px] text-text-tertiary font-mono mt-0.5">({hovered.point.x.toFixed(2)}, {hovered.point.y.toFixed(2)})</div>
            </div>
          </div>
        )}

        {/* Detail panel */}
        {selectedPoint && (
          <div className="absolute top-0 right-0 h-full w-[260px] bg-surface border-l border-border p-3 overflow-y-auto shadow-lg">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Detail</span>
              <button onClick={() => setSelectedPoint(null)} className="text-[10px] text-text-tertiary hover:text-text-primary cursor-pointer">Close</button>
            </div>
            <div className="space-y-2">
              {[
                ['Type', <span key="t" className="capitalize">{selectedPoint.type}</span>],
                ['Label', <span key="l" className="break-all">{selectedPoint.label}</span>],
                ['Cluster', selectedPoint.cluster],
                ...(selectedPoint.similarity !== undefined ? [['Similarity', <span key="s" className="font-mono">{selectedPoint.similarity.toFixed(4)}</span>]] : []),
                ['Coords', <span key="c" className="font-mono">({selectedPoint.x.toFixed(3)}, {selectedPoint.y.toFixed(3)})</span>],
              ].map(([label, val], i) => (
                <div key={i}>
                  <div className="text-[9px] text-text-tertiary uppercase tracking-[0.06em]">{label}</div>
                  <div className="text-[11px] text-text-primary mt-0.5">{val}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="absolute bottom-3 left-3 bg-surface border border-border rounded-md p-2 text-[9px] max-h-[180px] overflow-y-auto">
          <div className="text-text-tertiary font-medium uppercase tracking-[0.06em] mb-1">Clusters</div>
          {clusterList.map(([cid, name]) => (
            <div key={cid} className="flex items-center gap-1.5 mb-0.5">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: CLUSTER_COLORS[cid] || '#888' }} />
              <span className="text-text-secondary truncate max-w-[100px]">{name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
