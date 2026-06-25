'use client';

import { useEffect, useMemo, useState } from 'react';
import { X, ExternalLink } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import type { ContentPiece } from './data';
import { PLATFORM_LIST, formatTraffic } from './data';
import { fetchContentDetail, fetchSimilarContent, generateEmbeddings } from '../_lib/api';
import type { SimilarContentItemAPI } from '../_lib/api';
import { SIGNAL_NAME_TO_FIELD, SIGNAL_FIELD_MAP } from '../_lib/types';
import type { SignalAverageRow, ContentDetailAPI } from '../_lib/types';
import {
  toDrawerTrafficTimeline,
  toDrawerTrafficSources,
  toDrawerPlatformCoverage,
  toDrawerCitationTimeline,
} from '../_lib/adapters';

interface StructuralDetailRow {
  signal: string;
  citedAvg: string;
  yours: string;
  gap: string;
  status: 'above' | 'match' | 'below' | 'missing';
}

function computeCompliance(
  pageSignals: Record<string, number | boolean | string | null> | null,
  citedAverages: SignalAverageRow[],
): StructuralDetailRow[] {
  if (!pageSignals || citedAverages.length === 0) return [];

  return citedAverages.slice(0, 10).map((avg) => {
    const field = SIGNAL_NAME_TO_FIELD[avg.signal];
    const def = field ? SIGNAL_FIELD_MAP[field] : undefined;
    const rawVal = field ? pageSignals[field] : undefined;

    let yours: number | null = null;
    if (rawVal === true) yours = 1;
    else if (rawVal === false) yours = 0;
    else if (typeof rawVal === 'number') yours = rawVal;

    const citedAvg = avg.citation_avg;
    const isBool = def?.isBool ?? false;

    const fmtCited = isBool ? `${Math.round(citedAvg * 100)}%` : `${Math.round(citedAvg * 100) / 100}`;
    const fmtYours = yours === null ? '—' : isBool ? `${yours ? 'Yes' : 'No'}` : `${Math.round(yours * 100) / 100}`;

    let status: StructuralDetailRow['status'] = 'missing';
    let gap = '—';
    if (yours !== null) {
      if (isBool) {
        status = yours >= 1 ? 'above' : citedAvg > 0.5 ? 'below' : 'match';
        gap = yours >= 1 ? '+' : '-';
      } else {
        const diff = yours - citedAvg;
        if (citedAvg === 0) {
          status = yours > 0 ? 'above' : 'match';
        } else if (yours >= citedAvg * 1.1) {
          status = 'above';
        } else if (yours >= citedAvg * 0.9) {
          status = 'match';
        } else {
          status = 'below';
        }
        gap = diff > 0 ? `+${Math.round(diff * 100) / 100}` : `${Math.round(diff * 100) / 100}`;
      }
    }

    return { signal: avg.signal, citedAvg: fmtCited, yours: fmtYours, gap, status };
  });
}

interface ContentDrawerProps {
  piece: ContentPiece | null;
  onClose: () => void;
  signalAverages?: SignalAverageRow[];
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 16 }}>
      <h4 style={{ fontSize: 14, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-primary)', marginBottom: 10 }}>
        {children}
      </h4>
    </div>
  );
}

function UnavailableSection({ message }: { message: string }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 12 }}>
      <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{message}</span>
    </div>
  );
}

function MiniTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: Record<string, unknown> }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, padding: '5px 8px', boxShadow: 'var(--shadow-float)' }}>
      <p style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{d.date as string}</p>
      {d.citations !== undefined && <p style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>{d.citations as number} citations</p>}
      {d.pageviews !== undefined && <p style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-secondary)' }}>{d.pageviews as number} pageviews</p>}
    </div>
  );
}

export function ContentDrawer({ piece, onClose, signalAverages = [] }: ContentDrawerProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  // Fetch full detail from API when drawer opens
  const [detailData, setDetailData] = useState<ContentDetailAPI | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    if (!piece) { setDetailData(null); return; }

    // piece.id is the inventory_id UUID from the adapter
    const invId = piece.id;
    if (!invId) { setDetailData(null); return; }

    const controller = new AbortController();
    setDetailLoading(true);
    setDetailError(null);
    fetchContentDetail(invId, undefined, controller.signal)
      .then((detail) => {
        setDetailData(detail);
        setDetailLoading(false);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setDetailData(null);
          setDetailError(err instanceof Error ? err.message : 'Failed to load page details');
          setDetailLoading(false);
        }
      });
    return () => controller.abort();
  }, [piece]);

  // Fetch similar content (cannibalization) in parallel
  const [similarPages, setSimilarPages] = useState<SimilarContentItemAPI[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [embeddingsReady, setEmbeddingsReady] = useState(true);
  const [generatingEmbeddings, setGeneratingEmbeddings] = useState(false);

  const loadSimilar = (invId: string, signal?: AbortSignal) => {
    setSimilarLoading(true);
    fetchSimilarContent(invId, undefined, signal)
      .then((resp) => {
        setSimilarPages(resp.similar_pages ?? []);
        setEmbeddingsReady(resp.embeddings_ready ?? true);
        setSimilarLoading(false);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setSimilarPages([]);
          setSimilarLoading(false);
        }
      });
  };

  useEffect(() => {
    if (!piece) { setSimilarPages([]); setEmbeddingsReady(true); return; }
    const invId = piece.id;
    if (!invId) { setSimilarPages([]); return; }

    const controller = new AbortController();
    loadSimilar(invId, controller.signal);
    return () => controller.abort();
  }, [piece]);

  const handleGenerateEmbeddings = async () => {
    setGeneratingEmbeddings(true);
    try {
      await generateEmbeddings();
      // Reload similar content after embeddings are generated
      if (piece?.id) loadSimilar(piece.id);
    } catch {
      // Silently fail — user can retry
    } finally {
      setGeneratingEmbeddings(false);
    }
  };

  // Structural compliance from real signals
  const pageSignals = detailData?.structural_signals ?? null;
  const realCompliance = useMemo(
    () => computeCompliance(pageSignals, signalAverages),
    [pageSignals, signalAverages],
  );

  // Traffic timeline from real detail
  const trafficTimeline = useMemo(
    () => detailData?.daily_traffic ? toDrawerTrafficTimeline(detailData.daily_traffic) : [],
    [detailData],
  );

  // Traffic sources from real detail
  const trafficSources = useMemo(
    () => detailData?.source_breakdown ? toDrawerTrafficSources(detailData.source_breakdown) : [],
    [detailData],
  );

  // AI platform breakdown from real detail
  const platformDetails = useMemo(
    () => detailData ? toDrawerPlatformCoverage(detailData.platforms, detailData.ai_platform_breakdown) : [],
    [detailData],
  );
  const hasPlatformSignals = platformDetails.some((pd) => pd.citationPresent || pd.aiSessions > 0);

  // Citation timeline from real detail
  const citationTimeline = useMemo(
    () => detailData?.citation_timeline ? toDrawerCitationTimeline(detailData.citation_timeline) : [],
    [detailData],
  );
  const queriesCovered = detailData?.queries_covered ?? piece?.queriesCovered ?? 0;

  if (!piece) return null;

  const publishedAtValue = detailData?.published_at ?? piece.publishedAt;
  const publishedDate = publishedAtValue
    ? new Date(publishedAtValue).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : '—';
  const freshness = detailData?.freshness;
  const contentAgeDays = freshness?.content_age_days ?? null;
  const lastUpdatedAgeDays = freshness?.last_updated_age_days ?? null;
  const benchmarkAvgAgeDays = freshness?.cited_exemplar_avg_age_days ?? null;
  const benchmarkMedianAgeDays = freshness?.cited_exemplar_median_age_days ?? null;
  const freshnessScore = freshness?.freshness_score ?? null;
  const freshnessStatus = freshness?.freshness_status ?? 'insufficient_data';
  const freshnessReason = freshness?.freshness_reason ?? 'Freshness assessment is unavailable.';

  return (
    <AnimatePresence>
      {piece && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.15)', zIndex: 40 }}
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            style={{
              position: 'fixed', top: 0, right: 0, height: '100vh', width: '50vw',
              background: 'var(--surface)', borderLeft: '1px solid var(--border)',
              boxShadow: 'var(--shadow-float)', zIndex: 50, display: 'flex', flexDirection: 'column',
            }}
          >
            {/* Header */}
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{piece.title}</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6 }}>
                    <a href={piece.url.startsWith('http') ? piece.url : `https://${piece.url}`} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                      {piece.url} <ExternalLink size={10} strokeWidth={1.5} />
                    </a>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Published: {publishedDate}</span>
                    {piece.structuralScore > 0 && (
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        Structural: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{piece.structuralScore}/100</span>
                      </span>
                    )}
                  </div>
                </div>
                <button onClick={onClose} style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none', background: 'none', cursor: 'pointer', borderRadius: 4, color: 'var(--text-tertiary)' }}>
                  <X size={16} strokeWidth={1.5} />
                </button>
              </div>
            </div>

            {/* Scrollable content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '0 20px 20px' }}>
              {detailError && (
                <div style={{ marginTop: 16, border: '1px solid rgba(229,72,77,0.24)', borderRadius: 4, background: 'rgba(229,72,77,0.04)', padding: 12 }}>
                  <span style={{ fontSize: 12, color: '#B42318' }}>
                    Failed to load the full page detail. The drawer is showing fallback empty states until the detail endpoint succeeds again.
                  </span>
                </div>
              )}

              {/* A. CITATION TIMELINE */}
              <SectionHeader>A. Citation Timeline</SectionHeader>
              {detailLoading ? (
                <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Loading citation data...</span>
                </div>
              ) : citationTimeline.length > 0 ? (
                <div style={{ height: 140 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={citationTimeline} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                      <defs>
                        <linearGradient id="citGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--success)" stopOpacity={0.12} />
                          <stop offset="100%" stopColor="var(--success)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={false} width={28} allowDecimals={false} />
                      <Tooltip content={<MiniTooltip />} />
                      <Area type="monotone" dataKey="citations" stroke="var(--success)" strokeWidth={1.5} fill="url(#citGrad)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <UnavailableSection message="No citation data yet. Link prompts to this page via Content-to-Prompt, then run the daily tracker." />
              )}

              {/* B. TRAFFIC */}
              <SectionHeader>B. Traffic</SectionHeader>
              {detailLoading ? (
                <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Loading traffic data...</span>
                </div>
              ) : trafficTimeline.length > 0 ? (
                <>
                  <div style={{ height: 140 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={trafficTimeline} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                        <defs>
                          <linearGradient id="tvGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.12} />
                            <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={false} interval={4} />
                        <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={false} width={32} />
                        <Tooltip content={<MiniTooltip />} />
                        <Area type="monotone" dataKey="pageviews" stroke="var(--accent)" strokeWidth={2} fill="url(#tvGrad)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <div style={{ width: 12, height: 2, borderRadius: 1, background: 'var(--accent)' }} />
                      <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Pageviews</span>
                    </div>
                  </div>
                </>
              ) : (
                <UnavailableSection message="No traffic data available for this page. Ensure GA4 is connected and synced." />
              )}

              {/* C. PLATFORM DISTRIBUTION */}
              <SectionHeader>C. Platform Distribution</SectionHeader>
              {detailLoading ? (
                <div style={{ height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Loading platform data...</span>
                </div>
              ) : hasPlatformSignals ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
                  {platformDetails.map((pd) => (
                    <div key={pd.platform} style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 12, textAlign: 'center', opacity: pd.citationPresent || pd.aiSessions > 0 ? 1 : 0.5 }}>
                      <img src={`https://www.google.com/s2/favicons?domain=${pd.domain}&sz=32`} alt={pd.platform} width={16} height={16} style={{ borderRadius: 3, margin: '0 auto' }} />
                      <p style={{ fontSize: 11, color: 'var(--text-primary)', marginTop: 6 }}>{pd.platform}</p>
                      {pd.citationPresent || pd.aiSessions > 0 ? (
                        <>
                          <p style={{ fontSize: 10, color: pd.citationPresent ? 'var(--success)' : 'var(--text-tertiary)', marginTop: 8 }}>
                            {pd.citationPresent ? 'Seen in citations' : 'No citation hits'}
                          </p>
                          {pd.aiSessions > 0 ? (
                            <>
                              <p style={{ fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>{pd.aiSessions}</p>
                              <p style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>AI referral sessions</p>
                            </>
                          ) : (
                            <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>No AI referrals</p>
                          )}
                        </>
                      ) : (
                        <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 8 }}>No platform signal</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <UnavailableSection message="No citation-platform matches or AI referral sessions are available yet. Run Daily Tracker and sync GA4." />
              )}

              {/* D. STRUCTURAL COMPLIANCE */}
              <SectionHeader>D. Structural Compliance</SectionHeader>
              {detailLoading ? (
                <div style={{ height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Loading structural data...</span>
                </div>
              ) : realCompliance.length > 0 ? (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        {['Signal', 'Cited Avg', 'Yours', 'Gap', 'Status'].map((h) => (
                          <th key={h} style={{ padding: '6px 8px', textAlign: 'left', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {realCompliance.map((sd) => (
                        <tr key={sd.signal} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '6px 8px', fontSize: 12, color: 'var(--text-primary)' }}>{sd.signal}</td>
                          <td style={{ padding: '6px 8px', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{sd.citedAvg}</td>
                          <td style={{ padding: '6px 8px', fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>{sd.yours}</td>
                          <td style={{ padding: '6px 8px', fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 500, color: sd.gap.startsWith('+') ? 'var(--success)' : '#E5484D' }}>{sd.gap}</td>
                          <td style={{ padding: '6px 8px' }}>
                            {sd.status === 'above' && <span style={{ fontSize: 11, color: 'var(--success)' }}>&#10003; Above</span>}
                            {sd.status === 'match' && <span style={{ fontSize: 11, color: 'var(--success)' }}>&#10003; Match</span>}
                            {sd.status === 'below' && <span style={{ fontSize: 11, color: '#F5A623' }}>&#9888; Below</span>}
                            {sd.status === 'missing' && <span style={{ fontSize: 11, color: '#E5484D' }}>&#10007; Missing</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <UnavailableSection message="No structural data available. Run a gap analysis to get signal averages." />
              )}

              <SectionHeader>E. Query Coverage</SectionHeader>
              {detailLoading ? (
                <div style={{ height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Loading query coverage...</span>
                </div>
              ) : (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Gap-analysis queries currently targeting this published URL</span>
                    <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{queriesCovered}</span>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {queriesCovered > 0
                      ? 'This page is already linked to tracked gap-analysis coverage.'
                      : 'No gap-analysis queries currently target this page yet.'}
                  </span>
                </div>
              )}

              {/* F. CANNIBALIZATION RISK */}
              <SectionHeader>F. Cannibalization Risk</SectionHeader>
              {similarLoading || generatingEmbeddings ? (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 16, textAlign: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {generatingEmbeddings ? 'Generating embeddings for your content...' : 'Checking for similar pages...'}
                  </span>
                </div>
              ) : !embeddingsReady ? (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 16 }}>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Content embeddings have not been generated yet. Embeddings are required to detect semantic overlap between your pages.
                  </p>
                  <button onClick={handleGenerateEmbeddings}
                    style={{ height: 30, padding: '0 12px', fontSize: 12, fontWeight: 500, borderRadius: 4, background: 'var(--accent)', color: 'white', border: 'none', cursor: 'pointer' }}>
                    Generate Embeddings
                  </button>
                </div>
              ) : similarPages.length > 0 ? (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        <th style={{ textAlign: 'left', fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-tertiary)', padding: '6px 8px' }}>Similar Page</th>
                        <th style={{ textAlign: 'right', fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-tertiary)', padding: '6px 8px', width: 70 }}>Words</th>
                        <th style={{ textAlign: 'right', fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-tertiary)', padding: '6px 8px', width: 70 }}>Overlap</th>
                      </tr>
                    </thead>
                    <tbody>
                      {similarPages.map((sp, i) => {
                        const overlapPct = Math.round(sp.similarity * 100);
                        const overlapColor = sp.similarity >= 0.90 ? '#E5484D' : sp.similarity >= 0.80 ? '#F5A623' : 'var(--success)';
                        return (
                          <tr key={sp.inventory_id} style={{ borderBottom: i < similarPages.length - 1 ? '1px solid var(--border-subtle)' : undefined }}>
                            <td style={{ padding: '6px 8px' }}>
                              <p style={{ fontSize: 12, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 280 }}>{sp.title}</p>
                              <a href={sp.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: 'var(--text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 280, display: 'block' }}>{sp.url}</a>
                            </td>
                            <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>{sp.word_count.toLocaleString()}</td>
                            <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: overlapColor }}>{overlapPct}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 16 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>No similar pages detected. This content has unique semantic coverage.</span>
                </div>
              )}

              {/* G. BRIEF COMPLIANCE — not yet available */}

              {/* H. FRESHNESS ASSESSMENT */}
              <SectionHeader>H. Freshness Assessment</SectionHeader>
              <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 12 }}>
                <div style={{ display: 'flex', gap: 24, marginBottom: 12 }}>
                  <div>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Content Age</p>
                    <p style={{ marginTop: 2 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 16, color: 'var(--text-primary)' }}>{contentAgeDays ?? '—'}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 4 }}>days</span>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 6 }}>(published {publishedDate})</span>
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Last Updated Age</p>
                    <p style={{ marginTop: 2 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 16, color: 'var(--text-primary)' }}>{lastUpdatedAgeDays ?? '—'}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 4 }}>days</span>
                    </p>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12, marginBottom: 12 }}>
                  <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 4, padding: 10 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>Benchmark Avg Age</div>
                    <div style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {benchmarkAvgAgeDays ?? '—'}
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-sans)', fontWeight: 400, color: 'var(--text-secondary)', marginLeft: 4 }}>days</span>
                    </div>
                  </div>
                  <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 4, padding: 10 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>Benchmark Median Age</div>
                    <div style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {benchmarkMedianAgeDays ?? '—'}
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-sans)', fontWeight: 400, color: 'var(--text-secondary)', marginLeft: 4 }}>days</span>
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Assessment Status</span>
                  <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600, color: freshnessStatus === 'insufficient_data' ? 'var(--text-secondary)' : 'var(--text-primary)' }}>
                    {freshnessStatus}
                  </span>
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>
                  {freshnessReason}
                </p>
                {freshnessScore !== null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Freshness Score</span>
                    <span style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{freshnessScore}/100</span>
                  </div>
                )}
              </div>

              {/* I. TRAFFIC SOURCES */}
              <SectionHeader>I. Traffic Sources</SectionHeader>
              {detailLoading ? (
                <div style={{ height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Loading source data...</span>
                </div>
              ) : trafficSources.length > 0 ? (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                  {trafficSources.map((src, i) => {
                    const maxPct = Math.max(...trafficSources.map((s) => s.pct));
                    return (
                      <div key={src.source} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: i < trafficSources.length - 1 ? '1px solid var(--border-subtle)' : undefined }}>
                        <span style={{ fontSize: 12, color: 'var(--text-primary)', width: 130, flexShrink: 0 }}>{src.source}</span>
                        <div style={{ flex: 1, height: 8, borderRadius: 4, background: 'var(--border)', overflow: 'hidden' }}>
                          <div style={{
                            width: `${maxPct > 0 ? (src.pct / maxPct) * 100 : 0}%`, height: '100%', borderRadius: 4,
                            background: src.source.includes('AI') ? 'var(--accent)' : src.source === 'Organic' ? 'var(--success)' : 'var(--text-tertiary)',
                            opacity: src.source.includes('AI') ? 1 : 0.5,
                          }} />
                        </div>
                        <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', width: 50, textAlign: 'right' }}>{formatTraffic(src.sessions)}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 32, textAlign: 'right' }}>{src.pct}%</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <UnavailableSection message="No traffic source data available. Ensure GA4 is connected and synced." />
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
