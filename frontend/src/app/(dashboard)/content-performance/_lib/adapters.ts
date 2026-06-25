/**
 * Adapters: convert snake_case backend API types → camelCase frontend display types.
 */

import type {
  ContentPerformanceRowAPI,
  VelocityInsightAPI,
  DailyTrafficPoint,
  SourceBreakdownItem,
  AIPlatformBreakdownItem,
  CitationTimelinePoint,
  ContentDetailAPI,
} from './types';
import type {
  ContentPiece,
  VelocityDatum,
  LifecycleStage,
  VelocityTrend,
  PlatformDetail,
  TrafficSource,
} from '../_components/data';
import { PLATFORM_LIST } from '../_components/data';

// ── Validation helpers ────────────────────────────────

const VALID_VELOCITY_TRENDS = new Set<VelocityTrend>(['up', 'down', 'flat']);
const VALID_LIFECYCLES = new Set<LifecycleStage>([
  'growing', 'peaking', 'stable', 'declining', 'stale',
]);

function asVelocityTrend(v: string): VelocityTrend {
  return VALID_VELOCITY_TRENDS.has(v as VelocityTrend)
    ? (v as VelocityTrend)
    : 'flat';
}

function asLifecycleStage(v: string): LifecycleStage {
  return VALID_LIFECYCLES.has(v as LifecycleStage)
    ? (v as LifecycleStage)
    : 'stable';
}

// ── Table row adapter ─────────────────────────────────

export function toContentPiece(row: ContentPerformanceRowAPI): ContentPiece {
  return {
    id: row.inventory_id,
    title: row.title,
    url: row.url,
    traffic: row.traffic,
    aiReferrals: row.ai_referrals,
    velocity: row.velocity,
    velocityTrend: asVelocityTrend(row.velocity_trend),
    freshnessDays: row.freshness_days,
    lifecycle: asLifecycleStage(row.lifecycle),
    publishedAt: row.published_at ?? '',
    structuralScore: row.structural_score,
    // GAP fields — partially wired (citations, platforms, queriesCovered from API)
    cluster: '',
    clusterColor: '#687076',
    citations: row.citations ?? 0,
    cps: 0,
    platforms: {
      chatgpt: row.platforms?.chatgpt ?? false,
      claude: row.platforms?.claude ?? false,
      perplexity: row.platforms?.perplexity ?? false,
      google_ai: row.platforms?.google_ai ?? false,
      gemini: row.platforms?.gemini ?? false,
    },
    cannibalization: 0,
    queriesCovered: row.queries_covered ?? 0,
    exemplarSimilarity: 0,
    briefCompliance: 0,
  };
}

// ── Velocity insight adapter ──────────────────────────

export function toVelocityDatum(insight: VelocityInsightAPI): VelocityDatum {
  return {
    title: insight.title,
    velocity: insight.velocity,
    lifecycle: asLifecycleStage(insight.lifecycle),
    cluster: '',
  };
}

// ── Drawer: daily traffic timeline ────────────────────

function formatShortDate(isoDate: string): string {
  const d = new Date(isoDate);
  if (isNaN(d.getTime())) return isoDate;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function toDrawerTrafficTimeline(
  dailyTraffic: DailyTrafficPoint[],
): { date: string; pageviews: number }[] {
  return dailyTraffic.map((pt) => ({
    date: formatShortDate(pt.date),
    pageviews: pt.pageviews,
  }));
}

// ── Drawer: traffic sources ───────────────────────────

function capitalizeChannel(channel: string): string {
  if (channel === 'ai_referral') return 'AI Referral';
  return channel
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function toDrawerTrafficSources(
  sourceBreakdown: SourceBreakdownItem[],
): TrafficSource[] {
  return sourceBreakdown.map((item) => ({
    source: capitalizeChannel(item.channel),
    sessions: item.sessions,
    pct: Math.round(item.percentage),
  }));
}

// ── Drawer: AI platform breakdown ─────────────────────

/** Map backend platform identifiers to PLATFORM_LIST entries. */
const PLATFORM_ALIAS: Record<string, string> = {
  openai: 'chatgpt',
  anthropic: 'claude',
  perplexity: 'perplexity',
  google: 'google_ai',
  gemini: 'gemini',
};

export function toDrawerPlatformCoverage(
  platforms: ContentDetailAPI['platforms'],
  aiBreakdown: AIPlatformBreakdownItem[],
): PlatformDetail[] {
  const sessionsByKey = new Map<string, number>();
  for (const item of aiBreakdown) {
    const key =
      PLATFORM_ALIAS[item.platform.toLowerCase()] ?? item.platform.toLowerCase();
    sessionsByKey.set(key, (sessionsByKey.get(key) ?? 0) + item.sessions);
  }

  return PLATFORM_LIST.map((p) => {
    const aiSessions = sessionsByKey.get(p.key) ?? 0;
    return {
      platform: p.name,
      domain: p.domain,
      citationPresent: platforms?.[p.key] ?? false,
      aiSessions,
    };
  });
}

// ── Drawer: citation timeline ────────────────────────

export function toDrawerCitationTimeline(
  timeline: CitationTimelinePoint[],
): { date: string; citations: number }[] {
  return timeline.map((pt) => ({
    date: formatShortDate(pt.date),
    citations: pt.cited,
  }));
}
