'use client';

import { Bot, Brain, Search, Sparkles, Globe, Target, TrendingDown } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';
import {
  PLATFORM_SUMMARIES,
  CLUSTER_COLORS,
  CLUSTER_NAMES,
  type PlatformSummary,
} from '../data/sample-data';

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  ChatGPT: <Bot className="h-5 w-5 text-[#d97757]" />,
  Claude: <Brain className="h-5 w-5 text-[#6a9bcc]" />,
  Perplexity: <Search className="h-5 w-5 text-[#788c5d]" />,
  Gemini: <Sparkles className="h-5 w-5 text-[#b0aea5]" />,
};

const PLATFORM_ACCENT: Record<string, string> = {
  ChatGPT: 'border-[#d97757]/30',
  Claude: 'border-[#6a9bcc]/30',
  Perplexity: 'border-[#788c5d]/30',
  Gemini: 'border-[#b0aea5]/30',
};

interface ClusterBarData {
  cluster: string;
  name: string;
  citations: number;
  color: string;
}

function PlatformCard({ platform }: { platform: PlatformSummary }) {
  const clusterData: ClusterBarData[] = Object.entries(platform.per_cluster).map(
    ([key, count]) => ({
      cluster: key,
      name: CLUSTER_NAMES[key] ?? key,
      citations: count,
      color: CLUSTER_COLORS[key] ?? '#b0aea5',
    })
  );

  return (
    <div
      className={cn(
        'rounded-lg border-2 bg-white p-4 space-y-3',
        PLATFORM_ACCENT[platform.name] ?? 'border-gray-200'
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        {PLATFORM_ICONS[platform.name]}
        <h3 className="font-serif text-lg font-semibold text-[#141413]">
          {platform.name}
        </h3>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs font-sans text-[#141413]/50 uppercase tracking-wide">
            Total Citations
          </p>
          <p className="text-2xl font-sans font-bold text-[#141413]">
            {platform.total_citations}
          </p>
        </div>
        <div>
          <p className="text-xs font-sans text-[#141413]/50 uppercase tracking-wide">
            Unique Domains
          </p>
          <div className="flex items-center gap-1.5">
            <Globe className="h-3.5 w-3.5 text-[#141413]/40" />
            <p className="text-2xl font-sans font-bold text-[#141413]">
              {platform.unique_domains}
            </p>
          </div>
        </div>
      </div>

      {/* Avg similarity */}
      <div>
        <p className="text-xs font-sans text-[#141413]/50 uppercase tracking-wide">
          Avg Citation Similarity
        </p>
        <p className="text-lg font-sans font-semibold text-[#141413]">
          {platform.avg_citation_sim.toFixed(4)}
        </p>
      </div>

      {/* Most cited domain */}
      <div>
        <p className="text-xs font-sans text-[#141413]/50 uppercase tracking-wide">
          Most Cited Domain
        </p>
        <p className="text-sm font-sans font-medium text-[#6a9bcc] truncate">
          {platform.most_cited_domain}
        </p>
      </div>

      {/* Best / Worst clusters */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1">
          <Target className="h-3.5 w-3.5 text-[#788c5d]" />
          <span className="text-xs font-sans text-[#141413]/50">Best:</span>
          <Badge variant="green" className="text-xs">
            {platform.best_cluster}
          </Badge>
        </div>
        <div className="flex items-center gap-1">
          <TrendingDown className="h-3.5 w-3.5 text-[#d97757]" />
          <span className="text-xs font-sans text-[#141413]/50">Worst:</span>
          <Badge variant="warning" className="text-xs">
            {platform.worst_cluster}
          </Badge>
        </div>
      </div>

      {/* Mini bar chart */}
      <div className="pt-1">
        <p className="text-xs font-sans text-[#141413]/50 uppercase tracking-wide mb-1">
          Citations per Cluster
        </p>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart
            data={clusterData}
            margin={{ top: 4, right: 4, bottom: 4, left: 4 }}
          >
            <XAxis
              dataKey="cluster"
              tick={{ fontSize: 9, fill: '#141413', opacity: 0.5 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis hide />
            <Tooltip
              contentStyle={{
                backgroundColor: '#faf9f5',
                border: '1px solid #e8e6e1',
                borderRadius: '6px',
                fontSize: '12px',
                fontFamily: 'sans-serif',
              }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={((value: any, _name: any, props: any) => [
                `${value} citations`,
                props.payload.name,
              ]) as any}
              labelFormatter={() => ''}
            />
            <Bar dataKey="citations" radius={[2, 2, 0, 0]} maxBarSize={20}>
              {clusterData.map((entry) => (
                <Cell key={entry.cluster} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function PlatformComparisonDashboard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-serif">Platform Comparison</CardTitle>
        <CardDescription className="font-sans">
          How each AI platform cites content differently
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {PLATFORM_SUMMARIES.map((platform) => (
            <PlatformCard key={platform.name} platform={platform} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
