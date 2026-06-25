'use client';

import { YOUR_DATA } from './data';

export function KPIStrip() {
  const d = YOUR_DATA;
  return (
    <div className="grid grid-cols-3" style={{ gap: 12 }}>
      <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: '14px 16px' }}>
        <p style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Share of Voice</p>
        <p style={{ fontSize: 26, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', lineHeight: 1 }}>{d.sov}%</p>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>up from {d.sovStart}%</p>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: '14px 16px' }}>
        <p style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Rank</p>
        <p style={{ fontSize: 26, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', lineHeight: 1 }}>#{d.rank}</p>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>of {d.totalTracked} tracked brands</p>
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: '14px 16px' }}>
        <p style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', marginBottom: 4 }}>Win Rate</p>
        <p style={{ fontSize: 26, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', lineHeight: 1 }}>{d.winRate}%</p>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>vs top competitors</p>
      </div>
    </div>
  );
}
