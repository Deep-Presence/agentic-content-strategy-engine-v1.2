'use client';

import { useMemo } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PLATFORM_SUMMARIES, CLUSTER_COLORS, CLUSTER_NAMES } from '../data/sample-data';

interface SliceData {
  cluster: string;
  name: string;
  value: number;
  color: string;
}

interface TooltipPayloadItem {
  name: string;
  value: number;
  payload: SliceData;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}

function DonutTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0];
  return (
    <div className="bg-white border border-stone-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <div className="flex items-center gap-2 mb-1">
        <span
          className="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
          style={{ backgroundColor: data.payload.color }}
        />
        <span className="font-semibold text-stone-800">{data.payload.name}</span>
      </div>
      <p className="text-stone-500">
        {data.value} citation{data.value !== 1 ? 's' : ''}
      </p>
    </div>
  );
}

interface PlatformDonutProps {
  platform: string;
  icon: string;
  totalCitations: number;
  slices: SliceData[];
}

function PlatformDonut({ platform, icon, totalCitations, slices }: PlatformDonutProps) {
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-[140px] h-[140px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              cx="50%"
              cy="50%"
              innerRadius={38}
              outerRadius={62}
              paddingAngle={1.5}
              dataKey="value"
              strokeWidth={0}
              animationBegin={0}
              animationDuration={800}
            >
              {slices.map((slice, i) => (
                <Cell
                  key={i}
                  fill={slice.color}
                  opacity={0.85}
                  className="hover:opacity-100 transition-opacity"
                />
              ))}
            </Pie>
            <Tooltip content={<DonutTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-xl font-serif font-bold text-stone-800">
            {totalCitations}
          </span>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-1.5">
        <span className="text-base">{icon}</span>
        <span className="text-sm font-medium text-stone-700">{platform}</span>
      </div>
    </div>
  );
}

const PLATFORM_ICONS: Record<string, string> = {
  ChatGPT: '\u{1F916}',
  Claude: '\u{1F9E0}',
  Perplexity: '\u{1F50D}',
  Gemini: '\u{2728}',
};

export function PlatformCitationDonuts() {
  const platformData = useMemo(() => {
    return PLATFORM_SUMMARIES.map((platform) => {
      const slices: SliceData[] = Object.entries(platform.per_cluster)
        .map(([clusterId, count]) => ({
          cluster: clusterId,
          name:
            CLUSTER_NAMES[clusterId as keyof typeof CLUSTER_NAMES] || clusterId,
          value: count,
          color:
            CLUSTER_COLORS[clusterId as keyof typeof CLUSTER_COLORS] ||
            '#8a8880',
        }))
        .filter((s) => s.value > 0)
        .sort((a, b) => b.value - a.value);

      const totalCitations = slices.reduce((sum, s) => sum + s.value, 0);

      return {
        platform: platform.name,
        icon: PLATFORM_ICONS[platform.name] || '\u{1F310}',
        totalCitations,
        slices,
      };
    });
  }, []);

  return (
    <Card className="bg-white border-stone-200/60 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-serif font-semibold text-stone-900">
          AI Platform Citation Distribution
        </CardTitle>
        <p className="text-sm text-stone-500 mt-0.5">
          How citations are distributed across query clusters per platform
        </p>
      </CardHeader>
      <CardContent className="pt-4 pb-5">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
          {platformData.map((p) => (
            <PlatformDonut
              key={p.platform}
              platform={p.platform}
              icon={p.icon}
              totalCitations={p.totalCitations}
              slices={p.slices}
            />
          ))}
        </div>

        {/* Legend */}
        <div className="mt-6 pt-4 border-t border-stone-100">
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5">
            {Object.entries(CLUSTER_NAMES).map(([id, name]) => (
              <div key={id} className="flex items-center gap-1.5">
                <span
                  className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                  style={{
                    backgroundColor:
                      CLUSTER_COLORS[id as keyof typeof CLUSTER_COLORS] ||
                      '#8a8880',
                  }}
                />
                <span className="text-[10px] text-stone-500 whitespace-nowrap">
                  {id}: {name}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
