'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Swords, Eye, BookOpen } from 'lucide-react';
import { COMPETITORS, MINDSHARE, AUTHORITY, type LandscapeBrand } from './data';
import { BrandLogo } from './brand-logo';
import { Sparkline } from './sparkline';

// Sample queries per category (for expandable detail)
const CATEGORY_QUERIES: Record<string, string[]> = {
  direct: ['best AI app builder 2026', 'no-code AI app builder', 'AI app builder pricing', 'vibe coding tools comparison'],
  mindshare: ['AI app builder reviews', 'top no-code platforms for startups', 'lovable vs bolt.new comparison', 'AI code generation tools list'],
  authority: ['AI code generation security risks', 'RBAC in AI-generated applications', 'AI app builder data privacy', 'enterprise software compliance'],
};

function Card({ title, percent, icon, brands, sparklines, showDelta, categoryKey }: {
  title: string; percent: number; icon: React.ReactNode; brands: (LandscapeBrand & { delta?: number; sparkline?: number[] })[]; sparklines?: boolean; showDelta?: boolean; categoryKey: string;
}) {
  const [showQueries, setShowQueries] = useState(false);
  const queries = CATEGORY_QUERIES[categoryKey] || [];

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg)' }}>
        <div style={{ color: 'var(--text-tertiary)' }}>{icon}</div>
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{title}</span>
        </div>
        <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{percent}%</span>
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>of citations</span>
      </div>

      {brands.map((b, i) => (
        <div key={b.domain} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderBottom: i < brands.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
          <BrandLogo domain={b.domain} size={14} />
          <span style={{ fontSize: 11, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.domain}</span>
          {sparklines && b.sparkline && <Sparkline data={b.sparkline} color={b.delta && b.delta > 0 ? 'var(--error)' : b.delta && b.delta < 0 ? 'var(--success)' : 'var(--text-tertiary)'} width={32} height={12} />}
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>{b.sov}%</span>
          {showDelta && b.delta !== undefined && (
            <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: b.delta > 0 ? 'var(--error)' : b.delta < 0 ? 'var(--success)' : 'var(--text-tertiary)', minWidth: 24, textAlign: 'right' }}>{b.delta > 0 ? '+' : ''}{b.delta}</span>
          )}
          {!showDelta && b.label && <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{b.label}</span>}
        </div>
      ))}

      {/* Expandable queries */}
      <button
        onClick={() => setShowQueries(!showQueries)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', border: 'none', borderTop: '1px solid var(--border-subtle)', background: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)', fontSize: 10, fontWeight: 500, transition: 'background 0.15s' }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        {showQueries ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        Queries they appear in ({queries.length})
      </button>
      {showQueries && (
        <div style={{ padding: '0 12px 8px' }}>
          {queries.map((q) => (
            <p key={q} style={{ fontSize: 10, color: 'var(--text-secondary)', padding: '2px 0', borderBottom: '1px solid var(--border-subtle)' }}>&ldquo;{q}&rdquo;</p>
          ))}
        </div>
      )}
    </div>
  );
}

export function LandscapeGrid() {
  const directPercent = Math.round(COMPETITORS.reduce((s, c) => s + c.sov, 0));
  const mindPercent = Math.round(MINDSHARE.reduce((s, c) => s + c.sov, 0));
  const authPercent = Math.round(AUTHORITY.reduce((s, c) => s + c.sov, 0));

  return (
    <div>
      <div style={{ marginBottom: 10 }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Competitive Landscape</p>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Who occupies citation slots in your space — and how to compete with each type</p>
      </div>

      <div className="grid grid-cols-3" style={{ gap: 12 }}>
        <Card
          title="Direct Competitors"
          percent={directPercent}
          icon={<Swords size={13} />}
          brands={COMPETITORS.map((c) => ({ domain: c.domain, name: c.name, sov: c.sov, citations: c.citations, delta: c.delta, category: 'direct' as const, sparkline: c.sparkline }))}
          sparklines
          showDelta
          categoryKey="direct"
        />
        <Card
          title="Mind Share"
          percent={mindPercent}
          icon={<Eye size={13} />}
          brands={MINDSHARE}
          categoryKey="mindshare"
        />
        <Card
          title="Authority Sources"
          percent={authPercent}
          icon={<BookOpen size={13} />}
          brands={AUTHORITY}
          categoryKey="authority"
        />
      </div>

      {/* Strategy Insight Panel */}
      <div style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', background: 'var(--accent-subtle)' }}>
          <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)', fontFamily: 'var(--font-display)' }}>Strategy per Category</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 0 }}>
          {[
            { title: 'Direct Competitors', pct: directPercent, color: 'var(--error)', text: 'Fight with better content — longer pages, FAQ sections, structured data, fresher updates. These are head-to-head battles you can win.' },
            { title: 'Mind Share', pct: mindPercent, color: 'var(--warning)', text: 'Get listed and well-reviewed on G2, Capterra, Product Hunt. You can\'t outrank review aggregators — but you can make sure they rank you favorably.' },
            { title: 'Authority Sources', pct: authPercent, color: 'var(--text-secondary)', text: 'Don\'t compete with CMS.gov on reference data. Create practitioner guides that AI engines cite alongside authoritative sources.' },
          ].map((s, i) => (
            <div key={s.title} style={{ padding: '10px 14px', borderRight: i < 2 ? '1px solid var(--border)' : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: s.color }} />
                <span style={{ fontSize: 10, fontWeight: 600, color: s.color }}>{s.title} · {s.pct}%</span>
              </div>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{s.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
