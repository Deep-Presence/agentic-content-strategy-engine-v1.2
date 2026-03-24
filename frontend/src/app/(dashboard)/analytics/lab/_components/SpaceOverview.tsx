'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { Toggle, Skeleton } from '@/components/ui';
import type { EmbeddingPoint } from '@/types';

const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => <Skeleton variant="rectangular" height="100%" width="100%" />,
});

interface SpaceOverviewProps {
  tsnePoints: EmbeddingPoint[];
  umapPoints: EmbeddingPoint[];
  clusters: string[];
  onPointClick?: (point: EmbeddingPoint) => void;
}

const TYPE_COLORS: Record<string, string> = {
  company: '#5BA4C4',
  citation: 'rgba(91,164,196,0.4)',
  query: '#DC7B18',
};

const TYPE_SIZES: Record<string, number> = {
  company: 8,
  citation: 4,
  query: 6,
};

const CLUSTER_COLORS = [
  '#5BA4C4', '#DC7B18', '#34B27B', '#E5484D', '#886FBF',
  '#3498DB', '#F59E0B', '#10B981', '#EF4444',
];

export function SpaceOverview({ tsnePoints, umapPoints, clusters, onPointClick }: SpaceOverviewProps) {
  const [useUmap, setUseUmap] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const points = useUmap ? umapPoints : tsnePoints;

  // Cluster centroids for labels
  const centroids = useMemo(() => {
    const map: Record<string, { sumX: number; sumY: number; count: number }> = {};
    points.forEach((p) => {
      if (!map[p.cluster]) map[p.cluster] = { sumX: 0, sumY: 0, count: 0 };
      map[p.cluster].sumX += p.x;
      map[p.cluster].sumY += p.y;
      map[p.cluster].count++;
    });
    return Object.entries(map).map(([name, d]) => ({
      name,
      x: d.sumX / d.count,
      y: d.sumY / d.count,
    }));
  }, [points]);

  const traces = useMemo(() => {
    const groups: Record<string, EmbeddingPoint[]> = { company: [], citation: [], query: [] };
    points.forEach((p) => {
      if (selectedCluster && p.cluster !== selectedCluster) return;
      if (groups[p.type]) groups[p.type].push(p);
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result: any[] = Object.entries(groups).map(([type, pts]) => ({
      x: pts.map((p) => p.x),
      y: pts.map((p) => p.y),
      text: pts.map((p) =>
        `<b>${(p.label || p.id).slice(0, 60)}</b><br>Type: ${p.type}<br>Cluster: ${p.cluster}${p.similarity ? `<br>Similarity: ${p.similarity.toFixed(4)}` : ''}`
      ),
      customdata: pts,
      mode: 'markers',
      type: 'scatter',
      name: type.charAt(0).toUpperCase() + type.slice(1),
      marker: {
        color: TYPE_COLORS[type],
        size: TYPE_SIZES[type],
        opacity: type === 'citation' ? 0.4 : 0.8,
      },
      hovertemplate: '%{text}<extra></extra>',
    }));

    // Cluster label annotations as a scatter trace with text mode
    if (!selectedCluster) {
      result.push({
        x: centroids.map((c) => c.x),
        y: centroids.map((c) => c.y),
        text: centroids.map((c) => c.name),
        mode: 'text',
        type: 'scatter',
        name: 'Clusters',
        textfont: {
          size: 11,
          color: 'rgba(104,112,118,0.8)',
          family: 'Space Grotesk',
        },
        hoverinfo: 'skip',
        showlegend: false,
      });
    }

    return result;
  }, [points, selectedCluster, centroids]);

  const pointCounts = useMemo(() => {
    const c = { company: 0, citation: 0, query: 0 };
    points.forEach((p) => {
      if (selectedCluster && p.cluster !== selectedCluster) return;
      if (p.type in c) c[p.type as keyof typeof c]++;
    });
    return c;
  }, [points, selectedCluster]);

  return (
    <div className="flex gap-0 h-[calc(100vh-160px)] min-h-[500px]">
      {/* Main scatter — fills available space */}
      <div className="flex-1 bg-bg border border-border rounded-md overflow-hidden">
        <Plot
          data={traces}
          layout={{
            autosize: true,
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: { visible: false },
            yaxis: { visible: false },
            margin: { l: 0, r: 0, t: 0, b: 0 },
            hovermode: 'closest' as const,
            dragmode: 'pan' as const,
            legend: {
              x: 0.01,
              y: 0.99,
              font: { size: 11, family: 'Space Grotesk' },
              bgcolor: 'rgba(251,252,253,0.9)',
              bordercolor: 'var(--border)',
              borderwidth: 1,
            },
          }}
          config={{
            responsive: true,
            scrollZoom: true,
            displayModeBar: false,
          }}
          style={{ width: '100%', height: '100%' }}
          onClick={(data: { points: Array<{ customdata?: EmbeddingPoint }> }) => {
            const pt = data.points[0]?.customdata;
            if (pt && onPointClick) onPointClick(pt);
          }}
        />
      </div>

      {/* Right legend panel — 260px */}
      <div className="w-[260px] shrink-0 bg-surface border border-border border-l-0 rounded-r-md overflow-y-auto p-3 space-y-4">
        {/* Toggle */}
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">Projection</p>
          <div className="flex items-center gap-2">
            <span className={`text-[11px] ${!useUmap ? 'text-accent font-semibold' : 'text-text-secondary'}`}>t-SNE</span>
            <Toggle checked={useUmap} onChange={setUseUmap} />
            <span className={`text-[11px] ${useUmap ? 'text-accent font-semibold' : 'text-text-secondary'}`}>UMAP</span>
          </div>
        </div>

        {/* Point types */}
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">Point Types</p>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#5BA4C4' }} />
              <span className="text-[11px] text-text-primary">Company Content</span>
              <span className="text-[10px] font-mono text-text-tertiary ml-auto">{pointCounts.company}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(91,164,196,0.5)' }} />
              <span className="text-[11px] text-text-primary">Cited Exemplars</span>
              <span className="text-[10px] font-mono text-text-tertiary ml-auto">{pointCounts.citation}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#DC7B18' }} />
              <span className="text-[11px] text-text-primary">Query Points</span>
              <span className="text-[10px] font-mono text-text-tertiary ml-auto">{pointCounts.query}</span>
            </div>
          </div>
        </div>

        {/* Clusters */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Clusters ({clusters.length})</p>
            {selectedCluster && (
              <button
                onClick={() => setSelectedCluster(null)}
                className="text-[10px] text-accent cursor-pointer hover:underline"
              >
                Clear
              </button>
            )}
          </div>
          <div className="space-y-1">
            {clusters.map((cluster, i) => {
              const count = points.filter((p) => p.cluster === cluster).length;
              const isActive = selectedCluster === cluster;
              return (
                <button
                  key={cluster}
                  onClick={() => setSelectedCluster(isActive ? null : cluster)}
                  className={`w-full flex items-center gap-2 p-1.5 rounded-sm transition-colors cursor-pointer text-left ${isActive ? 'bg-accent-subtle' : 'hover:bg-accent-subtle'}`}
                >
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
                  <span className={`text-[11px] truncate ${isActive ? 'text-accent font-medium' : 'text-text-primary'}`}>{cluster}</span>
                  <span className="text-[9px] font-mono text-text-tertiary ml-auto shrink-0">{count}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Stats */}
        <div className="border-t border-border pt-3">
          <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">Total Points</p>
          <p className="font-display text-[16px] font-semibold text-text-primary">
            {selectedCluster ? points.filter((p) => p.cluster === selectedCluster).length : points.length}
          </p>
        </div>
      </div>
    </div>
  );
}
