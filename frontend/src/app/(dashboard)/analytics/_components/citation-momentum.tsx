'use client';

import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceDot,
} from 'recharts';
import { generateMomentumData, PLATFORM_COLORS, PLATFORM_KEYS, CHART_EVENTS } from './data';

const RAW_DATA = generateMomentumData();

// Add 'total' field to each day
const MOMENTUM_DATA = RAW_DATA.map(d => ({
  ...d,
  total: PLATFORM_KEYS.reduce((s, p) => s + (d[p] as number), 0),
}));

const PLATFORM_DOMAINS: Record<string, string> = {
  ChatGPT: 'openai.com',
  Claude: 'anthropic.com',
  Perplexity: 'perplexity.ai',
  'Google AI': 'google.com',
  Gemini: 'gemini.google.com',
};

function PlatformStrip() {
  const totals = useMemo(() => {
    const t: Record<string, number> = {};
    let grand = 0;
    PLATFORM_KEYS.forEach(p => {
      const sum = MOMENTUM_DATA.reduce((s, d) => s + (d[p] as number), 0);
      t[p] = sum;
      grand += sum;
    });
    return { platforms: t, grand };
  }, []);

  return (
    <div style={{ marginTop: 12 }}>
      {/* Stacked horizontal bar */}
      <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden' }}>
        {PLATFORM_KEYS.map(p => (
          <div
            key={p}
            style={{
              width: `${(totals.platforms[p] / totals.grand) * 100}%`,
              background: PLATFORM_COLORS[p],
            }}
          />
        ))}
      </div>
      {/* Platform labels */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
        {PLATFORM_KEYS.map(p => (
          <div key={p} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 2,
                background: PLATFORM_COLORS[p],
                flexShrink: 0,
              }}
            />
            <img
              src={`https://www.google.com/s2/favicons?domain=${PLATFORM_DOMAINS[p]}&sz=24`}
              alt={p}
              width={12}
              height={12}
              style={{ borderRadius: 2 }}
            />
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
              {p}
            </span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
              {Math.round((totals.platforms[p] / totals.grand) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EventStrip() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
      {CHART_EVENTS.map((evt, i) => (
        <div
          key={i}
          className="flex items-center gap-1.5 text-[11px]"
          style={{
            fontFamily: 'var(--font-body)',
            color: 'var(--text-secondary)',
            animation: `fadeUp 250ms ease ${i * 50}ms both`,
          }}
        >
          <span
            className="inline-block w-[6px] h-[6px] rounded-full flex-shrink-0"
            style={{ background: evt.color }}
          />
          <span style={{ color: 'var(--text-tertiary)' }}>{evt.date}</span>
          <span>{evt.label}</span>
        </div>
      ))}
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const total = payload.find((p: any) => p.dataKey === 'total')?.value || 0;
  const dayData = MOMENTUM_DATA.find(d => d.date === label);
  return (
    <div
      style={{
        background: '#1e1e1e',
        border: '1px solid #333',
        borderRadius: 6,
        padding: '10px 14px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
        fontSize: 12,
        maxWidth: 260,
      }}
    >
      <div style={{ color: '#EDEDED', fontWeight: 600, marginBottom: 6, fontFamily: 'var(--font-body)' }}>
        {label}
      </div>
      <div style={{ color: '#EDEDED', fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
        {total} citations
      </div>
      {dayData &&
        PLATFORM_KEYS.map(p => (
          <div key={p} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span style={{ width: 6, height: 6, borderRadius: 1, background: PLATFORM_COLORS[p] }} />
            <span style={{ color: '#A0A0A0', flex: 1, fontFamily: 'var(--font-body)' }}>{p}</span>
            <span style={{ color: '#EDEDED', fontFamily: 'var(--font-mono)' }}>{dayData[p] as number}</span>
          </div>
        ))}
    </div>
  );
}

export function CitationMomentum() {
  const eventDateIndices = useMemo(() => {
    return CHART_EVENTS.map(evt => {
      const idx = MOMENTUM_DATA.findIndex(d => d.date === evt.date);
      if (idx < 0) return null;
      const row = MOMENTUM_DATA[idx];
      const total = PLATFORM_KEYS.reduce((s, p) => s + (row[p] as number), 0);
      return { ...evt, idx, total };
    }).filter(Boolean) as (typeof CHART_EVENTS[number] & { idx: number; total: number })[];
  }, []);

  return (
    <div id="citation-momentum" style={{ animation: 'fadeIn 300ms ease' }}>
      <div
        className="p-3.5 rounded-[var(--radius-md)]"
        style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}
      >
        <div className="flex items-center justify-between mb-1">
          <h2
            className="text-[16px] font-semibold"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
          >
            Citation Momentum
          </h2>
        </div>

        <ResponsiveContainer width="100%" height={340}>
          <AreaChart data={MOMENTUM_DATA} margin={{ top: 12, right: 8, left: -8, bottom: 0 }}>
            <defs>
              <linearGradient id="citationGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.25} />
                <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fontFamily: 'var(--font-mono)', fill: 'var(--text-tertiary)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
              interval={3}
            />
            <YAxis
              tick={{ fontSize: 11, fontFamily: 'var(--font-mono)', fill: 'var(--text-tertiary)' }}
              tickLine={false}
              axisLine={false}
              tickCount={5}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="total"
              stroke="var(--accent)"
              strokeWidth={2}
              fill="url(#citationGrad)"
              dot={false}
            />
            {eventDateIndices.map(evt => (
              <ReferenceDot
                key={evt.date}
                x={evt.date}
                y={evt.total}
                r={4}
                fill={evt.color}
                stroke="var(--surface)"
                strokeWidth={1.5}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>

        <PlatformStrip />
        <EventStrip />
      </div>
    </div>
  );
}
