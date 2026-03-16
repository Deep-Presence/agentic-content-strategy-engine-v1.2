import type { SiteAudit, AuditDimension, AuditFinding } from '@/types';
import rawData from '../../data/artifacts/site_audit/lovable/039d53f8-cf4c-43c7-bae9-614ddd2cb472/audit_result.json';

interface RawAudit {
  audit_id: string;
  domain: string;
  overall_score: number;
  grade: string;
  pages_crawled: number;
  dimension_scores: Array<{
    dimension: string;
    score: number;
    weight: number;
    weighted_score: number;
    finding_count: number;
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
  }>;
  ai_bot_access: Record<string, boolean | null>;
  findings?: Array<{
    severity: string;
    dimension: string;
    title: string;
    affected_pages: number;
    recommendation: string;
  }>;
  aeo_readiness?: {
    avg_snippet_readiness: number;
    pages_with_structured_data: number;
    avg_question_heading_ratio: number;
  };
}

export function getSiteAudit(): SiteAudit {
  const data = rawData as unknown as RawAudit;

  const dimensions: AuditDimension[] = data.dimension_scores.map((d) => ({
    name: d.dimension.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
    score: d.score,
    weight: d.weight,
    weighted: d.weighted_score,
    findings: d.finding_count,
  }));

  const totalFindings = dimensions.reduce((sum, d) => sum + d.findings, 0);

  const botAccess = Object.entries(data.ai_bot_access)
    .filter(([key]) => key.endsWith('_allowed'))
    .map(([key, val]) => ({
      bot: key.replace('_allowed', '').replace(/_/g, ' '),
      allowed: val === true,
    }));

  const findings: AuditFinding[] = (data.findings || []).map((f) => ({
    severity: f.severity as AuditFinding['severity'],
    dimension: f.dimension,
    title: f.title,
    affectedPages: f.affected_pages,
    recommendation: f.recommendation,
  }));

  return {
    overallScore: Math.round(data.overall_score * 100) / 100,
    grade: data.grade,
    pagesCrawled: data.pages_crawled,
    totalFindings,
    dimensions,
    botAccess,
    aeoReadiness: {
      avgSnippetReadiness: data.aeo_readiness?.avg_snippet_readiness ?? 0,
      pagesWithStructuredData: data.aeo_readiness?.pages_with_structured_data ?? 0,
      avgQuestionHeadingRatio: data.aeo_readiness?.avg_question_heading_ratio ?? 0,
    },
    findings,
  };
}
