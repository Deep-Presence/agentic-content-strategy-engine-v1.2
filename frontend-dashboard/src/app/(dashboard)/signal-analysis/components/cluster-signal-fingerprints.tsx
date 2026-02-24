'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { Fingerprint } from 'lucide-react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts';
import {
  CLUSTER_FINGERPRINTS,
  CLUSTER_COLORS,
  CLUSTER_NAMES,
} from '../data/sample-data';

const AXES = [
  { key: 'word_count', label: 'Words' },
  { key: 'headers', label: 'Headers' },
  { key: 'lists', label: 'Lists' },
  { key: 'tables', label: 'Tables' },
  { key: 'faq', label: 'FAQ' },
  { key: 'stats', label: 'Stats' },
  { key: 'citations', label: 'Citations' },
] as const;

interface FingerPrintChartProps {
  clusterId: string;
  data: Record<string, number>;
  color: string;
  name: string;
}

function FingerprintChart({ clusterId, data, color, name }: FingerPrintChartProps) {
  const chartData = AXES.map((axis) => ({
    axis: axis.label,
    value: data[axis.key] ?? 0,
  }));

  return (
    <div className="flex flex-col items-center">
      <div className="flex items-center gap-2 mb-1">
        <span
          className="h-2.5 w-2.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <h4 className="text-sm font-sans font-medium text-[#141413]/80 truncate max-w-[160px]">
          {clusterId} {name}
        </h4>
      </div>
      <div style={{ width: '100%', height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
            <PolarGrid
              stroke="#e8e5de"
              strokeWidth={0.8}
            />
            <PolarAngleAxis
              dataKey="axis"
              tick={{
                fontSize: 9,
                fontFamily: 'system-ui, sans-serif',
                fill: '#141413',
                opacity: 0.5,
              }}
              tickLine={false}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 1]}
              tick={false}
              axisLine={false}
            />
            <Radar
              name={name}
              dataKey="value"
              stroke={color}
              fill={color}
              fillOpacity={0.2}
              strokeWidth={1.5}
              dot={{
                r: 2,
                fill: color,
                stroke: color,
                strokeWidth: 0,
              }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function ClusterSignalFingerprints() {
  const clusterIds = Object.keys(CLUSTER_FINGERPRINTS).sort();

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex items-center gap-2.5">
          <Fingerprint className="h-5 w-5 text-[#6a9bcc]" />
          <div>
            <CardTitle className="font-serif text-xl text-[#141413]">
              Cluster Signal Fingerprints
            </CardTitle>
            <CardDescription className="font-sans text-sm text-[#141413]/50 mt-0.5">
              Structural DNA patterns that distinguish each cluster
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {clusterIds.map((id) => (
            <div
              key={id}
              className="rounded-lg border border-[#e8e5de]/80 bg-[#faf9f5]/50 p-2"
            >
              <FingerprintChart
                clusterId={id}
                data={CLUSTER_FINGERPRINTS[id]}
                color={CLUSTER_COLORS[id] || '#6a9bcc'}
                name={CLUSTER_NAMES[id] || id}
              />
            </div>
          ))}
        </div>

        {/* Legend for axes */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          {AXES.map((axis) => (
            <span
              key={axis.key}
              className="text-[10px] font-sans text-[#141413]/40"
            >
              {axis.label}
            </span>
          ))}
          <span className="text-[10px] font-sans text-[#141413]/30 ml-2">
            Values normalized 0–1
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
