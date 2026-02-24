'use client';

import { cn } from '@/lib/utils/cn';

interface LegendItem {
  label: string;
  color: string;
  shape?: 'circle' | 'triangle' | 'square' | 'line';
}

interface ChartLegendProps {
  items: LegendItem[];
  className?: string;
}

function ShapeIcon({ shape, color }: { shape: string; color: string }) {
  if (shape === 'triangle') {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" className="shrink-0">
        <polygon points="6,1 11,10 1,10" fill={color} />
      </svg>
    );
  }
  if (shape === 'square') {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" className="shrink-0">
        <rect x="1" y="1" width="10" height="10" fill={color} rx="1" />
      </svg>
    );
  }
  if (shape === 'line') {
    return (
      <svg width="16" height="12" viewBox="0 0 16 12" className="shrink-0">
        <line x1="0" y1="6" x2="16" y2="6" stroke={color} strokeWidth="2" />
      </svg>
    );
  }
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" className="shrink-0">
      <circle cx="6" cy="6" r="5" fill={color} />
    </svg>
  );
}

function ChartLegend({ items, className }: ChartLegendProps) {
  return (
    <div className={cn('flex flex-wrap items-center gap-x-4 gap-y-1', className)}>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <ShapeIcon shape={item.shape || 'circle'} color={item.color} />
          <span className="text-caption font-sans text-cream-700">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export { ChartLegend };
export type { ChartLegendProps, LegendItem };
