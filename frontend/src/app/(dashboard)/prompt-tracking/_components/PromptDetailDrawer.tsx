'use client';

import { ChevronDown, ChevronRight, User } from 'lucide-react';
import { useState, useMemo } from 'react';
import type { PromptRow, AnswerHistoryRow } from './prompt-data';
import {
  getCompetitorMentions,
  getPlatformMentionRates,
  getQueryFanouts,
  getAnswerHistory,
} from './prompt-data';
import { AnswerDetailView } from './AnswerDetailView';

interface PromptDetailDrawerProps {
  prompt: PromptRow;
}

function Favicon({ domain, size = 16 }: { domain: string; size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      style={{ borderRadius: 3, flexShrink: 0 }}
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

function DeltaText({ value }: { value: number }) {
  if (value === 0) return <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>0.0%</span>;
  const pos = value > 0;
  return (
    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color: pos ? 'var(--success)' : 'var(--error)' }}>
      {pos ? '+' : ''}{(value * 100).toFixed(1)}%
    </span>
  );
}

export function PromptDetailDrawer({ prompt }: PromptDetailDrawerProps) {
  const [selectedAnswer, setSelectedAnswer] = useState<AnswerHistoryRow | null>(null);
  const [expandedDates, setExpandedDates] = useState<Set<string>>(new Set());

  const competitors = useMemo(() => getCompetitorMentions(prompt.id), [prompt.id]);
  const platformRates = useMemo(() => getPlatformMentionRates(prompt.id), [prompt.id]);
  const fanouts = useMemo(() => getQueryFanouts(prompt.id), [prompt.id]);
  const answerHistory = useMemo(() => getAnswerHistory(prompt.id), [prompt.id]);

  // Group answers by date
  const answersByDate = useMemo(() => {
    const groups: Record<string, AnswerHistoryRow[]> = {};
    for (const a of answerHistory) {
      if (!groups[a.date]) groups[a.date] = [];
      groups[a.date].push(a);
    }
    return groups;
  }, [answerHistory]);

  const dateKeys = Object.keys(answersByDate);

  // Auto-expand first two dates on mount
  useState(() => {
    if (dateKeys.length >= 2) {
      setExpandedDates(new Set([dateKeys[0], dateKeys[1]]));
    } else if (dateKeys.length === 1) {
      setExpandedDates(new Set([dateKeys[0]]));
    }
  });

  const toggleDate = (date: string) => {
    setExpandedDates((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  };

  // If viewing an individual answer → Level 2
  if (selectedAnswer) {
    return (
      <AnswerDetailView
        promptText={prompt.text}
        promptId={prompt.id}
        answer={selectedAnswer}
        onBack={() => setSelectedAnswer(null)}
      />
    );
  }

  const youEntry = competitors.find((c) => c.isYou);
  const youRank = youEntry?.rank ?? 0;
  const maxRate = Math.max(...platformRates.map((p) => p.mentionRate), 0.01);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 4 }}>
          Prompt
        </div>
        <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.3, paddingRight: 32 }}>
          &ldquo;{prompt.text}&rdquo;
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
          Related Keyword: {prompt.text.split(' ').slice(0, 4).join(' ').toLowerCase()} &middot; Category Related
        </div>
        {/* Filter pills: 24px height, 11px text */}
        <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
          {[
            { icon: <User size={11} strokeWidth={1.5} />, label: 'Persona' },
            { icon: null, label: '🌐 United States' },
            { icon: null, label: '📅 Mar 20 – Mar 26' },
          ].map((pill) => (
            <span
              key={pill.label}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                height: 24,
                padding: '0 8px',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 11,
                color: 'var(--text-secondary)',
              }}
            >
              {pill.icon}
              {pill.label}
            </span>
          ))}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {/* Section A: Mention Rate by Competitor — two columns */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 10 }}>
            Mention Rate by Competitor
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {/* Left: Position + Brand Leaderboard */}
            <div>
              {/* Position: 32px JetBrains Mono, font-weight 700 */}
              <div style={{ marginBottom: 10 }}>
                <span style={{
                  fontSize: 32,
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 700,
                  color: youRank <= 2 ? 'var(--accent)' : 'var(--text-primary)',
                }}>
                  {youRank}{youRank === 1 ? 'st' : youRank === 2 ? 'nd' : youRank === 3 ? 'rd' : 'th'}
                </span>
                <div style={{ marginTop: 2 }}>
                  <DeltaText value={youEntry?.mentionDelta ?? 0} />
                </div>
              </div>

              {/* Leaderboard table */}
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', textAlign: 'left', padding: '4px 0' }}>Brand</th>
                    <th style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', textAlign: 'right', padding: '4px 0' }}>Mentions</th>
                    <th style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', textAlign: 'right', padding: '4px 0' }}>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {competitors.map((c) => (
                    <tr key={c.domain} style={{ background: c.isYou ? 'var(--accent-subtle)' : 'transparent' }}>
                      <td style={{ padding: '5px 0' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', width: 14, textAlign: 'right' }}>{c.rank}.</span>
                          <Favicon domain={c.domain} size={16} />
                          <span style={{ fontSize: 12, fontWeight: c.isYou ? 600 : 400, color: c.isYou ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                            {c.brand}
                          </span>
                          {c.isYou && (
                            <span style={{
                              fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
                              padding: '1px 4px', borderRadius: 2,
                              background: 'var(--accent)', color: 'white',
                            }}>
                              You
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', textAlign: 'right', padding: '5px 0' }}>{c.mentions}</td>
                      <td style={{ textAlign: 'right', padding: '5px 0' }}>
                        <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{(c.mentionRate * 100).toFixed(0)}%</span>
                        {' '}
                        <DeltaText value={c.mentionDelta} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Right: Platform mention rates with progress bars */}
            <div>
              <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 10 }}>
                Mention Rate by Platform
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {platformRates.map((p) => (
                  <div key={p.platform}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Favicon domain={p.domain} size={16} />
                        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{p.label}</span>
                      </div>
                      <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 500 }}>
                        {(p.mentionRate * 100).toFixed(0)}%
                      </span>
                    </div>
                    {/* Subtle progress bar: 4px height */}
                    <div style={{ height: 4, borderRadius: 2, background: 'var(--border)' }}>
                      <div style={{
                        height: '100%',
                        borderRadius: 2,
                        background: 'var(--accent)',
                        width: `${(p.mentionRate / maxRate) * 100}%`,
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Section B: Query Fanouts */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 8 }}>
            Query Fanouts ({fanouts.length})
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', textAlign: 'left', padding: '4px 0' }}>Query</th>
                <th style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', textAlign: 'right', padding: '4px 0', width: 90 }}>Observations</th>
              </tr>
            </thead>
            <tbody>
              {fanouts.map((f, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <td style={{ fontSize: 12, color: 'var(--text-primary)', padding: '5px 0' }}>{f.query}</td>
                  <td style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', textAlign: 'right', padding: '5px 0' }}>{f.observations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Section C: Answer History */}
        <div style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 8 }}>
            Answer History ({answerHistory.length})
          </div>

          {/* Column headers */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '60px 110px 1fr 40px 40px 70px',
              gap: 6,
              padding: '4px 6px',
              fontSize: 11,
              fontWeight: 500,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--text-secondary)',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <span>Persona</span>
            <span>Platform</span>
            <span>Answer Preview</span>
            <span style={{ textAlign: 'center' }}>Cited</span>
            <span style={{ textAlign: 'center' }}>Ment.</span>
            <span>Competitors</span>
          </div>

          {dateKeys.map((date) => {
            const answers = answersByDate[date];
            const isExpanded = expandedDates.has(date);

            return (
              <div key={date}>
                {/* Date group header: 12px font-weight 600, subtle background */}
                <button
                  onClick={() => toggleDate(date)}
                  className="cursor-pointer"
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 6px',
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    background: 'var(--surface)',
                    border: 'none',
                    borderBottom: '1px solid var(--border-subtle)',
                    textAlign: 'left',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-raised)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
                >
                  {isExpanded
                    ? <ChevronDown size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
                    : <ChevronRight size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
                  }
                  {date}
                  <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--text-secondary)' }}>
                    ({answers.length} responses)
                  </span>
                </button>

                {/* Answer rows — no Date column repeated */}
                {isExpanded && answers.map((a) => (
                  <div
                    key={a.id}
                    onClick={() => setSelectedAnswer(a)}
                    className="cursor-pointer"
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '60px 110px 1fr 40px 40px 70px',
                      gap: 6,
                      padding: '5px 6px',
                      alignItems: 'center',
                      borderBottom: '1px solid var(--border-subtle)',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-subtle)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 12, color: 'var(--text-secondary)' }}>
                      <User size={11} strokeWidth={1.5} />
                      {a.persona}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--text-secondary)' }}>
                      <Favicon domain={a.platformDomain} size={14} />
                      {a.platformLabel}
                    </span>
                    <span style={{
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {a.answerPreview}
                    </span>
                    <span style={{ textAlign: 'center', fontSize: 12 }}>
                      {a.cited
                        ? <span style={{ color: 'var(--success)' }}>✓</span>
                        : <span style={{ color: 'var(--text-secondary)' }}>✗</span>
                      }
                    </span>
                    <span style={{ textAlign: 'center', fontSize: 12 }}>
                      {a.mentioned
                        ? <span style={{ color: 'var(--success)' }}>✓</span>
                        : <span style={{ color: 'var(--text-secondary)' }}>✗</span>
                      }
                    </span>
                    {/* Competitor favicons: -2px overlap (GitHub avatar style) */}
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      {a.competitorDomains.slice(0, 3).map((d, i) => (
                        <span key={d} style={{ marginLeft: i > 0 ? -2 : 0, position: 'relative', zIndex: 3 - i }}>
                          <Favicon domain={d} size={14} />
                        </span>
                      ))}
                      {a.competitorDomains.length > 3 && (
                        <span style={{ fontSize: 10, color: 'var(--text-secondary)', marginLeft: 2 }}>
                          +{a.competitorDomains.length - 3}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
