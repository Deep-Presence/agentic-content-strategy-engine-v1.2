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

function PlatformDrawerContent({ platform, stat, data }: { platform: typeof PLATFORMS[number]; stat: PlatformStat; data: DayData[] }) {
  return (
    <div className="space-y-5 pt-5">
      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
        {[
          { label: 'Citations', value: String(stat.totalCitations), color: platform.color },
          { label: 'Share of Voice', value: `${stat.sov}%`, color: 'var(--accent)' },
          { label: 'Avg Rank', value: String(stat.avgRank), color: stat.avgRank <= 2.5 ? 'var(--success)' : 'var(--warning)' },
          { label: 'Coverage', value: `${stat.coverage}%`, color: stat.coverage >= 75 ? 'var(--success)' : 'var(--text-primary)' },
        ].map(s => (
          <div key={s.label} className="border border-border rounded-md" style={{ padding: '10px 12px', background: 'var(--bg)' }}>
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', marginBottom: 4 }}>
              {s.label}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 600, color: s.color }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      {/* Daily trend */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', marginBottom: 8 }}>
          Daily Citations (last 7 days)
        </div>
        <div className="space-y-1">
          {data.slice(-7).map(d => (
            <div key={d.dateShort} className="flex items-center justify-between" style={{ padding: '4px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>{d.dateShort}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500, color: platform.color }}>
                {d[platform.key] as number}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Insights */}
      <div className="border border-border rounded-md" style={{ padding: '10px 12px', background: 'var(--bg)' }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', marginBottom: 8 }}>
          Platform Insights
        </div>
        <div className="space-y-2">
          <div style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
            <span style={{ color: 'var(--success)' }}>&#10003;</span> {stat.positive}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
            <span style={{ color: 'var(--warning)' }}>&#10007;</span> {stat.negative}
          </div>
        </div>
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
                padding: 12,
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
            data={data}
          />
        )}
      </SlideDrawer>
    </div>
  );
}
