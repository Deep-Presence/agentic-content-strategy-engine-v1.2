'use client';

import { useState, useMemo, useCallback } from 'react';
import { Calendar, ChevronDown, ChevronUp, ChevronRight, TrendingUp, TrendingDown } from 'lucide-react';
import Link from 'next/link';
import { generateDayData, VIEW_CONFIGS, type ViewType } from './_components/brand-presence/mock-data';
import { PresenceChart } from './_components/brand-presence/PresenceChart';
import { CompetitiveLeaderboard } from './_components/brand-presence/CompetitiveLeaderboard';
import { InsightCards } from './_components/brand-presence/InsightCards';
import { PlatformIntelligence } from './_components/brand-presence/PlatformIntelligence';

type DateRange = '7d' | '14d' | '28d';

const DATE_RANGES: { key: DateRange; label: string; days: number }[] = [
  { key: '7d', label: 'Mar 22, 2026 – Mar 28, 2026', days: 7 },
  { key: '14d', label: 'Mar 15, 2026 – Mar 28, 2026', days: 14 },
  { key: '28d', label: 'Mar 1, 2026 – Mar 28, 2026', days: 28 },
];

const TRAJECTORY = {
  months: [
    { label: 'Jan', score: 45 },
    { label: 'Feb', score: 52 },
    { label: 'Mar', score: 58 },
    { label: 'Apr', score: 74 },
  ],
  avgGrowth: 7.2,
  direction: 'gaining' as const,
};

const SCORE_BREAKDOWN = [
  { name: 'Share of Voice', raw: 49.6, weight: 0.35, maxLabel: '100' },
  { name: 'Citation Rate', raw: 67.0, weight: 0.25, maxLabel: '100' },
  { name: 'Avg Position', raw: 67.5, weight: 0.20, maxLabel: '100' },
  { name: 'Sentiment', raw: 72.0, weight: 0.10, maxLabel: '100' },
  { name: 'Platform Coverage', raw: 100, weight: 0.10, maxLabel: '100' },
];

export default function BrandSummaryPage() {
  const fullData = useMemo(() => generateDayData(), []);
  const [activeView, setActiveView] = useState<ViewType>('presenceScore');
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [showCompetitors, setShowCompetitors] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange>('28d');
  const [showDateDrop, setShowDateDrop] = useState(false);
  const [showBreakdown, setShowBreakdown] = useState(false);

  const data = useMemo(() => {
    const range = DATE_RANGES.find(r => r.key === dateRange)!;
    return fullData.slice(-range.days);
  }, [fullData, dateRange]);

  const viewConfig = VIEW_CONFIGS.find(v => v.key === activeView)!;
  const latest = data[data.length - 1];
  const earliest = data[0];

  const displayDay = hoverIdx !== null ? data[hoverIdx] : latest;
  const heroValue = displayDay[viewConfig.dataKey] as number;
  const delta = viewConfig.deltaFormat(
    latest[viewConfig.dataKey] as number,
    earliest[viewConfig.dataKey] as number,
  );
  const isPositive = viewConfig.key === 'position'
    ? (latest.position < earliest.position)
    : ((latest[viewConfig.dataKey] as number) >= (earliest[viewConfig.dataKey] as number));

  const dateLabel = DATE_RANGES.find(r => r.key === dateRange)!.label;
  const hoverDelta = hoverIdx !== null ? (data[hoverIdx][viewConfig.dataKey] as number) - (latest[viewConfig.dataKey] as number) : 0;

  // Navigational KPI cards data
  const navKpis = useMemo(() => {
    const l = data[data.length - 1];
    const e = data[0];
    const totalCitations = data.reduce((s, d) => s + d.citations, 0);

    return [
      {
        label: 'Share of Voice',
        value: `${l.sov.toFixed(1)}%`,
        delta: `+${(l.sov - e.sov).toFixed(1)} this period`,
        positive: l.sov >= e.sov,
        href: '/competitive-position',
        linkLabel: 'Competitive Position',
      },
      {
        label: 'Avg Position',
        value: l.position.toFixed(1),
        delta: `from ${e.position.toFixed(1)}`,
        positive: l.position <= e.position,
        href: '/competitive-position',
        linkLabel: 'Competitive Position',
      },
      {
        label: 'Total Citations',
        value: String(totalCitations),
        delta: `+${Math.round(totalCitations * 0.15)} this period`,
        positive: true,
        href: '/analytics',
        linkLabel: 'Citation Intelligence',
      },
      {
        label: 'Content Velocity',
        value: '3.2/week',
        delta: '2 published, 1 in review',
        positive: true,
        href: '/content-studio',
        linkLabel: 'Content Studio',
      },
    ];
  }, [data]);

  const handleKPIClick = useCallback((viewKey: ViewType) => {
    setActiveView(viewKey);
  }, []);

  // Presence score for hero
  const presenceScore = Math.round(latest.presenceScore);
  const presenceDelta = Math.round(latest.presenceScore - earliest.presenceScore);
  const breakdownTotal = SCORE_BREAKDOWN.reduce((s, c) => s + c.raw * c.weight, 0);

  return (
    <div style={{ margin: '-16px' }}>
      {/* Page Header */}
      <div style={{ padding: '16px 24px 0' }}>
        <h1
          style={{
            fontSize: 26,
            fontWeight: 600,
            fontFamily: 'var(--font-display)',
            color: 'var(--text-primary)',
          }}
        >
          Brand Summary
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          Your brand&apos;s overall health across AI engines — at a glance
        </p>
      </div>

      {/* Global Filter Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '0 16px',
          height: 44,
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowDateDrop(!showDateDrop)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '4px 8px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              fontSize: 13,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-display)',
            }}
          >
            <Calendar size={14} style={{ color: 'var(--text-secondary)' }} />
            <span>{dateLabel}</span>
          </button>
          {showDateDrop && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                marginTop: 4,
                zIndex: 50,
                minWidth: 220,
                padding: '4px 0',
                borderRadius: 'var(--radius-md)',
                background: 'var(--surface-raised)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-float)',
              }}
            >
              {DATE_RANGES.map(r => (
                <button
                  key={r.key}
                  onClick={() => { setDateRange(r.key); setShowDateDrop(false); setHoverIdx(null); }}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '6px 12px',
                    fontSize: 12,
                    fontFamily: 'var(--font-display)',
                    border: 'none',
                    cursor: 'pointer',
                    color: r.key === dateRange ? 'var(--accent)' : 'var(--text-primary)',
                    background: r.key === dateRange ? 'var(--accent-subtle)' : 'transparent',
                  }}
                  onMouseEnter={(e) => { if (r.key !== dateRange) e.currentTarget.style.background = 'var(--accent-subtle)'; }}
                  onMouseLeave={(e) => { if (r.key !== dateRange) e.currentTarget.style.background = 'transparent'; }}
                >
                  {r.label} ({r.days}d)
                </button>
              ))}
            </div>
          )}
        </div>

        <div style={{ width: 1, height: 16, background: 'var(--border)' }} />

        <button
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '4px 8px',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            fontSize: 13,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-display)',
          }}
        >
          <span>All Platforms</span>
          <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} />
        </button>

        <div style={{ width: 1, height: 16, background: 'var(--border)' }} />

        <button
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '4px 8px',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            fontSize: 13,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-display)',
          }}
        >
          <span>All Clusters</span>
          <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} />
        </button>
      </div>

      {/* Page Content */}
      <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 0 }}>

        {/* Navigational KPI Cards — 4 cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
          }}
        >
          {navKpis.map((kpi) => (
            <Link
              key={kpi.label}
              href={kpi.href}
              style={{
                position: 'relative',
                padding: 14,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--surface)',
                cursor: 'pointer',
                transition: 'all 150ms',
                textDecoration: 'none',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent)';
                e.currentTarget.style.background = 'var(--accent-subtle)';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.background = 'var(--surface)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <ChevronRight
                size={14}
                style={{
                  position: 'absolute',
                  top: 12,
                  right: 12,
                  color: 'var(--text-muted)',
                }}
              />
              <span
                style={{
                  fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
                  letterSpacing: '0.06em', color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-display)',
                }}
              >
                {kpi.label}
              </span>
              <span
                style={{
                  fontSize: 32, fontWeight: 600, lineHeight: 1,
                  fontFamily: 'var(--font-mono)', color: 'var(--text-primary)',
                }}
              >
                {kpi.value}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {kpi.positive ? (
                  <TrendingUp size={12} style={{ color: 'var(--success)' }} />
                ) : (
                  <TrendingDown size={12} style={{ color: 'var(--error)' }} />
                )}
                <span
                  style={{
                    fontSize: 12, fontWeight: 500,
                    color: kpi.positive ? 'var(--success)' : 'var(--error)',
                    fontFamily: 'var(--font-display)',
                  }}
                >
                  {kpi.delta}
                </span>
              </div>
            </Link>
          ))}
        </div>

        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0' }} />

        {/* Chart + Leaderboard */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16 }}>
          {/* Left: Chart with hero + toggles inside */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {/* Hero display + View toggles */}
            <div
              style={{
                border: '1px solid var(--border)',
                borderBottom: 'none',
                borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
                background: 'var(--surface)',
                padding: '12px 12px 8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                  <span
                    onClick={() => {
                      if (viewConfig.key === 'presenceScore' && hoverIdx === null) {
                        setShowBreakdown(!showBreakdown);
                      }
                    }}
                    style={{
                      fontFamily: 'var(--font-mono)', fontSize: 56, fontWeight: 700,
                      color: 'var(--text-primary)', lineHeight: 1, letterSpacing: '-0.03em',
                      cursor: viewConfig.key === 'presenceScore' && hoverIdx === null ? 'pointer' : 'default',
                    }}
                  >
                    {viewConfig.format(heroValue)}
                  </span>
                  {hoverIdx !== null ? (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                        {data[hoverIdx]?.dateShort}
                      </span>
                      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: hoverDelta >= 0 ? 'var(--success)' : 'var(--error)' }}>
                        ({hoverDelta >= 0 ? '+' : ''}{hoverDelta.toFixed(1)} from current)
                      </span>
                    </div>
                  ) : (
                    <>
                      <span style={{ fontSize: 14, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                        {viewConfig.label}
                      </span>
                      <span
                        style={{
                          fontSize: 18, fontFamily: 'var(--font-mono)', fontWeight: 600,
                          color: isPositive ? 'var(--success)' : 'var(--error)',
                        }}
                      >
                        {delta}
                      </span>
                    </>
                  )}
                </div>
                {viewConfig.key === 'presenceScore' && hoverIdx === null && (
                  <button
                    onClick={() => setShowBreakdown(!showBreakdown)}
                    style={{
                      fontSize: 11, color: 'var(--text-tertiary)', cursor: 'pointer',
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      gap: 4, background: 'none', border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)', padding: '2px 8px',
                    }}
                  >
                    {showBreakdown ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    <span>Breakdown</span>
                  </button>
                )}
              </div>

              {/* Presence Score Breakdown — expandable */}
              {showBreakdown && viewConfig.key === 'presenceScore' && hoverIdx === null && (
                <div
                  style={{
                    padding: 14,
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg)',
                    marginBottom: 8,
                  }}
                >
                  <div
                    style={{
                      fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
                      letterSpacing: '0.06em', color: 'var(--text-secondary)',
                      fontFamily: 'var(--font-display)', marginBottom: 10,
                    }}
                  >
                    Score Breakdown
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {SCORE_BREAKDOWN.map((comp) => {
                      const weighted = comp.raw * comp.weight;
                      return (
                        <div key={comp.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 13, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', width: 130, flexShrink: 0 }}>
                            {comp.name}
                          </span>
                          <div style={{ flex: 1, height: 8, borderRadius: 9999, background: 'var(--border)', position: 'relative' }}>
                            <div
                              style={{
                                height: '100%',
                                borderRadius: 9999,
                                width: `${comp.raw}%`,
                                background: 'var(--accent)',
                                transition: 'width 300ms ease',
                              }}
                            />
                          </div>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)', width: 80, textAlign: 'right', flexShrink: 0 }}>
                            {comp.raw.toFixed(1)}/100
                          </span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-tertiary)', width: 40, textAlign: 'center', flexShrink: 0 }}>
                            ×{(comp.weight * 100).toFixed(0)}%
                          </span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', width: 40, textAlign: 'right', flexShrink: 0 }}>
                            = {weighted.toFixed(1)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <div style={{ borderTop: '1px solid var(--border)', marginTop: 8, paddingTop: 8, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: 12, color: 'var(--text-secondary)' }}>
                      TOTAL
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                      = {breakdownTotal.toFixed(1)}
                    </span>
                  </div>
                </div>
              )}

              {/* 3-Month Trajectory — below Presence Score */}
              {viewConfig.key === 'presenceScore' && hoverIdx === null && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {TRAJECTORY.months.map((m, i) => (
                      <span key={m.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 600, color: i === TRAJECTORY.months.length - 1 ? 'var(--accent)' : 'var(--text-primary)' }}>
                          {m.score}
                        </span>
                        <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-display)' }}>
                          {m.label}
                        </span>
                        {i < TRAJECTORY.months.length - 1 && (
                          <ChevronRight size={10} style={{ color: 'var(--text-tertiary)' }} />
                        )}
                      </span>
                    ))}
                  </div>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-display)', color: 'var(--success)' }}>
                    Gaining {TRAJECTORY.avgGrowth} points per month on average
                  </span>
                </div>
              )}

              {/* View toggles */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {VIEW_CONFIGS.map(vc => {
                  const isActive = vc.key === activeView;
                  return (
                    <button
                      key={vc.key}
                      onClick={() => { setActiveView(vc.key); setShowBreakdown(false); }}
                      style={{
                        padding: '4px 10px', fontSize: 12, fontWeight: 500,
                        fontFamily: 'var(--font-display)',
                        background: isActive ? 'var(--accent-subtle)' : 'transparent',
                        color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                        border: 'none', borderRadius: 9999,
                        cursor: 'pointer', transition: 'all 100ms',
                      }}
                    >
                      {vc.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Chart */}
            <div style={{ marginTop: -1 }}>
              <PresenceChart
                data={data}
                viewConfig={viewConfig}
                hoverIdx={hoverIdx}
                onHover={setHoverIdx}
                showCompetitors={showCompetitors}
              />
            </div>

            {/* Competitor toggle */}
            <div style={{ marginTop: 8, display: 'flex', alignItems: 'center' }}>
              <button
                onClick={() => setShowCompetitors(!showCompetitors)}
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  fontFamily: 'var(--font-display)',
                  color: showCompetitors ? 'var(--accent)' : 'var(--text-secondary)',
                  background: showCompetitors ? 'var(--accent-subtle)' : 'transparent',
                  border: '1px solid',
                  borderColor: showCompetitors ? 'var(--accent)' : 'var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '4px 10px',
                  cursor: 'pointer',
                  transition: 'all 150ms',
                }}
              >
                {showCompetitors ? 'Hide competitor trends' : 'Show competitor trends'}
              </button>
            </div>
          </div>

          {/* Right: Leaderboard */}
          <CompetitiveLeaderboard
            data={data}
            viewConfig={viewConfig}
            hoverIdx={hoverIdx}
          />
        </div>

        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0' }} />

        {/* Insight Cards */}
        <InsightCards
          data={data}
          activeView={activeView}
          onViewChange={setActiveView}
        />

        <div style={{ height: 1, background: 'var(--border)', margin: '24px 0' }} />

        {/* Platform Intelligence */}
        <PlatformIntelligence data={data} />
      </div>
    </div>
  );
}
