/**
 * API response types for Embedding Lab — mirrors backend Pydantic schemas (snake_case).
 */

// ── Cluster Profiles ─────────────────────────────────────────

export interface ClusterDomainEntryAPI {
  domain: string;
  citations: number;
  is_company: boolean;
  share: number;
  type: string;
}

export interface ClusterProfileAPI {
  cluster_id: string;
  cluster_name: string;
  query_count: number;
  total_citations: number;
  unique_domains: number;
  company_citations: number;
  company_share: number;
  company_rank: number | null;
  presence: string;
  avg_word_count: number;
  word_count_range: [number, number];
  dominant_content_type: string | null;
  dominant_authority_type: string | null;
  structural_rates: Record<string, number>;
  faq_rate: number;
  table_rate: number;
  required_elements: string[];
  exemplar_themes: string[];
  authority_signals: Record<string, number>;
  proximity: { mean: number; std: number; count: number } | null;
  engine_breakdown: Record<string, number>;
  top_domains: ClusterDomainEntryAPI[];
}

export interface ClusterProfileListAPI {
  profiles: Record<string, ClusterProfileAPI>;
}

// ── Territory Gaps ───────────────────────────────────────────

export interface TerritoryGapExemplarAPI {
  domain: string;
  url: string;
  similarity: number;
  content_type: string | null;
  authority_type: string | null;
  word_count: number | null;
  header_count: number | null;
  has_faq: boolean;
  has_tables: boolean;
  reading_level: number | null;
  list_item_count: number;
  stat_count: number;
  citation_count: number;
}

export interface TerritoryCompanySignalsAPI {
  word_count: number | null;
  header_count: number | null;
  has_faq: boolean;
  has_tables: boolean;
  reading_level: number | null;
  list_item_count: number;
}

export interface TerritoryContentBriefAPI {
  word_count_range: [number, number] | null;
  reading_level_range: [number, number] | null;
  header_count_range: [number, number] | null;
  header_hierarchy: Record<string, number> | null;
  has_faq: number;
  has_tables: number;
  has_definition: number;
  has_key_takeaways: number;
  has_step_by_step: number;
  dominant_content_type: string | null;
  dominant_authority_type: string | null;
  data_density: number | null;
  citation_density: number | null;
}

export interface TerritoryGapQueryAPI {
  id: string;
  query: string;
  cluster: string;
  cluster_id: string;
  gap: number;
  classification: string;
  company_cited: boolean;
  company_url: string | null;
  company_similarity: number | null;
  avg_citation_similarity: number;
  exemplars: TerritoryGapExemplarAPI[];
  company_signals: TerritoryCompanySignalsAPI | null;
  content_brief: TerritoryContentBriefAPI | null;
}

export interface TerritoryProximityStatsAPI {
  citation_mean: number;
  citation_median: number;
  company_mean: number;
  company_median: number;
  similarity_gap: number;
}

export interface TerritorySPAAPI {
  t_stat: number;
  p_value: number;
  effect: string;
}

export interface TerritoryGapsResponseAPI {
  gaps: TerritoryGapQueryAPI[];
  proximity_stats: TerritoryProximityStatsAPI;
  spa: TerritorySPAAPI;
  per_cluster_proximity: Record<string, { mean: number; std: number; min: number; max: number; count: number }>;
  total_gaps: number;
  uncovered_queries: number;
}

// ── Embedding Projections ────────────────────────────────────

export interface EmbeddingPointAPI {
  id: string;
  x: number;
  y: number;
  type: string;
  label: string;
  cluster: string;
  cluster_id: string;
  query_id: string | null;
  similarity: number | null;
  gap_score: number | null;
}

export interface EmbeddingProjectionAPI {
  method: string;
  point_count: number;
  points: EmbeddingPointAPI[];
}
