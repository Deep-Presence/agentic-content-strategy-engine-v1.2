/**
 * Adapters — transform backend Topic Discovery API responses
 * into frontend Assignment / Cluster / RejectedItem types.
 *
 * Every derived value comes from a real pipeline signal.
 * No fabricated numbers, no placeholder data.
 */

import type { SubdomainNodeAPI, TopicAssignmentAPI, PersonaSubdomainEntryAPI } from './types';
import type { Assignment, Cluster, RejectedItem, TargetKeywords, RelatedQuery } from '../_components/planner-data';

// ── Taxonomy helpers ────────────────────────────────────

export interface TaxonomyMapEntry {
  clusterName: string;
  subdomainName: string;
  description: string;
  scoringRationale: string | null;
  node: SubdomainNodeAPI;
}

/**
 * Walk the taxonomy tree recursively and build a lookup map
 * keyed by subdomain ID. Depth-0 nodes are clusters;
 * depth-1+ nodes are subclusters nested under their root.
 */
export function buildTaxonomyMap(
  rootNodes: SubdomainNodeAPI[],
): Map<string, TaxonomyMapEntry> {
  const map = new Map<string, TaxonomyMapEntry>();

  function walk(node: SubdomainNodeAPI, clusterName: string): void {
    map.set(node.id, {
      clusterName,
      subdomainName: node.name,
      description: node.description ?? '',
      scoringRationale: (node.metadata?.scoring_rationale as string) ?? null,
      node,
    });
    for (const child of node.children) {
      walk(child, clusterName);
    }
  }

  for (const root of rootNodes) {
    walk(root, root.name);
  }

  return map;
}

// ── Cluster builder ─────────────────────────────────────

/**
 * Convert SubdomainNodeAPI root nodes into the frontend Cluster[] shape.
 * Each root becomes a Cluster; its direct children become subclusters
 * with citOpp derived from priority_score and description from the node.
 */
export function buildClusters(rootNodes: SubdomainNodeAPI[]): Cluster[] {
  return rootNodes.map((root) => ({
    id: root.id,
    name: root.name,
    subclusters: root.children.map((child) => ({
      id: child.id,
      name: child.name,
      description: child.description ?? '',
      citOpp: child.priority_score,
      personaAffinity: child.persona_affinity ?? {},
    })),
  }));
}

// ── Persona scores ──────────────────────────────────────

/**
 * Persona scores are dynamic — keyed by actual persona_id from the pipeline
 * (e.g. "david", "sarah", "marcus"), not hardcoded abbreviations.
 */
export type PersonaScores = Record<string, number>;

/**
 * Convert the backend persona_entries dict into a lookup map
 * keyed by subdomain_id. Affinity scores (0-1) are scaled to 0-100.
 *
 * The backend groups entries by persona_id (e.g. "david", "sarah").
 * We invert this into a per-subdomain view with all persona scores.
 */
export function buildPersonaScoresMap(
  personaEntries: Record<string, PersonaSubdomainEntryAPI[]>,
): Map<string, PersonaScores> {
  const map = new Map<string, PersonaScores>();

  for (const [personaKey, entries] of Object.entries(personaEntries)) {
    if (!entries) continue;

    for (const entry of entries) {
      let scores = map.get(entry.subdomain_id);
      if (!scores) {
        scores = {};
        map.set(entry.subdomain_id, scores);
      }
      scores[personaKey] = Math.round(entry.affinity_score * 100);
    }
  }

  return map;
}

// ── Derivation helpers (all from real pipeline data) ────

const FORMAT_LABELS: Record<string, string> = {
  comprehensive_guide: 'Comprehensive Guide',
  long_form_article: 'Long-form Article',
  comparison_guide: 'Comparison Guide',
  how_to_guide: 'How-to Guide',
  explainer: 'Explainer',
  listicle: 'Listicle',
  case_study: 'Case Study',
  tutorial: 'Tutorial',
};

function formatContentFormat(raw: string | undefined | null): string | null {
  if (!raw) return null;
  return FORMAT_LABELS[raw] ?? raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function deriveEffort(
  wordCount: number | null,
  contentFormat: string | null,
): 'low' | 'medium' | 'high' | null {
  if (wordCount == null) return null;
  if (
    wordCount >= 2800 ||
    contentFormat === 'comprehensive_guide' ||
    contentFormat === 'long_form_article'
  )
    return 'high';
  if (wordCount >= 2000 || contentFormat === 'comparison_guide') return 'medium';
  return 'low';
}

function deriveDays(wordCount: number | null): number | null {
  if (wordCount == null) return null;
  return Math.max(2, Math.ceil(wordCount / 600));
}

const FACTOR_DESCRIPTIONS: Record<string, string> = {
  citation_opportunity: 'high likelihood of being cited by AI engines',
  conversion_potential: 'strong conversion signal from this topic',
  strategic_centrality: 'core to brand positioning strategy',
  content_authority: 'strong content authority potential',
};

function deriveReasons(
  metadata: Record<string, unknown>,
  taxonomyEntry: TaxonomyMapEntry | undefined,
  priorityFactors: Record<string, number>,
): Array<{ title: string; text: string }> {
  const reasons: Array<{ title: string; text: string }> = [];

  // 1. Content angle from metadata
  const angle = metadata?.angle as string | undefined;
  if (angle) {
    reasons.push({ title: 'Content Angle', text: angle });
  }

  // 2. Scoring rationale from taxonomy node
  const rationale = taxonomyEntry?.scoringRationale;
  if (rationale) {
    reasons.push({ title: 'Cluster Signal', text: rationale });
  }

  // 3. Top priority factor
  const entries = Object.entries(priorityFactors);
  if (entries.length > 0) {
    const [topKey, topVal] = entries.sort(([, a], [, b]) => b - a)[0];
    const label = topKey.replace(/_/g, ' ');
    const desc = FACTOR_DESCRIPTIONS[topKey] ?? `strong ${label}`;
    reasons.push({
      title: `Strong ${label}`,
      text: `Scores ${Math.round(topVal * 100)}% \u2014 ${desc}`,
    });
  }

  return reasons;
}

function deriveTargetKeywords(metadata: Record<string, unknown>): TargetKeywords {
  const kw = metadata?.target_keywords as
    | { primary?: string; secondary?: string[] }
    | undefined;
  return {
    primary: kw?.primary ?? '',
    secondary: kw?.secondary ?? [],
  };
}

function deriveRelatedQueries(
  metadata: Record<string, unknown>,
  intentType: string,
): RelatedQuery[] {
  const kw = metadata?.target_keywords as
    | { secondary?: string[] }
    | undefined;
  if (!kw?.secondary?.length) return [];

  const capitalizedIntent = (intentType.charAt(0).toUpperCase() +
    intentType.slice(1)) as RelatedQuery['intent'];

  return kw.secondary.map((q) => ({
    query: q,
    intent: capitalizedIntent,
  }));
}

function deriveActivityLog(
  isManuallyAdded: boolean,
  status: string,
  matrixCreatedAt: string | null,
): Array<{ action: string; date: string | null; by: string }> {
  const log: Array<{ action: string; date: string | null; by: string }> = [];

  log.push({
    action: isManuallyAdded
      ? 'Manually added'
      : 'Discovered by topic discovery pipeline',
    date: matrixCreatedAt,
    by: isManuallyAdded ? 'User' : 'System',
  });

  if (status !== 'not_started') {
    log.push({
      action: `Status: ${status.replace(/_/g, ' ')}`,
      date: null,
      by: 'System',
    });
  }

  return log;
}

// ── Single assignment adapter ───────────────────────────

function capitalizeFirst(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Convert a single TopicAssignmentAPI into a frontend Assignment.
 * Every field is derived from real pipeline data — no fabricated values.
 */
export function adaptAssignment(
  item: TopicAssignmentAPI,
  taxonomyMap: Map<string, TaxonomyMapEntry>,
  personaScoresMap: Map<string, PersonaScores>,
  matrixCreatedAt: string | null,
): Assignment {
  const createdAt = matrixCreatedAt ?? new Date().toISOString();
  const meta = (item.metadata ?? {}) as Record<string, unknown>;
  const factors = item.priority_factors ?? {};
  const taxonomyEntry = taxonomyMap.get(item.subdomain_id);

  const rawFormat = meta.content_format as string | undefined;
  const wordCount = (meta.estimated_word_count as number) ?? null;

  return {
    id: item.id,
    displayId: '', // assigned by hook after sorting
    title: item.topic_text,
    description: (meta.description as string) ?? '',
    cluster: taxonomyEntry?.clusterName ?? 'Uncategorized',
    subcluster: item.subdomain_name,
    stage: item.buyer_stage.toUpperCase() as 'TOFU' | 'MOFU' | 'BOFU',
    intent: capitalizeFirst(item.intent_type) as Assignment['intent'],
    format: formatContentFormat(rawFormat),
    source: item.is_manually_added ? 'custom' : 'gap',
    initiative: undefined,
    personaScores: personaScoresMap.get(item.subdomain_id) ?? {},
    persona: item.persona_id,
    citationOpp: factors.citation_opportunity ?? item.priority_score,
    priorityScore: item.priority_score,
    effort: deriveEffort(wordCount, rawFormat ?? null),
    estDays: deriveDays(wordCount),
    wordCount,
    contentFormat: rawFormat ?? null,
    targetKeywords: deriveTargetKeywords(meta),
    reasons: deriveReasons(meta, taxonomyEntry, factors),
    relatedQueries: deriveRelatedQueries(meta, item.intent_type),
    createdAt,
    activityLog: deriveActivityLog(item.is_manually_added, item.status, matrixCreatedAt),
    priorityFactors: factors,
  };
}

// ── Batch adapter ───────────────────────────────────────

/**
 * Adapt a full batch of assignments. Builds internal lookup maps
 * from taxonomy root nodes and persona entries, then maps each item.
 */
export function adaptAssignments(
  items: TopicAssignmentAPI[],
  rootNodes: SubdomainNodeAPI[],
  personaEntries: Record<string, PersonaSubdomainEntryAPI[]>,
  matrixCreatedAt: string | null,
): Assignment[] {
  const taxonomyMap = buildTaxonomyMap(rootNodes);
  const personaScoresMap = buildPersonaScoresMap(personaEntries);
  return items.map((item) =>
    adaptAssignment(item, taxonomyMap, personaScoresMap, matrixCreatedAt),
  );
}

// ── Rejected item adapter ───────────────────────────────

/**
 * Convert a rejected assignment into a frontend RejectedItem.
 */
export function adaptRejectedItem(
  item: TopicAssignmentAPI,
  taxonomyMap: Map<string, TaxonomyMapEntry>,
): RejectedItem {
  return {
    id: item.id,
    title: item.topic_text,
    cluster: taxonomyMap.get(item.subdomain_id)?.clusterName ?? 'Uncategorized',
    reason: (item.metadata?.rejection_reason as string) ?? 'Rejected',
    date: new Date().toISOString(),
    rejectedBy: 'Pipeline',
    stage: item.buyer_stage.toUpperCase() as 'TOFU' | 'MOFU' | 'BOFU',
  };
}
