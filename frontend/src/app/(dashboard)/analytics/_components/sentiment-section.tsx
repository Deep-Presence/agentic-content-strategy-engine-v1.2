'use client';

import { SENTIMENT_CATEGORIES } from './data';

function DonutChart({ size = 120, strokeWidth = 16 }: { size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let offset = 0;
  const segments = SENTIMENT_CATEGORIES.map(cat => {
    const length = (cat.percentage / 100) * circumference;
    const segment = { ...cat, offset, length };
    offset += length;
    return segment;
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke="var(--border)"
        strokeWidth={strokeWidth}
      />
      {segments.map(seg => (
        <circle
          key={seg.name}
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={seg.color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${seg.length} ${circumference - seg.length}`}
          strokeDashoffset={-seg.offset}
          strokeLinecap="butt"
        />
      ))}
    </svg>
  );
}

export function SentimentSection() {
  const positive = SENTIMENT_CATEGORIES.filter(c =>
    ['Recommendation', 'Comparison', 'Feature mention'].includes(c.name),
  ).reduce((s, c) => s + c.percentage, 0);
  const negative = SENTIMENT_CATEGORIES.find(c => c.name === 'Criticism')?.percentage || 0;

  return (
    <div
      className="rounded-[var(--radius-md)]"
      style={{ border: '1px solid var(--border)', background: 'var(--surface)', padding: 14 }}
    >
      <h2
        className="text-[16px] font-semibold mb-4"
        style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
      >
        How AI Engines Talk About You
      </h2>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {/* Left: Donut */}
        <div style={{ flexShrink: 0, position: 'relative' }}>
          <DonutChart size={120} strokeWidth={16} />
          {/* Center text */}
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                fontSize: 20,
                fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                color: 'var(--success)',
                lineHeight: 1,
              }}
            >
              {positive}%
            </div>
            <div
              style={{
                fontSize: 9,
                color: 'var(--text-tertiary)',
                fontFamily: 'var(--font-body)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              positive
            </div>
          </div>
        </div>

        {/* Right: Stats + insight */}
        <div style={{ flex: 1 }}>
          {/* Compact category list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
            {SENTIMENT_CATEGORIES.map(cat => (
              <div key={cat.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 2,
                    background: cat.color,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-body)',
                    flex: 1,
                  }}
                >
                  {cat.name}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-primary)',
                    minWidth: 32,
                    textAlign: 'right',
                  }}
                >
                  {cat.percentage}%
                </span>
              </div>
            ))}
          </div>

          {/* Insight summary */}
          <div
            style={{
              fontSize: 12,
              lineHeight: 1.6,
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font-body)',
              padding: 10,
              background: 'var(--bg)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
            }}
          >
            <span style={{ color: 'var(--success)', fontWeight: 600 }}>{positive}% positive</span> — mostly
            recommendations for non-technical teams.
            <span style={{ color: 'var(--error)', fontWeight: 600 }}> {negative}% criticism</span> relates to
            pricing transparency.
          </div>
        </div>
      </div>
    </div>
  );
}
