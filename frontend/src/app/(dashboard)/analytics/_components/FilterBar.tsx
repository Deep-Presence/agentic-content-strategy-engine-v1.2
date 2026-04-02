'use client';

import { useState } from 'react';
import { Calendar, ChevronDown, X } from 'lucide-react';

export function CitationFilterBar({
  platform,
  onPlatformChange,
  cluster,
  onClusterChange,
}: {
  platform: string;
  onPlatformChange: (v: string) => void;
  cluster: string;
  onClusterChange: (v: string) => void;
}) {
  const [showPlatformDrop, setShowPlatformDrop] = useState(false);
  const [showClusterDrop, setShowClusterDrop] = useState(false);

  const platforms = ['All Platforms', 'ChatGPT', 'Claude', 'Perplexity', 'Google AI', 'Gemini'];
  const clusters = ['All Clusters', 'AI App Builders', 'No-Code Tools', 'Developer Productivity', 'Enterprise Security'];

  const hasFilters = platform !== 'All Platforms' || cluster !== 'All Clusters';

  return (
    <div
      className="flex items-center gap-3 px-4 h-[44px] border-b"
      style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}
    >
      {/* Date Range */}
      <button
        className="flex items-center gap-2 px-2 py-1 rounded-sm text-[13px]"
        style={{ color: 'var(--text-primary)' }}
      >
        <Calendar size={14} style={{ color: 'var(--text-secondary)' }} />
        <span>Mar 1, 2026 – Mar 28, 2026</span>
      </button>

      <div className="h-4 w-px" style={{ background: 'var(--border)' }} />

      {/* Platform Filter */}
      <div className="relative">
        <button
          className="flex items-center gap-1 px-2 py-1 rounded-sm text-[13px]"
          style={{ color: 'var(--text-primary)' }}
          onClick={() => { setShowPlatformDrop(!showPlatformDrop); setShowClusterDrop(false); }}
        >
          <span>{platform}</span>
          <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} />
        </button>
        {showPlatformDrop && (
          <div
            className="absolute top-full left-0 mt-1 z-50 min-w-[160px] py-1 rounded-md"
            style={{ background: 'var(--surface-raised)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-float)' }}
          >
            {platforms.map((p) => (
              <button
                key={p}
                className="block w-full text-left px-3 py-1.5 text-[12px] transition-colors"
                style={{
                  color: p === platform ? 'var(--accent)' : 'var(--text-primary)',
                  background: p === platform ? 'var(--accent-subtle)' : 'transparent',
                }}
                onMouseEnter={(e) => { if (p !== platform) (e.target as HTMLElement).style.background = 'var(--accent-subtle)'; }}
                onMouseLeave={(e) => { if (p !== platform) (e.target as HTMLElement).style.background = 'transparent'; }}
                onClick={() => { onPlatformChange(p); setShowPlatformDrop(false); }}
              >
                {p}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="h-4 w-px" style={{ background: 'var(--border)' }} />

      {/* Cluster Filter */}
      <div className="relative">
        <button
          className="flex items-center gap-1 px-2 py-1 rounded-sm text-[13px]"
          style={{ color: 'var(--text-primary)' }}
          onClick={() => { setShowClusterDrop(!showClusterDrop); setShowPlatformDrop(false); }}
        >
          <span>{cluster}</span>
          <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} />
        </button>
        {showClusterDrop && (
          <div
            className="absolute top-full left-0 mt-1 z-50 min-w-[180px] py-1 rounded-md"
            style={{ background: 'var(--surface-raised)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-float)' }}
          >
            {clusters.map((c) => (
              <button
                key={c}
                className="block w-full text-left px-3 py-1.5 text-[12px] transition-colors"
                style={{
                  color: c === cluster ? 'var(--accent)' : 'var(--text-primary)',
                  background: c === cluster ? 'var(--accent-subtle)' : 'transparent',
                }}
                onMouseEnter={(e) => { if (c !== cluster) (e.target as HTMLElement).style.background = 'var(--accent-subtle)'; }}
                onMouseLeave={(e) => { if (c !== cluster) (e.target as HTMLElement).style.background = 'transparent'; }}
                onClick={() => { onClusterChange(c); setShowClusterDrop(false); }}
              >
                {c}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Clear */}
      {hasFilters && (
        <button
          className="ml-auto flex items-center gap-1 text-[12px] px-2 py-1"
          style={{ color: 'var(--text-secondary)' }}
          onClick={() => { onPlatformChange('All Platforms'); onClusterChange('All Clusters'); }}
        >
          <X size={12} /> Clear
        </button>
      )}
    </div>
  );
}
