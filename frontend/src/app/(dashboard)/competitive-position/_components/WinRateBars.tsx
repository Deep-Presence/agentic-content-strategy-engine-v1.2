'use client';

import { WIN_RATES } from './data';

function Favicon({ domain, size = 16 }: { domain: string; size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size + 4}`}
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

interface WinRateBarsProps {
  onCompetitorClick: (domain: string) => void;
}

export function WinRateBars({ onCompetitorClick }: WinRateBarsProps) {
  return (
    <div className="rounded-sm overflow-hidden" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div className="px-3 pt-3 pb-2">
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Head-to-Head Win Rate
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          When competing for the same query, how often are you cited instead?
        </p>
      </div>

      <div className="px-3 pb-3 space-y-2">
        {WIN_RATES.map((entry) => {
          const pct = Math.round(entry.rate * 100);
          const color = pct >= 50
            ? 'var(--success)'
            : pct >= 30
            ? 'var(--accent)'
            : 'var(--error)';

          return (
            <div
              key={entry.domain}
              className="flex items-center gap-3 cursor-pointer group"
              onClick={() => onCompetitorClick(entry.domain)}
            >
              <div className="flex items-center gap-2 shrink-0" style={{ width: '120px' }}>
                <Favicon domain={entry.domain} size={16} />
                <span style={{
                  fontSize: '13px',
                  color: 'var(--text-secondary)',
                }}>
                  {entry.domain}
                </span>
              </div>
              <div
                className="flex-1 rounded-sm overflow-hidden relative"
                style={{ height: '24px', background: 'rgba(var(--border), 0.2)' }}
              >
                {/* Background track */}
                <div
                  className="absolute inset-0"
                  style={{ background: 'var(--border)', opacity: 0.2 }}
                />
                {/* Bar fill */}
                <div
                  className="absolute inset-y-0 left-0 rounded-sm transition-all duration-300"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
              </div>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '13px',
                fontWeight: 500,
                color: 'var(--text-primary)',
                width: '40px',
                textAlign: 'right',
              }}>
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
