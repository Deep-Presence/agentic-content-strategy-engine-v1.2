'use client';

import { useState } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { VISIBILITY, SENTIMENT, CONTEXT_CATEGORIES } from './data';

function DonutChart({
  value,
  label,
  color,
  rawCount,
  totalCount,
}: {
  value: number;
  label: string;
  color: string;
  rawCount: number;
  totalCount: number;
}) {
  const pct = Math.round(value * 100);
  const data = [
    { name: 'active', value: pct },
    { name: 'inactive', value: 100 - pct },
  ];

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: 120, height: 120 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={60}
              startAngle={90}
              endAngle={-270}
              strokeWidth={0}
            >
              <Cell fill={color} />
              <Cell fill="var(--border)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-[24px] font-semibold leading-none"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
          >
            {pct}%
          </span>
          <span className="text-[10px] mt-0.5" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
            {rawCount} of {totalCount}
          </span>
        </div>
      </div>
      <span className="text-[12px] font-medium mt-1" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
        {label}
      </span>
    </div>
  );
}

function SentimentBars() {
  const bars = [
    { label: 'Positive', value: SENTIMENT.positive, color: 'var(--success)' },
    { label: 'Neutral', value: SENTIMENT.neutral, color: 'var(--text-tertiary)' },
    { label: 'Negative', value: SENTIMENT.negative, color: 'var(--error)' },
  ];

  return (
    <div className="flex flex-col gap-2">
      {bars.map((b) => (
        <div key={b.label} className="flex items-center gap-2">
          <span className="text-[12px] w-[60px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
            {b.label}
          </span>
          <div className="flex-1 h-[6px] rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${b.value * 100}%`, background: b.color }}
            />
          </div>
          <span className="text-[12px] w-[36px] text-right" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
            {Math.round(b.value * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}

export function VisibilityBreakdown() {
  const [toastVisible, setToastVisible] = useState(false);

  const citedCount = Math.round(VISIBILITY.cited * VISIBILITY.totalQueries);
  const mentionedCount = Math.round(VISIBILITY.mentioned * VISIBILITY.totalQueries);
  const gapPct = Math.round((VISIBILITY.mentioned - VISIBILITY.cited) * 100);
  const gapQueries = mentionedCount - citedCount;

  const handleGapClick = () => {
    setToastVisible(true);
    setTimeout(() => setToastVisible(false), 2500);
  };

  return (
    <div
      className="p-3 flex flex-col gap-3"
      style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
    >
      <h3 className="text-[15px] font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
        Your Visibility
      </h3>

      {/* Donuts */}
      <div className="flex items-center justify-center gap-8">
        <DonutChart
          value={VISIBILITY.cited}
          label="Cited"
          color="var(--accent)"
          rawCount={citedCount}
          totalCount={VISIBILITY.totalQueries}
        />
        <DonutChart
          value={VISIBILITY.mentioned}
          label="Mentioned"
          color="var(--accent-hover)"
          rawCount={mentionedCount}
          totalCount={VISIBILITY.totalQueries}
        />
      </div>

      {/* Gap CTA */}
      <div className="relative">
        <button
          onClick={handleGapClick}
          className="w-full flex items-center gap-3 p-3 rounded-md text-left transition-colors"
          style={{
            background: 'rgba(245, 166, 35, 0.08)',
            border: '1px solid rgba(245, 166, 35, 0.2)',
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(245, 166, 35, 0.4)'; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(245, 166, 35, 0.2)'; }}
        >
          <span className="text-[20px] font-semibold flex-shrink-0" style={{ fontFamily: 'var(--font-mono)', color: '#F5A623' }}>
            {gapPct}%
          </span>
          <div>
            <div className="text-[12px] font-medium" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
              Mention-to-Citation Gap
            </div>
            <div className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
              {gapQueries} queries mention you without citing — View queries &rarr;
            </div>
          </div>
        </button>

        {toastVisible && (
          <div
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-md text-[12px] font-medium whitespace-nowrap z-50"
            style={{
              background: 'rgba(17,24,28,0.92)',
              color: '#EDEDED',
              backdropFilter: 'blur(8px)',
              boxShadow: 'var(--shadow-float)',
            }}
          >
            View in Prompt Tracking &rarr; mentioned but not cited queries
          </div>
        )}
      </div>

      <p className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
        You&apos;re mentioned in 89% of tracked queries but only cited (with a link) in 67%.
        The gap represents opportunities to convert mentions into citations by improving content structure.
      </p>

      {/* Sentiment */}
      <div
        className="p-3"
        style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
      >
        <h4 className="text-[13px] font-semibold mb-2" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
          Citation Sentiment
        </h4>
        <SentimentBars />
      </div>

      {/* Context Categories */}
      <div className="grid grid-cols-3 gap-2">
        {CONTEXT_CATEGORIES.map((cat) => (
          <div
            key={cat.category}
            className="p-2 flex flex-col items-center gap-0.5"
            style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)' }}
          >
            <span className="text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
              {cat.category}
            </span>
            <span className="text-[16px] font-semibold" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {cat.percentage}%
            </span>
          </div>
        ))}
      </div>
      <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
        When AI engines mention you, the context is overwhelmingly positive (72%). Negative mentions are primarily around pricing concerns.
      </p>
    </div>
  );
}
