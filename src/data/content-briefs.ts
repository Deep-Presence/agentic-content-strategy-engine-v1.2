import type { ContentBrief, ContentPiece, Platform } from '@/types';
import rawBriefsFile from '../../data/artifacts/content/carta/briefs.json';
import fs from 'fs';
import path from 'path';

interface RawBrief {
  brief_id: string;
  title: string;
  target_cluster: string;
  target_queries: Array<{ query_text: string; cluster_name: string }>;
  content_format: string;
  priority_score: number;
  word_count_range: [number, number];
  structural_targets: {
    header_rate?: number;
    list_rate?: number;
    stat_rate?: number;
    citation_rate?: number;
    min_headers?: number;
    min_lists?: number;
    min_citations?: number;
  };
}

export function getContentBriefs(): ContentBrief[] {
  const raw = rawBriefsFile as unknown as { briefs: RawBrief[] } | RawBrief[];
  const data = Array.isArray(raw) ? raw : raw.briefs;

  return data.map((b) => ({
    id: b.brief_id,
    title: b.title,
    targetCluster: b.target_cluster,
    targetQuery: b.target_queries?.[0]?.query_text || '',
    stage: 'review' as const,
    personas: [],
    cpsPredict: {} as Record<Platform, number>,
    structuralTargets: {
      words: b.word_count_range?.[1] || 0,
      paragraphs: 0,
      headers: b.structural_targets?.min_headers ?? 0,
      lists: b.structural_targets?.min_lists ?? 0,
      stats: 0,
      citations: b.structural_targets?.min_citations ?? 0,
    },
    createdAt: new Date().toISOString(),
  }));
}

export function getContentPieces(briefId: string): ContentPiece[] {
  const basePath = path.join(process.cwd(), `data/artifacts/content/carta/content/${briefId}`);
  const pieces: ContentPiece[] = [];
  const stages = ['outline', 'draft', 'enriched', 'final', 'formatted'] as const;

  try {
    for (const stage of stages) {
      const mdPath = path.join(basePath, `${stage}.md`);
      if (fs.existsSync(mdPath)) {
        const content = fs.readFileSync(mdPath, 'utf-8');
        const wordCount = content.split(/\s+/).length;
        pieces.push({
          briefId,
          stage,
          markdown: content,
          wordCount,
          structuralAnalysis: {
            words: wordCount,
            paragraphs: (content.match(/\n\n/g) || []).length + 1,
            headers: (content.match(/^#+\s/gm) || []).length,
            lists: (content.match(/^[-*]\s/gm) || []).length,
            stats: 0,
            citations: (content.match(/\[.*?\]\(.*?\)/g) || []).length,
          },
          voiceComplianceScore: 0,
          interlinkSuggestions: [],
        });
      }
    }
  } catch {
    // Data not available
  }

  return pieces;
}
