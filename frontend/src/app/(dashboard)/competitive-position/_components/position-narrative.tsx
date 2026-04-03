'use client';

import { YOUR_DATA } from './data';

export function PositionNarrative() {
  const d = YOUR_DATA;

  const rankChange = d.previousRank > d.rank
    ? `up from #${d.previousRank} last month`
    : d.previousRank < d.rank
    ? `down from #${d.previousRank} last month`
    : 'unchanged from last month';

  return (
    <div
      style={{
        background: 'var(--accent-subtle)',
        border: '1px solid var(--accent)',
        borderColor: 'rgba(91,164,196,0.2)',
        borderRadius: '6px',
        padding: '14px',
        animation: 'fadeUp 400ms ease 200ms both',
      }}
    >
      <p
        style={{
          fontSize: '14px',
          lineHeight: 1.6,
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-display)',
        }}
      >
        You&apos;re ranked{' '}
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>#{d.rank}</span> out of{' '}
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{d.totalTracked}</span> tracked
        brands — {rankChange}. Your share of voice grew from{' '}
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{d.sovStart}%</span> to{' '}
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{d.sov}%</span> this period,
        closing the gap on Bolt.new. At this pace, you&apos;ll overtake Cursor within 2 weeks.
      </p>
    </div>
  );
}
