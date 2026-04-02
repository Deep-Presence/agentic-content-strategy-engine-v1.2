'use client';

import { useState } from 'react';
import { CITATION_URLS, PLATFORMS } from './mock-data';
import { SlideDrawer } from './SlideDrawer';

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

function getPlatformDomain(key: string): string {
  return PLATFORMS.find(p => p.key === key)?.domain || '';
}

function getPlatformName(key: string): string {
  return PLATFORMS.find(p => p.key === key)?.name || key;
}

type CitationUrl = typeof CITATION_URLS[number];

function DrawerContent({ row }: { row: CitationUrl }) {
  return (
    <div className="space-y-5 pt-5">
      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {[
          { label: 'Total Citations', value: String(row.citations), color: 'var(--text-primary)' },
          { label: 'CPS', value: row.cps.toFixed(3), color: row.cps >= 0.6 ? 'var(--success)' : row.cps >= 0.45 ? 'var(--warning)' : 'var(--error)' },
          { label: 'Velocity', value: row.velocity.toFixed(1), color: row.velocity >= 3.0 ? 'var(--success)' : 'var(--text-primary)' },
        ].map(s => (
          <div key={s.label} className="border border-border rounded-md" style={{ padding: '10px 12px', background: 'var(--bg)' }}>
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', marginBottom: 4 }}>
              {s.label}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 600, color: s.color }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      {/* Citing platforms */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', marginBottom: 8 }}>
          Citing Platforms
        </div>
        <div className="space-y-2">
          {row.platforms.map(pk => (
            <div key={pk} className="flex items-center gap-2 border border-border rounded-sm" style={{ padding: '6px 10px', background: 'var(--bg)' }}>
              <BrandLogo domain={getPlatformDomain(pk)} size={16} />
              <span style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
                {getPlatformName(pk)}
              </span>
              <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--success)' }}>
                Active
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* URL info */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', marginBottom: 8 }}>
          URL Details
        </div>
        <div className="border border-border rounded-md" style={{ padding: '10px 12px', background: 'var(--bg)' }}>
          <div className="space-y-3">
            {[
              { label: 'Full URL', value: row.url },
              { label: 'First Cited', value: row.firstCited },
              { label: 'Platforms Count', value: `${row.platforms.length} of 5` },
            ].map(item => (
              <div key={item.label}>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', marginBottom: 2 }}>
                  {item.label}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function CitationUrlsTable() {
  const [selectedRow, setSelectedRow] = useState<CitationUrl | null>(null);

  return (
    <div>
      <h2
        className="mb-1"
        style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
      >
        Citation URLs
      </h2>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-body)', marginBottom: 10 }}>
        Every URL cited by AI platforms, ranked by citation count
      </p>

      <div className="border border-border rounded-md overflow-hidden">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
              {['URL', 'TITLE', 'CITATIONS', 'PLATFORMS', 'CPS', 'VELOCITY'].map(h => (
                <th
                  key={h}
                  style={{
                    padding: '6px 8px',
                    textAlign: h === 'URL' || h === 'TITLE' ? 'left' : 'right',
                    fontSize: 11,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: h === 'CITATIONS' ? 'var(--accent)' : 'var(--text-tertiary)',
                    fontFamily: 'var(--font-display)',
                    background: 'var(--surface)',
                  }}
                >
                  {h === 'CITATIONS' ? `${h} \u2193` : h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {CITATION_URLS.map((row, idx) => (
              <tr
                key={row.url}
                onClick={() => setSelectedRow(row)}
                style={{
                  height: 40,
                  borderBottom: idx < CITATION_URLS.length - 1 ? '1px solid var(--border)' : 'none',
                  cursor: 'pointer',
                  transition: 'background 100ms',
                  animation: `fadeUp 300ms ease-out ${idx * 25}ms both`,
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--accent-subtle)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
              >
                <td style={{ padding: '6px 8px', fontSize: 12, fontFamily: 'var(--font-display)', color: 'var(--accent)', maxWidth: 200 }}>
                  <span className="truncate block" style={{ maxWidth: 200 }}>{row.url}</span>
                </td>
                <td style={{ padding: '6px 8px', fontSize: 13, fontWeight: 500, fontFamily: 'var(--font-display)', color: 'var(--text-primary)', maxWidth: 220 }}>
                  <span className="truncate block" style={{ maxWidth: 220 }}>{row.title}</span>
                </td>
                <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {row.citations}
                </td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4 }}>
                    {row.platforms.map(pk => (
                      <BrandLogo key={pk} domain={getPlatformDomain(pk)} size={12} />
                    ))}
                  </div>
                </td>
                <td style={{
                  padding: '6px 8px',
                  textAlign: 'right',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 13,
                  color: row.cps >= 0.6 ? 'var(--success)' : row.cps >= 0.45 ? 'var(--warning)' : 'var(--error)',
                }}>
                  {row.cps.toFixed(3)}
                </td>
                <td style={{
                  padding: '6px 8px',
                  textAlign: 'right',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 13,
                  color: row.velocity >= 3.0 ? 'var(--success)' : 'var(--text-primary)',
                }}>
                  {row.velocity.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SlideDrawer
        open={selectedRow !== null}
        onClose={() => setSelectedRow(null)}
        title={selectedRow?.title || ''}
        subtitle={selectedRow?.url}
      >
        {selectedRow && <DrawerContent row={selectedRow} />}
      </SlideDrawer>
    </div>
  );
}
