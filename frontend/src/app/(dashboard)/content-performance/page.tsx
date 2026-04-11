'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Calendar, X, Search, RefreshCw, Loader2 } from 'lucide-react';
import { MetricCard, FilterBar } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import type { ContentPiece, StructuralSignal, ImpactLevel } from './_components/data';
import type { ContentCard } from '../content-studio/_components/types';
import { adaptBriefList } from '../content-studio/_lib/adapters';
import { FullPageView } from '../content-studio/_components/FullPageView';
import { formatTraffic } from './_components/data';
import {
  fetchSignalAverages, fetchCMSConnection, triggerCMSSync,
  fetchContentPerformanceReadiness,
  generatePromptsForNewPages, fetchTaskStatus, fetchUnpublishedBriefs, publishContentBrief,
} from './_lib/api';
import type {
  ContentPerformanceReadinessAPI,
  SignalAverageRow,
  SignalCorrelationRow,
} from './_lib/types';
import { useContentPerformanceData } from './_hooks/useContentPerformanceData';
import { VelocityChart } from './_components/VelocityChart';
import { StructuralAlignment } from './_components/StructuralAlignment';
import { ContentTable } from './_components/ContentTable';
import { ContentDrawer } from './_components/ContentDrawer';
import { LifecycleDistribution } from './_components/LifecycleDistribution';
import { UnpublishedPagesTable } from './_components/UnpublishedPagesTable';

const LIFECYCLE_OPTIONS = [
  { value: 'all', label: 'All Stages' },
  { value: 'growing', label: 'Growing' },
  { value: 'peaking', label: 'Peaking' },
  { value: 'stable', label: 'Stable' },
  { value: 'declining', label: 'Declining' },
  { value: 'stale', label: 'Stale' },
];

const REPORTING_DAYS = 28;

type Tab = 'pages' | 'unpublished' | 'insights';

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

function getReadinessTitle(state: string): string {
  switch (state) {
    case 'not_connected':
      return 'Google Analytics not connected';
    case 'property_required':
      return 'GA4 property selection required';
    case 'never_synced':
      return 'Initial GA4 sync still pending';
    case 'sync_failed':
      return 'Latest GA4 sync failed';
    case 'no_matching_pages':
      return 'GA4 data is not matching your content inventory yet';
    case 'no_recent_data':
      return 'No matched GA4 page traffic in this reporting window';
    case 'no_data':
      return 'GA4 is connected but no traffic rows are available yet';
    default:
      return 'Analytics setup incomplete';
  }
}

function formatPathSample(path: string): string {
  return path || '/';
}

export default function ContentPerformancePage() {
  const { companySlug, isInitialized } = useAuth();
  const [cluster, setCluster] = useState('all');
  const [lifecycle, setLifecycle] = useState('all');
  const [selectedPiece, setSelectedPiece] = useState<ContentPiece | null>(null);
  const [selectedUnpublishedCard, setSelectedUnpublishedCard] = useState<ContentCard | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('pages');
  const [searchQuery, setSearchQuery] = useState('');
  const [unpublishedCards, setUnpublishedCards] = useState<ContentCard[]>([]);
  const [unpublishedLoading, setUnpublishedLoading] = useState(true);
  const [unpublishedError, setUnpublishedError] = useState<string | null>(null);
  const [publishPendingId, setPublishPendingId] = useState<string | null>(null);

  // Real data from backend
  const {
    pieces, velocityData, periodStart, periodEnd, totalItems,
    isLoading, error, refetch,
  } = useContentPerformanceData({ days: REPORTING_DAYS });
  const [analyticsReadiness, setAnalyticsReadiness] = useState<ContentPerformanceReadinessAPI | null>(null);
  const readinessAbortRef = useRef<AbortController | null>(null);

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

  const loadAnalyticsReadiness = useCallback(async () => {
    if (!companySlug) return;
    readinessAbortRef.current?.abort();
    const controller = new AbortController();
    readinessAbortRef.current = controller;

    try {
      const readiness = await fetchContentPerformanceReadiness(
        { days: REPORTING_DAYS },
        controller.signal,
      );
      if (!controller.signal.aborted) {
        setAnalyticsReadiness(readiness);
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setAnalyticsReadiness(null);
      }
    }
  }, [companySlug]);

  useEffect(() => {
    if (!isInitialized || !companySlug) return;
    loadAnalyticsReadiness();
    return () => readinessAbortRef.current?.abort();
  }, [isInitialized, companySlug, loadAnalyticsReadiness]);

  const refetchAll = useCallback(() => {
    refetch();
    loadAnalyticsReadiness();
  }, [refetch, loadAnalyticsReadiness]);

  const loadUnpublishedCards = useCallback(async () => {
    if (!companySlug) return;
    setUnpublishedLoading(true);
    setUnpublishedError(null);
    try {
      const response = await fetchUnpublishedBriefs(companySlug);
      const adapted = adaptBriefList(response.briefs).filter(
        (card) => card.status === 'completed' && !card.publishedUrl,
      );
      setUnpublishedCards(adapted);
    } catch (err) {
      setUnpublishedError(err instanceof Error ? err.message : 'Failed to load unpublished pages');
    } finally {
      setUnpublishedLoading(false);
    }
  }, [companySlug]);

  useEffect(() => {
    if (!isInitialized || !companySlug) return;
    loadUnpublishedCards();
  }, [isInitialized, companySlug, loadUnpublishedCards]);

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
      refetchAll();

      // Reset after 5 seconds
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 5000);
    } catch (err) {
      setSyncState('error');
      setSyncMessage(err instanceof Error ? err.message : 'Sync failed');
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 5000);
    }
  }, [syncState, cmsConnected, refetchAll]);

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

  const filteredUnpublishedCards = useMemo(() => unpublishedCards, [unpublishedCards]);

  // KPI calculations
  const totalAIReferrals = filteredPieces.reduce((s, p) => s + p.aiReferrals, 0);
  const staleCount = filteredPieces.filter((p) => p.lifecycle === 'stale' || p.lifecycle === 'declining').length;

  const handleRowClick = useCallback((piece: ContentPiece) => setSelectedPiece(piece), []);
  const handleDrawerClose = useCallback(() => setSelectedPiece(null), []);
  const handleUnpublishedRowClick = useCallback((card: ContentCard) => setSelectedUnpublishedCard(card), []);
  const handleUnpublishedClose = useCallback(() => setSelectedUnpublishedCard(null), []);
  const handlePublishUnpublished = useCallback(async () => {
    if (!selectedUnpublishedCard) return;
    setPublishPendingId(selectedUnpublishedCard.id);
    try {
      await publishContentBrief(selectedUnpublishedCard.id, selectedUnpublishedCard.effectiveSlug);
      setSelectedUnpublishedCard(null);
      await loadUnpublishedCards();
      refetchAll();
    } finally {
      setPublishPendingId(null);
    }
  }, [selectedUnpublishedCard, loadUnpublishedCards, refetchAll]);

  const hasSyncedGA4Rows = (analyticsReadiness?.ga4_rows_total ?? 0) > 0;
  const showReadinessBanner = analyticsReadiness !== null && analyticsReadiness.state !== 'ready';

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
        <MetricCard
          label="AI Referrals"
          value={formatTraffic(totalAIReferrals)}
          delta={hasSyncedGA4Rows ? 'from GA4 data' : 'Awaiting GA4 sync'}
          deltaType={hasSyncedGA4Rows ? 'positive' : 'neutral'}
        />
        <MetricCard label="Avg CPS" value="—" delta="Needs CPS scoring" deltaType="neutral" />
        <MetricCard label="Utilization" value="—" delta="Needs citation data" deltaType="neutral" />
        <MetricCard label="Stale Alerts" value={staleCount} delta="velocity below threshold" deltaType={staleCount > 0 ? 'negative' : 'neutral'} />
        <MetricCard
          label="AI Referral Est."
          value={totalAIReferrals > 0 ? `${formatTraffic(totalAIReferrals)}/mo` : '—'}
          delta={
            totalAIReferrals > 0
              ? 'from GA4 AI referrals'
              : hasSyncedGA4Rows
                ? 'No AI referrals detected'
                : 'No GA4 data'
          }
          deltaType={totalAIReferrals > 0 ? 'positive' : 'neutral'}
        />
      </div>

      {showReadinessBanner && (
        <div style={{
          border: '1px solid rgba(245,166,35,0.35)',
          background: 'rgba(245,166,35,0.06)',
          borderRadius: 4,
          padding: '12px 14px',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 16,
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              {getReadinessTitle(analyticsReadiness.state)}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 3, maxWidth: 760 }}>
              {analyticsReadiness.message}
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                Inventory pages: {analyticsReadiness.inventory_pages}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                GA4 rows: {analyticsReadiness.ga4_rows_total}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                Matched pages: {analyticsReadiness.matched_inventory_pages}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                Unmatched GA4 paths: {analyticsReadiness.unmatched_ga4_paths_in_window || analyticsReadiness.unmatched_ga4_paths_total}
              </span>
              {analyticsReadiness.last_sync_status && (
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                  Last sync status: {analyticsReadiness.last_sync_status}
                </span>
              )}
            </div>
            {(analyticsReadiness.inventory_paths_sample.length > 0 || analyticsReadiness.unmatched_ga4_paths_sample.length > 0) && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 16, marginTop: 10 }}>
                {analyticsReadiness.inventory_paths_sample.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                      Inventory path sample
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      {analyticsReadiness.inventory_paths_sample.map((path) => (
                        <span key={path} style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                          {formatPathSample(path)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {analyticsReadiness.unmatched_ga4_paths_sample.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                      Top unmatched GA4 paths in this window
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      {analyticsReadiness.unmatched_ga4_paths_sample.map((item) => (
                        <span key={item.path} style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                          {formatPathSample(item.path)} · {item.sessions} sessions
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            {analyticsReadiness.last_sync_error && (
              <div style={{ fontSize: 11, color: '#E5484D', marginTop: 6 }}>
                {analyticsReadiness.last_sync_error}
              </div>
            )}
          </div>
          <a
            href="/settings?tab=integrations"
            style={{
              flexShrink: 0,
              display: 'inline-flex',
              alignItems: 'center',
              height: 30,
              padding: '0 12px',
              borderRadius: 4,
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              color: 'var(--text-primary)',
              fontSize: 12,
              fontWeight: 500,
              textDecoration: 'none',
            }}
          >
            Open Integrations
          </a>
        </div>
      )}

      {/* Tab bar: Pages / Insights */}
      <div style={{
        display: 'flex', alignItems: 'center', borderBottom: '1px solid var(--border)', padding: '0 4px',
      }}>
        <div style={{ display: 'flex', gap: 0 }}>
          {([
            ['pages', 'Pages'],
            ['unpublished', 'Unpublished Pages'],
            ['insights', 'Insights'],
          ] as const).map(([tab, label]) => (
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
              {label}
            </button>
          ))}
        </div>
        {(activeTab === 'pages' || activeTab === 'unpublished') && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6, height: 30,
              padding: '0 10px', border: '1px solid var(--border)', background: 'transparent',
              borderRadius: 4, width: 200,
            }}>
              <Search size={12} strokeWidth={1.5} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
              <input
                type="text"
                placeholder={activeTab === 'unpublished' ? 'Search unpublished pages...' : 'Search content...'}
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
      {activeTab !== 'unpublished' && error && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', border: '1px solid rgba(229,72,77,0.3)',
          borderRadius: 4, background: 'rgba(229,72,77,0.04)',
        }}>
          <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{error}</span>
          <button
            onClick={refetchAll}
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
      {activeTab !== 'unpublished' && isLoading && pieces.length === 0 && !error && (
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
      {activeTab !== 'unpublished' && !isLoading && !error && pieces.length === 0 && (
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

      {activeTab === 'unpublished' && unpublishedError && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', border: '1px solid rgba(229,72,77,0.3)',
          borderRadius: 4, background: 'rgba(229,72,77,0.04)',
        }}>
          <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{unpublishedError}</span>
          <button
            onClick={loadUnpublishedCards}
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

      {activeTab === 'unpublished' && unpublishedLoading && !unpublishedError && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 48, gap: 8 }}>
          <div style={{
            width: 24, height: 24, border: '2px solid var(--border)',
            borderTopColor: 'var(--accent)', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Loading unpublished pages...</span>
        </div>
      )}

      {activeTab === 'unpublished' && !unpublishedLoading && !unpublishedError && filteredUnpublishedCards.length === 0 && (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: 48, gap: 8, border: '1px solid var(--border)', borderRadius: 4,
        }}>
          <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>No unpublished pages</p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', maxWidth: 400 }}>
            Final approvals from Content Studio land here until you publish them to the connected CMS.
          </p>
        </div>
      )}

      {activeTab === 'unpublished' && !unpublishedLoading && !unpublishedError && filteredUnpublishedCards.length > 0 && (
        <UnpublishedPagesTable
          cards={filteredUnpublishedCards}
          searchQuery={searchQuery}
          onRowClick={handleUnpublishedRowClick}
        />
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
      {selectedUnpublishedCard && (
        <FullPageView
          card={selectedUnpublishedCard}
          onClose={handleUnpublishedClose}
          onAction={async () => {}}
          onPublish={handlePublishUnpublished}
          publishLabel={publishPendingId === selectedUnpublishedCard.id ? 'Publishing...' : 'Publish'}
          isPublishPending={publishPendingId === selectedUnpublishedCard.id}
        />
      )}
    </div>
  );
}
