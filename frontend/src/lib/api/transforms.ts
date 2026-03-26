/**
 * Transform functions — bridge between API snake_case responses
 * and frontend camelCase types defined in @/types/index.ts.
 */

import type {
  Query, Cluster, SiteAudit, EmbeddingPoint,
  ContentBrief, Platform,
} from '@/types';
import type {
  QueryRow, ClusterSpecResponse, AuditDetailResponse,
  ContentBriefItem,
} from './types';

// ── Gap Analysis ──────────────────────────────────────────────────────

const VALID_CLASSIFICATIONS = new Set(['significant_gap', 'gap_to_close', 'roughly_equal', 'company_wins']);
// Backend may emit 'openai' or 'chatgpt' — accept both
const VALID_PLATFORMS = new Set(['chatgpt', 'claude', 'perplexity', 'google_ai_overview', 'gemini', 'openai']);

function safeClassification(raw: string): Query['classification'] {
  return VALID_CLASSIFICATIONS.has(raw) ? raw as Query['classification'] : 'roughly_equal';
}

export function toQuery(row: QueryRow): Query {
  return {
    id: row.query_id,
    text: row.query_text,
    cluster: row.cluster_name ?? '',
    classification: safeClassification(row.classification),
    gap: row.gap_score,
    avgCitationSimilarity: row.citation_sim,
    bestCompanyUnit: {
      id: '',
      url: '',
      similarity: row.company_sim,
      snippet: '',
    },
    citedExemplars: row.top_exemplars.map((ex) => ({
      url: ex.url,
      domain: ex.domain ?? '',
      similarity: ex.similarity,
      snippet: ex.snippet ?? '',
      structure: {
        words: row.target_words?.max ?? 0,
        paragraphs: 0,
        headers: row.headers,
        lists: 0,
        stats: 0,
        citations: 0,
        readingLevel: row.reading_level?.max ?? undefined,
      },
    })),
    companyCited: row.company_cited ?? (row.classification === 'company_wins' || row.company_sim > row.citation_sim),
    platforms: row.company_cited_platforms?.length
      ? row.company_cited_platforms.filter((k) => VALID_PLATFORMS.has(k)) as Platform[]
      : Object.keys(row.platform_citations).filter((k) => VALID_PLATFORMS.has(k)) as Platform[],
  };
}

export function toCluster(spec: ClusterSpecResponse): Cluster {
  return {
    id: spec.cluster_id ?? '',
    name: spec.cluster_name,
    queryCount: spec.query_count,
    citationsAnalyzed: spec.citations_analyzed,
    requiredElements: spec.required_elements,
    avgWordCount: spec.avg_word_count,
    faqRate: spec.faq_rate,
    tableRate: spec.table_rate,
    dominantContentType: spec.dominant_content_type ?? '',
    dominantAuthority: spec.dominant_authority_type ?? '',
  };
}

// ── Site Audit ────────────────────────────────────────────────────────

const BOT_MAP: [keyof AuditDetailResponse['ai_bot_access'], string][] = [
  ['gptbot_allowed', 'GPTBot'],
  ['claudebot_allowed', 'ClaudeBot'],
  ['perplexitybot_allowed', 'PerplexityBot'],
  ['google_extended_allowed', 'Google-Extended'],
  ['ccbot_allowed', 'CCBot'],
];

export function toSiteAudit(detail: AuditDetailResponse): SiteAudit {
  return {
    overallScore: detail.overall_score,
    grade: detail.grade,
    pagesCrawled: detail.pages_crawled,
    totalFindings: detail.total_findings,
    dimensions: detail.dimension_scores.map((d) => ({
      name: d.dimension,
      score: d.score,
      weight: d.weight,
      weighted: d.weighted_score,
      findings: d.finding_count,
    })),
    botAccess: BOT_MAP.map(([key, bot]) => ({
      bot,
      allowed: detail.ai_bot_access[key] as boolean,
    })),
    aeoReadiness: {
      avgSnippetReadiness: detail.avg_snippet_readiness,
      pagesWithStructuredData: detail.pages_with_schema,
      avgQuestionHeadingRatio: detail.avg_question_heading_ratio,
    },
    findings: [], // Findings need separate endpoint fetch
  };
}

// ── Embedding Points ──────────────────────────────────────────────────

export function toEmbeddingPoint(point: {
  id: string;
  type: 'company' | 'citation' | 'query';
  x: number;
  y: number;
  cluster: string;
  label: string;
  url?: string;
  similarity?: number;
}): EmbeddingPoint {
  return { ...point };
}

// ── Content Briefs ────────────────────────────────────────────────────

const STATUS_TO_STAGE: Record<string, ContentBrief['stage']> = {
  // Triage
  suggested: 'triage',
  // Brief
  briefing: 'brief',
  brief_review: 'brief',
  approved: 'brief',
  pending_brief_approval: 'brief',
  // Generating
  outlining: 'generating',
  drafting: 'generating',
  linking: 'generating',
  enriching: 'generating',
  evaluating: 'generating',
  revising: 'generating',
  in_progress: 'generating', // legacy compat
  research: 'generating', // legacy compat (v1.0 outline status)
  // Review
  review: 'review',
  pending_review: 'review',
  pending_content_approval: 'review',
  // Approved
  completed: 'approved',
  published: 'approved',
  // Hidden
  rejected: 'triage',
  failed: 'triage',
};

export function toBriefStage(status: string): ContentBrief['stage'] {
  return STATUS_TO_STAGE[status] ?? 'triage';
}

export function toBrief(item: ContentBriefItem): ContentBrief {
  return {
    id: item.id,
    title: item.title,
    targetCluster: item.cluster,
    targetQuery: '',
    status: item.status,
    stage: toBriefStage(item.status),
    taskId: item.task_id ?? undefined,
    personas: [],
    cpsPredict: {} as Record<Platform, number>,
    structuralTargets: { words: item.target_word_count, paragraphs: 0, headers: 0, lists: 0, stats: 0, citations: 0 },
    createdAt: item.created_at,
    publishedAt: item.published_at ?? undefined,
    publishedUrl: item.published_url || undefined,
  };
}
