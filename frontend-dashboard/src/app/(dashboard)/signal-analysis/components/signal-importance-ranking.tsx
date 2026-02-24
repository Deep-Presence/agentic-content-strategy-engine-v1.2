'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import { TrendingUp } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  LabelList,
  Tooltip,
} from 'recharts';
import { SIGNAL_CORRELATIONS } from '../data/sample-data';

const CATEGORY_BADGE_STYLES: Record<string, string> = {
  'Text Composition': 'bg-[#d97757]/10 text-[#d97757] border-[#d97757]/20',
  'Structural Elements': 'bg-[#6a9bcc]/10 text-[#6a9bcc] border-[#6a9bcc]/20',
  'Content Patterns': 'bg-[#788c5d]/10 text-[#788c5d] border-[#788c5d]/20',
  'Factual Density': 'bg-[#a09a8e]/10 text-[#a09a8e] border-[#a09a8e]/20',
};

function getBarColor(correlation: number): string {
  if (correlation > 0.6) return '#d97757';
  if (correlation >= 0.4) return '#6a9bcc';
  return '#c4c0b8';
}

function getStrengthLabel(correlation: number): string {
  if (correlation > 0.6) return 'Strong';
  if (correlation >= 0.4) return 'Medium';
  return 'Weak';
}

interface CustomYTickProps {
  x?: number;
  y?: number;
  payload?: { value: string };
}

function CustomYTick({ x, y, payload }: CustomYTickProps) {
  if (!payload) return null;
  const item = SIGNAL_CORRELATIONS.find((s) => s.signal === payload.value);
  if (!item) return null;

  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={-8}
        y={0}
        dy={4}
        textAnchor="end"
        fill="#141413"
        opacity={0.7}
        fontSize={12}
        fontFamily="system-ui, sans-serif"
      >
        {item.signal}
      </text>
    </g>
  );
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      signal: string;
      correlation: number;
      category: string;
    };
  }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0].payload;

  return (
    <div className="bg-white border border-[#e8e5de] rounded-lg px-3 py-2 shadow-md">
      <p className="text-sm font-sans font-medium text-[#141413]">{data.signal}</p>
      <p className="text-xs font-sans text-[#141413]/60 mt-0.5">{data.category}</p>
      <div className="flex items-center gap-2 mt-1.5">
        <span className="text-sm font-sans font-semibold text-[#141413]">
          r = {data.correlation.toFixed(2)}
        </span>
        <span
          className={cn(
            'text-[10px] font-sans font-medium px-1.5 py-0.5 rounded',
            data.correlation > 0.6
              ? 'bg-[#d97757]/10 text-[#d97757]'
              : data.correlation >= 0.4
                ? 'bg-[#6a9bcc]/10 text-[#6a9bcc]'
                : 'bg-[#c4c0b8]/20 text-[#a09a8e]'
          )}
        >
          {getStrengthLabel(data.correlation)}
        </span>
      </div>
    </div>
  );
}

export default function SignalImportanceRanking() {
  const chartData = [...SIGNAL_CORRELATIONS].sort(
    (a, b) => a.correlation - b.correlation
  );

  const chartHeight = Math.max(400, chartData.length * 36 + 60);

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex items-center gap-2.5">
          <TrendingUp className="h-5 w-5 text-[#d97757]" />
          <div>
            <CardTitle className="font-serif text-xl text-[#141413]">
              Signal Importance Ranking
            </CardTitle>
            <CardDescription className="font-sans text-sm text-[#141413]/50 mt-0.5">
              Correlation between signal presence and citation similarity
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 mb-5">
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-[#d97757]" />
            <span className="text-xs font-sans text-[#141413]/60">
              Strong (&gt;0.6)
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-[#6a9bcc]" />
            <span className="text-xs font-sans text-[#141413]/60">
              Medium (0.4–0.6)
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-[#c4c0b8]" />
            <span className="text-xs font-sans text-[#141413]/60">
              Weak (&lt;0.4)
            </span>
          </div>
        </div>

        {/* Category badges inline */}
        <div className="flex flex-wrap gap-2 mb-4">
          {Array.from(new Set(SIGNAL_CORRELATIONS.map((s) => s.category))).map(
            (cat) => (
              <Badge
                key={cat}
                variant="default"
                className={cn(
                  'text-[10px] font-sans',
                  CATEGORY_BADGE_STYLES[cat] || ''
                )}
              >
                {cat}
              </Badge>
            )
          )}
        </div>

        {/* Chart */}
        <div style={{ width: '100%', height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 5, right: 60, left: 160, bottom: 5 }}
              barCategoryGap="20%"
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#e8e5de"
                horizontal={false}
              />
              <XAxis
                type="number"
                domain={[0, 1]}
                tickCount={6}
                tick={{ fontSize: 11, fontFamily: 'system-ui, sans-serif', fill: '#14141380' }}
                axisLine={{ stroke: '#e8e5de' }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="signal"
                tick={<CustomYTick />}
                axisLine={false}
                tickLine={false}
                width={155}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: '#141413', opacity: 0.03 }}
              />
              <Bar dataKey="correlation" radius={[0, 4, 4, 0]} maxBarSize={24}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.signal}
                    fill={getBarColor(entry.correlation)}
                  />
                ))}
                <LabelList
                  dataKey="correlation"
                  position="right"
                  formatter={(value: string | number | boolean | null | undefined) => Number(value).toFixed(2)}
                  style={{
                    fontSize: 11,
                    fontFamily: 'system-ui, sans-serif',
                    fill: '#141413',
                    opacity: 0.6,
                  }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Insight callout */}
        <div className="mt-5 px-4 py-3 bg-[#d97757]/[0.06] border border-[#d97757]/15 rounded-lg">
          <p className="text-sm font-sans text-[#141413]/70 leading-relaxed">
            <span className="font-semibold text-[#d97757]">Top predictors: </span>
            FAQ sections, table presence, and H2 header count are the 3 strongest
            citation predictors. Prioritize adding these structural elements to
            improve citation likelihood.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
