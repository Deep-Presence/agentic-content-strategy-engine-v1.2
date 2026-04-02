'use client';

import { useState } from 'react';
import { FINDINGS, type Finding } from './tech-readiness-data';
import { X, ExternalLink, CheckCircle } from 'lucide-react';

interface FindingsTableProps {
  severityFilter: string;
  dimensionFilter: string | null;
}

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

const SEVERITY_STYLES: Record<string, { bg: string; color: string }> = {
  critical: { bg: '#E5484D', color: '#FFFFFF' },
  high: { bg: '#F5A623', color: '#11181C' },
  medium: { bg: 'var(--accent)', color: '#FFFFFF' },
  low: { bg: 'rgba(136,144,152,0.2)', color: 'var(--text-primary)' },
};

function SeverityPill({ severity }: { severity: string }) {
  const style = SEVERITY_STYLES[severity] || SEVERITY_STYLES.low;
  return (
    <span style={{
      display: 'inline-block', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase',
      padding: '2px 6px', borderRadius: '4px',
      background: style.bg, color: style.color,
    }}>
      {severity}
    </span>
  );
}

export function FindingsTable({ severityFilter, dimensionFilter }: FindingsTableProps) {
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);

  const filtered = FINDINGS.filter((f) => {
    if (severityFilter !== 'all' && f.severity !== severityFilter) return false;
    if (dimensionFilter && f.dimension !== dimensionFilter) return false;
    return true;
  }).sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);

  return (
    <>
      <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>Top Findings</h3>
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{filtered.length} findings</span>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Severity', 'Finding', 'Dimension', 'Pages', 'Fix', 'Impact'].map((h, i) => (
                <th key={h} style={{
                  textAlign: i === 3 ? 'right' : 'left',
                  fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
                  color: 'var(--text-tertiary)', padding: '6px 8px',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((finding) => (
              <tr
                key={finding.id}
                onClick={() => setSelectedFinding(finding)}
                style={{
                  height: '40px', borderBottom: '1px solid var(--border-subtle)',
                  cursor: 'pointer', transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--accent-subtle)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}
              >
                <td style={{ padding: '6px 8px' }}>
                  <SeverityPill severity={finding.severity} />
                </td>
                <td style={{ fontSize: '13px', color: 'var(--text-primary)', padding: '6px 8px', maxWidth: '200px' }}>
                  {finding.title}
                </td>
                <td style={{ fontSize: '13px', color: 'var(--text-secondary)', padding: '6px 8px' }}>
                  {finding.dimension}
                </td>
                <td style={{ textAlign: 'right', fontSize: '13px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', padding: '6px 8px' }}>
                  {finding.affectedPages}
                </td>
                <td style={{ fontSize: '13px', color: 'var(--text-secondary)', padding: '6px 8px', maxWidth: '200px' }}>
                  {finding.fix}
                </td>
                <td style={{ padding: '6px 8px' }}>
                  <SeverityPill severity={finding.impact} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <p style={{ fontSize: '13px', color: 'var(--text-tertiary)' }}>No findings match the current filters.</p>
          </div>
        )}
      </div>

      {selectedFinding && (
        <FindingDrawer
          finding={selectedFinding}
          onClose={() => setSelectedFinding(null)}
        />
      )}
    </>
  );
}

// ─── Drawer ──────────────────────────────────────────────────────────────────

function FindingDrawer({ finding, onClose }: { finding: Finding; onClose: () => void }) {
  const [markedFixed, setMarkedFixed] = useState(false);
  const [showToast, setShowToast] = useState(false);

  const currentScore = 38.7;
  const afterScore = currentScore + finding.impactPoints;

  const handleMarkFixed = () => {
    setMarkedFixed(!markedFixed);
    if (!markedFixed) {
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    }
  };

  function scoreColor(score: number): string {
    if (score < 20) return 'var(--error)';
    if (score <= 40) return 'var(--warning)';
    return 'var(--success)';
  }

  return (
    <>
      {/* Overlay */}
      <div
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.15)', zIndex: 40 }}
        onClick={onClose}
      />
      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, height: '100vh', width: '50vw',
        maxWidth: 700, minWidth: 360, zIndex: 50,
        background: 'var(--surface)', borderLeft: '1px solid var(--border)',
        boxShadow: 'var(--shadow-float)', overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <SeverityPill severity={finding.severity} />
              <span style={{
                fontSize: '10px', fontWeight: 600, textTransform: 'uppercase',
                padding: '2px 6px', borderRadius: '4px',
                background: 'var(--bg)', border: '1px solid var(--border)',
                color: 'var(--text-secondary)',
              }}>
                {finding.dimension}
              </span>
            </div>
            <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>{finding.title}</h2>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center',
              borderRadius: 4, cursor: 'pointer', background: 'none', border: 'none',
              color: 'var(--text-tertiary)',
            }}
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Section A: AFFECTED PAGES */}
          <div>
            <h4 style={{ fontSize: '14px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px', letterSpacing: '0.05em' }}>
              Affected Pages
            </h4>
            <div style={{
              maxHeight: 300, overflowY: 'auto',
              border: '1px solid var(--border)', borderRadius: '6px', background: 'var(--bg)',
            }}>
              {finding.pages.map((page, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '6px 10px',
                    borderBottom: i < finding.pages.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                    {page.url}
                    <ExternalLink size={10} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
                  </span>
                  {page.score !== undefined && (
                    <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: scoreColor(page.score) }}>
                      {page.score}
                    </span>
                  )}
                </div>
              ))}
            </div>
            {finding.affectedPages > finding.pages.length && (
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Showing {finding.pages.length} of {finding.affectedPages} pages
              </p>
            )}
          </div>

          {/* Section B: HOW TO FIX */}
          <div>
            <h4 style={{ fontSize: '14px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px', letterSpacing: '0.05em' }}>
              How to Fix
            </h4>
            <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {finding.steps.map((step, i) => {
                const lines = step.split('\n');
                return (
                  <li key={i} style={{ display: 'flex', gap: '8px' }}>
                    <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--accent)', flexShrink: 0 }}>
                      {i + 1}.
                    </span>
                    <div>
                      <span style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                        {lines[0]}
                      </span>
                      {lines.slice(1).map((sub, j) => (
                        <div key={j} style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                          {sub.trim()}
                        </div>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>

          {/* Section C: ESTIMATED IMPACT */}
          <div>
            <h4 style={{ fontSize: '14px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px', letterSpacing: '0.05em' }}>
              Estimated Impact
            </h4>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              Fixing this would improve AEO Readiness by approximately <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--success)' }}>+{finding.impactPoints} points</span> ({currentScore} {'\u2192'} ~{Math.round(afterScore * 10) / 10})
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', width: '60px' }}>Current:</span>
                <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', width: '40px' }}>{currentScore}</span>
                <div style={{ flex: 1, height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: `${currentScore}%`, height: '100%', background: 'var(--error)', borderRadius: 4 }} />
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', width: '60px' }}>After:</span>
                <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', width: '40px' }}>~{Math.round(afterScore * 10) / 10}</span>
                <div style={{ flex: 1, height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: `${afterScore}%`, height: '100%', background: 'var(--success)', borderRadius: 4, transition: 'width 0.5s ease' }} />
                </div>
                <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--success)' }}>
                  (+{finding.impactPoints} pts)
                </span>
              </div>
            </div>
          </div>

          {/* Section D: ACTION */}
          <div>
            <h4 style={{ fontSize: '14px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px', letterSpacing: '0.05em' }}>
              Action
            </h4>
            <button
              onClick={handleMarkFixed}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                height: '30px', padding: '0 12px', borderRadius: '4px',
                fontSize: '12px', fontWeight: 500, cursor: 'pointer',
                background: markedFixed ? 'var(--success-subtle)' : 'var(--bg)',
                color: markedFixed ? 'var(--success)' : 'var(--text-secondary)',
                border: `1px solid ${markedFixed ? 'var(--success)' : 'var(--border)'}`,
                transition: 'all 0.15s',
              }}
            >
              <CheckCircle size={14} strokeWidth={1.5} />
              {markedFixed ? 'Marked as Fixed' : 'Mark as Fixed'}
            </button>
          </div>
        </div>
      </div>

      {/* Toast */}
      {showToast && (
        <div style={{
          position: 'fixed', bottom: 20, right: 20, zIndex: 60,
          background: 'var(--surface-raised)', border: '1px solid var(--border)',
          borderRadius: '6px', padding: '10px 16px',
          boxShadow: 'var(--shadow-float)', fontSize: '12px', color: 'var(--text-primary)',
        }}>
          Marked as fixed — will re-audit on next scan.
        </div>
      )}
    </>
  );
}
