// ──────────────────────────────────────────────────────────────
// Embedding Lab — Types, Constants, and Helpers
// Data is loaded via useEmbeddingLabData() hook and provided
// through EmbeddingLabContext. Components consume via
// useEmbeddingLabContext().
// ──────────────────────────────────────────────────────────────

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
  opportunityScore?: number;
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
  gapScore?: number;
  domain?: string;
  engine?: string;
  authorityType?: string;
  wordCount?: number;
  headers?: number;
  hasFaq?: boolean;
}

// ── Engine aggregate data ──────────────────────────────────
export interface EngineData {
  key: EngineKey;
  label: string;
  domain: string;
  totalCitations: number;
  color: string;
  topDomain?: string;
  uniqueCitations?: number;
  preferredTraits?: string[];
}

// ── Divergence data ────────────────────────────────────────
export interface DivergenceRow {
  query: string;
  clusterId: string;
  engines: Partial<Record<EngineKey, string>>;
  agreement: number;
}

// ── ClusterData (used by intelligence-panel) ───────────────
export interface ClusterData {
  id: string;
  name: string;
  color: string;
  citations: number;
  domains: number;
  yourCitations: number;
  yourShare: number;
  yourRank: number;
  presence: ClusterProfile['presence'];
  competitors: DomainEntry[];
  engineBreakdown: Record<EngineKey, number>;
  queriesTotal: number;
}

// ── Helper: filter cluster data for a specific engine ──────
export function getClusterDataForEngine(
  clusters: ClusterProfile[],
  engineKey: EngineKey | 'all',
): ClusterProfile[] {
  if (engineKey === 'all') return clusters;

  return clusters.map(cluster => ({
    ...cluster,
    totalCitations: cluster.engineBreakdown[engineKey] || 0,
  }));
}
