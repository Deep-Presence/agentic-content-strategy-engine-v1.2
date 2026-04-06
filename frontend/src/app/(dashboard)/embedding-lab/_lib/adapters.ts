/**
 * Adapters: transform backend snake_case API responses to frontend camelCase types.
 */
import type {
  ClusterProfileAPI,
  ClusterProfileListAPI,
  EmbeddingPointAPI,
  TerritoryGapQueryAPI,
  TerritoryGapsResponseAPI,
} from './types';
import type {
  ClusterProfile,
  CompanySignals,
  ContentBrief,
  DomainEntry,
  EmbeddingPoint,
  GapExemplar,
  GapQuery,
  ProximityStats,
  SPAResult,
} from '../_components/data';
import { CLUSTER_COLORS } from '../_components/data';

// ── Classification label mapping ─────────────────────────────
// Backend uses: significant_gap, gap_to_close, roughly_equal, company_wins
// Frontend uses: significant_gap, moderate_gap, minor_gap, no_gap

const CLASSIFICATION_MAP: Record<string, string> = {
  significant_gap: 'significant_gap',
  gap_to_close: 'moderate_gap',
  roughly_equal: 'minor_gap',
  company_wins: 'no_gap',
};

function mapClassification(backend: string): string {
  return CLASSIFICATION_MAP[backend] ?? backend;
}

// ── Cluster Profiles ─────────────────────────────────────────

function toClusterProfile(id: string, api: ClusterProfileAPI): ClusterProfile {
  return {
    id,
    name: api.cluster_name,
    queryCount: api.query_count,
    totalCitations: api.total_citations,
    uniqueDomains: api.unique_domains,
    companyCitations: api.company_citations,
    companyShare: api.company_share,
    companyRank: api.company_rank,
    presence: api.presence as ClusterProfile['presence'],
    avgWordCount: api.avg_word_count,
    wordCountRange: api.word_count_range,
    dominantContentType: api.dominant_content_type ?? '',
    dominantAuthorityType: api.dominant_authority_type ?? '',
    structuralRates: api.structural_rates,
    faqRate: api.faq_rate,
    tableRate: api.table_rate,
    requiredElements: api.required_elements,
    exemplarThemes: api.exemplar_themes,
    authoritySignals: api.authority_signals,
    proximity: api.proximity,
    engineBreakdown: api.engine_breakdown,
    topDomains: api.top_domains.map((d): DomainEntry => ({
      domain: d.domain,
      citations: d.citations,
      isCompany: d.is_company,
      share: d.share,
      type: d.type as DomainEntry['type'],
    })),
    color: CLUSTER_COLORS[id] || '#888',
  };
}

export function toClusterProfiles(
  api: ClusterProfileListAPI,
): Record<string, ClusterProfile> {
  const result: Record<string, ClusterProfile> = {};
  for (const [id, profile] of Object.entries(api.profiles)) {
    result[id] = toClusterProfile(id, profile);
  }
  return result;
}

// ── Gap Queries ──────────────────────────────────────────────

function toGapExemplar(api: TerritoryGapQueryAPI['exemplars'][number]): GapExemplar {
  return {
    domain: api.domain,
    url: api.url,
    similarity: api.similarity,
    contentType: api.content_type,
    authorityType: api.authority_type,
    wordCount: api.word_count,
    headerCount: api.header_count,
    hasFaq: api.has_faq,
    hasTables: api.has_tables,
    readingLevel: api.reading_level,
    listItemCount: api.list_item_count,
    statCount: api.stat_count,
    citationCount: api.citation_count,
  };
}

function toCompanySignals(
  api: TerritoryGapQueryAPI['company_signals'],
): CompanySignals | null {
  if (!api) return null;
  return {
    wordCount: api.word_count,
    headerCount: api.header_count,
    hasFaq: api.has_faq,
    hasTables: api.has_tables,
    readingLevel: api.reading_level,
    listItemCount: api.list_item_count,
  };
}

function toContentBrief(
  api: TerritoryGapQueryAPI['content_brief'],
): ContentBrief {
  if (!api) {
    return {
      wordCountRange: null,
      readingLevelRange: null,
      headerCountRange: null,
      headerHierarchy: null,
      hasFaq: 0,
      hasTables: 0,
      hasDefinition: 0,
      hasKeyTakeaways: 0,
      hasStepByStep: 0,
      dominantContentType: null,
      dominantAuthorityType: null,
      dataDensity: null,
      citationDensity: null,
    };
  }
  return {
    wordCountRange: api.word_count_range,
    readingLevelRange: api.reading_level_range,
    headerCountRange: api.header_count_range,
    headerHierarchy: api.header_hierarchy,
    hasFaq: api.has_faq,
    hasTables: api.has_tables,
    hasDefinition: api.has_definition,
    hasKeyTakeaways: api.has_key_takeaways,
    hasStepByStep: api.has_step_by_step,
    dominantContentType: api.dominant_content_type,
    dominantAuthorityType: api.dominant_authority_type,
    dataDensity: api.data_density,
    citationDensity: api.citation_density,
  };
}

function toGapQuery(api: TerritoryGapQueryAPI): GapQuery {
  return {
    id: api.id,
    query: api.query,
    cluster: api.cluster,
    clusterId: api.cluster_id,
    gap: api.gap,
    classification: mapClassification(api.classification),
    companyCited: api.company_cited,
    companyUrl: api.company_url,
    companySimilarity: api.company_similarity,
    avgCitationSimilarity: api.avg_citation_similarity,
    exemplars: api.exemplars.map(toGapExemplar),
    companySignals: toCompanySignals(api.company_signals),
    contentBrief: toContentBrief(api.content_brief),
  };
}

export interface TerritoryGapsData {
  gapQueries: GapQuery[];
  proximityStats: ProximityStats;
  spaResult: SPAResult;
  perClusterProximity: Record<string, { mean: number; std: number; min: number; max: number; count: number }>;
  totalGaps: number;
  uncoveredQueries: number;
}

export function toTerritoryGaps(api: TerritoryGapsResponseAPI): TerritoryGapsData {
  return {
    gapQueries: api.gaps.map(toGapQuery),
    proximityStats: {
      citationMean: api.proximity_stats.citation_mean,
      citationMedian: api.proximity_stats.citation_median,
      companyMean: api.proximity_stats.company_mean,
      companyMedian: api.proximity_stats.company_median,
      similarityGap: api.proximity_stats.similarity_gap,
    },
    spaResult: {
      tStat: api.spa.t_stat,
      pValue: api.spa.p_value,
      effect: api.spa.effect,
    },
    perClusterProximity: api.per_cluster_proximity,
    totalGaps: api.total_gaps,
    uncoveredQueries: api.uncovered_queries,
  };
}

// ── Embedding Points ─────────────────────────────────────────

export function toEmbeddingPoints(points: EmbeddingPointAPI[]): EmbeddingPoint[] {
  return points.map((p) => ({
    id: p.id,
    x: p.x,
    y: p.y,
    type: p.type as EmbeddingPoint['type'],
    label: p.label,
    cluster: p.cluster,
    clusterId: p.cluster_id,
    queryId: p.query_id,
    similarity: p.similarity ?? undefined,
  }));
}
