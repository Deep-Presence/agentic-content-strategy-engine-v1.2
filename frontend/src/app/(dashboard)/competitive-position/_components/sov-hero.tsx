'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown, AlertTriangle, ShieldAlert, Zap } from 'lucide-react';
import { RANK_HISTORY, COMPETITORS, YOUR_DATA } from './data';
import { BrandLogo } from './brand-logo';
import { Sparkline } from './sparkline';

const COLORS: Record<string, string> = {
  you: 'var(--accent)', 'bolt.new': '#E5484D', 'cursor.com': '#34B27B',
  'replit.com': '#F5A623', 'v0.dev': '#9D8CE0', 'emergent.sh': 'var(--text-tertiary)',
};

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'rgba(17,24,28,0.94)', backdropFilter: 'blur(8px)', borderRadius: 8, padding: '10px 14px', boxShadow: 'var(--shadow-float)', border: '1px solid rgba(255,255,255,0.06)' }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: '#fff', marginBottom: 4 }}>{label}</p>
      {payload.map((e) => (
        <div key={e.dataKey} style={{ display: 'flex', alignItems: 'center', gap: 6, lineHeight: 1.8 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: e.color }} />
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.65)', minWidth: 56 }}>{e.dataKey === 'you' ? 'You' : e.dataKey}</span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#fff' }}>#{e.value}</span>
        </div>
      ))}
    </div>
  );
}

export function RankHero({ onCompetitorClick }: { onCompetitorClick: (domain: string) => void }) {
  // Rising threats — competitors with positive delta, sorted by delta
  const threats = [...COMPETITORS].filter((c) => c.delta > 0).sort((a, b) => b.delta - a.delta);
  // Recent changes
  const changes = [
    { icon: <ShieldAlert size={12} />, color: 'var(--error)', text: '3 citations lost to competitors with newer content' },
    { icon: <Zap size={12} />, color: 'var(--success)', text: 'Overtook Replit — now #2 overall (was #4 last month)' },
    { icon: <AlertTriangle size={12} />, color: 'var(--warning)', text: 'Emergent.sh growing +3.1 pts — fastest mover in your space' },
  ];

  return (
    <div id="rank-hero" className="grid" style={{ gridTemplateColumns: '1fr 280px', gap: 0, border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
      {/* Rank Trajectory Chart */}
      <div style={{ padding: '14px 16px', borderRight: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>Rank Trajectory</p>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Your competitive rank over 28 days — #1 is the top position</p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {[{ k: 'you', l: 'You', d: 'lovable.dev' }, { k: 'bolt.new', l: 'Bolt', d: 'bolt.new' }, { k: 'cursor.com', l: 'Cursor', d: 'cursor.com' }].map((e) => (
              <div key={e.k} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <div style={{ width: e.k === 'you' ? 14 : 10, borderTop: `${e.k === 'you' ? '2.5px solid' : '1.5px dashed'} ${COLORS[e.k]}`, opacity: e.k === 'you' ? 1 : 0.5 }} />
                <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{e.l}</span>
              </div>
            ))}
          </div>
        </div>

        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={RANK_HISTORY} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={{ stroke: 'var(--border)' }} interval={4} />
            <YAxis reversed tick={{ fontSize: 10, fontFamily: 'var(--font-mono)', fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={false} domain={[1, 7]} tickFormatter={(v: number) => `#${v}`} />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--border-strong)', strokeWidth: 1, strokeDasharray: '4 4' }} />
            <Line type="monotone" dataKey="you" stroke="var(--accent)" strokeWidth={2.5} dot={false} activeDot={{ r: 5, fill: 'var(--accent)', stroke: 'var(--surface)', strokeWidth: 2 }} />
            {(['bolt.new', 'cursor.com', 'replit.com', 'v0.dev', 'emergent.sh'] as const).map((k) => (
              <Line key={k} type="monotone" dataKey={k} stroke={COLORS[k]} strokeWidth={1} strokeDasharray="4 4" strokeOpacity={0.3} dot={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Threat Watch sidebar */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {/* Rising Threats */}
        <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid var(--border)' }}>
          <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--error)', marginBottom: 8 }}>
            Rising Threats
          </p>
          {threats.map((c) => (
            <div
              key={c.domain}
              onClick={() => onCompetitorClick(c.domain)}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 0', borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <BrandLogo domain={c.domain} size={14} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>{c.name}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <TrendingUp size={9} style={{ color: 'var(--error)' }} />
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--error)' }}>+{c.delta}</span>
                  <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>· {c.winRate}% win rate</span>
                </div>
              </div>
              <Sparkline data={c.sparkline} color="var(--error)" width={32} height={12} />
            </div>
          ))}
        </div>

        {/* What Changed This Week */}
        <div style={{ padding: '10px 14px', flex: 1 }}>
          <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
            This Week
          </p>
          {changes.map((c, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginBottom: 8 }}>
              <div style={{ width: 18, height: 18, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: c.color, background: `color-mix(in srgb, ${c.color} 12%, transparent)`, flexShrink: 0, marginTop: 1 }}>{c.icon}</div>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{c.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
