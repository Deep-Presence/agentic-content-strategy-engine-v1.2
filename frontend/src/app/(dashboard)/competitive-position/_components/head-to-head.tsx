'use client';

import { useState } from 'react';
import { Pin, ChevronDown, ChevronRight } from 'lucide-react';
import { COMPETITORS, MINDSHARE, AUTHORITY, YOUR_DATA, type LandscapeBrand } from './data';
import { BrandLogo } from './brand-logo';
import { Sparkline } from './sparkline';

function barColor(rate: number) { return rate > 50 ? 'var(--success)' : rate >= 30 ? 'var(--warning)' : 'var(--error)'; }

// Build full brand list sorted by SOV
const ALL: (LandscapeBrand & { winRate?: number; sparkline?: number[]; delta?: number; categoryLabel: string })[] = [
  ...COMPETITORS.map((c) => ({ ...c, category: 'direct' as const, categoryLabel: 'Direct', winRate: c.winRate, sparkline: c.sparkline })),
  ...MINDSHARE.map((m) => ({ ...m, categoryLabel: 'Mind Share' })),
  ...AUTHORITY.map((a) => ({ ...a, categoryLabel: 'Authority' })),
].sort((a, b) => b.sov - a.sov);

export function HeadToHead({ onCompetitorClick }: { onCompetitorClick: (domain: string) => void }) {
  const [pinned, setPinned] = useState<Set<string>>(new Set(ALL.slice(0, 6).map((b) => b.domain)));
  const [showTable, setShowTable] = useState(false);

  const togglePin = (domain: string) => {
    setPinned((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else if (next.size < 10) next.add(domain);
      return next;
    });
  };

  const pinnedBrands = ALL.filter((b) => pinned.has(b.domain));
  const unpinnedBrands = ALL.filter((b) => !pinned.has(b.domain));

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div>
          <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Head-to-Head</p>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Your SOV vs each competitor. Pin up to 10. Click for full profile.</p>
        </div>
        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{pinned.size}/10 pinned</span>
      </div>

      {/* Pinned cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
        {pinnedBrands.map((b) => {
          const sovMax = Math.max(YOUR_DATA.sov, b.sov);
          return (
            <div key={b.domain} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '14px', transition: 'border-color 0.15s' }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-strong)')} onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}>
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <BrandLogo domain={b.domain} size={18} />
                  <div>
                    <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{b.name}</p>
                    <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 3, background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-tertiary)', fontWeight: 500 }}>{b.categoryLabel}</span>
                  </div>
                </div>
                <button onClick={(e) => { e.stopPropagation(); togglePin(b.domain); }} style={{ width: 22, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none', background: 'var(--accent-subtle)', borderRadius: 4, cursor: 'pointer', color: 'var(--accent)' }}>
                  <Pin size={10} />
                </button>
              </div>

              {/* SOV comparison */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#5BA4C4' }}>{YOUR_DATA.sov}%</span>
                  <span style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{b.sov}%</span>
                </div>
                <div style={{ display: 'flex', height: 5, gap: 2, borderRadius: 9999, overflow: 'hidden' }}>
                  <div style={{ width: `${(YOUR_DATA.sov / sovMax) * 100}%`, background: '#5BA4C4', borderRadius: '9999px 0 0 9999px' }} />
                  <div style={{ width: `${(b.sov / sovMax) * 100}%`, background: '#D7DBDF', borderRadius: '0 9999px 9999px 0' }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
                  <span style={{ fontSize: 8, color: '#5BA4C4' }}>You</span>
                  <span style={{ fontSize: 8, color: 'var(--text-tertiary)' }}>SOV</span>
                  <span style={{ fontSize: 8, color: 'var(--text-tertiary)' }}>{b.name}</span>
                </div>
              </div>

              {/* Sparkline + action */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: 8 }}>
                {b.sparkline ? <Sparkline data={b.sparkline} color={b.delta && b.delta > 0 ? '#E5484D' : '#34B27B'} width={48} height={16} /> : <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>No trend</span>}
                <button onClick={() => onCompetitorClick(b.domain)} style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 500, background: 'none', border: 'none', cursor: 'pointer' }}>Details</button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Expandable table for remaining brands */}
      {unpinnedBrands.length > 0 && (
        <div style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
          <button onClick={() => setShowTable(!showTable)} style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 6, padding: '10px 16px',
            border: 'none', background: 'var(--bg)', cursor: 'pointer', transition: 'background 0.12s',
          }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg)')}>
            {showTable ? <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} /> : <ChevronRight size={12} style={{ color: 'var(--text-tertiary)' }} />}
            <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>{unpinnedBrands.length} more brands</span>
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Click to pin any to cards above</span>
          </button>
          {showTable && unpinnedBrands.map((b, i) => (
            <div key={b.domain} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', height: 36, borderTop: '1px solid var(--border-subtle)' }}>
              <button onClick={() => togglePin(b.domain)} style={{ width: 20, height: 20, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border)', borderRadius: 4, background: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
                <Pin size={9} />
              </button>
              <BrandLogo domain={b.domain} size={14} />
              <span style={{ fontSize: 12, color: 'var(--text-primary)', flex: 1 }}>{b.domain}</span>
              <span style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}>{b.categoryLabel}</span>
              <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', minWidth: 40, textAlign: 'right' }}>{b.sov}%</span>
              <button onClick={() => onCompetitorClick(b.domain)} style={{ fontSize: 10, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer' }}>View</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
