'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export interface PlatformData {
  name: string;
  icon: string;
  citationShare: number;
  trend: 'up' | 'flat' | 'down';
  trendPct: number;
  sparklineData: Array<{ week: string; value: number }>;
  color: string;
}

interface PlatformPerformanceGridProps {
  platforms: PlatformData[];
}

function PlatformCard({ platform, index }: { platform: PlatformData; index: number }) {
  const TrendIcon = platform.trend === 'up' ? TrendingUp : platform.trend === 'down' ? TrendingDown : Minus;
  const trendBadge = platform.trend === 'up'
    ? 'green'
    : platform.trend === 'down'
    ? 'error'
    : 'default';
  const trendLabel = platform.trend === 'flat'
    ? 'Flat'
    : `${platform.trendPct > 0 ? '+' : ''}${Math.round(platform.trendPct * 100)}%`;

  return (
    <Card hoverable className="animate-fade-in-up" style={{ animationDelay: `${0.2 + index * 0.06}s` }}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-body-lg">{platform.icon}</span>
            <span className="font-sans text-body-sm font-semibold text-cream-950">{platform.name}</span>
          </div>
          <Badge variant={trendBadge}>
            <TrendIcon className="h-3 w-3 mr-0.5" />
            {trendLabel}
          </Badge>
        </div>

        <p className="font-serif text-heading-1 font-semibold text-cream-950 mb-1">
          {Math.round(platform.citationShare * 100)}%
        </p>
        <p className="text-caption font-sans text-cream-600 mb-3">citation share</p>

        <div className="h-10 -mx-1">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={platform.sparklineData}>
              <YAxis hide domain={['dataMin - 2', 'dataMax + 2']} />
              <Line
                type="monotone"
                dataKey="value"
                stroke={platform.color}
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export function PlatformPerformanceGrid({ platforms }: PlatformPerformanceGridProps) {
  return (
    <div>
      <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-3 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
        Platform Performance
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {platforms.map((p, i) => (
          <PlatformCard key={p.name} platform={p} index={i} />
        ))}
      </div>
    </div>
  );
}
