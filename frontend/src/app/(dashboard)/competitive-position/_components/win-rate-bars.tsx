'use client';

import { useState } from 'react';
import { COMPETITORS, COMPETITOR_DETAILS, ENGINE_DOMAINS } from './data';
import { BrandLogo } from './brand-logo';
import { SlideDrawer } from './slide-drawer';
import { Check, X, ArrowRight } from 'lucide-react';

function barColor(rate: number): string {
  if (rate > 50) return 'var(--success)';
  if (rate >= 30) return 'var(--warning)';
  return 'var(--error)';
}

export function WinRateBars() {
  const [drawerDomain, setDrawerDomain] = useState<string | null>(null);

  const sorted = [...COMPETITORS].sort((a, b) => b.winRate - a.winRate);
  const detail = drawerDomain ? COMPETITOR_DETAILS[drawerDomain] : null;
  const competitor = drawerDomain ? COMPETITORS.find((c) => c.domain === drawerDomain) : null;

  return (
    <>
      <div
        style={{
          border: '1px solid var(--border)',
          borderRadius: 6,
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            Your Win Rate
          </h3>
        </div>

        {/* Table header */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 200px 60px',
            alignItems: 'center',
            padding: '0 14px',
            height: 32,
            borderBottom: '1px solid var(--border)',
          }}
        >
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)' }}>
            Competitor
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)' }}>
            Win Rate
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)', textAlign: 'right' }}>
            Result
          </span>
        </div>

        {/* Rows */}
        {sorted.map((c, i) => (
          <div
            key={c.domain}
            onClick={() => setDrawerDomain(c.domain)}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 200px 60px',
              alignItems: 'center',
              padding: '0 14px',
              height: 40,
              borderBottom: i < sorted.length - 1 ? '1px solid var(--border-subtle)' : 'none',
              cursor: 'pointer',
              transition: 'background 0.15s',
              animation: `fadeUp 300ms ease ${i * 30}ms both`,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            {/* Competitor */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <BrandLogo domain={c.domain} size={14} />
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                {c.domain}
              </span>
            </div>

            {/* Win Rate bar + number */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${c.winRate}%`,
                    background: barColor(c.winRate),
                    borderRadius: 3,
                    animation: `barGrow 500ms ease ${150 + i * 30}ms both`,
                    transformOrigin: 'left',
                  }}
                />
              </div>
              <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-mono)', color: barColor(c.winRate), minWidth: 36, textAlign: 'right' }}>
                {c.winRate}%
              </span>
            </div>

            {/* Result label */}
            <span style={{ fontSize: 10, fontWeight: 500, textAlign: 'right', fontFamily: 'var(--font-body)', color: c.winRate > 50 ? 'var(--success)' : c.winRate >= 30 ? 'var(--warning)' : 'var(--error)' }}>
              {c.winRate > 50 ? 'Winning' : c.winRate >= 30 ? 'Close' : 'Losing'}
            </span>
          </div>
        ))}
      </div>

      {/* Competitor Detail Drawer */}
      <SlideDrawer
        isOpen={!!drawerDomain}
        onClose={() => setDrawerDomain(null)}
        title={competitor ? `${competitor.name} — Head to Head` : ''}
        subtitle={detail ? `Your win rate against ${competitor?.domain}` : undefined}
      >
        {detail && competitor && (
          <div style={{ paddingTop: 16 }}>
            {/* Win Rate Big Number */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
              <BrandLogo domain={competitor.domain} size={32} />
              <div>
                <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                  Your Win Rate
                </p>
                <p style={{ fontSize: 28, fontWeight: 600, fontFamily: 'var(--font-mono)', color: barColor(detail.winRate) }}>
                  {detail.winRate}%
                </p>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {competitor.domain} wins {100 - detail.winRate}% of {detail.totalShared} shared queries
                </p>
              </div>
            </div>

            {/* Queries You Win */}
            <div style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--success)', marginBottom: 8 }}>
                Queries You Win ({detail.queriesYouWin.length} of {detail.totalShared})
              </p>
              {detail.queriesYouWin.map((q) => (
                <div key={q.query} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <Check size={14} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 1 }} strokeWidth={2} />
                  <div>
                    <p style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                      &ldquo;{q.query}&rdquo;
                    </p>
                    <div style={{ display: 'flex', gap: 6, marginTop: 3, flexWrap: 'wrap' }}>
                      {q.platforms.map((p) => (
                        <span key={p} style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 11, color: 'var(--text-secondary)' }}>
                          <BrandLogo domain={ENGINE_DOMAINS[p] || ''} size={10} />
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Queries You Lose */}
            <div style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--error)', marginBottom: 8 }}>
                Queries You Lose ({detail.queriesYouLose.length} of {detail.totalShared})
              </p>
              {detail.queriesYouLose.map((q) => (
                <div key={q.query} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <X size={14} style={{ color: 'var(--error)', flexShrink: 0, marginTop: 1 }} strokeWidth={2} />
                  <div>
                    <p style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                      &ldquo;{q.query}&rdquo;
                    </p>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                      {competitor.domain} cited on {q.competitorCitations} engine{q.competitorCitations > 1 ? 's' : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Why They Win */}
            <div style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 8 }}>
                Why {competitor.name} Wins
              </p>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {detail.whyTheyWin.map((reason, i) => (
                  <li key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 4 }}>
                    {reason}
                  </li>
                ))}
              </ul>
            </div>

            {/* How to Close the Gap */}
            <div style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent)', marginBottom: 8 }}>
                How to Close the Gap
              </p>
              <ol style={{ margin: 0, paddingLeft: 16 }}>
                {detail.howToClose.map((step, i) => (
                  <li key={i} style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 6 }}>
                    {step.action}
                    <span style={{ fontSize: 11, color: 'var(--success)', marginLeft: 6 }}>({step.impact})</span>
                  </li>
                ))}
              </ol>
            </div>

            {/* Action */}
            <button
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                height: 30,
                padding: '0 12px',
                borderRadius: 4,
                border: 'none',
                background: 'var(--accent)',
                color: 'var(--text-on-accent)',
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'var(--font-display)',
              }}
            >
              Create tasks in Content Planner
              <ArrowRight size={13} strokeWidth={1.5} />
            </button>
          </div>
        )}
      </SlideDrawer>
    </>
  );
}
