export interface GapAnalysisStartInput {
  input_data: {
    company_name: string;
    domain: string;
    seed_urls: string[];
    company_slug?: string;
  };
  skip_steps?: number[];
}

export interface GapBrief {
  query_id: string;
  query_text: string;
  cluster: string;
  cluster_id: string;
  gap_score: number;
  gap_classification: 'significant_gap' | 'gap_to_close' | 'roughly_equal' | 'company_wins';
  best_company_unit: {
    unit_id: string;
    similarity: number;
    snippet: string;
  };
  avg_citation_similarity: number;
  content_brief: ContentBrief;
  top_exemplars: CitationExemplar[];
}

export interface ContentBrief {
  target_word_count: { min: number; max: number };
  target_reading_level: { min: number; max: number };
  recommended_header_count: number;
  header_hierarchy: Record<string, number>;
  content_patterns: string[];
  dominant_authority: string;
  dominant_content_type: string;
  exemplars_analyzed: number;
}

export interface CitationExemplar {
  similarity: number;
  domain: string;
  url: string;
  snippet: string;
  structural_signals: StructuralSignals;
  authority_type: string;
  content_type: string;
}

export interface StructuralSignals {
  // Category A: Text Composition
  word_count: number;
  sentence_count: number;
  paragraph_count: number;
  avg_paragraph_length: number;
  reading_level: number;
  self_contained_ratio: number;
  // Category B: Structural Elements
  h1_count: number;
  h2_count: number;
  h3_count: number;
  h4_count: number;
  list_count: number;
  ordered_list_count: number;
  table_count: number;
  code_block_count: number;
  // Category C: Content Patterns
  has_faq_section: boolean;
  has_definition_opening: boolean;
  has_key_takeaways: boolean;
  has_comparison_table: boolean;
  has_step_by_step: boolean;
  has_research_refs: boolean;
  has_expert_quotes: boolean;
  // Category D: Factual Density
  data_point_count: number;
  citation_density: number;
  named_entity_density: number;
}

export interface ClusterSpec {
  cluster_id: string;
  cluster_name: string;
  query_count: number;
  citations_analyzed: number;
  centroid_distance: number;
  min_similarity_threshold: number;
  word_count_range: { min: number; max: number };
  required_elements: string[];
  structural_rates: {
    headers: number;
    lists: number;
    stats: number;
    citations: number;
  };
  avg_word_count: number;
  faq_rate: number;
  table_rate: number;
  key_takeaways_rate: number;
  dominant_content_type: string;
  dominant_authority_type: string;
  exemplar_themes: string[];
}

export interface GapReport {
  executive_summary: string;
  spa_score: {
    t_statistic: number;
    p_value: number;
    citation_advantage: number;
    company_advantage: number;
  };
  clusters: ClusterSpec[];
  top_gaps: GapBrief[];
  total_queries: number;
  total_citations: number;
}

export type GapAnalysisStep =
  | 's1_embed_assets' | 's2_generate_queries' | 's3_search_platforms'
  | 's4_enrich_citations' | 's5_embed_content' | 's6_analyze'
  | 's7_visualize' | 's8_generate_report';

export const GAP_ANALYSIS_STEPS: { key: GapAnalysisStep; label: string; description: string }[] = [
  { key: 's1_embed_assets', label: 'Embed Assets', description: 'Crawling and embedding company content' },
  { key: 's2_generate_queries', label: 'Generate Queries', description: 'Creating 150 buyer-intent queries across 9 clusters' },
  { key: 's3_search_platforms', label: 'Search AI Platforms', description: 'Querying ChatGPT, Claude, Perplexity, Gemini' },
  { key: 's4_enrich_citations', label: 'Enrich Citations', description: 'Extracting 45 structural signals from each citation' },
  { key: 's5_embed_content', label: 'Embed Content', description: 'Embedding queries and citations for comparison' },
  { key: 's6_analyze', label: 'Analyze Gaps', description: 'Computing semantic proximity and gap scores' },
  { key: 's7_visualize', label: 'Visualize', description: 'Generating interactive visualizations' },
  { key: 's8_generate_report', label: 'Generate Report', description: 'Producing gap report and generation specs' },
] as const;
