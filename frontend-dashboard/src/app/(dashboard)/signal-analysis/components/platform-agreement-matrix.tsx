'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import {
  PLATFORM_AGREEMENT,
  CITATION_EXCLUSIVITY,
  CLUSTER_NAMES,
} from '../data/sample-data';

const PLATFORMS = ['ChatGPT', 'Claude', 'Perplexity', 'Gemini'] as const;

/**
 * Interpolate between white and ocean blue based on value.
 * Range: 0.3 (white) to 0.5+ (full ocean blue #6a9bcc).
 */
function getHeatColor(value: number, isDiagonal: boolean): string {
  if (isDiagonal) return '#f0f4f8';
  const minVal = 0.3;
  const maxVal = 0.5;
  const t = Math.min(1, Math.max(0, (value - minVal) / (maxVal - minVal)));
  // Interpolate RGB: white (255,255,255) → ocean blue (106,155,204)
  const r = Math.round(255 + (106 - 255) * t);
  const g = Math.round(255 + (155 - 255) * t);
  const b = Math.round(255 + (204 - 255) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

function getTextColor(value: number, isDiagonal: boolean): string {
  if (isDiagonal) return '#6a9bcc';
  const minVal = 0.3;
  const maxVal = 0.5;
  const t = Math.min(1, Math.max(0, (value - minVal) / (maxVal - minVal)));
  return t > 0.65 ? '#ffffff' : '#141413';
}

function AgreementHeatmap() {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="font-serif text-base font-semibold text-[#141413]">
          Platform Citation Agreement
        </h3>
        <p className="text-sm font-sans text-[#141413]/60">
          Jaccard similarity between each platform pair&apos;s citation sets
        </p>
      </div>

      {/* Matrix */}
      <div className="overflow-x-auto">
        <div className="min-w-[400px]">
          {/* Column headers */}
          <div className="grid grid-cols-[120px_repeat(4,1fr)] gap-1 mb-1">
            <div /> {/* empty corner */}
            {PLATFORMS.map((platform) => (
              <div
                key={platform}
                className="text-center text-xs font-sans font-medium text-[#141413]/70 py-1"
              >
                {platform}
              </div>
            ))}
          </div>

          {/* Rows */}
          {PLATFORMS.map((rowPlatform) => (
            <div
              key={rowPlatform}
              className="grid grid-cols-[120px_repeat(4,1fr)] gap-1 mb-1"
            >
              {/* Row label */}
              <div className="flex items-center text-xs font-sans font-medium text-[#141413]/70 pr-2 justify-end">
                {rowPlatform}
              </div>

              {/* Cells */}
              {PLATFORMS.map((colPlatform) => {
                const value = PLATFORM_AGREEMENT[rowPlatform]?.[colPlatform] ?? 0;
                const isDiagonal = rowPlatform === colPlatform;

                return (
                  <div
                    key={colPlatform}
                    className={cn(
                      'flex items-center justify-center rounded-md py-3 transition-all',
                      isDiagonal && 'border-2 border-[#6a9bcc]/30 border-dashed'
                    )}
                    style={{
                      backgroundColor: getHeatColor(value, isDiagonal),
                      color: getTextColor(value, isDiagonal),
                    }}
                  >
                    <span
                      className={cn(
                        'text-sm font-sans font-semibold tabular-nums',
                        isDiagonal && 'font-bold'
                      )}
                    >
                      {value.toFixed(2)}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Insight */}
      <div className="rounded-md bg-[#6a9bcc]/8 border border-[#6a9bcc]/20 px-3 py-2">
        <p className="text-xs font-sans text-[#141413]/70 leading-relaxed">
          <span className="font-semibold text-[#6a9bcc]">Insight:</span>{' '}
          ChatGPT and Claude agree on 45% of citations. Perplexity is most
          different from Gemini.
        </p>
      </div>
    </div>
  );
}

interface ExclusivityBarData {
  cluster: string;
  name: string;
  all_4: number;
  three: number;
  two: number;
  one: number;
  none: number;
}

function CitationExclusivityChart() {
  const data: ExclusivityBarData[] = useMemo(
    () =>
      Object.entries(CITATION_EXCLUSIVITY).map(([key, counts]) => ({
        cluster: key,
        name: CLUSTER_NAMES[key] ?? key,
        all_4: counts.all_4,
        three: counts.three,
        two: counts.two,
        one: counts.one,
        none: counts.none,
      })),
    []
  );

  return (
    <div className="space-y-3">
      <div>
        <h3 className="font-serif text-base font-semibold text-[#141413]">
          Citation Exclusivity
        </h3>
        <p className="text-sm font-sans text-[#141413]/60">
          How many platforms cite the same URLs per cluster
        </p>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
        >
          <XAxis
            dataKey="cluster"
            tick={{ fontSize: 11, fill: '#141413', opacity: 0.6 }}
            tickLine={false}
            axisLine={{ stroke: '#e8e6e1' }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#141413', opacity: 0.5 }}
            tickLine={false}
            axisLine={false}
            width={36}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#faf9f5',
              border: '1px solid #e8e6e1',
              borderRadius: '8px',
              fontSize: '12px',
              fontFamily: 'sans-serif',
            }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            labelFormatter={(label: any) => {
              const entry = data.find((d) => d.cluster === String(label));
              return entry ? `${entry.cluster} — ${entry.name}` : String(label);
            }}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            iconType="square"
            iconSize={10}
            wrapperStyle={{ fontSize: '11px', fontFamily: 'sans-serif' }}
          />
          <Bar
            dataKey="all_4"
            name="All 4 platforms"
            stackId="stack"
            fill="#3d6f96"
            radius={[0, 0, 0, 0]}
          />
          <Bar
            dataKey="three"
            name="3 platforms"
            stackId="stack"
            fill="#6a9bcc"
            radius={[0, 0, 0, 0]}
          />
          <Bar
            dataKey="two"
            name="2 platforms"
            stackId="stack"
            fill="#a3c4e0"
            radius={[0, 0, 0, 0]}
          />
          <Bar
            dataKey="one"
            name="1 platform"
            stackId="stack"
            fill="#d4e4f0"
            radius={[0, 0, 0, 0]}
          />
          <Bar
            dataKey="none"
            name="Not cited"
            stackId="stack"
            fill="#d97757"
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function PlatformAgreementMatrix() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-serif">Platform Intelligence</CardTitle>
        <CardDescription className="font-sans">
          Cross-platform citation agreement and exclusivity analysis
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-8">
        <AgreementHeatmap />
        <div className="border-t border-[#e8e6e1]" />
        <CitationExclusivityChart />
      </CardContent>
    </Card>
  );
}
