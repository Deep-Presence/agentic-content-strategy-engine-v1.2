'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { Card, Badge, Skeleton } from '@/components/ui';
import type { EmbeddingPoint, Query } from '@/types';

const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => <Skeleton variant="rectangular" height="100%" width="100%" />,
});

interface QueryMicroscopeProps {
  points: EmbeddingPoint[];
  queries: Query[];
}

export function QueryMicroscope({ points, queries }: QueryMicroscopeProps) {
  const [selectedQueryId, setSelectedQueryId] = useState(queries[0]?.id || '');
  const [searchTerm, setSearchTerm] = useState('');

  const selectedQuery = useMemo(
    () => queries.find((q) => q.id === selectedQueryId),
    [queries, selectedQueryId]
  );

  const filteredQueryList = useMemo(() => {
    if (!searchTerm) return queries;
    const lower = searchTerm.toLowerCase();
    return queries.filter((q) => q.text.toLowerCase().includes(lower));
  }, [queries, searchTerm]);

  // Get points for this query's cluster
  const relevantPoints = useMemo(() => {
    const queryPoint = points.find((p) => p.type === 'query' && p.id === selectedQueryId);
    const cluster = queryPoint?.cluster;
    if (!cluster) return [];
    return points.filter(
      (p) => p.cluster === cluster && (p.type === 'company' || p.type === 'citation' || p.id === selectedQueryId)
    );
  }, [points, selectedQueryId]);

  const traces = useMemo(() => {
    const groups: Record<string, EmbeddingPoint[]> = { query: [], company: [], citation: [] };
    relevantPoints.forEach((p) => { if (groups[p.type]) groups[p.type].push(p); });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result: any[] = [];

    if (groups.company.length > 0) {
      result.push({
        x: groups.company.map((p) => p.x),
        y: groups.company.map((p) => p.y),
        text: groups.company.map((p) => (p.label || p.id).slice(0, 50)),
        mode: 'markers',
        type: 'scatter',
        name: 'Your Content',
        marker: { color: '#5BA4C4', size: 10, symbol: 'diamond' },
        hovertemplate: '%{text}<extra>Company</extra>',
      });
    }

    if (groups.citation.length > 0) {
      // Color code by similarity
      const sims = groups.citation.map((p) => p.similarity ?? 0.5);
      result.push({
        x: groups.citation.map((p) => p.x),
        y: groups.citation.map((p) => p.y),
        text: groups.citation.map((p) => `${(p.label || p.id).slice(0, 50)}<br>Sim: ${(p.similarity ?? 0).toFixed(4)}`),
        mode: 'markers',
        type: 'scatter',
        name: 'Cited Content',
        marker: {
          color: sims,
          colorscale: [[0, '#E5484D'], [0.5, '#DC7B18'], [1, '#34B27B']],
          size: 7,
          showscale: true,
          colorbar: { title: 'Similarity', titlefont: { size: 10 }, tickfont: { size: 9 }, len: 0.5, thickness: 10 },
        },
        hovertemplate: '%{text}<extra>Citation</extra>',
      });
    }

    if (groups.query.length > 0) {
      result.push({
        x: groups.query.map((p) => p.x),
        y: groups.query.map((p) => p.y),
        text: groups.query.map((p) => (p.label || p.id).slice(0, 50)),
        mode: 'markers',
        type: 'scatter',
        name: 'Query',
        marker: { color: '#DC7B18', size: 14, symbol: 'star' },
        hovertemplate: '%{text}<extra>Query</extra>',
      });

      // Connection lines
      const qp = groups.query[0];
      const targets = [...groups.company, ...groups.citation.slice(0, 15)];
      const lx: (number | null)[] = [];
      const ly: (number | null)[] = [];
      targets.forEach((t) => { lx.push(qp.x, t.x, null); ly.push(qp.y, t.y, null); });
      result.push({
        x: lx, y: ly,
        mode: 'lines',
        type: 'scatter',
        name: 'Connections',
        line: { color: 'rgba(220,123,24,0.15)', width: 1, dash: 'dot' },
        hoverinfo: 'skip',
        showlegend: false,
      });
    }

    return result;
  }, [relevantPoints]);

  return (
    <div className="flex gap-4 h-[calc(100vh-200px)] min-h-[400px]">
      {/* Scatter */}
      <div className="flex-1 bg-bg border border-border rounded-md overflow-hidden">
        <div className="p-2 border-b border-border">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search queries..."
            className="w-full h-[26px] px-2 rounded-sm border border-border bg-surface text-[11px] text-text-primary outline-none focus:border-accent"
          />
          {searchTerm && (
            <div className="max-h-[150px] overflow-y-auto mt-1 bg-surface border border-border rounded-sm">
              {filteredQueryList.slice(0, 10).map((q) => (
                <button
                  key={q.id}
                  onClick={() => { setSelectedQueryId(q.id); setSearchTerm(''); }}
                  className="w-full text-left p-1.5 text-[11px] text-text-primary hover:bg-accent-subtle cursor-pointer truncate"
                >
                  {q.text}
                </button>
              ))}
            </div>
          )}
        </div>
        <div style={{ height: 'calc(100% - 42px)' }}>
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
              showlegend: true,
            }}
            config={{ responsive: true, scrollZoom: true, displayModeBar: false }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
      </div>

      {/* Right panel: query analysis */}
      <div className="w-[300px] shrink-0 space-y-3 overflow-y-auto">
        {selectedQuery ? (
          <>
            <Card hoverable={false}>
              <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">Query</p>
              <p className="text-[13px] text-text-primary leading-[1.4] font-medium">{selectedQuery.text}</p>
              <div className="flex gap-1.5 mt-2">
                <Badge variant="info">{selectedQuery.cluster}</Badge>
                <Badge variant={selectedQuery.classification === 'significant_gap' ? 'error' : selectedQuery.classification === 'company_wins' ? 'success' : 'neutral'}>
                  {selectedQuery.classification.replace(/_/g, ' ')}
                </Badge>
              </div>
            </Card>

            <Card hoverable={false}>
              <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">Gap Score</p>
              <p className="font-mono text-[20px] font-semibold text-text-primary">{selectedQuery.gap.toFixed(4)}</p>
              <div className="mt-2 space-y-1 text-[11px] text-text-secondary">
                <p>Citation similarity: {selectedQuery.avgCitationSimilarity.toFixed(4)}</p>
                <p>Company similarity: {selectedQuery.bestCompanyUnit.similarity.toFixed(4)}</p>
              </div>
            </Card>

            {/* Structural comparison table */}
            {selectedQuery.citedExemplars.length > 0 && (
              <Card hoverable={false}>
                <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">Structural Comparison</p>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left p-[4px_6px] text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Metric</th>
                        {selectedQuery.citedExemplars.slice(0, 3).map((ex, i) => (
                          <th key={i} className="text-center p-[4px_6px] text-[9px] font-medium uppercase tracking-[0.06em] text-text-tertiary truncate max-w-[60px]">
                            {ex.domain.slice(0, 12)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(['words', 'headers', 'lists', 'citations', 'paragraphs'] as const).map((metric) => (
                        <tr key={metric} className="border-b border-border-subtle">
                          <td className="p-[4px_6px] text-[10px] text-text-primary capitalize">{metric}</td>
                          {selectedQuery.citedExemplars.slice(0, 3).map((ex, i) => (
                            <td key={i} className="p-[4px_6px] text-[10px] font-mono text-text-primary text-center">
                              {ex.structure[metric]}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {/* Top exemplars */}
            <Card hoverable={false}>
              <p className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-2">Cited Exemplars</p>
              <div className="space-y-2">
                {selectedQuery.citedExemplars.slice(0, 3).map((ex, i) => (
                  <div key={i} className="bg-bg border border-border rounded-md p-2">
                    <p className="text-[11px] font-mono text-accent truncate">{ex.domain}</p>
                    <p className="text-[9px] text-text-tertiary truncate mt-0.5">{ex.url}</p>
                    <p className="text-[10px] font-mono text-text-secondary mt-0.5">sim: {ex.similarity.toFixed(4)}</p>
                  </div>
                ))}
              </div>
            </Card>
          </>
        ) : (
          <Card hoverable={false}>
            <p className="text-[12px] text-text-secondary">Search and select a query above.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
