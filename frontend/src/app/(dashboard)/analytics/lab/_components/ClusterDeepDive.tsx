'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { Card, Badge, Skeleton } from '@/components/ui';
import type { EmbeddingPoint } from '@/types';

const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => <Skeleton variant="rectangular" height="100%" width="100%" />,
});

interface ClusterDeepDiveProps {
  points: EmbeddingPoint[];
  clusters: string[];
  clusterStats: Record<string, {
    queryCount: number;
    avgWordCount: number | null;
    faqRate: number;
    tableRate: number;
    dominantContentType: string;
    requiredElements?: string[];
  }>;
}

const TYPE_COLORS: Record<string, string> = {
  company: '#5BA4C4',
  citation: 'rgba(91,164,196,0.5)',
  query: '#DC7B18',
};

export function ClusterDeepDive({ points, clusters, clusterStats }: ClusterDeepDiveProps) {
  const [selectedCluster, setSelectedCluster] = useState(clusters[0] || '');

  const filteredPoints = useMemo(
    () => points.filter((p) => p.cluster === selectedCluster),
    [points, selectedCluster]
  );

  const traces = useMemo(() => {
    const groups: Record<string, EmbeddingPoint[]> = { company: [], citation: [], query: [] };
    filteredPoints.forEach((p) => {
      if (groups[p.type]) groups[p.type].push(p);
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result: any[] = Object.entries(groups).map(([type, pts]) => ({
      x: pts.map((p) => p.x),
      y: pts.map((p) => p.y),
      text: pts.map((p) => `${(p.label || p.id).slice(0, 60)}<br>Type: ${type}`),
      mode: 'markers',
      type: 'scatter',
      name: type.charAt(0).toUpperCase() + type.slice(1),
      marker: {
        color: TYPE_COLORS[type],
        size: type === 'company' ? 10 : type === 'query' ? 7 : 5,
      },
      hovertemplate: '%{text}<extra></extra>',
    }));

    // Gap lines: dashed lines from company to nearest citations
    const compPts = groups.company;
    const citPts = groups.citation.slice(0, 25);
    if (compPts.length > 0 && citPts.length > 0) {
      const gapX: (number | null)[] = [];
      const gapY: (number | null)[] = [];
      compPts.forEach((cp) => {
        citPts.forEach((ct) => {
          gapX.push(cp.x, ct.x, null);
          gapY.push(cp.y, ct.y, null);
        });
      });
      result.push({
        x: gapX,
        y: gapY,
        mode: 'lines',
        type: 'scatter',
        name: 'Gap Lines',
        line: { color: 'rgba(229,72,77,0.15)', width: 1, dash: 'dot' },
        hoverinfo: 'skip',
        showlegend: true,
      });
    }

    return result;
  }, [filteredPoints]);

  const stats = clusterStats[selectedCluster];
  const typeCounts = useMemo(() => {
    const c = { company: 0, citation: 0, query: 0 };
    filteredPoints.forEach((p) => { if (p.type in c) c[p.type as keyof typeof c]++; });
    return c;
  }, [filteredPoints]);

  return (
    <div className="flex gap-4 h-[calc(100vh-200px)] min-h-[400px]">
      {/* Scatter */}
      <div className="flex-1 bg-bg border border-border rounded-md overflow-hidden">
        <div className="flex items-center gap-2 p-2 border-b border-border">
          <select
            value={selectedCluster}
            onChange={(e) => setSelectedCluster(e.target.value)}
            className="h-[26px] px-2 rounded-sm border border-border bg-surface text-[11px] text-text-primary outline-none cursor-pointer"
          >
            {clusters.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <span className="text-[10px] font-mono text-text-tertiary">{filteredPoints.length} points</span>
        </div>
        <div style={{ height: 'calc(100% - 38px)' }}>
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
              legend: { x: 0.01, y: 0.99, font: { size: 10, family: 'Space Grotesk' } },
            }}
            config={{ responsive: true, scrollZoom: true, displayModeBar: false }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      </div>

      {/* Right panel: cluster stats */}
      <div className="w-[280px] shrink-0 space-y-3 overflow-y-auto">
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">{selectedCluster}</h3>
          <div className="space-y-2.5">
            {[
              { label: 'Query Count', value: stats?.queryCount ?? typeCounts.query },
              { label: 'Company Pages', value: typeCounts.company },
              { label: 'Citations', value: typeCounts.citation },
              { label: 'FAQ Rate', value: stats?.faqRate ? `${(stats.faqRate * 100).toFixed(0)}%` : 'N/A' },
              { label: 'Table Rate', value: stats?.tableRate ? `${(stats.tableRate * 100).toFixed(0)}%` : 'N/A' },
            ].map(({ label, value }) => (
              <div key={label}>
                <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">{label}</p>
                <p className="text-[16px] font-semibold text-text-primary mt-0.5">{value}</p>
              </div>
            ))}
            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Content Type</p>
              <Badge variant="info" className="mt-1">{stats?.dominantContentType || 'N/A'}</Badge>
            </div>
          </div>
        </Card>

        <Card hoverable={false}>
          <h3 className="text-[13px] font-semibold text-text-primary tracking-[-0.01em] mb-2">Gap Analysis</h3>
          <p className="text-[11px] text-text-secondary leading-relaxed">
            Dashed lines show the embedding distance between your content and cited exemplars.
            Shorter lines = closer match. Long lines indicate content gaps to address.
          </p>
          <div className="mt-2 flex gap-2">
            <div className="flex items-center gap-1.5 text-[10px]">
              <span className="w-2 h-2 rounded-full" style={{ background: '#5BA4C4' }} /> Your content
            </div>
            <div className="flex items-center gap-1.5 text-[10px]">
              <span className="w-2 h-2 rounded-full" style={{ background: 'rgba(91,164,196,0.5)' }} /> Citations
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
