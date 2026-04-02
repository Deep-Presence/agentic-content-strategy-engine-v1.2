'use client';

import { useState, useRef, useCallback } from 'react';
import { Calendar } from 'lucide-react';
import { KPIStrip } from './_components/KPIStrip';
import { BattleChart } from './_components/BattleChart';
import { WinRateBars } from './_components/WinRateBars';
import { GapTrendChart } from './_components/GapTrendChart';
import { ClusterAuthorityTable } from './_components/ClusterAuthority';
import { DriftTracker } from './_components/DriftTracker';
import { MostCitedURLs } from './_components/MostCitedURLs';
import { SlideDrawer } from './_components/SlideDrawer';
import { clusterOptions, platformOptions } from './_components/data';

// ─── Date Range Picker (proper two-month calendar) ──────────────────────────

function DateRangePicker({
  value,
  onChange,
}: {
  value: [string, string];
  onChange: (range: [string, string]) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [selecting, setSelecting] = useState<'start' | 'end'>('start');
  const [tempStart, setTempStart] = useState(value[0]);
  const containerRef = useRef<HTMLDivElement>(null);

  const formatDisplay = (d: string) => {
    const date = new Date(d + 'T00:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const getMonthDays = (year: number, month: number) => {
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const days: (number | null)[] = Array(firstDay).fill(null);
    for (let i = 1; i <= daysInMonth; i++) days.push(i);
    return days;
  };

  const month1 = { year: 2026, month: 2 }; // March 2026
  const month2 = { year: 2026, month: 3 }; // April 2026
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dayNames = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

  const handleDayClick = (year: number, month: number, day: number) => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    if (selecting === 'start') {
      setTempStart(dateStr);
      setSelecting('end');
    } else {
      const start = tempStart < dateStr ? tempStart : dateStr;
      const end = tempStart < dateStr ? dateStr : tempStart;
      onChange([start, end]);
      setSelecting('start');
      setIsOpen(false);
    }
  };

  const isInRange = (year: number, month: number, day: number) => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return dateStr >= value[0] && dateStr <= value[1];
  };

  const isRangeEnd = (year: number, month: number, day: number) => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return dateStr === value[0] || dateStr === value[1];
  };

  const renderMonth = (year: number, month: number) => {
    const days = getMonthDays(year, month);
    return (
      <div>
        <p style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', textAlign: 'center', marginBottom: '8px' }}>
          {monthNames[month]} {year}
        </p>
        <div className="grid grid-cols-7 gap-0">
          {dayNames.map((d) => (
            <div key={d} style={{ fontSize: '9px', fontWeight: 500, color: 'var(--text-tertiary)', textAlign: 'center', padding: '4px 0' }}>
              {d}
            </div>
          ))}
          {days.map((day, i) => {
            if (!day) return <div key={`e-${i}`} />;
            const inRange = isInRange(year, month, day);
            const isEnd = isRangeEnd(year, month, day);
            return (
              <button
                key={day}
                onClick={() => handleDayClick(year, month, day)}
                style={{
                  height: '26px',
                  width: '26px',
                  margin: '0 auto',
                  fontSize: '11px',
                  borderRadius: '2px',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                  background: isEnd ? 'var(--accent)' : inRange ? 'var(--accent-subtle)' : 'transparent',
                  color: isEnd ? 'var(--text-on-accent)' : 'var(--text-secondary)',
                }}
              >
                {day}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2"
        style={{
          height: '30px',
          padding: '0 10px',
          border: '1px solid var(--border)',
          borderRadius: '4px',
          background: 'var(--surface)',
          fontSize: '12px',
          color: 'var(--text-primary)',
          cursor: 'pointer',
        }}
      >
        <Calendar size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
        <span>{formatDisplay(value[0])} – {formatDisplay(value[1])}</span>
      </button>

      {isOpen && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          marginTop: '4px',
          background: 'var(--surface-raised)',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          boxShadow: 'var(--shadow-float)',
          padding: '16px',
          zIndex: 50,
        }}>
          <div className="flex gap-6">
            {renderMonth(month1.year, month1.month)}
            {renderMonth(month2.year, month2.month)}
          </div>
          {selecting === 'end' && (
            <p style={{ fontSize: '10px', color: 'var(--accent)', marginTop: '8px', textAlign: 'center' }}>Click end date</p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function CompetitivePositionPage() {
  // Filter state
  const [dateRange, setDateRange] = useState<[string, string]>(['2026-03-01', '2026-03-28']);
  const [cluster, setCluster] = useState('all');
  const [platform, setPlatform] = useState('all');

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerType, setDrawerType] = useState<'competitor' | 'query' | null>(null);
  const [drawerIdentifier, setDrawerIdentifier] = useState<string | null>(null);

  const openCompetitorDrawer = useCallback((domain: string) => {
    setDrawerType('competitor');
    setDrawerIdentifier(domain);
    setDrawerOpen(true);
  }, []);

  const openQueryDrawer = useCallback((query: string) => {
    setDrawerType('query');
    setDrawerIdentifier(query);
    setDrawerOpen(true);
  }, []);

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
  }, []);

  const clearFilters = () => {
    setDateRange(['2026-03-01', '2026-03-28']);
    setCluster('all');
    setPlatform('all');
  };

  const selectStyle = {
    height: '30px',
    padding: '0 8px',
    border: '1px solid var(--border)',
    borderRadius: '4px',
    background: 'var(--surface)',
    fontSize: '12px',
    color: 'var(--text-primary)',
    cursor: 'pointer',
    outline: 'none',
  } as const;

  return (
    <div style={{ padding: '16px 24px' }}>
      {/* Page Header — 0 gap to filter bar */}
      <div>
        <h1 style={{
          fontSize: '22px',
          fontWeight: 600,
          color: 'var(--text-primary)',
          letterSpacing: '-0.02em',
          fontFamily: 'var(--font-display)',
        }}>
          Competitive Position
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          Am I winning or losing, and against whom?
        </p>
      </div>

      {/* Global Filter Bar — full-width toolbar, 44px, border-b only, no rounded corners, 0 gap from title */}
      <div
        className="flex items-center gap-3"
        style={{
          height: '44px',
          marginLeft: '-24px',
          marginRight: '-24px',
          paddingLeft: '24px',
          paddingRight: '24px',
          borderBottom: '1px solid var(--border)',
          marginTop: '0',
        }}
      >
        <DateRangePicker value={dateRange} onChange={setDateRange} />

        <div style={{ height: '16px', width: '1px', background: 'var(--border)' }} />

        <select value={cluster} onChange={(e) => setCluster(e.target.value)} style={selectStyle}>
          {clusterOptions.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <div style={{ height: '16px', width: '1px', background: 'var(--border)' }} />

        <select value={platform} onChange={(e) => setPlatform(e.target.value)} style={selectStyle}>
          {platformOptions.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <button
          onClick={clearFilters}
          style={{
            marginLeft: 'auto',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          × Clear
        </button>
      </div>

      {/* Content sections — 16px gaps */}
      <div className="flex flex-col" style={{ gap: '16px', marginTop: '16px' }}>
        {/* KPI Strip */}
        <KPIStrip />

        {/* Section 1: Head-to-Head Daily Battle */}
        <BattleChart />

        {/* Section 2: Two-column — 55% left / 45% right */}
        <div className="grid" style={{ gridTemplateColumns: '55fr 45fr', gap: '16px' }}>
          <WinRateBars onCompetitorClick={openCompetitorDrawer} />
          <GapTrendChart />
        </div>

        {/* Section 3: Competitor SOV by Cluster */}
        <ClusterAuthorityTable onCompetitorClick={openCompetitorDrawer} />

        {/* Section 4: Citation Drift Tracker */}
        <DriftTracker
          onQueryClick={openQueryDrawer}
          onCompetitorClick={openCompetitorDrawer}
        />

        {/* Section 5: Most-Cited Competitor URLs */}
        <MostCitedURLs onCompetitorClick={openCompetitorDrawer} />
      </div>

      {/* Side Drawer */}
      <SlideDrawer
        isOpen={drawerOpen}
        onClose={closeDrawer}
        type={drawerType}
        identifier={drawerIdentifier}
      />
    </div>
  );
}
