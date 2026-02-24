'use client';

import { useMemo } from 'react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  BarChart, Bar,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';
import { CONTENT_TYPE_LABELS } from '@/lib/utils/constants';
import type { ContentBriefItem } from '@/types/content';

interface AnalyticsChartsProps {
  briefs: ContentBriefItem[];
  className?: string;
}

const TYPE_COLORS: Record<string, string> = {
  blog: '#788c5d',
  guide: '#6a9bcc',
  case_study: '#d97757',
  product_page: '#b0aea5',
};

const CLUSTER_COLORS = [
  '#d97757', '#6a9bcc', '#788c5d', '#e8926d', '#4a7ba8',
  '#5a6f45', '#c4593a', '#9abfdb', '#a3b88e',
];

export function AnalyticsCharts({ briefs, className }: AnalyticsChartsProps) {
  const typeData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const b of briefs) {
      counts[b.content_type] = (counts[b.content_type] ?? 0) + 1;
    }
    return Object.entries(counts).map(([type, count]) => ({
      name: CONTENT_TYPE_LABELS[type as keyof typeof CONTENT_TYPE_LABELS] ?? type,
      value: count,
      type,
    }));
  }, [briefs]);

  // Mock trend data (in production, would come from historical data)
  const trendData = useMemo(() => {
    const weeks = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];
    return weeks.map((week, i) => ({
      week,
      score: 65 + Math.round(Math.random() * 20 + i * 1.5),
    }));
  }, []);

  const velocityData = useMemo(() => {
    const weeks = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];
    return weeks.map((week) => ({
      week,
      completed: Math.round(Math.random() * 6 + 3),
    }));
  }, []);

  const clusterData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const b of briefs) {
      counts[b.cluster] = (counts[b.cluster] ?? 0) + 1;
    }
    return Object.entries(counts)
      .map(([cluster, count]) => ({ cluster, count }))
      .sort((a, b) => b.count - a.count);
  }, [briefs]);

  return (
    <div className={cn('space-y-6', className)}>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Content Type Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Content Type Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={typeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                    nameKey="name"
                  >
                    {typeData.map((entry) => (
                      <Cell key={entry.type} fill={TYPE_COLORS[entry.type] ?? '#b0aea5'} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: '#fff',
                      border: '1px solid #e8e6dc',
                      borderRadius: '6px',
                      fontSize: '13px',
                      fontFamily: 'system-ui',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-3 mt-2 justify-center">
              {typeData.map((entry) => (
                <div key={entry.type} className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: TYPE_COLORS[entry.type] ?? '#b0aea5' }}
                  />
                  <span className="text-caption font-sans text-cream-700">
                    {entry.name}: {entry.value}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Citability Score Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Citability Score Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e8e6dc" />
                  <XAxis dataKey="week" tick={{ fontSize: 12, fontFamily: 'system-ui', fill: '#6b6960' }} />
                  <YAxis domain={[50, 100]} tick={{ fontSize: 12, fontFamily: 'system-ui', fill: '#6b6960' }} />
                  <Tooltip
                    contentStyle={{
                      background: '#fff',
                      border: '1px solid #e8e6dc',
                      borderRadius: '6px',
                      fontSize: '13px',
                      fontFamily: 'system-ui',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#788c5d"
                    strokeWidth={2}
                    dot={{ fill: '#788c5d', r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cycle Velocity */}
        <Card>
          <CardHeader>
            <CardTitle>Cycle Velocity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={velocityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e8e6dc" />
                  <XAxis dataKey="week" tick={{ fontSize: 12, fontFamily: 'system-ui', fill: '#6b6960' }} />
                  <YAxis tick={{ fontSize: 12, fontFamily: 'system-ui', fill: '#6b6960' }} />
                  <Tooltip
                    contentStyle={{
                      background: '#fff',
                      border: '1px solid #e8e6dc',
                      borderRadius: '6px',
                      fontSize: '13px',
                      fontFamily: 'system-ui',
                    }}
                  />
                  <Bar dataKey="completed" fill="#d97757" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Cluster Coverage */}
        <Card>
          <CardHeader>
            <CardTitle>Cluster Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {clusterData.map((item, idx) => {
                const maxCount = clusterData[0]?.count ?? 1;
                const pct = Math.round((item.count / maxCount) * 100);
                return (
                  <div key={item.cluster} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-body-sm font-sans text-cream-800 truncate max-w-[200px]">
                        {item.cluster}
                      </span>
                      <span className="text-caption font-sans tabular-nums text-cream-600">
                        {item.count}
                      </span>
                    </div>
                    <div className="h-2 bg-cream-300 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: CLUSTER_COLORS[idx % CLUSTER_COLORS.length],
                        }}
                      />
                    </div>
                  </div>
                );
              })}
              {clusterData.length === 0 && (
                <p className="text-body-sm font-sans text-cream-500 text-center py-4">
                  No cluster data available.
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
