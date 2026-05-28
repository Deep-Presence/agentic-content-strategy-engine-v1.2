'use client';

import { useEffect, useState } from 'react';
import { GAP_DATA } from './tech-readiness-data';

export function GapStatement() {
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="border border-[var(--border)] rounded-[var(--radius-md)] p-4 bg-[var(--surface)]">
      <p
        className="text-[10px] font-semibold uppercase tracking-[0.06em] mb-5"
        style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}
      >
        Your AI Readiness Assessment
      </p>

      {/* Site Health Bar */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-1.5">
          <span
            className="text-[13px] font-medium"
            style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
          >
            Site Health
          </span>
          <span
            className="text-[28px] font-semibold"
            style={{ color: 'var(--success)', fontFamily: 'var(--font-mono)' }}
          >
            {GAP_DATA.siteHealth.score}<span className="text-[14px] text-[var(--text-tertiary)]">/100</span>
          </span>
        </div>
        <div className="w-full h-3 rounded-full bg-[var(--border)]">
          <div
            className="h-3 rounded-full transition-all ease-out"
            style={{
              width: animated ? `${GAP_DATA.siteHealth.score}%` : '0%',
              backgroundColor: 'var(--success)',
              transitionDuration: '600ms',
            }}
          />
        </div>
        <p
          className="text-[12px] mt-1"
          style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
        >
          {GAP_DATA.siteHealth.label}
        </p>
      </div>

      {/* AI Citation Ready Bar */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-1.5">
          <span
            className="text-[13px] font-medium"
            style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
          >
            AI Citation Ready
          </span>
          <span
            className="text-[28px] font-semibold"
            style={{ color: 'var(--error)', fontFamily: 'var(--font-mono)' }}
          >
            {GAP_DATA.aiCitationReady.score}<span className="text-[14px] text-[var(--text-tertiary)]">/100</span>
          </span>
        </div>
        <div className="w-full h-3 rounded-full bg-[var(--border)]">
          <div
            className="h-3 rounded-full transition-all ease-out"
            style={{
              width: animated ? `${GAP_DATA.aiCitationReady.score}%` : '0%',
              backgroundColor: 'var(--error)',
              transitionDuration: '600ms',
            }}
          />
        </div>
        <p
          className="text-[12px] mt-1"
          style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
        >
          {GAP_DATA.aiCitationReady.label}
        </p>
      </div>

      {/* Gap Narrative */}
      <div
        className="rounded-[var(--radius-md)] p-3"
        style={{
          border: '1px solid var(--warning)',
          borderLeft: '3px solid var(--warning)',
          background: 'var(--warning-subtle)',
        }}
      >
        <p
          className="text-[10px] font-semibold uppercase tracking-[0.06em] mb-1.5"
          style={{ color: 'var(--warning)', fontFamily: 'var(--font-display)' }}
        >
          {GAP_DATA.narrative.title}
        </p>
        <p className="text-[13px] leading-[1.6]" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
          {GAP_DATA.narrative.body}
        </p>
        <p className="text-[13px] leading-[1.6] mt-1" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          Focus on: <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{GAP_DATA.narrative.focus}</span>.
        </p>
        <p className="text-[13px] leading-[1.6] mt-1" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          These 4 changes would increase your AI readiness score from {GAP_DATA.aiCitationReady.score} to an estimated{' '}
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontWeight: 600 }}>{GAP_DATA.narrative.estimate}</span>.
        </p>
      </div>
    </div>
  );
}
