import { describe, it, expect } from 'vitest';
import {
  toQuery,
  toCluster,
  toSiteAudit,
  toEmbeddingPoint,
  toBriefStage,
} from '@/lib/api/transforms';
import type { QueryRow, ClusterSpecResponse, AuditDetailResponse } from '@/lib/api/types';

describe('API Transforms', () => {
  describe('toQuery', () => {
    it('maps QueryRow to frontend Query type', () => {
      const row: QueryRow = {
        query_id: 'q-1',
        query_text: 'What is B2B SaaS?',
        cluster_id: 'c-1',
        cluster_name: 'SaaS Basics',
        gap_score: 0.15,
        classification: 'significant_gap',
        company_sim: 0.68,
        citation_sim: 0.82,
        target_words: { min: 1200, max: 2000 },
        reading_level: { min: 7.0, max: 9.0 },
        headers: 8,
        patterns: ['faq', 'definition_opening'],
        top_domain: 'example.com',
        top_exemplar_sim: 0.85,
        platform_citations: { perplexity: 3, openai: 2 },
        content_brief: null,
        top_exemplars: [
          { similarity: 0.85, domain: 'example.com', url: 'https://example.com/post', snippet: 'A snippet', authority_type: 'industry', content_type: 'article' },
        ],
      };

      const query = toQuery(row);

      expect(query.id).toBe('q-1');
      expect(query.text).toBe('What is B2B SaaS?');
      expect(query.cluster).toBe('SaaS Basics');
      expect(query.classification).toBe('significant_gap');
      expect(query.gap).toBe(0.15);
      expect(query.avgCitationSimilarity).toBe(0.82);
      expect(query.citedExemplars).toHaveLength(1);
      expect(query.citedExemplars[0].domain).toBe('example.com');
      expect(query.platforms).toEqual(['perplexity', 'openai']);
    });

    it('handles empty exemplars and platforms', () => {
      const row: QueryRow = {
        query_id: 'q-2',
        query_text: 'Test',
        cluster_id: null,
        cluster_name: null,
        gap_score: 0,
        classification: 'roughly_equal',
        company_sim: 0.5,
        citation_sim: 0.5,
        target_words: { min: 0, max: 0 },
        reading_level: { min: 0, max: 0 },
        headers: 0,
        patterns: [],
        top_domain: null,
        top_exemplar_sim: 0,
        platform_citations: {},
        content_brief: null,
        top_exemplars: [],
      };

      const query = toQuery(row);
      expect(query.citedExemplars).toEqual([]);
      expect(query.platforms).toEqual([]);
      expect(query.cluster).toBe('');
    });
  });

  describe('toCluster', () => {
    it('maps ClusterSpecResponse to frontend Cluster type', () => {
      const spec: ClusterSpecResponse = {
        cluster_id: 'c-1',
        cluster_name: 'SEO Strategy',
        query_count: 20,
        citations_analyzed: 100,
        centroid_distance: 0.45,
        min_similarity_threshold: 0.65,
        word_count_range: { min: 800, max: 3000 },
        required_elements: ['faq', 'table'],
        structural_rates: { faq: 0.45, table: 0.30 },
        avg_word_count: 1500,
        faq_rate: 0.45,
        table_rate: 0.30,
        key_takeaways_rate: 0.25,
        dominant_content_type: 'blog',
        dominant_authority_type: 'industry',
        exemplar_themes: ['theme1'],
      };

      const cluster = toCluster(spec);

      expect(cluster.id).toBe('c-1');
      expect(cluster.name).toBe('SEO Strategy');
      expect(cluster.queryCount).toBe(20);
      expect(cluster.citationsAnalyzed).toBe(100);
      expect(cluster.avgWordCount).toBe(1500);
      expect(cluster.faqRate).toBe(0.45);
      expect(cluster.tableRate).toBe(0.30);
      expect(cluster.dominantContentType).toBe('blog');
      expect(cluster.dominantAuthority).toBe('industry');
    });
  });

  describe('toSiteAudit', () => {
    it('maps AuditDetailResponse to frontend SiteAudit type', () => {
      const detail: AuditDetailResponse = {
        audit_id: 'a-1',
        domain: 'example.com',
        overall_score: 85.5,
        grade: 'A',
        pages_crawled: 150,
        pages_discovered: 200,
        duration_seconds: 3600,
        dimension_scores: [
          { dimension: 'crawlability', score: 90, weight: 0.15, weighted_score: 13.5, finding_count: 5, critical_count: 0, high_count: 2, medium_count: 2, low_count: 1, info_count: 0 },
        ],
        ai_bot_access: {
          gptbot_allowed: true, claudebot_allowed: true, perplexitybot_allowed: false,
          google_extended_allowed: true, ccbot_allowed: true, has_llms_txt: false, robots_txt_exists: true,
        },
        sitemap_health: { has_sitemap: true, sitemap_url_count: 500, sitemap_urls: [], sitemap_errors: [], has_sitemap_index: false },
        total_findings: 42,
        findings_by_severity: { critical: 0, high: 2, medium: 5 },
        findings_by_dimension: { crawlability: 5 },
        avg_snippet_readiness: 0.82,
        pages_with_schema: 120,
        avg_question_heading_ratio: 0.15,
        status: 'completed',
        error_message: null,
        started_at: '2026-03-01T00:00:00Z',
        completed_at: '2026-03-01T01:00:00Z',
      };

      const audit = toSiteAudit(detail);

      expect(audit.overallScore).toBe(85.5);
      expect(audit.grade).toBe('A');
      expect(audit.pagesCrawled).toBe(150);
      expect(audit.totalFindings).toBe(42);
      expect(audit.dimensions).toHaveLength(1);
      expect(audit.dimensions[0].name).toBe('crawlability');
      expect(audit.dimensions[0].score).toBe(90);
      expect(audit.dimensions[0].weight).toBe(0.15);
      expect(audit.dimensions[0].weighted).toBe(13.5);
      expect(audit.dimensions[0].findings).toBe(5);
      expect(audit.botAccess).toHaveLength(5);
      expect(audit.botAccess.find(b => b.bot === 'PerplexityBot')?.allowed).toBe(false);
      expect(audit.aeoReadiness.avgSnippetReadiness).toBe(0.82);
    });
  });

  describe('toEmbeddingPoint', () => {
    it('maps API embedding point to frontend EmbeddingPoint', () => {
      const apiPoint = { id: 'p-1', type: 'query' as const, x: 1.5, y: 2.3, cluster: 'seo', label: 'test query', url: 'https://example.com', similarity: 0.8 };
      const point = toEmbeddingPoint(apiPoint);

      expect(point.id).toBe('p-1');
      expect(point.type).toBe('query');
      expect(point.x).toBe(1.5);
      expect(point.y).toBe(2.3);
      expect(point.cluster).toBe('seo');
    });
  });

  describe('toBriefStage', () => {
    it('maps backend status to kanban column stage', () => {
      expect(toBriefStage('suggested')).toBe('triage');
      expect(toBriefStage('approved')).toBe('brief');
      expect(toBriefStage('in_progress')).toBe('generating');
      expect(toBriefStage('completed')).toBe('approved');
      expect(toBriefStage('unknown')).toBe('triage');
    });
  });
});
