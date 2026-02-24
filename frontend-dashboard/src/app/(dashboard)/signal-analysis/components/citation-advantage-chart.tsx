'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  Label,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CLUSTER_NAMES, type QueryData } from '../data/sample-data';

interface CitationAdvantageChartProps {
  queries: QueryData[];
}

interface ClusterAverage {
  cluster: string;
  name: string;
  shortName: string;
  citationSim: number;
  companySim: number;
  gap: number;
}

interface TooltipPayloadItem {
  name: string;
  value: number;
  color: string;
  dataKey: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const citationVal = payload.find((p) => p.dataKey === 'citationSim')?.value ?? 0;
  const companyVal = payload.find((p) => p.dataKey === 'companySim')?.value ?? 0;
  const gap = citationVal - companyVal;

  return (
    <div className="bg-white border border-stone-200 rounded-lg shadow-lg px-4 py-3 text-sm">
      <p className="font-semibold text-stone-800 mb-2">{label}</p>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm"
            style={{ backgroundColor: '#6a9bcc' }}
          />
          <span className="text-stone-600">Citation Similarity:</span>
          <span className="font-mono font-semibold text-stone-800">
            {citationVal.toFixed(4)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm"
            style={{ backgroundColor: '#788c5d' }}
          />
          <span className="text-stone-600">Company Similarity:</span>
          <span className="font-mono font-semibold text-stone-800">
            {companyVal.toFixed(4)}
          </span>
        </div>
        <div className="border-t border-stone-100 pt-1 mt-1">
          <div className="flex items-center gap-2">
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: '#d97757' }}
            />
            <span className="text-stone-600">Gap:</span>
            <span className="font-mono font-semibold text-red-600">
              {gap > 0 ? '+' : ''}
              {gap.toFixed(4)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function CitationAdvantageChart({ queries }: CitationAdvantageChartProps) {
  const clusterData = useMemo(() => {
    const grouped: Record<
      string,
      { citationSims: number[]; companySims: number[] }
    > = {};

    for (const q of queries) {
      if (!grouped[q.cluster_id]) {
        grouped[q.cluster_id] = { citationSims: [], companySims: [] };
      }
      grouped[q.cluster_id].citationSims.push(q.citation_sim);
      grouped[q.cluster_id].companySims.push(q.company_sim);
    }

    const result: ClusterAverage[] = Object.entries(grouped)
      .map(([clusterId, data]) => {
        const citationSim =
          data.citationSims.reduce((a, b) => a + b, 0) /
          data.citationSims.length;
        const companySim =
          data.companySims.reduce((a, b) => a + b, 0) /
          data.companySims.length;
        const fullName =
          CLUSTER_NAMES[clusterId as keyof typeof CLUSTER_NAMES] || clusterId;
        // Truncate name for x-axis label
        const shortName =
          fullName.length > 16 ? fullName.substring(0, 14) + '...' : fullName;

        return {
          cluster: clusterId,
          name: fullName,
          shortName,
          citationSim: parseFloat(citationSim.toFixed(4)),
          companySim: parseFloat(companySim.toFixed(4)),
          gap: parseFloat((citationSim - companySim).toFixed(4)),
        };
      })
      .sort((a, b) => {
        const numA = parseInt(a.cluster.replace('C', ''));
        const numB = parseInt(b.cluster.replace('C', ''));
        return numA - numB;
      });

    return result;
  }, [queries]);

  const maxGapCluster = useMemo(() => {
    if (clusterData.length === 0) return null;
    return clusterData.reduce((max, item) =>
      item.gap > max.gap ? item : max
    );
  }, [clusterData]);

  // Compute domain bounds for y-axis
  const yMin = useMemo(() => {
    if (clusterData.length === 0) return 0;
    const allVals = clusterData.flatMap((d) => [d.citationSim, d.companySim]);
    return Math.floor(Math.min(...allVals) * 20) / 20; // round down to nearest 0.05
  }, [clusterData]);

  const yMax = useMemo(() => {
    if (clusterData.length === 0) return 1;
    const allVals = clusterData.flatMap((d) => [d.citationSim, d.companySim]);
    return Math.ceil(Math.max(...allVals) * 20) / 20; // round up to nearest 0.05
  }, [clusterData]);

  return (
    <Card className="bg-white border-stone-200/60 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-serif font-semibold text-stone-900">
          Citation vs Company Similarity by Cluster
        </CardTitle>
        <p className="text-sm text-stone-500 mt-0.5">
          Gap between citations and company content across query clusters
        </p>
      </CardHeader>
      <CardContent className="pt-2 pb-4">
        <div className="h-[380px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={clusterData}
              margin={{ top: 20, right: 24, left: 8, bottom: 20 }}
              barCategoryGap="20%"
              barGap={2}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#e8e5de"
                vertical={false}
              />
              <XAxis
                dataKey="shortName"
                tick={{ fontSize: 11, fill: '#78756e' }}
                tickLine={false}
                axisLine={{ stroke: '#d4d1ca' }}
                angle={-25}
                textAnchor="end"
                height={60}
                interval={0}
              />
              <YAxis
                domain={[yMin, yMax]}
                tick={{ fontSize: 11, fill: '#78756e' }}
                tickLine={false}
                axisLine={{ stroke: '#d4d1ca' }}
                tickFormatter={(v: number) => v.toFixed(2)}
              >
                <Label
                  value="Cosine Similarity"
                  angle={-90}
                  position="insideLeft"
                  style={{
                    textAnchor: 'middle',
                    fill: '#8a8880',
                    fontSize: 11,
                  }}
                  offset={0}
                />
              </YAxis>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                verticalAlign="top"
                height={36}
                iconType="rect"
                iconSize={10}
                formatter={(value: string) => (
                  <span className="text-xs text-stone-600">{value}</span>
                )}
              />

              {/* Reference line at overall average gap */}
              {maxGapCluster && (
                <ReferenceLine
                  y={maxGapCluster.citationSim}
                  stroke="#d97757"
                  strokeDasharray="4 4"
                  strokeWidth={1}
                  opacity={0.5}
                />
              )}

              <Bar
                dataKey="citationSim"
                name="Citation Similarity"
                fill="#6a9bcc"
                radius={[3, 3, 0, 0]}
                maxBarSize={36}
              >
                {clusterData.map((entry) => (
                  <Cell
                    key={entry.cluster}
                    fill="#6a9bcc"
                    opacity={
                      maxGapCluster && entry.cluster === maxGapCluster.cluster
                        ? 1
                        : 0.8
                    }
                  />
                ))}
              </Bar>
              <Bar
                dataKey="companySim"
                name="Company Similarity"
                fill="#788c5d"
                radius={[3, 3, 0, 0]}
                maxBarSize={36}
              >
                {clusterData.map((entry) => (
                  <Cell
                    key={entry.cluster}
                    fill="#788c5d"
                    opacity={
                      maxGapCluster && entry.cluster === maxGapCluster.cluster
                        ? 1
                        : 0.8
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Annotation for largest gap */}
        {maxGapCluster && (
          <div className="mt-2 flex items-center justify-center gap-2 text-xs">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: '#d97757' }}
            />
            <span className="text-stone-500">
              Largest gap:{' '}
              <span className="font-semibold text-stone-700">
                {maxGapCluster.name}
              </span>{' '}
              ({maxGapCluster.cluster}) &mdash;{' '}
              <span className="font-mono text-red-600">
                {maxGapCluster.gap > 0 ? '+' : ''}
                {maxGapCluster.gap.toFixed(4)}
              </span>{' '}
              delta
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
