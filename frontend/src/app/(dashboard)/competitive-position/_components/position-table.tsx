'use client';

import { COMPETITORS, COMPETITOR_DETAILS, YOUR_DATA } from './data';
import { BrandLogo } from './brand-logo';
import { Sparkline } from './sparkline';

function barColor(rate: number) { return rate > 50 ? 'var(--success)' : rate >= 30 ? 'var(--warning)' : 'var(--error)'; }
function dirLabel(d: number) { return d > 2 ? 'Surging' : d > 0 ? 'Growing' : d === 0 ? 'Stable' : 'Declining'; }
function dirColor(d: number) { return d > 2 ? 'var(--error)' : d > 0 ? 'var(--warning)' : d === 0 ? 'var(--text-tertiary)' : 'var(--success)'; }

export function PositionTable({ onCompetitorClick }: { onCompetitorClick: (domain: string) => void }) {
  const sorted = [...COMPETITORS].sort((a, b) => b.winRate - a.winRate);

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 64px 80px 64px 64px 52px 64px', padding: '0 14px', height: 28, alignItems: 'center', borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
        <TH>Competitor</TH><TH r>Win Rate</TH><TH>Win/Loss Bar</TH><TH r>Queries Won</TH><TH r>Queries Lost</TH><TH>Trend</TH><TH r>Threat Level</TH>
      </div>

      {/* Rows */}
      {sorted.map((c) => {
        const detail = COMPETITOR_DETAILS[c.domain];
        const won = detail?.queriesYouWin.length || 0;
        const lost = detail?.queriesYouLose.length || 0;
        const total = won + lost;

        return (
          <div
            key={c.domain}
            onClick={() => onCompetitorClick(c.domain)}
            style={{
              display: 'grid', gridTemplateColumns: '1fr 64px 80px 64px 64px 52px 64px',
              padding: '0 14px', height: 38, alignItems: 'center',
              borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer', transition: 'background 0.12s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            {/* Competitor */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <BrandLogo domain={c.domain} size={16} />
              <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{c.name}</span>
              <Sparkline data={c.sparkline} color={c.delta > 0 ? 'var(--error)' : c.delta < 0 ? 'var(--success)' : 'var(--text-tertiary)'} width={36} height={12} />
            </div>

            {/* Win Rate */}
            <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600, color: barColor(c.winRate), textAlign: 'right' }}>{c.winRate}%</span>

            {/* Win/Loss stacked bar */}
            <div style={{ display: 'flex', height: 6, borderRadius: 9999, overflow: 'hidden', gap: 1 }}>
              <div style={{ width: total > 0 ? `${(won / total) * 100}%` : '0%', background: 'var(--success)', borderRadius: '9999px 0 0 9999px' }} />
              <div style={{ width: total > 0 ? `${(lost / total) * 100}%` : '0%', background: 'var(--error)', opacity: 0.6, borderRadius: '0 9999px 9999px 0' }} />
            </div>

            {/* Queries Won */}
            <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--success)', textAlign: 'right' }}>{won}</span>

            {/* Queries Lost */}
            <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--error)', textAlign: 'right' }}>{lost}</span>

            {/* Trend sparkline direction */}
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: c.delta > 0 ? 'var(--error)' : c.delta < 0 ? 'var(--success)' : 'var(--text-tertiary)' }}>
              {c.delta > 0 ? '+' : ''}{c.delta}
            </span>

            {/* Threat Level */}
            <span style={{ fontSize: 9, fontWeight: 600, textAlign: 'right', color: dirColor(c.delta), fontFamily: 'var(--font-display)' }}>{dirLabel(c.delta)}</span>
          </div>
        );
      })}

      {/* Insight */}
      <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', background: 'var(--bg)' }}>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
          You beat V0.dev and Replit consistently but lose to Bolt.new and Emergent on technical queries. Adding FAQ sections and structured data to your top pages could shift 3 matchups.
        </p>
      </div>
    </div>
  );
}

function TH({ children, r }: { children: React.ReactNode; r?: boolean }) {
  return <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', textAlign: r ? 'right' : 'left' }}>{children}</span>;
}
