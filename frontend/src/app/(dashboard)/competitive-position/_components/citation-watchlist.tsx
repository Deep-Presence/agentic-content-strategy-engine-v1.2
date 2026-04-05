'use client';

import { useState } from 'react';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import { CITATIONS, ENGINE_DOMAINS, type CitationItem } from './data';
import { BrandLogo } from './brand-logo';

const S: Record<string, { label: string; color: string }> = {
  lost: { label: 'Lost', color: 'var(--error)' }, at_risk: { label: 'At Risk', color: 'var(--warning)' },
  stable: { label: 'Stable', color: 'var(--success)' }, never_had: { label: 'New Opp', color: 'var(--text-tertiary)' },
};

const P: Record<string, { bg: string; color: string }> = {
  high: { bg: 'var(--success-subtle)', color: 'var(--success)' }, medium: { bg: 'var(--warning-subtle)', color: 'var(--warning)' }, low: { bg: 'var(--error-subtle)', color: 'var(--error)' },
};

export function CitationWatchlist({ onCitationClick }: { onCitationClick: (item: CitationItem) => void }) {
  const [showStable, setShowStable] = useState(false);
  const lost = CITATIONS.filter((c) => c.status === 'lost');
  const atRisk = CITATIONS.filter((c) => c.status === 'at_risk');
  const stable = CITATIONS.filter((c) => c.status === 'stable');
  const neverHad = CITATIONS.filter((c) => c.status === 'never_had');
  const actionable = [...lost, ...atRisk];

  return (
    <div>

      {/* Header */}
      <div style={{ display: 'grid', gridTemplateColumns: '50px 1fr 90px 80px 36px 56px 60px', padding: '0 14px', height: 26, alignItems: 'center', borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
        <TH>Status</TH><TH>Query</TH><TH>Competitor</TH><TH>Engine</TH><TH r>Age</TH><TH>Probability</TH><TH>Quick Fix</TH>
      </div>

      {/* Actionable rows */}
      {actionable.map((item) => (
        <div
          key={item.query}
          onClick={() => onCitationClick(item)}
          style={{
            display: 'grid', gridTemplateColumns: '50px 1fr 90px 80px 36px 56px 60px', padding: '0 14px', height: 36, alignItems: 'center',
            borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer', transition: 'background 0.12s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <span style={{ fontSize: 10, fontWeight: 600, color: S[item.status].color }}>{S[item.status].label}</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.query}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 3, overflow: 'hidden' }}>
            {item.competitor ? <><BrandLogo domain={item.competitor} size={12} /><span style={{ fontSize: 10, color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.competitor}</span></> : <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>—</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            {item.engine && <BrandLogo domain={ENGINE_DOMAINS[item.engine] || ''} size={11} />}
            <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{item.engine || '—'}</span>
          </div>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', textAlign: 'right' }}>{item.daysAgo ? `${item.daysAgo}d` : '—'}</span>
          {item.recaptureProbability ? (
            <span style={{ fontSize: 8, fontWeight: 600, padding: '1px 5px', borderRadius: 3, background: P[item.recaptureProbability].bg, color: P[item.recaptureProbability].color, textTransform: 'uppercase' }}>{item.recaptureProbability}</span>
          ) : <span />}
          <span style={{ fontSize: 9, color: 'var(--accent)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.quickFix || '—'}</span>
        </div>
      ))}

      {/* Stable collapsed */}
      <div onClick={() => setShowStable(!showStable)} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '0 14px', height: 30, borderBottom: neverHad.length > 0 || showStable ? '1px solid var(--border-subtle)' : 'none', cursor: 'pointer' }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
        {showStable ? <ChevronDown size={10} style={{ color: 'var(--text-tertiary)' }} /> : <ChevronRight size={10} style={{ color: 'var(--text-tertiary)' }} />}
        <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--success)' }} />
        <span style={{ fontSize: 10, color: 'var(--success)', fontWeight: 500 }}>{stable.length} stable citations — no action needed</span>
      </div>
      {showStable && stable.map((item) => (
        <div key={item.query} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 14px 0 28px', height: 26, borderBottom: '1px solid var(--border-subtle)' }}>
          <Check size={10} strokeWidth={2} style={{ color: 'var(--success)' }} /><span style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1 }}>{item.query}</span><span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{item.detail}</span>
        </div>
      ))}

      {/* Never had */}
      {neverHad.map((item) => (
        <div key={item.query} style={{ display: 'grid', gridTemplateColumns: '50px 1fr 90px 80px 36px 56px 60px', padding: '0 14px', height: 34, alignItems: 'center', borderBottom: '1px solid var(--border-subtle)' }}>
          <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-tertiary)' }}>New</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.query}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>{item.competitor && <><BrandLogo domain={item.competitor} size={12} /><span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{item.competitor}</span></>}</div>
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{item.engines ? `${item.engines} engines` : '—'}</span>
          <span /><span /><span style={{ fontSize: 9, color: 'var(--accent)', cursor: 'pointer' }}>Create →</span>
        </div>
      ))}
    </div>
  );
}

function TH({ children, r }: { children: React.ReactNode; r?: boolean }) {
  return <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', textAlign: r ? 'right' : 'left' }}>{children}</span>;
}
