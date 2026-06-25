/**
 * API response types for Brand Hub / Artifacts endpoints.
 * Mirrors backend Pydantic schemas exactly.
 */

// ── Voice Style Guide ───────────────────────────────────

export interface VoiceGuideResponse {
  slug: string;
  guide_md: string;
  version: number;
  word_count: number;
  last_updated: string | null;
  source_authors: string[];
}

// ── Audience Persona ────────────────────────────────────

export interface PersonaListItemAPI {
  persona_id: string;
  persona_name: string;
  tagline: string;
  kind: string;
  status: string;
  current_version: number;
  last_updated: string | null;
  created_by: string;
  word_count: number;
}

export interface PersonaListResponseAPI {
  slug: string;
  personas: PersonaListItemAPI[];
  total: number;
}

// ── Knowledge Base Health ───────────────────────────────

export interface KBDocHealthAPI {
  doc_type: string;
  status: string;
  current_version: number;
  last_updated: string | null;
  age_days: number;
  staleness_threshold_days: number;
  stale_reason: string | null;
  dependencies: string[];
}

export interface KBHealthResponseAPI {
  slug: string;
  overall_score: number;
  doc_health: Record<string, KBDocHealthAPI>;
  synthesis_version: number;
  synthesis_last_updated: string | null;
  synthesis_needs_refresh: boolean;
  stale_docs: string[];
  missing_docs: string[];
  last_full_refresh: string | null;
}

// ── Artifact File Listing ───────────────────────────────

export interface ArtifactFileListResponse {
  artifact_type: string;
  slug: string;
  files: { name: string; size: number }[];
}

// ── Version Entry (shared across all detail views) ──────

export interface VersionEntry {
  /** Numeric version for pipeline-generated files, or -1 for user uploads */
  version: number;
  /** Display label: "v2" for versioned, or filename for uploads */
  label: string;
  /** Whether this is the current/latest pipeline version */
  current: boolean;
  /** The relative file path (for fetching). e.g. "company_overview/v2.md" or "guide/my-doc.md" */
  filePath: string;
  /** True if this is a user-uploaded file (not pipeline-generated) */
  isUpload?: boolean;
}

// ── KB Doc Types ────────────────────────────────────────

export const KB_DOC_TYPES = [
  'company_overview',
  'brand_perception',
  'competitor_registry',
  'customer_reviews',
  'weakness_analysis',
] as const;

export type KBDocType = (typeof KB_DOC_TYPES)[number];
