import type { ClusterSpec, GapBrief, StructuralSignals, CitationExemplar } from '@/types/gap-analysis';

export const CLUSTER_COLORS = [
  'var(--color-terracotta-400)',
  'var(--color-ocean-400)',
  'var(--color-sage-400)',
  '#e8926d',
  '#9abfdb',
  '#a3b88e',
  '#c4593a',
  '#4a7ba8',
  '#5a6f45',
] as const;

export const CLUSTER_COLOR_MAP: Record<string, string> = {
  C1: '#d97757',
  C2: '#6a9bcc',
  C3: '#788c5d',
  C4: '#e8926d',
  C5: '#9abfdb',
  C6: '#a3b88e',
  C7: '#c4593a',
  C8: '#4a7ba8',
  C9: '#5a6f45',
};

export const SAMPLE_CLUSTERS: ClusterSpec[] = [
  {
    cluster_id: 'C1',
    cluster_name: 'Mechanism',
    query_count: 8,
    citations_analyzed: 42,
    centroid_distance: 0.34,
    min_similarity_threshold: 0.62,
    word_count_range: { min: 1200, max: 2400 },
    required_elements: ['headers', 'lists', 'stats'],
    structural_rates: { headers: 0.90, lists: 0.80, stats: 0.62, citations: 0.96 },
    avg_word_count: 1740,
    faq_rate: 0.32,
    table_rate: 0.21,
    key_takeaways_rate: 0.45,
    dominant_content_type: 'guide',
    dominant_authority_type: 'industry_expert',
    exemplar_themes: ['how it works', 'underlying technology', 'architecture'],
  },
  {
    cluster_id: 'C2',
    cluster_name: 'Boundary',
    query_count: 8,
    citations_analyzed: 38,
    centroid_distance: 0.31,
    min_similarity_threshold: 0.58,
    word_count_range: { min: 1100, max: 2200 },
    required_elements: ['headers', 'comparison_table', 'stats'],
    structural_rates: { headers: 0.96, lists: 0.78, stats: 0.75, citations: 0.98 },
    avg_word_count: 1596,
    faq_rate: 0.23,
    table_rate: 0.29,
    key_takeaways_rate: 0.38,
    dominant_content_type: 'comparison',
    dominant_authority_type: 'analyst',
    exemplar_themes: ['limitations', 'edge cases', 'when not to use'],
  },
  {
    cluster_id: 'C3',
    cluster_name: 'Category Comparison',
    query_count: 8,
    citations_analyzed: 45,
    centroid_distance: 0.28,
    min_similarity_threshold: 0.65,
    word_count_range: { min: 1400, max: 2500 },
    required_elements: ['headers', 'comparison_table', 'lists'],
    structural_rates: { headers: 0.96, lists: 0.87, stats: 0.75, citations: 0.96 },
    avg_word_count: 1858,
    faq_rate: 0.36,
    table_rate: 0.39,
    key_takeaways_rate: 0.52,
    dominant_content_type: 'comparison',
    dominant_authority_type: 'industry_expert',
    exemplar_themes: ['vs competitors', 'category landscape', 'market position'],
  },
  {
    cluster_id: 'C4',
    cluster_name: 'Decision Criteria',
    query_count: 8,
    citations_analyzed: 40,
    centroid_distance: 0.36,
    min_similarity_threshold: 0.60,
    word_count_range: { min: 1500, max: 2800 },
    required_elements: ['headers', 'lists', 'stats', 'key_takeaways'],
    structural_rates: { headers: 0.91, lists: 0.77, stats: 0.71, citations: 0.95 },
    avg_word_count: 2055,
    faq_rate: 0.27,
    table_rate: 0.24,
    key_takeaways_rate: 0.61,
    dominant_content_type: 'guide',
    dominant_authority_type: 'industry_expert',
    exemplar_themes: ['evaluation criteria', 'buying guide', 'selection process'],
  },
  {
    cluster_id: 'C5',
    cluster_name: 'Definition',
    query_count: 8,
    citations_analyzed: 36,
    centroid_distance: 0.25,
    min_similarity_threshold: 0.70,
    word_count_range: { min: 1000, max: 2200 },
    required_elements: ['definition_opening', 'headers', 'lists'],
    structural_rates: { headers: 0.92, lists: 0.80, stats: 0.68, citations: 0.93 },
    avg_word_count: 1690,
    faq_rate: 0.24,
    table_rate: 0.12,
    key_takeaways_rate: 0.35,
    dominant_content_type: 'explainer',
    dominant_authority_type: 'documentation',
    exemplar_themes: ['what is', 'definition', 'fundamentals'],
  },
  {
    cluster_id: 'C6',
    cluster_name: 'Problem/Awareness',
    query_count: 8,
    citations_analyzed: 41,
    centroid_distance: 0.30,
    min_similarity_threshold: 0.63,
    word_count_range: { min: 1100, max: 2300 },
    required_elements: ['headers', 'lists', 'step_by_step'],
    structural_rates: { headers: 0.95, lists: 0.84, stats: 0.73, citations: 0.95 },
    avg_word_count: 1685,
    faq_rate: 0.23,
    table_rate: 0.13,
    key_takeaways_rate: 0.40,
    dominant_content_type: 'blog',
    dominant_authority_type: 'thought_leader',
    exemplar_themes: ['pain points', 'challenges', 'problems solved'],
  },
  {
    cluster_id: 'C7',
    cluster_name: 'Best-of/Consideration',
    query_count: 8,
    citations_analyzed: 44,
    centroid_distance: 0.33,
    min_similarity_threshold: 0.61,
    word_count_range: { min: 1200, max: 2400 },
    required_elements: ['headers', 'lists', 'comparison_table'],
    structural_rates: { headers: 0.91, lists: 0.84, stats: 0.71, citations: 0.95 },
    avg_word_count: 1748,
    faq_rate: 0.28,
    table_rate: 0.29,
    key_takeaways_rate: 0.48,
    dominant_content_type: 'listicle',
    dominant_authority_type: 'reviewer',
    exemplar_themes: ['best tools', 'top picks', 'roundup'],
  },
  {
    cluster_id: 'C8',
    cluster_name: 'Branded Evaluation',
    query_count: 8,
    citations_analyzed: 43,
    centroid_distance: 0.29,
    min_similarity_threshold: 0.66,
    word_count_range: { min: 1300, max: 2500 },
    required_elements: ['headers', 'stats', 'comparison_table', 'faq'],
    structural_rates: { headers: 0.92, lists: 0.80, stats: 0.77, citations: 0.97 },
    avg_word_count: 1821,
    faq_rate: 0.38,
    table_rate: 0.40,
    key_takeaways_rate: 0.55,
    dominant_content_type: 'review',
    dominant_authority_type: 'analyst',
    exemplar_themes: ['review', 'analysis', 'evaluation'],
  },
  {
    cluster_id: 'C9',
    cluster_name: 'Feature Verification',
    query_count: 8,
    citations_analyzed: 35,
    centroid_distance: 0.38,
    min_similarity_threshold: 0.55,
    word_count_range: { min: 900, max: 1900 },
    required_elements: ['headers', 'lists'],
    structural_rates: { headers: 0.86, lists: 0.80, stats: 0.56, citations: 0.99 },
    avg_word_count: 1423,
    faq_rate: 0.22,
    table_rate: 0.20,
    key_takeaways_rate: 0.30,
    dominant_content_type: 'documentation',
    dominant_authority_type: 'official',
    exemplar_themes: ['does it support', 'feature check', 'capability'],
  },
];

const sampleSignals: StructuralSignals = {
  word_count: 1090,
  sentence_count: 45,
  paragraph_count: 26,
  avg_paragraph_length: 42,
  reading_level: 12.3,
  self_contained_ratio: 0.85,
  h1_count: 1,
  h2_count: 5,
  h3_count: 8,
  h4_count: 2,
  list_count: 12,
  ordered_list_count: 3,
  table_count: 1,
  code_block_count: 0,
  has_faq_section: true,
  has_definition_opening: false,
  has_key_takeaways: true,
  has_comparison_table: false,
  has_step_by_step: true,
  has_research_refs: false,
  has_expert_quotes: false,
  data_point_count: 3,
  citation_density: 0.42,
  named_entity_density: 0.18,
};

const sampleSignals2: StructuralSignals = {
  word_count: 1540,
  sentence_count: 62,
  paragraph_count: 30,
  avg_paragraph_length: 51,
  reading_level: 10.8,
  self_contained_ratio: 0.78,
  h1_count: 1,
  h2_count: 7,
  h3_count: 4,
  h4_count: 0,
  list_count: 8,
  ordered_list_count: 5,
  table_count: 2,
  code_block_count: 1,
  has_faq_section: false,
  has_definition_opening: true,
  has_key_takeaways: false,
  has_comparison_table: true,
  has_step_by_step: false,
  has_research_refs: true,
  has_expert_quotes: true,
  data_point_count: 7,
  citation_density: 0.56,
  named_entity_density: 0.24,
};

export const SAMPLE_EXEMPLARS: CitationExemplar[] = [
  {
    similarity: 0.89,
    domain: 'webflow.com',
    url: 'https://webflow.com/blog/no-code-website-builders',
    snippet: 'No-code website builders enable businesses to create professional sites without writing code. Webflow stands out with its visual development approach...',
    structural_signals: sampleSignals,
    authority_type: 'official',
    content_type: 'blog',
  },
  {
    similarity: 0.82,
    domain: 'g2.com',
    url: 'https://g2.com/products/webflow/reviews',
    snippet: 'Webflow is a visual web development platform that allows designers and developers to build responsive websites. It combines the power of code...',
    structural_signals: sampleSignals2,
    authority_type: 'reviewer',
    content_type: 'review',
  },
  {
    similarity: 0.78,
    domain: 'zapier.com',
    url: 'https://zapier.com/blog/best-website-builders',
    snippet: 'The best website builders for 2024 include Webflow for design-focused teams, Squarespace for simplicity, and WordPress for flexibility...',
    structural_signals: { ...sampleSignals, word_count: 2100, has_comparison_table: true, table_count: 3 },
    authority_type: 'industry_expert',
    content_type: 'listicle',
  },
  {
    similarity: 0.75,
    domain: 'hubspot.com',
    url: 'https://blog.hubspot.com/website/website-builder-comparison',
    snippet: 'When choosing a website builder, consider factors like design flexibility, SEO capabilities, and ease of use. Enterprise teams often prefer...',
    structural_signals: { ...sampleSignals2, word_count: 1890, has_faq_section: true },
    authority_type: 'thought_leader',
    content_type: 'guide',
  },
  {
    similarity: 0.71,
    domain: 'techradar.com',
    url: 'https://techradar.com/best/website-builders',
    snippet: 'Our expert review of the top website builders evaluated pricing, features, and performance. Webflow earned high marks for its visual editor...',
    structural_signals: { ...sampleSignals, word_count: 1650, reading_level: 11.2 },
    authority_type: 'analyst',
    content_type: 'review',
  },
];

export const SAMPLE_GAP_BRIEFS: GapBrief[] = [
  {
    query_id: 'q1',
    query_text: 'How does Webflow compare to WordPress for enterprise websites?',
    cluster: 'Category Comparison',
    cluster_id: 'C3',
    gap_score: 0.85,
    gap_classification: 'significant_gap',
    best_company_unit: { unit_id: 'u1', similarity: 0.42, snippet: 'Webflow is a visual web development platform...' },
    avg_citation_similarity: 0.78,
    content_brief: {
      target_word_count: { min: 1600, max: 2200 },
      target_reading_level: { min: 10, max: 13 },
      recommended_header_count: 8,
      header_hierarchy: { h1: 1, h2: 5, h3: 8 },
      content_patterns: ['comparison_table', 'key_takeaways', 'faq'],
      dominant_authority: 'industry_expert',
      dominant_content_type: 'comparison',
      exemplars_analyzed: 12,
    },
    top_exemplars: SAMPLE_EXEMPLARS.slice(0, 3),
  },
  {
    query_id: 'q2',
    query_text: 'What is no-code web development and who should use it?',
    cluster: 'Definition',
    cluster_id: 'C5',
    gap_score: 0.72,
    gap_classification: 'gap_to_close',
    best_company_unit: { unit_id: 'u2', similarity: 0.55, snippet: 'No-code development eliminates the need for traditional programming...' },
    avg_citation_similarity: 0.68,
    content_brief: {
      target_word_count: { min: 1200, max: 1800 },
      target_reading_level: { min: 9, max: 12 },
      recommended_header_count: 6,
      header_hierarchy: { h1: 1, h2: 4, h3: 5 },
      content_patterns: ['definition_opening', 'lists', 'step_by_step'],
      dominant_authority: 'documentation',
      dominant_content_type: 'explainer',
      exemplars_analyzed: 10,
    },
    top_exemplars: SAMPLE_EXEMPLARS.slice(1, 4),
  },
  {
    query_id: 'q3',
    query_text: 'Best website builders for design agencies in 2024',
    cluster: 'Best-of/Consideration',
    cluster_id: 'C7',
    gap_score: 0.68,
    gap_classification: 'gap_to_close',
    best_company_unit: { unit_id: 'u3', similarity: 0.58, snippet: 'Design agencies need tools that support creative freedom...' },
    avg_citation_similarity: 0.72,
    content_brief: {
      target_word_count: { min: 1400, max: 2000 },
      target_reading_level: { min: 10, max: 12 },
      recommended_header_count: 7,
      header_hierarchy: { h1: 1, h2: 6, h3: 4 },
      content_patterns: ['comparison_table', 'lists', 'faq'],
      dominant_authority: 'reviewer',
      dominant_content_type: 'listicle',
      exemplars_analyzed: 14,
    },
    top_exemplars: SAMPLE_EXEMPLARS.slice(2, 5),
  },
  {
    query_id: 'q4',
    query_text: 'How to evaluate website builder performance and SEO',
    cluster: 'Decision Criteria',
    cluster_id: 'C4',
    gap_score: 0.61,
    gap_classification: 'gap_to_close',
    best_company_unit: { unit_id: 'u4', similarity: 0.62, snippet: 'Website performance depends on hosting, code optimization...' },
    avg_citation_similarity: 0.65,
    content_brief: {
      target_word_count: { min: 1800, max: 2500 },
      target_reading_level: { min: 11, max: 14 },
      recommended_header_count: 9,
      header_hierarchy: { h1: 1, h2: 6, h3: 8 },
      content_patterns: ['key_takeaways', 'stats', 'step_by_step'],
      dominant_authority: 'industry_expert',
      dominant_content_type: 'guide',
      exemplars_analyzed: 11,
    },
    top_exemplars: SAMPLE_EXEMPLARS.slice(0, 3),
  },
  {
    query_id: 'q5',
    query_text: 'Webflow review: pros, cons, and pricing analysis',
    cluster: 'Branded Evaluation',
    cluster_id: 'C8',
    gap_score: 0.55,
    gap_classification: 'roughly_equal',
    best_company_unit: { unit_id: 'u5', similarity: 0.70, snippet: 'Webflow pricing starts at $14/month for basic sites...' },
    avg_citation_similarity: 0.68,
    content_brief: {
      target_word_count: { min: 1600, max: 2200 },
      target_reading_level: { min: 10, max: 13 },
      recommended_header_count: 8,
      header_hierarchy: { h1: 1, h2: 5, h3: 6 },
      content_patterns: ['comparison_table', 'faq', 'stats'],
      dominant_authority: 'analyst',
      dominant_content_type: 'review',
      exemplars_analyzed: 13,
    },
    top_exemplars: SAMPLE_EXEMPLARS.slice(1, 4),
  },
];

export interface EmbeddingPoint {
  x: number;
  y: number;
  type: 'query' | 'citation' | 'company';
  id: string;
  label: string;
  cluster: string;
  clusterId: string;
  similarity?: number;
  gapScore?: number;
}

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function generateClusterPoints(
  clusterId: string,
  clusterName: string,
  centerX: number,
  centerY: number,
  seed: number,
): EmbeddingPoint[] {
  const rand = seededRandom(seed);
  const points: EmbeddingPoint[] = [];

  for (let i = 0; i < 8; i++) {
    points.push({
      x: centerX + (rand() - 0.5) * 3,
      y: centerY + (rand() - 0.5) * 3,
      type: 'query',
      id: `${clusterId}-q${i}`,
      label: `Query ${i + 1} for ${clusterName}`,
      cluster: clusterName,
      clusterId,
      gapScore: 0.3 + rand() * 0.6,
    });
  }

  for (let i = 0; i < 12; i++) {
    points.push({
      x: centerX + (rand() - 0.5) * 5,
      y: centerY + (rand() - 0.5) * 5,
      type: 'citation',
      id: `${clusterId}-c${i}`,
      label: `Citation ${i + 1} from ${clusterName} cluster`,
      cluster: clusterName,
      clusterId,
      similarity: 0.4 + rand() * 0.5,
    });
  }

  for (let i = 0; i < 4; i++) {
    points.push({
      x: centerX + (rand() - 0.5) * 4 + 1,
      y: centerY + (rand() - 0.5) * 4 + 0.5,
      type: 'company',
      id: `${clusterId}-co${i}`,
      label: `Company content ${i + 1} near ${clusterName}`,
      cluster: clusterName,
      clusterId,
      similarity: 0.5 + rand() * 0.4,
    });
  }

  return points;
}

const clusterCenters: Array<[number, number]> = [
  [-8, 6], [-3, 8], [4, 7],
  [-7, 0], [0, 0], [7, 1],
  [-6, -6], [1, -7], [8, -5],
];

export const SAMPLE_EMBEDDING_POINTS: EmbeddingPoint[] = SAMPLE_CLUSTERS.flatMap((cluster, i) =>
  generateClusterPoints(
    cluster.cluster_id,
    cluster.cluster_name,
    clusterCenters[i][0],
    clusterCenters[i][1],
    (i + 1) * 42,
  ),
);

export interface PlatformData {
  platform: string;
  totalCitations: number;
  uniqueCitations: number;
  avgSimilarity: number;
  topDomain: string;
}

export const SAMPLE_PLATFORM_DATA: PlatformData[] = [
  { platform: 'ChatGPT', totalCitations: 142, uniqueCitations: 98, avgSimilarity: 0.72, topDomain: 'hubspot.com' },
  { platform: 'Claude', totalCitations: 128, uniqueCitations: 85, avgSimilarity: 0.75, topDomain: 'zapier.com' },
  { platform: 'Perplexity', totalCitations: 156, uniqueCitations: 112, avgSimilarity: 0.69, topDomain: 'g2.com' },
  { platform: 'Gemini', totalCitations: 118, uniqueCitations: 78, avgSimilarity: 0.71, topDomain: 'techradar.com' },
];

export interface DomainCitation {
  domain: string;
  count: number;
  avgSimilarity: number;
  authorityType: string;
}

export const SAMPLE_DOMAIN_CITATIONS: DomainCitation[] = [
  { domain: 'hubspot.com', count: 28, avgSimilarity: 0.74, authorityType: 'thought_leader' },
  { domain: 'g2.com', count: 24, avgSimilarity: 0.71, authorityType: 'reviewer' },
  { domain: 'zapier.com', count: 22, avgSimilarity: 0.76, authorityType: 'industry_expert' },
  { domain: 'webflow.com', count: 18, avgSimilarity: 0.82, authorityType: 'official' },
  { domain: 'techradar.com', count: 16, avgSimilarity: 0.68, authorityType: 'analyst' },
  { domain: 'capterra.com', count: 14, avgSimilarity: 0.65, authorityType: 'reviewer' },
  { domain: 'wordpress.org', count: 12, avgSimilarity: 0.63, authorityType: 'official' },
  { domain: 'smashingmagazine.com', count: 10, avgSimilarity: 0.70, authorityType: 'thought_leader' },
  { domain: 'css-tricks.com', count: 8, avgSimilarity: 0.72, authorityType: 'thought_leader' },
  { domain: 'wix.com', count: 7, avgSimilarity: 0.60, authorityType: 'official' },
  { domain: 'squarespace.com', count: 6, avgSimilarity: 0.58, authorityType: 'official' },
  { domain: 'ahrefs.com', count: 5, avgSimilarity: 0.73, authorityType: 'industry_expert' },
];

export const SAMPLE_HEATMAP_DATA = SAMPLE_CLUSTERS.flatMap((cluster) =>
  SAMPLE_GAP_BRIEFS.map((brief) => ({
    query_id: brief.query_id,
    query_text: brief.query_text,
    cluster: cluster.cluster_name,
    cluster_id: cluster.cluster_id,
    gap_score: brief.cluster_id === cluster.cluster_id
      ? brief.gap_score
      : Math.max(0, brief.gap_score - 0.1 + Math.random() * 0.2),
    classification: brief.gap_classification,
  })),
);

export const SAMPLE_SIMILARITY_DATA = [
  { range: '0.0-0.1', count: 2 },
  { range: '0.1-0.2', count: 5 },
  { range: '0.2-0.3', count: 12 },
  { range: '0.3-0.4', count: 28 },
  { range: '0.4-0.5', count: 45 },
  { range: '0.5-0.6', count: 62 },
  { range: '0.6-0.7', count: 78 },
  { range: '0.7-0.8', count: 56 },
  { range: '0.8-0.9', count: 32 },
  { range: '0.9-1.0', count: 14 },
];

export const SAMPLE_COMPANY_VS_CITATION = SAMPLE_CLUSTERS.map((c) => ({
  cluster: c.cluster_name,
  clusterId: c.cluster_id,
  companySimilarity: 0.45 + Math.random() * 0.25,
  citationSimilarity: 0.60 + Math.random() * 0.25,
}));
