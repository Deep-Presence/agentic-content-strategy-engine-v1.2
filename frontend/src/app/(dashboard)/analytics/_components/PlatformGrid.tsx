'use client';

import { useMemo, useState } from 'react';
import {
  AreaChart,
  Area,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { PLATFORM_GRID, PLATFORM_COLORS, PLATFORM_INSIGHTS, generatePlatformSparkline } from './data';
import { BrandLogo } from './BrandLogo';
import { CheckCircle, AlertTriangle } from 'lucide-react';

function SparklineTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { day: number; value: number } }> }) {
  if (!active || !payload?.[0]) return null;
  const { day, value } = payload[0].payload;
  return (
    <div
      style={{
        background: 'rgba(17,24,28,0.92)',
        backdropFilter: 'blur(8px)',
        color: '#EDEDED',
        fontSize: '10px',
        padding: '3px 6px',
        borderRadius: '3px',
        fontFamily: 'var(--font-display)',
        whiteSpace: 'nowrap',
      }}
    >
      Mar {day}: {value} citations
    </div>
  );
}

export function PlatformGrid() {
  const highestSOV = useMemo(() => {
    return PLATFORM_GRID.reduce((max, p) => (p.sov > max.sov ? p : max), PLATFORM_GRID[0]);
  }, []);

  const sparklines = useMemo(() => {
    const result: Record<string, { day: number; value: number }[]> = {};
    PLATFORM_GRID.forEach((p) => {
      result[p.platform] = generatePlatformSparkline(p.citations);
    });
    return result;
  }, []);

  // Compute average and trend for each sparkline
  const sparkMeta = useMemo(() => {
    const result: Record<string, { avg: number; declining: boolean }> = {};
    Object.entries(sparklines).forEach(([platform, data]) => {
      const avg = data.reduce((s, d) => s + d.value, 0) / data.length;
      // Simple: compare first half average vs second half average
      const firstHalf = data.slice(0, 14).reduce((s, d) => s + d.value, 0) / 14;
      const secondHalf = data.slice(14).reduce((s, d) => s + d.value, 0) / 14;
      result[platform] = { avg, declining: secondHalf < firstHalf * 0.9 };
    });
    return result;
  }, [sparklines]);

  return (
    <div
      className="p-3"
      style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
    >
      <h3 className="text-[15px] font-semibold mb-3" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
        Platform Intelligence
      </h3>

      <div className="grid grid-cols-5 gap-0">
        {PLATFORM_GRID.map((p) => {
          const isHighest = p.platform === highestSOV.platform;
          const color = PLATFORM_COLORS[p.platform] || 'var(--accent)';
          const insight = PLATFORM_INSIGHTS[p.platform];
          const meta = sparkMeta[p.platform];
          const sparkColor = meta?.declining ? 'var(--error)' : color;

          return (
            <div
              key={p.platform}
              className="p-3 flex flex-col gap-2 relative"
              style={{
                borderTop: isHighest ? `2px solid var(--accent)` : '1px solid var(--border)',
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
                borderLeft: '1px solid var(--border)',
              }}
            >
              {/* Top platform badge */}
              {isHighest && (
                <span
                  className="absolute top-1.5 right-1.5 text-[10px]"
                  style={{ color: 'var(--accent)', fontFamily: 'var(--font-display)' }}
                >
                  Top platform
                </span>
              )}

              {/* Platform header */}
              <div className="flex items-center gap-2">
                <BrandLogo domain={p.domain} size={20} />
                <span
                  className="text-[13px] font-semibold"
                  style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
                >
                  {p.platform}
                </span>
              </div>

              {/* Citations — larger for top platform */}
              <div>
                <span
                  className="text-[11px] uppercase block"
                  style={{ letterSpacing: '0.05em', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
                >
                  Citations
                </span>
                <span
                  className={isHighest ? 'text-[24px]' : 'text-[20px]'}
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}
                >
                  {p.citations}
                </span>
              </div>

              {/* Metrics */}
              <div className="flex flex-col gap-1">
                <MetricRow label="SOV" value={`${p.sov}%`} />
                <MetricRow label="Avg Rank" value={`${p.avgRank}`} />
                <MetricRow label="Coverage" value={`${p.coverage}%`} />
              </div>

              {/* Sentiment pill */}
              <div>
                <span
                  className="text-[11px] uppercase block mb-1"
                  style={{ letterSpacing: '0.05em', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
                >
                  Sentiment
                </span>
                <span
                  className="inline-block text-[10px] font-medium px-2 py-0.5 rounded-full"
                  style={{
                    background: p.sentiment === 'Positive' ? 'var(--success-subtle)' : p.sentiment === 'Neutral' ? 'var(--accent-subtle)' : 'var(--error-subtle)',
                    color: p.sentiment === 'Positive' ? 'var(--success)' : p.sentiment === 'Neutral' ? 'var(--text-secondary)' : 'var(--error)',
                  }}
                >
                  {p.sentiment}
                </span>
              </div>

              {/* Sparkline — 64px with average reference line + hover tooltip */}
              <div style={{ height: 64 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sparklines[p.platform]} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
                    <Tooltip content={<SparklineTooltip />} />
                    <ReferenceLine
                      y={meta?.avg || 0}
                      stroke="var(--border)"
                      strokeDasharray="3 3"
                      strokeWidth={1}
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={sparkColor}
                      strokeWidth={1.5}
                      fill={sparkColor}
                      fillOpacity={0.08}
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Strength & Weakness */}
              {insight && (
                <div className="flex flex-col gap-1 mt-auto">
                  <div className="flex items-start gap-1">
                    <CheckCircle size={10} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--success)' }} />
                    <span className="text-[10px] leading-tight truncate" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                      {insight.strength}
                    </span>
                  </div>
                  <div className="flex items-start gap-1">
                    <AlertTriangle size={10} className="flex-shrink-0 mt-0.5" style={{ color: '#F5A623' }} />
                    <span className="text-[10px] leading-tight truncate" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                      {insight.weakness}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span
        className="text-[11px] uppercase"
        style={{ letterSpacing: '0.05em', color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
      >
        {label}
      </span>
      <span
        className="text-[13px]"
        style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
      >
        {value}
      </span>
    </div>
  );
}
