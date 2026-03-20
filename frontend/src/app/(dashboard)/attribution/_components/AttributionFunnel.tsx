'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { FunnelStepData } from './data';
import { getPlatformBreakdownForStage, platformLabels } from './data';

interface AttributionFunnelProps {
  steps: FunnelStepData[];
}

export function AttributionFunnel({ steps }: AttributionFunnelProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const maxCount = steps[0]?.count || 1;

  return (
    <div className="space-y-2">
      {steps.map((step, i) => {
        const widthPct = Math.max(20, (step.count / maxCount) * 100);
        const breakdown = getPlatformBreakdownForStage(i);

        return (
          <div key={step.name} className="relative group">
            <div className="flex items-center gap-3">
              {/* Label */}
              <div className="w-[140px] flex-shrink-0 text-right">
                <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
                  {step.name}
                </div>
              </div>

              {/* Bar */}
              <div className="flex-1 relative">
                <div
                  className={cn(
                    'relative h-[48px] rounded-sm border border-border transition-all duration-300 ease-out flex items-center px-3 cursor-default',
                    'bg-accent-subtle hover:border-accent'
                  )}
                  style={{ width: `${widthPct}%` }}
                  onMouseEnter={() => setHoveredIndex(i)}
                  onMouseLeave={() => setHoveredIndex(null)}
                >
                  {/* Fill overlay */}
                  <div
                    className="absolute inset-0 rounded-sm bg-accent opacity-[0.08]"
                    style={{ width: `${widthPct}%` }}
                  />
                  <span className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary relative z-10">
                    {step.name === 'Revenue'
                      ? `$${step.count.toLocaleString()}`
                      : step.count.toLocaleString()}
                  </span>
                </div>

                {/* Platform breakdown tooltip */}
                {hoveredIndex === i && (
                  <div className="absolute left-0 top-[54px] z-30 bg-surface-raised border border-border rounded-md p-2.5 shadow-float min-w-[220px] backdrop-blur-sm">
                    <div className="text-[11px] font-medium text-text-tertiary uppercase tracking-[0.06em] mb-1.5">
                      Platform Breakdown
                    </div>
                    <div className="space-y-1">
                      {breakdown.map((b) => (
                        <div key={b.platform} className="flex items-center justify-between text-[12px]">
                          <span className="text-text-secondary">{platformLabels[b.platform]}</span>
                          <span className="text-text-primary font-medium">
                            {step.name === 'Revenue'
                              ? `$${b.value.toLocaleString()}`
                              : b.value.toLocaleString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Conversion rate */}
              <div className="w-[80px] flex-shrink-0">
                {step.rate && (
                  <span className="text-[12px] text-text-tertiary">{step.rate}</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
