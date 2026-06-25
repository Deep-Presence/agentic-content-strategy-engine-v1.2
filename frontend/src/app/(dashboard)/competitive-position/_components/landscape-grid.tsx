'use client';

import { COMPETITORS, MINDSHARE, AUTHORITY, type LandscapeBrand } from './data';
import { BrandLogo } from './brand-logo';
import { Sparkline } from './sparkline';

interface CategorySectionProps {
  title: string;
  description: string;
  percent: number;
  brands: (LandscapeBrand & { delta?: number; sparkline?: number[] })[];
  showDelta?: boolean;
  onBrandClick: (domain: string) => void;
}

function CategorySection({ title, description, percent, brands, showDelta, onBrandClick }: CategorySectionProps) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{title}</p>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, maxWidth: 600 }}>{description}</p>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <span style={{ fontSize: 22, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{percent}%</span>
            <p style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>of all citations</p>
          </div>
        </div>
      </div>

      {/* Table header */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 60px 56px 48px', padding: '0 16px', height: 28, alignItems: 'center', borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
        <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>Brand</span>
        <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', textAlign: 'right' }}>SOV</span>
        <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', textAlign: 'center' }}>Trend</span>
        {showDelta && <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', textAlign: 'right' }}>Delta</span>}
        {!showDelta && <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', textAlign: 'right' }}>Type</span>}
      </div>

      {brands.map((b, i) => (
        <div
          key={b.domain}
          onClick={() => onBrandClick(b.domain)}
          style={{
            display: 'grid', gridTemplateColumns: '1fr 60px 56px 48px', padding: '0 16px', height: 38, alignItems: 'center',
            borderBottom: i < brands.length - 1 ? '1px solid var(--border-subtle)' : 'none',
            cursor: 'pointer', transition: 'background 0.12s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <BrandLogo domain={b.domain} size={16} />
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{b.domain}</span>
          </div>
          <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', textAlign: 'right' }}>{b.sov}%</span>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            {b.sparkline ? <Sparkline data={b.sparkline} color={b.delta && b.delta > 0 ? '#E5484D' : b.delta && b.delta < 0 ? '#34B27B' : '#889096'} width={40} height={14} /> : <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>-</span>}
          </div>
          {showDelta && b.delta !== undefined && (
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: b.delta > 0 ? '#E5484D' : b.delta < 0 ? '#34B27B' : 'var(--text-tertiary)', textAlign: 'right' }}>{b.delta > 0 ? '+' : ''}{b.delta}</span>
          )}
          {!showDelta && b.label && <span style={{ fontSize: 9, color: 'var(--text-tertiary)', textAlign: 'right' }}>{b.label}</span>}
        </div>
      ))}
    </div>
  );
}

export function LandscapeGrid({ onBrandClick }: { onBrandClick: (domain: string) => void }) {
  const directPct = Math.round(COMPETITORS.reduce((s, c) => s + c.sov, 0));
  const mindPct = Math.round(MINDSHARE.reduce((s, c) => s + c.sov, 0));
  const authPct = Math.round(AUTHORITY.reduce((s, c) => s + c.sov, 0));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Competitive Landscape</p>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>All brands competing for citation slots in your space. Click any brand for full profile.</p>
      </div>

      <CategorySection
        title="Direct Competitors"
        description="Brands in the same product category competing for the same queries and citations."
        percent={directPct}
        brands={COMPETITORS.map((c) => ({ domain: c.domain, name: c.name, sov: c.sov, citations: c.citations, delta: c.delta, category: 'direct' as const, sparkline: c.sparkline }))}
        showDelta
        onBrandClick={onBrandClick}
      />

      <CategorySection
        title="Mind Share Competitors"
        description="Review sites, media outlets, and directories that appear in the same AI responses. Not direct competitors, but they occupy citation slots you could fill."
        percent={mindPct}
        brands={MINDSHARE}
        onBrandClick={onBrandClick}
      />

      <CategorySection
        title="Authority Sources"
        description="Government, academic, and institutional sources that AI engines trust. You compete alongside them, not against them. Create practitioner content that gets cited next to these sources."
        percent={authPct}
        brands={AUTHORITY}
        onBrandClick={onBrandClick}
      />
    </div>
  );
}
