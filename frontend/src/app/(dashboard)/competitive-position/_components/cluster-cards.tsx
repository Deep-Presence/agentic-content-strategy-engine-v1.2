'use client';

import { useState } from 'react';
import { CLUSTER_CARDS, INTENT_BREAKDOWN, FUNNEL_BREAKDOWN, PERSONA_BREAKDOWN, type DimensionBreakdown } from './data';
import { BrandLogo } from './brand-logo';

const STATUS_COLORS: Record<string, string> = { winning: '#34B27B', competitive: '#D97706', losing: '#E5484D' };

// ─── Mini Donut (SVG) ──────────────────────────────────────────────────────

function MiniDonut({ you, total, size = 48 }: { you: number; total: number; size?: number }) {
  const pct = Math.min(you / total, 1);
  const r = (size - 8) / 2; const cx = size / 2; const cy = size / 2; const sw = 5;
  const circ = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#ECEEF0" strokeWidth={sw} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#5BA4C4" strokeWidth={sw} strokeDasharray={`${circ * pct} ${circ * (1 - pct)}`} strokeLinecap="round" transform={`rotate(-90 ${cx} ${cy})`} />
      <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="central" fill="#11181C" fontSize={10} fontWeight={600} fontFamily="JetBrains Mono, monospace">{you}%</text>
    </svg>
  );
}

// ─── Dimension Card ─────────────────────────────────────────────────────────

function DimensionCard({ d }: { d: DimensionBreakdown }) {
  const maxPct = Math.max(d.you, d.leaderPct, 25);
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '14px', display: 'flex', gap: 14, alignItems: 'flex-start' }}>
      <MiniDonut you={d.you} total={maxPct} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{d.dimension}</p>
        <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>{d.totalQueries} queries tracked</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
          <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>Leader:</span>
          <BrandLogo domain={d.leaderDomain} size={12} />
          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-primary)' }}>{d.leader}</span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{d.leaderPct}%</span>
        </div>
        <p style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.4 }}>{d.insight}</p>
      </div>
    </div>
  );
}

// ─── Competitive Breakdown (Intent / Funnel / Persona) ──────────────────────

function CompetitiveBreakdown() {
  const [view, setView] = useState<'intent' | 'funnel' | 'persona'>('intent');
  const data = view === 'intent' ? INTENT_BREAKDOWN : view === 'funnel' ? FUNNEL_BREAKDOWN : PERSONA_BREAKDOWN;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div>
          <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Competitive Breakdown</p>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Your SOV by dimension. Each card shows your share vs the leader.</p>
        </div>
        <div style={{ display: 'flex', gap: 0, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
          {([['intent', 'Intent'], ['funnel', 'Funnel'], ['persona', 'Persona']] as const).map(([key, label]) => (
            <button key={key} onClick={() => setView(key)} style={{
              padding: '5px 14px', fontSize: 11, fontWeight: 500, border: 'none', cursor: 'pointer',
              background: view === key ? 'var(--accent)' : 'transparent', color: view === key ? '#fff' : 'var(--text-secondary)',
              fontFamily: 'var(--font-display)', transition: 'all 0.15s',
            }}>{label}</button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2" style={{ gap: 10 }}>
        {data.map((d) => <DimensionCard key={d.dimension} d={d} />)}
      </div>
    </div>
  );
}

// ─── Cluster Cards ──────────────────────────────────────────────────────────

function ClusterCard({ card, onClick }: { card: typeof CLUSTER_CARDS[0]; onClick: () => void }) {
  return (
    <div onClick={onClick} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '14px', cursor: 'pointer', transition: 'border-color 0.15s', borderLeft: `3px solid ${STATUS_COLORS[card.status]}` }}
      onMouseEnter={(e) => (e.currentTarget.style.borderTopColor = 'var(--border-strong)')} onMouseLeave={(e) => (e.currentTarget.style.borderTopColor = 'var(--border)')}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <div>
          <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{card.cluster}</p>
          <div style={{ display: 'flex', gap: 4, marginTop: 3 }}>
            <span style={{ fontSize: 8, padding: '1px 5px', borderRadius: 3, background: 'var(--accent-subtle)', color: 'var(--accent)', fontWeight: 500 }}>{card.intent}</span>
            <span style={{ fontSize: 8, padding: '1px 5px', borderRadius: 3, background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-tertiary)', fontWeight: 500 }}>{card.funnelStage}</span>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <p style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: card.yourRank ? 'var(--text-primary)' : '#E5484D' }}>
            {card.yourRank ? `#${card.yourRank}` : 'No presence'}
          </p>
          <p style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{card.totalCitations} citations</p>
        </div>
      </div>

      {card.topBrands.slice(0, 4).map((b, i) => {
        const isYou = b.domain === 'lovable.dev';
        return (
          <div key={b.domain} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 0' }}>
            <span style={{ fontSize: 9, color: 'var(--text-tertiary)', minWidth: 14 }}>#{i + 1}</span>
            <BrandLogo domain={b.domain} size={12} />
            <span style={{ fontSize: 11, fontWeight: isYou ? 600 : 400, color: isYou ? '#5BA4C4' : 'var(--text-primary)', flex: 1 }}>{isYou ? 'You' : b.name}</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{b.sov}%</span>
          </div>
        );
      })}

      <p style={{ fontSize: 10, color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: 6, marginTop: 6, lineHeight: 1.4 }}>{card.contentGap}</p>
    </div>
  );
}

function ClusterBreakdown({ onClusterClick }: { onClusterClick: (cluster: string) => void }) {
  return (
    <div>
      <div style={{ marginBottom: 10 }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Cluster Breakdown</p>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Top competitors in each query cluster. Click for full query list.</p>
      </div>
      <div className="grid grid-cols-3" style={{ gap: 10 }}>
        {CLUSTER_CARDS.map((card) => <ClusterCard key={card.cluster} card={card} onClick={() => onClusterClick(card.cluster)} />)}
      </div>
    </div>
  );
}

// ─── Combined Export ────────────────────────────────────────────────────────

export function ClusterAndDimensions({ onClusterClick }: { onClusterClick: (cluster: string) => void }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <CompetitiveBreakdown />
      <ClusterBreakdown onClusterClick={onClusterClick} />
    </div>
  );
}
