'use client';

import { useState, useMemo, useCallback } from 'react';
import { Calendar, ChevronDown } from 'lucide-react';
import { generateDayData, VIEW_CONFIGS, type ViewType } from './_components/brand-presence/mock-data';
import { PresenceChart } from './_components/brand-presence/PresenceChart';
import { CompetitiveLeaderboard } from './_components/brand-presence/CompetitiveLeaderboard';
import { InsightCards } from './_components/brand-presence/InsightCards';
import { PlatformIntelligence } from './_components/brand-presence/PlatformIntelligence';
import { CitationUrlsTable } from './_components/brand-presence/CitationUrlsTable';

type DateRange = '7d' | '14d' | '28d';

const DATE_RANGES: { key: DateRange; label: string; days: number }[] = [
  { key: '7d', label: 'Mar 22, 2026 – Mar 28, 2026', days: 7 },
  { key: '14d', label: 'Mar 15, 2026 – Mar 28, 2026', days: 14 },
  { key: '28d', label: 'Mar 1, 2026 – Mar 28, 2026', days: 28 },
];

export default function BrandPresencePage() {
  const fullData = useMemo(() => generateDayData(), []);
  const [activeView, setActiveView] = useState<ViewType>('presenceScore');
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [showCompetitors, setShowCompetitors] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange>('28d');
  const [showDateDrop, setShowDateDrop] = useState(false);

  // Date filter controls which slice of data the chart uses
  const data = useMemo(() => {
    const range = DATE_RANGES.find(r => r.key === dateRange)!;
    return fullData.slice(-range.days);
  }, [fullData, dateRange]);

  const viewConfig = VIEW_CONFIGS.find(v => v.key === activeView)!;
  const latest = data[data.length - 1];
  const earliest = data[0];

  // Hero display value (updates on hover)
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

  // KPI strip data — derived from filtered data
  const kpis = useMemo(() => {
    const l = data[data.length - 1];
    const e = data[0];
    const totalCitations = data.reduce((s, d) => s + d.citations, 0);
    const totalMentions = data.reduce((s, d) => s + d.mentions, 0);
    const citationRate = Math.round((totalCitations / (totalCitations + totalMentions)) * 100);
    const earlySlice = data.slice(0, Math.max(1, Math.floor(data.length / 4)));
    const earlyCitRate = Math.round(
      (earlySlice.reduce((s, d) => s + d.citations, 0) /
       earlySlice.reduce((s, d) => s + d.citations + d.mentions, 0)) * 100
    );

    return [
      {
        label: 'Presence Score',
        value: String(Math.round(l.presenceScore)),
        delta: `+${Math.round(l.presenceScore - e.presenceScore)} this period`,
        positive: l.presenceScore >= e.presenceScore,
        isPrimary: true,
        viewKey: 'presenceScore' as ViewType,
      },
      {
        label: 'Share of Voice',
        value: `${l.sov.toFixed(1)}%`,
        delta: `from ${e.sov.toFixed(1)}%`,
        positive: l.sov >= e.sov,
        viewKey: 'sov' as ViewType,
      },
      {
        label: 'Citation Rate',
        value: `${citationRate}%`,
        delta: `from ${earlyCitRate}%`,
        positive: citationRate >= earlyCitRate,
        viewKey: 'citations' as ViewType,
      },
      {
        label: 'Avg Position',
        value: l.position.toFixed(1),
        delta: `from ${e.position.toFixed(1)}`,
        positive: l.position <= e.position,
        viewKey: 'position' as ViewType,
      },
    ];
  }, [data]);

  const handleKPIClick = useCallback((viewKey: ViewType) => {
    setActiveView(viewKey);
  }, []);

  return (
    <div style={{ margin: '-16px' }}>
      {/* Page Header */}
      <div style={{ padding: '16px 24px 0' }}>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            fontFamily: 'var(--font-display)',
            color: 'var(--text-primary)',
          }}
        >
          Brand Presence
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
          Your brand&apos;s visibility and authority across AI engines
        </p>
      </div>

      {/* Global Filter Bar — 44px, matching Citation Intelligence */}
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
        {/* Date Range Picker */}
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
      <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* KPI Strip — 4 cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
          }}
        >
          {kpis.map((kpi, i) => (
            <div
              key={kpi.label}
              onClick={() => handleKPIClick(kpi.viewKey)}
              style={{
                padding: 12,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                borderLeft: i > 0 ? '1px solid var(--border)' : 'none',
                background: activeView === kpi.viewKey ? 'var(--accent-subtle)' : 'var(--surface)',
                cursor: 'pointer',
                transition: 'background 150ms',
                position: 'relative',
              }}
            >
              {kpi.isPrimary && (
                <div style={{
                  position: 'absolute',
                  left: 0, top: 0, bottom: 0, width: 2,
                  background: 'var(--accent)',
                  borderRadius: '2px 0 0 2px',
                }} />
              )}
              <span
                style={{
                  fontSize: 11, fontWeight: 500, textTransform: 'uppercase',
                  letterSpacing: '0.05em', color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-display)',
                }}
              >
                {kpi.label}
              </span>
              <span
                style={{
                  fontSize: 28, fontWeight: 600, lineHeight: 1,
                  fontFamily: 'var(--font-mono)', color: 'var(--text-primary)',
                }}
              >
                {kpi.value}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                  {kpi.positive ? (
                    <path d="M5 2L8 6H2L5 2Z" fill="var(--success)" />
                  ) : (
                    <path d="M5 8L2 4H8L5 8Z" fill="var(--error)" />
                  )}
                </svg>
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
            </div>
          ))}
        </div>

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
                    style={{
                      fontFamily: 'var(--font-mono)', fontSize: 48, fontWeight: 600,
                      color: 'var(--text-primary)', lineHeight: 1, letterSpacing: '-0.03em',
                    }}
                  >
                    {viewConfig.format(heroValue)}
                  </span>
                  <span style={{ fontSize: 14, color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}>
                    {hoverIdx !== null ? data[hoverIdx]?.dateShort : viewConfig.label}
                  </span>
                  {hoverIdx === null && (
                    <span
                      style={{
                        fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600,
                        color: isPositive ? 'var(--success)' : 'var(--error)',
                      }}
                    >
                      {delta}
                    </span>
                  )}
                </div>
                {viewConfig.key === 'presenceScore' && hoverIdx === null && (
                  <span
                    title="SOV (35%) + Citation Rate (25%) + Avg Position (20%) + Sentiment (10%) + Coverage (10%)"
                    style={{
                      fontSize: 11, color: 'var(--text-tertiary)', cursor: 'help',
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      width: 16, height: 16, borderRadius: 9999, border: '1px solid var(--border)',
                    }}
                  >
                    ?
                  </span>
                )}
              </div>

              {/* View toggles */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {VIEW_CONFIGS.map(vc => {
                  const isActive = vc.key === activeView;
                  return (
                    <button
                      key={vc.key}
                      onClick={() => setActiveView(vc.key)}
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

            {/* Competitor toggle — bordered button */}
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

        {/* Insight Cards */}
        <InsightCards
          data={data}
          activeView={activeView}
          onViewChange={setActiveView}
        />

        {/* Platform Intelligence */}
        <PlatformIntelligence data={data} />

        {/* Citation URLs Table */}
        <CitationUrlsTable />
      </div>
    </div>
  );
}
