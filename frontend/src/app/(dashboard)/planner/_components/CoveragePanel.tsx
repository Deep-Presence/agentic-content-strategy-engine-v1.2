'use client';

import { cn } from '@/lib/utils';
import { Card } from '@/components/ui';

interface CoveragePanelProps {
  open: boolean;
  coverageScore?: number;
  totalSubdomains?: number;
}

export function CoveragePanel({ open, coverageScore, totalSubdomains }: CoveragePanelProps) {
  if (!open) return null;

  const stats = [
    {
      label: 'COVERAGE SCORE',
      value: coverageScore != null ? `${(coverageScore * 100).toFixed(1)}%` : '—',
      highlight: true,
    },
    { label: 'TOTAL SUBDOMAINS', value: String(totalSubdomains ?? 0) },
  ];

  return (
    <Card hoverable={false} className="mx-0 rounded-none border-x-0 border-t-0">
      <div className="flex items-start gap-3 flex-wrap">
        {stats.map((s) => (
          <div
            key={s.label}
            className={cn(
              'flex flex-col gap-1 px-3 py-2 rounded-sm min-w-[120px]',
              s.highlight && 'bg-accent-subtle border border-accent/20'
            )}
          >
            <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
              {s.label}
            </span>
            <span
              className={cn(
                'text-[18px] font-semibold font-mono tracking-[-0.02em]',
                s.highlight ? 'text-accent' : 'text-text-primary'
              )}
            >
              {s.value}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
