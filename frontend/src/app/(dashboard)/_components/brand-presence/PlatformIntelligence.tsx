'use client';

import { useState, useMemo } from 'react';
import type { DayData } from './mock-data';
import { PLATFORMS } from './mock-data';
import { SlideDrawer } from './SlideDrawer';

interface PlatformIntelligenceProps {
  data: DayData[];
}

function BrandLogo({ domain, size = 16 }: { domain: string; size?: number }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 3 }}
      onError={(e) => {
        const target = e.target as HTMLImageElement;
        if (!target.dataset.fallback) {
          target.dataset.fallback = '1';
          target.src = `https://logo.clearbit.com/${domain}`;
        }
      }}
    />
  );
}

function Sparkline({ values, color, width = 80, height = 24 }: { values: number[]; color: string; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface PlatformStat {
  totalCitations: number;
  sov: number;
  avgRank: number;
  coverage: number;
  sentiment: string;
  sparklineData: number[];
  positive: string;
  negative: string;
}

const PLATFORM_INSIGHTS: Record<string, { positive: string; negative: string; avgRank: number; coverage: number }> = {
  chatgpt: { positive: 'Best reach (36.8%)', negative: 'Low security coverage', avgRank: 2.1, coverage: 78 },
  claude: { positive: 'Highest accuracy', negative: 'Fewer total queries', avgRank: 2.4, coverage: 72 },
  perplexity: { positive: 'Fastest citation growth', negative: 'Inconsistent ranking', avgRank: 2.8, coverage: 68 },
  google: { positive: 'Best rank (2.1)', negative: 'Limited query diversity', avgRank: 2.1, coverage: 82 },
  gemini: { positive: 'Growing coverage', negative: 'Lowest citation volume', avgRank: 3.2, coverage: 65 },
};

const PLATFORM_DRAWER_INSIGHTS: Record<string, { working: string[]; improve: string[] }> = {
  chatgpt: { working: ['Best reach — 36.8% of citations', 'Strong branded query ranking', '78% coverage of tracked queries'], improve: ['Low security query coverage', 'Not citing your API docs', 'No FAQ sections on cited pages'] },
  claude: { working: ['Highest accuracy citations', 'Best technical depth', 'Growing developer audience'], improve: ['Fewer total queries tracked', 'Low comparison content ranking', 'Missing enterprise use cases'] },
  perplexity: { working: ['Fastest citation growth', 'Strong for comparison queries', 'Good source attribution'], improve: ['Inconsistent ranking positions', 'Limited branded query coverage', 'Few how-to citations'] },
  google: { working: ['Best average rank (#2.1)', 'Strong snippet presence', 'Good query diversity'], improve: ['Limited query diversity', 'Low blog content citations', 'Weak competitor comparison coverage'] },
  gemini: { working: ['Growing coverage steadily', 'Good technical documentation citations', 'Improving sentiment'], improve: ['Lowest citation volume overall', 'Poor branded query ranking', 'Limited content type diversity'] },
};

const PLATFORM_DRAWER_QUERIES: Record<string, { query: string; citations: number; rank: string }[]> = {
  chatgpt: [
    { query: 'AI app builder comparison', citations: 14, rank: '#1' },
    { query: 'lovable vs cursor', citations: 9, rank: '#2' },
    { query: 'best no-code AI platform', citations: 7, rank: '#1' },
    { query: 'enterprise AI app builder', citations: 5, rank: 'Not cited' },
    { query: 'vibe coding tools', citations: 4, rank: '#3' },
  ],
  claude: [
    { query: 'AI code generation tools', citations: 11, rank: '#2' },
    { query: 'lovable dev review', citations: 8, rank: '#1' },
    { query: 'best app builder 2026', citations: 6, rank: '#3' },
    { query: 'no-code vs low-code', citations: 4, rank: '#2' },
    { query: 'AI development platforms', citations: 3, rank: 'Not cited' },
  ],
  perplexity: [
    { query: 'lovable alternatives', citations: 10, rank: '#1' },
    { query: 'AI app development', citations: 7, rank: '#2' },
    { query: 'best coding AI tools', citations: 5, rank: '#3' },
    { query: 'no-code AI builder review', citations: 4, rank: '#1' },
    { query: 'enterprise software builder', citations: 3, rank: 'Not cited' },
  ],
  google: [
    { query: 'AI app builder', citations: 12, rank: '#1' },
    { query: 'lovable dev pricing', citations: 8, rank: '#1' },
    { query: 'no-code platform comparison', citations: 6, rank: '#2' },
    { query: 'AI development tools 2026', citations: 5, rank: '#2' },
    { query: 'build app with AI', citations: 4, rank: '#3' },
  ],
  gemini: [
    { query: 'AI code tools comparison', citations: 6, rank: '#3' },
    { query: 'lovable vs bolt', citations: 5, rank: '#2' },
    { query: 'best AI builders', citations: 4, rank: '#3' },
    { query: 'no-code AI platform', citations: 3, rank: 'Not cited' },
    { query: 'rapid app development AI', citations: 2, rank: '#4' },
  ],
};

const PLATFORM_DRAWER_URLS: Record<string, { url: string; citations: number }[]> = {
  chatgpt: [{ url: '/blog/ai-app-builder-comparison', citations: 23 }, { url: '/blog/lovable-vs-cursor', citations: 12 }, { url: '/docs/getting-started', citations: 8 }],
  claude: [{ url: '/blog/ai-code-generation-guide', citations: 18 }, { url: '/blog/lovable-review-2026', citations: 11 }, { url: '/docs/api-reference', citations: 7 }],
  perplexity: [{ url: '/blog/lovable-alternatives-2026', citations: 15 }, { url: '/blog/ai-app-development', citations: 10 }, { url: '/pricing', citations: 6 }],
  google: [{ url: '/blog/ai-app-builder-comparison', citations: 20 }, { url: '/pricing', citations: 9 }, { url: '/blog/no-code-comparison', citations: 7 }],
  gemini: [{ url: '/blog/ai-code-tools', citations: 10 }, { url: '/blog/lovable-vs-bolt', citations: 8 }, { url: '/docs/getting-started', citations: 5 }],
};

const PLATFORM_SCORES: Record<string, number> = {
  chatgpt: 72,
  claude: 65,
  perplexity: 58,
  google: 78,
  gemini: 45,
};

const PLATFORM_STRENGTH: Record<string, string> = {
  chatgpt: 'strongest',
  claude: 'second strongest',
  perplexity: 'third strongest',
  google: 'top-performing',
  gemini: 'weakest',
};

function computePlatformStats(data: DayData[]): Record<string, PlatformStat> {
  const stats: Record<string, PlatformStat> = {};
  const totalAllCitations = data.reduce((s, d) => s + d.citations, 0);

  PLATFORMS.forEach(p => {
    const platformCitations = data.map(d => d[p.key] as number);
    const total = platformCitations.reduce((s, v) => s + v, 0);
    const sov = (total / totalAllCitations) * 100;
    const insights = PLATFORM_INSIGHTS[p.key];

    stats[p.key] = {
      totalCitations: total,
      sov: Math.round(sov * 10) / 10,
      avgRank: insights.avgRank,
      coverage: insights.coverage,
      sentiment: 'Positive',
      sparklineData: platformCitations,
      positive: insights.positive,
      negative: insights.negative,
    };
  });

  return stats;
}

type SelectedPlatform = typeof PLATFORMS[number] | null;

function DrawerSparkline({ values, color, width = '100%', height = 140 }: { values: number[]; color: string; width?: string | number; height?: number }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const svgWidth = 400;

  const pathPoints = values.map((v, i) => {
    const x = (i / (values.length - 1)) * svgWidth;
    const y = height - 4 - ((v - min) / range) * (height - 8);
    return { x, y };
  });

  const linePath = pathPoints.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
  const areaPath = `${linePath} L${svgWidth},${height} L0,${height} Z`;

  return (
    <div style={{ width, height, borderRadius: 'var(--radius-sm)', overflow: 'hidden', border: '1px solid var(--border)', background: 'var(--bg)' }}>
      <svg width="100%" height={height} viewBox={`0 0 ${svgWidth} ${height}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.15" />
            <stop offset="100%" stopColor={color} stopOpacity="0.01" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#sparkGrad)" />
        <path d={linePath} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

function PlatformDrawerContent({ platform, stat }: { platform: typeof PLATFORMS[number]; stat: PlatformStat }) {
  const insights = PLATFORM_DRAWER_INSIGHTS[platform.key] || { working: [], improve: [] };
  const queries = PLATFORM_DRAWER_QUERIES[platform.key] || [];
  const urls = PLATFORM_DRAWER_URLS[platform.key] || [];
  const score = PLATFORM_SCORES[platform.key] || 50;
  const strength = PLATFORM_STRENGTH[platform.key] || 'moderate';
  const citationPct = stat.sov.toFixed(1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, paddingTop: 16 }}>
      {/* 1. Narrative sentence */}
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)', margin: 0, lineHeight: 1.5 }}>
        {platform.name} is your <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{strength}</span> platform — {citationPct}% of all citations come from here.
      </p>

      {/* 2. Stat strip */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          padding: '10px 14px',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--bg)',
          flexWrap: 'wrap',
        }}
      >
        {[
          { label: String(stat.totalCitations), suffix: ' citations' },
          { label: `${stat.sov}%`, suffix: ' SOV' },
          { label: `#${stat.avgRank}`, suffix: ' avg rank' },
          { label: `${stat.coverage}%`, suffix: ' coverage' },
        ].map((item, i, arr) => (
          <span key={item.suffix} style={{ display: 'inline-flex', alignItems: 'center', fontSize: 13, fontFamily: 'var(--font-display)' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{item.label}</span>
            <span style={{ color: 'var(--text-secondary)' }}>{item.suffix}</span>
            {i < arr.length - 1 && (
              <span style={{ margin: '0 8px', color: 'var(--text-tertiary)' }}>&middot;</span>
            )}
          </span>
        ))}
      </div>

      {/* 3. Citation trend sparkline */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)', marginBottom: 8 }}>
          Citation Trend
        </div>
        <DrawerSparkline values={stat.sparklineData} color={platform.color} />
      </div>

      {/* 4. Two-column summary: What's Working / Where to Improve */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--bg)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--success)', fontFamily: 'var(--font-display)', marginBottom: 8 }}>
            What&apos;s Working
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {insights.working.map((item, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', lineHeight: 1.4 }}>
                <span style={{ color: 'var(--success)', flexShrink: 0 }}>&#10003;</span>
                {item}
              </div>
            ))}
          </div>
        </div>
        <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--bg)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--warning)', fontFamily: 'var(--font-display)', marginBottom: 8 }}>
            Where to Improve
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {insights.improve.map((item, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', lineHeight: 1.4 }}>
                <span style={{ color: 'var(--warning)', flexShrink: 0 }}>&#10007;</span>
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 5. Top queries table */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)', marginBottom: 8 }}>
          Top Queries
        </div>
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
          {/* Header */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 80px', padding: '6px 12px', background: 'var(--bg)', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>Query</span>
            <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)', textAlign: 'right' }}>Citations</span>
            <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)', textAlign: 'right' }}>Rank</span>
          </div>
          {queries.map((q, i) => (
            <div
              key={i}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 80px 80px',
                padding: '6px 12px',
                borderBottom: i < queries.length - 1 ? '1px solid var(--border)' : 'none',
                background: 'var(--surface)',
              }}
            >
              <span className="truncate" style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{q.query}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', textAlign: 'right' }}>{q.citations}</span>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500, textAlign: 'right',
                color: q.rank === 'Not cited' ? 'var(--text-tertiary)' : q.rank === '#1' ? 'var(--success)' : 'var(--text-primary)',
              }}>{q.rank}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 6. Top cited URLs */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)', marginBottom: 8 }}>
          Top Cited URLs
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {urls.map((u, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--bg)' }}>
              <span className="truncate" style={{ fontSize: 12, color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 500, flex: 1, marginRight: 12 }}>{u.url}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', flexShrink: 0 }}>{u.citations} citations</span>
            </div>
          ))}
        </div>
      </div>

      {/* 7. Structural preferences */}
      <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--bg)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)', marginBottom: 8 }}>
          Structural Preferences
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {[
            { pref: 'Lists & bullet points', has: true },
            { pref: 'Comparison tables', has: platform.key === 'chatgpt' || platform.key === 'perplexity' },
            { pref: 'FAQ sections', has: platform.key === 'google' },
            { pref: 'Technical depth', has: platform.key === 'claude' || platform.key === 'gemini' },
            { pref: 'Source attribution', has: true },
          ].map((item, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12, fontFamily: 'var(--font-display)' }}>
              <span style={{ color: 'var(--text-primary)' }}>{item.pref}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 500, color: item.has ? 'var(--success)' : 'var(--text-tertiary)' }}>
                {item.has ? 'Present' : 'Missing'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 8. Overall score */}
      <div style={{ padding: '16px 0', borderTop: '1px solid var(--border)', textAlign: 'center' }}>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          Your score for {platform.name}:
        </span>
        <span style={{ fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)', marginLeft: 8 }}>
          {score}/100
        </span>
      </div>
    </div>
  );
}

export function PlatformIntelligence({ data }: PlatformIntelligenceProps) {
  const stats = useMemo(() => computePlatformStats(data), [data]);
  const [selectedPlatform, setSelectedPlatform] = useState<SelectedPlatform>(null);

  const topPlatform = PLATFORMS.reduce((best, p) =>
    stats[p.key].totalCitations > stats[best.key].totalCitations ? p : best
  , PLATFORMS[0]);

  return (
    <div>
      <h2
        className="mb-3"
        style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
      >
        Platform Intelligence
      </h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
        {PLATFORMS.map((p, pIdx) => {
          const s = stats[p.key];
          const isTop = p.key === topPlatform.key;

          return (
            <div
              key={p.key}
              onClick={() => setSelectedPlatform(p)}
              className="border rounded-md transition-colors duration-150 hover:border-border-strong cursor-pointer"
              style={{
                padding: 16,
                background: 'var(--surface)',
                borderColor: 'var(--border)',
                borderTopWidth: isTop ? 2 : 1,
                borderTopColor: isTop ? p.color : 'var(--border)',
                animation: `fadeUp 400ms ease-out ${pIdx * 50}ms both`,
              }}
            >
              <div className="flex items-center gap-2 mb-3">
                <BrandLogo domain={p.domain} size={16} />
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                  {p.name}
                </span>
                {isTop && (
                  <span style={{ fontSize: 9, fontWeight: 600, background: p.color, color: '#fff', padding: '1px 5px', borderRadius: 9999, fontFamily: 'var(--font-body)', marginLeft: 'auto' }}>
                    TOP
                  </span>
                )}
              </div>

              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 26, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                {s.totalCitations}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-body)', marginBottom: 10 }}>
                citations
              </div>

              <div className="space-y-1.5 mb-3">
                {[
                  { label: 'SOV', value: `${s.sov}%` },
                  { label: 'Avg Rank', value: String(s.avgRank) },
                  { label: 'Coverage', value: `${s.coverage}%` },
                  { label: 'Sentiment', value: s.sentiment },
                ].map(row => (
                  <div key={row.label} className="flex items-center justify-between">
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>{row.label}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 500, color: 'var(--text-primary)' }}>{row.value}</span>
                  </div>
                ))}
              </div>

              <div className="mb-2">
                <Sparkline values={s.sparklineData} color={p.color} />
              </div>

              <div className="space-y-1">
                <div style={{ fontSize: 10, color: 'var(--success)', fontFamily: 'var(--font-body)' }}>&#10003; {s.positive}</div>
                <div style={{ fontSize: 10, color: 'var(--warning)', fontFamily: 'var(--font-body)' }}>&#10007; {s.negative}</div>
              </div>
            </div>
          );
        })}
      </div>

      <SlideDrawer
        open={selectedPlatform !== null}
        onClose={() => setSelectedPlatform(null)}
        title={selectedPlatform?.name || ''}
        subtitle={`Detailed citation analytics for ${selectedPlatform?.name || ''}`}
      >
        {selectedPlatform && (
          <PlatformDrawerContent
            platform={selectedPlatform}
            stat={stats[selectedPlatform.key]}
          />
        )}
      </SlideDrawer>
    </div>
  );
}
