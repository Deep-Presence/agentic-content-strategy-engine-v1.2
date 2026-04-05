'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { COMPETITORS, YOUR_DATA } from './data';
import { BrandLogo } from './brand-logo';

function barColor(rate: number) { return rate > 50 ? 'var(--success)' : rate >= 30 ? 'var(--warning)' : 'var(--error)'; }

export function HeadToHead({ onCompetitorClick }: { onCompetitorClick: (domain: string) => void }) {
  return (
    <div id="head-to-head">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div>
          <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Head-to-Head</p>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Click any card for the full battle plan</p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4 }}>
        {COMPETITORS.map((c, i) => {
          const sovMax = Math.max(YOUR_DATA.sov, c.sov);
          const TrendIcon = c.trend === 'growing' ? TrendingUp : c.trend === 'declining' ? TrendingDown : Minus;
          const trendColor = c.trend === 'growing' ? 'var(--error)' : c.trend === 'declining' ? 'var(--success)' : 'var(--text-tertiary)';
          const trendLabel = c.trend === 'growing' ? 'Growing' : c.trend === 'declining' ? 'Declining' : 'Stable';

          return (
            <div
              key={c.domain}
              onClick={() => onCompetitorClick(c.domain)}
              style={{
                minWidth: 220, maxWidth: 240, flex: '0 0 auto',
                border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: 14,
                cursor: 'pointer', transition: 'border-color 0.15s, background 0.15s',
                animation: `fadeUp 250ms ease ${i * 40}ms both`,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border-strong)'; e.currentTarget.style.background = 'var(--accent-subtle)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'transparent'; }}
            >
              {/* Header: You vs Competitor */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <BrandLogo domain={YOUR_DATA.domain} size={16} />
                  <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--accent)' }}>You</span>
                </div>
                <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 500 }}>vs</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--text-primary)' }}>{c.name}</span>
                  <BrandLogo domain={c.domain} size={16} />
                </div>
              </div>

              {/* SOV comparison */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)' }}>{YOUR_DATA.sov}%</span>
                  <span style={{ fontSize: 9, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-tertiary)' }}>SOV</span>
                  <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{c.sov}%</span>
                </div>
                <div style={{ display: 'flex', height: 5, gap: 2, borderRadius: 9999, overflow: 'hidden' }}>
                  <div style={{ width: `${(YOUR_DATA.sov / sovMax) * 100}%`, background: 'var(--accent)', borderRadius: '9999px 0 0 9999px' }} />
                  <div style={{ width: `${(c.sov / sovMax) * 100}%`, background: 'var(--border-strong)', opacity: 0.5, borderRadius: '0 9999px 9999px 0' }} />
                </div>
              </div>

              {/* Win Rate */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
                <span style={{ fontSize: 9, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-tertiary)' }}>Win Rate</span>
                <span style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: barColor(c.winRate) }}>{c.winRate}%</span>
              </div>

              {/* Trend + CTA */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <TrendIcon size={11} style={{ color: trendColor }} />
                  <span style={{ fontSize: 10, color: trendColor, fontWeight: 500 }}>{trendLabel}</span>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: trendColor }}>{c.delta > 0 ? '+' : ''}{c.delta}</span>
                </div>
                <span style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 500 }}>Details →</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
