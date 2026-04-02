'use client';

import { useState, useMemo, useCallback } from 'react';
import { Calendar, X, Search } from 'lucide-react';
import { MetricCard, FilterBar } from '@/components/ui';
import {
  CONTENT_PIECES, STRUCTURAL_SIGNALS, VELOCITY_DATA, CPS_SCATTER,
} from './_components/data';
import type { ContentPiece } from './_components/data';
import { VelocityChart } from './_components/VelocityChart';
import { CPSScatterChart } from './_components/CPSScatterChart';
import { StructuralAlignment } from './_components/StructuralAlignment';
import { ContentTable } from './_components/ContentTable';
import { ContentDrawer } from './_components/ContentDrawer';
import { LifecycleDistribution } from './_components/LifecycleDistribution';

const CLUSTER_OPTIONS = [
  { value: 'all', label: 'All Clusters' },
  ...Array.from(new Set(CONTENT_PIECES.map((p) => p.cluster))).map((c) => ({ value: c, label: c })),
];

const LIFECYCLE_OPTIONS = [
  { value: 'all', label: 'All Stages' },
  { value: 'growing', label: 'Growing' },
  { value: 'peaking', label: 'Peaking' },
  { value: 'stable', label: 'Stable' },
  { value: 'declining', label: 'Declining' },
  { value: 'stale', label: 'Stale' },
];

type Tab = 'pages' | 'insights';

export default function ContentPerformancePage() {
  const [cluster, setCluster] = useState('all');
  const [lifecycle, setLifecycle] = useState('all');
  const [selectedPiece, setSelectedPiece] = useState<ContentPiece | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('pages');
  const [searchQuery, setSearchQuery] = useState('');

  const hasFilters = cluster !== 'all' || lifecycle !== 'all';

  const clearFilters = () => { setCluster('all'); setLifecycle('all'); };

  const filteredPieces = useMemo(() => {
    return CONTENT_PIECES.filter((p) => {
      if (cluster !== 'all' && p.cluster !== cluster) return false;
      if (lifecycle !== 'all' && p.lifecycle !== lifecycle) return false;
      return true;
    });
  }, [cluster, lifecycle]);

  // KPI calculations
  const totalCitations = filteredPieces.reduce((s, p) => s + p.citations, 0);
  const avgCPS = filteredPieces.length > 0 ? filteredPieces.reduce((s, p) => s + p.cps, 0) / filteredPieces.length : 0;
  // Utilization: pieces with meaningful citation presence (CPS > 0.5 = actively earning citations)
  const citedPieces = filteredPieces.filter((p) => p.cps >= 0.5).length;
  const utilization = filteredPieces.length > 0 ? Math.round((citedPieces / filteredPieces.length) * 100) : 0;
  const staleCount = filteredPieces.filter((p) => p.lifecycle === 'stale' || p.lifecycle === 'declining').length;

  const handleRowClick = useCallback((piece: ContentPiece) => setSelectedPiece(piece), []);
  const handleDrawerClose = useCallback(() => setSelectedPiece(null), []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Page title */}
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
          Content Performance
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
          Which of your content is earning citations, and which isn&apos;t?
        </p>
      </div>

      {/* Global Filter Bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, height: 44,
        borderBottom: '1px solid var(--border)', padding: '0 4px', marginTop: -8,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, height: 32,
          padding: '0 10px', border: '1px solid var(--border)', background: 'var(--surface)',
          fontSize: 12, color: 'var(--text-secondary)',
        }}>
          <Calendar size={13} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)' }} />
          <span>Feb 28, 2026 – Mar 27, 2026</span>
        </div>
        <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
        <FilterBar
          filters={[
            { key: 'cluster', label: 'Cluster', options: CLUSTER_OPTIONS, value: cluster },
            { key: 'lifecycle', label: 'Lifecycle', options: LIFECYCLE_OPTIONS, value: lifecycle },
          ]}
          onChange={(key, value) => {
            if (key === 'cluster') setCluster(value);
            if (key === 'lifecycle') setLifecycle(value);
          }}
        />
        {hasFilters && (
          <button
            onClick={clearFilters}
            style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-secondary)', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <X size={12} strokeWidth={1.5} /> Clear
          </button>
        )}
      </div>

      {/* KPI Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12 }}>
        <MetricCard label="Published" value={filteredPieces.length} delta="+3 this week" deltaType="positive" />
        <MetricCard label="Total Citations" value={totalCitations} delta="+38 this period" deltaType="positive" />
        <MetricCard label="Avg CPS" value={avgCPS.toFixed(3)} delta={'\u2191 from 0.48'} deltaType="positive" />
        <MetricCard label="Utilization" value={`${utilization}%`} delta={`${citedPieces}/${filteredPieces.length} pieces cited`} deltaType="positive" />
        <MetricCard label="Stale Alerts" value={staleCount} delta="velocity below threshold" deltaType="negative" />
        <MetricCard label="AI Referral Est." value="~2,400/mo" delta="estimated from citations" deltaType="neutral" />
      </div>

      {/* Tab bar: Pages / Insights */}
      <div style={{
        display: 'flex', alignItems: 'center', borderBottom: '1px solid var(--border)', padding: '0 4px',
      }}>
        <div style={{ display: 'flex', gap: 0 }}>
          {(['pages', 'insights'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: activeTab === tab ? 600 : 400,
                color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-secondary)',
                background: 'none',
                border: 'none',
                borderBottom: activeTab === tab ? '2px solid var(--accent)' : '2px solid transparent',
                cursor: 'pointer',
                textTransform: 'capitalize',
                marginBottom: -1,
              }}
            >
              {tab}
            </button>
          ))}
        </div>
        {activeTab === 'pages' && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6, height: 30,
              padding: '0 10px', border: '1px solid var(--border)', background: 'transparent',
              borderRadius: 4, width: 200,
            }}>
              <Search size={12} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
              <input
                type="text"
                placeholder="Search content..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  border: 'none', background: 'transparent', outline: 'none',
                  fontSize: 12, color: 'var(--text-primary)', width: '100%',
                  fontFamily: 'var(--font-body)',
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Pages tab: Content table as primary view */}
      {activeTab === 'pages' && (
        <ContentTable pieces={filteredPieces} onRowClick={handleRowClick} searchQuery={searchQuery} />
      )}

      {/* Insights tab: Charts + structural signals + lifecycle distribution */}
      {activeTab === 'insights' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Two-column charts: 55% left / 45% right */}
          <div style={{ display: 'grid', gridTemplateColumns: '55fr 45fr', gap: 12 }}>
            <VelocityChart data={VELOCITY_DATA} />
            <CPSScatterChart data={CPS_SCATTER} />
          </div>

          {/* Structural Alignment */}
          <StructuralAlignment signals={STRUCTURAL_SIGNALS} />

          {/* Lifecycle Distribution */}
          <LifecycleDistribution pieces={filteredPieces} />
        </div>
      )}

      {/* Side Drawer */}
      <ContentDrawer piece={selectedPiece} onClose={handleDrawerClose} />
    </div>
  );
}
