'use client';

import { useEffect, useMemo, useState } from 'react';
import { X, ExternalLink } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import type { ContentPiece, QueryCoverage as QC } from './data';
import {
  generateCitationTimeline, generateTrafficTimeline, getPlatformDetails,
  getTrafficSources, formatTraffic,
  STRUCTURAL_DETAILS, QUERY_COVERAGE, CANNIBALIZATION_DATA, BRIEF_COMPLIANCE,
} from './data';
import { fetchContentDetail } from '../_lib/api';
import { SIGNAL_NAME_TO_FIELD, SIGNAL_FIELD_MAP } from '../_lib/types';
import type { SignalAverageRow } from '../_lib/types';

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

    // Normalize: booleans → 0 or 1, numbers pass through
    let yours: number | null = null;
    if (rawVal === true) yours = 1;
    else if (rawVal === false) yours = 0;
    else if (typeof rawVal === 'number') yours = rawVal;

    const citedAvg = avg.citation_avg;
    const isBool = def?.isBool ?? false;

    // Format for display
    const fmtCited = isBool ? `${Math.round(citedAvg * 100)}%` : `${Math.round(citedAvg * 100) / 100}`;
    const fmtYours = yours === null ? '—' : isBool ? `${yours ? 'Yes' : 'No'}` : `${Math.round(yours * 100) / 100}`;

    // Compute gap and status
    let status: StructuralDetailRow['status'] = 'missing';
    let gap = '—';
    if (yours !== null) {
      const numCited = isBool ? citedAvg : citedAvg;
      const numYours = isBool ? yours : yours;
      const diff = numYours - numCited;
      if (isBool) {
        // Bool: "Yes" when citedAvg > 0.5 is 'above', otherwise 'below'
        status = yours >= 1 ? 'above' : citedAvg > 0.5 ? 'below' : 'match';
        gap = yours >= 1 ? '+' : '-';
      } else {
        if (numCited === 0) {
          status = numYours > 0 ? 'above' : 'match';
        } else if (numYours >= numCited * 1.1) {
          status = 'above';
        } else if (numYours >= numCited * 0.9) {
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

const CLASSIFICATION_STYLES: Record<string, { bg: string; text: string }> = {
  aligned: { bg: 'var(--success)', text: '#FFFFFF' },
  company_leads: { bg: 'var(--accent)', text: '#FFFFFF' },
  moderate_gap: { bg: '#F5A623', text: '#11181C' },
  significant_gap: { bg: '#E5484D', text: '#FFFFFF' },
};

function ClassificationBadge({ classification }: { classification: string }) {
  const style = CLASSIFICATION_STYLES[classification] || { bg: 'var(--text-tertiary)', text: '#FFFFFF' };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', height: 18, padding: '0 6px', borderRadius: 4, fontSize: 10, fontWeight: 600, textTransform: 'uppercase', background: style.bg, color: style.text, whiteSpace: 'nowrap' }}>
      {classification.replace(/_/g, ' ')}
    </span>
  );
}

export function ContentDrawer({ piece, onClose, signalAverages = [] }: ContentDrawerProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const timeline = useMemo(() => piece ? generateCitationTimeline(piece.citations) : [], [piece]);
  const trafficTimeline = useMemo(() => piece ? generateTrafficTimeline(piece.traffic) : [], [piece]);
  const platformDetails = useMemo(() => piece ? getPlatformDetails(piece) : [], [piece]);
  const trafficSources = useMemo(() => piece ? getTrafficSources(piece) : [], [piece]);

  // Fetch per-page structural signals from API when drawer opens
  const [pageSignals, setPageSignals] = useState<Record<string, number | boolean | string | null> | null>(null);
  const [signalsLoading, setSignalsLoading] = useState(false);

  useEffect(() => {
    if (!piece) { setPageSignals(null); return; }
    // Use inventory_id if available (real data), otherwise skip API fetch
    const pieceAny = piece as unknown as Record<string, unknown>;
    const invId = pieceAny.inventoryId ?? pieceAny.inventory_id;
    if (!invId || typeof invId !== 'string') { setPageSignals(null); return; }

    const controller = new AbortController();
    setSignalsLoading(true);
    fetchContentDetail(invId, undefined, controller.signal)
      .then((detail) => {
        setPageSignals(detail.structural_signals);
        setSignalsLoading(false);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setPageSignals(null);
          setSignalsLoading(false);
        }
      });
    return () => controller.abort();
  }, [piece]);

  if (!piece) return null;

  // Compute real structural compliance or fall back to mock
  const realCompliance = useMemo(
    () => computeCompliance(pageSignals, signalAverages),
    [pageSignals, signalAverages],
  );
  const structuralDetails = realCompliance.length > 0 ? realCompliance : (STRUCTURAL_DETAILS[piece.id] || []);
  const queryCoverage: QC[] = QUERY_COVERAGE[piece.id] || [];
  const cannibalization = CANNIBALIZATION_DATA[piece.id] || [];
  const briefCompliance = BRIEF_COMPLIANCE[piece.id];
  const publishedDate = new Date(piece.publishedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const exemplarAvgAge = Math.round(piece.freshnessDays * 0.56);
  const freshnessScore = Math.max(0, Math.min(100, 100 - Math.max(0, (piece.freshnessDays - exemplarAvgAge) - 10) * 2));

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
                    <a href={`https://${piece.url}`} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                      {piece.url} <ExternalLink size={10} strokeWidth={1.5} />
                    </a>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Published: {publishedDate}</span>
                  </div>
                </div>
                <button onClick={onClose} style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none', background: 'none', cursor: 'pointer', borderRadius: 4, color: 'var(--text-tertiary)' }}>
                  <X size={16} strokeWidth={1.5} />
                </button>
              </div>
            </div>

            {/* Scrollable content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '0 20px 20px' }}>

              {/* A. CITATION TIMELINE */}
              <SectionHeader>A. Citation Timeline</SectionHeader>
              <div style={{ height: 120 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={timeline} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="ctGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.1} />
                        <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} tickLine={false} axisLine={false} interval={4} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }} tickLine={false} axisLine={false} width={28} />
                    <Tooltip content={<MiniTooltip />} />
                    <Area type="monotone" dataKey="citations" stroke="var(--accent)" strokeWidth={2} fill="url(#ctGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* B. TRAFFIC */}
              <SectionHeader>B. Traffic</SectionHeader>
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

              {/* C. PLATFORM DISTRIBUTION */}
              <SectionHeader>C. Platform Distribution</SectionHeader>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
                {platformDetails.map((pd) => (
                  <div key={pd.platform} style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 12, textAlign: 'center', opacity: pd.cited ? 1 : 0.5 }}>
                    <img src={`https://www.google.com/s2/favicons?domain=${pd.domain}&sz=32`} alt={pd.platform} width={16} height={16} style={{ borderRadius: 3, margin: '0 auto' }} />
                    <p style={{ fontSize: 11, color: 'var(--text-primary)', marginTop: 6 }}>{pd.platform}</p>
                    {pd.cited ? (
                      <>
                        <p style={{ fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>{pd.citations}</p>
                        <p style={{ fontSize: 10, color: 'var(--success)', marginTop: 2 }}>Cited &#10003;</p>
                      </>
                    ) : (
                      <p style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 8 }}>Not cited &#10007;</p>
                    )}
                  </div>
                ))}
              </div>

              {/* D. STRUCTURAL COMPLIANCE */}
              <SectionHeader>D. Structural Compliance</SectionHeader>
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
                    {structuralDetails.map((sd) => (
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

              {/* E. QUERY COVERAGE */}
              <SectionHeader>E. Query Coverage</SectionHeader>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>{queryCoverage.length} queries this content serves</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {queryCoverage.map((q, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', border: '1px solid var(--border-subtle)', borderRadius: 4 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-primary)', flex: 1 }}>{q.query}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 8, flexShrink: 0 }}>
                      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 500, color: q.gapScore <= 0.2 ? 'var(--success)' : q.gapScore <= 0.5 ? '#F5A623' : '#E5484D' }}>{q.gapScore.toFixed(2)}</span>
                      <ClassificationBadge classification={q.classification} />
                    </div>
                  </div>
                ))}
              </div>

              {/* F. CANNIBALIZATION RISK */}
              <SectionHeader>F. Cannibalization Risk</SectionHeader>
              {cannibalization.length > 0 ? (
                <div style={{ border: '1px solid rgba(245,166,35,0.3)', borderRadius: 4, padding: 12, background: 'rgba(245,166,35,0.04)' }}>
                  <p style={{ fontSize: 12, color: 'var(--text-primary)', marginBottom: 8 }}>
                    &#9888; This page competes with {cannibalization.length} other page{cannibalization.length > 1 ? 's' : ''} for the same citations:
                  </p>
                  {cannibalization.map((c, i) => (
                    <div key={i} style={{ marginBottom: 6 }}>
                      <a href={`https://${c.url}`} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}>&ldquo;{c.title}&rdquo;</a>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 8 }}>— similarity: <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{c.similarity.toFixed(2)}</span></span>
                    </div>
                  ))}
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>Recommendation: Differentiate by focusing on different comparison angles.</p>
                </div>
              ) : (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 12 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>&#10003; No cannibalization detected — this content has unique query coverage.</span>
                </div>
              )}

              {/* G. BRIEF COMPLIANCE — hidden until backend data is available */}
              {/* <SectionHeader>G. Brief Compliance</SectionHeader>
              {briefCompliance ? (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Word Count</span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        Target <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{briefCompliance.wordCountTarget.toLocaleString()}</span>
                        {' | '}Actual <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{briefCompliance.wordCountActual.toLocaleString()}</span>
                        {' | '}<span style={{ fontWeight: 500, color: briefCompliance.wordCountActual >= briefCompliance.wordCountTarget ? 'var(--success)' : '#F5A623' }}>
                          {Math.round((briefCompliance.wordCountActual / briefCompliance.wordCountTarget) * 100)}% of target
                        </span>
                      </span>
                    </div>
                    <div style={{ width: '100%', height: 8, borderRadius: 4, background: 'var(--border)', overflow: 'hidden' }}>
                      <div style={{ width: `${Math.min(100, (briefCompliance.wordCountActual / briefCompliance.wordCountTarget) * 100)}%`, height: '100%', borderRadius: 4, background: briefCompliance.wordCountActual >= briefCompliance.wordCountTarget ? 'var(--success)' : '#F5A623' }} />
                    </div>
                  </div>
                  <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
                    <p style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: 6 }}>Required Elements</p>
                    {briefCompliance.requiredElements.map((el) => (
                      <div key={el.element} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0' }}>
                        <span style={{ fontSize: 12, color: el.present ? 'var(--success)' : '#E5484D' }}>{el.present ? '\u2705' : '\u274C'}</span>
                        <span style={{ fontSize: 12, color: el.present ? 'var(--text-primary)' : 'var(--text-secondary)' }}>{el.element} {el.present ? 'present' : 'missing'}</span>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Reading Level</span>
                    <span style={{ fontSize: 12 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)' }}>{briefCompliance.readingLevelActual}</span>
                      <span style={{ color: 'var(--text-tertiary)', marginLeft: 6 }}>(target: {briefCompliance.readingLevelTarget})</span>
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px' }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>Brief Compliance Score</span>
                    <span style={{ fontSize: 16, fontFamily: 'var(--font-mono)', fontWeight: 600, color: piece.briefCompliance >= 80 ? 'var(--success)' : piece.briefCompliance >= 60 ? '#F5A623' : '#E5484D' }}>{piece.briefCompliance}%</span>
                  </div>
                </div>
              ) : (
                <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 12 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>No content brief found</span>
                </div>
              )} */}

              {/* H. FRESHNESS ASSESSMENT */}
              <SectionHeader>H. Freshness Assessment</SectionHeader>
              <div style={{ border: '1px solid var(--border)', borderRadius: 4, padding: 12 }}>
                <div style={{ display: 'flex', gap: 24, marginBottom: 12 }}>
                  <div>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Content Age</p>
                    <p style={{ marginTop: 2 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 16, color: 'var(--text-primary)' }}>{piece.freshnessDays}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 4 }}>days</span>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 6 }}>(published {publishedDate})</span>
                    </p>
                  </div>
                  <div>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Cited Exemplar Avg Age</p>
                    <p style={{ marginTop: 2 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 16, color: 'var(--text-primary)' }}>{exemplarAvgAge}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 4 }}>days</span>
                    </p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3 }}>Your content</div>
                    <div style={{ width: '100%', height: 10, borderRadius: 5, background: 'var(--border)', overflow: 'hidden' }}>
                      <div style={{ width: `${Math.min(100, (piece.freshnessDays / Math.max(piece.freshnessDays, exemplarAvgAge)) * 100)}%`, height: '100%', borderRadius: 5, background: piece.freshnessDays - exemplarAvgAge > 30 ? '#E5484D' : piece.freshnessDays - exemplarAvgAge > 0 ? '#F5A623' : 'var(--success)' }} />
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3 }}>Cited avg</div>
                    <div style={{ width: '100%', height: 10, borderRadius: 5, background: 'var(--border)', overflow: 'hidden' }}>
                      <div style={{ width: `${Math.min(100, (exemplarAvgAge / Math.max(piece.freshnessDays, exemplarAvgAge)) * 100)}%`, height: '100%', borderRadius: 5, background: 'var(--success)' }} />
                    </div>
                  </div>
                </div>
                {piece.freshnessDays > exemplarAvgAge && (
                  <div style={{ background: 'rgba(245,166,35,0.06)', border: '1px solid rgba(245,166,35,0.2)', borderRadius: 4, padding: '8px 10px', marginBottom: 8 }}>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      &#9888; Your content is <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{piece.freshnessDays - exemplarAvgAge}</span> days older than the average cited piece. Consider refreshing with updated data and recent developments.
                    </p>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Freshness Score</span>
                  <span style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 600, color: freshnessScore >= 70 ? 'var(--success)' : freshnessScore >= 50 ? '#F5A623' : '#E5484D' }}>{freshnessScore}/100</span>
                </div>
              </div>

              {/* I. TRAFFIC SOURCES */}
              <SectionHeader>I. Traffic Sources</SectionHeader>
              <div style={{ border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                {trafficSources.map((src, i) => {
                  const maxPct = Math.max(...trafficSources.map((s) => s.pct));
                  return (
                    <div key={src.source} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: i < trafficSources.length - 1 ? '1px solid var(--border-subtle)' : undefined }}>
                      <span style={{ fontSize: 12, color: 'var(--text-primary)', width: 130, flexShrink: 0 }}>{src.source}</span>
                      <div style={{ flex: 1, height: 8, borderRadius: 4, background: 'var(--border)', overflow: 'hidden' }}>
                        <div style={{
                          width: `${(src.pct / maxPct) * 100}%`, height: '100%', borderRadius: 4,
                          background: src.source.includes('AI') ? 'var(--accent)' : src.source === 'Organic Search' ? 'var(--success)' : 'var(--text-tertiary)',
                          opacity: src.source.includes('AI') ? 1 : 0.5,
                        }} />
                      </div>
                      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--text-primary)', width: 50, textAlign: 'right' }}>{formatTraffic(src.sessions)}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 32, textAlign: 'right' }}>{src.pct}%</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
