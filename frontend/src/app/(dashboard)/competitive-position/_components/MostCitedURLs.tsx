'use client';

import { MOST_CITED_URLS, PLATFORM_DOMAINS } from './data';

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

function PlatformLogos({ platforms }: { platforms: string[] }) {
  return (
    <div className="flex items-center gap-1">
      {platforms.map((p) => {
        const domain = PLATFORM_DOMAINS[p] || '';
        return (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={p}
            src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
            alt={p}
            width={16}
            height={16}
            title={p}
            style={{ borderRadius: 2 }}
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              if (!target.dataset.fallback) {
                target.dataset.fallback = '1';
                target.src = `https://logo.clearbit.com/${domain}`;
              }
            }}
          />
        );
      })}
    </div>
  );
}

interface MostCitedURLsProps {
  onCompetitorClick: (domain: string) => void;
}

export function MostCitedURLs({ onCompetitorClick }: MostCitedURLsProps) {
  return (
    <div className="rounded-sm overflow-hidden" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div className="px-3 pt-3 pb-2" style={{ borderBottom: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Most-Cited Competitor URLs
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          Specific competitor pages cited most across AI platforms
        </p>
      </div>

      <table className="w-full">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th className="text-left" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px 8px 8px 12px' }}>
              URL
            </th>
            <th className="text-left" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px', width: '120px' }}>
              Domain
            </th>
            <th className="text-right" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px', width: '80px' }}>
              Influence
            </th>
            <th className="text-center" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px', width: '120px' }}>
              Cited On
            </th>
            <th className="text-center" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px', width: '120px' }}>
              Your Overlap
            </th>
            <th className="text-right" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px 12px 8px 8px', width: '80px' }}>
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {MOST_CITED_URLS.map((row) => (
            <tr
              key={row.url}
              className="transition-colors cursor-pointer"
              style={{
                borderBottom: '1px solid var(--border-subtle)',
                height: '40px',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = '')}
            >
              <td style={{ padding: '6px 8px 6px 12px' }}>
                <span
                  className="block truncate"
                  style={{ fontSize: '13px', color: 'var(--text-primary)', maxWidth: '300px' }}
                  title={row.url}
                >
                  {row.url}
                </span>
              </td>
              <td style={{ padding: '6px 8px' }}>
                <button
                  className="flex items-center gap-1.5"
                  onClick={() => onCompetitorClick(row.domain)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  <Favicon domain={row.domain} size={16} />
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{row.domain}</span>
                </button>
              </td>
              <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '13px',
                  fontWeight: 500,
                  color: 'var(--text-primary)',
                }}>
                  {row.influence}
                </span>
              </td>
              <td style={{ padding: '6px 8px' }}>
                <div className="flex justify-center">
                  <PlatformLogos platforms={row.platforms} />
                </div>
              </td>
              <td style={{ padding: '6px 8px' }}>
                <div className="flex items-center justify-center gap-2">
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '13px',
                    color: 'var(--text-secondary)',
                  }}>
                    {row.overlap}
                  </span>
                  {/* Mini progress bar */}
                  <div
                    className="rounded-full overflow-hidden"
                    style={{ width: '40px', height: '4px', background: 'var(--border)' }}
                  >
                    <div
                      className="rounded-full"
                      style={{
                        width: `${row.overlapRatio * 100}%`,
                        height: '4px',
                        background: 'var(--accent)',
                      }}
                    />
                  </div>
                </div>
              </td>
              <td style={{ padding: '6px 12px 6px 8px', textAlign: 'right' }}>
                <button style={{
                  fontSize: '12px',
                  fontWeight: 500,
                  color: 'var(--accent)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}>
                  Analyze →
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
