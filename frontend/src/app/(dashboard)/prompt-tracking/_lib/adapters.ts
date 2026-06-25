/**
 * Adapters: API response types → frontend display types.
 * Pure functions — no side effects, no fetching.
 */

import type { Platform } from '@/types';
import type {
  EnrichedPromptAPI,
  CompetitorMetricsAPI,
  PerPromptPlatformMetricsAPI,
  FanoutQueryResponseAPI,
  AnswerRecordAPI,
  PromptRow,
  CompetitorMention,
  PlatformMentionRate,
  QueryFanout,
  AnswerHistoryRow,
  Topic,
} from './types';

// ── Constants ───────────────────────────────────────────────────

/** Backend engine string → frontend Platform type. */
export const ENGINE_TO_PLATFORM: Record<string, Platform> = {
  openai: 'chatgpt',
  claude: 'claude',
  gemini: 'gemini',
  perplexity: 'perplexity',
};

/** Platform display metadata (label + domain for favicons). */
export const PLATFORM_MAP: Record<Platform, { label: string; domain: string }> = {
  chatgpt: { label: 'ChatGPT', domain: 'openai.com' },
  claude: { label: 'Claude', domain: 'anthropic.com' },
  perplexity: { label: 'Perplexity', domain: 'perplexity.ai' },
  google_ai_overview: { label: 'Google AI Mode', domain: 'google.com' },
  gemini: { label: 'Gemini', domain: 'gemini.google.com' },
};

/** Backend category enum → display name + color. */
export const CATEGORY_DISPLAY_MAP: Record<string, { name: string; color: string }> = {
  brand_awareness: { name: 'Brand Awareness', color: '#5BA4C4' },
  product_comparison: { name: 'Product Comparison', color: '#34B27B' },
  feature_query: { name: 'Feature Evaluation', color: '#DC7B18' },
  industry_knowledge: { name: 'Industry Knowledge', color: '#8B7EC8' },
  competitor_analysis: { name: 'Competitive Analysis', color: '#E5484D' },
  use_case: { name: 'Use Case', color: '#EC4899' },
  general: { name: 'General', color: '#6B7280' },
};

/** Known competitor brand → domain mapping for favicons. */
const KNOWN_BRAND_DOMAINS: Record<string, string> = {
  'Bolt.new': 'bolt.new',
  'Cursor': 'cursor.com',
  'Replit': 'replit.com',
  'V0.dev': 'v0.dev',
  'Copilot': 'github.com',
  'ChatGPT': 'openai.com',
  'Claude': 'anthropic.com',
  'Gemini': 'gemini.google.com',
  'Perplexity': 'perplexity.ai',
};

/** Deterministic color palette for unknown categories. */
const FALLBACK_COLORS = [
  '#5BA4C4', '#34B27B', '#DC7B18', '#8B7EC8', '#E5484D',
  '#EC4899', '#6B7280', '#F59E0B', '#10B981', '#3B82F6',
];

// ── Helpers ─────────────────────────────────────────────────────

/** Simple hash to pick a deterministic color for unknown categories. */
function hashColor(s: string): string {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash + s.charCodeAt(i)) | 0;
  }
  return FALLBACK_COLORS[Math.abs(hash) % FALLBACK_COLORS.length];
}

/** Convert snake_case to Title Case display name. */
function humanize(s: string | null | undefined): string {
  if (!s) return 'Uncategorized';
  return s
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

/** Guess domain from brand name — fallback when not in KNOWN_BRAND_DOMAINS. */
function guessDomain(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9.]/g, '') + '.com';
}

/** Extract hostname from a URL, falling back to the raw string. */
function extractDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

/** Format ISO datetime to readable string: "Mar 26, 2026 · 2:30 PM". */
function formatDateTime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const datePart = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const timePart = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  return `${datePart} · ${timePart}`;
}

// ── Adapter Functions ───────────────────────────────────────────

export function toPromptRow(enriched: EnrichedPromptAPI): PromptRow {
  const cat = enriched.category ?? '';
  const display = CATEGORY_DISPLAY_MAP[cat];
  return {
    id: enriched.id,
    text: enriched.text,
    topic: display?.name ?? humanize(cat),
    topicColor: display?.color ?? hashColor(cat),
    tags: enriched.tags,
    queryFanouts: enriched.fanout_count,
    mentionRate: enriched.mention_rate,
    mentionDelta: enriched.mention_delta,
    citationRate: enriched.citation_rate,
    citationDelta: enriched.citation_delta,
    volume: enriched.daily_volume,
  };
}

export function toCompetitorMention(
  comp: CompetitorMetricsAPI,
  brandName: string,
  brandDomain: string,
): CompetitorMention {
  const isYou = comp.name.toLowerCase() === brandName.toLowerCase();
  return {
    rank: comp.rank,
    brand: comp.name,
    domain: isYou ? brandDomain : (KNOWN_BRAND_DOMAINS[comp.name] ?? guessDomain(comp.name)),
    mentions: comp.mention_count,
    mentionRate: comp.mention_rate,
    mentionDelta: comp.mention_delta,
    isYou,
  };
}

export function toPlatformMentionRate(plat: PerPromptPlatformMetricsAPI): PlatformMentionRate {
  const platform = ENGINE_TO_PLATFORM[plat.engine] ?? (plat.engine as Platform);
  const info = PLATFORM_MAP[platform] ?? { label: plat.engine, domain: '' };
  return {
    platform,
    label: info.label,
    domain: info.domain,
    mentionRate: plat.mention_rate,
  };
}

export function toQueryFanout(fanout: FanoutQueryResponseAPI): QueryFanout {
  return {
    query: fanout.query_text,
    observations: fanout.observation_count,
  };
}

export function toAnswerHistoryRow(
  record: AnswerRecordAPI,
  brandName: string,
  brandDomain: string,
): AnswerHistoryRow {
  const platform = ENGINE_TO_PLATFORM[record.engine] ?? (record.engine as Platform);
  const info = PLATFORM_MAP[platform] ?? { label: record.engine, domain: '' };
  const hasText = record.response_text !== '';

  // Build mentionedBrands array
  const mentionedBrands: { domain: string; name: string; checked: boolean }[] = [];
  if (record.brand_mentioned) {
    mentionedBrands.push({ domain: brandDomain, name: brandName, checked: true });
  }
  for (const compName of Object.keys(record.competitor_mentions)) {
    if (record.competitor_mentions[compName] > 0) {
      mentionedBrands.push({
        domain: KNOWN_BRAND_DOMAINS[compName] ?? guessDomain(compName),
        name: compName,
        checked: false,
      });
    }
  }

  return {
    id: record.id,
    date: formatDateTime(record.created_at),
    persona: record.persona || 'Default',
    platform,
    platformLabel: info.label,
    platformDomain: info.domain,
    answerPreview: hasText
      ? record.response_text.slice(0, 80) + (record.response_text.length > 80 ? '...' : '')
      : 'Response text no longer available',
    cited: record.citations.length > 0,
    mentioned: record.brand_mentioned,
    competitorDomains: Object.keys(record.competitor_mentions)
      .filter((n) => record.competitor_mentions[n] > 0)
      .map((n) => KNOWN_BRAND_DOMAINS[n] ?? guessDomain(n)),
    fullAnswer: hasText ? record.response_text : null,
    citations: record.citations.map(extractDomain),
    mentionedBrands,
  };
}

/** Derive topics from a list of PromptRows (same as the old TOPICS computation). */
export function deriveTopics(prompts: PromptRow[]): Topic[] {
  const map = new Map<string, { color: string; rows: PromptRow[] }>();
  for (const p of prompts) {
    const entry = map.get(p.topic);
    if (entry) {
      entry.rows.push(p);
    } else {
      map.set(p.topic, { color: p.topicColor, rows: [p] });
    }
  }
  return Array.from(map.entries()).map(([name, { color, rows }]) => ({
    name,
    color,
    count: rows.length,
    avgMentionRate: rows.reduce((s, r) => s + r.mentionRate, 0) / rows.length,
    avgCitationRate: rows.reduce((s, r) => s + r.citationRate, 0) / rows.length,
  }));
}
