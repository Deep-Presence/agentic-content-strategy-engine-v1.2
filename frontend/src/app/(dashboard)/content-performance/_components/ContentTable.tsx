'use client';

import { useState, useMemo } from 'react';
import { ChevronRight, ArrowUpDown } from 'lucide-react';
import type { ContentPiece, PlatformCitations, LifecycleStage } from './data';
import { LIFECYCLE_CONFIG, PLATFORM_LIST, formatTraffic } from './data';

type SortKey = 'title' | 'citations' | 'cps' | 'velocity' | 'traffic' | 'structuralScore' | 'freshnessDays' | 'lifecycle' | 'cannibalization' | 'aiReferrals';
type SortDir = 'asc' | 'desc';

interface ContentTableProps {
  pieces: ContentPiece[];
  onRowClick: (piece: ContentPiece) => void;
  searchQuery: string;
}

function getFreshnessLabel(days: number): { label: string; bg: string; text: string } {
  if (days <= 30) return { label: 'Fresh', bg: 'var(--success)', text: '#FFFFFF' };
  if (days <= 60) return { label: 'Aging', bg: '#F5A623', text: '#11181C' };
  return { label: 'Stale', bg: '#E5484D', text: '#FFFFFF' };
}

function getLifecycleStyle(lc: LifecycleStage): { bg: string; text: string } {
  switch (lc) {
    case 'growing': return { bg: 'var(--accent)', text: '#FFFFFF' };
    case 'peaking': return { bg: '#F5A623', text: '#11181C' };
    case 'stable': return { bg: 'rgba(104,112,118,0.2)', text: 'var(--text-primary)' };
    case 'declining': return { bg: '#E87C3F', text: '#FFFFFF' };
    case 'stale': return { bg: '#E5484D', text: '#FFFFFF' };
  }
}

function getCPSColor(cps: number): string {
  if (cps >= 0.6) return 'var(--success)';
  if (cps >= 0.45) return '#F5A623';
  return '#E5484D';
}

function getCitationColor(c: number): string {
  if (c >= 40) return 'var(--success)';
  if (c >= 20) return '#F5A623';
  return 'var(--text-primary)';
}

function getStructuralBarColor(score: number): string {
  if (score >= 70) return 'var(--success)';
  if (score >= 40) return '#F5A623';
  return '#E5484D';
}

function PlatformDots({ platforms }: { platforms: PlatformCitations }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
      {PLATFORM_LIST.map((p) => {
        const cited = platforms[p.key];
        return cited ? (
          <img
            key={p.key}
            src={`https://www.google.com/s2/favicons?domain=${p.domain}&sz=24`}
            alt={p.name} width={12} height={12} style={{ borderRadius: 2 }}
          />
        ) : (
          <div key={p.key} style={{
            width: 12, height: 12, borderRadius: '50%',
            border: '1px solid var(--border)', background: 'transparent',
          }} />
        );
      })}
    </div>
  );
}

export function ContentTable({ pieces, onRowClick, searchQuery }: ContentTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('citations');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const filtered = useMemo(() => {
    if (!searchQuery) return pieces;
    const q = searchQuery.toLowerCase();
    return pieces.filter((p) =>
      p.title.toLowerCase().includes(q) || p.url.toLowerCase().includes(q) || p.cluster.toLowerCase().includes(q)
    );
  }, [pieces, searchQuery]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
  }, [filtered, sortKey, sortDir]);

  const cols: { key: SortKey; label: string; w: string }[] = [
    { key: 'title', label: 'Page', w: '22%' },
    { key: 'citations', label: 'Citations', w: '6%' },
    { key: 'cps', label: 'CPS', w: '6%' },
    { key: 'velocity', label: 'Velocity', w: '6%' },
    { key: 'traffic', label: 'Traffic', w: '7%' },
    { key: 'structuralScore', label: 'Structural', w: '6%' },
    { key: 'freshnessDays', label: 'Freshness', w: '7%' },
    { key: 'lifecycle', label: 'Lifecycle', w: '7%' },
    { key: 'cannibalization', label: 'Cannibal.', w: '5%' },
    { key: 'aiReferrals', label: 'AI Referrals', w: '7%' },
  ];

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: 4, overflow: 'hidden' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {cols.map((col) => (
                <th
                  key={col.key}
                  style={{
                    width: col.w, padding: '8px 8px', textAlign: 'left',
                    fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
                    letterSpacing: '0.05em', color: 'var(--text-secondary)',
                    cursor: 'pointer', userSelect: 'none',
                  }}
                  onClick={() => handleSort(col.key)}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    {col.label}
                    <ArrowUpDown size={10} strokeWidth={1.5} style={{ color: sortKey === col.key ? 'var(--accent)' : 'var(--text-tertiary)', opacity: sortKey === col.key ? 1 : 0.4 }} />
                  </span>
                </th>
              ))}
              <th style={{ width: '8%', padding: '8px', textAlign: 'left', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>Cluster</th>
              <th style={{ width: '10%', padding: '8px', textAlign: 'left', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>Platforms</th>
              <th style={{ width: '3%', padding: '8px' }} />
            </tr>
          </thead>
          <tbody>
            {sorted.map((piece) => {
              const freshness = getFreshnessLabel(piece.freshnessDays);
              const lcConfig = LIFECYCLE_CONFIG[piece.lifecycle];
              const lcStyle = getLifecycleStyle(piece.lifecycle);
              const velocityArrow = piece.velocityTrend === 'up' ? '\u2191' : piece.velocityTrend === 'down' ? '\u2193' : '\u2014';
              const rowBg =
                piece.lifecycle === 'stale' ? 'rgba(229, 72, 77, 0.04)' :
                piece.lifecycle === 'declining' ? 'rgba(245, 166, 35, 0.04)' : 'transparent';
              const truncUrl = piece.url.length > 32 ? piece.url.slice(0, 32) + '\u2026' : piece.url;

              return (
                <tr
                  key={piece.id}
                  onClick={() => onRowClick(piece)}
                  style={{ borderBottom: '1px solid var(--border-subtle)', height: 44, cursor: 'pointer', background: rowBg, transition: 'background 0.12s' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = rowBg)}
                >
                  {/* Page: title + URL subtitle */}
                  <td style={{ padding: '4px 8px' }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {piece.title}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 1 }}>
                      {truncUrl}
                    </div>
                  </td>
                  {/* Citations */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: getCitationColor(piece.citations) }}>
                      {piece.citations}
                    </span>
                  </td>
                  {/* CPS */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: getCPSColor(piece.cps) }}>
                      {piece.cps.toFixed(3)}
                    </span>
                  </td>
                  {/* Velocity */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>{piece.velocity}</span>
                    <span style={{ fontSize: 13, marginLeft: 3, color: piece.velocityTrend === 'up' ? 'var(--success)' : piece.velocityTrend === 'down' ? '#E5484D' : 'var(--text-tertiary)' }}>{velocityArrow}</span>
                  </td>
                  {/* Traffic */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {formatTraffic(piece.traffic)}
                    </span>
                  </td>
                  {/* Structural: score + mini bar */}
                  <td style={{ padding: '6px 8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', width: 22 }}>{piece.structuralScore}</span>
                      <div style={{ width: 36, height: 6, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
                        <div style={{ width: `${piece.structuralScore}%`, height: '100%', borderRadius: 3, background: getStructuralBarColor(piece.structuralScore) }} />
                      </div>
                    </div>
                  </td>
                  {/* Freshness */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', height: 20, padding: '0 8px', borderRadius: 10, fontSize: 11, fontWeight: 500, background: freshness.bg, color: freshness.text }}>{freshness.label}</span>
                  </td>
                  {/* Lifecycle */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, height: 20, padding: '0 8px', borderRadius: 10, fontSize: 11, fontWeight: 500, background: lcStyle.bg, color: lcStyle.text }}>{lcConfig.icon} {lcConfig.label}</span>
                  </td>
                  {/* Cannibalization */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: piece.cannibalization > 0 ? '#F5A623' : 'var(--text-tertiary)' }}>
                      {piece.cannibalization > 0 ? piece.cannibalization : '\u2014'}
                    </span>
                  </td>
                  {/* AI Referrals */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {formatTraffic(piece.aiReferrals)}
                    </span>
                  </td>
                  {/* Cluster */}
                  <td style={{ padding: '6px 8px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', height: 20, padding: '0 8px', borderRadius: 10, fontSize: 11, fontWeight: 500, background: piece.clusterColor, color: '#FFFFFF' }}>{piece.cluster}</span>
                  </td>
                  {/* Platforms */}
                  <td style={{ padding: '6px 8px' }}><PlatformDots platforms={piece.platforms} /></td>
                  {/* Chevron */}
                  <td style={{ padding: '6px 8px', textAlign: 'right' }}><ChevronRight size={14} strokeWidth={1.5} style={{ color: 'var(--text-secondary)' }} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {/* Footer */}
      <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-secondary)' }}>
        {filtered.length} published piece{filtered.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
