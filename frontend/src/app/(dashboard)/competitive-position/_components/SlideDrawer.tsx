'use client';

import { useEffect, useCallback } from 'react';
import { X, ExternalLink } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { cn } from '@/lib/utils';
import { getCompetitorDetail, getQueryDetail, PLATFORM_DOMAINS } from './data';

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

function SectionHeader({ title }: { title: string }) {
  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: '12px', marginTop: '16px' }}>
      <h4 style={{
        fontSize: '14px',
        fontWeight: 600,
        textTransform: 'uppercase' as const,
        color: 'var(--text-secondary)',
        letterSpacing: '0.03em',
      }}>
        {title}
      </h4>
    </div>
  );
}

function MiniTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.[0]) return null;
  return (
    <div style={{
      background: 'rgba(17,24,28,0.92)',
      backdropFilter: 'blur(8px)',
      border: '1px solid var(--border-strong)',
      padding: '4px 8px',
      borderRadius: '4px',
    }}>
      <span style={{ fontSize: '11px', color: '#A0A0A0' }}>{label}: </span>
      <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: '#EDEDED' }}>
        {payload[0].value}
      </span>
    </div>
  );
}

// ─── Competitor Drawer ───────────────────────────────────────────────────────

function CompetitorDrawerContent({ domain }: { domain: string }) {
  const d = getCompetitorDetail(domain);
  const threatColors = { HIGH: 'var(--error)', MEDIUM: 'var(--warning)', LOW: 'var(--success)' };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <Favicon domain={domain} size={28} />
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>{domain}</h2>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Competitor analysis</p>
        </div>
      </div>

      {/* Section 1: SOV by Cluster */}
      <SectionHeader title="SOV by Cluster" />
      <div className="space-y-2 mt-3">
        {d.sovByClusters.map((c) => (
          <div key={c.cluster} className="flex items-center gap-2">
            <span className="truncate" style={{ fontSize: '12px', color: 'var(--text-secondary)', width: '130px', flexShrink: 0 }}>
              {c.cluster}
            </span>
            <div className="flex items-center gap-1 flex-1">
              <div className="flex-1 rounded-sm overflow-hidden relative" style={{ height: '14px', background: 'var(--border-subtle)' }}>
                <div className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${c.you}%`, background: 'var(--accent)' }} />
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 500, color: 'var(--accent)', width: '24px', textAlign: 'right' }}>{c.you}</span>
            </div>
            <span style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>vs</span>
            <div className="flex items-center gap-1 flex-1">
              <div className="flex-1 rounded-sm overflow-hidden relative" style={{ height: '14px', background: 'var(--border-subtle)' }}>
                <div className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${c.them}%`, background: 'var(--text-tertiary)' }} />
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 500, color: 'var(--text-secondary)', width: '24px', textAlign: 'right' }}>{c.them}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Section 2: Top Cited URLs */}
      <SectionHeader title="Top Cited URLs" />
      <div className="space-y-1.5 mt-3">
        {d.topURLs.map((u) => (
          <div
            key={u.url}
            className="flex items-center justify-between rounded-sm"
            style={{ padding: '6px 8px', border: '1px solid var(--border)', background: 'var(--bg)' }}
          >
            <span className="truncate" style={{ fontSize: '12px', color: 'var(--text-primary)', flex: 1 }}>
              {u.url}
            </span>
            <div className="flex items-center gap-3 shrink-0 ml-2">
              <div className="flex items-center gap-1">
                {u.platforms.map((p) => (
                  <Favicon key={p} domain={PLATFORM_DOMAINS[p] || ''} size={12} />
                ))}
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)' }}>
                {u.citations} citations
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Section 3: Structural Comparison */}
      <SectionHeader title="Structural Comparison" />
      <table className="w-full mt-3">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th className="text-left" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '6px 0' }}>Signal</th>
            <th className="text-right" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '6px 0' }}>Their Avg</th>
            <th className="text-right" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '6px 0' }}>Your Avg</th>
            <th className="text-right" style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', padding: '6px 0' }}>Gap</th>
          </tr>
        </thead>
        <tbody>
          {d.structuralComparison.map((s) => (
            <tr key={s.signal} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <td style={{ fontSize: '12px', color: 'var(--text-secondary)', padding: '5px 0' }}>{s.signal}</td>
              <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-primary)', padding: '5px 0' }}>{s.theirAvg}</td>
              <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-primary)', padding: '5px 0' }}>{s.yourAvg}</td>
              <td style={{
                textAlign: 'right',
                fontFamily: 'var(--font-mono)',
                fontSize: '12px',
                fontWeight: 500,
                color: s.gapDirection === 'behind' ? 'var(--error)' : 'var(--success)',
                padding: '5px 0',
              }}>
                {s.gap}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Section 4: Citation Trajectory */}
      <SectionHeader title="Citation Trajectory (28d)" />
      <div className="mt-3 rounded-sm" style={{ border: '1px solid var(--border)', background: 'var(--bg)', padding: '8px' }}>
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={d.trajectory} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={false} stroke="var(--border)" />
            <YAxis
              tick={{ fontSize: 9, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}
              stroke="var(--border)"
              tickLine={false}
              width={25}
            />
            <Tooltip content={<MiniTooltip />} />
            <Line
              type="monotone"
              dataKey="citations"
              stroke="var(--text-secondary)"
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Section 5: Threat Assessment */}
      <SectionHeader title="Threat Assessment" />
      <div className="mt-3 space-y-2">
        <div className="flex items-center gap-2">
          <span style={{
            fontSize: '11px',
            fontWeight: 500,
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            Threat Level
          </span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              height: '20px',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '10px',
              fontWeight: 600,
              textTransform: 'uppercase',
              background: threatColors[d.threatScore],
              color: '#FFFFFF',
            }}
          >
            {d.threatScore}
          </span>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          Content velocity: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.contentVelocity}</span>
        </p>
        <div className="space-y-1 mt-2">
          {d.threatSummary.map((line, i) => (
            <p key={i} style={{ fontSize: '12px', color: 'var(--text-primary)' }}>• {line}</p>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Query Drawer ────────────────────────────────────────────────────────────

function QueryDrawerContent({ query }: { query: string }) {
  const d = getQueryDetail(query);

  const showToast = (msg: string) => {
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
    <div>
      {/* Section 1: Query Text */}
      <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
        &ldquo;{d.query}&rdquo;
      </h2>

      {/* Section 2: Your Content */}
      <SectionHeader title="Your Content" />
      <div className="mt-3 rounded-sm" style={{ border: '1px solid var(--border)', background: 'var(--bg)', padding: '10px' }}>
        <div className="flex items-center gap-1.5">
          <Favicon domain="lovable.dev" size={14} />
          <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{d.yourContent.url}</span>
          <ExternalLink size={11} style={{ color: 'var(--text-tertiary)' }} />
        </div>
        <div className="flex gap-4 mt-2 flex-wrap">
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Similarity: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.yourContent.similarity}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Words: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.yourContent.wordCount.toLocaleString()}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Headers: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.yourContent.headers}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            FAQ: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.yourContent.faq ? 'Yes' : 'No'}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Tables: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.yourContent.tables}</span>
          </span>
        </div>
      </div>

      {/* Section 3: What Replaced You */}
      <SectionHeader title="What Replaced You" />
      <div className="mt-3 rounded-sm" style={{ border: '1px solid var(--border)', background: 'var(--bg)', padding: '10px' }}>
        <div className="flex items-center gap-1.5">
          <Favicon domain={d.theirContent.domain} size={14} />
          <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{d.theirContent.url}</span>
          <ExternalLink size={11} style={{ color: 'var(--text-tertiary)' }} />
        </div>
        <div className="flex gap-4 mt-2 flex-wrap">
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Similarity: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--success)' }}>{d.theirContent.similarity}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Words: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.theirContent.wordCount.toLocaleString()}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Headers: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.theirContent.headers}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            FAQ: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--success)' }}>{d.theirContent.faq ? `Yes (${d.theirContent.faqCount})` : 'No'}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Tables: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.theirContent.tables}</span>
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
            Ext Citations: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{d.theirContent.externalCitations}</span>
          </span>
        </div>
      </div>

      {/* Section 4: Structural Gap */}
      <SectionHeader title="Structural Gap" />
      <div className="space-y-1.5 mt-3">
        {d.structuralGaps.map((gap, i) => (
          <div
            key={i}
            className="flex items-start gap-2 rounded-sm"
            style={{
              padding: '8px 10px',
              background: gap.type === 'missing' ? 'var(--error-subtle)' : 'var(--success-subtle)',
            }}
          >
            <span style={{ fontSize: '13px', flexShrink: 0 }}>
              {gap.type === 'missing' ? '❌' : '✅'}
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{gap.text}</span>
          </div>
        ))}
      </div>

      {/* Section 5: Action */}
      <SectionHeader title="Action" />
      <button
        onClick={() => showToast('Content brief created — view in Content Planner')}
        className="w-full mt-3"
        style={{
          height: '30px',
          background: 'var(--accent)',
          color: 'var(--text-on-accent)',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: 500,
          border: 'none',
          cursor: 'pointer',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-hover)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--accent)')}
      >
        Create content brief →
      </button>
    </div>
  );
}

// ─── Slide Drawer Shell ──────────────────────────────────────────────────────

interface SlideDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  type: 'competitor' | 'query' | null;
  identifier: string | null;
}

export function SlideDrawer({ isOpen, onClose, type, identifier }: SlideDrawerProps) {
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, handleEscape]);

  return (
    <>
      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 transition-opacity"
          style={{ background: 'rgba(0,0,0,0.15)' }}
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={cn(
          'fixed top-0 right-0 h-full z-50 overflow-y-auto',
          'transform transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
        style={{
          width: '50vw',
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-float)',
        }}
      >
        {/* Close button */}
        <div className="sticky top-0 z-10 flex items-center justify-end" style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
        }}>
          <button
            onClick={onClose}
            className="flex items-center justify-center transition-colors"
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '4px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              color: 'var(--text-secondary)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-raised)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '16px 20px 24px' }}>
          {type === 'competitor' && identifier && (
            <CompetitorDrawerContent domain={identifier} />
          )}
          {type === 'query' && identifier && (
            <QueryDrawerContent query={identifier} />
          )}
        </div>
      </div>
    </>
  );
}
