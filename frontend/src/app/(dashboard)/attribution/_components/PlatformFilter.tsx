'use client';

import { cn } from '@/lib/utils';
import type { Platform } from '@/types';
import { platformLabels } from './data';

interface PlatformFilterProps {
  selected: Platform | 'all';
  onChange: (value: Platform | 'all') => void;
}

const platforms: (Platform | 'all')[] = ['all', 'chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini'];

export function PlatformFilter({ selected, onChange }: PlatformFilterProps) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {platforms.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={cn(
            'h-[30px] px-3 rounded-sm text-[12px] font-medium transition-all duration-150 cursor-pointer',
            selected === p
              ? 'bg-accent text-text-on-accent border border-accent'
              : 'bg-surface text-text-secondary border border-border hover:border-border-strong hover:text-text-primary'
          )}
        >
          {p === 'all' ? 'All Platforms' : platformLabels[p]}
        </button>
      ))}
    </div>
  );
}
