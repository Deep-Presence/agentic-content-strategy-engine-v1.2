/**
 * Topic Discovery types and pure utility functions.
 * Data is fetched from API hooks (useTopicDiscovery), not from local artifacts.
 */

// ─── Types ───────────────────────────────────────────────

export interface SourceProvenance {
  source_a?: boolean;
  source_b?: boolean;
  source_c?: boolean;
  source_d?: boolean;
}

export interface PriorityFactors {
  strategic_centrality: number;
  citation_opportunity: number;
  content_authority: number;
  conversion_potential: number;
}

export interface SubdomainNode {
  id: string;
  name: string;
  description: string;
  depth: number;
  source_provenance: SourceProvenance;
  confidence: number;
  sort_order: number;
  children: SubdomainNode[];
  metadata: {
    llm_composite?: number;
    scoring_rationale?: string;
    scoring_source?: string;
    persona_rationale?: Record<string, string>;
  };
  priority_score: number;
  priority_factors: PriorityFactors;
  persona_affinity: Record<string, number>;
  expansion_status: string;
}

export interface CategoryNode {
  id: string;
  name: string;
  description: string;
  depth: number;
  source_provenance: SourceProvenance;
  confidence: number;
  sort_order: number;
  children: SubdomainNode[];
}

export interface Assignment {
  id: string;
  subdomain_id: string;
  subdomain_name: string;
  topic_text: string;
  buyer_stage: 'tofu' | 'mofu' | 'bofu';
  intent_type: 'informational' | 'commercial' | 'transactional' | 'navigational';
  audience_segment: string;
  audience_segment_type: string;
  relevance: string;
  priority_score: number;
  priority_factors: Record<string, number>;
  status: 'not_started' | 'in_gap_analysis' | 'content_produced' | 'published';
  is_manually_added: boolean;
  metadata: {
    slug?: string;
    angle?: string;
    description?: string;
    target_keywords?: { primary: string; secondary: string[] };
    ai_citation_potential?: string;
    content_format?: string;
    estimated_word_count?: number;
  };
  persona_id: string;
  persona_name: string;
}

export interface CoverageData {
  sample_coverage: number;
  observed_count: number;
  chao1_lower_bound: number;
  median_estimate: number;
  estimate_range: number[];
  pairwise_estimates: Record<string, number>;
  per_source_coverage: Record<string, {
    source: string;
    observed: number;
    chao1_estimate: number;
    sample_coverage: number;
  }>;
}

export interface ScoringEntry {
  subdomain_id: string;
  subdomain_name: string;
  composite_score: number;
  signal_scores: {
    strategic_centrality: number;
    citation_opportunity: number;
    content_authority: number;
    conversion_potential: number;
    source_confidence: number;
  };
  rank: number;
}

// ─── Persona Labels ──────────────────────────────────────

export const PERSONA_MAP: Record<string, { short: string; full: string }> = {
  david: { short: 'DA', full: 'Agency Owner' },
  sarah: { short: 'PM', full: 'Product Manager' },
  marcus: { short: 'SF', full: 'Solo Founder' },
};

export const PERSONA_IDS = Object.keys(PERSONA_MAP);

// ─── Format Labels ───────────────────────────────────────

export const FORMAT_LABELS: Record<string, string> = {
  long_form_article: 'Article',
  comparison_guide: 'Comparison',
  how_to_guide: 'How-To',
  decision_framework: 'Framework',
  checklist: 'Checklist',
  case_study: 'Case Study',
  explainer: 'Explainer',
  comprehensive_guide: 'Guide',
  buyers_guide: "Buyer's Guide",
  evaluation_framework: 'Eval Framework',
  tactical_guide: 'Tactical Guide',
  objection_handling: 'Objection Handler',
  roi_calculator: 'ROI Calculator',
};

// ─── Pure Utility Functions ──────────────────────────────

export function getCategoryStats(cat: CategoryNode, assignmentsBySubdomain: Map<string, Assignment[]>) {
  const subdomains = cat.children;
  const avgScore = subdomains.length > 0
    ? subdomains.reduce((sum, s) => sum + (s.priority_score || 0), 0) / subdomains.length
    : 0;
  const totalAssignments = subdomains.reduce(
    (sum, s) => sum + (assignmentsBySubdomain.get(s.id)?.length ?? 0),
    0
  );
  return { avgScore, totalAssignments, count: subdomains.length };
}

export function getSourceCount(provenance: SourceProvenance): number {
  return Object.values(provenance).filter(Boolean).length;
}

export type SortDimension = 'citation' | 'feasibility' | 'return';

export function getSortScore(sub: SubdomainNode, dimension: SortDimension): number {
  const factors = sub.priority_factors;
  if (!factors) return sub.priority_score || 0;
  switch (dimension) {
    case 'citation':
      return factors.citation_opportunity ?? 0;
    case 'feasibility':
      return factors.content_authority ?? 0;
    case 'return':
      return sub.priority_score ?? 0;
  }
}
