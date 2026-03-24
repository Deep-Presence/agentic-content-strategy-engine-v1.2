'use client';

import { cn } from '@/lib/utils';
import { Card } from '@/components/ui';
import { getCoverage } from './topic-data';

interface CoveragePanelProps {
  open: boolean;
}

export function CoveragePanel({ open }: CoveragePanelProps) {
  const cov = getCoverage();
  if (!open) return null;

  const stats = [
    {
      label: 'SAMPLE COVERAGE',
      value: `${(cov.sample_coverage * 100).toFixed(1)}%`,
      highlight: true,
    },
    { label: 'OBSERVED', value: String(cov.observed_count) },
    { label: 'CHAO1 LOWER BOUND', value: String(cov.chao1_lower_bound) },
    { label: 'CR MEDIAN', value: String(cov.median_estimate) },
    {
      label: 'REMAINING (EST)',
      value: `${cov.estimate_range[0]}–${cov.estimate_range[1]}`,
    },
  ];

  const pairwise = Object.entries(cov.pairwise_estimates);

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

        {/* Pairwise CR values */}
        <div className="flex flex-col gap-1 px-3 py-2">
          <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
            PAIRWISE CR
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            {pairwise.map(([pair, val]) => {
              const label = pair.replace(/_/g, ' ').replace('source ', '').toUpperCase();
              return (
                <span key={pair} className="text-[10px] text-text-secondary font-mono">
                  {label}: {val}
                </span>
              );
            })}
          </div>
        </div>
      </div>
    </Card>
  );
}
