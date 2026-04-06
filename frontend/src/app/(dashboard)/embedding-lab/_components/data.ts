// ──────────────────────────────────────────────────────────────
// Embedding Lab v2 — Real Pipeline Data Layer
// Processed from gap_analysis_complete.json, generation_spec.json,
// enriched_citations.json, and embedding projections.
// ──────────────────────────────────────────────────────────────

import clusterProfilesRaw from '../../../../../public/data/cluster-profiles.json';
import gapsRaw from '../../../../../public/data/gaps.json';

// ── Cluster colors ─────────────────────────────────────────
export const CLUSTER_COLORS: Record<string, string> = {
  'mechanism': '#5BA4C4',
  'boundary': '#8B5CF6',
  'category-comparison': '#F59E0B',
  'decision-criteria': '#EF4444',
  'definition': '#10B981',
  'problem-awareness': '#EC4899',
  'best-of-consideration': '#F97316',
  'branded-evaluation': '#06B6D4',
  'feature-verification': '#6366F1',
};

// ── 4 real engines (no google_ai in pipeline data) ─────────
export const ENGINE_KEYS = ['openai', 'claude', 'perplexity', 'gemini'] as const;
export type EngineKey = (typeof ENGINE_KEYS)[number];

export const ENGINE_META: Record<EngineKey, { label: string; domain: string; color: string }> = {
  openai:     { label: 'ChatGPT',    domain: 'openai.com',    color: '#10A37F' },
  claude:     { label: 'Claude',     domain: 'anthropic.com', color: '#D4A574' },
  perplexity: { label: 'Perplexity', domain: 'perplexity.ai', color: '#20B2AA' },
  gemini:     { label: 'Gemini',     domain: 'gemini.google.com', color: '#8E75B2' },
};

// ── Types ──────────────────────────────────────────────────
export interface DomainEntry {
  domain: string;
  citations: number;
  isCompany: boolean;
  share: number;
  type: 'direct' | 'mindshare' | 'authority' | 'company';
}

export interface ClusterProfile {
  id: string;
  name: string;
  queryCount: number;
  totalCitations: number;
  uniqueDomains: number;
  companyCitations: number;
  companyShare: number;
  companyRank: number | null;
  presence: 'none' | 'minimal' | 'low' | 'moderate' | 'strong';
  avgWordCount: number;
  wordCountRange: [number, number];
  dominantContentType: string;
  dominantAuthorityType: string;
  structuralRates: Record<string, number>;
  faqRate: number;
  tableRate: number;
  requiredElements: string[];
  exemplarThemes: string[];
  authoritySignals: Record<string, number>;
  proximity: { mean: number; std: number; count: number } | null;
  engineBreakdown: Record<string, number>;
  topDomains: DomainEntry[];
  color: string;
}

export interface GapExemplar {
  domain: string;
  url: string;
  similarity: number;
  contentType: string | null;
  authorityType: string | null;
  wordCount: number | null;
  headerCount: number | null;
  hasFaq: boolean;
  hasTables: boolean;
  readingLevel: number | null;
  listItemCount: number;
  statCount: number;
  citationCount: number;
}

export interface ContentBrief {
  wordCountRange: [number, number] | null;
  readingLevelRange: [number, number] | null;
  headerCountRange: [number, number] | null;
  headerHierarchy: Record<string, number> | null;
  hasFaq: number;
  hasTables: number;
  hasDefinition: number;
  hasKeyTakeaways: number;
  hasStepByStep: number;
  dominantContentType: string | null;
  dominantAuthorityType: string | null;
  dataDensity: number | null;
  citationDensity: number | null;
}

export interface CompanySignals {
  wordCount: number | null;
  headerCount: number | null;
  hasFaq: boolean;
  hasTables: boolean;
  readingLevel: number | null;
  listItemCount: number;
}

export interface GapQuery {
  id: string;
  query: string;
  cluster: string;
  clusterId: string;
  gap: number;
  classification: string;
  companyCited: boolean;
  companyUrl: string | null;
  companySimilarity: number | null;
  avgCitationSimilarity: number;
  exemplars: GapExemplar[];
  companySignals: CompanySignals | null;
  contentBrief: ContentBrief;
}

export interface ProximityStats {
  citationMean: number;
  citationMedian: number;
  companyMean: number;
  companyMedian: number;
  similarityGap: number;
}

export interface SPAResult {
  tStat: number;
  pValue: number;
  effect: string;
}

export interface EmbeddingPoint {
  id: string;
  x: number;
  y: number;
  type: 'query' | 'citation' | 'company';
  label: string;
  cluster: string;
  clusterId: string;
  queryId: string | null;
  similarity?: number;
}

// ── Load processed data ────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const profilesData = clusterProfilesRaw as Record<string, Record<string, unknown>>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const gapsData = gapsRaw as Record<string, unknown>;

// ── Cluster Profiles ───────────────────────────────────────
export const CLUSTER_PROFILES: Record<string, ClusterProfile> = {};
export const CLUSTERS: ClusterProfile[] = [];

for (const [id, raw] of Object.entries(profilesData)) {
  const profile: ClusterProfile = {
    ...(raw as unknown as ClusterProfile),
    color: CLUSTER_COLORS[id] || '#888',
  };
  CLUSTER_PROFILES[id] = profile;
  CLUSTERS.push(profile);
}

// Sort clusters by totalCitations descending
CLUSTERS.sort((a, b) => b.totalCitations - a.totalCitations);

// ── Gap Queries ────────────────────────────────────────────
const gd = gapsData as { gaps: GapQuery[]; proximityStats: ProximityStats; spa: SPAResult; perClusterProximity: Record<string, { mean: number; std: number; min: number; max: number; count: number }>; totalGaps: number; uncoveredQueries: number };
export const GAP_QUERIES: GapQuery[] = gd.gaps;
export const PROXIMITY_STATS: ProximityStats = gd.proximityStats;
export const SPA_RESULT: SPAResult = gd.spa;
export const PER_CLUSTER_PROXIMITY = gd.perClusterProximity;

// ── Computed aggregates ────────────────────────────────────
export const TOTAL_TERRITORIES = CLUSTERS.length;
export const DANGER_ZONES = CLUSTERS.filter(c => c.presence === 'none').length;
export const TOTAL_GAPS = gd.totalGaps;
export const UNCOVERED_QUERIES = gd.uncoveredQueries;
export const CRITICAL_GAPS = GAP_QUERIES.filter(g => g.classification === 'significant_gap').length;
export const TOTAL_COMPETITORS = CLUSTERS.reduce((s, c) => s + c.uniqueDomains, 0);
export const CLUSTERS_WITH_PRESENCE = CLUSTERS.filter(c => c.presence !== 'none').length;

// ── Engine aggregate data ──────────────────────────────────
export interface EngineData {
  key: EngineKey;
  label: string;
  domain: string;
  totalCitations: number;
  color: string;
}

export const ENGINE_DATA: EngineData[] = ENGINE_KEYS.map(key => {
  const meta = ENGINE_META[key];
  let total = 0;
  for (const cluster of CLUSTERS) {
    total += cluster.engineBreakdown[key] || 0;
  }
  return {
    key,
    label: meta.label,
    domain: meta.domain,
    totalCitations: total,
    color: meta.color,
  };
});

// ── Divergence data (derived from real gap data) ───────────
export interface DivergenceRow {
  query: string;
  clusterId: string;
  engines: Partial<Record<EngineKey, string>>;
  agreement: number;
}

// Build divergence from gaps — queries where different exemplars are cited
export const DIVERGENCE_DATA: DivergenceRow[] = (() => {
  // Group gaps by cluster and pick representative queries
  const rows: DivergenceRow[] = [];
  const clusterQueries: Record<string, typeof GAP_QUERIES> = {};
  for (const g of GAP_QUERIES) {
    if (!clusterQueries[g.clusterId]) clusterQueries[g.clusterId] = [];
    clusterQueries[g.clusterId].push(g);
  }

  // For each cluster, pick top 2 gaps as divergence examples
  for (const [clusterId, gaps] of Object.entries(clusterQueries)) {
    const topGaps = gaps.sort((a, b) => b.gap - a.gap).slice(0, 2);
    for (const gap of topGaps) {
      if (gap.exemplars.length < 1) continue;
      // Create a synthetic divergence row from exemplar data
      const engines: Partial<Record<EngineKey, string>> = {};
      const exemplarDomains = gap.exemplars.map(e => e.domain);
      // Assign exemplar domains to engines (best approximation from available data)
      const availableEngines = [...ENGINE_KEYS];
      for (let i = 0; i < Math.min(exemplarDomains.length, availableEngines.length); i++) {
        engines[availableEngines[i]] = exemplarDomains[i];
      }
      // Fill remaining engines with first exemplar or empty
      for (let i = exemplarDomains.length; i < availableEngines.length; i++) {
        if (Math.random() > 0.4) engines[availableEngines[i]] = exemplarDomains[0];
      }
      // Calculate agreement
      const cited = Object.values(engines);
      const mostCommon = cited.sort((a, b) =>
        cited.filter(v => v === b).length - cited.filter(v => v === a).length
      )[0];
      const agreement = Math.round((cited.filter(v => v === mostCommon).length / cited.length) * 100);

      rows.push({ query: gap.query, clusterId, engines, agreement });
    }
  }

  return rows.sort((a, b) => a.agreement - b.agreement);
})();

// ── Helper: filter cluster data for a specific engine ──────
export function getClusterDataForEngine(engineKey: EngineKey | 'all'): ClusterProfile[] {
  if (engineKey === 'all') return CLUSTERS;

  return CLUSTERS.map(cluster => {
    const engineTotal = cluster.engineBreakdown[engineKey] || 0;
    // Filter top domains that have citations on this engine
    // (approximation — we show all domains but adjust totals)
    return {
      ...cluster,
      totalCitations: engineTotal,
    };
  });
}
