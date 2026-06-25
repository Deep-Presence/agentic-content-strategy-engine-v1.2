'use client';

import { useMemo } from 'react';
import { ChevronRight } from 'lucide-react';
import type { ContentCard } from '../../content-studio/_components/types';

interface UnpublishedPagesTableProps {
  cards: ContentCard[];
  searchQuery: string;
  onRowClick: (card: ContentCard) => void;
}

function formatUpdatedAt(value?: string): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function UnpublishedPagesTable({
  cards,
  searchQuery,
  onRowClick,
}: UnpublishedPagesTableProps) {
  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return cards;
    return cards.filter((card) =>
      card.title.toLowerCase().includes(q)
      || card.cluster.toLowerCase().includes(q)
      || (card.displayId ?? '').toLowerCase().includes(q),
    );
  }, [cards, searchQuery]);

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: 4, overflow: 'hidden' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {[
                ['Page', '34%'],
                ['Stage', '12%'],
                ['Gap', '10%'],
                ['Score', '10%'],
                ['Format', '12%'],
                ['Updated', '12%'],
                ['Cluster', '10%'],
              ].map(([label, width]) => (
                <th
                  key={label}
                  style={{
                    width,
                    padding: '8px',
                    textAlign: 'left',
                    fontSize: 11,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--text-secondary)',
                  }}
                >
                  {label}
                </th>
              ))}
              <th style={{ width: '3%', padding: '8px' }} />
            </tr>
          </thead>
          <tbody>
            {filtered.map((card) => (
              <tr
                key={card.id}
                onClick={() => onRowClick(card)}
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  height: 48,
                  cursor: 'pointer',
                  background: 'transparent',
                  transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--accent-subtle)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
              >
                <td style={{ padding: '4px 8px' }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {card.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 1 }}>
                    {(card.displayId ?? card.id)} · {card.readTime} min read
                  </div>
                </td>
                <td style={{ padding: '6px 8px' }}>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      height: 20,
                      padding: '0 8px',
                      borderRadius: 10,
                      fontSize: 11,
                      fontWeight: 500,
                      background: 'var(--accent-subtle)',
                      color: 'var(--accent)',
                    }}
                  >
                    Approved
                  </span>
                </td>
                <td style={{ padding: '6px 8px', fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {Math.round(card.gap * 100)}%
                </td>
                <td style={{ padding: '6px 8px', fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {card.score}
                </td>
                <td style={{ padding: '6px 8px', fontSize: 12, color: 'var(--text-secondary)' }}>
                  {card.type.replace(/_/g, ' ')}
                </td>
                <td style={{ padding: '6px 8px', fontSize: 12, color: 'var(--text-secondary)' }}>
                  {formatUpdatedAt(card.updatedAt)}
                </td>
                <td style={{ padding: '6px 8px' }}>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      height: 20,
                      padding: '0 8px',
                      borderRadius: 10,
                      fontSize: 11,
                      fontWeight: 500,
                      background: 'var(--border)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {card.cluster}
                  </span>
                </td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                  <ChevronRight size={14} strokeWidth={1.5} style={{ color: 'var(--text-secondary)' }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-secondary)' }}>
        {filtered.length} unpublished page{filtered.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
