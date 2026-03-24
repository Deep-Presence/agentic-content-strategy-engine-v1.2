import type { EmbeddingPoint } from '@/types';
import tsneData from '../../data/artifacts/gap_analysis/lovable/visualizations/embedding_projections_tsne.json';
import umapData from '../../data/artifacts/gap_analysis/lovable/visualizations/embedding_projections_umap.json';

interface RawEmbeddingData {
  method: string;
  point_count: number;
  points: Array<{
    x: number;
    y: number;
    type: 'query' | 'citation' | 'company';
    id: string;
    label: string;
    cluster: string;
    cluster_id: string;
    similarity?: number;
  }>;
}

function parsePoints(data: RawEmbeddingData): EmbeddingPoint[] {
  return data.points.map((p) => ({
    id: p.id,
    type: p.type,
    x: p.x,
    y: p.y,
    cluster: p.cluster,
    label: p.label,
    url: p.type === 'citation' ? p.label : undefined,
    similarity: p.similarity,
  }));
}

export function getTsneEmbeddings(): EmbeddingPoint[] {
  return parsePoints(tsneData as unknown as RawEmbeddingData);
}

export function getUmapEmbeddings(): EmbeddingPoint[] {
  return parsePoints(umapData as unknown as RawEmbeddingData);
}

export function getEmbeddingStats(points: EmbeddingPoint[]) {
  const byType = {
    query: points.filter((p) => p.type === 'query').length,
    citation: points.filter((p) => p.type === 'citation').length,
    company: points.filter((p) => p.type === 'company').length,
  };
  const clusters = Array.from(new Set(points.map((p) => p.cluster)));
  return { total: points.length, byType, clusterCount: clusters.length, clusters };
}
