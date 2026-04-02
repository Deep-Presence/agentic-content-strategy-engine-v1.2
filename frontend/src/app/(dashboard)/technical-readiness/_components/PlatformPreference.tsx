'use client';

import { useState } from 'react';
import {
  PLATFORMS,
  PLATFORM_PREFERENCES,
  PLATFORM_INSIGHTS,
  type PlatformKey,
} from './tech-readiness-data';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';

function BrandLogo({ domain, size = 14 }: { domain: string; size?: number }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 4 }}
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

export function PlatformPreference() {
  const [selected, setSelected] = useState<PlatformKey>('chatgpt');
  const platform = PLATFORMS.find((p) => p.key === selected)!;
  const data = PLATFORM_PREFERENCES[selected];

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
      <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>
        Platform Citation Preferences
      </h3>

      {/* Platform selector tabs — border-bottom style */}
      <div style={{ display: 'flex', gap: '0', borderBottom: '1px solid var(--border)', marginBottom: '12px' }}>
        {PLATFORMS.map((p) => (
          <button
            key={p.key}
            onClick={() => setSelected(p.key)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '8px 12px', fontSize: '12px', cursor: 'pointer',
              background: 'none', border: 'none',
              fontWeight: selected === p.key ? 600 : 400,
              color: selected === p.key ? 'var(--text-primary)' : 'var(--text-secondary)',
              borderBottom: selected === p.key ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: '-1px',
              transition: 'color 0.1s, border-color 0.1s',
            }}
          >
            <BrandLogo domain={p.domain} size={14} />
            {p.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: '2fr 3fr' }}>
        {/* Radar (40%) */}
        <div>
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis
                  dataKey="signal"
                  tick={{ fontSize: 11, fill: 'var(--text-secondary)' }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 100]}
                  tick={{ fontSize: 9, fill: 'var(--text-tertiary)' }}
                  axisLine={false}
                />
                <Radar
                  name={platform.label}
                  dataKey="value"
                  stroke="var(--accent)"
                  fill="var(--accent)"
                  fillOpacity={0.12}
                  strokeWidth={2}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Preference table + insight (60%) */}
        <div>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ textAlign: 'left', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '6px 8px' }}>
                  Signal
                </th>
                <th style={{ textAlign: 'right', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '6px 8px' }}>
                  Preference
                </th>
                <th style={{ textAlign: 'right', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', padding: '6px 8px', width: '100px' }}>
                  Strength
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((signal) => (
                <tr key={signal.signal} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ fontSize: '13px', color: 'var(--text-primary)', padding: '6px 8px' }}>{signal.signal}</td>
                  <td style={{ textAlign: 'right', fontSize: '13px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', padding: '6px 8px' }}>
                    {signal.value}%
                  </td>
                  <td style={{ padding: '6px 8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                      <div style={{ width: 80, height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                        <div
                          style={{
                            width: `${signal.value}%`,
                            height: '100%',
                            background: 'var(--accent)',
                            borderRadius: 4,
                            transition: 'width 0.3s ease',
                          }}
                        />
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Dynamic insight callout */}
          <div style={{
            border: '1px solid var(--border)', background: 'var(--bg)', borderRadius: '6px', padding: '12px',
            fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6,
          }}>
            {PLATFORM_INSIGHTS[selected]}
          </div>
        </div>
      </div>
    </div>
  );
}
