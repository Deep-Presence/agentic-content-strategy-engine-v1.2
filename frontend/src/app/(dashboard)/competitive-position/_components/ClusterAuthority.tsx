'use client';

import { CLUSTER_SOV } from './data';

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

const ACTION_STYLES: Record<string, { bg: string; text: string }> = {
  defend: { bg: '#34B27B', text: '#FFFFFF' },
  close_gap: { bg: 'var(--accent)', text: '#FFFFFF' },
  invest: { bg: '#F5A623', text: '#11181C' },
  priority: { bg: '#E5484D', text: '#FFFFFF' },
};

const ACTION_LABELS: Record<string, string> = {
  defend: 'DEFEND',
  close_gap: 'CLOSE GAP',
  invest: 'INVEST',
  priority: 'PRIORITY',
};

function DualBar({ you, comp }: { you: number; comp: number }) {
  const maxVal = Math.max(you, comp, 100);
  return (
    <div className="flex items-center gap-2">
      {/* Your bar */}
      <div className="flex items-center gap-1" style={{ width: '140px' }}>
        <div
          className="relative rounded-sm overflow-hidden"
          style={{ width: '120px', height: '18px', background: 'var(--border)', opacity: 0.3 }}
        >
          <div
            className="absolute inset-0 rounded-sm"
            style={{
              width: '120px',
              height: '18px',
              background: 'var(--border-subtle)',
            }}
          />
        </div>
        <div
          className="absolute rounded-sm flex items-center"
          style={{
            width: `${Math.max((you / maxVal) * 120, 8)}px`,
            height: '18px',
            background: 'var(--accent)',
            position: 'relative',
          }}
        >
          {you > 20 && (
            <span style={{
              fontSize: '10px',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              color: '#FFFFFF',
              paddingLeft: '4px',
            }}>
              {you}
            </span>
          )}
        </div>
        {you <= 20 && (
          <span style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            fontWeight: 500,
            color: 'var(--accent)',
          }}>
            {you}
          </span>
        )}
      </div>
      <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>vs</span>
      {/* Competitor bar */}
      <div className="flex items-center gap-1" style={{ width: '140px' }}>
        <div
          className="rounded-sm flex items-center"
          style={{
            width: `${Math.max((comp / maxVal) * 120, 8)}px`,
            height: '18px',
            background: 'var(--text-tertiary)',
            position: 'relative',
          }}
        >
          {comp > 20 && (
            <span style={{
              fontSize: '10px',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              color: '#FFFFFF',
              paddingLeft: '4px',
            }}>
              {comp}
            </span>
          )}
        </div>
        {comp <= 20 && (
          <span style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            fontWeight: 500,
            color: 'var(--text-secondary)',
          }}>
            {comp}
          </span>
        )}
      </div>
    </div>
  );
}

interface ClusterAuthorityTableProps {
  onCompetitorClick: (domain: string) => void;
}

export function ClusterAuthorityTable({ onCompetitorClick }: ClusterAuthorityTableProps) {
  return (
    <div className="rounded-sm overflow-hidden" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div className="px-3 pt-3 pb-2" style={{ borderBottom: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Competitor SOV by Cluster
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          Authority score comparison per intent cluster — sorted by your strength
        </p>
      </div>

      <table className="w-full">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th className="text-left px-2 py-2" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', paddingLeft: '12px' }}>
              Cluster
            </th>
            <th className="text-left px-2 py-2" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', width: '340px' }}>
              Authority
            </th>
            <th className="text-left px-2 py-2" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
              #1 Competitor
            </th>
            <th className="text-right px-2 py-2" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', paddingRight: '12px', width: '110px' }}>
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {CLUSTER_SOV.map((row) => {
            const actionStyle = ACTION_STYLES[row.action];
            return (
              <tr
                key={row.cluster}
                className="transition-colors cursor-pointer"
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  height: '40px',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '')}
              >
                <td style={{ padding: '6px 8px 6px 12px', fontSize: '13px', color: 'var(--text-primary)' }}>
                  {row.cluster}
                </td>
                <td style={{ padding: '6px 8px' }}>
                  <DualBar you={row.you} comp={row.comp} />
                </td>
                <td style={{ padding: '6px 8px' }}>
                  <button
                    className="flex items-center gap-1.5"
                    onClick={() => onCompetitorClick(row.compDomain)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                  >
                    <Favicon domain={row.compDomain} size={14} />
                    <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{row.compDomain}</span>
                  </button>
                </td>
                <td style={{ padding: '6px 12px 6px 8px', textAlign: 'right' }}>
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
                      background: actionStyle.bg,
                      color: actionStyle.text,
                    }}
                  >
                    {ACTION_LABELS[row.action]}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
