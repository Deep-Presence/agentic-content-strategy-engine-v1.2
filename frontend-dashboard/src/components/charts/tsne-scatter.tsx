'use client';

import { UmapScatter, type ScatterPoint } from './umap-scatter';

interface TsneScatterProps {
  points: ScatterPoint[];
  colorBy: 'type' | 'cluster' | 'gap_score';
  selectedCluster?: string;
  highlightedIds?: string[];
  onPointClick?: (point: ScatterPoint) => void;
  onPointHover?: (point: ScatterPoint | null) => void;
  onBrushSelect?: (points: ScatterPoint[]) => void;
  width?: number;
  height?: number;
  clusterColors?: Record<string, string>;
  className?: string;
}

function TsneScatter(props: TsneScatterProps) {
  // t-SNE uses the same rendering as UMAP — the difference is in the data coordinates,
  // which are computed server-side. This component wraps UmapScatter for API consistency.
  return <UmapScatter {...props} />;
}

export { TsneScatter };
export type { TsneScatterProps };
