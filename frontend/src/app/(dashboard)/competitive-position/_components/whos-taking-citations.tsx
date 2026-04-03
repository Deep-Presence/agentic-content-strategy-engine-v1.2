'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { COMPETITORS, MINDSHARE, AUTHORITY } from './data';
import { BrandLogo } from './brand-logo';

function TierSection({
  title,
  subtitle,
  count,
  percent,
  children,
  defaultOpen = true,
  delay,
}: {
  title: string;
  subtitle: string;
  count: number;
  percent: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
  delay: number;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div style={{ animation: `fadeUp 200ms ease ${delay}ms both` }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 14px',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          textAlign: 'left',
          borderBottom: '1px solid var(--border-subtle)',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        {open ? (
          <ChevronDown size={14} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
        ) : (
          <ChevronRight size={14} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
        )}
        <span style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
          {title}
        </span>
        <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
          — {count} brands, {percent}% of competitive citations
        </span>
      </button>
      {open && (
        <div style={{ paddingBottom: '4px' }}>
          <p style={{ fontSize: '11px', color: 'var(--text-tertiary)', padding: '6px 14px 4px 36px' }}>
            {subtitle}
          </p>
          {children}
        </div>
      )}
    </div>
  );
}

function CompetitorRow({
  domain,
  name,
  sov,
  citations,
  delta,
  label,
  delay,
}: {
  domain: string;
  name: string;
  sov: number;
  citations: number;
  delta?: number;
  label?: string;
  delay: number;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '6px 14px 6px 36px',
        borderBottom: '1px solid var(--border-subtle)',
        transition: 'background 0.15s',
        animation: `fadeUp 200ms ease ${delay}ms both`,
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <BrandLogo domain={domain} size={16} />
      <span style={{ fontSize: '13px', color: 'var(--text-primary)', fontFamily: 'var(--font-display)', minWidth: '120px' }}>
        {domain}
      </span>
      <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', minWidth: '50px' }}>
        {sov}%
      </span>
      <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', minWidth: '90px' }}>
        {citations.toLocaleString()} citations
      </span>
      {delta !== undefined && (
        <span
          style={{
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            color: delta > 0 ? 'var(--success)' : delta < 0 ? 'var(--error)' : 'var(--text-tertiary)',
          }}
        >
          {delta > 0 ? '+' : ''}{delta} this month
        </span>
      )}
      {label && (
        <span style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
          {label}
        </span>
      )}
    </div>
  );
}

export function WhosTakingCitations() {
  const directTotal = COMPETITORS.reduce((sum, c) => sum + c.sov, 0);
  const mindshareTotal = MINDSHARE.reduce((sum, c) => sum + c.sov, 0);
  const authorityTotal = AUTHORITY.reduce((sum, c) => sum + c.sov, 0);

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: '6px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
          Who&apos;s Taking Your Citations
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          Not all competitors are direct — mind share and authority sources also occupy citation slots
        </p>
      </div>

      {/* Direct Competitors */}
      <TierSection
        title="Direct Competitors"
        subtitle="Same product category — these compete head-to-head with you"
        count={COMPETITORS.length}
        percent={Math.round(directTotal)}
        delay={0}
      >
        {COMPETITORS.map((c, i) => (
          <CompetitorRow
            key={c.domain}
            domain={c.domain}
            name={c.name}
            sov={c.sov}
            citations={c.citations}
            delta={c.delta}
            delay={i * 30}
          />
        ))}
      </TierSection>

      {/* Mind Share */}
      <TierSection
        title="Mind Share"
        subtitle="Different product, same queries — they appear in the same AI responses as you"
        count={MINDSHARE.length}
        percent={Math.round(mindshareTotal)}
        defaultOpen={false}
        delay={100}
      >
        {MINDSHARE.map((c, i) => (
          <CompetitorRow
            key={c.domain}
            domain={c.domain}
            name={c.name}
            sov={c.sov}
            citations={c.citations}
            label={c.label}
            delay={i * 30}
          />
        ))}
      </TierSection>

      {/* Authority Sources */}
      <TierSection
        title="Authority Sources"
        subtitle="Government, educational, and institutional sources that AI engines trust"
        count={AUTHORITY.length}
        percent={Math.round(authorityTotal)}
        defaultOpen={false}
        delay={200}
      >
        {AUTHORITY.map((c, i) => (
          <CompetitorRow
            key={c.domain}
            domain={c.domain}
            name={c.name}
            sov={c.sov}
            citations={c.citations}
            label={c.label}
            delay={i * 30}
          />
        ))}
      </TierSection>

      {/* Insight Card */}
      <div
        style={{
          background: 'var(--surface)',
          borderLeft: '3px solid var(--accent)',
          padding: 14,
          borderRadius: 'var(--radius-sm)',
          marginTop: 12,
          margin: '14px',
        }}
      >
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', lineHeight: 1.5 }}>
          Authority sources like government sites and academic journals are gaining citation share. Focus on creating authoritative how-to content rather than reference material to defend your position.
        </p>
      </div>
    </div>
  );
}
