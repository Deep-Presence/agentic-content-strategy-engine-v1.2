'use client';

import { useMemo } from 'react';
import type { DayData, ViewConfig } from './mock-data';
import { COMPETITORS } from './mock-data';

interface LeaderboardProps {
  data: DayData[];
  viewConfig: ViewConfig;
  hoverIdx: number | null;
}

function BrandLogo({ domain, size = 16 }: { domain: string; size?: number }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 3, flexShrink: 0 }}
      onError={(e) => {
        const target = e.target as HTMLImageElement;
        if (!target.dataset.fallback) {
          target.dataset.fallback = '1';
          target.src = `https://logo.clearbit.com/${domain}`;
        }
      }}
    />
  );
}

export function CompetitiveLeaderboard({ data, viewConfig, hoverIdx }: LeaderboardProps) {
  const dayIdx = hoverIdx ?? data.length - 1;
  const dayData = data[dayIdx];

  const ranked = useMemo(() => {
    if (!dayData) return [];
    const entries = COMPETITORS.map(c => ({
      ...c,
      value: dayData[c.keys[viewConfig.key]] as number,
    }));
    if (viewConfig.key === 'position') {
      entries.sort((a, b) => a.value - b.value);
    } else {
      entries.sort((a, b) => b.value - a.value);
    }
    return entries;
  }, [dayData, viewConfig.key]);

  const formatValue = (v: number): string => {
    switch (viewConfig.key) {
      case 'sov': return `${v.toFixed(1)}%`;
      case 'position': return v.toFixed(1);
      case 'presenceScore': return String(Math.round(v));
      default: return String(Math.round(v));
    }
  };

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        background: 'var(--surface)',
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      {/* Title */}
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-display)',
          marginBottom: 4,
        }}
      >
        {viewConfig.leaderboardLabel}
      </div>

      {/* Rows — scrollable */}
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
      {ranked.map((entry, rank) => (
        <div
          key={entry.domain}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 8px',
            borderRadius: 'var(--radius-sm)',
            background: entry.isYou ? 'var(--accent-subtle)' : 'transparent',
            borderLeft: entry.isYou ? '3px solid var(--accent)' : '3px solid transparent',
            borderBottom: rank < ranked.length - 1 ? '1px solid var(--border)' : 'none',
            transition: 'all 180ms ease-out',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => {
            if (!entry.isYou) (e.currentTarget.style.background = 'var(--accent-subtle)');
          }}
          onMouseLeave={(e) => {
            if (!entry.isYou) (e.currentTarget.style.background = 'transparent');
          }}
        >
          {/* Rank */}
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--text-tertiary)',
              width: 20,
              textAlign: 'center',
              flexShrink: 0,
            }}
          >
            {rank + 1}
          </span>

          <BrandLogo domain={entry.domain} size={16} />

          {/* Name */}
          <span
            className="truncate"
            style={{
              flex: 1,
              fontSize: 13,
              fontWeight: entry.isYou ? 600 : 500,
              color: entry.isYou ? 'var(--accent)' : 'var(--text-primary)',
              fontFamily: 'var(--font-display)',
            }}
          >
            {entry.name}
          </span>

          {/* YOU badge */}
          {entry.isYou && (
            <span
              style={{
                fontSize: 9,
                fontWeight: 600,
                background: 'var(--accent)',
                color: 'var(--text-on-accent)',
                padding: '2px 6px',
                borderRadius: 9999,
                fontFamily: 'var(--font-display)',
                flexShrink: 0,
              }}
            >
              YOU
            </span>
          )}

          {/* Value */}
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 14,
              fontWeight: entry.isYou ? 600 : 500,
              color: entry.isYou ? 'var(--accent)' : 'var(--text-primary)',
              flexShrink: 0,
              minWidth: 44,
              textAlign: 'right',
            }}
          >
            {formatValue(entry.value)}
          </span>
        </div>
      ))}
      </div>

      {/* Date indicator on hover */}
      {hoverIdx !== null && (
        <div
          style={{
            marginTop: 4,
            paddingTop: 8,
            borderTop: '1px solid var(--border)',
            textAlign: 'center',
            fontSize: 11,
            color: 'var(--text-tertiary)',
            fontFamily: 'var(--font-display)',
          }}
        >
          {data[hoverIdx]?.dateShort}
        </div>
      )}
    </div>
  );
}
