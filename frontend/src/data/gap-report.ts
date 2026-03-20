import type { GapReport, Query, Cluster, Platform } from '@/types';
import rawData from '../../data/artifacts/gap_analysis/lovable/gap_report.json';

interface RawStructuralSignals {
  word_count?: number;
  paragraph_count?: number;
  header_count?: number;
  list_item_count?: number;
  stat_count?: number;
  citation_count?: number;
  reading_level?: number;
  has_faq_section?: boolean;
  has_comparison_table?: boolean;
  has_step_by_step?: boolean;
  has_key_takeaways?: boolean;
  has_definition_opening?: boolean;
  content_type?: string;
  authority_type?: string;
}

interface RawGap {
  query_id: string;
  cluster_name: string;
  query_text: string;
  best_company_unit: string;
  best_company_unit_text: string;
  best_company_url: string;
  best_company_similarity: number;
  avg_citation_similarity: number;
  gap: number;
  interpretation: string;
  top_cited_exemplars: Array<{
    url: string;
    domain: string;
    similarity: number;
    snippet?: string;
    structural_signals?: RawStructuralSignals;
    authority_type?: string;
  }>;
  content_brief?: {
    target_word_count?: number[];
    target_reading_level?: number[];
    recommended_header_count?: number[];
    header_hierarchy?: Record<string, number>;
    has_ordered_lists?: number;
    has_unordered_lists?: number;
    has_tables?: number;
    has_faq_section?: number;
    has_definition_opening?: number;
    has_key_takeaways?: number;
    has_step_by_step?: number;
    has_comparison_table?: number;
    target_data_point_density?: number;
    target_citation_density?: number;
    dominant_authority_type?: string;
    dominant_content_type?: string;
    exemplar_count?: number;
  };
  best_company_structural_signals?: RawStructuralSignals;
  company_cited: boolean;
  company_cited_platforms: string[];
}

interface RawReport {
  executive_summary: string;
  recommendations: Array<{ title_idea: string; target_cluster: string }>;
  proximity_stats: {
    citation_similarity_mean: number;
    company_similarity_mean: number;
    per_cluster: Record<string, { mean: number; std: number; min: number; max: number; count: number }>;
  };
  spa_results: Array<{
    cluster_name: string;
    t_stat: number;
    p_value: number;
    mean_citation_similarity: number;
    mean_company_similarity: number;
    effect: string;
  }>;
  gaps: RawGap[];
  decision_metrics: {
    total_queries: number;
    total_citations: number;
    avg_gap: number;
  };
}

function classifyGap(gap: number): Query['classification'] {
  if (gap > 0.05) return 'significant_gap';
  if (gap > 0.01) return 'gap_to_close';
  if (gap > -0.01) return 'roughly_equal';
  return 'company_wins';
}

export interface ContentBriefData {
  targetWordCount: [number, number];
  targetReadingLevel: [number, number];
  recommendedHeaders: [number, number];
  headerHierarchy: Record<string, number>;
  hasFaq: number;
  hasTables: number;
  hasStepByStep: number;
  hasKeyTakeaways: number;
  dominantContentType: string;
  dominantAuthority: string;
  exemplarCount: number;
}

export interface CompanyStructuralData {
  wordCount: number;
  headers: number;
  lists: number;
  readingLevel: number;
}

export interface EnrichedQuery extends Query {
  contentBrief: ContentBriefData | null;
  companyStructural: CompanyStructuralData | null;
}

export function getGapReport(): GapReport & { enrichedQueries: EnrichedQuery[] } {
  const data = rawData as unknown as RawReport;

  const spaOverall = data.spa_results?.[0];

  const queries: Query[] = [];
  const enrichedQueries: EnrichedQuery[] = [];

  for (const g of data.gaps) {
    const query: Query = {
      id: g.query_id,
      text: g.query_text,
      cluster: g.cluster_name,
      classification: classifyGap(g.gap),
      gap: g.gap,
      avgCitationSimilarity: g.avg_citation_similarity,
      bestCompanyUnit: {
        id: g.best_company_unit || '',
        url: g.best_company_url || '',
        similarity: g.best_company_similarity,
        snippet: g.best_company_unit_text || '',
      },
      citedExemplars: (g.top_cited_exemplars || []).map((e) => ({
        url: e.url,
        domain: e.domain,
        similarity: e.similarity,
        snippet: e.snippet || '',
        structure: {
          words: e.structural_signals?.word_count ?? 0,
          paragraphs: e.structural_signals?.paragraph_count ?? 0,
          headers: e.structural_signals?.header_count ?? 0,
          lists: e.structural_signals?.list_item_count ?? 0,
          stats: e.structural_signals?.stat_count ?? 0,
          citations: e.structural_signals?.citation_count ?? 0,
          readingLevel: e.structural_signals?.reading_level,
        },
      })),
      companyCited: g.company_cited,
      platforms: (g.company_cited_platforms || []) as Platform[],
    };

    queries.push(query);

    const brief = g.content_brief;
    const compSig = g.best_company_structural_signals;

    enrichedQueries.push({
      ...query,
      contentBrief: brief ? {
        targetWordCount: [brief.target_word_count?.[0] ?? 0, brief.target_word_count?.[1] ?? 0],
        targetReadingLevel: [brief.target_reading_level?.[0] ?? 0, brief.target_reading_level?.[1] ?? 0],
        recommendedHeaders: [brief.recommended_header_count?.[0] ?? 0, brief.recommended_header_count?.[1] ?? 0],
        headerHierarchy: brief.header_hierarchy ?? {},
        hasFaq: brief.has_faq_section ?? 0,
        hasTables: brief.has_tables ?? 0,
        hasStepByStep: brief.has_step_by_step ?? 0,
        hasKeyTakeaways: brief.has_key_takeaways ?? 0,
        dominantContentType: brief.dominant_content_type ?? '',
        dominantAuthority: brief.dominant_authority_type ?? '',
        exemplarCount: brief.exemplar_count ?? 0,
      } : null,
      companyStructural: compSig ? {
        wordCount: compSig.word_count ?? 0,
        headers: compSig.header_count ?? 0,
        lists: compSig.list_item_count ?? 0,
        readingLevel: compSig.reading_level ?? 0,
      } : null,
    });
  }

  const perCluster = data.proximity_stats.per_cluster || {};
  const clusterNames = Array.from(new Set(queries.map((q) => q.cluster)));

  const clusters: Cluster[] = clusterNames.map((name) => {
    const raw = perCluster[name];
    return {
      id: name.toLowerCase().replace(/\s+/g, '-'),
      name,
      queryCount: queries.filter((q) => q.cluster === name).length,
      citationsAnalyzed: raw?.count ?? 0,
      requiredElements: [],
      avgWordCount: 0,
      faqRate: 0,
      tableRate: 0,
      dominantContentType: '',
      dominantAuthority: '',
    };
  });

  return {
    summary: {
      spaScore: spaOverall?.t_stat ? Math.round(spaOverall.t_stat * 1000) / 1000 : 1.13,
      meanCitationSimilarity: data.proximity_stats.citation_similarity_mean,
      meanCompanySimilarity: data.proximity_stats.company_similarity_mean,
      totalQueries: data.decision_metrics.total_queries,
      totalCitations: data.decision_metrics.total_citations,
      averageGap: Math.round(data.decision_metrics.avg_gap * 10000) / 10000,
    },
    queries,
    clusters,
    enrichedQueries,
  };
}
