'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Calendar, X, Search, RefreshCw, Loader2 } from 'lucide-react';
import { MetricCard, FilterBar } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import type { ContentPiece, StructuralSignal, ImpactLevel } from './_components/data';
import { formatTraffic } from './_components/data';
import {
  fetchSignalAverages, fetchCMSConnection, triggerCMSSync,
  generatePromptsForNewPages, fetchTaskStatus,
} from './_lib/api';
import type { SignalAverageRow, SignalCorrelationRow } from './_lib/types';
import { useContentPerformanceData } from './_hooks/useContentPerformanceData';
import { VelocityChart } from './_components/VelocityChart';
import { StructuralAlignment } from './_components/StructuralAlignment';
import { ContentTable } from './_components/ContentTable';
import { ContentDrawer } from './_components/ContentDrawer';
import { LifecycleDistribution } from './_components/LifecycleDistribution';

const LIFECYCLE_OPTIONS = [
  { value: 'all', label: 'All Stages' },
  { value: 'growing', label: 'Growing' },
  { value: 'peaking', label: 'Peaking' },
  { value: 'stable', label: 'Stable' },
  { value: 'declining', label: 'Declining' },
  { value: 'stale', label: 'Stale' },
];

type Tab = 'pages' | 'insights';

function deriveImpact(r: number): ImpactLevel {
  const absR = Math.abs(r);
  if (absR >= 0.65) return 'critical';
  if (absR >= 0.5) return 'high';
  if (absR >= 0.35) return 'medium';
  return 'low';
}

function buildStructuralSignals(
  averages: SignalAverageRow[],
  correlations: SignalCorrelationRow[],
): StructuralSignal[] {
  const corrMap = new Map(correlations.map((c) => [c.signal, c.correlation]));
  return averages
    .map((avg) => {
      const r = corrMap.get(avg.signal) ?? 0;
      const isBoolSignal = avg.unit === '%';
      const citedAvg = isBoolSignal ? Math.round(avg.citation_avg * 100) : Math.round(avg.citation_avg * 100) / 100;
      const yours = isBoolSignal ? Math.round(avg.company_avg * 100) : Math.round(avg.company_avg * 100) / 100;
      return { signal: avg.signal, r, citedAvg, yours, impact: deriveImpact(r) };
    })
    .sort((a, b) => Math.abs(b.r) - Math.abs(a.r));
}

function formatPeriodDate(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function ContentPerformancePage() {
  const { companySlug } = useAuth();
  const [cluster, setCluster] = useState('all');
  const [lifecycle, setLifecycle] = useState('all');
  const [selectedPiece, setSelectedPiece] = useState<ContentPiece | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('pages');
  const [searchQuery, setSearchQuery] = useState('');

  // Real data from backend
  const {
    pieces, velocityData, periodStart, periodEnd, totalItems,
    isLoading, error, refetch,
  } = useContentPerformanceData({ days: 28 });

  // CMS sync state
  const [cmsConnected, setCmsConnected] = useState<boolean | null>(null); // null = loading
  const [syncState, setSyncState] = useState<'idle' | 'syncing' | 'generating' | 'done' | 'error'>('idle');
  const [syncMessage, setSyncMessage] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Check CMS connection status on mount
  useEffect(() => {
    if (!companySlug) return;
    const controller = new AbortController();
    fetchCMSConnection(controller.signal)
      .then((conn) => setCmsConnected(conn !== null && conn.is_active))
      .catch(() => setCmsConnected(false));
    return () => controller.abort();
  }, [companySlug]);

  // CMS sync + prompt generation handler
  const handleSyncCMS = useCallback(async () => {
    if (syncState !== 'idle' || !cmsConnected) return;

    setSyncState('syncing');
    setSyncMessage('Syncing pages from CMS...');

    try {
      // Step 1: Trigger CMS sync
      const syncResp = await triggerCMSSync();
      const taskId = syncResp.run_id;

      // Step 2: Poll task status until complete
      await new Promise<void>((resolve, reject) => {
        pollRef.current = setInterval(async () => {
          try {
            const status = await fetchTaskStatus(taskId);
            if (status.status === 'completed') {
              if (pollRef.current) clearInterval(pollRef.current);
              resolve();
            } else if (status.status === 'failed') {
              if (pollRef.current) clearInterval(pollRef.current);
              reject(new Error(status.error || 'CMS sync failed'));
            }
          } catch {
            // Polling error — keep trying
          }
        }, 2000);
      });

      // Step 3: Generate prompts for NEW pages only
      setSyncState('generating');
      setSyncMessage('Generating tracking prompts for new pages...');

      const genResp = await generatePromptsForNewPages();

      if (genResp.pages_processed === 0) {
        setSyncMessage('All pages already have tracking prompts.');
      } else {
        setSyncMessage(
          `Synced! ${genResp.prompts_created} prompts created for ${genResp.pages_succeeded} new page${genResp.pages_succeeded !== 1 ? 's' : ''}.`,
        );
      }
      setSyncState('done');

      // Refresh the content table data
      refetch();

      // Reset after 5 seconds
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 5000);
    } catch (err) {
      setSyncState('error');
      setSyncMessage(err instanceof Error ? err.message : 'Sync failed');
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 5000);
    }
  }, [syncState, cmsConnected, refetch]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // Fetch company-level signal averages + correlations
  const [signalAverages, setSignalAverages] = useState<SignalAverageRow[]>([]);
  const [realSignals, setRealSignals] = useState<StructuralSignal[] | null>(null);

  useEffect(() => {
    if (!companySlug) return;
    const controller = new AbortController();
    fetchSignalAverages(companySlug, controller.signal)
      .then((res) => {
        setSignalAverages(res.signals);
        setRealSignals(buildStructuralSignals(res.signals, res.correlations));
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setRealSignals(null);
        }
      });
    return () => controller.abort();
  }, [companySlug]);

  // Derive cluster options from real data
  const clusterOptions = useMemo(() => {
    const clusters = Array.from(new Set(pieces.map((p) => p.cluster).filter(Boolean)));
    return [
      { value: 'all', label: 'All Clusters' },
      ...clusters.map((c) => ({ value: c, label: c })),
    ];
  }, [pieces]);

  const hasFilters = cluster !== 'all' || lifecycle !== 'all';

  const clearFilters = () => { setCluster('all'); setLifecycle('all'); };

  const filteredPieces = useMemo(() => {
    return pieces.filter((p) => {
      if (cluster !== 'all' && p.cluster !== cluster) return false;
      if (lifecycle !== 'all' && p.lifecycle !== lifecycle) return false;
      return true;
    });
  }, [pieces, cluster, lifecycle]);

  // KPI calculations
  const totalAIReferrals = filteredPieces.reduce((s, p) => s + p.aiReferrals, 0);
  const staleCount = filteredPieces.filter((p) => p.lifecycle === 'stale' || p.lifecycle === 'declining').length;

  const handleRowClick = useCallback((piece: ContentPiece) => setSelectedPiece(piece), []);
  const handleDrawerClose = useCallback(() => setSelectedPiece(null), []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Page title + Sync CMS button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
            Content Performance
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Which of your content is earning citations, and which isn&apos;t?
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {syncMessage && (
            <span style={{
              fontSize: 12,
              color: syncState === 'error' ? '#E5484D' : syncState === 'done' ? 'var(--success)' : 'var(--text-secondary)',
              maxWidth: 280, textAlign: 'right',
            }}>
              {syncMessage}
            </span>
          )}
          <button
            onClick={handleSyncCMS}
            disabled={!cmsConnected || syncState !== 'idle'}
            title={cmsConnected === false ? 'Connect CMS in Settings → Integrations first' : cmsConnected === null ? 'Checking CMS connection...' : 'Sync pages from CMS and generate tracking prompts'}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              height: 30, padding: '0 12px', borderRadius: 4,
              fontSize: 12, fontWeight: 500,
              fontFamily: 'var(--font-body)',
              border: '1px solid var(--border)',
              background: cmsConnected && syncState === 'idle' ? 'var(--surface)' : 'transparent',
              color: cmsConnected && syncState === 'idle' ? 'var(--text-primary)' : 'var(--text-tertiary)',
              cursor: cmsConnected && syncState === 'idle' ? 'pointer' : 'not-allowed',
              opacity: cmsConnected && syncState === 'idle' ? 1 : 0.5,
              transition: 'all 0.15s',
            }}
          >
            {syncState === 'syncing' || syncState === 'generating' ? (
              <Loader2 size={13} strokeWidth={1.5} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <RefreshCw size={13} strokeWidth={1.5} />
            )}
            {syncState === 'syncing' ? 'Syncing...' : syncState === 'generating' ? 'Generating...' : 'Sync CMS'}
          </button>
        </div>
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
          <span>{formatPeriodDate(periodStart)} – {formatPeriodDate(periodEnd)}</span>
        </div>
        <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
        <FilterBar
          filters={[
            { key: 'cluster', label: 'Cluster', options: clusterOptions, value: cluster },
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
        <MetricCard label="Published" value={filteredPieces.length} delta={`${totalItems} total`} deltaType="neutral" />
        <MetricCard label="AI Referrals" value={formatTraffic(totalAIReferrals)} delta="from GA4 data" deltaType="positive" />
        <MetricCard label="Avg CPS" value="—" delta="Needs CPS scoring" deltaType="neutral" />
        <MetricCard label="Utilization" value="—" delta="Needs citation data" deltaType="neutral" />
        <MetricCard label="Stale Alerts" value={staleCount} delta="velocity below threshold" deltaType={staleCount > 0 ? 'negative' : 'neutral'} />
        <MetricCard label="AI Referral Est." value={totalAIReferrals > 0 ? `${formatTraffic(totalAIReferrals)}/mo` : '—'} delta={totalAIReferrals > 0 ? 'from GA4 AI referrals' : 'No GA4 data'} deltaType={totalAIReferrals > 0 ? 'positive' : 'neutral'} />
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

      {/* Error state */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', border: '1px solid rgba(229,72,77,0.3)',
          borderRadius: 4, background: 'rgba(229,72,77,0.04)',
        }}>
          <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{error}</span>
          <button
            onClick={refetch}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '4px 10px', fontSize: 12, fontWeight: 500,
              border: '1px solid var(--border)', borderRadius: 4,
              background: 'var(--surface)', color: 'var(--text-primary)',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={12} strokeWidth={1.5} /> Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && pieces.length === 0 && !error && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 48, gap: 8 }}>
          <div style={{
            width: 24, height: 24, border: '2px solid var(--border)',
            borderTopColor: 'var(--accent)', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Loading content performance data...</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && pieces.length === 0 && (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: 48, gap: 8, border: '1px solid var(--border)', borderRadius: 4,
        }}>
          <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>No content inventory found</p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', maxWidth: 400 }}>
            Run the content crawl to populate your content inventory, then connect GA4 to see traffic data.
          </p>
        </div>
      )}

      {/* Pages tab: Content table as primary view */}
      {activeTab === 'pages' && filteredPieces.length > 0 && (
        <ContentTable pieces={filteredPieces} onRowClick={handleRowClick} searchQuery={searchQuery} />
      )}

      {/* Insights tab: Charts + structural signals + lifecycle distribution */}
      {activeTab === 'insights' && pieces.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Velocity chart — full width */}
          <VelocityChart data={velocityData} />

          {/* Structural Alignment */}
          {realSignals ? (
            <StructuralAlignment signals={realSignals} />
          ) : (
            <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 24, textAlign: 'center' }}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                Structural alignment data requires a completed gap analysis run.
              </p>
            </div>
          )}

          {/* Lifecycle Distribution */}
          <LifecycleDistribution pieces={filteredPieces} />
        </div>
      )}

      {/* Side Drawer */}
      <ContentDrawer piece={selectedPiece} onClose={handleDrawerClose} signalAverages={signalAverages} />
    </div>
  );
}
