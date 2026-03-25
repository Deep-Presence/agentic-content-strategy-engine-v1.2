// Data layer for Topic Discovery — loads real pipeline artifacts
import taxonomyRaw from '@/../data/result-draft/artifacts/topic_discovery/lovable/taxonomy/v2.json';
import matrixRaw from '@/../data/result-draft/artifacts/topic_discovery/lovable/matrix/v2.json';
import coverageRaw from '@/../data/result-draft/artifacts/topic_discovery/lovable/raw/coverage_v1.json';
import scoringRaw from '@/../data/result-draft/artifacts/topic_discovery/lovable/scoring/v1.json';
import personaAffinityRaw from '@/../data/result-draft/artifacts/topic_discovery/lovable/persona_affinity/v1.json';

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

// ─── Data Loading ────────────────────────────────────────

const taxonomy = taxonomyRaw as {
  domain_name: string;
  version: number;
  status: string;
  root_nodes: CategoryNode[];
};

const matrix = matrixRaw as {
  version: number;
  status: string;
  assignments: Assignment[];
};

const coverage = coverageRaw as CoverageData;

const scoring = scoringRaw as {
  version: number;
  scores: ScoringEntry[];
};

const personaAffinity = personaAffinityRaw as {
  version: number;
  persona_entries: Record<string, Array<{
    subdomain_id: string;
    subdomain_name: string;
    affinity_score: number;
  }>>;
};

// ─── Computed Data ───────────────────────────────────────

// Build scoring lookup by subdomain_id
const scoringMap = new Map<string, ScoringEntry>();
for (const entry of scoring.scores) {
  scoringMap.set(entry.subdomain_id, entry);
}

// Build persona affinity lookup by subdomain_id
const affinityMap = new Map<string, Record<string, number>>();
for (const [personaId, entries] of Object.entries(personaAffinity.persona_entries)) {
  for (const entry of entries) {
    if (!affinityMap.has(entry.subdomain_id)) {
      affinityMap.set(entry.subdomain_id, {});
    }
    affinityMap.get(entry.subdomain_id)![personaId] = entry.affinity_score;
  }
}

// Build assignment lookup by subdomain_id
const assignmentsBySubdomain = new Map<string, Assignment[]>();
for (const a of matrix.assignments) {
  if (!assignmentsBySubdomain.has(a.subdomain_id)) {
    assignmentsBySubdomain.set(a.subdomain_id, []);
  }
  assignmentsBySubdomain.get(a.subdomain_id)!.push(a);
}

// ─── Exported Data ───────────────────────────────────────

export const categories: CategoryNode[] = taxonomy.root_nodes;
export const companyName = 'Lovable';
export const domainName = taxonomy.domain_name;
export const taxonomyVersion = taxonomy.version;

export function getScoring(subdomainId: string): ScoringEntry | undefined {
  return scoringMap.get(subdomainId);
}

export function getPersonaAffinity(subdomainId: string): Record<string, number> {
  return affinityMap.get(subdomainId) ?? {};
}

export function getAssignments(subdomainId: string): Assignment[] {
  return assignmentsBySubdomain.get(subdomainId) ?? [];
}

export function getAllAssignments(): Assignment[] {
  return matrix.assignments;
}

export function getCoverage(): CoverageData {
  return coverage;
}

// ─── Computed Stats ──────────────────────────────────────

export function getCategoryStats(cat: CategoryNode) {
  const subdomains = cat.children;
  const avgScore = subdomains.length > 0
    ? subdomains.reduce((sum, s) => sum + (s.priority_score || 0), 0) / subdomains.length
    : 0;
  const totalAssignments = subdomains.reduce(
    (sum, s) => sum + (getAssignments(s.id).length),
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
