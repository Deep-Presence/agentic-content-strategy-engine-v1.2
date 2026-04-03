'use client';

import { useState, useCallback } from 'react';
import { Calendar, X } from 'lucide-react';
import { GapStatement } from './GapStatement';
import { PriorityFixes } from './PriorityFixes';
import { DimensionBreakdown } from './DimensionBreakdown';
import { BotAccess } from './BotAccess';
import { PlatformPreferences } from './PlatformPreferences';
import { BotCrawlActivity } from './BotCrawlActivity';
import { SnippetReadiness } from './SnippetReadiness';
import { SlideDrawer } from './SlideDrawer';
import { DIMENSIONS } from './tech-readiness-data';

type SeverityFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

export function TechnicalReadinessClient() {
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [dimensionFilter, setDimensionFilter] = useState<string>('all');
  const [activeDimension, setActiveDimension] = useState<string | null>(null);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTitle, setDrawerTitle] = useState('');
  const [drawerType, setDrawerType] = useState<'pages' | 'dimension'>('pages');
  const [drawerDimensionName, setDrawerDimensionName] = useState<string | undefined>();

  const handleViewPages = useCallback((fixTitle: string) => {
    setDrawerTitle(fixTitle);
    setDrawerType('pages');
    setDrawerDimensionName(undefined);
    setDrawerOpen(true);
  }, []);

  const handleViewLowPages = useCallback(() => {
    setDrawerTitle('Pages with readiness below 20');
    setDrawerType('pages');
    setDrawerDimensionName(undefined);
    setDrawerOpen(true);
  }, []);

  const handleDimensionClick = useCallback((name: string | null) => {
    setActiveDimension(name);
  }, []);

  const clearFilters = () => {
    setSeverityFilter('all');
    setDimensionFilter('all');
    setActiveDimension(null);
  };

  const hasActiveFilters = severityFilter !== 'all' || dimensionFilter !== 'all';

  // Determine effective dimension filter (from filter bar or from clicking dimension table)
  const effectiveDimensionFilter =
    activeDimension || (dimensionFilter !== 'all' ? dimensionFilter : null);

  return (
    <div className="max-w-full px-6 py-5">
      {/* Page Header */}
      <div className="mb-4">
        <h1
          className="text-[22px] font-semibold"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          Technical Readiness
        </h1>
        <p
          className="text-[13px]"
          style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
        >
          Is your site structured for AI engines to discover and cite you?
        </p>
      </div>

      {/* Filter Bar */}
      <div
        className="flex items-center gap-3 h-[44px] px-3 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] mb-4"
      >
        <div className="flex items-center gap-1.5">
          <Calendar size={14} style={{ color: 'var(--text-tertiary)' }} />
          <span
            className="text-[13px]"
            style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
          >
            Mar 1, 2026 – Mar 28, 2026
          </span>
        </div>

        <span className="w-px h-5 bg-[var(--border)]" />

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as SeverityFilter)}
          className="h-[32px] px-2.5 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] text-[13px] outline-none cursor-pointer hover:border-[var(--border-strong)] transition-colors"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>

        <select
          value={dimensionFilter}
          onChange={(e) => {
            setDimensionFilter(e.target.value);
            setActiveDimension(e.target.value !== 'all' ? e.target.value : null);
          }}
          className="h-[32px] px-2.5 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] text-[13px] outline-none cursor-pointer hover:border-[var(--border-strong)] transition-colors"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          <option value="all">All Dimensions</option>
          {DIMENSIONS.map((d) => (
            <option key={d.name} value={d.name}>{d.name}</option>
          ))}
        </select>

        {hasActiveFilters && (
          <button
            className="flex items-center gap-1 text-[12px] font-medium hover:opacity-80 transition-opacity ml-auto"
            style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-display)' }}
            onClick={clearFilters}
          >
            <X size={12} />
            Clear
          </button>
        )}
      </div>

      {/* Sections */}
      <div className="flex flex-col gap-4">
        {/* Section 1: Gap Statement */}
        <GapStatement />

        {/* Section 2: Priority Fixes */}
        <PriorityFixes
          dimensionFilter={effectiveDimensionFilter}
          onViewPages={handleViewPages}
        />

        {/* Section 3: Dimension Breakdown */}
        <DimensionBreakdown
          activeDimension={activeDimension}
          onDimensionClick={handleDimensionClick}
        />

        {/* Section 4: Bot Access */}
        <BotAccess />

        {/* Section 5: Platform Citation Preferences */}
        <PlatformPreferences />

        {/* Section 6: Bot Crawl Activity */}
        <BotCrawlActivity />

        {/* Section 7: Snippet Readiness Distribution */}
        <SnippetReadiness onViewLowPages={handleViewLowPages} />
      </div>

      {/* Slide Drawer */}
      <SlideDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerTitle}
        type={drawerType}
        dimensionName={drawerDimensionName}
      />

      {/* Global Animations */}
      <style jsx global>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
