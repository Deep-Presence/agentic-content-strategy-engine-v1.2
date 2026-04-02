'use client';

import { useState } from 'react';
import { GapGauge } from './GapGauge';
import { DimensionSection } from './DimensionSection';
import { BotAccessCard } from './BotAccessCard';
import { SnippetDistribution } from './SnippetDistribution';
import { BotCrawlChart } from './BotCrawlChart';
import { PlatformPreference } from './PlatformPreference';
import { FindingsTable } from './FindingsTable';
import { KPI_DATA } from './tech-readiness-data';

const SEVERITY_OPTIONS = [
  { value: 'all', label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const DIMENSION_OPTIONS = [
  { value: '', label: 'All Dimensions' },
  { value: 'Crawlability', label: 'Crawlability' },
  { value: 'Performance', label: 'Performance' },
  { value: 'On-Page SEO', label: 'On-Page SEO' },
  { value: 'Extractability', label: 'Extractability' },
  { value: 'Schema Markup', label: 'Schema Markup' },
  { value: 'E-E-A-T', label: 'E-E-A-T' },
  { value: 'Freshness', label: 'Freshness' },
  { value: 'Security', label: 'Security' },
];

function KPICard({ label, value, sub, accent }: { label: string; value: string | number; sub: string; accent: string }) {
  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
      <p style={{ fontSize: '11px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
        {label}
      </p>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '28px', fontWeight: 600, color: 'var(--text-primary)' }}>
          {value}
        </span>
      </div>
      <p style={{ fontSize: '12px', fontWeight: 500, color: accent, marginTop: '2px' }}>
        {sub}
      </p>
    </div>
  );
}

export function TechnicalReadinessClient() {
  const [severityFilter, setSeverityFilter] = useState('all');
  const [dimensionFilter, setDimensionFilter] = useState<string | null>(null);

  const hasActiveFilters = severityFilter !== 'all' || dimensionFilter !== null;

  const clearFilters = () => {
    setSeverityFilter('all');
    setDimensionFilter(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Page Title */}
      <div>
        <h1 style={{ fontSize: '22px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
          Technical Readiness
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          Is your site technically ready for AI engines to discover and cite you?
        </p>
      </div>

      {/* Global Filter Bar — full-width toolbar, 44px, no rounded corners */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '12px', height: '44px',
        padding: '0 16px', borderBottom: '1px solid var(--border)',
        margin: '0 -24px', paddingLeft: '24px', paddingRight: '24px',
      }}>
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          Mar 1, 2026 {'\u2013'} Mar 28, 2026
        </span>
        <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          style={{
            height: 30, padding: '0 8px', fontSize: '12px', color: 'var(--text-primary)',
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4,
            cursor: 'pointer', outline: 'none',
          }}
        >
          {SEVERITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
        <select
          value={dimensionFilter || ''}
          onChange={(e) => setDimensionFilter(e.target.value || null)}
          style={{
            height: 30, padding: '0 8px', fontSize: '12px', color: 'var(--text-primary)',
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4,
            cursor: 'pointer', outline: 'none',
          }}
        >
          {DIMENSION_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            style={{
              marginLeft: 'auto', fontSize: '12px', color: 'var(--text-secondary)',
              background: 'none', border: 'none', cursor: 'pointer',
            }}
          >
            {'\u00D7'} Clear
          </button>
        )}
      </div>

      {/* KPI Strip — 6 cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '12px' }}>
        <KPICard label="Site Health" value={KPI_DATA.siteHealth.value} sub={`/${KPI_DATA.siteHealth.max} \u2014 Grade ${KPI_DATA.siteHealth.grade}`} accent="var(--success)" />
        <KPICard label="AEO Readiness" value={KPI_DATA.aeoReadiness.value} sub={`/${KPI_DATA.aeoReadiness.max} \u2014 THE GAP`} accent="var(--error)" />
        <KPICard label="Snippet Readiness" value={KPI_DATA.snippetReadiness.value} sub={KPI_DATA.snippetReadiness.label} accent="var(--error)" />
        <KPICard label="Question Headings" value={`${KPI_DATA.questionHeadings.value}%`} sub={`vs ${KPI_DATA.questionHeadings.target}% target`} accent="var(--warning)" />
        <KPICard label="Critical Issues" value={KPI_DATA.criticalIssues.value} sub={KPI_DATA.criticalIssues.label} accent="var(--error)" />
        {/* llms.txt — custom card with pill */}
        <div style={{ border: '1px solid var(--border)', background: 'var(--surface)', borderRadius: '6px', padding: '12px' }}>
          <p style={{ fontSize: '11px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
            llms.txt
          </p>
          <div style={{ marginTop: '4px' }}>
            <span style={{
              display: 'inline-block', fontSize: '12px', fontWeight: 600,
              padding: '2px 8px', borderRadius: '4px',
              background: '#E5484D', color: '#FFFFFF',
            }}>
              {KPI_DATA.llmsTxt.status}
            </span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {KPI_DATA.llmsTxt.label}
          </p>
        </div>
      </div>

      {/* Section 1: Dual Gauge Hero */}
      <GapGauge />

      {/* Section 2: Dimension Radar + Table */}
      <DimensionSection
        selectedDimension={dimensionFilter}
        onSelectDimension={setDimensionFilter}
      />

      {/* Section 3: Bot Access + Snippet Distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <BotAccessCard />
        <SnippetDistribution />
      </div>

      {/* Section 4: Bot Crawl Activity */}
      <BotCrawlChart />

      {/* Section 5: Platform Citation Preferences */}
      <PlatformPreference />

      {/* Section 6: Findings Table */}
      <FindingsTable
        severityFilter={severityFilter}
        dimensionFilter={dimensionFilter}
      />
    </div>
  );
}
