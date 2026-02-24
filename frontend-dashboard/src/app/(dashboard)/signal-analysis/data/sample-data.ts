// Deep Signal Analysis — Complete sample dataset for Webflow gap analysis
// 72 queries across 9 clusters, structural signals, platform data, run history

// ─── Types ───────────────────────────────────────────────────────────────────

export interface QueryData {
  id: string;
  text: string;
  cluster_id: string;
  cluster_name: string;
  gap_score: number;
  classification: 'significant_gap' | 'gap_to_close' | 'roughly_equal' | 'company_wins';
  company_sim: number;
  citation_sim: number;
  target_words: { min: number; max: number };
  reading_level: { min: number; max: number };
  headers: number;
  patterns: string[];
  top_domain: string;
  top_exemplar_sim: number;
  platform_citations: { chatgpt: number; claude: number; perplexity: number; gemini: number };
}

export interface SignalAverageRow {
  signal: string;
  category: 'Text Composition' | 'Structural Elements' | 'Content Patterns' | 'Factual Density';
  citation_avg: number;
  company_avg: number;
  unit: string;
  recommendation: string;
}

export interface PlatformSummary {
  name: string;
  total_citations: number;
  unique_domains: number;
  avg_citation_sim: number;
  most_cited_domain: string;
  best_cluster: string;
  worst_cluster: string;
  per_cluster: Record<string, number>;
}

export interface RunHistoryItem {
  id: string;
  company: string;
  company_slug: string;
  status: 'completed' | 'running' | 'failed';
  started: string;
  duration: string;
  queries: number;
  citations: number;
  spa_score: number;
  steps_completed: number;
}

export interface SignalCorrelation {
  signal: string;
  correlation: number;
  category: string;
}

export interface CalendarWeek {
  week: string;
  start: string;
  briefs: { query_id: string; query_text: string; cluster: string; gap_score: number }[];
}

export interface ClusterPatternRates {
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

// ─── 72 Queries (8 per cluster × 9 clusters) ────────────────────────────────

export const SAMPLE_QUERIES: QueryData[] = [
  // ── C1 Mechanism (8) ──
  { id: 'q_01', text: 'How does visual website development generate semantic HTML output?', cluster_id: 'C1', cluster_name: 'Mechanism', gap_score: 0.1803, classification: 'significant_gap', company_sim: 0.5210, citation_sim: 0.7013, target_words: { min: 1200, max: 2800 }, reading_level: { min: 11.5, max: 14.0 }, headers: 18, patterns: ['FAQ', 'Step-by-Step'], top_domain: 'hubspot.com', top_exemplar_sim: 0.7845, platform_citations: { chatgpt: 6, claude: 5, perplexity: 7, gemini: 4 } },
  { id: 'q_02', text: 'How do no-code builders handle responsive design patterns automatically?', cluster_id: 'C1', cluster_name: 'Mechanism', gap_score: 0.1688, classification: 'significant_gap', company_sim: 0.4920, citation_sim: 0.6608, target_words: { min: 1100, max: 2400 }, reading_level: { min: 12.0, max: 14.5 }, headers: 15, patterns: ['Step-by-Step'], top_domain: 'smashingmagazine.com', top_exemplar_sim: 0.7520, platform_citations: { chatgpt: 5, claude: 6, perplexity: 5, gemini: 5 } },
  { id: 'q_03', text: 'What technology powers modern drag-and-drop website editors?', cluster_id: 'C1', cluster_name: 'Mechanism', gap_score: 0.1524, classification: 'significant_gap', company_sim: 0.5080, citation_sim: 0.6604, target_words: { min: 900, max: 2100 }, reading_level: { min: 11.8, max: 13.5 }, headers: 12, patterns: ['FAQ'], top_domain: 'css-tricks.com', top_exemplar_sim: 0.7312, platform_citations: { chatgpt: 5, claude: 4, perplexity: 6, gemini: 5 } },
  { id: 'q_04', text: 'How do visual builders optimize images and assets for web performance?', cluster_id: 'C1', cluster_name: 'Mechanism', gap_score: 0.1190, classification: 'gap_to_close', company_sim: 0.5380, citation_sim: 0.6570, target_words: { min: 800, max: 1800 }, reading_level: { min: 10.5, max: 13.0 }, headers: 14, patterns: ['Step-by-Step', 'Tables'], top_domain: 'web.dev', top_exemplar_sim: 0.7190, platform_citations: { chatgpt: 6, claude: 5, perplexity: 5, gemini: 6 } },
  { id: 'q_05', text: 'How does a visual CMS handle content versioning and rollback internally?', cluster_id: 'C1', cluster_name: 'Mechanism', gap_score: 0.1045, classification: 'gap_to_close', company_sim: 0.4780, citation_sim: 0.5825, target_words: { min: 1000, max: 2200 }, reading_level: { min: 12.2, max: 14.8 }, headers: 20, patterns: ['FAQ', 'Step-by-Step'], top_domain: 'kinsta.com', top_exemplar_sim: 0.6850, platform_citations: { chatgpt: 4, claude: 5, perplexity: 6, gemini: 4 } },
  { id: 'q_06', text: 'What rendering approach do modern website builders use for SEO?', cluster_id: 'C1', cluster_name: 'Mechanism', gap_score: 0.0892, classification: 'gap_to_close', company_sim: 0.4650, citation_sim: 0.5542, target_words: { min: 1300, max: 3000 }, reading_level: { min: 11.0, max: 13.8 }, headers: 16, patterns: ['FAQ'], top_domain: 'dev.to', top_exemplar_sim: 0.6410, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_07', text: 'How do website platforms generate clean production-ready code?', cluster_id: 'C1', cluster_name: 'Mechanism', gap_score: 0.0510, classification: 'roughly_equal', company_sim: 0.5320, citation_sim: 0.5830, target_words: { min: 800, max: 1600 }, reading_level: { min: 12.5, max: 14.2 }, headers: 10, patterns: [], top_domain: 'sitepoint.com', top_exemplar_sim: 0.6320, platform_citations: { chatgpt: 4, claude: 5, perplexity: 4, gemini: 5 } },
  { id: 'q_08', text: 'How do visual editors handle complex CSS grid and flexbox layouts?', cluster_id: 'C1', cluster_name: 'Mechanism', gap_score: -0.0120, classification: 'company_wins', company_sim: 0.5540, citation_sim: 0.5420, target_words: { min: 1100, max: 2500 }, reading_level: { min: 13.0, max: 15.0 }, headers: 22, patterns: ['Step-by-Step'], top_domain: 'medium.com', top_exemplar_sim: 0.6100, platform_citations: { chatgpt: 5, claude: 3, perplexity: 5, gemini: 4 } },

  // ── C2 Boundary (8) ──
  { id: 'q_09', text: 'Where do no-code website platforms fall short compared to custom development?', cluster_id: 'C2', cluster_name: 'Boundary', gap_score: 0.1612, classification: 'significant_gap', company_sim: 0.5350, citation_sim: 0.6962, target_words: { min: 1400, max: 3200 }, reading_level: { min: 11.0, max: 13.5 }, headers: 20, patterns: ['FAQ', 'Tables', 'Comparison Table'], top_domain: 'zapier.com', top_exemplar_sim: 0.7680, platform_citations: { chatgpt: 5, claude: 5, perplexity: 6, gemini: 4 } },
  { id: 'q_10', text: 'What types of websites can you NOT build with a visual website builder?', cluster_id: 'C2', cluster_name: 'Boundary', gap_score: 0.1508, classification: 'significant_gap', company_sim: 0.5180, citation_sim: 0.6688, target_words: { min: 1200, max: 2600 }, reading_level: { min: 10.8, max: 12.5 }, headers: 16, patterns: ['FAQ'], top_domain: 'g2.com', top_exemplar_sim: 0.7450, platform_citations: { chatgpt: 6, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_11', text: 'When should a company switch from no-code to custom code for their website?', cluster_id: 'C2', cluster_name: 'Boundary', gap_score: 0.1280, classification: 'gap_to_close', company_sim: 0.5520, citation_sim: 0.6800, target_words: { min: 1000, max: 2000 }, reading_level: { min: 11.5, max: 13.8 }, headers: 18, patterns: ['Step-by-Step', 'Tables'], top_domain: 'techcrunch.com', top_exemplar_sim: 0.7210, platform_citations: { chatgpt: 5, claude: 5, perplexity: 5, gemini: 4 } },
  { id: 'q_12', text: 'What are the scalability limits of visual website builders for enterprise?', cluster_id: 'C2', cluster_name: 'Boundary', gap_score: 0.1105, classification: 'gap_to_close', company_sim: 0.5420, citation_sim: 0.6525, target_words: { min: 1500, max: 3000 }, reading_level: { min: 12.0, max: 14.2 }, headers: 22, patterns: ['FAQ', 'Tables'], top_domain: 'builtwith.com', top_exemplar_sim: 0.7020, platform_citations: { chatgpt: 4, claude: 5, perplexity: 6, gemini: 4 } },
  { id: 'q_13', text: 'Can no-code tools handle complex multi-step form workflows reliably?', cluster_id: 'C2', cluster_name: 'Boundary', gap_score: 0.0920, classification: 'gap_to_close', company_sim: 0.5280, citation_sim: 0.6200, target_words: { min: 900, max: 1800 }, reading_level: { min: 10.5, max: 12.8 }, headers: 14, patterns: ['Step-by-Step'], top_domain: 'capterra.com', top_exemplar_sim: 0.6880, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_14', text: 'What e-commerce functionality is typically missing from website builders?', cluster_id: 'C2', cluster_name: 'Boundary', gap_score: 0.0580, classification: 'roughly_equal', company_sim: 0.5600, citation_sim: 0.6180, target_words: { min: 1100, max: 2400 }, reading_level: { min: 11.2, max: 13.0 }, headers: 18, patterns: ['Tables', 'Comparison Table'], top_domain: 'gartner.com', top_exemplar_sim: 0.6650, platform_citations: { chatgpt: 5, claude: 5, perplexity: 4, gemini: 5 } },
  { id: 'q_15', text: 'When does a growing startup outgrow its no-code website platform?', cluster_id: 'C2', cluster_name: 'Boundary', gap_score: 0.0380, classification: 'roughly_equal', company_sim: 0.5480, citation_sim: 0.5860, target_words: { min: 800, max: 1600 }, reading_level: { min: 10.0, max: 12.0 }, headers: 12, patterns: [], top_domain: 'medium.com', top_exemplar_sim: 0.6340, platform_citations: { chatgpt: 4, claude: 4, perplexity: 5, gemini: 4 } },
  { id: 'q_16', text: 'What are the real performance ceilings of hosted website builders?', cluster_id: 'C2', cluster_name: 'Boundary', gap_score: -0.0150, classification: 'company_wins', company_sim: 0.5720, citation_sim: 0.5570, target_words: { min: 1300, max: 2800 }, reading_level: { min: 12.5, max: 14.5 }, headers: 24, patterns: ['Tables'], top_domain: 'forbes.com', top_exemplar_sim: 0.6150, platform_citations: { chatgpt: 4, claude: 4, perplexity: 4, gemini: 4 } },

  // ── C3 Category Comparison (8) ──
  { id: 'q_17', text: 'Webflow vs WordPress for enterprise marketing websites: which platform wins?', cluster_id: 'C3', cluster_name: 'Category Comparison', gap_score: 0.2810, classification: 'significant_gap', company_sim: 0.4680, citation_sim: 0.7490, target_words: { min: 1600, max: 3400 }, reading_level: { min: 11.5, max: 14.0 }, headers: 24, patterns: ['FAQ', 'Tables', 'Comparison Table'], top_domain: 'g2.com', top_exemplar_sim: 0.8120, platform_citations: { chatgpt: 6, claude: 5, perplexity: 7, gemini: 5 } },
  { id: 'q_18', text: 'How do no-code website builders compare to building with a headless CMS and Next.js?', cluster_id: 'C3', cluster_name: 'Category Comparison', gap_score: 0.2438, classification: 'significant_gap', company_sim: 0.4920, citation_sim: 0.7358, target_words: { min: 1090, max: 1110 }, reading_level: { min: 12.0, max: 14.6 }, headers: 13, patterns: ['Step-by-Step'], top_domain: 'thenewstack.io', top_exemplar_sim: 0.8088, platform_citations: { chatgpt: 5, claude: 6, perplexity: 6, gemini: 5 } },
  { id: 'q_19', text: 'No-code CMS vs headless CMS: which is better for marketing agencies?', cluster_id: 'C3', cluster_name: 'Category Comparison', gap_score: 0.2215, classification: 'significant_gap', company_sim: 0.4850, citation_sim: 0.7065, target_words: { min: 1400, max: 2800 }, reading_level: { min: 12.2, max: 14.8 }, headers: 20, patterns: ['FAQ', 'Tables', 'Comparison Table'], top_domain: 'capterra.com', top_exemplar_sim: 0.7890, platform_citations: { chatgpt: 6, claude: 5, perplexity: 5, gemini: 6 } },
  { id: 'q_20', text: 'Visual website builders vs static site generators for marketing teams', cluster_id: 'C3', cluster_name: 'Category Comparison', gap_score: 0.1920, classification: 'significant_gap', company_sim: 0.5010, citation_sim: 0.6930, target_words: { min: 1200, max: 2200 }, reading_level: { min: 13.0, max: 15.0 }, headers: 16, patterns: ['Tables', 'Comparison Table'], top_domain: 'kinsta.com', top_exemplar_sim: 0.7650, platform_citations: { chatgpt: 5, claude: 4, perplexity: 6, gemini: 4 } },
  { id: 'q_21', text: 'Squarespace vs Webflow vs WordPress: feature-by-feature comparison', cluster_id: 'C3', cluster_name: 'Category Comparison', gap_score: 0.1705, classification: 'significant_gap', company_sim: 0.5120, citation_sim: 0.6825, target_words: { min: 1800, max: 3600 }, reading_level: { min: 10.5, max: 12.8 }, headers: 28, patterns: ['FAQ', 'Tables', 'Key Takeaways'], top_domain: 'wpbeginner.com', top_exemplar_sim: 0.7480, platform_citations: { chatgpt: 5, claude: 5, perplexity: 6, gemini: 5 } },
  { id: 'q_22', text: 'Website builder vs custom development: total cost comparison for mid-market', cluster_id: 'C3', cluster_name: 'Category Comparison', gap_score: 0.1180, classification: 'gap_to_close', company_sim: 0.5250, citation_sim: 0.6430, target_words: { min: 1500, max: 2800 }, reading_level: { min: 11.8, max: 13.5 }, headers: 18, patterns: ['Tables'], top_domain: 'semrush.com', top_exemplar_sim: 0.7120, platform_citations: { chatgpt: 4, claude: 5, perplexity: 5, gemini: 4 } },
  { id: 'q_23', text: 'Comparison of visual editors for design-heavy marketing websites', cluster_id: 'C3', cluster_name: 'Category Comparison', gap_score: 0.0980, classification: 'gap_to_close', company_sim: 0.5080, citation_sim: 0.6060, target_words: { min: 1000, max: 2000 }, reading_level: { min: 12.5, max: 14.2 }, headers: 14, patterns: ['Tables', 'Key Takeaways'], top_domain: 'searchengineland.com', top_exemplar_sim: 0.6780, platform_citations: { chatgpt: 5, claude: 4, perplexity: 4, gemini: 5 } },
  { id: 'q_24', text: 'Marketing site builders vs developer frameworks: when to use each approach', cluster_id: 'C3', cluster_name: 'Category Comparison', gap_score: 0.0420, classification: 'roughly_equal', company_sim: 0.5380, citation_sim: 0.5800, target_words: { min: 900, max: 1600 }, reading_level: { min: 11.0, max: 13.0 }, headers: 12, patterns: ['FAQ'], top_domain: 'hubspot.com', top_exemplar_sim: 0.6350, platform_citations: { chatgpt: 4, claude: 4, perplexity: 5, gemini: 4 } },

  // ── C4 Decision Criteria (8) ──
  { id: 'q_25', text: 'How to estimate total cost of ownership for a no-code website platform', cluster_id: 'C4', cluster_name: 'Decision Criteria', gap_score: 0.2878, classification: 'significant_gap', company_sim: 0.4178, citation_sim: 0.7056, target_words: { min: 1636, max: 2353 }, reading_level: { min: 9.7, max: 13.3 }, headers: 27, patterns: ['FAQ', 'Step-by-Step', 'Tables'], top_domain: 'kissflow.com', top_exemplar_sim: 0.7829, platform_citations: { chatgpt: 5, claude: 5, perplexity: 6, gemini: 4 } },
  { id: 'q_26', text: 'How to evaluate website platforms for enterprise-scale marketing operations', cluster_id: 'C4', cluster_name: 'Decision Criteria', gap_score: 0.2010, classification: 'significant_gap', company_sim: 0.4620, citation_sim: 0.6630, target_words: { min: 1800, max: 3200 }, reading_level: { min: 12.0, max: 14.5 }, headers: 22, patterns: ['FAQ', 'Tables', 'Step-by-Step'], top_domain: 'gartner.com', top_exemplar_sim: 0.7420, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_27', text: 'What should a website platform RFP include for marketing teams?', cluster_id: 'C4', cluster_name: 'Decision Criteria', gap_score: 0.1720, classification: 'significant_gap', company_sim: 0.4880, citation_sim: 0.6600, target_words: { min: 2000, max: 4000 }, reading_level: { min: 11.5, max: 13.8 }, headers: 30, patterns: ['Tables', 'Step-by-Step', 'Key Takeaways'], top_domain: 'forrester.com', top_exemplar_sim: 0.7280, platform_citations: { chatgpt: 4, claude: 5, perplexity: 5, gemini: 4 } },
  { id: 'q_28', text: 'TCO comparison of hosted website builders vs self-hosted CMS solutions', cluster_id: 'C4', cluster_name: 'Decision Criteria', gap_score: 0.1540, classification: 'significant_gap', company_sim: 0.5050, citation_sim: 0.6590, target_words: { min: 1500, max: 2800 }, reading_level: { min: 12.5, max: 14.2 }, headers: 20, patterns: ['Tables', 'Comparison Table'], top_domain: 'g2.com', top_exemplar_sim: 0.7150, platform_citations: { chatgpt: 5, claude: 5, perplexity: 4, gemini: 5 } },
  { id: 'q_29', text: 'Key criteria for choosing a website builder for B2B SaaS marketing', cluster_id: 'C4', cluster_name: 'Decision Criteria', gap_score: 0.1120, classification: 'gap_to_close', company_sim: 0.5180, citation_sim: 0.6300, target_words: { min: 1200, max: 2400 }, reading_level: { min: 11.0, max: 13.0 }, headers: 18, patterns: ['FAQ', 'Key Takeaways'], top_domain: 'capterra.com', top_exemplar_sim: 0.6950, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_30', text: 'How to assess website platform vendor lock-in risk before committing', cluster_id: 'C4', cluster_name: 'Decision Criteria', gap_score: 0.0880, classification: 'gap_to_close', company_sim: 0.5020, citation_sim: 0.5900, target_words: { min: 1000, max: 2000 }, reading_level: { min: 12.0, max: 14.0 }, headers: 15, patterns: ['Step-by-Step'], top_domain: 'hubspot.com', top_exemplar_sim: 0.6650, platform_citations: { chatgpt: 4, claude: 4, perplexity: 5, gemini: 4 } },
  { id: 'q_31', text: 'What integration requirements matter most when choosing a CMS?', cluster_id: 'C4', cluster_name: 'Decision Criteria', gap_score: 0.0520, classification: 'roughly_equal', company_sim: 0.5350, citation_sim: 0.5870, target_words: { min: 1100, max: 2200 }, reading_level: { min: 11.5, max: 13.5 }, headers: 16, patterns: ['Tables'], top_domain: 'zapier.com', top_exemplar_sim: 0.6420, platform_citations: { chatgpt: 5, claude: 5, perplexity: 4, gemini: 4 } },
  { id: 'q_32', text: 'How to calculate ROI of switching website platforms for marketing', cluster_id: 'C4', cluster_name: 'Decision Criteria', gap_score: 0.0280, classification: 'roughly_equal', company_sim: 0.5200, citation_sim: 0.5480, target_words: { min: 1400, max: 2600 }, reading_level: { min: 10.5, max: 12.5 }, headers: 14, patterns: ['Step-by-Step'], top_domain: 'forbes.com', top_exemplar_sim: 0.6100, platform_citations: { chatgpt: 4, claude: 4, perplexity: 4, gemini: 4 } },

  // ── C5 Definition (8) — includes 5 real queries ──
  { id: 'q_33', text: 'What headless CMS should marketing teams use and why?', cluster_id: 'C5', cluster_name: 'Definition', gap_score: 0.2535, classification: 'significant_gap', company_sim: 0.5188, citation_sim: 0.7723, target_words: { min: 977, max: 4268 }, reading_level: { min: 13.0, max: 14.3 }, headers: 37, patterns: ['FAQ', 'Key Takeaways', 'Step-by-Step', 'Tables'], top_domain: 'agilitycms.com', top_exemplar_sim: 0.8775, platform_citations: { chatgpt: 5, claude: 6, perplexity: 6, gemini: 5 } },
  { id: 'q_34', text: 'What is a headless CMS and how does it help marketing teams publish faster?', cluster_id: 'C5', cluster_name: 'Definition', gap_score: 0.2535, classification: 'significant_gap', company_sim: 0.5188, citation_sim: 0.7723, target_words: { min: 977, max: 4268 }, reading_level: { min: 13.0, max: 14.3 }, headers: 37, patterns: ['FAQ', 'Tables'], top_domain: 'storyblok.com', top_exemplar_sim: 0.8309, platform_citations: { chatgpt: 6, claude: 5, perplexity: 5, gemini: 5 } },
  { id: 'q_35', text: 'What is a staging environment and why do website teams need one?', cluster_id: 'C5', cluster_name: 'Definition', gap_score: 0.2307, classification: 'significant_gap', company_sim: 0.4788, citation_sim: 0.7094, target_words: { min: 607, max: 1493 }, reading_level: { min: 11.0, max: 11.0 }, headers: 25, patterns: ['FAQ', 'Step-by-Step'], top_domain: 'marker.io', top_exemplar_sim: 0.7664, platform_citations: { chatgpt: 5, claude: 5, perplexity: 6, gemini: 4 } },
  { id: 'q_36', text: 'What are website performance core web vitals and how do site builders impact them?', cluster_id: 'C5', cluster_name: 'Definition', gap_score: 0.2290, classification: 'significant_gap', company_sim: 0.4692, citation_sim: 0.6982, target_words: { min: 581, max: 1068 }, reading_level: { min: 11.9, max: 13.3 }, headers: 12, patterns: [], top_domain: 'dynatrace.com', top_exemplar_sim: 0.7621, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_37', text: 'What is a design system in the context of website building tools?', cluster_id: 'C5', cluster_name: 'Definition', gap_score: 0.1901, classification: 'significant_gap', company_sim: 0.5047, citation_sim: 0.6948, target_words: { min: 772, max: 2404 }, reading_level: { min: 12.9, max: 14.2 }, headers: 14, patterns: [], top_domain: 'webflow.com', top_exemplar_sim: 0.7485, platform_citations: { chatgpt: 4, claude: 5, perplexity: 5, gemini: 5 } },
  { id: 'q_38', text: 'What is component-based web design and why does it matter?', cluster_id: 'C5', cluster_name: 'Definition', gap_score: 0.1150, classification: 'gap_to_close', company_sim: 0.5280, citation_sim: 0.6430, target_words: { min: 900, max: 2000 }, reading_level: { min: 12.5, max: 14.0 }, headers: 16, patterns: ['Definition Opening'], top_domain: 'smashingmagazine.com', top_exemplar_sim: 0.7050, platform_citations: { chatgpt: 5, claude: 4, perplexity: 4, gemini: 4 } },
  { id: 'q_39', text: 'What does headless mean in modern web development architecture?', cluster_id: 'C5', cluster_name: 'Definition', gap_score: 0.0920, classification: 'gap_to_close', company_sim: 0.5150, citation_sim: 0.6070, target_words: { min: 700, max: 1500 }, reading_level: { min: 11.0, max: 13.0 }, headers: 10, patterns: ['Definition Opening', 'FAQ'], top_domain: 'contentful.com', top_exemplar_sim: 0.6780, platform_citations: { chatgpt: 5, claude: 5, perplexity: 5, gemini: 4 } },
  { id: 'q_40', text: 'What is a visual development environment for the web?', cluster_id: 'C5', cluster_name: 'Definition', gap_score: 0.0380, classification: 'roughly_equal', company_sim: 0.5420, citation_sim: 0.5800, target_words: { min: 600, max: 1200 }, reading_level: { min: 10.5, max: 12.5 }, headers: 8, patterns: ['Definition Opening'], top_domain: 'prismic.io', top_exemplar_sim: 0.6350, platform_citations: { chatgpt: 4, claude: 4, perplexity: 4, gemini: 4 } },

  // ── C6 Problem/Awareness (8) — includes 2 real queries ──
  { id: 'q_41', text: 'How can I migrate off WordPress without losing SEO rankings and backlinks?', cluster_id: 'C6', cluster_name: 'Problem/Awareness', gap_score: 0.3233, classification: 'significant_gap', company_sim: 0.4076, citation_sim: 0.7308, target_words: { min: 693, max: 3819 }, reading_level: { min: 8.6, max: 14.2 }, headers: 15, patterns: ['Step-by-Step'], top_domain: 'wpx.net', top_exemplar_sim: 0.8002, platform_citations: { chatgpt: 6, claude: 5, perplexity: 7, gemini: 5 } },
  { id: 'q_42', text: 'How can I standardize landing pages so different teams dont break brand design?', cluster_id: 'C6', cluster_name: 'Problem/Awareness', gap_score: 0.1606, classification: 'significant_gap', company_sim: 0.4448, citation_sim: 0.6053, target_words: { min: 5258, max: 5258 }, reading_level: { min: 10.8, max: 10.8 }, headers: 33, patterns: [], top_domain: 'klientboost.com', top_exemplar_sim: 0.7033, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_43', text: 'How to fix slow website load times without hiring a performance engineer', cluster_id: 'C6', cluster_name: 'Problem/Awareness', gap_score: 0.2210, classification: 'significant_gap', company_sim: 0.4520, citation_sim: 0.6730, target_words: { min: 1200, max: 2800 }, reading_level: { min: 10.0, max: 12.5 }, headers: 18, patterns: ['Step-by-Step', 'FAQ'], top_domain: 'moz.com', top_exemplar_sim: 0.7580, platform_citations: { chatgpt: 5, claude: 5, perplexity: 6, gemini: 4 } },
  { id: 'q_44', text: 'Why do marketing teams need a design system for their website?', cluster_id: 'C6', cluster_name: 'Problem/Awareness', gap_score: 0.1920, classification: 'significant_gap', company_sim: 0.4680, citation_sim: 0.6600, target_words: { min: 1400, max: 3000 }, reading_level: { min: 11.5, max: 13.5 }, headers: 20, patterns: ['FAQ', 'Key Takeaways'], top_domain: 'ahrefs.com', top_exemplar_sim: 0.7350, platform_citations: { chatgpt: 5, claude: 5, perplexity: 5, gemini: 5 } },
  { id: 'q_45', text: 'Common problems with WordPress multisite management for agencies', cluster_id: 'C6', cluster_name: 'Problem/Awareness', gap_score: 0.1580, classification: 'significant_gap', company_sim: 0.4750, citation_sim: 0.6330, target_words: { min: 1600, max: 3200 }, reading_level: { min: 11.0, max: 13.8 }, headers: 22, patterns: ['FAQ', 'Tables'], top_domain: 'hubspot.com', top_exemplar_sim: 0.7180, platform_citations: { chatgpt: 4, claude: 5, perplexity: 5, gemini: 5 } },
  { id: 'q_46', text: 'How to reduce developer dependency for marketing website updates', cluster_id: 'C6', cluster_name: 'Problem/Awareness', gap_score: 0.1280, classification: 'gap_to_close', company_sim: 0.4850, citation_sim: 0.6130, target_words: { min: 1000, max: 2200 }, reading_level: { min: 10.5, max: 12.8 }, headers: 16, patterns: ['Step-by-Step'], top_domain: 'searchengineland.com', top_exemplar_sim: 0.6920, platform_citations: { chatgpt: 5, claude: 4, perplexity: 4, gemini: 4 } },
  { id: 'q_47', text: 'Why do website redesigns consistently go over budget and timeline?', cluster_id: 'C6', cluster_name: 'Problem/Awareness', gap_score: 0.0980, classification: 'gap_to_close', company_sim: 0.4920, citation_sim: 0.5900, target_words: { min: 1300, max: 2600 }, reading_level: { min: 11.5, max: 13.5 }, headers: 14, patterns: ['Research Refs'], top_domain: 'kinsta.com', top_exemplar_sim: 0.6680, platform_citations: { chatgpt: 4, claude: 4, perplexity: 5, gemini: 4 } },
  { id: 'q_48', text: 'How to manage multiple brand websites without duplicating effort', cluster_id: 'C6', cluster_name: 'Problem/Awareness', gap_score: 0.0450, classification: 'roughly_equal', company_sim: 0.5180, citation_sim: 0.5630, target_words: { min: 900, max: 1800 }, reading_level: { min: 10.0, max: 12.0 }, headers: 12, patterns: [], top_domain: 'semrush.com', top_exemplar_sim: 0.6250, platform_citations: { chatgpt: 4, claude: 4, perplexity: 4, gemini: 4 } },

  // ── C7 Best-of/Consideration (8) — includes 1 real query ──
  { id: 'q_49', text: 'Best website platforms with enterprise security features (SSO, SOC 2, roles)', cluster_id: 'C7', cluster_name: 'Best-of/Consideration', gap_score: 0.1884, classification: 'significant_gap', company_sim: 0.4402, citation_sim: 0.6287, target_words: { min: 3803, max: 3803 }, reading_level: { min: 18.6, max: 18.6 }, headers: 47, patterns: ['FAQ', 'Tables'], top_domain: 'oloid.com', top_exemplar_sim: 0.7124, platform_citations: { chatgpt: 6, claude: 5, perplexity: 6, gemini: 5 } },
  { id: 'q_50', text: 'Best website builders for B2B SaaS companies in 2026', cluster_id: 'C7', cluster_name: 'Best-of/Consideration', gap_score: 0.1780, classification: 'significant_gap', company_sim: 0.4550, citation_sim: 0.6330, target_words: { min: 2000, max: 4000 }, reading_level: { min: 10.5, max: 13.0 }, headers: 30, patterns: ['FAQ', 'Tables', 'Key Takeaways'], top_domain: 'g2.com', top_exemplar_sim: 0.7280, platform_citations: { chatgpt: 5, claude: 6, perplexity: 7, gemini: 5 } },
  { id: 'q_51', text: 'Top CMS platforms for marketing teams with high content velocity needs', cluster_id: 'C7', cluster_name: 'Best-of/Consideration', gap_score: 0.1650, classification: 'significant_gap', company_sim: 0.4680, citation_sim: 0.6330, target_words: { min: 1800, max: 3500 }, reading_level: { min: 11.0, max: 13.5 }, headers: 25, patterns: ['Tables', 'Key Takeaways', 'Comparison Table'], top_domain: 'capterra.com', top_exemplar_sim: 0.7150, platform_citations: { chatgpt: 5, claude: 5, perplexity: 6, gemini: 5 } },
  { id: 'q_52', text: 'Best enterprise website platforms with built-in SSO support', cluster_id: 'C7', cluster_name: 'Best-of/Consideration', gap_score: 0.1520, classification: 'significant_gap', company_sim: 0.4820, citation_sim: 0.6340, target_words: { min: 1500, max: 3000 }, reading_level: { min: 12.0, max: 14.5 }, headers: 22, patterns: ['Tables', 'FAQ'], top_domain: 'trustradius.com', top_exemplar_sim: 0.7050, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_53', text: 'Best visual development platforms for digital agencies', cluster_id: 'C7', cluster_name: 'Best-of/Consideration', gap_score: 0.1080, classification: 'gap_to_close', company_sim: 0.5050, citation_sim: 0.6130, target_words: { min: 1200, max: 2600 }, reading_level: { min: 11.5, max: 13.5 }, headers: 18, patterns: ['Tables'], top_domain: 'gartner.com', top_exemplar_sim: 0.6850, platform_citations: { chatgpt: 4, claude: 5, perplexity: 5, gemini: 4 } },
  { id: 'q_54', text: 'Top website builders for content-heavy B2B marketing sites', cluster_id: 'C7', cluster_name: 'Best-of/Consideration', gap_score: 0.0920, classification: 'gap_to_close', company_sim: 0.5180, citation_sim: 0.6100, target_words: { min: 1600, max: 3200 }, reading_level: { min: 10.8, max: 12.8 }, headers: 20, patterns: ['FAQ', 'Tables'], top_domain: 'hubspot.com', top_exemplar_sim: 0.6750, platform_citations: { chatgpt: 5, claude: 4, perplexity: 4, gemini: 5 } },
  { id: 'q_55', text: 'Most scalable website builders for rapidly growing companies', cluster_id: 'C7', cluster_name: 'Best-of/Consideration', gap_score: 0.0420, classification: 'roughly_equal', company_sim: 0.5350, citation_sim: 0.5770, target_words: { min: 1000, max: 2000 }, reading_level: { min: 11.0, max: 13.0 }, headers: 14, patterns: ['Tables'], top_domain: 'kinsta.com', top_exemplar_sim: 0.6380, platform_citations: { chatgpt: 4, claude: 4, perplexity: 4, gemini: 4 } },
  { id: 'q_56', text: 'Best no-code platforms for enterprise brand management at scale', cluster_id: 'C7', cluster_name: 'Best-of/Consideration', gap_score: -0.0180, classification: 'company_wins', company_sim: 0.5580, citation_sim: 0.5400, target_words: { min: 1400, max: 2800 }, reading_level: { min: 12.0, max: 14.0 }, headers: 16, patterns: ['FAQ'], top_domain: 'zapier.com', top_exemplar_sim: 0.6120, platform_citations: { chatgpt: 4, claude: 4, perplexity: 4, gemini: 3 } },

  // ── C8 Branded Evaluation (8) ──
  { id: 'q_57', text: 'Webflow vs Framer: detailed comparison for marketing teams', cluster_id: 'C8', cluster_name: 'Branded Evaluation', gap_score: 0.1680, classification: 'significant_gap', company_sim: 0.5520, citation_sim: 0.7200, target_words: { min: 1800, max: 3400 }, reading_level: { min: 11.0, max: 13.5 }, headers: 24, patterns: ['FAQ', 'Tables', 'Comparison Table', 'Key Takeaways'], top_domain: 'g2.com', top_exemplar_sim: 0.7920, platform_citations: { chatgpt: 6, claude: 5, perplexity: 6, gemini: 6 } },
  { id: 'q_58', text: 'Webflow enterprise pricing analysis: is it worth the investment?', cluster_id: 'C8', cluster_name: 'Branded Evaluation', gap_score: 0.1520, classification: 'significant_gap', company_sim: 0.5680, citation_sim: 0.7200, target_words: { min: 1500, max: 2800 }, reading_level: { min: 10.5, max: 12.8 }, headers: 20, patterns: ['Tables', 'FAQ', 'Key Takeaways'], top_domain: 'capterra.com', top_exemplar_sim: 0.7750, platform_citations: { chatgpt: 5, claude: 6, perplexity: 5, gemini: 5 } },
  { id: 'q_59', text: 'Is Webflow worth it for enterprise websites with complex requirements?', cluster_id: 'C8', cluster_name: 'Branded Evaluation', gap_score: 0.1350, classification: 'gap_to_close', company_sim: 0.5750, citation_sim: 0.7100, target_words: { min: 1200, max: 2400 }, reading_level: { min: 11.5, max: 13.8 }, headers: 18, patterns: ['FAQ', 'Key Takeaways'], top_domain: 'producthunt.com', top_exemplar_sim: 0.7580, platform_citations: { chatgpt: 5, claude: 5, perplexity: 5, gemini: 5 } },
  { id: 'q_60', text: 'Webflow vs HubSpot CMS for B2B marketing website management', cluster_id: 'C8', cluster_name: 'Branded Evaluation', gap_score: 0.1020, classification: 'gap_to_close', company_sim: 0.5850, citation_sim: 0.6870, target_words: { min: 1600, max: 3000 }, reading_level: { min: 11.0, max: 13.0 }, headers: 22, patterns: ['Tables', 'Comparison Table'], top_domain: 'techcrunch.com', top_exemplar_sim: 0.7380, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 5 } },
  { id: 'q_61', text: 'Webflow enterprise plan features, limitations, and real user reviews', cluster_id: 'C8', cluster_name: 'Branded Evaluation', gap_score: 0.0780, classification: 'roughly_equal', company_sim: 0.5920, citation_sim: 0.6700, target_words: { min: 1400, max: 2600 }, reading_level: { min: 10.8, max: 12.5 }, headers: 20, patterns: ['FAQ', 'Tables'], top_domain: 'trustradius.com', top_exemplar_sim: 0.7200, platform_citations: { chatgpt: 5, claude: 5, perplexity: 4, gemini: 5 } },
  { id: 'q_62', text: 'Webflow vs Contentful for marketing teams managing structured content', cluster_id: 'C8', cluster_name: 'Branded Evaluation', gap_score: 0.0520, classification: 'roughly_equal', company_sim: 0.5780, citation_sim: 0.6300, target_words: { min: 1200, max: 2200 }, reading_level: { min: 12.5, max: 14.5 }, headers: 16, patterns: ['Tables', 'Comparison Table'], top_domain: 'medium.com', top_exemplar_sim: 0.6850, platform_citations: { chatgpt: 4, claude: 4, perplexity: 5, gemini: 4 } },
  { id: 'q_63', text: 'Webflow designer vs Figma to code workflows: which is more efficient?', cluster_id: 'C8', cluster_name: 'Branded Evaluation', gap_score: 0.0280, classification: 'roughly_equal', company_sim: 0.5950, citation_sim: 0.6230, target_words: { min: 1000, max: 1800 }, reading_level: { min: 12.0, max: 14.0 }, headers: 12, patterns: ['Comparison Table'], top_domain: 'zapier.com', top_exemplar_sim: 0.6620, platform_citations: { chatgpt: 4, claude: 4, perplexity: 4, gemini: 3 } },
  { id: 'q_64', text: 'How does Webflow handle localization and multi-language website management?', cluster_id: 'C8', cluster_name: 'Branded Evaluation', gap_score: -0.0080, classification: 'company_wins', company_sim: 0.6020, citation_sim: 0.5940, target_words: { min: 1300, max: 2500 }, reading_level: { min: 11.0, max: 13.0 }, headers: 18, patterns: ['FAQ', 'Step-by-Step'], top_domain: 'hubspot.com', top_exemplar_sim: 0.6480, platform_citations: { chatgpt: 5, claude: 4, perplexity: 4, gemini: 4 } },

  // ── C9 Feature Verification (8) — includes 2 real queries ──
  { id: 'q_65', text: 'Do modern website builders support SSO (SAML) and SCIM user provisioning?', cluster_id: 'C9', cluster_name: 'Feature Verification', gap_score: 0.2491, classification: 'significant_gap', company_sim: 0.3454, citation_sim: 0.5946, target_words: { min: 726, max: 3306 }, reading_level: { min: 10.2, max: 12.5 }, headers: 44, patterns: ['FAQ', 'Step-by-Step', 'Tables'], top_domain: 'frontegg.com', top_exemplar_sim: 0.6550, platform_citations: { chatgpt: 5, claude: 4, perplexity: 5, gemini: 3 } },
  { id: 'q_66', text: 'Do hosted website builders provide staging environments and rollback/version history?', cluster_id: 'C9', cluster_name: 'Feature Verification', gap_score: 0.1676, classification: 'significant_gap', company_sim: 0.4113, citation_sim: 0.5789, target_words: { min: 1358, max: 1358 }, reading_level: { min: 10.1, max: 10.1 }, headers: 17, patterns: ['FAQ', 'Key Takeaways', 'Step-by-Step'], top_domain: 'dohost.us', top_exemplar_sim: 0.6817, platform_citations: { chatgpt: 4, claude: 4, perplexity: 5, gemini: 3 } },
  { id: 'q_67', text: 'Does Webflow support SCIM provisioning for enterprise user management?', cluster_id: 'C9', cluster_name: 'Feature Verification', gap_score: 0.1580, classification: 'significant_gap', company_sim: 0.3980, citation_sim: 0.5560, target_words: { min: 800, max: 2200 }, reading_level: { min: 11.0, max: 13.5 }, headers: 20, patterns: ['FAQ', 'Tables'], top_domain: 'marker.io', top_exemplar_sim: 0.6450, platform_citations: { chatgpt: 4, claude: 3, perplexity: 4, gemini: 3 } },
  { id: 'q_68', text: 'Can Webflow handle websites with 100k+ pages efficiently?', cluster_id: 'C9', cluster_name: 'Feature Verification', gap_score: 0.1320, classification: 'gap_to_close', company_sim: 0.4250, citation_sim: 0.5570, target_words: { min: 1000, max: 2000 }, reading_level: { min: 10.5, max: 12.8 }, headers: 14, patterns: ['FAQ'], top_domain: 'kinsta.com', top_exemplar_sim: 0.6280, platform_citations: { chatgpt: 4, claude: 4, perplexity: 4, gemini: 4 } },
  { id: 'q_69', text: 'Webflow staging environment capabilities and deployment workflows', cluster_id: 'C9', cluster_name: 'Feature Verification', gap_score: 0.1050, classification: 'gap_to_close', company_sim: 0.4380, citation_sim: 0.5430, target_words: { min: 900, max: 1800 }, reading_level: { min: 11.5, max: 13.5 }, headers: 16, patterns: ['Step-by-Step'], top_domain: 'wpengine.com', top_exemplar_sim: 0.6120, platform_citations: { chatgpt: 3, claude: 4, perplexity: 4, gemini: 3 } },
  { id: 'q_70', text: 'Does Webflow support custom code injection and third-party API integrations?', cluster_id: 'C9', cluster_name: 'Feature Verification', gap_score: 0.0820, classification: 'gap_to_close', company_sim: 0.4520, citation_sim: 0.5340, target_words: { min: 800, max: 1600 }, reading_level: { min: 12.0, max: 14.0 }, headers: 12, patterns: ['Step-by-Step', 'FAQ'], top_domain: 'netlify.com', top_exemplar_sim: 0.5980, platform_citations: { chatgpt: 4, claude: 3, perplexity: 4, gemini: 3 } },
  { id: 'q_71', text: 'Can visual website builders output AMP-compliant pages?', cluster_id: 'C9', cluster_name: 'Feature Verification', gap_score: 0.0380, classification: 'roughly_equal', company_sim: 0.4650, citation_sim: 0.5030, target_words: { min: 700, max: 1400 }, reading_level: { min: 10.0, max: 12.0 }, headers: 10, patterns: [], top_domain: 'siteground.com', top_exemplar_sim: 0.5620, platform_citations: { chatgpt: 3, claude: 3, perplexity: 3, gemini: 3 } },
  { id: 'q_72', text: 'Do website builders support native A/B testing and experimentation?', cluster_id: 'C9', cluster_name: 'Feature Verification', gap_score: -0.0150, classification: 'company_wins', company_sim: 0.4780, citation_sim: 0.4630, target_words: { min: 900, max: 1800 }, reading_level: { min: 11.0, max: 13.0 }, headers: 14, patterns: ['FAQ'], top_domain: 'vercel.com', top_exemplar_sim: 0.5350, platform_citations: { chatgpt: 3, claude: 3, perplexity: 3, gemini: 3 } },
];

// ─── Signal Averages: Citation vs Company (24 signals) ───────────────────────

export const SIGNAL_AVERAGES: SignalAverageRow[] = [
  // Text Composition
  { signal: 'Word Count', category: 'Text Composition', citation_avg: 1735, company_avg: 1100, unit: 'words', recommendation: 'Increase average content length by ~58%' },
  { signal: 'Sentence Count', category: 'Text Composition', citation_avg: 96, company_avg: 62, unit: 'sentences', recommendation: 'Add more depth and supporting detail' },
  { signal: 'Paragraph Count', category: 'Text Composition', citation_avg: 24, company_avg: 17, unit: 'paragraphs', recommendation: 'Break content into more focused paragraphs' },
  { signal: 'Avg Paragraph Length', category: 'Text Composition', citation_avg: 4.0, company_avg: 3.6, unit: 'sentences', recommendation: 'Slightly expand paragraph depth' },
  { signal: 'Reading Level', category: 'Text Composition', citation_avg: 12.8, company_avg: 11.5, unit: 'grade', recommendation: 'Target 12-13 grade reading level' },
  { signal: 'Self-Contained Ratio', category: 'Text Composition', citation_avg: 0.76, company_avg: 0.62, unit: 'ratio', recommendation: 'Make content more self-contained (+23%)' },
  // Structural Elements
  { signal: 'H1 Count', category: 'Structural Elements', citation_avg: 1.0, company_avg: 1.0, unit: 'headers', recommendation: 'Maintain current level' },
  { signal: 'H2 Count', category: 'Structural Elements', citation_avg: 5.3, company_avg: 3.8, unit: 'headers', recommendation: 'Add 1-2 more H2 sections per article' },
  { signal: 'H3 Count', category: 'Structural Elements', citation_avg: 7.8, company_avg: 4.2, unit: 'headers', recommendation: 'Nearly double H3 subsections' },
  { signal: 'H4 Count', category: 'Structural Elements', citation_avg: 2.1, company_avg: 1.0, unit: 'headers', recommendation: 'Add more granular sub-sections' },
  { signal: 'List Count', category: 'Structural Elements', citation_avg: 6.2, company_avg: 3.5, unit: 'lists', recommendation: 'Use 2x more bulleted/numbered lists' },
  { signal: 'Ordered List Count', category: 'Structural Elements', citation_avg: 1.8, company_avg: 0.8, unit: 'lists', recommendation: 'Add more step-by-step numbered lists' },
  { signal: 'Table Count', category: 'Structural Elements', citation_avg: 0.7, company_avg: 0.2, unit: 'tables', recommendation: 'Include comparison or data tables' },
  { signal: 'Code Block Count', category: 'Structural Elements', citation_avg: 0.4, company_avg: 0.2, unit: 'blocks', recommendation: 'Add code examples where relevant' },
  // Content Patterns
  { signal: 'FAQ Section', category: 'Content Patterns', citation_avg: 0.28, company_avg: 0.05, unit: '%', recommendation: 'Add FAQ sections to 25%+ of content' },
  { signal: 'Definition Opening', category: 'Content Patterns', citation_avg: 0.35, company_avg: 0.20, unit: '%', recommendation: 'Open with clear definitions more often' },
  { signal: 'Key Takeaways', category: 'Content Patterns', citation_avg: 0.13, company_avg: 0.08, unit: '%', recommendation: 'Add key takeaway summaries' },
  { signal: 'Comparison Table', category: 'Content Patterns', citation_avg: 0.18, company_avg: 0.05, unit: '%', recommendation: 'Include comparison tables in relevant content' },
  { signal: 'Step-by-Step', category: 'Content Patterns', citation_avg: 0.22, company_avg: 0.12, unit: '%', recommendation: 'Add more procedural/how-to content' },
  { signal: 'Research References', category: 'Content Patterns', citation_avg: 0.25, company_avg: 0.10, unit: '%', recommendation: 'Cite more third-party research and data' },
  { signal: 'Expert Quotes', category: 'Content Patterns', citation_avg: 0.15, company_avg: 0.08, unit: '%', recommendation: 'Include expert opinions and quotes' },
  // Factual Density
  { signal: 'Data Point Count', category: 'Factual Density', citation_avg: 8.2, company_avg: 4.5, unit: 'data points', recommendation: 'Include 80% more stats and data points' },
  { signal: 'Citation Density', category: 'Factual Density', citation_avg: 0.018, company_avg: 0.008, unit: 'per word', recommendation: 'Double the density of source citations' },
  { signal: 'Named Entity Density', category: 'Factual Density', citation_avg: 0.025, company_avg: 0.018, unit: 'per word', recommendation: 'Reference more specific tools, companies, people' },
];

// ─── Signal Importance Correlations (ranked) ─────────────────────────────────

export const SIGNAL_CORRELATIONS: SignalCorrelation[] = [
  { signal: 'FAQ Section', correlation: 0.82, category: 'Content Patterns' },
  { signal: 'Table Count', correlation: 0.78, category: 'Structural Elements' },
  { signal: 'H2 Count', correlation: 0.75, category: 'Structural Elements' },
  { signal: 'List Count', correlation: 0.71, category: 'Structural Elements' },
  { signal: 'Word Count', correlation: 0.68, category: 'Text Composition' },
  { signal: 'Key Takeaways', correlation: 0.65, category: 'Content Patterns' },
  { signal: 'Reading Level', correlation: 0.62, category: 'Text Composition' },
  { signal: 'Paragraph Count', correlation: 0.58, category: 'Text Composition' },
  { signal: 'Comparison Table', correlation: 0.55, category: 'Content Patterns' },
  { signal: 'Data Point Count', correlation: 0.52, category: 'Factual Density' },
  { signal: 'Citation Density', correlation: 0.48, category: 'Factual Density' },
  { signal: 'Step-by-Step', correlation: 0.45, category: 'Content Patterns' },
  { signal: 'Named Entity Density', correlation: 0.42, category: 'Factual Density' },
  { signal: 'Definition Opening', correlation: 0.38, category: 'Content Patterns' },
  { signal: 'Self-Contained Ratio', correlation: 0.35, category: 'Text Composition' },
];

// ─── Per-Cluster Pattern Adoption Rates (citation side) ──────────────────────

export const CLUSTER_PATTERN_RATES: ClusterPatternRates[] = [
  { cluster_id: 'C1', cluster_name: 'Mechanism', faq: 0.32, definition_opening: 0.40, key_takeaways: 0.10, comparison_table: 0.15, step_by_step: 0.35, research_refs: 0.30, expert_quotes: 0.12 },
  { cluster_id: 'C2', cluster_name: 'Boundary', faq: 0.23, definition_opening: 0.28, key_takeaways: 0.16, comparison_table: 0.22, step_by_step: 0.18, research_refs: 0.20, expert_quotes: 0.14 },
  { cluster_id: 'C3', cluster_name: 'Category Comparison', faq: 0.36, definition_opening: 0.20, key_takeaways: 0.16, comparison_table: 0.39, step_by_step: 0.12, research_refs: 0.28, expert_quotes: 0.18 },
  { cluster_id: 'C4', cluster_name: 'Decision Criteria', faq: 0.27, definition_opening: 0.22, key_takeaways: 0.10, comparison_table: 0.24, step_by_step: 0.30, research_refs: 0.35, expert_quotes: 0.20 },
  { cluster_id: 'C5', cluster_name: 'Definition', faq: 0.24, definition_opening: 0.55, key_takeaways: 0.08, comparison_table: 0.08, step_by_step: 0.15, research_refs: 0.22, expert_quotes: 0.10 },
  { cluster_id: 'C6', cluster_name: 'Problem/Awareness', faq: 0.23, definition_opening: 0.30, key_takeaways: 0.10, comparison_table: 0.10, step_by_step: 0.38, research_refs: 0.28, expert_quotes: 0.15 },
  { cluster_id: 'C7', cluster_name: 'Best-of/Consideration', faq: 0.28, definition_opening: 0.18, key_takeaways: 0.12, comparison_table: 0.29, step_by_step: 0.10, research_refs: 0.22, expert_quotes: 0.16 },
  { cluster_id: 'C8', cluster_name: 'Branded Evaluation', faq: 0.38, definition_opening: 0.15, key_takeaways: 0.29, comparison_table: 0.40, step_by_step: 0.08, research_refs: 0.18, expert_quotes: 0.22 },
  { cluster_id: 'C9', cluster_name: 'Feature Verification', faq: 0.22, definition_opening: 0.25, key_takeaways: 0.11, comparison_table: 0.15, step_by_step: 0.28, research_refs: 0.12, expert_quotes: 0.08 },
];

// ─── Cluster Signal Fingerprints (normalized 0-1 for radar charts) ───────────

export const CLUSTER_FINGERPRINTS: Record<string, { word_count: number; headers: number; lists: number; tables: number; faq: number; stats: number; citations: number }> = {
  C1: { word_count: 0.72, headers: 0.90, lists: 0.80, tables: 0.42, faq: 0.64, stats: 0.62, citations: 0.96 },
  C2: { word_count: 0.66, headers: 0.96, lists: 0.78, tables: 0.58, faq: 0.46, stats: 0.75, citations: 0.98 },
  C3: { word_count: 0.82, headers: 0.96, lists: 0.87, tables: 0.78, faq: 0.72, stats: 0.75, citations: 0.96 },
  C4: { word_count: 0.90, headers: 0.91, lists: 0.77, tables: 0.48, faq: 0.54, stats: 0.71, citations: 0.95 },
  C5: { word_count: 0.68, headers: 0.92, lists: 0.80, tables: 0.24, faq: 0.48, stats: 0.68, citations: 0.93 },
  C6: { word_count: 0.69, headers: 0.95, lists: 0.84, tables: 0.26, faq: 0.46, stats: 0.73, citations: 0.95 },
  C7: { word_count: 0.73, headers: 0.91, lists: 0.84, tables: 0.58, faq: 0.56, stats: 0.71, citations: 0.95 },
  C8: { word_count: 0.78, headers: 0.92, lists: 0.80, tables: 0.80, faq: 0.76, stats: 0.77, citations: 0.97 },
  C9: { word_count: 0.52, headers: 0.86, lists: 0.80, tables: 0.40, faq: 0.44, stats: 0.56, citations: 0.99 },
};

// ─── Platform Data ───────────────────────────────────────────────────────────

export const PLATFORM_SUMMARIES: PlatformSummary[] = [
  {
    name: 'ChatGPT',
    total_citations: 380,
    unique_domains: 142,
    avg_citation_sim: 0.6420,
    most_cited_domain: 'hubspot.com',
    best_cluster: 'C8',
    worst_cluster: 'C9',
    per_cluster: { C1: 45, C2: 42, C3: 44, C4: 41, C5: 43, C6: 42, C7: 43, C8: 44, C9: 36 },
  },
  {
    name: 'Claude',
    total_citations: 332,
    unique_domains: 128,
    avg_citation_sim: 0.6510,
    most_cited_domain: 'smashingmagazine.com',
    best_cluster: 'C5',
    worst_cluster: 'C9',
    per_cluster: { C1: 40, C2: 38, C3: 39, C4: 38, C5: 40, C6: 37, C7: 38, C8: 37, C9: 25 },
  },
  {
    name: 'Perplexity',
    total_citations: 390,
    unique_domains: 156,
    avg_citation_sim: 0.6280,
    most_cited_domain: 'g2.com',
    best_cluster: 'C3',
    worst_cluster: 'C9',
    per_cluster: { C1: 46, C2: 43, C3: 48, C4: 42, C5: 44, C6: 42, C7: 45, C8: 43, C9: 37 },
  },
  {
    name: 'Gemini',
    total_citations: 320,
    unique_domains: 118,
    avg_citation_sim: 0.6340,
    most_cited_domain: 'kinsta.com',
    best_cluster: 'C8',
    worst_cluster: 'C9',
    per_cluster: { C1: 38, C2: 37, C3: 39, C4: 36, C5: 37, C6: 36, C7: 37, C8: 37, C9: 23 },
  },
];

// Platform agreement (Jaccard similarity between citation sets)
export const PLATFORM_AGREEMENT: Record<string, Record<string, number>> = {
  ChatGPT: { ChatGPT: 1.00, Claude: 0.45, Perplexity: 0.42, Gemini: 0.38 },
  Claude: { ChatGPT: 0.45, Claude: 1.00, Perplexity: 0.40, Gemini: 0.35 },
  Perplexity: { ChatGPT: 0.42, Perplexity: 1.00, Claude: 0.40, Gemini: 0.33 },
  Gemini: { ChatGPT: 0.38, Claude: 0.35, Perplexity: 0.33, Gemini: 1.00 },
};

// Platform citation trend (4 analysis runs)
export const PLATFORM_TRENDS = [
  { run: 'Run 1 (Jan 6)', chatgpt: 310, claude: 280, perplexity: 320, gemini: 260 },
  { run: 'Run 2 (Jan 27)', chatgpt: 340, claude: 295, perplexity: 350, gemini: 285 },
  { run: 'Run 3 (Feb 10)', chatgpt: 355, claude: 315, perplexity: 370, gemini: 300 },
  { run: 'Run 4 (Feb 18)', chatgpt: 380, claude: 332, perplexity: 390, gemini: 320 },
];

// Citation exclusivity per cluster (how many platforms cite content)
export const CITATION_EXCLUSIVITY: Record<string, { all_4: number; three: number; two: number; one: number; none: number }> = {
  C1: { all_4: 12, three: 18, two: 22, one: 15, none: 2 },
  C2: { all_4: 10, three: 16, two: 20, one: 14, none: 3 },
  C3: { all_4: 15, three: 20, two: 18, one: 12, none: 1 },
  C4: { all_4: 11, three: 17, two: 21, one: 13, none: 2 },
  C5: { all_4: 13, three: 19, two: 20, one: 12, none: 2 },
  C6: { all_4: 12, three: 18, two: 19, one: 14, none: 3 },
  C7: { all_4: 14, three: 20, two: 22, one: 15, none: 1 },
  C8: { all_4: 16, three: 22, two: 20, one: 10, none: 1 },
  C9: { all_4: 8, three: 12, two: 15, one: 10, none: 5 },
};

// ─── Run History ─────────────────────────────────────────────────────────────

export const RUN_HISTORY: RunHistoryItem[] = [
  { id: 'run-001', company: 'Webflow', company_slug: 'webflow', status: 'completed', started: '2026-02-18T20:00:00Z', duration: '3h 46m', queries: 72, citations: 1422, spa_score: 14.975, steps_completed: 8 },
  { id: 'run-002', company: 'Ramp', company_slug: 'ramp', status: 'completed', started: '2026-02-15T14:00:00Z', duration: '4h 12m', queries: 68, citations: 1280, spa_score: 11.234, steps_completed: 8 },
  { id: 'run-003', company: 'Carta', company_slug: 'carta', status: 'completed', started: '2026-02-12T09:00:00Z', duration: '3h 58m', queries: 65, citations: 1150, spa_score: 8.891, steps_completed: 8 },
];

// SPA score trend across multiple runs for Webflow
export const SPA_SCORE_TREND = [
  { run: 'Jan 6', spa_score: 12.340 },
  { run: 'Jan 27', spa_score: 13.120 },
  { run: 'Feb 10', spa_score: 14.200 },
  { run: 'Feb 18', spa_score: 14.975 },
];

// ─── Content Calendar Suggestion ─────────────────────────────────────────────

export const CONTENT_CALENDAR: CalendarWeek[] = [
  {
    week: 'Week 1 (Feb 24)',
    start: '2026-02-24',
    briefs: [
      { query_id: 'q_41', query_text: 'How can I migrate off WordPress without losing SEO rankings and backlinks?', cluster: 'C6', gap_score: 0.3233 },
      { query_id: 'q_25', query_text: 'How to estimate total cost of ownership for a no-code website platform', cluster: 'C4', gap_score: 0.2878 },
      { query_id: 'q_17', query_text: 'Webflow vs WordPress for enterprise marketing websites', cluster: 'C3', gap_score: 0.2810 },
    ],
  },
  {
    week: 'Week 2 (Mar 3)',
    start: '2026-03-03',
    briefs: [
      { query_id: 'q_33', query_text: 'What headless CMS should marketing teams use and why?', cluster: 'C5', gap_score: 0.2535 },
      { query_id: 'q_65', query_text: 'Do modern website builders support SSO (SAML) and SCIM provisioning?', cluster: 'C9', gap_score: 0.2491 },
      { query_id: 'q_18', query_text: 'How do no-code website builders compare to building with a headless CMS and Next.js?', cluster: 'C3', gap_score: 0.2438 },
    ],
  },
  {
    week: 'Week 3 (Mar 10)',
    start: '2026-03-10',
    briefs: [
      { query_id: 'q_35', query_text: 'What is a staging environment and why do website teams need one?', cluster: 'C5', gap_score: 0.2307 },
      { query_id: 'q_43', query_text: 'How to fix slow website load times without hiring a performance engineer', cluster: 'C6', gap_score: 0.2210 },
      { query_id: 'q_19', query_text: 'No-code CMS vs headless CMS: which is better for marketing agencies?', cluster: 'C3', gap_score: 0.2215 },
    ],
  },
  {
    week: 'Week 4 (Mar 17)',
    start: '2026-03-17',
    briefs: [
      { query_id: 'q_26', query_text: 'How to evaluate website platforms for enterprise-scale marketing operations', cluster: 'C4', gap_score: 0.2010 },
      { query_id: 'q_44', query_text: 'Why do marketing teams need a design system for their website?', cluster: 'C6', gap_score: 0.1920 },
      { query_id: 'q_37', query_text: 'What is a design system in the context of website building tools?', cluster: 'C5', gap_score: 0.1901 },
    ],
  },
];

// ─── Cluster Recommendations ─────────────────────────────────────────────────

export const CLUSTER_RECOMMENDATIONS: { cluster_id: string; cluster_name: string; recommendation: string; priority: 'high' | 'medium' | 'low'; key_actions: string[] }[] = [
  { cluster_id: 'C6', cluster_name: 'Problem/Awareness', priority: 'high', recommendation: 'Largest average gap. Create problem-focused content targeting WordPress migration pain points and marketing team bottlenecks.', key_actions: ['Create step-by-step migration guides', 'Add FAQ sections (23% of citations use them)', 'Target 1,685 avg word count', 'Address developer dependency explicitly'] },
  { cluster_id: 'C3', cluster_name: 'Category Comparison', priority: 'high', recommendation: 'High gap with strong table and FAQ usage. Build comparison content with structured data tables.', key_actions: ['Include comparison tables (39% citation rate)', 'Add FAQ sections (36% rate)', 'Target 1,858 avg word count', 'Cover headless CMS vs visual builder tradeoffs'] },
  { cluster_id: 'C5', cluster_name: 'Definition', priority: 'high', recommendation: 'Multiple high-gap definition queries. Create authoritative glossary-style content with clear definitions.', key_actions: ['Open with clear definitions (55% of citations do this)', 'Target 1,690 avg word count', 'Cover headless CMS, design systems, staging environments', 'Add FAQ sections for related questions'] },
  { cluster_id: 'C4', cluster_name: 'Decision Criteria', priority: 'medium', recommendation: 'Create decision frameworks with TCO analysis and evaluation checklists.', key_actions: ['Include data tables for TCO comparison', 'Add step-by-step evaluation guides (30% rate)', 'Target 2,055 avg word count', 'Reference third-party research (35% rate)'] },
  { cluster_id: 'C1', cluster_name: 'Mechanism', priority: 'medium', recommendation: 'Technical content explaining how website builders work under the hood.', key_actions: ['Focus on step-by-step explanations (35% rate)', 'Target 1,740 avg word count', 'Include code examples where relevant', 'Cover responsive design, semantic HTML, rendering'] },
  { cluster_id: 'C7', cluster_name: 'Best-of/Consideration', priority: 'medium', recommendation: 'Build listicle-style content optimized for "best X" queries.', key_actions: ['Include comparison tables (29% rate)', 'Add key takeaways summaries', 'Target 1,748 avg word count', 'Focus on enterprise security, SSO, scalability'] },
  { cluster_id: 'C9', cluster_name: 'Feature Verification', priority: 'medium', recommendation: 'Create detailed feature documentation answering specific "does X support Y?" questions.', key_actions: ['Add FAQ sections (22% rate)', 'Include step-by-step guides (28% rate)', 'Target 1,423 avg word count', 'Cover SSO, staging, SCIM, scalability'] },
  { cluster_id: 'C2', cluster_name: 'Boundary', priority: 'low', recommendation: 'Address limitations honestly with workarounds and boundary definitions.', key_actions: ['Include comparison tables (29% rate)', 'Target 1,596 avg word count', 'Address scalability and custom code limitations', 'Highlight key takeaways (16% rate)'] },
  { cluster_id: 'C8', cluster_name: 'Branded Evaluation', priority: 'low', recommendation: 'Company already performs relatively well here. Maintain and update existing comparison content.', key_actions: ['Keep comparison tables updated (40% rate)', 'Maintain FAQ sections (38% rate)', 'Update key takeaways (29% rate)', 'Target 1,821 avg word count'] },
];

// ─── Derived Helpers ─────────────────────────────────────────────────────────

export function getClassificationCounts(queries: QueryData[]) {
  const counts = { significant_gap: 0, gap_to_close: 0, roughly_equal: 0, company_wins: 0 };
  for (const q of queries) counts[q.classification]++;
  return counts;
}

export function getQueriesByCluster(queries: QueryData[]) {
  const grouped: Record<string, QueryData[]> = {};
  for (const q of queries) {
    if (!grouped[q.cluster_id]) grouped[q.cluster_id] = [];
    grouped[q.cluster_id].push(q);
  }
  return grouped;
}

export function getClusterAvgGap(queries: QueryData[], cluster_id: string) {
  const clusterQueries = queries.filter((q) => q.cluster_id === cluster_id);
  if (clusterQueries.length === 0) return 0;
  return clusterQueries.reduce((sum, q) => sum + q.gap_score, 0) / clusterQueries.length;
}

export function getTopGapQueries(queries: QueryData[], n: number = 25) {
  return [...queries].sort((a, b) => b.gap_score - a.gap_score).slice(0, n);
}

export const CLUSTER_IDS = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9'] as const;
export const CLUSTER_NAMES: Record<string, string> = {
  C1: 'Mechanism', C2: 'Boundary', C3: 'Category Comparison', C4: 'Decision Criteria',
  C5: 'Definition', C6: 'Problem/Awareness', C7: 'Best-of/Consideration',
  C8: 'Branded Evaluation', C9: 'Feature Verification',
};

export const CLUSTER_COLORS: Record<string, string> = {
  C1: '#d97757', C2: '#6a9bcc', C3: '#788c5d', C4: '#e8926d', C5: '#4a7ba8',
  C6: '#5a6f45', C7: '#c4593a', C8: '#9abfdb', C9: '#a3b88e',
};
