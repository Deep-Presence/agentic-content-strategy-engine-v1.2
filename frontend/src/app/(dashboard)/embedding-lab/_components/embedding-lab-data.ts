/**
 * Embedding Lab — Mock Data & Types
 * ══════════════════════════════════
 * Structured to match backend Pydantic schemas field-for-field.
 * When real API is ready, swap the data source — component props stay the same.
 */

import type { Platform } from '@/types';

// ─── Types (mirror backend schemas) ─────────────────────────────────────────

export interface BrandPresence {
  domain: string;
  citationCount: number;
  avgSimilarity: number;
  platforms: Platform[];
  isCompany: boolean;
}

export interface ClusterData {
  id: string;
  name: string;
  queryCount: number;
  avgGap: number;
  gapClassification: 'critical' | 'warning' | 'moderate' | 'strong';
  brands: BrandPresence[];
}

export interface ScatterPoint {
  id: string;
  type: 'query' | 'citation' | 'company';
  x: number;
  y: number;
  cluster: string;
  clusterId: string;
  label: string;
  url?: string;
  similarity?: number;
  domain?: string;
}

export interface EmbeddingProjectionResponse {
  method: 'umap' | 'tsne';
  pointCount: number;
  points: ScatterPoint[];
}

export interface QueryRow {
  id: string;
  text: string;
  cluster: string;
  clusterId: string;
  gapScore: number;
  classification: 'significant_gap' | 'gap_to_close' | 'roughly_equal' | 'company_wins';
  companySimilarity: number;
  citationSimilarity: number;
  topDomain: string;
  platforms: Platform[];
  companyCited: boolean;
}

export interface StructuralFingerprint {
  faqRate: number;
  definitionOpening: number;
  keyTakeaways: number;
  comparisonTable: number;
  stepByStep: number;
  researchRefs: number;
}

export interface ClusterFingerprints {
  clusterId: string;
  clusterName: string;
  topCited: StructuralFingerprint;
  company: StructuralFingerprint;
}

export interface SignalCorrelationRow {
  signal: string;
  category: 'structure' | 'authority' | 'content' | 'technical' | 'engagement';
  correlation: number;
  pValue: number;
}

export interface PlatformSignalRow {
  platform: Platform;
  topSignals: { signal: string; importance: number }[];
}

export interface ClusterPerformanceRow {
  clusterId: string;
  clusterName: string;
  queryCount: number;
  avgGap: number;
  companyRank: number;
  totalBrands: number;
  companyCitationShare: number;
}

export interface GapSummaryResponse {
  totalCitations: number;
  companyCitations: number;
  clusterCount: number;
  queryCount: number;
  shareOfVoice: number;
  avgGap: number;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const COMPANY_DOMAIN = 'deeppresence.io';

const COMPETITOR_DOMAINS = [
  'hubspot.com', 'stripe.com', 'cloudflare.com', 'crowdstrike.com',
  'semrush.com', 'ahrefs.com', 'vercel.com', 'datadog.com',
  'snowflake.com', 'confluent.io', 'hashicorp.com', 'twilio.com',
  'segment.com', 'amplitude.com', 'mixpanel.com',
];

const ALL_PLATFORMS: Platform[] = ['chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini'];

export const CLUSTER_COLORS: Record<string, string> = {
  c1: '#5BA4C4', // Mechanism — teal
  c2: '#E5484D', // Boundary — red
  c3: '#34B27B', // Definition — green
  c4: '#DC7B18', // Category Comparison — amber
  c5: '#8B5CF6', // Problem/Awareness — purple
  c6: '#EC4899', // Use Case — pink
  c7: '#F59E0B', // Ecosystem — yellow
  c8: '#06B6D4', // How-To — cyan
};

// ─── Cluster data ───────────────────────────────────────────────────────────

function pickPlatforms(n: number): Platform[] {
  const shuffled = [...ALL_PLATFORMS].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}

function makeBrands(clusterSeed: number): BrandPresence[] {
  const count = 4 + (clusterSeed % 4); // 4-7 brands per cluster
  const domains = [...COMPETITOR_DOMAINS].sort(() => Math.random() - 0.5).slice(0, count);
  const brands: BrandPresence[] = domains.map((d) => ({
    domain: d,
    citationCount: Math.floor(12 + Math.random() * 40),
    avgSimilarity: 0.55 + Math.random() * 0.35,
    platforms: pickPlatforms(2 + Math.floor(Math.random() * 3)),
    isCompany: false,
  }));
  // Insert company
  brands.push({
    domain: COMPANY_DOMAIN,
    citationCount: Math.floor(3 + Math.random() * 18),
    avgSimilarity: 0.4 + Math.random() * 0.3,
    platforms: pickPlatforms(2 + Math.floor(Math.random() * 2)),
    isCompany: true,
  });
  return brands.sort((a, b) => b.citationCount - a.citationCount);
}

const CLUSTER_DEFS: Omit<ClusterData, 'brands'>[] = [
  { id: 'c1', name: 'SaaS Pricing Strategy', queryCount: 28, avgGap: 0.18, gapClassification: 'critical' },
  { id: 'c2', name: 'Enterprise Security', queryCount: 24, avgGap: 0.14, gapClassification: 'warning' },
  { id: 'c3', name: 'API Documentation', queryCount: 22, avgGap: 0.06, gapClassification: 'moderate' },
  { id: 'c4', name: 'AI Content Marketing', queryCount: 20, avgGap: 0.12, gapClassification: 'warning' },
  { id: 'c5', name: 'Developer Experience', queryCount: 18, avgGap: -0.02, gapClassification: 'strong' },
  { id: 'c6', name: 'Product Analytics', queryCount: 16, avgGap: 0.09, gapClassification: 'moderate' },
  { id: 'c7', name: 'Integration Ecosystem', queryCount: 14, avgGap: 0.15, gapClassification: 'warning' },
  { id: 'c8', name: 'Compliance & Privacy', queryCount: 14, avgGap: 0.21, gapClassification: 'critical' },
];

export const CLUSTERS: ClusterData[] = CLUSTER_DEFS.map((c, i) => ({ ...c, brands: makeBrands(i) }));

// ─── Gap summary ────────────────────────────────────────────────────────────

const totalCitations = CLUSTERS.reduce((s, c) => s + c.brands.reduce((bs, b) => bs + b.citationCount, 0), 0);
const companyCitations = CLUSTERS.reduce((s, c) => {
  const cb = c.brands.find(b => b.isCompany);
  return s + (cb?.citationCount ?? 0);
}, 0);

export const GAP_SUMMARY: GapSummaryResponse = {
  totalCitations,
  companyCitations,
  clusterCount: CLUSTERS.length,
  queryCount: CLUSTERS.reduce((s, c) => s + c.queryCount, 0),
  shareOfVoice: Math.round((companyCitations / totalCitations) * 1000) / 10,
  avgGap: 0.047,
};

// ─── Cluster performance ────────────────────────────────────────────────────

export const CLUSTER_PERFORMANCE: ClusterPerformanceRow[] = CLUSTERS.map(c => {
  const sorted = [...c.brands].sort((a, b) => b.citationCount - a.citationCount);
  const companyIdx = sorted.findIndex(b => b.isCompany);
  const totalBrandCitations = c.brands.reduce((s, b) => s + b.citationCount, 0);
  const companyCit = c.brands.find(b => b.isCompany)?.citationCount ?? 0;
  return {
    clusterId: c.id,
    clusterName: c.name,
    queryCount: c.queryCount,
    avgGap: c.avgGap,
    companyRank: companyIdx + 1,
    totalBrands: c.brands.length,
    companyCitationShare: Math.round((companyCit / totalBrandCitations) * 100),
  };
});

// ─── Scatter points (generate ~650 per projection) ─────────────────────────

const CLUSTER_CENTERS_UMAP: Record<string, [number, number]> = {
  c1: [-6, 4], c2: [5, -3], c3: [8, 6], c4: [-3, -7],
  c5: [2, 9], c6: [-8, -2], c7: [7, -8], c8: [-1, 12],
};

const CLUSTER_CENTERS_TSNE: Record<string, [number, number]> = {
  c1: [-12, 8], c2: [-3, -6], c3: [5, 4], c4: [10, -2],
  c5: [2, 12], c6: [-8, -12], c7: [14, 9], c8: [-1, 15],
};

function jitter(center: number, spread: number): number {
  // Box-Muller for Gaussian jitter
  const u1 = Math.random();
  const u2 = Math.random();
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  return center + z * spread;
}

function generateScatterPoints(
  centers: Record<string, [number, number]>,
  method: 'umap' | 'tsne',
): ScatterPoint[] {
  const points: ScatterPoint[] = [];
  let qIdx = 0;
  let cIdx = 0;
  let compIdx = 0;

  for (const cluster of CLUSTERS) {
    const [cx, cy] = centers[cluster.id];
    const spread = method === 'umap' ? 1.8 : 2.5;

    // Queries
    for (let i = 0; i < cluster.queryCount; i++) {
      points.push({
        id: `q-${String(++qIdx).padStart(3, '0')}`,
        type: 'query',
        x: jitter(cx, spread),
        y: jitter(cy, spread),
        cluster: cluster.name,
        clusterId: cluster.id,
        label: QUERY_TEXTS[qIdx % QUERY_TEXTS.length],
      });
    }

    // Citations (3-5 per query for top queries, 1-2 for others ≈ 2.5× queries avg)
    const citCount = Math.floor(cluster.queryCount * 2.5);
    for (let i = 0; i < citCount; i++) {
      const domain = COMPETITOR_DOMAINS[i % COMPETITOR_DOMAINS.length];
      points.push({
        id: `cit-${String(++cIdx).padStart(3, '0')}`,
        type: 'citation',
        x: jitter(cx, spread * 0.9),
        y: jitter(cy, spread * 0.9),
        cluster: cluster.name,
        clusterId: cluster.id,
        label: `https://${domain}/content/${cluster.id}-${i}`,
        url: `https://${domain}/content/${cluster.id}-${i}`,
        similarity: 0.45 + Math.random() * 0.45,
        domain,
      });
    }

    // Company points (2-4 per cluster)
    const compCount = 2 + Math.floor(Math.random() * 3);
    for (let i = 0; i < compCount; i++) {
      points.push({
        id: `comp-${String(++compIdx).padStart(3, '0')}`,
        type: 'company',
        x: jitter(cx, spread * 1.1),
        y: jitter(cy, spread * 1.1),
        cluster: cluster.name,
        clusterId: cluster.id,
        label: `${COMPANY_DOMAIN}/blog/${cluster.id}-${i}`,
        url: `https://${COMPANY_DOMAIN}/blog/${cluster.id}-${i}`,
        similarity: 0.35 + Math.random() * 0.35,
        domain: COMPANY_DOMAIN,
      });
    }
  }

  return points;
}

const QUERY_TEXTS = [
  'How should SaaS companies price their enterprise tier?',
  'What is usage-based pricing for cloud services?',
  'Best practices for SaaS pricing page design',
  'How to calculate customer lifetime value for SaaS',
  'What security certifications do enterprise buyers require?',
  'How to implement SOC 2 compliance for SaaS startups?',
  'Zero trust architecture for cloud-native applications',
  'Best API documentation tools for developer platforms',
  'How to write effective API reference documentation',
  'OpenAPI specification best practices',
  'How to use AI for content marketing at scale',
  'What is programmatic SEO for SaaS companies?',
  'AI content generation vs human-written content quality',
  'How to improve developer onboarding experience',
  'What makes a good developer experience (DX)?',
  'How to measure product analytics for B2B SaaS',
  'What are the best product analytics tools?',
  'Event tracking best practices for SaaS',
  'How to build an integration marketplace',
  'What APIs do CRM platforms typically expose?',
  'How to achieve GDPR compliance for SaaS',
  'Data privacy requirements for AI applications',
  'How to create a SOC 2 compliance program',
  'What is the difference between SOC 1 and SOC 2?',
  'How to price AI features in SaaS products',
  'Freemium vs free trial for SaaS conversion',
  'Enterprise SaaS security questionnaire best answers',
  'How to build developer documentation portals',
  'Content-led growth strategies for B2B SaaS',
  'How to track AI citation sources for attribution',
  'What is AEO (Answer Engine Optimization)?',
  'How to optimize content for AI search engines',
  'Developer community building strategies',
  'SDK design best practices for platform companies',
  'How to integrate with Salesforce API',
  'Webhook design patterns for event-driven architecture',
  'HIPAA compliance for cloud SaaS applications',
  'How to handle data residency requirements',
  'Enterprise SSO implementation guide',
  'How to build a consumption-based billing system',
];

export const UMAP_PROJECTION: EmbeddingProjectionResponse = {
  method: 'umap',
  pointCount: 0,
  points: generateScatterPoints(CLUSTER_CENTERS_UMAP, 'umap'),
};
UMAP_PROJECTION.pointCount = UMAP_PROJECTION.points.length;

export const TSNE_PROJECTION: EmbeddingProjectionResponse = {
  method: 'tsne',
  pointCount: 0,
  points: generateScatterPoints(CLUSTER_CENTERS_TSNE, 'tsne'),
};
TSNE_PROJECTION.pointCount = TSNE_PROJECTION.points.length;

// ─── Query rows per cluster ─────────────────────────────────────────────────

export function getQueriesForCluster(clusterId: string): QueryRow[] {
  const cluster = CLUSTERS.find(c => c.id === clusterId);
  if (!cluster) return [];

  return Array.from({ length: cluster.queryCount }, (_, i) => {
    const gap = cluster.avgGap + (Math.random() - 0.5) * 0.15;
    const classification: QueryRow['classification'] =
      gap > 0.12 ? 'significant_gap' :
      gap > 0.05 ? 'gap_to_close' :
      gap > -0.02 ? 'roughly_equal' :
      'company_wins';

    return {
      id: `${clusterId}-q-${String(i + 1).padStart(3, '0')}`,
      text: QUERY_TEXTS[(i + CLUSTERS.indexOf(cluster) * 5) % QUERY_TEXTS.length],
      cluster: cluster.name,
      clusterId,
      gapScore: Math.round(gap * 1000) / 1000,
      classification,
      companySimilarity: 0.35 + Math.random() * 0.4,
      citationSimilarity: 0.55 + Math.random() * 0.35,
      topDomain: COMPETITOR_DOMAINS[i % COMPETITOR_DOMAINS.length],
      platforms: pickPlatforms(2 + Math.floor(Math.random() * 3)),
      companyCited: Math.random() > 0.6,
    };
  });
}

// ─── Structural fingerprints ────────────────────────────────────────────────

export const CLUSTER_FINGERPRINTS: ClusterFingerprints[] = CLUSTERS.map(c => ({
  clusterId: c.id,
  clusterName: c.name,
  topCited: {
    faqRate: 0.5 + Math.random() * 0.4,
    definitionOpening: 0.3 + Math.random() * 0.5,
    keyTakeaways: 0.4 + Math.random() * 0.4,
    comparisonTable: 0.2 + Math.random() * 0.6,
    stepByStep: 0.3 + Math.random() * 0.4,
    researchRefs: 0.4 + Math.random() * 0.4,
  },
  company: {
    faqRate: 0.1 + Math.random() * 0.5,
    definitionOpening: 0.1 + Math.random() * 0.4,
    keyTakeaways: 0.2 + Math.random() * 0.4,
    comparisonTable: 0.05 + Math.random() * 0.4,
    stepByStep: 0.1 + Math.random() * 0.5,
    researchRefs: 0.1 + Math.random() * 0.4,
  },
}));

// ─── Signal correlations (~40 signals) ──────────────────────────────────────

export const SIGNAL_CORRELATIONS: SignalCorrelationRow[] = [
  // Structure signals
  { signal: 'FAQ Section Present', category: 'structure', correlation: 0.72, pValue: 0.001 },
  { signal: 'Header Count (H2+)', category: 'structure', correlation: 0.68, pValue: 0.001 },
  { signal: 'Comparison Table', category: 'structure', correlation: 0.61, pValue: 0.003 },
  { signal: 'Key Takeaways Box', category: 'structure', correlation: 0.58, pValue: 0.004 },
  { signal: 'Step-by-Step Format', category: 'structure', correlation: 0.54, pValue: 0.008 },
  { signal: 'Definition Opening', category: 'structure', correlation: 0.51, pValue: 0.01 },
  { signal: 'Table of Contents', category: 'structure', correlation: 0.48, pValue: 0.015 },
  { signal: 'Numbered Lists', category: 'structure', correlation: 0.44, pValue: 0.02 },
  { signal: 'Code Blocks', category: 'structure', correlation: 0.38, pValue: 0.03 },
  { signal: 'Image Alt Text', category: 'structure', correlation: 0.22, pValue: 0.08 },

  // Authority signals
  { signal: 'External Citation Count', category: 'authority', correlation: 0.65, pValue: 0.002 },
  { signal: 'Author Bio Present', category: 'authority', correlation: 0.55, pValue: 0.006 },
  { signal: 'Publication Date', category: 'authority', correlation: 0.49, pValue: 0.012 },
  { signal: 'Domain Authority Score', category: 'authority', correlation: 0.46, pValue: 0.018 },
  { signal: 'Research References', category: 'authority', correlation: 0.42, pValue: 0.022 },
  { signal: 'Expert Quotes', category: 'authority', correlation: 0.36, pValue: 0.035 },
  { signal: '.gov/.edu Backlinks', category: 'authority', correlation: 0.31, pValue: 0.05 },
  { signal: 'Peer Review Signal', category: 'authority', correlation: 0.18, pValue: 0.12 },

  // Content signals
  { signal: 'Word Count (2000+)', category: 'content', correlation: 0.59, pValue: 0.004 },
  { signal: 'Reading Level (Grade 10-12)', category: 'content', correlation: 0.52, pValue: 0.009 },
  { signal: 'Paragraph Length Variance', category: 'content', correlation: 0.41, pValue: 0.024 },
  { signal: 'Statistical Data Points', category: 'content', correlation: 0.39, pValue: 0.028 },
  { signal: 'Actionable CTAs', category: 'content', correlation: 0.34, pValue: 0.04 },
  { signal: 'Freshness (< 6 months)', category: 'content', correlation: 0.29, pValue: 0.055 },
  { signal: 'Entity Coverage Density', category: 'content', correlation: 0.25, pValue: 0.07 },
  { signal: 'Keyword Density', category: 'content', correlation: -0.15, pValue: 0.15 },
  { signal: 'Promotional Language', category: 'content', correlation: -0.42, pValue: 0.022 },
  { signal: 'Thin Content (< 500 words)', category: 'content', correlation: -0.58, pValue: 0.005 },

  // Technical signals
  { signal: 'Schema.org Markup', category: 'technical', correlation: 0.47, pValue: 0.016 },
  { signal: 'Page Speed Score', category: 'technical', correlation: 0.35, pValue: 0.038 },
  { signal: 'Mobile Responsiveness', category: 'technical', correlation: 0.32, pValue: 0.045 },
  { signal: 'HTTPS', category: 'technical', correlation: 0.28, pValue: 0.06 },
  { signal: 'Core Web Vitals Pass', category: 'technical', correlation: 0.26, pValue: 0.065 },
  { signal: 'Canonical URL Set', category: 'technical', correlation: 0.19, pValue: 0.1 },
  { signal: 'Render Blocking Resources', category: 'technical', correlation: -0.21, pValue: 0.09 },
  { signal: 'Broken Internal Links', category: 'technical', correlation: -0.38, pValue: 0.03 },

  // Engagement signals
  { signal: 'Avg Time on Page', category: 'engagement', correlation: 0.56, pValue: 0.005 },
  { signal: 'Social Share Count', category: 'engagement', correlation: 0.43, pValue: 0.02 },
  { signal: 'Comment Count', category: 'engagement', correlation: 0.33, pValue: 0.042 },
  { signal: 'Bounce Rate', category: 'engagement', correlation: -0.48, pValue: 0.014 },
  { signal: 'Scroll Depth < 25%', category: 'engagement', correlation: -0.52, pValue: 0.009 },
];

// ─── Platform signal rankings ───────────────────────────────────────────────

export const PLATFORM_SIGNALS: PlatformSignalRow[] = [
  {
    platform: 'chatgpt',
    topSignals: [
      { signal: 'FAQ Section Present', importance: 0.89 },
      { signal: 'External Citation Count', importance: 0.82 },
      { signal: 'Word Count (2000+)', importance: 0.78 },
      { signal: 'Header Count (H2+)', importance: 0.71 },
      { signal: 'Schema.org Markup', importance: 0.65 },
    ],
  },
  {
    platform: 'claude',
    topSignals: [
      { signal: 'Research References', importance: 0.91 },
      { signal: 'Reading Level (Grade 10-12)', importance: 0.84 },
      { signal: 'External Citation Count', importance: 0.79 },
      { signal: 'Statistical Data Points', importance: 0.72 },
      { signal: 'Author Bio Present', importance: 0.68 },
    ],
  },
  {
    platform: 'gemini',
    topSignals: [
      { signal: 'Schema.org Markup', importance: 0.87 },
      { signal: 'FAQ Section Present', importance: 0.81 },
      { signal: 'Page Speed Score', importance: 0.76 },
      { signal: 'Comparison Table', importance: 0.70 },
      { signal: 'Publication Date', importance: 0.64 },
    ],
  },
  {
    platform: 'perplexity',
    topSignals: [
      { signal: 'External Citation Count', importance: 0.93 },
      { signal: 'Freshness (< 6 months)', importance: 0.86 },
      { signal: 'Domain Authority Score', importance: 0.80 },
      { signal: 'Header Count (H2+)', importance: 0.73 },
      { signal: 'Key Takeaways Box', importance: 0.67 },
    ],
  },
];

// ─── Category metadata ──────────────────────────────────────────────────────

export const SIGNAL_CATEGORY_COLORS: Record<string, string> = {
  structure: 'var(--accent)',
  authority: 'var(--success)',
  content: 'var(--warning)',
  technical: 'var(--info)',
  engagement: '#8B5CF6',
};
