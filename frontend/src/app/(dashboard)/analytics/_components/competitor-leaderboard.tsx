'use client';

import { TrendingUp, TrendingDown } from 'lucide-react';
import { BrandLogo } from './brand-logo';
import { LEADERBOARD } from './data';

export function CompetitorLeaderboard() {
  return (
    <div
      className="rounded-[var(--radius-md)] overflow-hidden"
      style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
    >
      <div className="px-3.5 pt-3 pb-2">
        <div
          className="text-[10px] uppercase font-semibold tracking-[0.05em]"
          style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}
        >
          Competitor Leaderboard
        </div>
      </div>

      <div>
        {LEADERBOARD.map((entry, i) => (
          <div
            key={entry.domain}
            className="flex items-center gap-2 px-3.5 transition-colors duration-150"
            style={{
              height: 36,
              borderBottom: i < LEADERBOARD.length - 1 ? '1px solid var(--border-subtle)' : undefined,
              background: entry.isYou ? 'var(--accent-subtle)' : 'transparent',
              borderLeft: entry.isYou ? '3px solid var(--accent)' : '3px solid transparent',
              animation: `fadeUp 250ms ease ${i * 30}ms both`,
            }}
            onMouseEnter={(e) => { if (!entry.isYou) e.currentTarget.style.background = 'var(--accent-subtle)'; }}
            onMouseLeave={(e) => { if (!entry.isYou) e.currentTarget.style.background = 'transparent'; }}
          >
            <BrandLogo domain={entry.domain} size={14} />
            <span
              className="text-[13px] truncate flex-1 min-w-0"
              style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)', fontWeight: entry.isYou ? 500 : 400 }}
            >
              {entry.name}
              {entry.isYou && (
                <span
                  className="ml-1.5 text-[9px] uppercase font-semibold px-1 py-0.5 rounded-[3px]"
                  style={{ background: 'var(--accent)', color: 'var(--text-on-accent)', letterSpacing: '0.06em' }}
                >
                  YOU
                </span>
              )}
            </span>
            <span
              className="text-[13px] w-[44px] text-right flex-shrink-0"
              style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}
            >
              {entry.sov}%
            </span>
            <span
              className="text-[12px] w-[36px] text-right flex-shrink-0"
              style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
            >
              {entry.citations.toLocaleString()}
            </span>
            <div className="flex items-center gap-0.5 w-[44px] justify-end flex-shrink-0">
              {entry.delta > 0 ? (
                <TrendingUp size={12} style={{ color: 'var(--success)' }} />
              ) : entry.delta < 0 ? (
                <TrendingDown size={12} style={{ color: 'var(--error)' }} />
              ) : null}
              <span
                className="text-[12px]"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 600,
                  color: entry.delta > 0 ? 'var(--success)' : entry.delta < 0 ? 'var(--error)' : 'var(--text-tertiary)',
                }}
              >
                {entry.delta > 0 ? '+' : ''}{entry.delta}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
