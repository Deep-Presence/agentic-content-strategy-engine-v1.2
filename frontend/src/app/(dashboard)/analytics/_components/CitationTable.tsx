'use client';

import { useState, useMemo } from 'react';
import { ExternalLink, ArrowUp, ArrowDown, Minus, ChevronUp, ChevronDown, ChevronRight } from 'lucide-react';
import { CITATION_URLS, PLATFORM_DOMAINS, PER_PLATFORM_CITATIONS, type CitationURL } from './data';
import { BrandLogo } from './BrandLogo';

type SortKey = 'citations' | 'queries' | 'cps' | 'velocity' | 'firstCited';
type SortDir = 'asc' | 'desc';

const PLATFORM_KEYS = ['chatgpt', 'claude', 'perplexity', 'google_ai', 'gemini'] as const;
const PLATFORM_LABELS: Record<string, string> = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  perplexity: 'Perplexity',
  google_ai: 'Google AI',
  gemini: 'Gemini',
};

export function CitationTable({ onRowClick }: { onRowClick: (url: CitationURL) => void }) {
  const [sortKey, setSortKey] = useState<SortKey>('citations');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [expandedUrl, setExpandedUrl] = useState<string | null>(null);
  const [hoveredPlatform, setHoveredPlatform] = useState<{ url: string; platform: string; x: number; y: number } | null>(null);

  const sorted = useMemo(() => {
    return [...CITATION_URLS].sort((a, b) => {
      let aVal: number | string = a[sortKey];
      let bVal: number | string = b[sortKey];
      if (sortKey === 'firstCited') {
        aVal = new Date(a.firstCited).getTime();
        bVal = new Date(b.firstCited).getTime();
      }
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDir === 'desc' ? bVal - aVal : aVal - bVal;
      }
      return 0;
    });
  }, [sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const handleRowClick = (row: CitationURL) => {
    if (expandedUrl === row.url) {
      setExpandedUrl(null);
    } else {
      setExpandedUrl(row.url);
    }
  };

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return null;
    return sortDir === 'desc' ? <ChevronDown size={10} /> : <ChevronUp size={10} />;
  };

  const velocityBorderColor = (trend: CitationURL['velocityTrend']) => {
    if (trend === 'up') return 'var(--success)';
    if (trend === 'down') return 'var(--error)';
    return 'var(--text-tertiary)';
  };

  return (
    <div
      className="relative"
      style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)', overflow: 'hidden' }}
    >
      <div className="px-3 py-2">
        <h3 className="text-[15px] font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>
          Citation URLs
        </h3>
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          Every URL cited by AI platforms, ranked by citation count
        </p>
      </div>

      {/* Platform dot tooltip */}
      {hoveredPlatform && (
        <div
          className="fixed z-[100] px-2 py-1.5 rounded-md text-[11px] whitespace-nowrap pointer-events-none"
          style={{
            left: hoveredPlatform.x + 12,
            top: hoveredPlatform.y - 10,
            background: 'rgba(17,24,28,0.92)',
            backdropFilter: 'blur(8px)',
            color: '#EDEDED',
            fontFamily: 'var(--font-display)',
            boxShadow: 'var(--shadow-float)',
          }}
        >
          {(() => {
            const row = CITATION_URLS.find((u) => u.url === hoveredPlatform.url);
            const pk = hoveredPlatform.platform as keyof CitationURL['platforms'];
            const cited = row?.platforms[pk];
            const perPlat = PER_PLATFORM_CITATIONS[hoveredPlatform.url]?.[hoveredPlatform.platform];
            if (cited && perPlat) {
              return `Cited on ${PLATFORM_LABELS[hoveredPlatform.platform]} — ${perPlat.citations} times`;
            }
            return `Not cited on ${PLATFORM_LABELS[hoveredPlatform.platform]} — consider optimizing`;
          })()}
        </div>
      )}

      <table className="w-full" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
            <Th width="25%">URL</Th>
            <Th width="18%">Title</Th>
            <ThSort width="8%" col="citations" sortKey={sortKey} onClick={() => handleSort('citations')}>
              Citations <SortIcon col="citations" />
            </ThSort>
            <Th width="15%">Platforms</Th>
            <ThSort width="7%" col="queries" sortKey={sortKey} onClick={() => handleSort('queries')}>
              Queries <SortIcon col="queries" />
            </ThSort>
            <ThSort width="7%" col="cps" sortKey={sortKey} onClick={() => handleSort('cps')}>
              CPS <SortIcon col="cps" />
            </ThSort>
            <ThSort width="10%" col="firstCited" sortKey={sortKey} onClick={() => handleSort('firstCited')}>
              First Cited <SortIcon col="firstCited" />
            </ThSort>
            <ThSort width="7%" col="velocity" sortKey={sortKey} onClick={() => handleSort('velocity')}>
              Velocity <SortIcon col="velocity" />
            </ThSort>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const isExpanded = expandedUrl === row.url;
            const perPlat = PER_PLATFORM_CITATIONS[row.url];

            return (
              <TableRowGroup key={row.url}>
                {/* Main row */}
                <tr
                  className="cursor-pointer transition-colors"
                  style={{
                    borderBottom: isExpanded ? 'none' : '1px solid var(--border)',
                    height: 40,
                    borderLeft: `3px solid ${velocityBorderColor(row.velocityTrend)}`,
                  }}
                  onClick={() => handleRowClick(row)}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--accent-subtle)'; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                >
                  <Td>
                    <div className="flex items-center gap-1">
                      <ChevronRight
                        size={10}
                        style={{
                          color: 'var(--text-tertiary)',
                          flexShrink: 0,
                          transform: isExpanded ? 'rotate(90deg)' : 'none',
                          transition: 'transform 150ms',
                        }}
                      />
                      <span className="text-[12px] truncate" style={{ color: 'var(--accent)', fontFamily: 'var(--font-display)' }}>
                        {row.url}
                      </span>
                      <ExternalLink size={10} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
                    </div>
                  </Td>
                  <Td>
                    <span className="text-[13px] font-medium truncate block" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                      {row.title}
                    </span>
                  </Td>
                  <Td>
                    <span className="text-[13px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                      {row.citations}
                    </span>
                  </Td>
                  <Td>
                    <div className="flex items-center gap-1">
                      {PLATFORM_KEYS.map((pk) => {
                        const cited = row.platforms[pk];
                        const domain = PLATFORM_DOMAINS[PLATFORM_LABELS[pk]];
                        return cited ? (
                          <span
                            key={pk}
                            className="relative"
                            onMouseEnter={(e) => {
                              const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                              setHoveredPlatform({ url: row.url, platform: pk, x: rect.right, y: rect.top });
                            }}
                            onMouseLeave={() => setHoveredPlatform(null)}
                          >
                            <BrandLogo domain={domain} size={12} />
                          </span>
                        ) : (
                          <span
                            key={pk}
                            className="w-[12px] h-[12px] rounded-full flex-shrink-0"
                            style={{ border: '1px solid var(--border)' }}
                            onMouseEnter={(e) => {
                              const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                              setHoveredPlatform({ url: row.url, platform: pk, x: rect.right, y: rect.top });
                            }}
                            onMouseLeave={() => setHoveredPlatform(null)}
                          />
                        );
                      })}
                    </div>
                  </Td>
                  <Td>
                    <span className="text-[13px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                      {row.queries}
                    </span>
                  </Td>
                  <Td>
                    <span
                      className="text-[13px]"
                      style={{
                        fontFamily: 'var(--font-mono)',
                        color: row.cps >= 0.6 ? 'var(--success)' : row.cps >= 0.45 ? 'var(--warning)' : 'var(--error)',
                      }}
                    >
                      {row.cps.toFixed(3)}
                    </span>
                  </Td>
                  <Td>
                    <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                      {new Date(row.firstCited).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                  </Td>
                  <Td>
                    <div className="flex items-center gap-1">
                      <span className="text-[13px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                        {row.velocity}
                      </span>
                      {row.velocityTrend === 'up' && <ArrowUp size={10} style={{ color: 'var(--success)' }} />}
                      {row.velocityTrend === 'down' && <ArrowDown size={10} style={{ color: 'var(--error)' }} />}
                      {row.velocityTrend === 'flat' && <Minus size={10} style={{ color: 'var(--text-tertiary)' }} />}
                    </div>
                  </Td>
                </tr>

                {/* Expanded inline row */}
                {isExpanded && perPlat && (
                  <tr style={{ borderBottom: '1px solid var(--border)', borderLeft: `3px solid ${velocityBorderColor(row.velocityTrend)}` }}>
                    <td colSpan={8}>
                      <div className="px-4 py-3" style={{ background: 'var(--accent-subtle)' }}>
                        <div className="flex flex-col gap-1.5">
                          {PLATFORM_KEYS.map((pk, idx) => {
                            const data = perPlat[pk];
                            const isLast = idx === PLATFORM_KEYS.length - 1;
                            const domain = PLATFORM_DOMAINS[PLATFORM_LABELS[pk]];
                            return (
                              <div key={pk} className="flex items-center gap-2">
                                <span className="text-[11px]" style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', width: 12 }}>
                                  {isLast ? '└' : '├'}
                                </span>
                                <BrandLogo domain={domain} size={12} />
                                <span className="text-[12px] w-[72px]" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                                  {PLATFORM_LABELS[pk]}:
                                </span>
                                <span className="text-[12px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                                  {data.citations} citations
                                </span>
                                {data.citations > 0 && (
                                  <span className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                                    (cited for {data.queries} queries)
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                        <button
                          className="mt-2 text-[11px] font-medium"
                          style={{ color: 'var(--accent)' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            onRowClick(row);
                          }}
                        >
                          Open full analysis &rarr;
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </TableRowGroup>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Fragment wrapper to allow multiple <tr> per row in table body
function TableRowGroup({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function Th({ children, width }: { children: React.ReactNode; width: string }) {
  return (
    <th
      className="text-left px-2 py-1.5 text-[11px] font-semibold uppercase"
      style={{
        width,
        letterSpacing: '0.05em',
        color: 'var(--text-tertiary)',
        fontFamily: 'var(--font-display)',
      }}
    >
      {children}
    </th>
  );
}

function ThSort({
  children,
  width,
  col,
  sortKey,
  onClick,
}: {
  children: React.ReactNode;
  width: string;
  col: SortKey;
  sortKey: SortKey;
  onClick: () => void;
}) {
  return (
    <th
      className="text-left px-2 py-1.5 text-[11px] font-semibold uppercase cursor-pointer select-none"
      style={{
        width,
        letterSpacing: '0.05em',
        color: col === sortKey ? 'var(--accent)' : 'var(--text-tertiary)',
        fontFamily: 'var(--font-display)',
      }}
      onClick={onClick}
    >
      <div className="flex items-center gap-0.5">{children}</div>
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return (
    <td className="px-2" style={{ padding: '6px 8px' }}>
      {children}
    </td>
  );
}
