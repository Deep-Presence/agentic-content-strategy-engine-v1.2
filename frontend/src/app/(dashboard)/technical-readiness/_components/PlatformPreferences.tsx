'use client';

import { useState } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';
import {
  ENGINE_LIST,
  ENGINE_PREFERENCES,
  SIGNAL_KEYS,
  SIGNAL_LABELS,
  type EngineKey,
} from './tech-readiness-data';

function BrandLogo({ domain, size = 14 }: { domain: string; size?: number }) {
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

export function PlatformPreferences() {
  const [activeEngine, setActiveEngine] = useState<EngineKey>('chatgpt');
  const engine = ENGINE_PREFERENCES[activeEngine];

  const radarData = SIGNAL_KEYS.map((key) => ({
    signal: SIGNAL_LABELS[key],
    preference: engine.preferences[key],
    yours: engine.yourScores[key],
  }));

  return (
    <div>
      <div className="mb-3">
        <h2
          className="text-[16px] font-semibold"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          What Each AI Engine Prefers
        </h2>
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          Different engines prioritize different content signals. Here&apos;s what each one looks for.
        </p>
      </div>

      {/* Engine Tabs */}
      <div className="flex items-center gap-0 border-b border-[var(--border)] mb-4">
        {ENGINE_LIST.map((eng) => {
          const isActive = activeEngine === eng.key;
          return (
            <button
              key={eng.key}
              className="flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium transition-colors relative"
              style={{
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                fontFamily: 'var(--font-display)',
                fontWeight: isActive ? 600 : 400,
              }}
              onClick={() => setActiveEngine(eng.key)}
            >
              <BrandLogo domain={eng.domain} size={14} />
              {eng.name}
              {isActive && (
                <span
                  className="absolute bottom-0 left-0 right-0 h-[2px]"
                  style={{ backgroundColor: 'var(--accent)' }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Content: Radar + Table */}
      <div className="flex gap-4 flex-col lg:flex-row">
        {/* Radar */}
        <div
          className="border border-[var(--border)] rounded-[var(--radius-md)] p-3 bg-[var(--surface)] flex items-center justify-center"
          style={{ minWidth: 260, flex: '0 0 40%' }}
        >
          <ResponsiveContainer width={240} height={240}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis
                dataKey="signal"
                tick={{
                  fill: 'var(--text-secondary)',
                  fontSize: 9,
                  fontFamily: 'var(--font-display)',
                }}
              />
              <PolarRadiusAxis
                angle={90}
                domain={[0, 100]}
                tick={false}
                axisLine={false}
              />
              <Radar
                name="Engine Preference"
                dataKey="preference"
                stroke="var(--accent)"
                fill="var(--accent)"
                fillOpacity={0.15}
                strokeWidth={2}
              />
              <Radar
                name="Your Score"
                dataKey="yours"
                stroke="var(--success)"
                fill="var(--success)"
                fillOpacity={0.1}
                strokeWidth={1.5}
                strokeDasharray="4 3"
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Preferences Table */}
        <div className="border border-[var(--border)] rounded-[var(--radius-md)] bg-[var(--surface)] flex-1 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border)]">
                {['Signal', 'Preference', 'Your Strength'].map((h) => (
                  <th
                    key={h}
                    className="text-left px-3 py-2"
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: 'var(--text-tertiary)',
                      fontFamily: 'var(--font-display)',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SIGNAL_KEYS.map((key) => {
                const pref = engine.preferences[key];
                const yours = engine.yourScores[key];
                const gap = pref - yours;
                let barColor = 'var(--success)';
                if (gap > 20) barColor = 'var(--error)';
                else if (gap > 0) barColor = 'var(--warning)';

                return (
                  <tr key={key} className="border-b border-[var(--border)] last:border-b-0">
                    <td
                      className="px-3 py-1.5 text-[13px]"
                      style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
                    >
                      {SIGNAL_LABELS[key]}
                    </td>
                    <td className="px-3 py-1.5">
                      <span
                        className="text-[12px]"
                        style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
                      >
                        {pref}%
                      </span>
                    </td>
                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 rounded-full bg-[var(--border)]" style={{ maxWidth: 120 }}>
                          <div
                            className="h-2 rounded-full transition-all duration-300"
                            style={{ width: `${yours}%`, backgroundColor: barColor }}
                          />
                        </div>
                        <span
                          className="text-[12px]"
                          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
                        >
                          {yours}%
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Natural Language Summary */}
      <div
        className="border border-[var(--border)] rounded-[var(--radius-md)] p-3 bg-[var(--surface)] mt-3"
      >
        <p
          className="text-[13px] leading-[1.6]"
          style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
        >
          {engine.summary}
        </p>
        <p className="mt-2">
          <span
            className="text-[12px]"
            style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
          >
            Your overall score for {engine.name}&apos;s preferences:{' '}
          </span>
          <span
            className="text-[18px] font-semibold"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}
          >
            {engine.overallScore}/100
          </span>
        </p>
      </div>
    </div>
  );
}
