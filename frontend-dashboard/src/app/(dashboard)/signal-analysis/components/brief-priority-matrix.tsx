'use client';

import { useMemo } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Label,
  ZAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import { CLUSTER_COLORS, CLUSTER_NAMES, getTopGapQueries, type QueryData } from '../data/sample-data';

interface BriefPriorityMatrixProps {
  queries: QueryData[];
}

interface MatrixDataPoint {
  id: string;
  text: string;
  cluster_id: string;
  cluster_name: string;
  gap_score: number;
  impact: number;
  exemplar_size: number;
  fill: string;
  top_exemplar_sim: number;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: MatrixDataPoint }> }) {
  if (!active || !payload || payload.length === 0) return null;

  const data = payload[0].payload;

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-3 shadow-lg max-w-xs">
      <p className="font-serif text-sm font-semibold text-[#141413] mb-1.5 leading-snug">
        {data.text}
      </p>
      <div className="flex items-center gap-2 mb-2">
        <Badge
          variant="default"
          className="text-[10px] px-1.5 py-0"
          style={{ backgroundColor: data.fill, color: '#fff' }}
        >
          {data.cluster_name}
        </Badge>
      </div>
      <div className="space-y-1 text-xs text-stone-600 font-sans">
        <div className="flex justify-between">
          <span>Gap Score:</span>
          <span className="font-medium text-[#141413]">{data.gap_score.toFixed(4)}</span>
        </div>
        <div className="flex justify-between">
          <span>Est. Impact:</span>
          <span className="font-medium text-[#141413]">{data.impact.toFixed(1)}</span>
        </div>
        <div className="flex justify-between">
          <span>Exemplar Similarity:</span>
          <span className="font-medium text-[#141413]">{data.top_exemplar_sim.toFixed(4)}</span>
        </div>
      </div>
    </div>
  );
}

export default function BriefPriorityMatrix({ queries }: BriefPriorityMatrixProps) {
  const { dataByCluster, medianX, medianY, xDomain, yDomain } = useMemo(() => {
    const top25 = getTopGapQueries(queries, 25);

    const points: MatrixDataPoint[] = top25.map((q) => {
      const impact = (q.target_words.max / 1000) * q.gap_score * 10;
      return {
        id: q.id,
        text: q.text,
        cluster_id: q.cluster_id,
        cluster_name: q.cluster_name,
        gap_score: q.gap_score,
        impact,
        exemplar_size: q.top_exemplar_sim * 400 + 60,
        fill: CLUSTER_COLORS[q.cluster_id] || '#999',
        top_exemplar_sim: q.top_exemplar_sim,
      };
    });

    const gapScores = points.map((p) => p.gap_score).sort((a, b) => a - b);
    const impacts = points.map((p) => p.impact).sort((a, b) => a - b);

    const median = (arr: number[]) => {
      const mid = Math.floor(arr.length / 2);
      return arr.length % 2 !== 0 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
    };

    const mX = median(gapScores);
    const mY = median(impacts);

    const minX = Math.min(...gapScores) * 0.95;
    const maxX = Math.max(...gapScores) * 1.05;
    const minY = Math.min(...impacts) * 0.85;
    const maxY = Math.max(...impacts) * 1.1;

    // Group by cluster for separate Scatter series
    const grouped: Record<string, MatrixDataPoint[]> = {};
    for (const p of points) {
      if (!grouped[p.cluster_id]) grouped[p.cluster_id] = [];
      grouped[p.cluster_id].push(p);
    }

    return {
      dataByCluster: grouped,
      medianX: mX,
      medianY: mY,
      xDomain: [minX, maxX] as [number, number],
      yDomain: [minY, maxY] as [number, number],
    };
  }, [queries]);

  const clusterIds = Object.keys(dataByCluster).sort();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-serif text-lg">Brief Priority Matrix</CardTitle>
        <CardDescription className="font-sans text-sm text-stone-500">
          Gap severity vs estimated content impact
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* Legend */}
        <div className="flex flex-wrap gap-2 mb-4">
          {clusterIds.map((cid) => (
            <div key={cid} className="flex items-center gap-1.5 text-xs font-sans text-stone-600">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: CLUSTER_COLORS[cid] }}
              />
              <span>{CLUSTER_NAMES[cid] || cid}</span>
            </div>
          ))}
        </div>

        <div className="h-[480px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 30, right: 30, bottom: 30, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e0" />
              <XAxis
                type="number"
                dataKey="gap_score"
                domain={xDomain}
                name="Gap Score"
                tick={{ fontSize: 11, fill: '#78716c', fontFamily: 'var(--font-sans)' }}
                tickLine={false}
                axisLine={{ stroke: '#d6d3ce' }}
              >
                <Label
                  value="Gap Severity →"
                  position="insideBottom"
                  offset={-15}
                  style={{ fontSize: 12, fill: '#57534e', fontFamily: 'var(--font-sans)' }}
                />
              </XAxis>
              <YAxis
                type="number"
                dataKey="impact"
                domain={yDomain}
                name="Est. Impact"
                tick={{ fontSize: 11, fill: '#78716c', fontFamily: 'var(--font-sans)' }}
                tickLine={false}
                axisLine={{ stroke: '#d6d3ce' }}
              >
                <Label
                  value="Est. Impact →"
                  angle={-90}
                  position="insideLeft"
                  offset={5}
                  style={{ fontSize: 12, fill: '#57534e', fontFamily: 'var(--font-sans)' }}
                />
              </YAxis>
              <ZAxis type="number" dataKey="exemplar_size" range={[40, 260]} />

              {/* Quadrant reference lines */}
              <ReferenceLine
                x={medianX}
                stroke="#a8a29e"
                strokeDasharray="4 4"
                strokeWidth={1}
              />
              <ReferenceLine
                y={medianY}
                stroke="#a8a29e"
                strokeDasharray="4 4"
                strokeWidth={1}
              />

              {/* Quadrant labels */}
              <text
                x="95%"
                y="8%"
                textAnchor="end"
                fill="#d97757"
                fontSize={11}
                fontWeight={600}
                fontFamily="var(--font-sans)"
              >
                Strategic Investment
              </text>
              <text
                x="8%"
                y="8%"
                textAnchor="start"
                fill="#788c5d"
                fontSize={11}
                fontWeight={600}
                fontFamily="var(--font-sans)"
              >
                Quick Wins
              </text>
              <text
                x="95%"
                y="95%"
                textAnchor="end"
                fill="#a8a29e"
                fontSize={11}
                fontWeight={600}
                fontFamily="var(--font-sans)"
              >
                Diminishing Returns
              </text>
              <text
                x="8%"
                y="95%"
                textAnchor="start"
                fill="#78716c"
                fontSize={11}
                fontWeight={600}
                fontFamily="var(--font-sans)"
              >
                Maintenance
              </text>

              <Tooltip
                content={<CustomTooltip />}
                cursor={{ strokeDasharray: '3 3', stroke: '#d6d3ce' }}
              />

              {clusterIds.map((cid) => (
                <Scatter
                  key={cid}
                  name={CLUSTER_NAMES[cid] || cid}
                  data={dataByCluster[cid]}
                  fill={CLUSTER_COLORS[cid]}
                  fillOpacity={0.75}
                  stroke={CLUSTER_COLORS[cid]}
                  strokeWidth={1}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {/* Quadrant explanation */}
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { label: 'Strategic Investment', desc: 'High gap, high impact — prioritize these', color: '#d97757' },
            { label: 'Quick Wins', desc: 'Low gap, high impact — easy to address', color: '#788c5d' },
            { label: 'Diminishing Returns', desc: 'High gap, low impact — deprioritize', color: '#a8a29e' },
            { label: 'Maintenance', desc: 'Low gap, low impact — monitor only', color: '#78716c' },
          ].map((q) => (
            <div key={q.label} className="flex items-start gap-2">
              <span
                className="mt-1 inline-block h-2 w-2 shrink-0 rounded-sm"
                style={{ backgroundColor: q.color }}
              />
              <div>
                <p className="text-xs font-medium text-[#141413] font-sans">{q.label}</p>
                <p className="text-[10px] text-stone-500 font-sans leading-tight">{q.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
