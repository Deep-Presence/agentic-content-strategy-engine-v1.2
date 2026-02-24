'use client';

import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import type { ContentBriefItem } from '@/types/content';

interface ContentPerformanceRowProps {
  citabilityTrend: Array<{ week: string; score: number }>;
  velocityTrend: Array<{ week: string; completed: number }>;
  briefs: ContentBriefItem[];
}

const TOOLTIP_STYLE = {
  backgroundColor: '#ffffff',
  border: '1px solid var(--border-default)',
  borderRadius: 6,
  fontSize: 12,
  fontFamily: 'ui-sans-serif, sans-serif',
};

const TICK_STYLE = {
  fontSize: 10,
  fill: 'var(--text-tertiary)',
  fontFamily: 'ui-sans-serif, sans-serif',
};

const TYPE_COLORS: Record<string, string> = {
  blog: '#d97757',
  guide: '#6a9bcc',
  case_study: '#788c5d',
  product_page: '#e8926d',
};

export function ContentPerformanceRow({
  citabilityTrend,
  velocityTrend,
  briefs,
}: ContentPerformanceRowProps) {
  const typeData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const b of briefs) {
      counts[b.content_type] = (counts[b.content_type] ?? 0) + 1;
    }
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [briefs]);

  return (
    <div>
      <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-3 animate-fade-in-up" style={{ animationDelay: '0.4s' }}>
        Content Performance
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Citability Trend */}
        <Card className="animate-fade-in-up" style={{ animationDelay: '0.4s' }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-body-sm">Citability Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={citabilityTrend} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradSage" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#788c5d" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#788c5d" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="week" tick={TICK_STYLE} axisLine={false} tickLine={false} />
                <YAxis domain={[60, 100]} hide />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="score" stroke="#788c5d" fill="url(#gradSage)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Weekly Output */}
        <Card className="animate-fade-in-up" style={{ animationDelay: '0.45s' }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-body-sm">Weekly Output</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={velocityTrend} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                <XAxis dataKey="week" tick={TICK_STYLE} axisLine={false} tickLine={false} />
                <YAxis hide />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="completed" fill="#d97757" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Content by Type */}
        <Card className="animate-fade-in-up" style={{ animationDelay: '0.5s' }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-body-sm">Content by Type</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <ResponsiveContainer width={120} height={120}>
                <PieChart>
                  <Pie
                    data={typeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={35}
                    outerRadius={55}
                    paddingAngle={3}
                    dataKey="value"
                    strokeWidth={0}
                  >
                    {typeData.map((entry) => (
                      <Cell key={entry.name} fill={TYPE_COLORS[entry.name] ?? '#b0aea5'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5">
                {typeData.map((entry) => (
                  <div key={entry.name} className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: TYPE_COLORS[entry.name] ?? '#b0aea5' }}
                    />
                    <span className="text-caption font-sans text-cream-700 capitalize">
                      {entry.name.replace('_', ' ')}
                    </span>
                    <span className="text-caption font-sans font-semibold text-cream-900">
                      {entry.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
