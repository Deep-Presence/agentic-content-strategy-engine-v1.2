'use client';

import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils/cn';

interface TreemapItem {
  domain: string;
  count: number;
  avgSimilarity: number;
  authorityType: string;
}

interface CitationTreemapProps {
  data: TreemapItem[];
  onDomainClick?: (domain: string) => void;
  width?: number;
  height?: number;
  className?: string;
}

interface TreemapRect {
  x: number;
  y: number;
  w: number;
  h: number;
  item: TreemapItem;
}

function squarify(items: TreemapItem[], x: number, y: number, w: number, h: number): TreemapRect[] {
  if (items.length === 0) return [];
  if (items.length === 1) {
    return [{ x, y, w, h, item: items[0] }];
  }

  const total = items.reduce((s, i) => s + i.count, 0);
  const sorted = [...items].sort((a, b) => b.count - a.count);
  const rects: TreemapRect[] = [];

  let remaining = [...sorted];
  let cx = x;
  let cy = y;
  let cw = w;
  let ch = h;

  while (remaining.length > 0) {
    const isWide = cw >= ch;
    const side = isWide ? ch : cw;
    const remTotal = remaining.reduce((s, i) => s + i.count, 0);

    let row: TreemapItem[] = [remaining[0]];
    let rowTotal = remaining[0].count;
    let worstRatio = Infinity;

    for (let i = 1; i < remaining.length; i++) {
      const newTotal = rowTotal + remaining[i].count;
      const rowWidth = (newTotal / remTotal) * (isWide ? cw : ch);

      let maxRatio = 0;
      [...row, remaining[i]].forEach((item) => {
        const itemHeight = (item.count / newTotal) * side;
        const ratio = Math.max(rowWidth / itemHeight, itemHeight / rowWidth);
        maxRatio = Math.max(maxRatio, ratio);
      });

      if (i === 1 || maxRatio <= worstRatio) {
        row.push(remaining[i]);
        rowTotal = newTotal;
        worstRatio = maxRatio;
      } else {
        break;
      }
    }

    const rowWidth = (rowTotal / remTotal) * (isWide ? cw : ch);
    let offset = 0;

    row.forEach((item) => {
      const itemSize = (item.count / rowTotal) * side;
      if (isWide) {
        rects.push({ x: cx, y: cy + offset, w: rowWidth, h: itemSize, item });
      } else {
        rects.push({ x: cx + offset, y: cy, w: itemSize, h: rowWidth, item });
      }
      offset += itemSize;
    });

    remaining = remaining.slice(row.length);
    if (isWide) {
      cx += rowWidth;
      cw -= rowWidth;
    } else {
      cy += rowWidth;
      ch -= rowWidth;
    }
  }

  return rects;
}

function similarityToColor(similarity: number): string {
  const intensity = Math.min(1, Math.max(0, (similarity - 0.5) / 0.4));
  const r = Math.round(106 + intensity * (74 - 106));
  const g = Math.round(155 + intensity * (123 - 155));
  const b = Math.round(204 + intensity * (168 - 204));
  return `rgb(${r}, ${g}, ${b})`;
}

function CitationTreemap({
  data,
  onDomainClick,
  width = 700,
  height = 400,
  className,
}: CitationTreemapProps) {
  const [hoveredDomain, setHoveredDomain] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    item: TreemapItem;
  } | null>(null);

  const rects = useMemo(
    () => squarify(data, 0, 0, width, height),
    [data, width, height],
  );

  return (
    <div className={cn('relative', className)}>
      <svg
        width={width}
        height={height}
        className="rounded-md border border-[var(--border-default)]"
      >
        {rects.map((rect) => {
          const isHovered = hoveredDomain === rect.item.domain;
          return (
            <g
              key={rect.item.domain}
              onMouseEnter={(e) => {
                setHoveredDomain(rect.item.domain);
                setTooltip({
                  x: e.clientX - (e.currentTarget.closest('svg')?.getBoundingClientRect().left ?? 0),
                  y: e.clientY - (e.currentTarget.closest('svg')?.getBoundingClientRect().top ?? 0),
                  item: rect.item,
                });
              }}
              onMouseMove={(e) => {
                setTooltip({
                  x: e.clientX - (e.currentTarget.closest('svg')?.getBoundingClientRect().left ?? 0),
                  y: e.clientY - (e.currentTarget.closest('svg')?.getBoundingClientRect().top ?? 0),
                  item: rect.item,
                });
              }}
              onMouseLeave={() => {
                setHoveredDomain(null);
                setTooltip(null);
              }}
              onClick={() => onDomainClick?.(rect.item.domain)}
              className="cursor-pointer"
            >
              <rect
                x={rect.x + 1}
                y={rect.y + 1}
                width={Math.max(0, rect.w - 2)}
                height={Math.max(0, rect.h - 2)}
                fill={similarityToColor(rect.item.avgSimilarity)}
                stroke={isHovered ? '#141413' : '#ffffff'}
                strokeWidth={isHovered ? 2 : 1}
                rx={3}
                opacity={isHovered ? 1 : 0.85}
              />
              {rect.w > 50 && rect.h > 30 && (
                <>
                  <text
                    x={rect.x + rect.w / 2}
                    y={rect.y + rect.h / 2 - 4}
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize={rect.w > 80 ? 12 : 10}
                    fontFamily="ui-sans-serif, -apple-system, sans-serif"
                    fontWeight="600"
                  >
                    {rect.item.domain.replace('www.', '')}
                  </text>
                  <text
                    x={rect.x + rect.w / 2}
                    y={rect.y + rect.h / 2 + 12}
                    textAnchor="middle"
                    fill="rgba(255,255,255,0.8)"
                    fontSize={10}
                    fontFamily="ui-sans-serif, -apple-system, sans-serif"
                  >
                    {rect.item.count} citations
                  </text>
                </>
              )}
            </g>
          );
        })}
      </svg>
      {tooltip && (
        <div
          className="absolute z-50 pointer-events-none bg-cream-950 text-white px-3 py-2 rounded shadow-lg text-caption font-sans"
          style={{
            left: Math.min(tooltip.x + 12, width - 220),
            top: tooltip.y - 10,
          }}
        >
          <div className="font-medium">{tooltip.item.domain}</div>
          <div className="text-cream-400 text-micro mt-1">Citations: {tooltip.item.count}</div>
          <div className="text-cream-400 text-micro">Avg Similarity: {tooltip.item.avgSimilarity.toFixed(2)}</div>
          <div className="text-cream-400 text-micro capitalize">Authority: {tooltip.item.authorityType.replace(/_/g, ' ')}</div>
        </div>
      )}
    </div>
  );
}

export { CitationTreemap };
export type { CitationTreemapProps, TreemapItem };
