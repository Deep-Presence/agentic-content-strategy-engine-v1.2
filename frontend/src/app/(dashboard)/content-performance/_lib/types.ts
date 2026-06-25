/**
 * Content Performance API response types + signal definitions.
 * Mirrors backend schemas: api/schemas/content_performance.py, api/schemas/gap_data.py
 */

// ── Content Detail (from /content-performance/{id}) ────

export interface DailyTrafficPoint {
  date: string;
  sessions: number;
  pageviews: number;
  ai_sessions: number;
}

export interface SourceBreakdownItem {
  channel: string;
  sessions: number;
  percentage: number;
}

export interface AIPlatformBreakdownItem {
  platform: string;
  sessions: number;
}

export interface CitationTimelinePoint {
  date: string;
  cited: number;
  total_responses: number;
}

export interface FreshnessAssessmentAPI {
  content_age_days: number | null;
  last_updated_age_days: number | null;
  cited_exemplar_avg_age_days: number | null;
  cited_exemplar_median_age_days: number | null;
  benchmark_sample_size: number;
  freshness_delta_days: number | null;
  freshness_score: number | null;
  freshness_status: string;
  freshness_reason: string;
}

export interface ContentDetailAPI {
  inventory_id: string;
  url: string;
  title: string;
  published_at: string | null;
  traffic: number;
  ai_referrals: number;
  velocity: number;
  velocity_trend: string;
  freshness_days: number;
  lifecycle: string;
  daily_traffic: DailyTrafficPoint[];
  source_breakdown: SourceBreakdownItem[];
  ai_platform_breakdown: AIPlatformBreakdownItem[];
  structural_signals: Record<string, number | boolean | string | null> | null;
  structural_score: number;
  citation_timeline?: CitationTimelinePoint[];
  citations?: number;
  freshness: FreshnessAssessmentAPI;
  platforms?: Record<string, boolean>;
  queries_covered?: number;
}

// ── Signal Averages (from /gap-analysis/signals) ───────

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

export interface SignalAveragesAPI {
  signals: SignalAverageRow[];
  correlations: SignalCorrelationRow[];
}

// ── Content Performance Table (from /content-performance) ─────

export interface ContentPerformanceRowAPI {
  inventory_id: string;
  url: string;
  title: string;
  traffic: number;
  ai_referrals: number;
  velocity: number;
  velocity_trend: string;
  freshness_days: number;
  lifecycle: string;
  content_type: string;
  word_count: number;
  published_at: string | null;
  structural_score: number;
  citations?: number;
  platforms?: Record<string, boolean>;
  queries_covered?: number;
}

export interface ContentPerformanceTableResponseAPI {
  items: ContentPerformanceRowAPI[];
  period_start: string;
  period_end: string;
  total_items: number;
}

export interface PathMatchSampleItemAPI {
  path: string;
  sessions: number;
}

export interface ContentPerformanceReadinessAPI {
  state: string;
  message: string;
  connection_active: boolean;
  has_selected_property: boolean;
  last_sync_at: string | null;
  last_sync_status: string;
  last_sync_error: string;
  inventory_pages: number;
  ga4_rows_total: number;
  ga4_rows_in_window: number;
  matched_inventory_pages: number;
  matched_inventory_pages_in_window: number;
  unmatched_ga4_paths_total: number;
  unmatched_ga4_paths_in_window: number;
  inventory_paths_sample: string[];
  unmatched_ga4_paths_sample: PathMatchSampleItemAPI[];
}

// ── Velocity Insights (from /content-performance/insights/velocity) ──

export interface VelocityInsightAPI {
  inventory_id: string;
  url: string;
  title: string;
  velocity: number;
  velocity_trend: string;
  lifecycle: string;
  traffic: number;
}

export interface VelocityInsightsResponseAPI {
  items: VelocityInsightAPI[];
  period_start: string;
  period_end: string;
}

// ── Signal Definitions (mirrors _SIGNAL_DEFS in gap_data_service.py) ──

export interface SignalDef {
  field: string;
  name: string;
  category: string;
  unit: string;
  isBool: boolean;
}

/**
 * 24 signal definitions matching api/services/gap_data_service.py:240-268.
 * Stable semantic constants — safe to mirror on frontend.
 */
export const SIGNAL_DEFS: SignalDef[] = [
  // Text Composition
  { field: 'word_count', name: 'Word Count', category: 'Text Composition', unit: 'words', isBool: false },
  { field: 'sentence_count', name: 'Sentence Count', category: 'Text Composition', unit: 'count', isBool: false },
  { field: 'paragraph_count', name: 'Paragraph Count', category: 'Text Composition', unit: 'count', isBool: false },
  { field: 'avg_paragraph_length', name: 'Avg Paragraph Length', category: 'Text Composition', unit: 'words', isBool: false },
  { field: 'reading_level', name: 'Reading Level', category: 'Text Composition', unit: 'grade level', isBool: false },
  { field: 'self_contained_ratio', name: 'Self-Contained Ratio', category: 'Text Composition', unit: '%', isBool: false },
  // Structural Elements
  { field: 'h1_count', name: 'H1 Count', category: 'Structural Elements', unit: 'count', isBool: false },
  { field: 'h2_count', name: 'H2 Count', category: 'Structural Elements', unit: 'count', isBool: false },
  { field: 'h3_count', name: 'H3 Count', category: 'Structural Elements', unit: 'count', isBool: false },
  { field: 'h4_count', name: 'H4 Count', category: 'Structural Elements', unit: 'count', isBool: false },
  { field: 'list_block_count', name: 'List Count', category: 'Structural Elements', unit: 'count', isBool: false },
  { field: 'ordered_list_count', name: 'Ordered List Count', category: 'Structural Elements', unit: 'count', isBool: false },
  { field: 'table_count', name: 'Table Count', category: 'Structural Elements', unit: 'count', isBool: false },
  { field: 'code_block_count', name: 'Code Block Count', category: 'Structural Elements', unit: 'count', isBool: false },
  // Content Patterns (boolean signals — display as % rate)
  { field: 'has_faq_section', name: 'FAQ Section', category: 'Content Patterns', unit: '%', isBool: true },
  { field: 'has_definition_opening', name: 'Definition Opening', category: 'Content Patterns', unit: '%', isBool: true },
  { field: 'has_key_takeaways', name: 'Key Takeaways', category: 'Content Patterns', unit: '%', isBool: true },
  { field: 'has_comparison_table', name: 'Comparison Table', category: 'Content Patterns', unit: '%', isBool: true },
  { field: 'has_step_by_step', name: 'Step-by-Step', category: 'Content Patterns', unit: '%', isBool: true },
  { field: 'has_research_refs', name: 'Research References', category: 'Content Patterns', unit: '%', isBool: true },
  { field: 'has_expert_quotes', name: 'Expert Quotes', category: 'Content Patterns', unit: '%', isBool: true },
  // Factual Density
  { field: 'data_point_count', name: 'Data Point Count', category: 'Factual Density', unit: 'data points', isBool: false },
  { field: 'citation_density', name: 'Citation Density', category: 'Factual Density', unit: 'per word', isBool: false },
  { field: 'named_entity_density', name: 'Named Entity Density', category: 'Factual Density', unit: 'per word', isBool: false },
];

/** Map signal display name -> field key for JSONB lookups. */
export const SIGNAL_NAME_TO_FIELD: Record<string, string> = Object.fromEntries(
  SIGNAL_DEFS.map((d) => [d.name, d.field]),
);

/** Map field key -> SignalDef for reverse lookups. */
export const SIGNAL_FIELD_MAP: Record<string, SignalDef> = Object.fromEntries(
  SIGNAL_DEFS.map((d) => [d.field, d]),
);
