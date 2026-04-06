'use client';

import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Check, X } from 'lucide-react';
import * as d3 from 'd3';
import {
  ClusterProfile,
  GAP_QUERIES,
  CLUSTER_COLORS,
  ENGINE_KEYS,
  ENGINE_META,
  PER_CLUSTER_PROXIMITY,
  EmbeddingPoint,
  GapQuery,
} from './data';
import { BrandLogo } from './brand-logo';

// ── Extended DomainEntry (topDomains in cluster-profiles.json has extra fields) ──
interface ExtendedDomain {
  domain: string;
  citations: number;
  share: number;
  isCompany: boolean;
  type: 'direct' | 'mindshare' | 'authority' | 'company';
  avgWordCount: number | null;
  avgHeaderCount: number | null;
  faqRate: number;
  tableRate: number;
  avgReadingLevel: number | null;
  contentType: string | null;
  authorityType: string | null;
}

// ── Props ────────────────────────────────────────────────────
interface ClusterDrawerProps {
  cluster: ClusterProfile | null;
  onClose: () => void;
}

// ── Helpers ──────────────────────────────────────────────────
function formatPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

function formatRate(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

function gapColor(gap: number): string {
  if (gap > 0.15) return 'var(--danger, #EF4444)';
  if (gap > 0.05) return 'var(--warning, #F59E0B)';
  return 'var(--success, #10B981)';
}

function classificationColor(c: string): { bg: string; text: string } {
  switch (c) {
    case 'significant_gap':
      return { bg: 'rgba(239,68,68,0.1)', text: '#EF4444' };
    case 'moderate_gap':
      return { bg: 'rgba(245,158,11,0.1)', text: '#F59E0B' };
    case 'minor_gap':
      return { bg: 'rgba(16,185,129,0.1)', text: '#10B981' };
    case 'no_gap':
      return { bg: 'rgba(16,185,129,0.1)', text: '#10B981' };
    default:
      return { bg: 'rgba(107,114,128,0.1)', text: 'var(--text-tertiary)' };
  }
}

function typeColor(type: string): { bg: string; text: string } {
  switch (type) {
    case 'direct':
      return { bg: 'rgba(91,164,196,0.12)', text: 'var(--accent, #5BA4C4)' };
    case 'mindshare':
      return { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B' };
    case 'authority':
      return { bg: 'rgba(139,92,246,0.12)', text: '#8B5CF6' };
    case 'company':
      return { bg: 'rgba(91,164,196,0.12)', text: 'var(--accent, #5BA4C4)' };
    default:
      return { bg: 'rgba(107,114,128,0.1)', text: 'var(--text-tertiary)' };
  }
}

function formatLabel(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Section header component ──────────────────────────────────
function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3
      className="font-display"
      style={{
        fontSize: 10,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        color: 'var(--text-tertiary)',
        marginBottom: 12,
      }}
    >
      {children}
    </h3>
  );
}

// ── Mini Metric Card (for Overview tab) ─────────────────────
function OverviewMetricCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="border border-border rounded-md p-2.5">
      <div
        className="font-display"
        style={{
          fontSize: 9,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          color: 'var(--text-tertiary)',
        }}
      >
        {label}
      </div>
      <div
        className="font-mono"
        style={{ fontSize: 18, fontWeight: 600, marginTop: 2, color: color || 'var(--text-primary)' }}
      >
        {value}
      </div>
    </div>
  );
}

// ── Overview Section (summary dashboard) ─────────────────────
function OverviewSection({ cluster }: { cluster: ClusterProfile }) {
  const clusterGaps = GAP_QUERIES.filter((g) => g.clusterId === cluster.id);
  const cited = clusterGaps.filter((g) => g.companyCited).length;
  const prox = PER_CLUSTER_PROXIMITY[cluster.id];

  return (
    <div className="space-y-4">
      {/* Key metrics grid */}
      <div className="grid grid-cols-4 gap-3">
        <OverviewMetricCard label="CITATIONS" value={cluster.totalCitations} />
        <OverviewMetricCard
          label="YOUR SHARE"
          value={`${cluster.companyShare}%`}
          color={cluster.companyShare > 0 ? 'var(--success, #10B981)' : 'var(--error, #EF4444)'}
        />
        <OverviewMetricCard label="RANK" value={cluster.companyRank ? `#${cluster.companyRank}` : '\u2014'} />
        <OverviewMetricCard label="COVERAGE" value={`${cited}/${clusterGaps.length}`} />
      </div>

      {/* Similarity stats */}
      {prox && (
        <div className="border border-border rounded-md p-3">
          <h4
            className="font-display"
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-tertiary)',
              marginBottom: 8,
            }}
          >
            Semantic Positioning
          </h4>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div>
              <span className="font-display" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                Citation mean
              </span>
              <div className="font-mono" style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                {prox.mean.toFixed(3)}
              </div>
            </div>
            <div>
              <span className="font-display" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                Std dev
              </span>
              <div className="font-mono" style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                {prox.std.toFixed(3)}
              </div>
            </div>
            <div>
              <span className="font-display" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                Points
              </span>
              <div className="font-mono" style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                {prox.count}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Top 5 domains (mini preview) */}
      <div className="border border-border rounded-md p-3">
        <h4
          className="font-display"
          style={{
            fontSize: 10,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'var(--text-tertiary)',
            marginBottom: 8,
          }}
        >
          Top Domains
        </h4>
        {cluster.topDomains.slice(0, 5).map((d, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
            <span className="font-mono" style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 16 }}>
              {i + 1}
            </span>
            <img
              src={`https://www.google.com/s2/favicons?domain=${d.domain}&sz=16`}
              width={14}
              height={14}
              style={{ borderRadius: 2 }}
              alt={d.domain}
            />
            <span
              className="font-display"
              style={{
                fontSize: 12,
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                color: d.isCompany ? 'var(--accent, #5BA4C4)' : 'var(--text-primary)',
                fontWeight: d.isCompany ? 500 : 400,
              }}
            >
              {d.domain}
            </span>
            <span className="font-mono" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              {d.citations} cit
            </span>
          </div>
        ))}
      </div>

      {/* Structural summary */}
      <div className="border border-border rounded-md p-3">
        <h4
          className="font-display"
          style={{
            fontSize: 10,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'var(--text-tertiary)',
            marginBottom: 8,
          }}
        >
          Content Profile
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div className="font-display" style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>Avg words:</span>{' '}
            <span className="font-mono">{cluster.avgWordCount}</span>
          </div>
          <div className="font-display" style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>Content type:</span>{' '}
            <span>{cluster.dominantContentType?.replace(/_/g, ' ')}</span>
          </div>
          <div className="font-display" style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>Authority:</span>{' '}
            <span>{cluster.dominantAuthorityType?.replace(/_/g, ' ')}</span>
          </div>
          <div className="font-display" style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>Queries:</span>{' '}
            <span className="font-mono">{cluster.queryCount}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Competitor Table ──────────────────────────────────────────
function CompetitorTable({ cluster, onDomainClick }: { cluster: ClusterProfile; onDomainClick?: (domain: string) => void }) {
  const domains = (cluster.topDomains as unknown as ExtendedDomain[]).slice(0, 15);

  return (
    <div>
      <SectionHeader>Competitors &middot; Top 15 Domains</SectionHeader>
      <div
        className="overflow-x-auto"
        style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md, 6px)' }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr
              style={{
                borderBottom: '1px solid var(--border)',
                background: 'var(--surface-raised, var(--surface))',
              }}
            >
              {['#', 'Domain', 'Cit.', 'Share', 'Words', 'Hdrs', 'FAQ', 'Tbl', 'Type'].map(
                (h) => (
                  <th
                    key={h}
                    className="font-display"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: 'var(--text-tertiary)',
                      padding: '6px 8px',
                      textAlign: h === 'Domain' ? 'left' : 'right',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {domains.map((d, i) => (
              <motion.tr
                key={d.domain}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.025, duration: 0.2 }}
                onClick={() => onDomainClick?.(d.domain.replace(/^www\./, ''))}
                style={{
                  height: 32,
                  borderBottom: '1px solid var(--border)',
                  background: d.isCompany ? 'var(--accent-subtle, rgba(91,164,196,0.08))' : 'transparent',
                  cursor: onDomainClick ? 'pointer' : 'default',
                  transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => {
                  if (!d.isCompany) e.currentTarget.style.background = 'var(--surface-raised, var(--surface))';
                }}
                onMouseLeave={(e) => {
                  if (!d.isCompany) e.currentTarget.style.background = 'transparent';
                }}
              >
                {/* Rank */}
                <td
                  className="font-mono"
                  style={{
                    fontSize: 11,
                    color: 'var(--text-tertiary)',
                    padding: '6px 8px',
                    textAlign: 'right',
                    width: 32,
                  }}
                >
                  {i + 1}
                </td>
                {/* Domain */}
                <td
                  style={{
                    fontSize: 12,
                    padding: '6px 8px',
                    textAlign: 'left',
                    maxWidth: 180,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    color: d.isCompany ? 'var(--accent, #5BA4C4)' : 'var(--text-primary)',
                  }}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <BrandLogo domain={d.domain.replace(/^www\./, '')} size={14} />
                    <span className="font-display" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {d.domain.replace(/^www\./, '')}
                    </span>
                  </span>
                </td>
                {/* Citations */}
                <td className="font-mono" style={{ fontSize: 12, padding: '6px 8px', textAlign: 'right' }}>
                  {d.citations}
                </td>
                {/* Share */}
                <td className="font-mono" style={{ fontSize: 12, padding: '6px 8px', textAlign: 'right' }}>
                  {formatPct(d.share)}
                </td>
                {/* Words */}
                <td className="font-mono" style={{ fontSize: 11, padding: '6px 8px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                  {d.avgWordCount != null ? d.avgWordCount.toLocaleString() : '\u2014'}
                </td>
                {/* Headers */}
                <td className="font-mono" style={{ fontSize: 11, padding: '6px 8px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                  {d.avgHeaderCount != null ? d.avgHeaderCount : '\u2014'}
                </td>
                {/* FAQ */}
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                  {d.faqRate > 0.3 ? (
                    <Check size={10} style={{ color: '#10B981', display: 'inline' }} />
                  ) : (
                    <X size={10} style={{ color: '#EF4444', display: 'inline' }} />
                  )}
                </td>
                {/* Tables */}
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                  {d.tableRate > 0.3 ? (
                    <Check size={10} style={{ color: '#10B981', display: 'inline' }} />
                  ) : (
                    <X size={10} style={{ color: '#EF4444', display: 'inline' }} />
                  )}
                </td>
                {/* Type badge */}
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                  <span
                    className="font-display"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      padding: '1px 6px',
                      borderRadius: 9999,
                      background: typeColor(d.type).bg,
                      color: typeColor(d.type).text,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {d.type}
                  </span>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Structural Analysis ──────────────────────────────────────
function StructuralAnalysis({ cluster }: { cluster: ClusterProfile }) {
  const metrics = [
    { label: 'AVG WORDS', value: cluster.avgWordCount.toLocaleString() },
    { label: 'CONTENT TYPE', value: formatLabel(cluster.dominantContentType) },
    { label: 'AUTHORITY', value: formatLabel(cluster.dominantAuthorityType) },
    { label: 'QUERIES', value: String(cluster.queryCount) },
  ];

  // Structural rates sorted by rate descending
  const rates = [
    ...Object.entries(cluster.structuralRates).map(([k, v]) => ({ label: k, rate: v })),
    { label: 'faq', rate: cluster.faqRate },
    { label: 'tables', rate: cluster.tableRate },
  ].sort((a, b) => b.rate - a.rate);

  return (
    <div>
      <SectionHeader>Winning Content Profile</SectionHeader>

      {/* 2x2 metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
        {metrics.map((m, i) => (
          <motion.div
            key={m.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.025, duration: 0.2 }}
            style={{
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md, 6px)',
              padding: 12,
            }}
          >
            <div
              className="font-mono"
              style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.2 }}
            >
              {m.value}
            </div>
            <div
              className="font-display"
              style={{
                fontSize: 9,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: 'var(--text-tertiary)',
                marginTop: 4,
              }}
            >
              {m.label}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Structural rate bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}>
        {rates.map((r) => (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              className="font-display"
              style={{
                fontSize: 12,
                color: 'var(--text-secondary)',
                width: 72,
                flexShrink: 0,
                textTransform: 'capitalize',
              }}
            >
              {r.label}
            </span>
            <div
              style={{
                flex: 1,
                height: 6,
                borderRadius: 3,
                background: 'var(--border)',
                overflow: 'hidden',
              }}
            >
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(r.rate * 100, 100)}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                style={{
                  height: '100%',
                  borderRadius: 3,
                  background: cluster.color,
                }}
              />
            </div>
            <span
              className="font-mono"
              style={{ fontSize: 11, color: 'var(--text-secondary)', width: 36, textAlign: 'right', flexShrink: 0 }}
            >
              {formatRate(r.rate)}
            </span>
          </div>
        ))}
      </div>

      {/* Required elements */}
      {cluster.requiredElements.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div
            className="font-display"
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-tertiary)',
              marginBottom: 6,
            }}
          >
            Required Elements
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {cluster.requiredElements.map((el) => (
              <span
                key={el}
                className="font-display"
                style={{
                  fontSize: 10,
                  border: '1px solid var(--border)',
                  borderRadius: 9999,
                  padding: '2px 8px',
                  color: 'var(--text-secondary)',
                  whiteSpace: 'nowrap',
                }}
              >
                {el}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Exemplar themes */}
      {cluster.exemplarThemes.length > 0 && (
        <div>
          <div
            className="font-display"
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-tertiary)',
              marginBottom: 6,
            }}
          >
            Exemplar Themes
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {cluster.exemplarThemes.map((th) => (
              <span
                key={th}
                className="font-display"
                style={{
                  fontSize: 10,
                  border: '1px solid var(--border)',
                  borderRadius: 9999,
                  padding: '2px 8px',
                  color: 'var(--text-secondary)',
                  whiteSpace: 'nowrap',
                }}
              >
                {th}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Query Row (expandable) ───────────────────────────────────
function QueryRow({
  gap,
  expanded,
  onToggle,
  index,
}: {
  gap: GapQuery;
  expanded: boolean;
  onToggle: () => void;
  index: number;
}) {
  const topExemplar = gap.exemplars[0] ?? null;
  const clsColor = classificationColor(gap.classification);
  const brief = gap.contentBrief;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.025, duration: 0.2 }}
      style={{
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md, 6px)',
        marginBottom: 6,
        overflow: 'hidden',
      }}
    >
      {/* Collapsed header */}
      <button
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          width: '100%',
          padding: '10px 12px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          transition: 'background 0.12s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'var(--surface-raised, var(--surface))';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent';
        }}
      >
        {/* Chevron */}
        <span style={{ marginTop: 2, color: 'var(--text-tertiary)', flexShrink: 0 }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Query text */}
          <div
            className="font-display"
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--text-primary)',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              lineHeight: 1.4,
            }}
          >
            {gap.query}
          </div>

          {/* Meta row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
            {/* Gap value */}
            <span className="font-mono" style={{ fontSize: 12, color: gapColor(gap.gap) }}>
              Gap: {formatPct(gap.gap * 100)}
            </span>
            {/* Classification badge */}
            <span
              className="font-display"
              style={{
                fontSize: 10,
                fontWeight: 600,
                padding: '1px 6px',
                borderRadius: 9999,
                background: clsColor.bg,
                color: clsColor.text,
                whiteSpace: 'nowrap',
              }}
            >
              {gap.classification.replace(/_/g, ' ')}
            </span>
            {/* Cited? */}
            <span style={{ fontSize: 11, color: gap.companyCited ? '#10B981' : '#EF4444' }}>
              &middot; {gap.companyCited ? 'Cited \u2713' : 'Not cited'}
            </span>
          </div>

          {/* Top exemplar */}
          {topExemplar && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                marginTop: 4,
                fontSize: 11,
                color: 'var(--text-secondary)',
              }}
            >
              <span style={{ color: 'var(--text-tertiary)' }}>Top:</span>
              <BrandLogo domain={topExemplar.domain} size={12} />
              <span className="font-display">{topExemplar.domain}</span>
              <span className="font-mono" style={{ color: 'var(--text-tertiary)' }}>
                ({topExemplar.similarity.toFixed(3)})
              </span>
            </div>
          )}
        </div>
      </button>

      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <div
              style={{
                padding: '0 12px 12px 34px',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              {/* Target Content Brief */}
              <div>
                <div
                  className="font-display"
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'var(--text-tertiary)',
                    marginBottom: 6,
                  }}
                >
                  Target Content Brief
                </div>
                <div
                  className="font-mono"
                  style={{
                    fontSize: 11,
                    color: 'var(--text-secondary)',
                    lineHeight: 1.8,
                  }}
                >
                  {brief.wordCountRange && (
                    <span>
                      Words: {brief.wordCountRange[0].toLocaleString()}&ndash;{brief.wordCountRange[1].toLocaleString()}
                    </span>
                  )}
                  {brief.readingLevelRange && (
                    <span>
                      {' '}&middot; Reading level: {brief.readingLevelRange[0]}&ndash;{brief.readingLevelRange[1]}
                    </span>
                  )}
                  {brief.headerHierarchy && (
                    <span>
                      {' '}&middot; Headers:{' '}
                      {Object.entries(brief.headerHierarchy)
                        .map(([k, v]) => `${k.toUpperCase()}\u00D7${v}`)
                        .join(', ')}
                    </span>
                  )}
                  <br />
                  FAQ: {formatRate(brief.hasFaq)}
                  {' '}&middot; Tables: {formatRate(brief.hasTables)}
                  {brief.hasDefinition > 0 && <span> &middot; Definition: {formatRate(brief.hasDefinition)}</span>}
                  {brief.hasKeyTakeaways > 0 && <span> &middot; Key Takeaways: {formatRate(brief.hasKeyTakeaways)}</span>}
                  {brief.hasStepByStep > 0 && <span> &middot; Step-by-step: {formatRate(brief.hasStepByStep)}</span>}
                </div>
              </div>

              {/* Top Exemplar detail */}
              {topExemplar && (
                <div>
                  <div
                    className="font-display"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: 'var(--text-tertiary)',
                      marginBottom: 6,
                    }}
                  >
                    Top Exemplar
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                    <BrandLogo domain={topExemplar.domain} size={14} />
                    <span className="font-display" style={{ color: 'var(--text-primary)' }}>
                      {topExemplar.domain}
                    </span>
                  </div>
                  <div
                    className="font-mono"
                    style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.6 }}
                  >
                    {topExemplar.wordCount != null && <span>{topExemplar.wordCount.toLocaleString()} words</span>}
                    {topExemplar.headerCount != null && <span> &middot; {topExemplar.headerCount} headers</span>}
                    <span> &middot; FAQ {topExemplar.hasFaq ? '\u2713' : '\u2717'}</span>
                    <span> &middot; Tables {topExemplar.hasTables ? '\u2713' : '\u2717'}</span>
                    <span> &middot; sim: {topExemplar.similarity.toFixed(3)}</span>
                  </div>
                </div>
              )}

              {/* Company content (if cited) */}
              {gap.companySignals && gap.companyUrl && (
                <div>
                  <div
                    className="font-display"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: 'var(--text-tertiary)',
                      marginBottom: 6,
                    }}
                  >
                    Your Content
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                    <BrandLogo domain={new URL(gap.companyUrl).hostname} size={14} />
                    <span
                      className="font-display"
                      style={{
                        color: 'var(--accent, #5BA4C4)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: 320,
                      }}
                    >
                      {gap.companyUrl.replace(/^https?:\/\//, '')}
                    </span>
                  </div>
                  <div
                    className="font-mono"
                    style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.6 }}
                  >
                    {gap.companySignals.wordCount != null && (
                      <span>{gap.companySignals.wordCount.toLocaleString()} words</span>
                    )}
                    {gap.companySignals.headerCount != null && (
                      <span> &middot; {gap.companySignals.headerCount} headers</span>
                    )}
                    <span> &middot; FAQ {gap.companySignals.hasFaq ? '\u2713' : '\u2717'}</span>
                    <span> &middot; Tables {gap.companySignals.hasTables ? '\u2713' : '\u2717'}</span>
                    {gap.companySimilarity != null && (
                      <>
                        <br />
                        Similarity: {gap.companySimilarity.toFixed(3)}
                      </>
                    )}
                  </div>

                  {/* Gap analysis text */}
                  {topExemplar && gap.companySignals.wordCount != null && topExemplar.wordCount != null && (
                    <div
                      className="font-display"
                      style={{
                        fontSize: 12,
                        color: 'var(--text-secondary)',
                        marginTop: 8,
                        padding: '8px 10px',
                        background: 'rgba(239,68,68,0.04)',
                        border: '1px solid rgba(239,68,68,0.12)',
                        borderRadius: 'var(--radius-sm, 4px)',
                        lineHeight: 1.5,
                      }}
                    >
                      <strong style={{ fontWeight: 600, color: 'var(--text-primary)' }}>GAP:</strong>{' '}
                      Your content is{' '}
                      {(gap.companySignals.wordCount / topExemplar.wordCount).toFixed(1)}&times; the word count
                      {gap.companySimilarity != null &&
                        topExemplar.similarity > 0 &&
                        ` but ${((1 - gap.companySimilarity / topExemplar.similarity) * 100).toFixed(0)}% lower similarity`}
                      .
                      {topExemplar.hasFaq && !gap.companySignals.hasFaq && ' The exemplar has FAQ sections you lack.'}
                      {topExemplar.hasTables && !gap.companySignals.hasTables &&
                        ' The exemplar uses tables for data presentation.'}
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Query Intelligence Section ───────────────────────────────
function QueryIntelligence({ cluster }: { cluster: ClusterProfile }) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const queries = useMemo(
    () => GAP_QUERIES.filter((g) => g.clusterId === cluster.id).sort((a, b) => b.gap - a.gap),
    [cluster.id]
  );

  const toggle = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <div>
      <SectionHeader>
        Queries &middot; {queries.length} Total
      </SectionHeader>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {queries.map((g, i) => (
          <QueryRow
            key={g.id}
            gap={g}
            expanded={expandedIds.has(g.id)}
            onToggle={() => toggle(g.id)}
            index={i}
          />
        ))}
      </div>
    </div>
  );
}

// ── Mini Embedding Scatter ───────────────────────────────────
function EmbeddingScatter({ cluster }: { cluster: ClusterProfile }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [points, setPoints] = useState<EmbeddingPoint[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch('/data/embedding-umap.json')
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        const allPts: EmbeddingPoint[] = data.points || [];
        // Filter: this cluster + all company points
        const filtered = allPts.filter(
          (p) => p.clusterId === cluster.id || p.type === 'company'
        );
        setPoints(filtered);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cluster.id]);

  useEffect(() => {
    if (!points || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = 300;
    const margin = 24;

    const xExtent = d3.extent(points, (d) => d.x) as [number, number];
    const yExtent = d3.extent(points, (d) => d.y) as [number, number];

    const xScale = d3
      .scaleLinear()
      .domain([xExtent[0] - 0.5, xExtent[1] + 0.5])
      .range([margin, width - margin]);
    const yScale = d3
      .scaleLinear()
      .domain([yExtent[0] - 0.5, yExtent[1] + 0.5])
      .range([height - margin, margin]);

    const g = svg.append('g');

    // Citations (rects)
    const citations = points.filter((p) => p.type === 'citation');
    g.selectAll('rect.citation')
      .data(citations)
      .join('rect')
      .attr('class', 'citation')
      .attr('x', (d) => xScale(d.x) - 2.5)
      .attr('y', (d) => yScale(d.y) - 2.5)
      .attr('width', 5)
      .attr('height', 5)
      .attr('fill', cluster.color)
      .attr('opacity', 0.5)
      .attr('rx', 1)
      .append('title')
      .text((d) => d.label);

    // Queries (circles)
    const queries = points.filter((p) => p.type === 'query');
    g.selectAll('circle.query')
      .data(queries)
      .join('circle')
      .attr('class', 'query')
      .attr('cx', (d) => xScale(d.x))
      .attr('cy', (d) => yScale(d.y))
      .attr('r', 4)
      .attr('fill', cluster.color)
      .attr('opacity', 0.85)
      .append('title')
      .text((d) => d.label);

    // Company points (triangles)
    const companyPts = points.filter((p) => p.type === 'company');
    const triangle = d3.symbol().type(d3.symbolTriangle).size(36);

    const companyG = g
      .selectAll('g.company')
      .data(companyPts)
      .join('g')
      .attr('class', 'company')
      .attr('transform', (d) => `translate(${xScale(d.x)},${yScale(d.y)})`);

    // Glow ring for company points overlapping this cluster
    companyG
      .filter((d) => d.clusterId === cluster.id)
      .append('circle')
      .attr('r', 10)
      .attr('fill', 'none')
      .attr('stroke', 'var(--accent, #5BA4C4)')
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.5);

    companyG
      .append('path')
      .attr('d', triangle)
      .attr('fill', 'var(--accent, #5BA4C4)')
      .attr('opacity', 0.9);

    companyG.append('title').text((d) => d.label);
  }, [points, cluster.color, cluster.id]);

  return (
    <div>
      <SectionHeader>Embedding Space</SectionHeader>
      <div
        style={{
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md, 6px)',
          overflow: 'hidden',
          height: 300,
          position: 'relative',
          background: 'var(--surface)',
        }}
      >
        {loading ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-tertiary)',
              fontSize: 12,
            }}
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
              style={{
                width: 20,
                height: 20,
                border: '2px solid var(--border)',
                borderTopColor: cluster.color,
                borderRadius: '50%',
              }}
            />
          </div>
        ) : (
          <svg ref={svgRef} width="100%" height={300} />
        )}
      </div>

      {/* Legend */}
      <div
        style={{
          display: 'flex',
          gap: 16,
          marginTop: 8,
          fontSize: 10,
          color: 'var(--text-tertiary)',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: cluster.color,
              display: 'inline-block',
            }}
          />
          Query
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span
            style={{
              width: 7,
              height: 7,
              background: cluster.color,
              opacity: 0.6,
              display: 'inline-block',
              borderRadius: 1,
            }}
          />
          Citation
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span
            style={{
              width: 0,
              height: 0,
              borderLeft: '4px solid transparent',
              borderRight: '4px solid transparent',
              borderBottom: '7px solid var(--accent, #5BA4C4)',
              display: 'inline-block',
            }}
          />
          Company
        </span>
      </div>
    </div>
  );
}

// ── Drawer Tab type ──────────────────────────────────────────
type DrawerTab = 'overview' | 'domains' | 'queries' | 'structure' | 'embedding';

const DRAWER_TABS: { id: DrawerTab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'domains', label: 'Domains' },
  { id: 'queries', label: 'Queries' },
  { id: 'structure', label: 'Structure' },
  { id: 'embedding', label: 'Embedding' },
];

// ── Main Drawer ──────────────────────────────────────────────
export function ClusterDrawer({ cluster, onClose }: ClusterDrawerProps) {
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('overview');
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);

  // Reset tab when cluster changes
  useEffect(() => {
    setDrawerTab('overview');
    setSelectedDomain(null);
  }, [cluster?.id]);

  // Escape key
  useEffect(() => {
    if (!cluster) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [cluster, onClose]);

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (!cluster) return;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, [cluster]);

  const presenceLabel = useMemo(() => {
    if (!cluster) return null;
    if (cluster.companyShare > 0) {
      return {
        text: `${formatPct(cluster.companyShare)} share${cluster.companyRank ? ` (#${cluster.companyRank})` : ''}`,
        color: '#10B981',
      };
    }
    return { text: 'No presence', color: '#EF4444' };
  }, [cluster]);

  const handleDomainClick = useCallback((domain: string) => {
    setSelectedDomain(domain);
    // Domain drawer will be wired in a later task
    console.log('[ClusterDrawer] domain clicked:', domain);
  }, []);

  return (
    <AnimatePresence>
      {cluster && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(0,0,0,0.15)' }}
            onClick={onClose}
          />

          {/* Drawer panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="fixed top-0 right-0 z-50 flex flex-col"
            style={{
              width: '55vw',
              minWidth: 540,
              maxWidth: 800,
              height: '100vh',
              background: 'var(--surface)',
              borderLeft: '1px solid var(--border)',
              boxShadow: 'var(--shadow-float)',
            }}
          >
            {/* ── Header (sticky) ── */}
            <div
              style={{
                position: 'sticky',
                top: 0,
                zIndex: 10,
                background: 'var(--surface)',
              }}
            >
              <div style={{ padding: 16, paddingBottom: 12 }}>
                {/* Close button */}
                <button
                  onClick={onClose}
                  className="cursor-pointer"
                  style={{
                    position: 'absolute',
                    top: 12,
                    right: 12,
                    width: 30,
                    height: 30,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: 'none',
                    background: 'transparent',
                    borderRadius: 'var(--radius-sm, 4px)',
                    color: 'var(--text-tertiary)',
                    transition: 'color 0.12s, background 0.12s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = 'var(--text-primary)';
                    e.currentTarget.style.background = 'var(--surface-raised, var(--surface))';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = 'var(--text-tertiary)';
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <X size={14} strokeWidth={1.5} />
                </button>

                {/* Cluster name with dot */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingRight: 40 }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: cluster.color,
                      flexShrink: 0,
                    }}
                  />
                  <span className="font-display" style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {cluster.name}
                  </span>
                </div>

                {/* Stats line */}
                <div
                  className="font-display"
                  style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, marginLeft: 16 }}
                >
                  {cluster.totalCitations} citations &middot; {cluster.uniqueDomains} unique domains &middot;{' '}
                  {cluster.queryCount} queries
                </div>

                {/* Presence line */}
                {presenceLabel && (
                  <div
                    className="font-display"
                    style={{ fontSize: 12, marginTop: 2, marginLeft: 16 }}
                  >
                    <span style={{ color: 'var(--text-tertiary)' }}>Your presence: </span>
                    <span style={{ color: presenceLabel.color, fontWeight: 500 }}>
                      {presenceLabel.text}
                    </span>
                  </div>
                )}
              </div>

              {/* ── Tab bar ── */}
              <div
                className="flex items-center gap-0 border-b border-border"
                style={{ paddingLeft: 16, paddingRight: 16 }}
              >
                {DRAWER_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setDrawerTab(tab.id)}
                    className="cursor-pointer font-display"
                    style={{
                      padding: '0 12px',
                      height: 32,
                      fontSize: 12,
                      fontWeight: 500,
                      marginBottom: -1,
                      color: drawerTab === tab.id ? 'var(--accent, #5BA4C4)' : 'var(--text-secondary)',
                      background: 'transparent',
                      borderTop: 'none',
                      borderLeft: 'none',
                      borderRight: 'none',
                      borderBottomWidth: 2,
                      borderBottomStyle: 'solid',
                      borderBottomColor: drawerTab === tab.id ? 'var(--accent, #5BA4C4)' : 'transparent',
                      transition: 'color 0.12s, border-color 0.12s',
                    }}
                    onMouseEnter={(e) => {
                      if (drawerTab !== tab.id) e.currentTarget.style.color = 'var(--text-primary)';
                    }}
                    onMouseLeave={(e) => {
                      if (drawerTab !== tab.id) e.currentTarget.style.color = 'var(--text-secondary)';
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* ── Scrollable content (per tab) ── */}
            <div className="flex-1 overflow-y-auto" style={{ padding: 16 }}>
              {drawerTab === 'overview' && <OverviewSection cluster={cluster} />}
              {drawerTab === 'domains' && (
                <CompetitorTable cluster={cluster} onDomainClick={handleDomainClick} />
              )}
              {drawerTab === 'queries' && <QueryIntelligence cluster={cluster} />}
              {drawerTab === 'structure' && <StructuralAnalysis cluster={cluster} />}
              {drawerTab === 'embedding' && <EmbeddingScatter cluster={cluster} />}

              {/* Bottom spacing */}
              <div style={{ height: 24 }} />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
