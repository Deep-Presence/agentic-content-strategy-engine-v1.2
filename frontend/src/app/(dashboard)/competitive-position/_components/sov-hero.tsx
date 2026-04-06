'use client';

import { useState } from 'react';
import { AreaChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp } from 'lucide-react';
import { SOV_TREND, COMPETITORS, YOUR_DATA, MARKET_SHARE } from './data';
import { BrandLogo } from './brand-logo';
import { Sparkline } from './sparkline';

const PALETTE: Record<string, string> = {
  you: '#5BA4C4', 'bolt.new': '#E5484D', 'cursor.com': '#34B27B',
  'replit.com': '#E8A838', 'v0.dev': '#9D8CE0', 'emergent.sh': '#889096', 'retool.com': '#D97706',
};

const ALL_KEYS = ['you', 'bolt.new', 'cursor.com', 'replit.com', 'v0.dev', 'emergent.sh'] as const;

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const sorted = [...payload].sort((a, b) => b.value - a.value);
  return (
    <div style={{ background: 'rgba(17,24,28,0.94)', backdropFilter: 'blur(8px)', borderRadius: 8, padding: '10px 14px', boxShadow: '0 8px 30px rgba(0,0,0,0.3)' }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: '#fff', marginBottom: 6 }}>{label}</p>
      {sorted.map((e) => (
        <div key={e.dataKey} style={{ display: 'flex', alignItems: 'center', gap: 8, lineHeight: 1.8 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: e.color }} />
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', minWidth: 60 }}>{e.dataKey === 'you' ? 'You' : e.dataKey}</span>
          <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: '#fff' }}>{e.value}%</span>
        </div>
      ))}
    </div>
  );
}

// ─── Market Share Donut ─────────────────────────────────────────────────────

function MarketShareDonut() {
  const segments = Object.values(MARKET_SHARE);
  const total = segments.reduce((s, seg) => s + seg.pct, 0);
  const size = 190; const cx = size / 2; const cy = size / 2; const r = 70; const sw = 20;
  const colorMap: Record<string, string> = { 'var(--accent)': '#5BA4C4', 'var(--border-strong)': '#C4C9CD' };
  const resolve = (c: string) => colorMap[c] || c;

  let cum = 0;
  const arcs = segments.map((seg) => {
    const start = (cum / total) * 2 * Math.PI - Math.PI / 2;
    cum += seg.pct;
    const end = (cum / total) * 2 * Math.PI - Math.PI / 2;
    const large = seg.pct / total > 0.5 ? 1 : 0;
    return { ...seg, d: `M ${cx + r * Math.cos(start)} ${cy + r * Math.sin(start)} A ${r} ${r} 0 ${large} 1 ${cx + r * Math.cos(end)} ${cy + r * Math.sin(end)}` };
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {arcs.map((a) => <path key={a.label} d={a.d} fill="none" stroke={resolve(a.color)} strokeWidth={sw} strokeLinecap="butt" />)}
        <text x={cx} y={cy - 4} textAnchor="middle" fill="#11181C" fontSize={24} fontWeight={600} fontFamily="JetBrains Mono, monospace">{YOUR_DATA.sov}%</text>
        <text x={cx} y={cy + 14} textAnchor="middle" fill="#889096" fontSize={10}>Your Share</text>
      </svg>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px 10px', justifyContent: 'center', marginTop: 8 }}>
        {segments.map((seg) => (
          <div key={seg.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: resolve(seg.color) }} />
            <span style={{ fontSize: 9, color: '#687076' }}>{seg.label} {seg.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── SOV Trend + Donut + Threats ────────────────────────────────────────────

export function SOVHeroSection({ onCompetitorClick }: { onCompetitorClick: (domain: string) => void }) {
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const threats = [...COMPETITORS].filter((c) => c.delta > 0).sort((a, b) => b.delta - a.delta).slice(0, 4);

  const toggleHighlight = (key: string) => setHighlighted((prev) => (prev === key ? null : key));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Market Share + SOV Chart */}
      <div style={{ display: 'grid', gridTemplateColumns: '230px 1fr', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        {/* Donut */}
        <div style={{ padding: '20px 16px', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <p style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', marginBottom: 12, alignSelf: 'flex-start' }}>Market Share</p>
          <MarketShareDonut />
        </div>

        {/* SOV Chart */}
        <div style={{ padding: '14px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div>
              <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>SOV Trend</p>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Click any competitor line to highlight</p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {ALL_KEYS.slice(0, 4).map((k) => (
                <button key={k} onClick={() => toggleHighlight(k)} style={{
                  display: 'flex', alignItems: 'center', gap: 3, border: 'none', background: highlighted === k ? 'var(--accent-subtle)' : 'transparent',
                  padding: '2px 6px', borderRadius: 4, cursor: 'pointer',
                }}>
                  <div style={{ width: 8, height: 3, borderRadius: 2, background: PALETTE[k] }} />
                  <span style={{ fontSize: 9, color: highlighted === k ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>{k === 'you' ? 'You' : k.split('.')[0]}</span>
                </button>
              ))}
            </div>
          </div>

          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={SOV_TREND} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                <defs>
                  <linearGradient id="sovFill7" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#5BA4C4" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#5BA4C4" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#ECEEF0" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#889096' }} tickLine={false} axisLine={{ stroke: '#ECEEF0' }} interval={4} />
                <YAxis tick={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', fill: '#889096' }} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}%`} />
                <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#D7DBDF', strokeWidth: 1, strokeDasharray: '4 4' }} />
                <Area type="monotone" dataKey="you" stroke="#5BA4C4" strokeWidth={highlighted === 'you' || !highlighted ? 2.5 : 1} fill={!highlighted || highlighted === 'you' ? 'url(#sovFill7)' : 'none'} strokeOpacity={highlighted && highlighted !== 'you' ? 0.2 : 1} activeDot={{ r: 4, fill: '#5BA4C4', stroke: '#FBFCFD', strokeWidth: 2 }} />
                {ALL_KEYS.filter((k) => k !== 'you').map((k) => (
                  <Line key={k} type="monotone" dataKey={k} stroke={PALETTE[k]} strokeWidth={highlighted === k ? 2.5 : 1} strokeDasharray={highlighted === k ? undefined : '4 4'} strokeOpacity={highlighted && highlighted !== k ? 0.15 : highlighted === k ? 1 : 0.35} dot={false} />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Rising Threats (compact standalone card) */}
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px' }}>
        <p style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--error)', marginBottom: 8 }}>Rising Threats</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {threats.map((c) => (
            <div key={c.domain} onClick={() => onCompetitorClick(c.domain)} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 8px', borderRadius: 6, transition: 'background 0.12s' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
              <BrandLogo domain={c.domain} size={16} />
              <div style={{ flex: 1 }}>
                <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>{c.name}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <TrendingUp size={10} style={{ color: '#E5484D' }} />
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: '#E5484D' }}>+{c.delta}</span>
                </div>
              </div>
              <Sparkline data={c.sparkline} color="#E5484D" width={36} height={14} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
