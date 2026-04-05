'use client';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PLATFORM_SOV } from './data';
import { BrandLogo } from './brand-logo';

export function PlatformSection() {
  const chartData = PLATFORM_SOV.map((p) => ({ platform: p.platform, You: p.sov, Leader: p.leaderSov }));

  return (
    <div className="grid" style={{ gridTemplateColumns: '60% 40%', gap: 0, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
      {/* Chart */}
      <div style={{ padding: '14px 16px', borderRight: '1px solid var(--border)' }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', marginBottom: 2 }}>Platform Breakdown</p>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>
          Your SOV vs the platform leader on each AI engine
        </p>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }} barCategoryGap="20%">
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="platform" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
            <YAxis tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              return (
                <div style={{ background: 'rgba(17,24,28,0.94)', borderRadius: 8, padding: '8px 12px', boxShadow: 'var(--shadow-float)' }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#fff', marginBottom: 4 }}>{label}</p>
                  {payload.map((e) => (
                    <p key={String(e.dataKey)} style={{ fontSize: 10, color: 'rgba(255,255,255,0.7)', lineHeight: 1.8 }}>
                      {String(e.dataKey)}: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#fff' }}>{e.value}%</span>
                    </p>
                  ))}
                </div>
              );
            }} />
            <Bar dataKey="You" fill="var(--accent)" radius={[3, 3, 0, 0]} maxBarSize={20} />
            <Bar dataKey="Leader" fill="var(--border-strong)" fillOpacity={0.4} radius={[3, 3, 0, 0]} maxBarSize={20} />
          </BarChart>
        </ResponsiveContainer>
        <div style={{ display: 'flex', gap: 12, marginTop: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 10, height: 6, background: 'var(--accent)', borderRadius: 2 }} /><span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>You</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 10, height: 6, background: 'var(--border-strong)', opacity: 0.4, borderRadius: 2 }} /><span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>Platform Leader</span></div>
        </div>
      </div>

      {/* Summary list */}
      <div style={{ padding: '14px 0' }}>
        <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '0 14px', marginBottom: 8 }}>Per-Engine Summary</p>
        {PLATFORM_SOV.map((p, i) => {
          const isLeader = p.rank === 1;
          const isWeak = p.rank >= 4;
          return (
            <div key={p.platform} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 14px', height: 38, borderBottom: i < PLATFORM_SOV.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
              <BrandLogo domain={p.domain} size={16} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                  <span style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{p.sov}%</span>
                  <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: isLeader ? 'var(--success)' : isWeak ? 'var(--error)' : 'var(--text-tertiary)' }}>#{p.rank}</span>
                </div>
                <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{p.platform}</span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: p.delta > 0 ? 'var(--success)' : p.delta < 0 ? 'var(--error)' : 'var(--text-tertiary)' }}>
                  {p.delta > 0 ? '+' : ''}{p.delta}
                </span>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 2, justifyContent: 'flex-end' }}>
                  <BrandLogo domain={p.leaderDomain} size={9} />
                  <span>{p.leaderDomain.replace(/\.(com|new|dev|ai)$/, '')}</span>
                </div>
              </div>
            </div>
          );
        })}
        {/* Insight */}
        <div style={{ padding: '8px 14px', marginTop: 4 }}>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
            You lead on Perplexity (#1) but trail significantly on Claude (#5). Focus on Claude-optimized content: structured data, comprehensive guides.
          </p>
        </div>
      </div>
    </div>
  );
}
