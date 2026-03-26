/**
 * API response types — TypeScript mirrors of backend Pydantic schemas.
 *
 * Field names are snake_case to match JSON responses exactly.
 * Use transform functions in transforms.ts to convert to frontend types.
 */

// ── Gap Analysis ──────────────────────────────────────────────────────

export interface SPAScore {
  t_stat: number;
  p_value: number;
  effect: string;
  mean_citation_similarity: number;
  mean_company_similarity: number;
  median_citation_similarity: number;
  median_company_similarity: number;
}

export interface ProximityStats {
  citation_similarity_mean: number;
  citation_similarity_median: number;
  company_similarity_mean: number;
  company_similarity_median: number;
}

export interface GapClassificationCounts {
  significant_gap: number;
  gap_to_close: number;
  roughly_equal: number;
  company_wins: number;
}

export interface ClusterPerformanceRow {
  cluster_id: string | null;
  cluster_name: string;
  query_count: number;
  citation_count: number;
  avg_gap: number;
  avg_citation_sim: number;
  avg_company_sim: number;
  structural_rates: Record<string, number>;
}

export interface Recommendation {
  title_idea: string;
  target_cluster: string;
  structural_signals: string;
  expected_impact: string;
}

export interface GapSummaryResponse {
  spa_score: SPAScore;
  proximity_stats: ProximityStats;
  classification_counts: GapClassificationCounts;
  cluster_performance: ClusterPerformanceRow[];
  total_queries: number;
  total_citations: number;
  company_cited_count: number;
  average_gap: number;
  executive_summary: string;
  recommendations: Recommendation[];
}

export interface QueryContentBrief {
  target_word_count: { min: number; max: number };
  target_reading_level: { min: number; max: number };
  recommended_header_count: number;
  header_hierarchy: Record<string, number>;
  content_patterns: string[];
  dominant_authority: string | null;
  dominant_content_type: string | null;
  exemplars_analyzed: number;
}

export interface QueryExemplar {
  similarity: number;
  domain: string | null;
  url: string;
  snippet: string | null;
  authority_type: string | null;
  content_type: string | null;
}

export interface QueryRow {
  query_id: string;
  query_text: string;
  cluster_id: string | null;
  cluster_name: string | null;
  gap_score: number;
  classification: string;
  company_sim: number;
  citation_sim: number;
  target_words: { min: number; max: number };
  reading_level: { min: number; max: number };
  headers: number;
  patterns: string[];
  top_domain: string | null;
  top_exemplar_sim: number;
  platform_citations: Record<string, number>;
  company_cited: boolean;
  company_cited_platforms: string[];
  content_brief: QueryContentBrief | null;
  top_exemplars: QueryExemplar[];
}

export interface QueryListResponse {
  queries: QueryRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ClusterSpecResponse {
  cluster_id: string | null;
  cluster_name: string;
  query_count: number;
  citations_analyzed: number;
  centroid_distance: number | null;
  min_similarity_threshold: number | null;
  word_count_range: { min: number; max: number };
  required_elements: string[];
  structural_rates: Record<string, number>;
  avg_word_count: number;
  faq_rate: number;
  table_rate: number;
  key_takeaways_rate: number;
  dominant_content_type: string | null;
  dominant_authority_type: string | null;
  exemplar_themes: string[];
}

export interface ClusterListResponse {
  clusters: ClusterSpecResponse[];
}

export interface SignalAverageRow {
  signal: string;
  category: string;
  citation_avg: number;
  company_avg: number;
  unit: string;
  recommendation: string;
}

export interface SignalCorrelationRow {
  signal: string;
  correlation: number;
  category: string;
}

export interface ClusterPatternRow {
  cluster_id: string;
  cluster_name: string;
  faq: number;
  definition_opening: number;
  key_takeaways: number;
  comparison_table: number;
  step_by_step: number;
  research_refs: number;
  expert_quotes: number;
}

export interface SignalAveragesResponse {
  signals: SignalAverageRow[];
  correlations: SignalCorrelationRow[];
  cluster_patterns: ClusterPatternRow[];
  cluster_fingerprints: Record<string, Record<string, number>>;
}

export interface PlatformSummaryResponse {
  name: string;
  total_citations: number;
  unique_domains: number;
  avg_citation_sim: number;
  most_cited_domain: string | null;
  best_cluster: string | null;
  worst_cluster: string | null;
  per_cluster: Record<string, number>;
}

export interface PlatformListResponse {
  platforms: PlatformSummaryResponse[];
  agreement: Record<string, Record<string, number>>;
  citation_exclusivity: Record<string, Record<string, number>>;
}

export interface HeatmapQuery {
  query_id: string;
  query_text: string;
  gap_score: number;
  classification: string;
}

export interface HeatmapCluster {
  cluster_name: string;
  cluster_id: string | null;
  queries: HeatmapQuery[];
  avg_gap: number;
}

export interface HeatmapResponse {
  clusters: HeatmapCluster[];
  min_gap: number;
  max_gap: number;
}

// ── Site Audit ────────────────────────────────────────────────────────

export interface DimensionScoreResponse {
  dimension: string;
  score: number;
  weight: number;
  weighted_score: number;
  finding_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
}

export interface AIBotAccessResponse {
  gptbot_allowed: boolean;
  claudebot_allowed: boolean;
  perplexitybot_allowed: boolean;
  google_extended_allowed: boolean;
  ccbot_allowed: boolean;
  has_llms_txt: boolean;
  robots_txt_exists: boolean;
}

export interface SitemapHealthResponse {
  has_sitemap: boolean;
  sitemap_url_count: number;
  sitemap_urls: string[];
  sitemap_errors: string[];
  has_sitemap_index: boolean;
}

export interface AuditSummaryResponse {
  audit_id: string;
  domain: string;
  overall_score: number;
  grade: string;
  pages_crawled: number;
  total_findings: number;
  status: string;
  started_at: string;
  completed_at: string;
}

export interface AuditDetailResponse {
  audit_id: string;
  domain: string;
  overall_score: number;
  grade: string;
  pages_crawled: number;
  pages_discovered: number;
  duration_seconds: number;
  dimension_scores: DimensionScoreResponse[];
  ai_bot_access: AIBotAccessResponse;
  sitemap_health: SitemapHealthResponse;
  total_findings: number;
  findings_by_severity: Record<string, number>;
  findings_by_dimension: Record<string, number>;
  avg_snippet_readiness: number;
  pages_with_schema: number;
  avg_question_heading_ratio: number;
  status: string;
  error_message: string | null;
  started_at: string;
  completed_at: string;
}

// ── Content v1.3 ──────────────────────────────────────────────────────

export interface GapContextSummary {
  gap_score: number;
  classification: string;
  company_similarity: number;
  citation_similarity: number;
  company_cited: boolean;
  company_best_url: string;
  why_picked: string[];
  success_indicators: { label: string; value: string; sub: string }[];
  exemplars: { url: string; domain: string; similarity: number; word_count: number; authority_type: string }[];
}

export interface ContentBriefItem {
  id: string;
  title: string;
  status: string;
  content_type: string;
  cluster: string;
  target_word_count: number;
  citability_score: number | null;
  cycle_id: string | null;
  task_id: string | null;
  created_at: string;
  updated_at: string;
  gap_context: GapContextSummary | null;
  published_url: string;
  published_at: string | null;
}

export interface ContentBriefListResponse {
  briefs: ContentBriefItem[];
  total: number;
}

export interface EvalDimension {
  dimension: string;
  passed: boolean;
  score: number;
  feedback: string;
}

export interface EvalCycle {
  cycle: number;
  dimensions: EvalDimension[];
  overall_passed: boolean;
  overall_score: number;
}

export interface BriefExemplar {
  url: string;
  word_count: number;
  authority_type: string;
  content_type: string;
  snippet: string;
}

// ── SPA Trend ─────────────────────────────────────────────────────────

export interface SPATrendPoint {
  run_id: string;
  run: string;
  timestamp: string;
  spa_score: number;
  citation_advantage: number;
  company_advantage: number;
  total_queries: number;
  total_citations: number;
}

export interface SPATrendResponse {
  trend: SPATrendPoint[];
}

// ── Embedding Projections ─────────────────────────────────────────────

export interface EmbeddingPointResponse {
  x: number;
  y: number;
  type: string;
  id: string;
  label: string;
  cluster: string;
  cluster_id: string;
  query_id: string | null;
  similarity: number;
}

export interface EmbeddingProjectionResponse {
  method: string;
  point_count: number;
  points: EmbeddingPointResponse[];
}

export interface ContentBriefDetailResponse {
  id: string;
  title: string;
  status: string;
  content_type: string;
  cluster: string;
  target_word_count: { min: number; max: number };
  structural_targets: Record<string, unknown>;
  key_topics: string[];
  key_angles: string[];
  priority_score: number;
  citability_score: number | null;
  eval_history: EvalCycle[];
  final_passed: boolean;
  exemplars: BriefExemplar[];
  available_stages: string[];
}

export interface StageContentResponse {
  brief_id: string;
  stage: string;
  content_type: string;
  content: string | Record<string, unknown>;
}

export interface TopicContentStatusItem {
  topic_assignment_id: string;
  topic_text: string;
  status: string;
  content_piece_id: string | null;
  content_title: string | null;
}

export interface TopicContentStatusResponse {
  effective_slug: string;
  total_assignments: number;
  items: TopicContentStatusItem[];
}

// ── Topic Discovery ───────────────────────────────────────────────────

export interface TaxonomyReadResponse {
  slug: string;
  taxonomy: Record<string, unknown>;
  version: number;
  total_subdomains: number;
  coverage_score: number;
}

export interface MatrixReadResponse {
  slug: string;
  matrix: Record<string, unknown>;
  version: number;
  total_assignments: number;
}

export interface ScoredSubdomainsResponse {
  slug: string;
  scored_subdomains: Record<string, unknown>;
  version: number;
  total_scored: number;
  signals_used: string[];
}

export interface PersonaAffinityResponse {
  slug: string;
  persona_entries: Record<string, unknown>;
  total_personas: number;
  total_subdomains: number;
}

export interface ExpansionStatusResponse {
  slug: string;
  effective_slug: string;
  total_subdomains: number;
  expanded: number;
  not_expanded: number;
  expanded_ids: string[];
  available_for_expansion: Record<string, unknown>[];
}

// ── Settings ──────────────────────────────────────────────────────────

export interface TeamMemberResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface TeamListResponse {
  members: TeamMemberResponse[];
  total: number;
}

export interface CompanyProfileSettingsResponse {
  slug: string;
  name: string;
  domain: string;
  additional_domains: string[];
  industry: string | null;
  created_at: string;
  updated_at: string;
}

export interface PipelineDefaultsResponse {
  max_crawl_pages: number | null;
  max_crawl_depth: number | null;
  max_queries: number | null;
  platforms: string[] | null;
  max_personas: number | null;
  auto_approve_research: boolean;
  max_briefs: number | null;
  max_revision_cycles: number | null;
  auto_approve_content: boolean;
  updated_at: string | null;
}

// ── CMS Integration ──────────────────────────────────────────────────

export interface CMSConnectPayload {
  provider: string;
  site_url: string;
  username: string;
  api_key: string;
}

export interface CMSConnectResponse {
  connected: boolean;
  site_name: string;
  site_url: string;
  cms_version: string;
  user_display_name: string;
  error: string | null;
}

export interface CMSConnectionInfo {
  provider: string;
  site_url: string;
  site_name: string;
  cms_version: string;
  user_display_name: string;
  is_active: boolean;
  last_sync_at: string | null;
  sync_post_count: number;
}

export interface CMSPublishPayload {
  brief_id: string;
  effective_slug?: string;
  product_slug?: string;
  status: 'draft' | 'publish';
  slug_override?: string;
  categories: string[];
}

export interface CMSRefreshPayload {
  brief_id: string;
  effective_slug?: string;
  product_slug?: string;
}

export interface CMSStaleToTriagePayload {
  cms_synced_post_id: string;
}

export interface CMSPublishResponse {
  cms_post_id: string;
  url: string;
  slug: string;
  title: string;
  status: string;
  word_count: number;
}

export interface CMSSyncedPostSummary {
  id: string;
  cms_post_id: string;
  title: string;
  slug: string;
  url: string;
  word_count: number;
  published_at: string | null;
  modified_at: string | null;
  is_stale: boolean;
  staleness_days: number;
  categories: string[];
  queued_for_refresh: boolean;
}

export interface StaleContentAction {
  cms_synced_post_id: string;
  cms_post_id: string;
  title: string;
  url: string;
  staleness_days: number;
  description: string;
  queued_for_refresh: boolean;
}

export interface StaleToTriageResponse {
  brief_id: string;
  title: string;
  status: string;
  warning: string;
}

export interface CMSCategoryItem {
  cms_id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  post_count: number;
}

export interface CMSPublishHistoryItem {
  id: string;
  brief_id: string;
  effective_slug: string;
  cms_post_id: string;
  cms_post_url: string;
  cms_post_slug: string;
  action: string;
  status_at_publish: string;
  published_at: string | null;
  title_published: string;
  word_count: number;
}

export interface CMSSyncTriggerResponse {
  run_id: string;
  pipeline: string;
  status: string;
  company_slug: string;
}
