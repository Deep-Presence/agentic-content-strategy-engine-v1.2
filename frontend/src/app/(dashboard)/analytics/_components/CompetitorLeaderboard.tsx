'use client';

import { useMemo, useState } from 'react';
import { AreaChart, Area, ResponsiveContainer, LineChart, Line } from 'recharts';
import { LEADERBOARD, generateCompetitiveTrend, PLATFORM_COLORS, MICRO_TRENDS } from './data';
import { BrandLogo } from './BrandLogo';

const BRAND_COLORS: Record<string, string> = {
  'Bolt.new': PLATFORM_COLORS.ChatGPT,
  Lovable: 'var(--accent)',
  Cursor: PLATFORM_COLORS.Perplexity,
  Replit: PLATFORM_COLORS['Google AI'],
  'V0.dev': PLATFORM_COLORS.Gemini,
  Emergent: PLATFORM_COLORS.Claude,
};

export function CompetitorLeaderboard() {
  const trendData = useMemo(() => generateCompetitiveTrend(), []);
  const [toastBrand, setToastBrand] = useState<string | null>(null);

  const handleRowClick = (brand: (typeof LEADERBOARD)[0]) => {
    setToastBrand(brand.name);
    setTimeout(() => setToastBrand(null), 2500);
  };

  return (
    <div
      className="p-3 flex flex-col gap-3 relative"
      style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
    >
      <h3 className="text-[15px] font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
        Competitor Leaderboard
      </h3>

      {/* Toast */}
      {toastBrand && (
        <div
          className="absolute top-2 right-2 px-3 py-2 rounded-md text-[12px] font-medium whitespace-nowrap z-50"
          style={{
            background: 'rgba(17,24,28,0.92)',
            color: '#EDEDED',
            backdropFilter: 'blur(8px)',
            boxShadow: 'var(--shadow-float)',
          }}
        >
          View {toastBrand} in Competitive Position &rarr;
        </div>
      )}

      {/* Leaderboard rows */}
      <div className="flex flex-col">
        {LEADERBOARD.map((brand) => {
          const microData = MICRO_TRENDS[brand.domain];
          const microChartData = microData ? microData.map((v, i) => ({ d: i, v })) : [];

          return (
            <div
              key={brand.domain}
              className="flex items-center gap-2 px-2 py-2 transition-colors cursor-pointer"
              style={{
                background: brand.isYou ? 'var(--accent-subtle)' : 'transparent',
                borderBottom: '1px solid var(--border)',
                borderRadius: brand.isYou ? 'var(--radius-sm)' : 0,
                borderLeft: brand.isYou ? '3px solid var(--accent)' : '3px solid transparent',
              }}
              onClick={() => handleRowClick(brand)}
              onMouseEnter={(e) => {
                if (!brand.isYou) (e.currentTarget as HTMLElement).style.background = 'var(--accent-subtle)';
              }}
              onMouseLeave={(e) => {
                if (!brand.isYou) (e.currentTarget as HTMLElement).style.background = 'transparent';
              }}
            >
              {/* Rank */}
              <span
                className="text-[12px] w-[20px] text-center flex-shrink-0"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}
              >
                {brand.rank}
              </span>

              {/* Logo */}
              <BrandLogo domain={brand.domain} size={16} />

              {/* Name */}
              <span
                className="text-[13px] flex-1 min-w-0 truncate"
                style={{
                  fontFamily: 'var(--font-display)',
                  fontWeight: brand.isYou ? 600 : 500,
                  color: 'var(--text-primary)',
                }}
              >
                {brand.name}
              </span>

              {brand.isYou && (
                <span
                  className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0"
                  style={{ background: 'var(--accent)', color: 'var(--text-on-accent)' }}
                >
                  YOU
                </span>
              )}

              {/* SOV — bold for YOUR row */}
              <span
                className="text-[13px] w-[48px] text-right flex-shrink-0"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontWeight: brand.isYou ? 600 : 400,
                  color: 'var(--text-primary)',
                }}
              >
                {brand.sov}%
              </span>

              {/* Citations */}
              <span
                className="text-[13px] w-[48px] text-right flex-shrink-0"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
              >
                {brand.citations}
              </span>

              {/* Delta + micro sparkline */}
              <div className="flex items-center gap-1 w-[72px] justify-end flex-shrink-0">
                <span
                  className="text-[11px]"
                  style={{
                    color: brand.delta > 0 ? 'var(--success)' : brand.delta < 0 ? 'var(--error)' : 'var(--text-tertiary)',
                  }}
                >
                  {brand.delta > 0 ? '+' : ''}{brand.delta}
                </span>
                {/* 7-day micro sparkline */}
                <div style={{ width: 28, height: 14 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={microChartData} margin={{ top: 1, right: 1, left: 1, bottom: 1 }}>
                      <Line
                        type="monotone"
                        dataKey="v"
                        stroke={brand.delta > 0 ? 'var(--success)' : brand.delta < 0 ? 'var(--error)' : 'var(--text-tertiary)'}
                        strokeWidth={1}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Mini Competitive Trend */}
      <div>
        <ResponsiveContainer width="100%" height={80}>
          <AreaChart data={trendData} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            {LEADERBOARD.map((brand) => (
              <Area
                key={brand.name}
                type="monotone"
                dataKey={brand.name}
                stroke={BRAND_COLORS[brand.name] || 'var(--text-tertiary)'}
                strokeWidth={brand.isYou ? 2 : 1}
                fill="none"
                dot={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
