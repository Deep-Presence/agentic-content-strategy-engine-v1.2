/**
 * Adapter functions: map backend API responses → frontend display types.
 *
 * Every derivation is documented. Functions are pure (no side effects)
 * and independently testable.
 */

import type {
  ContentBriefListItemAPI,
  ContentBriefDetailResponseAPI,
  EvalCycleAPI,
  CPSDetailAPI,
} from './types';
import type {
  ContentCard,
  ContentMetadata,
  ContentType,
  Priority,
  BriefPipelineStatus,
  BriefContent,
  ArticleContent,
  ArticleSection,
  CitPrediction,
  ComplianceItem,
  EEATScore,
  InterlinkItem,
} from '../_components/types';

// ---------------------------------------------------------------------------
// content_format → ContentType
// ---------------------------------------------------------------------------

const FORMAT_TO_TYPE: Record<string, ContentType> = {
  how_to: 'HOW_TO',
  comparison: 'COMPARISON',
  long_blog: 'LONG_BLOG',
  pillar_page: 'PILLAR_PAGE',
  short_faq: 'LONG_BLOG',
};

export function mapContentType(format: string): ContentType {
  return FORMAT_TO_TYPE[format] ?? 'GUIDE';
}

// ---------------------------------------------------------------------------
// priority_score → Priority
// ---------------------------------------------------------------------------

export function mapPriority(score: number): Priority {
  if (score >= 0.7) return 'P0';
  if (score >= 0.4) return 'P1';
  return 'P2';
}

// ---------------------------------------------------------------------------
// target_word_count → readTime (minutes)
// ---------------------------------------------------------------------------

export function deriveReadTime(targetWordCount: number): number {
  return Math.max(1, Math.round(targetWordCount / 200));
}

// ---------------------------------------------------------------------------
// gap_context → gap score, competitor
// ---------------------------------------------------------------------------

export function deriveGap(ctx: ContentBriefListItemAPI['gap_context']): number {
  return ctx?.gap_score ?? 0;
}

export function deriveCompetitor(ctx: ContentBriefListItemAPI['gap_context']): string {
  if (!ctx?.exemplars?.length) return '';
  const first = ctx.exemplars[0];
  if (first.domain) return first.domain;
  if (first.url) {
    try {
      return new URL(first.url).hostname;
    } catch {
      return '';
    }
  }
  return '';
}

export function adaptPublishMetadata(
  raw?: ContentBriefListItemAPI['publish_metadata'] | ContentBriefDetailResponseAPI['publish_metadata'] | null,
): ContentMetadata {
  return {
    slug: raw?.slug || '',
    metaTitle: raw?.meta_title || '',
    metaDescription: raw?.meta_description || '',
    canonicalUrl: raw?.canonical_url || '',
    schemaMarkup: raw?.schema_markup || false,
    publishDate: raw?.publish_date || '',
    author: raw?.author || '',
    tags: raw?.tags || [],
  };
}

export function serializePublishMetadata(metadata?: ContentMetadata | null) {
  return {
    slug: metadata?.slug || '',
    meta_title: metadata?.metaTitle || '',
    meta_description: metadata?.metaDescription || '',
    canonical_url: metadata?.canonicalUrl || '',
    schema_markup: metadata?.schemaMarkup || false,
    publish_date: metadata?.publishDate || '',
    author: metadata?.author || '',
    tags: metadata?.tags || [],
  };
}

// ---------------------------------------------------------------------------
// Brief list item → ContentCard
// ---------------------------------------------------------------------------

export function adaptBriefToCard(item: ContentBriefListItemAPI): ContentCard {
  return {
    id: item.id,
    displayId: item.display_id || undefined,
    title: item.title,
    type: mapContentType(item.content_format),
    cluster: item.cluster,
    gap: deriveGap(item.gap_context),
    score: item.citability_score ?? 0,
    priority: mapPriority(item.priority_score),
    readTime: deriveReadTime(item.target_word_count),
    competitor: deriveCompetitor(item.gap_context),
    status: (item.status || 'suggested') as BriefPipelineStatus,
    taskId: item.task_id ?? undefined,
    topicAssignmentId: item.topic_assignment_id ?? undefined,
    buyerStage: item.buyer_stage ?? undefined,
    source: (item.source as ContentCard['source']) ?? undefined,
    gaRunId: item.ga_run_id ?? undefined,
    effectiveSlug: item.effective_slug ?? undefined,
    intentType: item.intent_type ?? undefined,
    personaName: item.persona_name ?? undefined,
    personaId: item.persona_id ?? undefined,
    personaAffinity: item.persona_affinity ?? undefined,
    priorityFactors: item.priority_factors ?? undefined,
    contentFormat: item.content_format || undefined,
    estimatedWordCount: item.estimated_word_count ?? undefined,
    citationOpp: item.citation_opportunity ?? undefined,
    description: item.description ?? undefined,
    targetKeywords: item.target_keywords ?? undefined,
    contentAngle: item.content_angle ?? undefined,
    metadata: adaptPublishMetadata(item.publish_metadata),
    gapContext: item.gap_context ?? undefined,
    cycleId: item.cycle_id ?? undefined,
    targetWordCount: item.target_word_count,
    publishedUrl: item.published_url || undefined,
    publishedAt: item.published_at ?? undefined,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptBriefList(items: ContentBriefListItemAPI[]): ContentCard[] {
  return items.map(adaptBriefToCard);
}

// ---------------------------------------------------------------------------
// Brief detail → BriefContent (for LeftSidebar / FullPageView brief review)
// ---------------------------------------------------------------------------

export function adaptBriefContent(
  detail: ContentBriefDetailResponseAPI,
): BriefContent {
  return {
    sections: detail.key_topics.length > 0 ? detail.key_topics : ['(No sections defined)'],
    targetWords: detail.target_word_count.max || 0,
    exemplarCount: detail.exemplars.length,
    sources: detail.exemplars.map((ex) => {
      let domain = '';
      try {
        domain = new URL(ex.url).hostname;
      } catch {
        /* skip */
      }
      return {
        name: ex.snippet || domain || ex.url,
        domain,
        engines: 0,
        url: ex.url,
        authorityType: ex.authority_type,
        wordCount: ex.word_count,
      };
    }),
    reasons: detail.key_angles.length > 0 ? detail.key_angles : detail.exemplars.length > 0
      ? [`${detail.exemplars.length} exemplar(s) analyzed for structural patterns`]
      : [],
  };
}

// ---------------------------------------------------------------------------
// Markdown → ArticleSection[] (client-side H2 splitting)
// ---------------------------------------------------------------------------

export function parseMarkdownSections(markdown: string): ArticleSection[] {
  const lines = markdown.split('\n');
  const sections: ArticleSection[] = [];
  let currentHeading = '';
  let currentLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (currentHeading || currentLines.length > 0) {
        const content = currentLines.join('\n').trim();
        const words = content.split(/\s+/).filter(Boolean).length;
        sections.push({ heading: currentHeading || 'Introduction', words, content });
      }
      currentHeading = line.replace(/^##\s*/, '').trim();
      currentLines = [];
    } else {
      currentLines.push(line);
    }
  }

  // Flush last section
  if (currentHeading || currentLines.length > 0) {
    const content = currentLines.join('\n').trim();
    const words = content.split(/\s+/).filter(Boolean).length;
    sections.push({ heading: currentHeading || 'Introduction', words, content });
  }

  return sections;
}

// ---------------------------------------------------------------------------
// eval_history → compliance, eeat, voiceCompliance
// ---------------------------------------------------------------------------

export interface AdaptedEvalMetrics {
  compliance: ComplianceItem[];
  eeat: EEATScore;
  voiceCompliance: number;
}

export function adaptEvalMetrics(evalHistory: EvalCycleAPI[]): AdaptedEvalMetrics {
  const defaults: AdaptedEvalMetrics = {
    compliance: [],
    eeat: { overall: 0, experience: 0, expertise: 0, authoritativeness: 0, trustworthiness: 0 },
    voiceCompliance: 0,
  };

  if (evalHistory.length === 0) return defaults;

  const latest = evalHistory[evalHistory.length - 1];
  let compliance: ComplianceItem[] = [];
  let eeat = defaults.eeat;
  let voiceCompliance = 0;

  for (const dim of latest.dimensions) {
    const d = dim.details as Record<string, unknown>;

    switch (dim.dimension) {
      case 'structural': {
        // Extract count-based compliance from structural details
        const items: ComplianceItem[] = [];
        const extract = (label: string, key: string) => {
          const detail = d[key] as Record<string, number> | undefined;
          if (detail && typeof detail === 'object' && 'actual' in detail && 'target' in detail) {
            items.push({ label, current: Number(detail.actual), target: Number(detail.target) });
          }
        };
        extract('Headers', 'header_count');
        extract('Citations', 'citation_count');
        extract('Stats', 'stat_presence');
        extract('Lists', 'list_count');

        // Word count from word_count detail
        const wc = d.word_count as Record<string, unknown> | undefined;
        if (wc && typeof wc === 'object' && 'word_count' in wc && 'range' in wc) {
          const range = wc.range as number[];
          if (Array.isArray(range) && range.length >= 2) {
            items.unshift({ label: 'Words', current: Number(wc.word_count), target: range[1] });
          }
        }

        compliance = items;
        break;
      }

      case 'eeat': {
        // E-E-A-T sub-dimensions in details.dimension_scores
        const scores = d.dimension_scores as Record<string, number> | undefined;
        eeat = {
          overall: Math.round(dim.score * 100),
          experience: Math.round(Number(scores?.experience ?? 0) * 100),
          expertise: Math.round(Number(scores?.expertise ?? 0) * 100),
          authoritativeness: Math.round(Number(scores?.authoritativeness ?? 0) * 100),
          trustworthiness: Math.round(Number(scores?.trustworthiness ?? 0) * 100),
        };
        break;
      }

      case 'style': {
        voiceCompliance = Math.round(dim.score * 100);
        break;
      }
    }
  }

  return { compliance, eeat, voiceCompliance };
}

// ---------------------------------------------------------------------------
// CPS per_engine → CitPrediction[]
// ---------------------------------------------------------------------------

const ENGINE_DISPLAY: Record<string, string> = {
  chatgpt_search: 'ChatGPT',
  chatgpt: 'ChatGPT',
  openai: 'ChatGPT',
  claude_search: 'Claude',
  claude: 'Claude',
  perplexity: 'Perplexity',
  gemini_search: 'Gemini',
  gemini: 'Gemini',
  google_ai: 'Google AI',
};

export function adaptCPS(cps: CPSDetailAPI | null): CitPrediction[] {
  if (!cps?.per_engine) return [];
  return Object.entries(cps.per_engine).map(([engine, score]) => ({
    engine: ENGINE_DISPLAY[engine] ?? engine,
    score: Math.round(score * 100),
  }));
}

// ---------------------------------------------------------------------------
// Markdown → InterlinkItem[] (parse inline links)
// ---------------------------------------------------------------------------

export function extractInterlinks(markdown: string, companyDomain?: string): InterlinkItem[] {
  const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  const seen = new Set<string>();
  const links: InterlinkItem[] = [];
  let match: RegExpExecArray | null;

  while ((match = linkRegex.exec(markdown)) !== null) {
    const [, title, path] = match;
    if (seen.has(path)) continue;
    seen.add(path);

    // Classify as internal (starts with / or matches company domain) vs external
    const isInternal = path.startsWith('/') || (companyDomain && path.includes(companyDomain));
    links.push({ title, path, linked: !isInternal });
  }

  return links;
}

// ---------------------------------------------------------------------------
// Full article content assembly (from detail + markdown + eval)
// ---------------------------------------------------------------------------

export function assembleArticleContent(
  detail: ContentBriefDetailResponseAPI,
  markdown: string,
): ArticleContent {
  const sections = parseMarkdownSections(markdown);
  const wordCount = sections.reduce((sum, s) => sum + s.words, 0);
  const { compliance, eeat, voiceCompliance } = adaptEvalMetrics(detail.eval_history);

  return {
    markdown,
    wordCount,
    targetWords: detail.target_word_count.max || 0,
    voiceCompliance,
    sections,
    citPrediction: adaptCPS(detail.cps),
    compliance,
    eeat,
    interlinks: extractInterlinks(markdown),
  };
}
