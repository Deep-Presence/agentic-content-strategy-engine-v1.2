'use client';

import { ChevronRight } from 'lucide-react';
import { VISIBILITY, UNCITED_QUERIES } from './data';

export function VisibilityPipeline({ onViewAll }: { onViewAll?: () => void }) {
  return (
    <div
      id="visibility-pipeline"
      className="rounded-[var(--radius-md)]"
      style={{ border: '1px solid var(--border)', background: 'var(--surface)', padding: 14 }}
    >
      <h2
        className="text-[16px] font-semibold mb-3"
        style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
      >
        Visibility Funnel
      </h2>

      {/* Compact stacked bar */}
      <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', marginBottom: 12 }}>
        <div style={{ width: `${VISIBILITY.citedPct}%`, background: 'var(--accent)' }} />
        <div
          style={{
            width: `${VISIBILITY.mentionedPct - VISIBILITY.citedPct}%`,
            background: 'var(--warning)',
          }}
        />
        <div style={{ flex: 1, background: 'var(--border)' }} />
      </div>

      {/* 3-stat row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <div>
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-tertiary)',
              fontFamily: 'var(--font-body)',
              marginBottom: 4,
            }}
          >
            Cited
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <span
              style={{
                fontSize: 22,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                color: 'var(--accent)',
              }}
            >
              {VISIBILITY.citedPct}%
            </span>
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-body)',
              }}
            >
              {VISIBILITY.cited} of {VISIBILITY.totalQueries} queries
            </span>
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-tertiary)',
              fontFamily: 'var(--font-body)',
              marginBottom: 4,
            }}
          >
            Mentioned
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <span
              style={{
                fontSize: 22,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-primary)',
              }}
            >
              {VISIBILITY.mentionedPct}%
            </span>
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-body)',
              }}
            >
              {VISIBILITY.mentioned} of {VISIBILITY.totalQueries}
            </span>
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-tertiary)',
              fontFamily: 'var(--font-body)',
              marginBottom: 4,
            }}
          >
            Not Appearing
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <span
              style={{
                fontSize: 22,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                color: 'var(--error)',
              }}
            >
              {VISIBILITY.notAppearingPct}%
            </span>
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-body)',
              }}
            >
              {VISIBILITY.notAppearing} queries
            </span>
          </div>
        </div>
      </div>

      {/* Link to uncited queries */}
      {onViewAll && (
        <button
          onClick={onViewAll}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            marginTop: 12,
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--accent)',
            fontFamily: 'var(--font-body)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          View {UNCITED_QUERIES.length} uncited queries
          <ChevronRight size={12} />
        </button>
      )}
    </div>
  );
}
