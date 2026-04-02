'use client';

import { useEffect, useState } from 'react';
import type { GapSummaryResponse } from './embedding-lab-data';

interface ShareOfVoiceBarProps {
  summary: GapSummaryResponse;
}

export function ShareOfVoiceBar({ summary }: ShareOfVoiceBarProps) {
  const [animatedWidth, setAnimatedWidth] = useState(0);

  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      setAnimatedWidth(summary.shareOfVoice);
    });
    return () => cancelAnimationFrame(raf);
  }, [summary.shareOfVoice]);

  return (
    <div className="bg-surface border border-border rounded-md p-[14px]">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
            Share of Voice
          </span>
          <span className="text-[20px] font-semibold text-text-primary tracking-[-0.02em] font-display">
            {summary.shareOfVoice}%
          </span>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-text-secondary">
          <span>{summary.companyCitations} company citations</span>
          <span className="text-text-tertiary">/</span>
          <span>{summary.totalCitations} total</span>
          <span className="text-text-tertiary">|</span>
          <span>{summary.clusterCount} clusters</span>
          <span className="text-text-tertiary">|</span>
          <span>{summary.queryCount} queries</span>
        </div>
      </div>
      <div className="w-full h-[6px] bg-bg rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-[width] duration-700 ease-out"
          style={{ width: `${animatedWidth}%` }}
        />
      </div>
    </div>
  );
}
