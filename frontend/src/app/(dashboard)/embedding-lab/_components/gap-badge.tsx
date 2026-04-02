'use client';

import { cn } from '@/lib/utils';

type GapClassification = 'critical' | 'warning' | 'moderate' | 'strong';

const GAP_CONFIG: Record<GapClassification, { label: string; bg: string; text: string }> = {
  critical: { label: 'Critical Gap', bg: 'bg-error-subtle', text: 'text-error' },
  warning: { label: 'Gap to Close', bg: 'bg-warning-subtle', text: 'text-warning' },
  moderate: { label: 'Moderate', bg: 'bg-info-subtle', text: 'text-info' },
  strong: { label: 'Strong', bg: 'bg-success-subtle', text: 'text-success' },
};

interface GapBadgeProps {
  classification: GapClassification;
  className?: string;
}

export function GapBadge({ classification, className }: GapBadgeProps) {
  const config = GAP_CONFIG[classification];
  return (
    <span
      className={cn(
        'inline-flex items-center px-[6px] py-[1px] rounded-full text-[10px] font-medium',
        config.bg,
        config.text,
        className,
      )}
    >
      {config.label}
    </span>
  );
}

export function gapClassificationFromScore(gap: number): GapClassification {
  if (gap > 0.12) return 'critical';
  if (gap > 0.05) return 'warning';
  if (gap > -0.02) return 'moderate';
  return 'strong';
}
