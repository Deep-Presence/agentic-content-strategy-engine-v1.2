'use client';

import { useState, useMemo } from 'react';
import type { StructuralSignal, ImpactLevel } from './data';

const IMPACT_STYLES: Record<ImpactLevel, { bg: string; text: string }> = {
  critical: { bg: '#E5484D', text: '#FFFFFF' },
  high: { bg: '#F5A623', text: '#11181C' },
  medium: { bg: 'var(--accent)', text: '#FFFFFF' },
  low: { bg: 'rgba(104,112,118,0.2)', text: 'var(--text-primary)' },
};

interface StructuralAlignmentProps {
  signals: StructuralSignal[];
}

export function StructuralAlignment({ signals }: StructuralAlignmentProps) {
  const [showAll, setShowAll] = useState(false);

  const displayed = useMemo(() => {
    return showAll ? signals : signals.slice(0, 12);
  }, [signals, showAll]);

  const maxAbsGap = useMemo(() => {
    return Math.max(...signals.map((s) => Math.abs(s.yours - s.citedAvg)));
  }, [signals]);

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: 4, padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
            What Structure Gets Cited? Your Content vs What AI Engines Prefer
          </h3>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            Structural signals sorted by Pearson correlation coefficient with citation likelihood
          </p>
        </div>
        <button
          onClick={() => setShowAll(!showAll)}
          style={{
            fontSize: 12, color: 'var(--accent)', background: 'none', border: 'none',
            cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
          }}
        >
          {showAll ? 'Show top 12' : 'Show all 20 signals'}
        </button>
      </div>

      {/* Column headers */}
      <div style={{
        display: 'grid', gridTemplateColumns: '160px 60px 1fr 70px',
        padding: '0 0 6px 0', borderBottom: '1px solid var(--border)',
        alignItems: 'center',
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
          Signal
        </span>
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', textAlign: 'center' }}>
          r
        </span>
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', textAlign: 'center' }}>
          Your Gap vs Cited Avg
        </span>
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', textAlign: 'right' }}>
          Impact
        </span>
      </div>

      {/* Rows */}
      <div>
        {displayed.map((s, idx) => {
          const gap = s.yours - s.citedAvg;
          const gapPct = gap / maxAbsGap; // -1 to +1
          const impactStyle = IMPACT_STYLES[s.impact];

          return (
            <div
              key={s.signal}
              className="group"
              style={{
                display: 'grid', gridTemplateColumns: '160px 60px 1fr 70px',
                alignItems: 'center',
                padding: '8px 0',
                borderBottom: idx < displayed.length - 1 ? '1px solid var(--border-subtle)' : undefined,
                position: 'relative',
                cursor: 'default',
              }}
            >
              {/* Signal name */}
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                {s.signal}
              </span>

              {/* r value */}
              <span style={{
                fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                textAlign: 'center',
              }}>
                {s.r.toFixed(2)}
              </span>

              {/* Diverging bar */}
              <div style={{ display: 'flex', alignItems: 'center', padding: '0 12px' }}>
                <div style={{ position: 'relative', width: '100%', height: 20 }}>
                  {/* Center line */}
                  <div style={{
                    position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1,
                    background: 'var(--text-tertiary)', opacity: 0.3,
                  }} />

                  {/* Bar */}
                  {gap < 0 ? (
                    // Negative gap: bar extends left from center
                    <div style={{
                      position: 'absolute',
                      right: '50%',
                      top: 4,
                      height: 12,
                      width: `${Math.abs(gapPct) * 50}%`,
                      borderRadius: '2px 0 0 2px',
                      background: Math.abs(gap) > 30 ? '#E5484D' : '#E87C3F',
                      transition: 'width 0.3s ease',
                    }} />
                  ) : (
                    // Positive gap: bar extends right from center
                    <div style={{
                      position: 'absolute',
                      left: '50%',
                      top: 4,
                      height: 12,
                      width: `${Math.abs(gapPct) * 50}%`,
                      borderRadius: '0 2px 2px 0',
                      background: '#34B27B',
                      transition: 'width 0.3s ease',
                    }} />
                  )}

                  {/* Gap label */}
                  <span style={{
                    position: 'absolute',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    ...(gap < 0
                      ? { right: `calc(50% + ${Math.abs(gapPct) * 50}% + 6px)` }
                      : { left: `calc(50% + ${Math.abs(gapPct) * 50}% + 6px)` }
                    ),
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 500,
                    color: gap < 0 ? '#E5484D' : '#34B27B',
                    whiteSpace: 'nowrap',
                  }}>
                    {gap > 0 ? '+' : ''}{gap}%
                  </span>
                </div>
              </div>

              {/* Impact badge */}
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', height: 20,
                  padding: '0 8px', borderRadius: 4,
                  fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
                  background: impactStyle.bg, color: impactStyle.text,
                }}>
                  {s.impact}
                </span>
              </div>

              {/* Hover tooltip */}
              <div
                className="opacity-0 group-hover:opacity-100 pointer-events-none"
                style={{
                  position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)',
                  background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4,
                  padding: '6px 10px', boxShadow: 'var(--shadow-float)',
                  whiteSpace: 'nowrap', zIndex: 10, transition: 'opacity 0.15s',
                  fontSize: 11, color: 'var(--text-primary)',
                }}
              >
                {s.signal} — Cited avg: {s.citedAvg}% | Yours: {s.yours}% | Gap: {gap > 0 ? '+' : ''}{gap}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
