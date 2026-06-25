'use client';

import { useState } from 'react';
import { Check, X as XIcon } from 'lucide-react';
import { BrandLogo } from './brand-logo';
import { SlideDrawer } from './slide-drawer';
import { PLATFORMS, PLATFORM_DRAWER_DATA, type PlatformIntel } from './data';
import { AreaChart, Area, ResponsiveContainer, XAxis, Tooltip } from 'recharts';

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const h = 28;
  const w = 100;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`).join(' ');
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="mt-1">
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

function PlatformCard({ platform, onClick, index }: { platform: PlatformIntel; onClick: () => void; index: number }) {
  return (
    <div
      className="cursor-pointer transition-colors duration-150 rounded-[var(--radius-md)]"
      style={{
        border: '1px solid var(--border)',
        borderTop: platform.isTop ? `2px solid ${platform.color}` : undefined,
        background: 'var(--surface)',
        padding: 14,
        animation: `fadeUp 250ms ease ${index * 50}ms both`,
      }}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-strong)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <BrandLogo domain={platform.domain} size={16} />
          <span className="text-[13px] font-semibold" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)' }}>
            {platform.name}
          </span>
        </div>
        {platform.isTop && (
          <span
            className="text-[9px] uppercase font-semibold px-1.5 py-0.5 rounded-[3px]"
            style={{ background: platform.color, color: '#fff', letterSpacing: '0.06em' }}
          >
            TOP
          </span>
        )}
      </div>

      {/* Citations */}
      <div
        className="text-[10px] uppercase font-semibold tracking-[0.05em]"
        style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}
      >
        Citations
      </div>
      <div
        className="text-[26px] font-bold"
        style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', lineHeight: 1.1 }}
      >
        {platform.citations}
      </div>

      {/* Stats */}
      <div className="mt-2 space-y-1">
        {[
          { label: 'SOV', value: `${platform.sov}%` },
          { label: 'AVG RANK', value: platform.avgRank.toFixed(1) },
          { label: 'COVERAGE', value: `${platform.coverage}%` },
        ].map((stat) => (
          <div key={stat.label} className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-semibold tracking-[0.05em]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>
              {stat.label}
            </span>
            <span className="text-[13px] font-medium" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {stat.value}
            </span>
          </div>
        ))}
      </div>

      {/* Sentiment */}
      <div className="mt-2">
        <span className="text-[10px] uppercase font-semibold tracking-[0.05em]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-tertiary)' }}>
          Sentiment
        </span>
        <div
          className="text-[12px] font-medium mt-0.5"
          style={{ fontFamily: 'var(--font-body)', color: platform.sentiment === 'Positive' ? 'var(--success)' : 'var(--text-secondary)' }}
        >
          {platform.sentiment}
        </div>
      </div>

      {/* Sparkline */}
      <Sparkline data={platform.sparklineData} color={platform.color} />

      {/* Strengths/Weaknesses */}
      <div className="mt-2 space-y-1">
        <div className="flex items-start gap-1">
          <Check size={11} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--success)' }} />
          <span className="text-[11px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--success)' }}>
            {platform.strength}
          </span>
        </div>
        <div className="flex items-start gap-1">
          <XIcon size={11} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--warning)' }} />
          <span className="text-[11px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--warning)' }}>
            {platform.weakness}
          </span>
        </div>
      </div>
    </div>
  );
}

function PlatformDrawerContent({ platform }: { platform: PlatformIntel }) {
  const detail = PLATFORM_DRAWER_DATA[platform.name];
  if (!detail) return null;

  const trendData = platform.sparklineData.map((v, i) => ({ day: i + 1, citations: v }));

  return (
    <div className="space-y-5">
      {/* Summary strip */}
      <div className="flex items-center gap-4 text-[13px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
        <span><strong style={{ color: 'var(--text-primary)' }}>{platform.citations}</strong> citations</span>
        <span><strong style={{ color: 'var(--text-primary)' }}>{platform.sov}%</strong> SOV</span>
        <span>Avg Rank <strong style={{ color: 'var(--text-primary)' }}>{platform.avgRank}</strong></span>
        <span><strong style={{ color: 'var(--text-primary)' }}>{platform.coverage}%</strong> Coverage</span>
      </div>

      {/* Citation Trend */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Citation Trend (30 days)
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={trendData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`grad-${platform.name}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={platform.color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={platform.color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="day" tick={{ fontSize: 10, fontFamily: 'var(--font-mono)', fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={false} interval={6} />
            <Tooltip
              contentStyle={{ background: 'var(--surface-overlay)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', fontSize: 11, fontFamily: 'var(--font-body)' }}
            />
            <Area type="monotone" dataKey="citations" stroke={platform.color} fill={`url(#grad-${platform.name})`} strokeWidth={1.5} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Top Queries */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Top Queries on {platform.name} ({detail.queries.length})
        </div>
        {detail.queries.map((q, i) => (
          <div
            key={i}
            className="flex items-center justify-between py-1.5"
            style={{ borderBottom: '1px solid var(--border-subtle)' }}
          >
            <span className="text-[13px] truncate" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)' }}>
              &quot;{q.query}&quot;
            </span>
            <div className="flex items-center gap-3 flex-shrink-0">
              <span className="text-[12px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                {q.citations} citations
              </span>
              {q.rank ? (
                <span className="text-[12px] font-medium" style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                  You: #{q.rank}
                </span>
              ) : (
                <span className="text-[12px] font-medium" style={{ fontFamily: 'var(--font-mono)', color: 'var(--error)' }}>
                  Not cited
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Top URLs */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Top Cited URLs on {platform.name}
        </div>
        {detail.urls.map((u, i) => (
          <div
            key={i}
            className="flex items-center justify-between py-1.5"
            style={{ borderBottom: '1px solid var(--border-subtle)' }}
          >
            <span className="text-[13px] truncate" style={{ fontFamily: 'var(--font-body)', color: 'var(--accent)' }}>
              {u.url}
            </span>
            <span className="text-[12px] flex-shrink-0" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {u.citations} citations
            </span>
          </div>
        ))}
      </div>

      {/* Competitor Performance */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Competitor Performance on {platform.name}
        </div>
        {detail.competitors.map((c, i) => (
          <div key={i} className="flex items-center gap-2 py-1.5" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <span className="text-[11px] w-[14px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{i + 1}.</span>
            <BrandLogo domain={c.domain} size={14} />
            <span className="text-[13px] flex-1" style={{ fontFamily: 'var(--font-body)', color: c.name === 'You' ? 'var(--accent)' : 'var(--text-primary)', fontWeight: c.name === 'You' ? 500 : 400 }}>
              {c.name}
            </span>
            <span className="text-[13px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{c.sov}%</span>
            <div className="w-[80px] h-[6px] rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
              <div className="h-full rounded-full" style={{ width: `${(c.sov / 50) * 100}%`, background: c.name === 'You' ? 'var(--accent)' : 'var(--text-tertiary)' }} />
            </div>
          </div>
        ))}
      </div>

      {/* Structural Preferences */}
      <div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mb-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          What {platform.name} Prefers (structural signals)
        </div>
        <div className="space-y-1.5 text-[13px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          <div>FAQ sections: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{detail.prefs.faqSections}%</span> of cited content has this</div>
          <div>Word count: average <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{detail.prefs.avgWordCount.toLocaleString()}</span> words</div>
          <div>Comparison tables: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{detail.prefs.comparisonTables}%</span> of cited content</div>
          <div>External citations: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{detail.prefs.externalCitations}%</span> of cited content</div>
        </div>
        <div className="mt-3 p-2.5 rounded-[var(--radius-sm)]" style={{ background: 'var(--accent-subtle)', border: '1px solid var(--border-subtle)' }}>
          <div className="text-[13px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)' }}>
            Your content scores: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{detail.prefs.yourScore}/100</span> for {platform.name}&apos;s preferences
          </div>
          <div className="text-[12px] mt-1" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
            Main gaps: {detail.prefs.mainGaps.join(', ')}
          </div>
        </div>
      </div>

      {/* Strengths & Weaknesses */}
      <div className="space-y-2">
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em]" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Strengths
        </div>
        <div className="flex items-start gap-1.5">
          <Check size={13} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--success)' }} />
          <span className="text-[13px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--success)' }}>{platform.strength}</span>
        </div>
        <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mt-2" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}>
          Weaknesses
        </div>
        <div className="flex items-start gap-1.5">
          <XIcon size={13} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--error)' }} />
          <span className="text-[13px]" style={{ fontFamily: 'var(--font-body)', color: 'var(--error)' }}>{platform.weakness}</span>
        </div>
      </div>
    </div>
  );
}

export function PlatformIntelligence() {
  const [selected, setSelected] = useState<PlatformIntel | null>(null);

  return (
    <div id="platform-intelligence">
      <h2 className="text-[16px] font-semibold mb-2" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
        Platform Intelligence
      </h2>
      <div className="grid gap-[10px]" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
        {PLATFORMS.map((p, i) => (
          <PlatformCard key={p.name} platform={p} onClick={() => setSelected(p)} index={i} />
        ))}
      </div>

      <SlideDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.name} — Detailed Intelligence` : ''}
        subtitle={selected ? `${selected.citations} citations across ${selected.topQueries} tracked queries` : ''}
      >
        {selected && <PlatformDrawerContent platform={selected} />}
      </SlideDrawer>
    </div>
  );
}
