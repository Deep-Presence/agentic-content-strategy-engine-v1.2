'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import { cn } from '@/lib/utils/cn';

interface ScatterPoint {
  x: number;
  y: number;
  type: 'query' | 'citation' | 'company';
  id: string;
  label: string;
  cluster?: string;
  similarity?: number;
  gapScore?: number;
}

interface UmapScatterProps {
  points: ScatterPoint[];
  colorBy: 'type' | 'cluster' | 'gap_score';
  selectedCluster?: string;
  highlightedIds?: string[];
  onPointClick?: (point: ScatterPoint) => void;
  onPointHover?: (point: ScatterPoint | null) => void;
  onBrushSelect?: (points: ScatterPoint[]) => void;
  width?: number;
  height?: number;
  clusterColors?: Record<string, string>;
  className?: string;
}

const TYPE_COLORS = {
  query: '#6a9bcc',
  citation: '#d97757',
  company: '#788c5d',
} as const;

const TYPE_SHAPES = {
  query: 'circle',
  citation: 'triangle',
  company: 'square',
} as const;

function drawShape(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  shape: string,
  size: number,
  fill: string,
  stroke: string,
  highlighted: boolean,
) {
  ctx.fillStyle = fill;
  ctx.strokeStyle = stroke;
  ctx.lineWidth = highlighted ? 2 : 1;

  if (shape === 'circle') {
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  } else if (shape === 'triangle') {
    ctx.beginPath();
    ctx.moveTo(x, y - size);
    ctx.lineTo(x - size, y + size * 0.7);
    ctx.lineTo(x + size, y + size * 0.7);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  } else {
    ctx.fillRect(x - size * 0.8, y - size * 0.8, size * 1.6, size * 1.6);
    ctx.strokeRect(x - size * 0.8, y - size * 0.8, size * 1.6, size * 1.6);
  }
}

function gapScoreToColor(score: number): string {
  if (score >= 0.7) return '#c44040';
  if (score >= 0.5) return '#e8926d';
  if (score >= 0.3) return '#d97757';
  return '#788c5d';
}

function UmapScatter({
  points,
  colorBy,
  selectedCluster,
  highlightedIds,
  onPointClick,
  onPointHover,
  width = 800,
  height = 500,
  clusterColors = {},
  className,
}: UmapScatterProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; point: ScatterPoint } | null>(null);
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const filteredPoints = selectedCluster
    ? points.filter((p) => p.cluster === selectedCluster)
    : points;

  const xMin = Math.min(...points.map((p) => p.x));
  const xMax = Math.max(...points.map((p) => p.x));
  const yMin = Math.min(...points.map((p) => p.y));
  const yMax = Math.max(...points.map((p) => p.y));
  const padding = 40;

  const toScreenX = useCallback((x: number) => {
    const normalized = (x - xMin) / (xMax - xMin || 1);
    return (padding + normalized * (width - padding * 2)) * transform.scale + transform.x;
  }, [xMin, xMax, width, transform]);

  const toScreenY = useCallback((y: number) => {
    const normalized = 1 - (y - yMin) / (yMax - yMin || 1);
    return (padding + normalized * (height - padding * 2)) * transform.scale + transform.y;
  }, [yMin, yMax, height, transform]);

  const getPointColor = useCallback((point: ScatterPoint): string => {
    if (colorBy === 'type') return TYPE_COLORS[point.type];
    if (colorBy === 'cluster' && point.cluster) return clusterColors[point.cluster] || '#b0aea5';
    if (colorBy === 'gap_score' && point.gapScore != null) return gapScoreToColor(point.gapScore);
    return '#b0aea5';
  }, [colorBy, clusterColors]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);

    const highlightSet = new Set(highlightedIds);

    const nonHighlighted: ScatterPoint[] = [];
    const highlighted: ScatterPoint[] = [];

    filteredPoints.forEach((p) => {
      if (highlightSet.size > 0 && highlightSet.has(p.id)) {
        highlighted.push(p);
      } else {
        nonHighlighted.push(p);
      }
    });

    nonHighlighted.forEach((point) => {
      const sx = toScreenX(point.x);
      const sy = toScreenY(point.y);
      const color = getPointColor(point);
      const alpha = highlightSet.size > 0 ? 0.25 : 0.7;
      const size = 4 * transform.scale;

      ctx.globalAlpha = alpha;
      drawShape(ctx, sx, sy, TYPE_SHAPES[point.type], size, color, color, false);
    });

    highlighted.forEach((point) => {
      const sx = toScreenX(point.x);
      const sy = toScreenY(point.y);
      const color = getPointColor(point);
      const size = 6 * transform.scale;

      ctx.globalAlpha = 1;
      drawShape(ctx, sx, sy, TYPE_SHAPES[point.type], size, color, '#141413', true);
    });

    ctx.globalAlpha = 1;
  }, [filteredPoints, colorBy, highlightedIds, transform, width, height, toScreenX, toScreenY, getPointColor]);

  const findPointAt = useCallback((clientX: number, clientY: number): ScatterPoint | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;
    const threshold = 8;

    for (let i = filteredPoints.length - 1; i >= 0; i--) {
      const p = filteredPoints[i];
      const sx = toScreenX(p.x);
      const sy = toScreenY(p.y);
      const dist = Math.sqrt((mx - sx) ** 2 + (my - sy) ** 2);
      if (dist < threshold) return p;
    }
    return null;
  }, [filteredPoints, toScreenX, toScreenY]);

  function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    if (isDragging) {
      const dx = e.clientX - dragStart.current.x;
      const dy = e.clientY - dragStart.current.y;
      dragStart.current = { x: e.clientX, y: e.clientY };
      setTransform((t) => ({ ...t, x: t.x + dx, y: t.y + dy }));
      return;
    }

    const point = findPointAt(e.clientX, e.clientY);
    if (point) {
      const rect = canvasRef.current!.getBoundingClientRect();
      setTooltip({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        point,
      });
      onPointHover?.(point);
      canvasRef.current!.style.cursor = 'pointer';
    } else {
      setTooltip(null);
      onPointHover?.(null);
      canvasRef.current!.style.cursor = isDragging ? 'grabbing' : 'grab';
    }
  }

  function handleMouseDown(e: React.MouseEvent<HTMLCanvasElement>) {
    setIsDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY };
    canvasRef.current!.style.cursor = 'grabbing';
  }

  function handleMouseUp(e: React.MouseEvent<HTMLCanvasElement>) {
    if (isDragging) {
      setIsDragging(false);
      canvasRef.current!.style.cursor = 'grab';
      return;
    }
    const point = findPointAt(e.clientX, e.clientY);
    if (point) onPointClick?.(point);
  }

  function handleWheel(e: React.WheelEvent<HTMLCanvasElement>) {
    e.preventDefault();
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = Math.max(0.5, Math.min(5, transform.scale * delta));

    setTransform((t) => ({
      scale: newScale,
      x: mx - (mx - t.x) * (newScale / t.scale),
      y: my - (my - t.y) * (newScale / t.scale),
    }));
  }

  function handleReset() {
    setTransform({ x: 0, y: 0, scale: 1 });
  }

  return (
    <div className={cn('relative', className)}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ width, height }}
        className="rounded-md border border-[var(--border-default)] bg-white"
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          setTooltip(null);
          setIsDragging(false);
        }}
        onWheel={handleWheel}
      />
      {tooltip && (
        <div
          className="absolute z-50 pointer-events-none bg-cream-950 text-white px-3 py-2 rounded shadow-lg text-caption font-sans max-w-[260px]"
          style={{
            left: Math.min(tooltip.x + 12, width - 270),
            top: tooltip.y - 10,
          }}
        >
          <div className="font-medium capitalize">{tooltip.point.type}</div>
          <div className="text-cream-300 truncate">{tooltip.point.label}</div>
          {tooltip.point.cluster && (
            <div className="text-cream-400 text-micro">Cluster: {tooltip.point.cluster}</div>
          )}
          {tooltip.point.similarity != null && (
            <div className="text-cream-400 text-micro">Similarity: {tooltip.point.similarity.toFixed(2)}</div>
          )}
          {tooltip.point.gapScore != null && (
            <div className="text-cream-400 text-micro">Gap Score: {tooltip.point.gapScore.toFixed(2)}</div>
          )}
        </div>
      )}
      {transform.scale !== 1 && (
        <button
          onClick={handleReset}
          className="absolute top-2 right-2 px-2 py-1 text-micro font-sans bg-white border border-[var(--border-default)] rounded shadow-sm hover:bg-cream-100 transition-colors"
        >
          Reset Zoom
        </button>
      )}
    </div>
  );
}

export { UmapScatter };
export type { UmapScatterProps, ScatterPoint };
