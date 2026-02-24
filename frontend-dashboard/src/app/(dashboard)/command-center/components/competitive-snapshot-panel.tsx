'use client';

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export interface CompetitorRow {
  domain: string;
  cluster: string;
  gap: number;
  exemplarSim: number;
  topQueries: number;
}

interface CompetitiveSnapshotPanelProps {
  competitors: CompetitorRow[];
}

const COMPETITOR_COLORS = ['#d97757', '#6a9bcc', '#788c5d', '#e8926d', '#4a7ba8', '#a3b88e', '#c44040', '#b0aea5'];

const TOOLTIP_STYLE = {
  backgroundColor: '#ffffff',
  border: '1px solid var(--border-default)',
  borderRadius: 6,
  fontSize: 12,
  fontFamily: 'ui-sans-serif, sans-serif',
};

export function CompetitiveSnapshotPanel({ competitors }: CompetitiveSnapshotPanelProps) {
  const pieData = competitors.map((c) => ({
    name: c.domain,
    value: Math.round(c.exemplarSim * 100),
  }));

  return (
    <div>
      <h3 className="font-serif text-heading-3 font-semibold text-cream-950 mb-3 animate-fade-in-up" style={{ animationDelay: '0.5s' }}>
        Competitive Snapshot
      </h3>
      <Card className="animate-fade-in-up" style={{ animationDelay: '0.55s' }}>
        <CardHeader>
          <CardTitle>Top Competitor Domains</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-6">
            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-body-sm font-sans">
                <thead>
                  <tr className="border-b border-[var(--border-default)]">
                    <th className="text-left text-caption font-medium text-cream-600 uppercase tracking-wider pb-2">Domain</th>
                    <th className="text-left text-caption font-medium text-cream-600 uppercase tracking-wider pb-2">Cluster</th>
                    <th className="text-right text-caption font-medium text-cream-600 uppercase tracking-wider pb-2">Gap</th>
                    <th className="text-right text-caption font-medium text-cream-600 uppercase tracking-wider pb-2">Similarity</th>
                    <th className="text-right text-caption font-medium text-cream-600 uppercase tracking-wider pb-2">Queries</th>
                  </tr>
                </thead>
                <tbody>
                  {competitors.map((c, i) => (
                    <tr key={c.domain} className="border-b border-[var(--border-subtle)] last:border-0">
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: COMPETITOR_COLORS[i % COMPETITOR_COLORS.length] }}
                          />
                          <span className="font-medium text-cream-950">{c.domain}</span>
                        </div>
                      </td>
                      <td className="py-2 text-cream-700">{c.cluster}</td>
                      <td className="py-2 text-right">
                        <Badge variant={c.gap > 0.25 ? 'error' : 'warning'}>
                          {Math.round(c.gap * 100)}%
                        </Badge>
                      </td>
                      <td className="py-2 text-right text-cream-700">
                        {(c.exemplarSim * 100).toFixed(0)}%
                      </td>
                      <td className="py-2 text-right text-cream-700">{c.topQueries}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-caption text-cream-500 mt-2">
                Domains that AI platforms cite instead of Webflow
              </p>
            </div>

            {/* Donut */}
            <div className="flex items-center justify-center">
              <ResponsiveContainer width={180} height={180}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={2}
                    dataKey="value"
                    strokeWidth={0}
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COMPETITOR_COLORS[i % COMPETITOR_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
