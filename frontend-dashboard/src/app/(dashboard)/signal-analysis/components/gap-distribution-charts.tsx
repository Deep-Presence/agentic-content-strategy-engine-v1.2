'use client';

import { useMemo, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ScatterChart,
  Scatter,
  ZAxis,
  ReferenceLine,
  Cell,
  ResponsiveContainer,
  Legend,
  ErrorBar,
  ComposedChart,
  Line,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { CLUSTER_COLORS, CLUSTER_NAMES, type QueryData } from '../data/sample-data';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GapDistributionChartsProps {
  queries: QueryData[];
}

// ---------------------------------------------------------------------------
// Histogram bin config
// ---------------------------------------------------------------------------

const HISTOGRAM_BINS = [
  { label: '0.00–0.05', min: 0, max: 0.05 },
  { label: '0.05–0.10', min: 0.05, max: 0.1 },
  { label: '0.10–0.15', min: 0.1, max: 0.15 },
  { label: '0.15–0.20', min: 0.15, max: 0.2 },
  { label: '0.20–0.25', min: 0.2, max: 0.25 },
  { label: '0.25–0.30', min: 0.25, max: 0.3 },
  { label: '0.30+', min: 0.3, max: Infinity },
];

// Gradient from sage green to terracotta
const BIN_COLORS = [
  '#788c5d',
  '#8b9a5e',
  '#a0a35e',
  '#b8a05c',
  '#c89460',
  '#d48a5e',
  '#d97757',
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (sorted[base + 1] !== undefined) {
    return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
  }
  return sorted[base];
}

function median(arr: number[]): number {
  const sorted = [...arr].sort((a, b) => a - b);
  return quantile(sorted, 0.5);
}

function mean(arr: number[]): number {
  if (arr.length === 0) return 0;
  return arr.reduce((s, v) => s + v, 0) / arr.length;
}

// ---------------------------------------------------------------------------
// Custom Tooltips
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function HistogramTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border border-[#141413]/10 bg-white px-3 py-2 text-xs font-sans shadow-sm">
      <p className="font-medium text-[#141413]">Bin: {label}</p>
      <p className="text-[#141413]/70">
        {payload[0].value} {payload[0].value === 1 ? 'query' : 'queries'}
      </p>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ScatterTooltip({ active, payload }: any) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload as {
    company_sim: number;
    citation_sim: number;
    text: string;
    cluster_id: string;
    cluster_name: string;
  };
  if (!data) return null;
  return (
    <div className="max-w-[280px] rounded-md border border-[#141413]/10 bg-white px-3 py-2 text-xs font-sans shadow-sm">
      <p className="font-medium text-[#141413] leading-snug mb-1 line-clamp-3">
        {data.text}
      </p>
      <div className="flex items-center gap-1.5 text-[#141413]/60">
        <span
          className="h-2 w-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: CLUSTER_COLORS[data.cluster_id] ?? '#888' }}
        />
        <span>{data.cluster_id}: {data.cluster_name}</span>
      </div>
      <div className="mt-1 space-y-0.5 text-[#141413]/70">
        <p>Company: <span className="font-mono">{data.company_sim.toFixed(4)}</span></p>
        <p>Citation: <span className="font-mono">{data.citation_sim.toFixed(4)}</span></p>
      </div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function BoxPlotTooltip({ active, payload }: any) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0]?.payload as {
    cluster: string;
    clusterName: string;
    min: number;
    q1: number;
    median: number;
    q3: number;
    max: number;
    count: number;
  };
  if (!data) return null;
  return (
    <div className="rounded-md border border-[#141413]/10 bg-white px-3 py-2 text-xs font-sans shadow-sm">
      <p className="font-medium text-[#141413] mb-1">
        {data.cluster}: {data.clusterName}
      </p>
      <div className="space-y-0.5 text-[#141413]/70 font-mono">
        <p>Min: {data.min.toFixed(4)}</p>
        <p>Q1: {data.q1.toFixed(4)}</p>
        <p>Median: <span className="font-semibold text-[#d97757]">{data.median.toFixed(4)}</span></p>
        <p>Q3: {data.q3.toFixed(4)}</p>
        <p>Max: {data.max.toFixed(4)}</p>
        <p className="text-[#141413]/50 pt-0.5">{data.count} queries</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom Box Plot shape for Recharts
// ---------------------------------------------------------------------------

interface BoxPlotShapeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: {
    cluster: string;
    min: number;
    q1: number;
    median: number;
    q3: number;
    max: number;
    base: number;
    iqr: number;
    whiskerLow: number;
    whiskerHigh: number;
    color: string;
  };
  // For scaling y values
  yScale?: (v: number) => number;
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function GapDistributionCharts({ queries }: GapDistributionChartsProps) {
  // --- Histogram data ------------------------------------------------------
  const histogramData = useMemo(() => {
    return HISTOGRAM_BINS.map((bin, i) => {
      const count = queries.filter((q) => {
        if (bin.max === Infinity) return q.gap_score >= bin.min;
        return q.gap_score >= bin.min && q.gap_score < bin.max;
      }).length;
      return { label: bin.label, count, color: BIN_COLORS[i] };
    });
  }, [queries]);

  const gapScores = useMemo(() => queries.map((q) => q.gap_score), [queries]);
  const meanGap = useMemo(() => mean(gapScores), [gapScores]);
  const medianGap = useMemo(() => median(gapScores), [gapScores]);

  // Map labels to approximate numeric centers for reference lines
  const medianBinIndex = useMemo(() => {
    for (let i = 0; i < HISTOGRAM_BINS.length; i++) {
      const bin = HISTOGRAM_BINS[i];
      if (bin.max === Infinity) return medianGap >= bin.min ? i : i - 1;
      if (medianGap >= bin.min && medianGap < bin.max) return i;
    }
    return 0;
  }, [medianGap]);

  // --- Scatter data --------------------------------------------------------
  const scatterData = useMemo(() => {
    return queries.map((q) => ({
      company_sim: q.company_sim,
      citation_sim: q.citation_sim,
      text: q.text,
      cluster_id: q.cluster_id,
      cluster_name: q.cluster_name,
      fill: CLUSTER_COLORS[q.cluster_id] ?? '#888',
    }));
  }, [queries]);

  // Scatter axis range
  const simRange = useMemo(() => {
    const allSims = queries.flatMap((q) => [q.company_sim, q.citation_sim]);
    const lo = Math.floor(Math.min(...allSims) * 100) / 100;
    const hi = Math.ceil(Math.max(...allSims) * 100) / 100;
    return { min: Math.max(0, lo - 0.02), max: Math.min(1, hi + 0.02) };
  }, [queries]);

  // --- Box plot data -------------------------------------------------------
  const boxPlotData = useMemo(() => {
    const clusters = new Map<string, number[]>();
    queries.forEach((q) => {
      const existing = clusters.get(q.cluster_id) ?? [];
      existing.push(q.gap_score);
      clusters.set(q.cluster_id, existing);
    });

    const result = Array.from(clusters.entries()).map(([clusterId, scores]) => {
      const sorted = [...scores].sort((a, b) => a - b);
      const q1Val = quantile(sorted, 0.25);
      const medVal = quantile(sorted, 0.5);
      const q3Val = quantile(sorted, 0.75);
      const minVal = sorted[0];
      const maxVal = sorted[sorted.length - 1];

      return {
        cluster: clusterId,
        clusterName: CLUSTER_NAMES[clusterId] ?? clusterId,
        min: minVal,
        q1: q1Val,
        median: medVal,
        q3: q3Val,
        max: maxVal,
        count: scores.length,
        color: CLUSTER_COLORS[clusterId] ?? '#888',
        // For stacking: base starts at min, whiskerLow = q1 - min, iqr = q3 - q1, whiskerHigh = max - q3
        base: minVal,
        whiskerLow: q1Val - minVal,
        iqr: q3Val - q1Val,
        whiskerHigh: maxVal - q3Val,
      };
    });

    // Sort by median desc (worst clusters first)
    result.sort((a, b) => b.median - a.median);
    return result;
  }, [queries]);

  // Unique clusters for scatter legend
  const scatterLegendItems = useMemo(() => {
    const seen = new Set<string>();
    return queries
      .filter((q) => {
        if (seen.has(q.cluster_id)) return false;
        seen.add(q.cluster_id);
        return true;
      })
      .map((q) => ({
        id: q.cluster_id,
        name: q.cluster_name,
        color: CLUSTER_COLORS[q.cluster_id] ?? '#888',
      }))
      .sort((a, b) => a.id.localeCompare(b.id));
  }, [queries]);

  // --- Render --------------------------------------------------------------

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="font-serif text-lg">Gap Analysis Distribution</CardTitle>
        <CardDescription className="text-xs text-[#141413]/60 font-sans">
          Statistical overview of gap scores across all {queries.length} queries
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ---- Chart 1: Histogram ---- */}
          <div className="space-y-2">
            <h4 className="font-serif text-sm font-semibold text-[#141413]">
              Gap Score Distribution
            </h4>
            <p className="text-[10px] text-[#141413]/50 font-sans">
              Mean: <span className="font-mono">{meanGap.toFixed(4)}</span> | Median:{' '}
              <span className="font-mono">{medianGap.toFixed(4)}</span>
            </p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={histogramData}
                margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(20,20,19,0.06)"
                  vertical={false}
                />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 9, fill: '#141413', opacity: 0.5 }}
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(20,20,19,0.1)' }}
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                  height={48}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#141413', opacity: 0.5 }}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                />
                <Tooltip content={<HistogramTooltip />} cursor={{ fill: 'rgba(217,119,87,0.06)' }} />
                {/* Reference lines for mean and median */}
                <ReferenceLine
                  x={histogramData[medianBinIndex]?.label}
                  stroke="#d97757"
                  strokeDasharray="4 4"
                  strokeWidth={1.5}
                  label={{
                    value: 'Median',
                    position: 'top',
                    fill: '#d97757',
                    fontSize: 9,
                  }}
                />
                <Bar
                  dataKey="count"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={40}
                >
                  {histogramData.map((entry, i) => (
                    <Cell key={`cell-${i}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* ---- Chart 2: Scatter ---- */}
          <div className="space-y-2">
            <h4 className="font-serif text-sm font-semibold text-[#141413]">
              Citation vs Company Similarity
            </h4>
            <p className="text-[10px] text-[#141413]/50 font-sans">
              Above diagonal = citations win, below = company wins
            </p>
            <ResponsiveContainer width="100%" height={240}>
              <ScatterChart
                margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(20,20,19,0.06)"
                />
                <XAxis
                  type="number"
                  dataKey="company_sim"
                  name="Company Sim"
                  domain={[simRange.min, simRange.max]}
                  tick={{ fontSize: 10, fill: '#141413', opacity: 0.5 }}
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(20,20,19,0.1)' }}
                  label={{
                    value: 'Company Sim',
                    position: 'insideBottom',
                    offset: -2,
                    fill: '#141413',
                    opacity: 0.4,
                    fontSize: 9,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="citation_sim"
                  name="Citation Sim"
                  domain={[simRange.min, simRange.max]}
                  tick={{ fontSize: 10, fill: '#141413', opacity: 0.5 }}
                  tickLine={false}
                  axisLine={false}
                  label={{
                    value: 'Citation Sim',
                    angle: -90,
                    position: 'insideLeft',
                    offset: 20,
                    fill: '#141413',
                    opacity: 0.4,
                    fontSize: 9,
                  }}
                />
                <ZAxis range={[32, 32]} />
                <Tooltip content={<ScatterTooltip />} cursor={false} />
                {/* Diagonal line y=x */}
                <ReferenceLine
                  segment={[
                    { x: simRange.min, y: simRange.min },
                    { x: simRange.max, y: simRange.max },
                  ]}
                  stroke="#141413"
                  strokeDasharray="6 3"
                  strokeOpacity={0.2}
                  strokeWidth={1}
                />
                <Scatter
                  data={scatterData}
                  fillOpacity={0.7}
                  strokeWidth={0}
                >
                  {scatterData.map((entry, i) => (
                    <Cell key={`dot-${i}`} fill={entry.fill} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            {/* Mini legend */}
            <div className="flex flex-wrap gap-x-3 gap-y-1 px-1">
              {scatterLegendItems.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center gap-1 text-[9px] text-[#141413]/50"
                >
                  <span
                    className="h-2 w-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: item.color }}
                  />
                  <span>{item.id}</span>
                </div>
              ))}
            </div>
          </div>

          {/* ---- Chart 3: Box Plot approximation ---- */}
          <div className="space-y-2">
            <h4 className="font-serif text-sm font-semibold text-[#141413]">
              Gap Score Spread by Cluster
            </h4>
            <p className="text-[10px] text-[#141413]/50 font-sans">
              Sorted by median gap score (worst first)
            </p>
            <div className="h-[240px] w-full">
              <BoxPlotVisualization data={boxPlotData} />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Custom Box Plot (SVG-based since Recharts lacks native box plot support)
// ---------------------------------------------------------------------------

interface BoxPlotDataPoint {
  cluster: string;
  clusterName: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  count: number;
  color: string;
}

function BoxPlotVisualization({ data }: { data: BoxPlotDataPoint[] }) {
  const config = useMemo(() => {
    const allValues = data.flatMap((d) => [d.min, d.max]);
    const yMin = Math.floor(Math.min(...allValues) * 100) / 100;
    const yMax = Math.ceil(Math.max(...allValues) * 100) / 100;
    return { yMin: Math.max(0, yMin - 0.01), yMax: yMax + 0.01 };
  }, [data]);

  const padding = { top: 16, right: 16, bottom: 32, left: 44 };
  const svgWidth = 320;
  const svgHeight = 240;
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  const xScale = (i: number) =>
    padding.left + (i + 0.5) * (chartWidth / data.length);

  const yScale = (val: number) => {
    const ratio = (val - config.yMin) / (config.yMax - config.yMin);
    return padding.top + chartHeight * (1 - ratio);
  };

  const barWidth = Math.min(24, (chartWidth / data.length) * 0.6);

  // Y-axis ticks
  const yTicks = useMemo(() => {
    const count = 5;
    const step = (config.yMax - config.yMin) / count;
    return Array.from({ length: count + 1 }, (_, i) => config.yMin + step * i);
  }, [config]);

  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  return (
    <div className="relative w-full h-full">
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        className="w-full h-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Grid lines */}
        {yTicks.map((tick, i) => (
          <g key={`tick-${i}`}>
            <line
              x1={padding.left}
              x2={svgWidth - padding.right}
              y1={yScale(tick)}
              y2={yScale(tick)}
              stroke="rgba(20,20,19,0.06)"
              strokeDasharray="3 3"
            />
            <text
              x={padding.left - 6}
              y={yScale(tick)}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={9}
              fill="rgba(20,20,19,0.5)"
              fontFamily="ui-monospace, monospace"
            >
              {tick.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Box plots */}
        {data.map((d, i) => {
          const cx = xScale(i);
          const halfBar = barWidth / 2;

          return (
            <g
              key={d.cluster}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
              className="cursor-pointer"
            >
              {/* Whisker line (min to max) */}
              <line
                x1={cx}
                x2={cx}
                y1={yScale(d.max)}
                y2={yScale(d.min)}
                stroke={d.color}
                strokeWidth={1.5}
                opacity={0.5}
              />

              {/* Whisker caps */}
              <line
                x1={cx - halfBar * 0.5}
                x2={cx + halfBar * 0.5}
                y1={yScale(d.max)}
                y2={yScale(d.max)}
                stroke={d.color}
                strokeWidth={1.5}
                opacity={0.6}
              />
              <line
                x1={cx - halfBar * 0.5}
                x2={cx + halfBar * 0.5}
                y1={yScale(d.min)}
                y2={yScale(d.min)}
                stroke={d.color}
                strokeWidth={1.5}
                opacity={0.6}
              />

              {/* IQR box (q1 to q3) */}
              <rect
                x={cx - halfBar}
                y={yScale(d.q3)}
                width={barWidth}
                height={Math.max(1, yScale(d.q1) - yScale(d.q3))}
                fill={d.color}
                fillOpacity={hoveredIdx === i ? 0.35 : 0.2}
                stroke={d.color}
                strokeWidth={1.5}
                rx={2}
              />

              {/* Median line */}
              <line
                x1={cx - halfBar}
                x2={cx + halfBar}
                y1={yScale(d.median)}
                y2={yScale(d.median)}
                stroke={d.color}
                strokeWidth={2.5}
              />

              {/* Cluster label */}
              <text
                x={cx}
                y={svgHeight - padding.bottom + 14}
                textAnchor="middle"
                fontSize={9}
                fill="rgba(20,20,19,0.6)"
                fontFamily="system-ui, sans-serif"
                fontWeight={500}
              >
                {d.cluster}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Tooltip overlay */}
      {hoveredIdx !== null && data[hoveredIdx] && (
        <div
          className="absolute pointer-events-none z-20 rounded-md border border-[#141413]/10 bg-white px-3 py-2 text-xs font-sans shadow-sm"
          style={{
            left: `${(xScale(hoveredIdx) / svgWidth) * 100}%`,
            top: `${(yScale(data[hoveredIdx].q3) / svgHeight) * 100 - 4}%`,
            transform: 'translate(-50%, -100%)',
          }}
        >
          <p className="font-medium text-[#141413] mb-0.5">
            {data[hoveredIdx].cluster}: {data[hoveredIdx].clusterName}
          </p>
          <div className="space-y-0.5 text-[#141413]/70 font-mono text-[10px]">
            <p>Max: {data[hoveredIdx].max.toFixed(4)}</p>
            <p>Q3: {data[hoveredIdx].q3.toFixed(4)}</p>
            <p className="font-semibold text-[#d97757]">
              Median: {data[hoveredIdx].median.toFixed(4)}
            </p>
            <p>Q1: {data[hoveredIdx].q1.toFixed(4)}</p>
            <p>Min: {data[hoveredIdx].min.toFixed(4)}</p>
            <p className="text-[#141413]/40 pt-0.5">{data[hoveredIdx].count} queries</p>
          </div>
        </div>
      )}
    </div>
  );
}
