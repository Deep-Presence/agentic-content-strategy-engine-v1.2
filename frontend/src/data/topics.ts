import type { Topic } from '@/types';
import { getGapReport } from './gap-report';
import type { EnrichedQuery } from './gap-report';

function classifyCoverage(gap: number, interpretation: string): Topic['coverage'] {
  if (interpretation === 'significant_gap' || gap > 0.10) return 'gap';
  if (interpretation === 'gap_to_close' || gap > 0.05) return 'partial';
  return 'covered';
}

function classifyPriority(gap: number): Topic['priority'] {
  if (gap > 0.10) return 'high';
  if (gap > 0.05) return 'medium';
  return 'low';
}

export interface EnrichedTopic extends Topic {
  exemplarCount: number;
  avgExemplarWords: number;
  avgExemplarHeaders: number;
  estCitations: string;
  estReferrals: string;
  companyWords: number;
  companyHeaders: number;
  contentType: string;
}

export function getTopics(): EnrichedTopic[] {
  const report = getGapReport();
  const top25 = report.enrichedQueries
    .sort((a, b) => b.gap - a.gap)
    .slice(0, 25);

  return top25.map((q: EnrichedQuery) => {
    const exemplars = q.citedExemplars;
    const avgWords = exemplars.length > 0
      ? Math.round(exemplars.reduce((s, e) => s + e.structure.words, 0) / exemplars.length)
      : 0;
    const avgHeaders = exemplars.length > 0
      ? Math.round(exemplars.reduce((s, e) => s + e.structure.headers, 0) / exemplars.length)
      : 0;

    const gapNorm = Math.min(q.gap / 0.18, 1);
    const estCitationsLow = Math.max(1, Math.round(gapNorm * 3 + exemplars.length * 0.5));
    const estCitationsHigh = Math.max(estCitationsLow + 1, Math.round(gapNorm * 8 + exemplars.length));
    const estReferrals = Math.round(gapNorm * 2000 + 200);

    return {
      id: q.id,
      title: q.text,
      priority: classifyPriority(q.gap),
      personas: q.companyCited ? ['Technical Evaluator'] : ['Technical Evaluator', 'Decision Maker'],
      coverage: classifyCoverage(q.gap, q.classification),
      cluster: q.cluster,
      subtopics: q.citedExemplars.map(e => e.domain).filter((v, idx, arr) => arr.indexOf(v) === idx).slice(0, 3),
      gapScore: q.gap,
      sources: q.citedExemplars.map(e => e.domain).filter((v, idx, arr) => arr.indexOf(v) === idx),
      exemplarCount: exemplars.length,
      avgExemplarWords: avgWords,
      avgExemplarHeaders: avgHeaders,
      estCitations: `${estCitationsLow}-${estCitationsHigh}/month`,
      estReferrals: `${(estReferrals / 1000).toFixed(1)}K/month`,
      companyWords: q.companyStructural?.wordCount ?? 0,
      companyHeaders: q.companyStructural?.headers ?? 0,
      contentType: q.contentBrief?.dominantContentType?.replace(/_/g, ' ') || 'blog / article',
    };
  });
}
