// ──────────────────────────────────────────────────────────────
// Embedding Lab v2 — Comprehensive Mock Data
// ──────────────────────────────────────────────────────────────

// ── Cluster colors (muted, brand-safe) ─────────────────────
export const CLUSTER_COLORS: Record<string, string> = {
  cl1: '#5BA4C4', // Mechanism — teal
  cl2: '#8B5CF6', // Boundary — purple
  cl3: '#F59E0B', // Category Comparison — amber
  cl4: '#EF4444', // Decision Criteria — red
  cl5: '#10B981', // Definition — green
  cl6: '#EC4899', // Problem/Awareness — pink
  cl7: '#F97316', // Best-of/Consideration — orange
  cl8: '#06B6D4', // Branded Evaluation — cyan
  cl9: '#6366F1', // Feature Verification — indigo
};

export const ENGINE_KEYS = ['chatgpt', 'claude', 'perplexity', 'google_ai', 'gemini'] as const;
export type EngineKey = (typeof ENGINE_KEYS)[number];

export const ENGINE_META: Record<EngineKey, { label: string; domain: string; color: string }> = {
  chatgpt:    { label: 'ChatGPT',    domain: 'openai.com',      color: '#10A37F' },
  claude:     { label: 'Claude',     domain: 'anthropic.com',   color: '#D4A574' },
  perplexity: { label: 'Perplexity', domain: 'perplexity.ai',   color: '#20B2AA' },
  google_ai:  { label: 'Google AI',  domain: 'google.com',      color: '#4285F4' },
  gemini:     { label: 'Gemini',     domain: 'gemini.google.com', color: '#8E75B2' },
};

// ── Types ──────────────────────────────────────────────────
export interface Competitor {
  domain: string;
  citations: number;
  share: number;
  type: 'direct' | 'mindshare' | 'authority';
  engines: Partial<Record<EngineKey, number>>;
}

export interface ClusterData {
  id: string;
  name: string;
  citations: number;
  share: number;
  domains: number;
  presence: 'none' | 'minimal' | 'low' | 'moderate' | 'strong';
  yourShare: number;
  yourRank: number | null;
  yourCitations: number;
  color: string;
  competitors: Competitor[];
  engineBreakdown: Record<EngineKey, number>;
  queriesTotal: number;
  queriesCovered: number;
}

export interface GapQuery {
  id: string;
  query: string;
  cluster: string;
  clusterId: string;
  gap: number;
  classification: 'significant_gap' | 'gap_to_close' | 'roughly_equal' | 'company_wins';
  yourContent: { url: string } | null;
  topCited: { domain: string; url: string };
  engines: Record<EngineKey, boolean>;
  opportunityScore: number;
  topCitedSignals?: ContentSignals;
  yourSignals?: ContentSignals;
}

export interface ContentSignals {
  wordCount: number;
  headers: number;
  hasFaq: boolean;
  hasTables: boolean;
  lists: number;
  externalCitations: number;
  readingLevel: number;
  hasSchema: boolean;
}

export interface EngineData {
  key: EngineKey;
  label: string;
  domain: string;
  totalCitations: number;
  uniqueCitations: number;
  topDomain: string;
  preferredTraits: string[];
  avgWordCount: number;
}

export interface EmbeddingPoint {
  id: string;
  x: number;
  y: number;
  tsne_x: number;
  tsne_y: number;
  type: 'query' | 'citation' | 'company';
  label: string;
  cluster: string;
  clusterId: string;
  similarity?: number;
  gapScore?: number;
  domain?: string;
  engine?: EngineKey;
  authorityType?: 'commercial' | 'government' | 'educational' | 'organization' | 'news';
  wordCount?: number;
  headers?: number;
  hasFaq?: boolean;
}

// ── Seeded random number generator ─────────────────────────
function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// ── Clusters ───────────────────────────────────────────────
export const CLUSTERS: ClusterData[] = [
  {
    id: 'cl1', name: 'Mechanism', citations: 173, share: 11.6, domains: 103,
    presence: 'moderate', yourShare: 1.6, yourRank: 1, yourCitations: 3, color: CLUSTER_COLORS.cl1,
    queriesTotal: 16, queriesCovered: 12,
    engineBreakdown: { chatgpt: 38, claude: 42, perplexity: 35, google_ai: 28, gemini: 30 },
    competitors: [
      { domain: 'nature.com', citations: 12, share: 6.9, type: 'authority', engines: { chatgpt: 4, claude: 3, perplexity: 3, gemini: 2 } },
      { domain: 'healthcatalyst.com', citations: 9, share: 5.2, type: 'direct', engines: { chatgpt: 3, claude: 2, perplexity: 2, google_ai: 2 } },
      { domain: 'arxiv.org', citations: 8, share: 4.6, type: 'authority', engines: { chatgpt: 2, claude: 3, perplexity: 2, gemini: 1 } },
      { domain: 'pubmed.ncbi.nlm.nih.gov', citations: 7, share: 4.0, type: 'authority', engines: { claude: 3, perplexity: 2, google_ai: 2 } },
      { domain: 'accountablehq.com', citations: 6, share: 3.5, type: 'direct', engines: { chatgpt: 2, claude: 2, perplexity: 2 } },
      { domain: 'sciencedirect.com', citations: 5, share: 2.9, type: 'authority', engines: { chatgpt: 2, perplexity: 1, gemini: 2 } },
      { domain: 'insighthealth.ai', citations: 3, share: 1.6, type: 'direct', engines: { chatgpt: 1, claude: 1, perplexity: 1 } },
      { domain: 'bmj.com', citations: 3, share: 1.7, type: 'authority', engines: { claude: 1, google_ai: 1, gemini: 1 } },
    ],
  },
  {
    id: 'cl2', name: 'Boundary', citations: 184, share: 1.6, domains: 103,
    presence: 'moderate', yourShare: 1.6, yourRank: 1, yourCitations: 3, color: CLUSTER_COLORS.cl2,
    queriesTotal: 16, queriesCovered: 8,
    engineBreakdown: { chatgpt: 42, claude: 38, perplexity: 40, google_ai: 32, gemini: 32 },
    competitors: [
      { domain: 'www.hhs.gov', citations: 14, share: 7.6, type: 'authority', engines: { chatgpt: 4, claude: 4, perplexity: 3, google_ai: 3 } },
      { domain: 'www.healthit.gov', citations: 10, share: 5.4, type: 'authority', engines: { chatgpt: 3, claude: 3, google_ai: 2, gemini: 2 } },
      { domain: 'hipaajournal.com', citations: 8, share: 4.3, type: 'mindshare', engines: { chatgpt: 3, perplexity: 3, gemini: 2 } },
      { domain: 'compliancy-group.com', citations: 6, share: 3.3, type: 'mindshare', engines: { chatgpt: 2, claude: 2, perplexity: 2 } },
      { domain: 'insighthealth.ai', citations: 3, share: 1.6, type: 'direct', engines: { chatgpt: 1, claude: 1, perplexity: 1 } },
      { domain: 'nist.gov', citations: 5, share: 2.7, type: 'authority', engines: { claude: 2, google_ai: 2, gemini: 1 } },
      { domain: 'epic.com', citations: 4, share: 2.2, type: 'direct', engines: { chatgpt: 2, google_ai: 1, gemini: 1 } },
      { domain: 'ama-assn.org', citations: 3, share: 1.6, type: 'authority', engines: { perplexity: 1, google_ai: 1, gemini: 1 } },
    ],
  },
  {
    id: 'cl3', name: 'Category Comparison', citations: 156, share: 5.0, domains: 89,
    presence: 'low', yourShare: 0.8, yourRank: 4, yourCitations: 1, color: CLUSTER_COLORS.cl3,
    queriesTotal: 14, queriesCovered: 6,
    engineBreakdown: { chatgpt: 35, claude: 30, perplexity: 32, google_ai: 28, gemini: 31 },
    competitors: [
      { domain: 'g2.com', citations: 15, share: 9.6, type: 'mindshare', engines: { chatgpt: 5, claude: 3, perplexity: 4, gemini: 3 } },
      { domain: 'gartner.com', citations: 12, share: 7.7, type: 'mindshare', engines: { chatgpt: 4, claude: 3, google_ai: 3, gemini: 2 } },
      { domain: 'healthcatalyst.com', citations: 8, share: 5.1, type: 'direct', engines: { chatgpt: 2, claude: 2, perplexity: 2, google_ai: 2 } },
      { domain: 'trustradius.com', citations: 7, share: 4.5, type: 'mindshare', engines: { chatgpt: 2, perplexity: 3, gemini: 2 } },
      { domain: 'innovaccer.com', citations: 6, share: 3.8, type: 'direct', engines: { chatgpt: 2, claude: 2, perplexity: 2 } },
      { domain: 'capterra.com', citations: 5, share: 3.2, type: 'mindshare', engines: { chatgpt: 2, perplexity: 2, gemini: 1 } },
      { domain: 'insighthealth.ai', citations: 1, share: 0.8, type: 'direct', engines: { claude: 1 } },
      { domain: 'epic.com', citations: 4, share: 2.6, type: 'direct', engines: { google_ai: 2, gemini: 2 } },
    ],
  },
  {
    id: 'cl4', name: 'Decision Criteria', citations: 200, share: 0.5, domains: 112,
    presence: 'minimal', yourShare: 0.2, yourRank: 8, yourCitations: 0, color: CLUSTER_COLORS.cl4,
    queriesTotal: 15, queriesCovered: 4,
    engineBreakdown: { chatgpt: 45, claude: 40, perplexity: 42, google_ai: 38, gemini: 35 },
    competitors: [
      { domain: 'gartner.com', citations: 16, share: 8.0, type: 'mindshare', engines: { chatgpt: 5, claude: 4, perplexity: 4, gemini: 3 } },
      { domain: 'klas.com', citations: 12, share: 6.0, type: 'mindshare', engines: { chatgpt: 4, claude: 3, google_ai: 3, gemini: 2 } },
      { domain: 'himss.org', citations: 9, share: 4.5, type: 'authority', engines: { chatgpt: 3, claude: 2, perplexity: 2, google_ai: 2 } },
      { domain: 'healthcatalyst.com', citations: 8, share: 4.0, type: 'direct', engines: { chatgpt: 2, claude: 3, perplexity: 2, gemini: 1 } },
      { domain: 'definitivehc.com', citations: 6, share: 3.0, type: 'direct', engines: { perplexity: 3, google_ai: 2, gemini: 1 } },
      { domain: 'forrester.com', citations: 5, share: 2.5, type: 'mindshare', engines: { chatgpt: 2, claude: 2, gemini: 1 } },
      { domain: 'epic.com', citations: 5, share: 2.5, type: 'direct', engines: { chatgpt: 2, google_ai: 2, gemini: 1 } },
      { domain: 'cerner.com', citations: 4, share: 2.0, type: 'direct', engines: { chatgpt: 1, claude: 1, perplexity: 1, gemini: 1 } },
    ],
  },
  {
    id: 'cl5', name: 'Definition', citations: 131, share: 1.0, domains: 78,
    presence: 'low', yourShare: 0.5, yourRank: 6, yourCitations: 1, color: CLUSTER_COLORS.cl5,
    queriesTotal: 12, queriesCovered: 3,
    engineBreakdown: { chatgpt: 30, claude: 28, perplexity: 26, google_ai: 24, gemini: 23 },
    competitors: [
      { domain: 'www.cms.gov', citations: 11, share: 8.4, type: 'authority', engines: { chatgpt: 3, claude: 3, perplexity: 3, google_ai: 2 } },
      { domain: 'wikipedia.org', citations: 9, share: 6.9, type: 'authority', engines: { chatgpt: 3, perplexity: 3, google_ai: 2, gemini: 1 } },
      { domain: 'www.who.int', citations: 7, share: 5.3, type: 'authority', engines: { claude: 3, perplexity: 2, google_ai: 2 } },
      { domain: 'mayoclinic.org', citations: 6, share: 4.6, type: 'authority', engines: { chatgpt: 2, gemini: 2, google_ai: 2 } },
      { domain: 'healthit.gov', citations: 5, share: 3.8, type: 'authority', engines: { chatgpt: 2, claude: 2, gemini: 1 } },
      { domain: 'insighthealth.ai', citations: 1, share: 0.5, type: 'direct', engines: { claude: 1 } },
      { domain: 'nih.gov', citations: 4, share: 3.1, type: 'authority', engines: { chatgpt: 1, perplexity: 1, google_ai: 1, gemini: 1 } },
      { domain: 'ahrq.gov', citations: 3, share: 2.3, type: 'authority', engines: { claude: 1, perplexity: 1, gemini: 1 } },
    ],
  },
  {
    id: 'cl6', name: 'Problem/Awareness', citations: 229, share: 0, domains: 159,
    presence: 'none', yourShare: 0, yourRank: null, yourCitations: 0, color: CLUSTER_COLORS.cl6,
    queriesTotal: 16, queriesCovered: 0,
    engineBreakdown: { chatgpt: 43, claude: 65, perplexity: 65, google_ai: 0, gemini: 56 },
    competitors: [
      { domain: 'www.cms.gov', citations: 10, share: 4.4, type: 'authority', engines: { chatgpt: 3, claude: 3, perplexity: 2, gemini: 2 } },
      { domain: 'healthcatalyst.com', citations: 9, share: 3.9, type: 'direct', engines: { chatgpt: 3, claude: 2, perplexity: 2, gemini: 2 } },
      { domain: 'www.cdc.gov', citations: 8, share: 3.5, type: 'authority', engines: { chatgpt: 2, claude: 3, perplexity: 2, gemini: 1 } },
      { domain: 'innovaccer.com', citations: 5, share: 2.2, type: 'direct', engines: { chatgpt: 1, claude: 1, perplexity: 2, gemini: 1 } },
      { domain: 'psnet.ahrq.gov', citations: 4, share: 1.7, type: 'authority', engines: { claude: 2, perplexity: 1, gemini: 1 } },
      { domain: 'www.aafp.org', citations: 4, share: 1.7, type: 'mindshare', engines: { chatgpt: 1, claude: 1, perplexity: 1, gemini: 1 } },
      { domain: 'www.ncqa.org', citations: 4, share: 1.7, type: 'authority', engines: { chatgpt: 1, perplexity: 1, google_ai: 0, gemini: 2 } },
      { domain: 'link.springer.com', citations: 4, share: 1.7, type: 'mindshare', engines: { claude: 2, perplexity: 1, gemini: 1 } },
    ],
  },
  {
    id: 'cl7', name: 'Best-of/Consideration', citations: 201, share: 0, domains: 142,
    presence: 'none', yourShare: 0, yourRank: null, yourCitations: 0, color: CLUSTER_COLORS.cl7,
    queriesTotal: 14, queriesCovered: 0,
    engineBreakdown: { chatgpt: 48, claude: 42, perplexity: 45, google_ai: 35, gemini: 31 },
    competitors: [
      { domain: 'g2.com', citations: 14, share: 7.0, type: 'mindshare', engines: { chatgpt: 5, claude: 3, perplexity: 4, gemini: 2 } },
      { domain: 'gartner.com', citations: 11, share: 5.5, type: 'mindshare', engines: { chatgpt: 4, claude: 3, google_ai: 2, gemini: 2 } },
      { domain: 'trustradius.com', citations: 8, share: 4.0, type: 'mindshare', engines: { chatgpt: 3, perplexity: 3, gemini: 2 } },
      { domain: 'healthcatalyst.com', citations: 7, share: 3.5, type: 'direct', engines: { chatgpt: 2, claude: 2, perplexity: 2, gemini: 1 } },
      { domain: 'epic.com', citations: 6, share: 3.0, type: 'direct', engines: { chatgpt: 2, google_ai: 2, gemini: 2 } },
      { domain: 'klas.com', citations: 5, share: 2.5, type: 'mindshare', engines: { claude: 2, perplexity: 2, gemini: 1 } },
      { domain: 'innovaccer.com', citations: 5, share: 2.5, type: 'direct', engines: { chatgpt: 2, perplexity: 2, google_ai: 1 } },
      { domain: 'capterra.com', citations: 4, share: 2.0, type: 'mindshare', engines: { chatgpt: 1, perplexity: 2, gemini: 1 } },
    ],
  },
  {
    id: 'cl8', name: 'Branded Evaluation', citations: 176, share: 4.5, domains: 95,
    presence: 'moderate', yourShare: 2.1, yourRank: 2, yourCitations: 4, color: CLUSTER_COLORS.cl8,
    queriesTotal: 17, queriesCovered: 13,
    engineBreakdown: { chatgpt: 40, claude: 36, perplexity: 38, google_ai: 30, gemini: 32 },
    competitors: [
      { domain: 'insighthealth.ai', citations: 4, share: 2.1, type: 'direct', engines: { chatgpt: 1, claude: 1, perplexity: 1, gemini: 1 } },
      { domain: 'trustradius.com', citations: 10, share: 5.7, type: 'mindshare', engines: { chatgpt: 3, perplexity: 4, gemini: 3 } },
      { domain: 'g2.com', citations: 9, share: 5.1, type: 'mindshare', engines: { chatgpt: 3, claude: 2, perplexity: 2, gemini: 2 } },
      { domain: 'healthcatalyst.com', citations: 8, share: 4.5, type: 'direct', engines: { chatgpt: 2, claude: 3, perplexity: 2, gemini: 1 } },
      { domain: 'epic.com', citations: 7, share: 4.0, type: 'direct', engines: { chatgpt: 2, claude: 2, google_ai: 2, gemini: 1 } },
      { domain: 'capterra.com', citations: 5, share: 2.8, type: 'mindshare', engines: { chatgpt: 2, perplexity: 2, gemini: 1 } },
      { domain: 'softwareadvice.com', citations: 4, share: 2.3, type: 'mindshare', engines: { chatgpt: 1, claude: 1, perplexity: 1, gemini: 1 } },
      { domain: 'innovaccer.com', citations: 3, share: 1.7, type: 'direct', engines: { chatgpt: 1, perplexity: 1, gemini: 1 } },
    ],
  },
  {
    id: 'cl9', name: 'Feature Verification', citations: 170, share: 1.0, domains: 98,
    presence: 'low', yourShare: 0.6, yourRank: 5, yourCitations: 1, color: CLUSTER_COLORS.cl9,
    queriesTotal: 15, queriesCovered: 10,
    engineBreakdown: { chatgpt: 38, claude: 34, perplexity: 36, google_ai: 30, gemini: 32 },
    competitors: [
      { domain: 'healthcatalyst.com', citations: 11, share: 6.5, type: 'direct', engines: { chatgpt: 3, claude: 3, perplexity: 3, gemini: 2 } },
      { domain: 'epic.com', citations: 9, share: 5.3, type: 'direct', engines: { chatgpt: 3, claude: 2, google_ai: 2, gemini: 2 } },
      { domain: 'innovaccer.com', citations: 7, share: 4.1, type: 'direct', engines: { chatgpt: 2, perplexity: 3, gemini: 2 } },
      { domain: 'definitivehc.com', citations: 5, share: 2.9, type: 'direct', engines: { chatgpt: 2, claude: 1, perplexity: 1, gemini: 1 } },
      { domain: 'cerner.com', citations: 5, share: 2.9, type: 'direct', engines: { chatgpt: 1, claude: 2, google_ai: 1, gemini: 1 } },
      { domain: 'insighthealth.ai', citations: 1, share: 0.6, type: 'direct', engines: { perplexity: 1 } },
      { domain: 'athenahealth.com', citations: 4, share: 2.4, type: 'direct', engines: { chatgpt: 1, perplexity: 1, google_ai: 1, gemini: 1 } },
      { domain: 'oracle.com', citations: 3, share: 1.8, type: 'mindshare', engines: { chatgpt: 1, claude: 1, gemini: 1 } },
    ],
  },
];

// ── Gap Queries (sorted by opportunity score) ──────────────
export const GAP_QUERIES: GapQuery[] = [
  {
    id: 'gq1', query: 'Best healthcare analytics platforms comparison 2026', cluster: 'Best-of/Consideration', clusterId: 'cl7',
    gap: 0.224, classification: 'significant_gap', yourContent: null,
    topCited: { domain: 'g2.com', url: 'g2.com/categories/healthcare-analytics' },
    engines: { chatgpt: true, claude: true, perplexity: true, google_ai: true, gemini: true },
    opportunityScore: 0.95,
    topCitedSignals: { wordCount: 3200, headers: 18, hasFaq: true, hasTables: true, lists: 12, externalCitations: 24, readingLevel: 8.5, hasSchema: true },
  },
  {
    id: 'gq2', query: 'How can we improve HCC risk adjustment accuracy and reduce coding misses?', cluster: 'Problem/Awareness', clusterId: 'cl6',
    gap: 0.267, classification: 'significant_gap', yourContent: null,
    topCited: { domain: 'healthcatalyst.com', url: 'healthcatalyst.com/resources/hcc' },
    engines: { chatgpt: true, claude: true, perplexity: true, gemini: true, google_ai: false },
    opportunityScore: 0.92,
    topCitedSignals: { wordCount: 2400, headers: 14, hasFaq: true, hasTables: true, lists: 8, externalCitations: 12, readingLevel: 9.2, hasSchema: true },
  },
  {
    id: 'gq3', query: 'How can we operationalize SDoH data to target interventions?', cluster: 'Problem/Awareness', clusterId: 'cl6',
    gap: 0.259, classification: 'significant_gap', yourContent: null,
    topCited: { domain: 'innovaccer.com', url: 'innovaccer.com/blog/sdoh' },
    engines: { chatgpt: true, claude: false, perplexity: true, gemini: true, google_ai: true },
    opportunityScore: 0.88,
    topCitedSignals: { wordCount: 1800, headers: 10, hasFaq: false, hasTables: true, lists: 6, externalCitations: 8, readingLevel: 10.1, hasSchema: false },
  },
  {
    id: 'gq4', query: 'Medicare Advantage Star Ratings improvement strategies', cluster: 'Problem/Awareness', clusterId: 'cl6',
    gap: 0.126, classification: 'gap_to_close', yourContent: null,
    topCited: { domain: 'cms.gov', url: 'cms.gov/Medicare/star-ratings' },
    engines: { chatgpt: true, claude: false, perplexity: true, gemini: true, google_ai: true },
    opportunityScore: 0.78,
  },
  {
    id: 'gq5', query: 'How to reduce 30-day hospital readmissions with data analytics?', cluster: 'Problem/Awareness', clusterId: 'cl6',
    gap: 0.104, classification: 'gap_to_close', yourContent: null,
    topCited: { domain: 'healthcatalyst.com', url: 'healthcatalyst.com/readmissions' },
    engines: { chatgpt: true, claude: true, perplexity: true, gemini: false, google_ai: true },
    opportunityScore: 0.74,
  },
  {
    id: 'gq6', query: 'What are common failure modes of healthcare predictive models?', cluster: 'Mechanism', clusterId: 'cl1',
    gap: 0.147, classification: 'gap_to_close',
    yourContent: { url: 'insighthealth.ai/blog/predictive-models' },
    topCited: { domain: 'nature.com', url: 'nature.com/articles/ml-healthcare' },
    engines: { chatgpt: true, claude: true, perplexity: false, gemini: true, google_ai: true },
    opportunityScore: 0.71,
    yourSignals: { wordCount: 976, headers: 0, hasFaq: false, hasTables: false, lists: 0, externalCitations: 2, readingLevel: 12.5, hasSchema: false },
    topCitedSignals: { wordCount: 2400, headers: 14, hasFaq: true, hasTables: true, lists: 8, externalCitations: 12, readingLevel: 9.2, hasSchema: true },
  },
  {
    id: 'gq7', query: 'What are the limitations of using claims data alone for care gap detection?', cluster: 'Mechanism', clusterId: 'cl1',
    gap: 0.130, classification: 'gap_to_close',
    yourContent: { url: 'insighthealth.ai/blog/claims-data' },
    topCited: { domain: 'accountablehq.com', url: 'accountablehq.com/post/claims-data' },
    engines: { chatgpt: false, claude: true, perplexity: true, gemini: false, google_ai: true },
    opportunityScore: 0.65,
    yourSignals: { wordCount: 1200, headers: 4, hasFaq: false, hasTables: false, lists: 2, externalCitations: 3, readingLevel: 11.8, hasSchema: false },
    topCitedSignals: { wordCount: 1900, headers: 8, hasFaq: true, hasTables: false, lists: 5, externalCitations: 7, readingLevel: 10.2, hasSchema: false },
  },
  {
    id: 'gq8', query: 'How do we evaluate bias and fairness risk in AI models?', cluster: 'Mechanism', clusterId: 'cl1',
    gap: 0.103, classification: 'gap_to_close',
    yourContent: { url: 'insighthealth.ai/blog/ai-fairness' },
    topCited: { domain: 'arxiv.org', url: 'arxiv.org/abs/2103.12345' },
    engines: { chatgpt: true, claude: true, perplexity: false, gemini: false, google_ai: true },
    opportunityScore: 0.58,
    yourSignals: { wordCount: 800, headers: 2, hasFaq: false, hasTables: false, lists: 1, externalCitations: 4, readingLevel: 13.0, hasSchema: false },
    topCitedSignals: { wordCount: 3200, headers: 16, hasFaq: false, hasTables: true, lists: 10, externalCitations: 35, readingLevel: 14.0, hasSchema: false },
  },
  {
    id: 'gq9', query: 'HIPAA compliance requirements for AI in healthcare', cluster: 'Boundary', clusterId: 'cl2',
    gap: 0.085, classification: 'gap_to_close',
    yourContent: { url: 'insighthealth.ai/blog/hipaa-ai' },
    topCited: { domain: 'www.hhs.gov', url: 'hhs.gov/hipaa/ai-guidance' },
    engines: { chatgpt: true, claude: true, perplexity: true, gemini: true, google_ai: true },
    opportunityScore: 0.45,
    yourSignals: { wordCount: 1500, headers: 6, hasFaq: true, hasTables: false, lists: 4, externalCitations: 5, readingLevel: 11.0, hasSchema: false },
    topCitedSignals: { wordCount: 4500, headers: 22, hasFaq: true, hasTables: true, lists: 14, externalCitations: 0, readingLevel: 12.5, hasSchema: true },
  },
  {
    id: 'gq10', query: 'Insight Health vs Epic analytics capabilities', cluster: 'Branded Evaluation', clusterId: 'cl8',
    gap: 0.042, classification: 'roughly_equal',
    yourContent: { url: 'insighthealth.ai/blog/vs-epic' },
    topCited: { domain: 'insighthealth.ai', url: 'insighthealth.ai/blog/vs-epic' },
    engines: { chatgpt: true, claude: true, perplexity: true, gemini: false, google_ai: false },
    opportunityScore: 0.22,
    yourSignals: { wordCount: 2200, headers: 12, hasFaq: true, hasTables: true, lists: 6, externalCitations: 3, readingLevel: 9.8, hasSchema: true },
    topCitedSignals: { wordCount: 2200, headers: 12, hasFaq: true, hasTables: true, lists: 6, externalCitations: 3, readingLevel: 9.8, hasSchema: true },
  },
  {
    id: 'gq11', query: 'Top population health management tools for health systems', cluster: 'Best-of/Consideration', clusterId: 'cl7',
    gap: 0.198, classification: 'significant_gap', yourContent: null,
    topCited: { domain: 'gartner.com', url: 'gartner.com/reviews/market/phm' },
    engines: { chatgpt: true, claude: true, perplexity: true, gemini: true, google_ai: false },
    opportunityScore: 0.85,
  },
  {
    id: 'gq12', query: 'What criteria should health systems use to evaluate analytics vendors?', cluster: 'Decision Criteria', clusterId: 'cl4',
    gap: 0.182, classification: 'significant_gap', yourContent: null,
    topCited: { domain: 'klas.com', url: 'klas.com/report/analytics-2026' },
    engines: { chatgpt: true, claude: true, perplexity: false, gemini: true, google_ai: true },
    opportunityScore: 0.82,
  },
  {
    id: 'gq13', query: 'How does Insight Health compare to Innovaccer for value-based care?', cluster: 'Branded Evaluation', clusterId: 'cl8',
    gap: 0.055, classification: 'roughly_equal',
    yourContent: { url: 'insighthealth.ai/blog/vs-innovaccer' },
    topCited: { domain: 'trustradius.com', url: 'trustradius.com/compare/insighthealth-vs-innovaccer' },
    engines: { chatgpt: true, claude: false, perplexity: true, gemini: true, google_ai: false },
    opportunityScore: 0.30,
    yourSignals: { wordCount: 1800, headers: 8, hasFaq: false, hasTables: true, lists: 4, externalCitations: 2, readingLevel: 10.0, hasSchema: false },
    topCitedSignals: { wordCount: 2600, headers: 14, hasFaq: true, hasTables: true, lists: 8, externalCitations: 6, readingLevel: 8.5, hasSchema: true },
  },
  {
    id: 'gq14', query: 'Does Insight Health support HL7 FHIR interoperability?', cluster: 'Feature Verification', clusterId: 'cl9',
    gap: 0.038, classification: 'company_wins',
    yourContent: { url: 'insighthealth.ai/integrations/fhir' },
    topCited: { domain: 'insighthealth.ai', url: 'insighthealth.ai/integrations/fhir' },
    engines: { chatgpt: true, claude: true, perplexity: true, gemini: true, google_ai: false },
    opportunityScore: 0.15,
  },
  {
    id: 'gq15', query: 'What is healthcare data interoperability and why does it matter?', cluster: 'Definition', clusterId: 'cl5',
    gap: 0.145, classification: 'gap_to_close',
    yourContent: { url: 'insighthealth.ai/blog/interoperability' },
    topCited: { domain: 'healthit.gov', url: 'healthit.gov/topic/interoperability' },
    engines: { chatgpt: true, claude: true, perplexity: true, gemini: false, google_ai: true },
    opportunityScore: 0.52,
    yourSignals: { wordCount: 900, headers: 3, hasFaq: false, hasTables: false, lists: 1, externalCitations: 2, readingLevel: 11.5, hasSchema: false },
    topCitedSignals: { wordCount: 3800, headers: 20, hasFaq: true, hasTables: true, lists: 12, externalCitations: 0, readingLevel: 10.0, hasSchema: true },
  },
];

// ── Engine divergence data ─────────────────────────────────
export interface DivergenceRow {
  query: string;
  clusterId: string;
  engines: Partial<Record<EngineKey, string>>;
  agreement: number;
}

export const DIVERGENCE_DATA: DivergenceRow[] = [
  { query: 'How to improve HCC risk adjustment accuracy', clusterId: 'cl6', engines: { chatgpt: 'cms.gov', claude: 'healthcatalyst.com', perplexity: 'cms.gov', gemini: 'innovaccer.com' }, agreement: 40 },
  { query: 'Care gap detection using claims data', clusterId: 'cl1', engines: { chatgpt: 'innovaccer.com', perplexity: 'accountablehq.com', google_ai: 'cms.gov' }, agreement: 0 },
  { query: 'Best population health analytics platform', clusterId: 'cl7', engines: { chatgpt: 'g2.com', claude: 'gartner.com', perplexity: 'g2.com', google_ai: 'klas.com', gemini: 'trustradius.com' }, agreement: 40 },
  { query: 'Healthcare AI bias evaluation framework', clusterId: 'cl1', engines: { chatgpt: 'arxiv.org', claude: 'nature.com', google_ai: 'arxiv.org' }, agreement: 33 },
  { query: 'HIPAA compliance for AI in healthcare', clusterId: 'cl2', engines: { chatgpt: 'hhs.gov', claude: 'hhs.gov', perplexity: 'hipaajournal.com', google_ai: 'hhs.gov', gemini: 'nist.gov' }, agreement: 60 },
  { query: 'Insight Health vs Epic comparison', clusterId: 'cl8', engines: { chatgpt: 'insighthealth.ai', claude: 'insighthealth.ai', perplexity: 'trustradius.com' }, agreement: 67 },
  { query: 'What is value-based care analytics?', clusterId: 'cl5', engines: { chatgpt: 'cms.gov', claude: 'wikipedia.org', perplexity: 'cms.gov', google_ai: 'who.int', gemini: 'cms.gov' }, agreement: 60 },
  { query: 'Healthcare predictive model failure modes', clusterId: 'cl1', engines: { chatgpt: 'nature.com', claude: 'arxiv.org', gemini: 'nature.com', google_ai: 'pubmed.ncbi.nlm.nih.gov' }, agreement: 25 },
  { query: 'SDoH data integration best practices', clusterId: 'cl6', engines: { chatgpt: 'healthcatalyst.com', claude: 'cms.gov', perplexity: 'innovaccer.com', gemini: 'aafp.org' }, agreement: 0 },
  { query: 'Healthcare analytics vendor evaluation criteria', clusterId: 'cl4', engines: { chatgpt: 'gartner.com', claude: 'klas.com', perplexity: 'gartner.com', google_ai: 'himss.org', gemini: 'forrester.com' }, agreement: 40 },
  { query: 'Star Ratings optimization strategies for MA plans', clusterId: 'cl6', engines: { chatgpt: 'cms.gov', claude: 'healthcatalyst.com', perplexity: 'cms.gov', google_ai: 'cms.gov' }, agreement: 75 },
  { query: 'HL7 FHIR healthcare interoperability standards', clusterId: 'cl9', engines: { chatgpt: 'hl7.org', claude: 'hl7.org', perplexity: 'healthit.gov', google_ai: 'hl7.org', gemini: 'hl7.org' }, agreement: 80 },
];

// ── Embedding points (generated deterministically) ─────────
function generateEmbeddingPoints(): EmbeddingPoint[] {
  const rng = seededRandom(42);
  const points: EmbeddingPoint[] = [];
  let id = 0;

  const clusterCenters: Record<string, { ux: number; uy: number; tx: number; ty: number }> = {
    cl1: { ux: -3.2, uy: 1.5, tx: -15, ty: 8 },
    cl2: { ux: 2.1, uy: 3.8, tx: 12, ty: 18 },
    cl3: { ux: -1.5, uy: -2.8, tx: -8, ty: -14 },
    cl4: { ux: 4.2, uy: -1.2, tx: 20, ty: -6 },
    cl5: { ux: -4.5, uy: -0.5, tx: -22, ty: -2 },
    cl6: { ux: 0.8, uy: 5.2, tx: 4, ty: 25 },
    cl7: { ux: 3.8, uy: 2.5, tx: 18, ty: 12 },
    cl8: { ux: -2.0, uy: 4.0, tx: -10, ty: 20 },
    cl9: { ux: 1.5, uy: -4.0, tx: 7, ty: -20 },
  };

  const domains = [
    'healthcatalyst.com', 'innovaccer.com', 'epic.com', 'cms.gov', 'cdc.gov',
    'nature.com', 'arxiv.org', 'g2.com', 'gartner.com', 'hhs.gov',
    'trustradius.com', 'klas.com', 'himss.org', 'pubmed.ncbi.nlm.nih.gov',
    'accountablehq.com', 'definitivehc.com', 'cerner.com', 'athenahealth.com',
    'wikipedia.org', 'mayoclinic.org', 'ahrq.gov', 'ncqa.org',
  ];

  const queryTemplates = [
    'How to improve', 'Best practices for', 'What is', 'How does', 'Comparison of',
    'Evaluation of', 'Limitations of', 'Requirements for', 'Strategies for', 'Tools for',
  ];

  for (const cluster of CLUSTERS) {
    const center = clusterCenters[cluster.id];

    // Generate query points
    const queryCount = Math.floor(4 + rng() * 4);
    for (let i = 0; i < queryCount; i++) {
      const spread = 0.8;
      points.push({
        id: `pt-${id++}`,
        x: center.ux + (rng() - 0.5) * spread * 2,
        y: center.uy + (rng() - 0.5) * spread * 2,
        tsne_x: center.tx + (rng() - 0.5) * spread * 10,
        tsne_y: center.ty + (rng() - 0.5) * spread * 10,
        type: 'query',
        label: `${queryTemplates[Math.floor(rng() * queryTemplates.length)]} ${cluster.name.toLowerCase()} topic ${i + 1}`,
        cluster: cluster.name,
        clusterId: cluster.id,
        gapScore: rng() * 0.3,
      });
    }

    // Generate citation points
    const citCount = Math.floor(8 + rng() * 8);
    for (let i = 0; i < citCount; i++) {
      const spread = 1.2;
      const domain = domains[Math.floor(rng() * domains.length)];
      const isGov = domain.endsWith('.gov');
      const isEdu = domain.endsWith('.edu');
      const isOrg = domain.endsWith('.org');
      points.push({
        id: `pt-${id++}`,
        x: center.ux + (rng() - 0.5) * spread * 2,
        y: center.uy + (rng() - 0.5) * spread * 2,
        tsne_x: center.tx + (rng() - 0.5) * spread * 10,
        tsne_y: center.ty + (rng() - 0.5) * spread * 10,
        type: 'citation',
        label: `${domain}/article-${Math.floor(rng() * 1000)}`,
        cluster: cluster.name,
        clusterId: cluster.id,
        domain,
        engine: ENGINE_KEYS[Math.floor(rng() * ENGINE_KEYS.length)],
        authorityType: isGov ? 'government' : isEdu ? 'educational' : isOrg ? 'organization' : rng() > 0.8 ? 'news' : 'commercial',
        similarity: 0.5 + rng() * 0.5,
        wordCount: Math.floor(500 + rng() * 4000),
        headers: Math.floor(rng() * 20),
        hasFaq: rng() > 0.6,
      });
    }

    // Generate company content points
    if (cluster.yourCitations > 0) {
      const compCount = Math.max(1, Math.floor(1 + rng() * 3));
      for (let i = 0; i < compCount; i++) {
        const distFromCenter = 0.3 + rng() * 1.5;
        const angle = rng() * Math.PI * 2;
        points.push({
          id: `pt-${id++}`,
          x: center.ux + Math.cos(angle) * distFromCenter,
          y: center.uy + Math.sin(angle) * distFromCenter,
          tsne_x: center.tx + Math.cos(angle) * distFromCenter * 5,
          tsne_y: center.ty + Math.sin(angle) * distFromCenter * 5,
          type: 'company',
          label: `insighthealth.ai/blog/${cluster.name.toLowerCase().replace(/\//g, '-')}-${i + 1}`,
          cluster: cluster.name,
          clusterId: cluster.id,
          domain: 'insighthealth.ai',
          similarity: 0.4 + rng() * 0.5,
          gapScore: rng() * 0.2,
          wordCount: Math.floor(600 + rng() * 2000),
          headers: Math.floor(rng() * 12),
          hasFaq: rng() > 0.7,
        });
      }
    }
  }

  return points;
}

export const EMBEDDING_POINTS = generateEmbeddingPoints();

// ── Computed aggregates ────────────────────────────────────
export const TOTAL_TERRITORIES = CLUSTERS.length;
export const DANGER_ZONES = CLUSTERS.filter(c => c.presence === 'none').length;
export const CRITICAL_GAPS = GAP_QUERIES.filter(g => g.classification === 'significant_gap').length;
export const TOTAL_COMPETITORS = CLUSTERS.reduce((s, c) => s + c.domains, 0);

// ── Engine aggregate data ──────────────────────────────────
export function computeEngineData(): EngineData[] {
  return ENGINE_KEYS.map(key => {
    const meta = ENGINE_META[key];
    let total = 0;
    const domainCounts: Record<string, number> = {};

    for (const cluster of CLUSTERS) {
      total += cluster.engineBreakdown[key];
      for (const comp of cluster.competitors) {
        const count = comp.engines[key] || 0;
        if (count > 0) {
          domainCounts[comp.domain] = (domainCounts[comp.domain] || 0) + count;
        }
      }
    }

    // Find domains unique to this engine
    const thisEngineDomains = new Set(Object.keys(domainCounts));
    for (const otherKey of ENGINE_KEYS) {
      if (otherKey === key) continue;
      for (const cluster of CLUSTERS) {
        for (const comp of cluster.competitors) {
          if ((comp.engines[otherKey] || 0) > 0) {
            thisEngineDomains.delete(comp.domain); // not unique
          }
        }
      }
    }

    const sorted = Object.entries(domainCounts).sort((a, b) => b[1] - a[1]);
    const topDomain = sorted[0]?.[0] || '';

    const traits: string[] = [];
    if (key === 'chatgpt') traits.push('Blog articles', 'Comparison content', '1400+ words');
    if (key === 'claude') traits.push('Technical papers', 'In-depth analysis', '2000+ words');
    if (key === 'perplexity') traits.push('FAQ sections', 'Listicles', '1200+ words');
    if (key === 'google_ai') traits.push('Schema markup', 'Structured data', '1800+ words');
    if (key === 'gemini') traits.push('Comprehensive guides', 'Tables & charts', '1600+ words');

    return {
      key,
      label: meta.label,
      domain: meta.domain,
      totalCitations: total,
      uniqueCitations: thisEngineDomains.size,
      topDomain,
      preferredTraits: traits,
      avgWordCount: key === 'chatgpt' ? 1400 : key === 'claude' ? 2000 : key === 'perplexity' ? 1200 : key === 'google_ai' ? 1800 : 1600,
    };
  });
}

export const ENGINE_DATA = computeEngineData();

// ── Helper: get cluster-filtered competitor data for an engine ──
export function getClusterDataForEngine(engineKey: EngineKey | 'all'): ClusterData[] {
  if (engineKey === 'all') return CLUSTERS;

  return CLUSTERS.map(cluster => {
    const engineTotal = cluster.engineBreakdown[engineKey as EngineKey];
    const filteredCompetitors = cluster.competitors
      .map(c => ({
        ...c,
        citations: c.engines[engineKey as EngineKey] || 0,
        share: engineTotal > 0 ? ((c.engines[engineKey as EngineKey] || 0) / engineTotal) * 100 : 0,
      }))
      .filter(c => c.citations > 0)
      .sort((a, b) => b.citations - a.citations);

    const yourComp = filteredCompetitors.find(c => c.domain === 'insighthealth.ai');
    return {
      ...cluster,
      citations: engineTotal,
      competitors: filteredCompetitors,
      yourCitations: yourComp?.citations || 0,
      yourShare: yourComp?.share || 0,
      yourRank: yourComp ? filteredCompetitors.indexOf(yourComp) + 1 : null,
    };
  });
}
