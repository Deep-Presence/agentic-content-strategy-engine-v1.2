'use client';

import { sortedDriftData, PLATFORM_DOMAINS, type DriftStatus } from './data';

function Favicon({ domain, size = 14 }: { domain: string; size?: number }) {
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

const STATUS_CONFIG: Record<DriftStatus, {
  rowBg: string;
  pillBg: string;
  pillText: string;
  label: string;
}> = {
  lost: {
    rowBg: 'rgba(229, 72, 77, 0.06)',
    pillBg: 'var(--error)',
    pillText: '#FFFFFF',
    label: 'LOST',
  },
  at_risk: {
    rowBg: 'rgba(245, 166, 35, 0.06)',
    pillBg: 'var(--warning)',
    pillText: '#11181C',
    label: 'AT RISK',
  },
  stable: {
    rowBg: 'transparent',
    pillBg: 'var(--success)',
    pillText: '#FFFFFF',
    label: 'STABLE',
  },
  never_had: {
    rowBg: 'transparent',
    pillBg: 'var(--text-tertiary)',
    pillText: '#FFFFFF',
    label: 'NEVER HAD',
  },
};

interface DriftTrackerProps {
  onQueryClick: (query: string) => void;
  onCompetitorClick: (domain: string) => void;
}

export function DriftTracker({ onQueryClick, onCompetitorClick }: DriftTrackerProps) {
  const showToast = (msg: string) => {
    // Simple toast using a temporary div
    const el = document.createElement('div');
    el.textContent = msg;
    Object.assign(el.style, {
      position: 'fixed',
      bottom: '20px',
      right: '20px',
      padding: '8px 16px',
      background: 'var(--surface-raised)',
      border: '1px solid var(--border)',
      borderRadius: '4px',
      fontSize: '12px',
      color: 'var(--text-primary)',
      zIndex: '9999',
      boxShadow: 'var(--shadow-float)',
    });
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  };

  return (
    <div className="rounded-sm overflow-hidden" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div className="px-3 pt-3 pb-2" style={{ borderBottom: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Citation Drift Tracker
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          Early warning system — citations you hold, are losing, or never had
        </p>
      </div>

      <table className="w-full">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th className="text-left" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px 8px 8px 12px' }}>
              Query
            </th>
            <th className="text-right" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px', width: '90px' }}>
              Drift Score
            </th>
            <th className="text-left" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px', width: '130px' }}>
              Took Over
            </th>
            <th className="text-left" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px', width: '110px' }}>
              Lost On
            </th>
            <th className="text-center" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px', width: '100px' }}>
              Status
            </th>
            <th className="text-right" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '8px 12px 8px 8px', width: '100px' }}>
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedDriftData.map((row) => {
            const config = STATUS_CONFIG[row.status];
            return (
              <tr
                key={row.id}
                className="transition-colors cursor-pointer"
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  background: config.rowBg,
                  height: '40px',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = config.rowBg)}
              >
                <td style={{ padding: '6px 8px 6px 12px' }}>
                  <button
                    style={{
                      fontSize: '13px',
                      color: 'var(--text-primary)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                    onClick={() => onQueryClick(row.query)}
                  >
                    {row.query}
                  </button>
                </td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '13px',
                    fontWeight: 500,
                    color: 'var(--text-primary)',
                  }}>
                    {row.drift.toFixed(2)}
                  </span>
                </td>
                <td style={{ padding: '6px 8px' }}>
                  {row.tookOver ? (
                    <button
                      className="flex items-center gap-1.5"
                      onClick={() => onCompetitorClick(row.tookOver!)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                    >
                      <Favicon domain={row.tookOver} size={14} />
                      <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{row.tookOver}</span>
                    </button>
                  ) : (
                    <span style={{ fontSize: '13px', color: 'var(--text-tertiary)' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '6px 8px' }}>
                  {row.lostOn ? (
                    <div className="flex items-center gap-1.5">
                      <Favicon domain={PLATFORM_DOMAINS[row.lostOn] || ''} size={14} />
                      <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{row.lostOn}</span>
                    </div>
                  ) : (
                    <span style={{ fontSize: '13px', color: 'var(--text-tertiary)' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      height: '22px',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '10px',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      background: config.pillBg,
                      color: config.pillText,
                    }}
                  >
                    {config.label}
                  </span>
                </td>
                <td style={{ padding: '6px 12px 6px 8px', textAlign: 'right' }}>
                  {row.status === 'lost' && (
                    <button
                      onClick={() => showToast('Added to content queue')}
                      style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: 'var(--error)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                      }}
                    >
                      Recapture →
                    </button>
                  )}
                  {row.status === 'at_risk' && (
                    <button
                      onClick={() => showToast('Added to content queue')}
                      style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: 'var(--warning)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                      }}
                    >
                      Defend →
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
