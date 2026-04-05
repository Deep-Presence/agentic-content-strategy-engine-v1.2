'use client';

import { CLUSTER_RANKINGS } from './data';
import { BrandLogo } from './brand-logo';

const G = { winning: { color: 'var(--success)', bg: 'var(--success-subtle)', label: 'Winning' }, competitive: { color: 'var(--warning)', bg: 'var(--warning-subtle)', label: 'Competitive' }, losing: { color: 'var(--error)', bg: 'var(--error-subtle)', label: 'Losing' } } as const;

export function TerritoryTable({ onClusterClick }: { onClusterClick: (cluster: string) => void }) {
  const groups = [
    { ...G.winning, items: CLUSTER_RANKINGS.filter((c) => c.status === 'winning') },
    { ...G.competitive, items: CLUSTER_RANKINGS.filter((c) => c.status === 'competitive') },
    { ...G.losing, items: CLUSTER_RANKINGS.filter((c) => c.status === 'losing') },
  ];

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'grid', gridTemplateColumns: '14px 1fr 60px 48px 100px 56px 48px', padding: '0 14px', height: 26, alignItems: 'center', gap: 6, borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
        <span /><TH>Cluster</TH><TH r>Your SOV</TH><TH r>Rank</TH><TH>Leader</TH><TH r>Gap</TH><TH r>Coverage</TH>
      </div>

      {groups.map((g) => g.items.length > 0 && (
        <div key={g.label}>
          <div style={{ padding: '3px 14px', background: g.bg, borderBottom: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: g.color }}>{g.label}</span>
          </div>
          {g.items.map((c) => {
            const isWhite = c.yourRank === null;
            const barMax = Math.max(c.yourShare, c.leaderShare) || 1;
            return (
              <div
                key={c.cluster}
                onClick={() => onClusterClick(c.cluster)}
                style={{
                  display: 'grid', gridTemplateColumns: '14px 1fr 60px 48px 100px 56px 48px',
                  padding: '0 14px', height: 34, alignItems: 'center', gap: 6,
                  borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer', transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: g.color }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, overflow: 'hidden' }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.cluster}</span>
                  {isWhite && <span style={{ fontSize: 7, fontWeight: 700, padding: '0 3px', borderRadius: 9999, background: 'var(--error)', color: '#fff', textTransform: 'uppercase', flexShrink: 0 }}>GAP</span>}
                </div>
                {/* Your SOV with mini bar */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                  <div style={{ width: 24, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(c.yourShare / barMax) * 100}%`, background: 'var(--accent)', borderRadius: 2 }} />
                  </div>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: isWhite ? 'var(--text-tertiary)' : 'var(--text-primary)' }}>{isWhite ? '—' : `${c.yourShare}%`}</span>
                </div>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: isWhite ? 'var(--text-tertiary)' : 'var(--text-secondary)', textAlign: 'right' }}>{isWhite ? '—' : `#${c.yourRank}`}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden' }}>
                  <BrandLogo domain={c.leaderDomain} size={12} />
                  <span style={{ fontSize: 10, color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.leaderDomain}</span>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{c.leaderShare}%</span>
                </div>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: g.color, textAlign: 'right' }}>{c.gap !== null ? `${c.gap > 0 ? '+' : ''}${c.gap}` : '—'}</span>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', textAlign: 'right' }}>{c.coverage}</span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function TH({ children, r }: { children: React.ReactNode; r?: boolean }) {
  return <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', textAlign: r ? 'right' : 'left' }}>{children}</span>;
}
