'use client';

import { useRef, useEffect, useState, useMemo } from 'react';
import { cn } from '@/lib/utils/cn';

interface HeatmapCell {
  query_id: string;
  query_text: string;
  cluster: string;
  gap_score: number;
  classification: string;
}

interface GapHeatmapProps {
  data: HeatmapCell[];
  clusters: string[];
  onCellClick?: (queryId: string, cluster: string) => void;
  width?: number;
  height?: number;
  className?: string;
}

function GapHeatmap({
  data,
  clusters,
  onCellClick,
  width = 800,
  height = 500,
  className,
}: GapHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    cell: HeatmapCell;
  } | null>(null);

  const queries = useMemo(() => {
    const seen = new Map<string, string>();
    data.forEach((d) => {
      if (!seen.has(d.query_id)) seen.set(d.query_id, d.query_text);
    });
    return Array.from(seen.entries()).map(([id, text]) => ({ id, text }));
  }, [data]);

  const dataMap = useMemo(() => {
    const map = new Map<string, HeatmapCell>();
    data.forEach((d) => map.set(`${d.query_id}:${d.cluster}`, d));
    return map;
  }, [data]);

  const maxGapScore = useMemo(
    () => Math.max(...data.map((d) => d.gap_score), 1),
    [data],
  );

  const labelWidth = 200;
  const headerHeight = 60;
  const cellWidth = Math.max(30, (width - labelWidth) / clusters.length);
  const cellHeight = Math.max(20, (height - headerHeight) / queries.length);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const totalWidth = labelWidth + cellWidth * clusters.length;
    const totalHeight = headerHeight + cellHeight * queries.length;
    canvas.width = totalWidth * dpr;
    canvas.height = totalHeight * dpr;
    canvas.style.width = `${totalWidth}px`;
    canvas.style.height = `${totalHeight}px`;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, totalWidth, totalHeight);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, totalWidth, totalHeight);

    // Column headers
    ctx.font = '10px ui-sans-serif, -apple-system, sans-serif';
    ctx.fillStyle = '#4a4840';
    ctx.textAlign = 'center';
    clusters.forEach((cluster, i) => {
      const x = labelWidth + i * cellWidth + cellWidth / 2;
      ctx.save();
      ctx.translate(x, headerHeight - 8);
      ctx.rotate(-Math.PI / 6);
      ctx.fillText(cluster.length > 12 ? cluster.slice(0, 12) + '...' : cluster, 0, 0);
      ctx.restore();
    });

    // Row labels and cells
    queries.forEach((query, row) => {
      const y = headerHeight + row * cellHeight;

      // Row label
      ctx.fillStyle = '#4a4840';
      ctx.textAlign = 'right';
      ctx.font = '10px ui-sans-serif, -apple-system, sans-serif';
      const truncated = query.text.length > 30 ? query.text.slice(0, 30) + '...' : query.text;
      ctx.fillText(truncated, labelWidth - 8, y + cellHeight / 2 + 3);

      // Cells
      clusters.forEach((cluster, col) => {
        const cell = dataMap.get(`${query.id}:${cluster}`);
        const score = cell?.gap_score ?? 0;
        const intensity = score / maxGapScore;

        const r = Math.round(255 - intensity * (255 - 217));
        const g = Math.round(255 - intensity * (255 - 119));
        const b = Math.round(255 - intensity * (255 - 87));

        const cx = labelWidth + col * cellWidth;
        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
        ctx.fillRect(cx + 1, y + 1, cellWidth - 2, cellHeight - 2);

        // Grid lines
        ctx.strokeStyle = '#f0ede6';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(cx, y, cellWidth, cellHeight);
      });
    });
  }, [data, clusters, queries, dataMap, maxGapScore, cellWidth, cellHeight]);

  function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (mx < labelWidth || my < headerHeight) {
      setTooltip(null);
      return;
    }

    const col = Math.floor((mx - labelWidth) / cellWidth);
    const row = Math.floor((my - headerHeight) / cellHeight);

    if (col < 0 || col >= clusters.length || row < 0 || row >= queries.length) {
      setTooltip(null);
      return;
    }

    const query = queries[row];
    const cluster = clusters[col];
    const cell = dataMap.get(`${query.id}:${cluster}`);

    if (cell) {
      setTooltip({ x: mx, y: my, cell });
    } else {
      setTooltip(null);
    }
  }

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (mx < labelWidth || my < headerHeight) return;

    const col = Math.floor((mx - labelWidth) / cellWidth);
    const row = Math.floor((my - headerHeight) / cellHeight);

    if (col >= 0 && col < clusters.length && row >= 0 && row < queries.length) {
      onCellClick?.(queries[row].id, clusters[col]);
    }
  }

  const classificationLabel: Record<string, string> = {
    significant_gap: 'Significant Gap',
    gap_to_close: 'Gap to Close',
    roughly_equal: 'Roughly Equal',
    company_wins: 'Company Wins',
  };

  return (
    <div className={cn('relative overflow-auto', className)}>
      <canvas
        ref={canvasRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
        onClick={handleClick}
        className="cursor-crosshair"
      />
      {tooltip && (
        <div
          className="absolute z-50 pointer-events-none bg-cream-950 text-white px-3 py-2 rounded shadow-lg text-caption font-sans max-w-[280px]"
          style={{
            left: Math.min(tooltip.x + 12, (canvasRef.current?.clientWidth ?? 600) - 290),
            top: tooltip.y - 10,
          }}
        >
          <div className="font-medium truncate">{tooltip.cell.query_text}</div>
          <div className="text-cream-400 text-micro mt-1">Cluster: {tooltip.cell.cluster}</div>
          <div className="text-cream-400 text-micro">Gap Score: {tooltip.cell.gap_score.toFixed(2)}</div>
          <div className="text-cream-400 text-micro">
            {classificationLabel[tooltip.cell.classification] || tooltip.cell.classification}
          </div>
        </div>
      )}
      {/* Color scale legend */}
      <div className="flex items-center gap-2 mt-3 px-2">
        <span className="text-micro font-sans text-cream-600">Low gap</span>
        <div className="flex h-3 flex-1 max-w-[200px] rounded overflow-hidden">
          <div className="flex-1 bg-white" />
          <div className="flex-1" style={{ backgroundColor: 'rgba(217,119,87,0.25)' }} />
          <div className="flex-1" style={{ backgroundColor: 'rgba(217,119,87,0.50)' }} />
          <div className="flex-1" style={{ backgroundColor: 'rgba(217,119,87,0.75)' }} />
          <div className="flex-1 bg-terracotta-400" />
        </div>
        <span className="text-micro font-sans text-cream-600">High gap</span>
      </div>
    </div>
  );
}

export { GapHeatmap };
export type { GapHeatmapProps, HeatmapCell };
