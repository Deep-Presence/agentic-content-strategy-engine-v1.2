'use client';

import { PRIORITY_FIXES, type Severity, type Effort } from './tech-readiness-data';

const SEVERITY_STYLES: Record<Severity, { bg: string; text: string }> = {
  critical: { bg: '#E5484D', text: '#FFFFFF' },
  high: { bg: '#F5A623', text: '#11181C' },
  medium: { bg: 'var(--accent)', text: '#FFFFFF' },
  low: { bg: 'var(--border-strong)', text: 'var(--text-primary)' },
};

const EFFORT_COLORS: Record<Effort, string> = {
  low: 'var(--success)',
  medium: 'var(--warning)',
  high: 'var(--error)',
};

interface PriorityFixesProps {
  dimensionFilter: string | null;
  onViewPages: (fixTitle: string, pages: number) => void;
}

export function PriorityFixes({ dimensionFilter, onViewPages }: PriorityFixesProps) {
  const fixes = dimensionFilter
    ? PRIORITY_FIXES.filter((f) => f.dimension === dimensionFilter)
    : PRIORITY_FIXES;

  return (
    <div>
      <div className="mb-3">
        <h2
          className="text-[16px] font-semibold"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          What to Fix — Sorted by Citation Impact
          {dimensionFilter && (
            <span className="text-[12px] font-normal ml-2" style={{ color: 'var(--accent)' }}>
              Filtered: {dimensionFilter}
            </span>
          )}
        </h2>
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          Each fix shows estimated improvement to your citation rate
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {fixes.map((fix, i) => {
          const sev = SEVERITY_STYLES[fix.severity];
          return (
            <div
              key={fix.rank}
              className="border border-[var(--border)] rounded-[var(--radius-md)] p-3.5 bg-[var(--surface)] hover:border-[var(--border-strong)] transition-colors"
              style={{
                animation: `fadeUp 300ms ease ${i * 60}ms both`,
              }}
            >
              {/* Top: Rank + Severity */}
              <div className="flex items-center gap-2.5 mb-2.5">
                <span
                  className="text-[14px]"
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}
                >
                  {fix.rank}
                </span>
                <span
                  className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-[var(--radius-sm)]"
                  style={{ backgroundColor: sev.bg, color: sev.text, letterSpacing: '0.05em' }}
                >
                  {fix.severity}
                </span>
              </div>

              {/* Title */}
              <h3
                className="text-[15px] font-semibold mb-2"
                style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
              >
                {fix.title}
              </h3>

              {/* Current / Target / Why */}
              <div className="flex flex-col gap-1 mb-3">
                <p className="text-[12px]" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Currently:</span>{' '}
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{fix.current}</span>
                </p>
                <p className="text-[12px]" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Target:</span>{' '}
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{fix.target}</span>
                </p>
                <p className="text-[12px]" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Why it matters:</span>{' '}
                  {fix.why}
                </p>
              </div>

              {/* Bottom row: Impact + Effort + Pages + Actions */}
              <div className="flex items-center justify-between flex-wrap gap-2 pt-2.5 border-t border-[var(--border)]">
                <div className="flex items-center gap-5">
                  <div>
                    <span
                      className="text-[10px] uppercase tracking-[0.05em] block mb-0.5"
                      style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
                    >
                      Est. Citation Impact
                    </span>
                    <span
                      className="text-[14px] font-semibold"
                      style={{ fontFamily: 'var(--font-mono)', color: 'var(--success)' }}
                    >
                      {fix.impact}
                    </span>
                  </div>
                  <div>
                    <span
                      className="text-[10px] uppercase tracking-[0.05em] block mb-0.5"
                      style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
                    >
                      Effort
                    </span>
                    <span
                      className="text-[12px] font-medium capitalize"
                      style={{ fontFamily: 'var(--font-display)', color: EFFORT_COLORS[fix.effort] }}
                    >
                      {fix.effort}
                    </span>
                  </div>
                  <div>
                    <span
                      className="text-[10px] uppercase tracking-[0.05em] block mb-0.5"
                      style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
                    >
                      Pages
                    </span>
                    <span
                      className="text-[12px]"
                      style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
                    >
                      {fix.pages}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    className="h-[30px] px-3 text-[12px] font-medium rounded-[var(--radius-sm)] border border-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors"
                    style={{ color: 'var(--accent)', fontFamily: 'var(--font-display)' }}
                  >
                    Create tasks for all {fix.pages} pages
                  </button>
                  <button
                    className="h-[30px] px-3 text-[12px] font-medium rounded-[var(--radius-sm)] hover:bg-[var(--accent-subtle)] transition-colors"
                    style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
                    onClick={() => onViewPages(fix.title, fix.pages)}
                  >
                    View pages
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
