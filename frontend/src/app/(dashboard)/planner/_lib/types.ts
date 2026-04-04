/**
 * Content Planner API response types — mirrors backend Topic Discovery schemas.
 */

// ── Topic Assignment ────────────────────────────────────

export interface TopicAssignmentAPI {
  id: string;
  subdomain_id: string;
  subdomain_name: string;
  topic_text: string;
  buyer_stage: 'tofu' | 'mofu' | 'bofu';
  intent_type: 'informational' | 'commercial' | 'navigational' | 'transactional';
  audience_segment: string;
  audience_segment_type: string;
  relevance: string;
  priority_score: number;
  priority_factors: Record<string, number>;
  status: string;
  is_manually_added: boolean;
  metadata: Record<string, unknown>;
  persona_id: string;
  persona_name: string;
}

export interface AssignmentListResponseAPI {
  slug: string;
  items: TopicAssignmentAPI[];
  total: number;
  page: number;
  page_size: number;
}

// ── Discovery Summary ───────────────────────────────────

export interface DiscoverySummaryResponseAPI {
  slug: string;
  company_name: string;
  has_taxonomy: boolean;
  taxonomy_version: number;
  has_matrix: boolean;
  matrix_version: number;
  scoring_version: number;
  persona_affinity_version: number;
  status: string | null;
  last_updated: string | null;
}

// ── Taxonomy ────────────────────────────────────────────

export interface SubdomainNodeAPI {
  id: string;
  name: string;
  description: string;
  depth: number;
  source_provenance: Record<string, boolean>;
  confidence: number;
  priority_score: number;
  persona_affinity: Record<string, number>;
  expansion_status: string;
  children: SubdomainNodeAPI[];
  metadata: Record<string, unknown>;
}

export interface TaxonomyReadResponseAPI {
  slug: string;
  taxonomy: {
    id: string;
    domain_name: string;
    version: number;
    root_nodes: SubdomainNodeAPI[];
    total_subdomains: number;
    coverage_score: number;
    [key: string]: unknown;
  };
  version: number;
  total_subdomains: number;
  coverage_score: number;
}

// ── Persona Affinity ────────────────────────────────────

export interface PersonaSubdomainEntryAPI {
  subdomain_id: string;
  subdomain_name: string;
  affinity_score: number;
  provenance: string;
  pain_points: string[];
}

export interface PersonaAffinityResponseAPI {
  slug: string;
  persona_entries: Record<string, PersonaSubdomainEntryAPI[]>;
  total_personas: number;
  total_subdomains: number;
}

// ── Status Update ───────────────────────────────────────

export interface AssignmentStatusUpdateResponseAPI {
  assignment_id: string;
  status: string;
  message: string;
}
