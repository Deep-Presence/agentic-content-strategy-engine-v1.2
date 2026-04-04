/**
 * Adapters — transform backend Topic Discovery API responses
 * into frontend Assignment / Cluster / RejectedItem types.
 */

import type { SubdomainNodeAPI, TopicAssignmentAPI, PersonaSubdomainEntryAPI } from './types';
import type { Assignment, Cluster, RejectedItem } from '../_components/planner-data';

// ── Taxonomy helpers ────────────────────────────────────

export interface TaxonomyMapEntry {
  clusterName: string;
  subdomainName: string;
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
      node,
    });
    for (const child of node.children) {
      walk(child, clusterName);
    }
  }

  for (const root of rootNodes) {
    // Root nodes (depth 0) are clusters — use their own name as clusterName
    walk(root, root.name);
  }

  return map;
}

// ── Cluster builder ─────────────────────────────────────

/**
 * Convert SubdomainNodeAPI root nodes into the frontend Cluster[] shape.
 * Each root becomes a Cluster; its direct children become subclusters
 * with citOpp derived from priority_score.
 */
export function buildClusters(rootNodes: SubdomainNodeAPI[]): Cluster[] {
  return rootNodes.map((root) => ({
    id: root.id,
    name: root.name,
    subclusters: root.children.map((child) => ({
      id: child.id,
      name: child.name,
      citOpp: child.priority_score,
    })),
  }));
}

// ── Persona scores ──────────────────────────────────────

export interface PersonaScores {
  sf: number;
  pm: number;
  da: number;
  te: number;
}

const PERSONA_KEY_ORDER: readonly string[] = ['sf', 'pm', 'da', 'te'];

/**
 * Convert the backend persona_entries dict into a lookup map
 * keyed by subdomain_id. Affinity scores (0-1) are scaled to 0-100.
 *
 * The backend groups entries by persona key (e.g. "sf", "pm").
 * Each entry contains subdomain_id + affinity_score.
 * We invert this into a per-subdomain view with all 4 persona scores.
 */
export function buildPersonaScoresMap(
  personaEntries: Record<string, PersonaSubdomainEntryAPI[]>,
): Map<string, PersonaScores> {
  const map = new Map<string, PersonaScores>();

  for (const personaKey of PERSONA_KEY_ORDER) {
    const entries = personaEntries[personaKey];
    if (!entries) continue;

    for (const entry of entries) {
      let scores = map.get(entry.subdomain_id);
      if (!scores) {
        scores = { sf: 0, pm: 0, da: 0, te: 0 };
        map.set(entry.subdomain_id, scores);
      }
      const scaled = Math.round(entry.affinity_score * 100);
      if (personaKey === 'sf') scores.sf = scaled;
      else if (personaKey === 'pm') scores.pm = scaled;
      else if (personaKey === 'da') scores.da = scaled;
      else if (personaKey === 'te') scores.te = scaled;
    }
  }

  return map;
}

// ── Single assignment adapter ───────────────────────────

function capitalizeFirst(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Convert a single TopicAssignmentAPI into a frontend Assignment.
 */
export function adaptAssignment(
  item: TopicAssignmentAPI,
  taxonomyMap: Map<string, TaxonomyMapEntry>,
  personaScoresMap: Map<string, PersonaScores>,
  matrixCreatedAt: string | null,
): Assignment {
  const createdAt = matrixCreatedAt ?? new Date().toISOString();

  return {
    id: item.id,
    title: item.topic_text,
    cluster: taxonomyMap.get(item.subdomain_id)?.clusterName ?? 'Uncategorized',
    subcluster: item.subdomain_name,
    stage: item.buyer_stage.toUpperCase() as 'TOFU' | 'MOFU' | 'BOFU',
    intent: capitalizeFirst(item.intent_type) as Assignment['intent'],
    format: null as unknown as Assignment['format'],
    source: item.is_manually_added ? 'custom' : 'gap',
    initiative: undefined,
    personaScores: personaScoresMap.get(item.subdomain_id) ?? { sf: 0, pm: 0, da: 0, te: 0 },
    persona: item.persona_id,
    estCitations: Math.round(item.priority_score * 25),
    citationOpp: item.priority_score,
    priorityScore: item.priority_score,
    effort: null as unknown as Assignment['effort'],
    estDays: null as unknown as Assignment['estDays'],
    competitors: [],
    reasons: [],
    relatedQueries: [],
    createdAt,
    activityLog: [
      {
        action: 'Created by topic discovery pipeline',
        date: matrixCreatedAt ?? '',
        by: 'Pipeline',
      },
    ],
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
