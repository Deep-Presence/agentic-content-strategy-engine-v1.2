'use client';

import { useState, useRef, useEffect } from 'react';
import { Calendar, ChevronDown, X } from 'lucide-react';

interface FilterBarProps {
  platform: string;
  onPlatformChange: (v: string) => void;
  cluster: string;
  onClusterChange: (v: string) => void;
}

const PLATFORMS = ['All Platforms', 'ChatGPT', 'Claude', 'Perplexity', 'Google AI', 'Gemini'];
const CLUSTERS = ['All Clusters', 'AI App Builders', 'Enterprise Features', 'Security & Compliance', 'Developer Tools', 'No-Code Platforms'];

function DropdownSelect({ value, options, onChange }: { value: string; options: string[]; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 h-[30px] rounded-[var(--radius-sm)] text-[12px] font-medium transition-colors duration-150"
        style={{
          fontFamily: 'var(--font-body)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        {value}
        <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} />
      </button>
      {open && (
        <div
          className="absolute top-[34px] left-0 z-50 min-w-[160px] py-1 rounded-[var(--radius-md)]"
          style={{ background: 'var(--surface-raised)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-float)' }}
        >
          {options.map((opt) => (
            <button
              key={opt}
              onClick={() => { onChange(opt); setOpen(false); }}
              className="block w-full text-left px-3 py-1.5 text-[12px] transition-colors duration-150"
              style={{
                fontFamily: 'var(--font-body)',
                color: opt === value ? 'var(--accent)' : 'var(--text-primary)',
                background: opt === value ? 'var(--accent-subtle)' : 'transparent',
              }}
              onMouseEnter={(e) => { if (opt !== value) (e.target as HTMLElement).style.background = 'var(--accent-subtle)'; }}
              onMouseLeave={(e) => { if (opt !== value) (e.target as HTMLElement).style.background = 'transparent'; }}
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function CitationFilterBar({ platform, onPlatformChange, cluster, onClusterChange }: FilterBarProps) {
  const hasFilters = platform !== 'All Platforms' || cluster !== 'All Clusters';

  return (
    <div
      className="flex items-center gap-3 px-6 h-[44px]"
      style={{ borderBottom: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-1.5 text-[12px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
        <Calendar size={13} style={{ color: 'var(--text-tertiary)' }} />
        <span>Mar 1, 2026 &ndash; Mar 28, 2026</span>
      </div>

      <div style={{ width: 1, height: 20, background: 'var(--border)' }} />

      <DropdownSelect value={platform} options={PLATFORMS} onChange={onPlatformChange} />
      <DropdownSelect value={cluster} options={CLUSTERS} onChange={onClusterChange} />

      {hasFilters && (
        <>
          <div style={{ width: 1, height: 20, background: 'var(--border)' }} />
          <button
            onClick={() => { onPlatformChange('All Platforms'); onClusterChange('All Clusters'); }}
            className="flex items-center gap-1 text-[11px] font-medium transition-colors duration-150"
            style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)' }}
            onMouseEnter={(e) => ((e.target as HTMLElement).style.color = 'var(--error)')}
            onMouseLeave={(e) => ((e.target as HTMLElement).style.color = 'var(--text-tertiary)')}
          >
            <X size={11} />
            Clear
          </button>
        </>
      )}
    </div>
  );
}
