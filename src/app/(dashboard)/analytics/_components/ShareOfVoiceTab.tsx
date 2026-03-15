'use client';

import { useMemo } from 'react';
import { Card, Badge } from '@/components/ui';
import type { Query } from '@/types';
import {
  ResponsiveContainer,
  AreaChart,
  BarChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LineChart,
  Line,
} from 'recharts';

interface ShareOfVoiceTabProps {
  queries: Query[];
}

const WEEKS = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];

const SOV_COLORS: Record<string, string> = {
  'lovable.dev': 'var(--accent)',
  'bolt.new': '#E5484D',
  'replit.com': '#34B27B',
  'v0.dev': '#886FBF',
  'cursor.com': '#DC7B18',
};

function getCompetitorDomains(queries: Query[]) {
  const counts: Record<string, number> = {};
  queries.forEach((q) => {
    q.citedExemplars.forEach((e) => {
      if (e.domain) counts[e.domain] = (counts[e.domain] || 0) + 1;
    });
  });
  return Object.entries(counts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)
    .map(([domain, citations]) => ({ domain, citations }));
}

function buildSOVTrend() {
  return WEEKS.map((w, i) => ({
    week: w,
    'lovable.dev': +(8 + i * 0.63).toFixed(1),
    'bolt.new': +(18 - i * 0.8).toFixed(1),
    'replit.com': +(15 - i * 0.3).toFixed(1),
    'v0.dev': +(10 + i * 0.2).toFixed(1),
    'cursor.com': +(8 + i * 0.1).toFixed(1),
  }));
}

const tooltipStyle = {
  backgroundColor: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: '6px',
  fontSize: '11px',
};

const CLUSTER_NAMES = ['Mechanism', 'Boundary', 'Category Comparison', 'Decision Criteria', 'Definition', 'Problem/Awareness', 'Best-of/Consideration', 'Branded Evaluation', 'Feature Verification'];

export function ShareOfVoiceTab({ queries }: ShareOfVoiceTabProps) {
  const competitors = useMemo(() => getCompetitorDomains(queries), [queries]);
  const sovData = useMemo(() => buildSOVTrend(), []);
  const domains = Object.keys(SOV_COLORS);

  // SOV by cluster — stacked horizontal bars
  const clusterSOV = useMemo(() => {
    return CLUSTER_NAMES.map((cluster) => {
      const clusterQueries = queries.filter((q) => q.cluster === cluster);
      const total = clusterQueries.length || 1;
      const cited = clusterQueries.filter((q) => q.companyCited).length;
      const compShare = +((cited / total) * 100).toFixed(0);
      // Simulate competitor shares
      return {
        cluster: cluster.length > 18 ? cluster.slice(0, 16) + '...' : cluster,
        You: compShare,
        Competitor1: Math.min(100 - compShare, Math.floor(15 + Math.random() * 20)),
        Competitor2: Math.min(100 - compShare, Math.floor(10 + Math.random() * 15)),
        Other: Math.max(0, 100 - compShare - 30),
      };
    });
  }, [queries]);

  // SOV movement / rank data
  const rankData = useMemo(() => {
    const domains = ['lovable.dev', 'bolt.new', 'replit.com', 'v0.dev', 'cursor.com'];
    return ['W1', 'W4', 'W6', 'W8'].map((w, wi) => {
      const entry: Record<string, string | number> = { week: w };
      domains.forEach((d, di) => {
        const baseRank = di + 1;
        const shift = d === 'lovable.dev' ? -wi * 0.3 : d === 'bolt.new' ? wi * 0.4 : Math.sin(wi + di) * 0.5;
        entry[d] = +(baseRank + shift).toFixed(1);
      });
      return entry;
    });
  }, []);

  return (
    <div className="space-y-4">
      {/* Chart 1 — SOV Trend (Stacked Area) */}
      <Card hoverable={false}>
        <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">
          Share of Voice Over Time
        </h3>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={sovData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
            <XAxis dataKey="week" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} unit="%" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v}%`]} />
            <Legend wrapperStyle={{ fontSize: '10px' }} />
            {domains.map((d) => (
              <Area key={d} type="monotone" dataKey={d} stackId="1" fill={SOV_COLORS[d]} stroke={SOV_COLORS[d]} fillOpacity={d === 'lovable.dev' ? 0.6 : 0.25} />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      {/* Chart 2 — Competitor Breakdown Table */}
      <Card hoverable={false}>
        <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">
          Competitor Breakdown
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                {['Domain', 'Citations', 'SOV %', 'Share'].map((h) => (
                  <th key={h} className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {competitors.map((c) => {
                const total = competitors.reduce((s, x) => s + x.citations, 0);
                const pct = ((c.citations / total) * 100).toFixed(1);
                return (
                  <tr key={c.domain} className="border-b border-border-subtle hover:bg-accent-subtle transition-colors">
                    <td className="p-[6px_10px] text-[12px] font-mono text-text-primary">{c.domain}</td>
                    <td className="p-[6px_10px] text-[12px] font-mono text-text-primary">{c.citations}</td>
                    <td className="p-[6px_10px]"><Badge variant="info">{pct}%</Badge></td>
                    <td className="p-[6px_10px] w-[120px]">
                      <div className="w-full bg-border-subtle rounded-full h-[6px]">
                        <div className="bg-accent h-[6px] rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Row 2: Cluster SOV + Movement */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 3 — SOV by Query Cluster */}
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">
            SOV by Query Cluster
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={clusterSOV} layout="vertical" margin={{ left: 100 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} unit="%" />
              <YAxis type="category" dataKey="cluster" tick={{ fontSize: 9, fill: 'var(--text-secondary)' }} axisLine={false} tickLine={false} width={95} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '10px' }} />
              <Bar dataKey="You" stackId="a" fill="var(--accent)" barSize={14} />
              <Bar dataKey="Competitor1" stackId="a" fill="#E5484D" barSize={14} />
              <Bar dataKey="Competitor2" stackId="a" fill="#34B27B" barSize={14} />
              <Bar dataKey="Other" stackId="a" fill="var(--border)" barSize={14} radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Chart 4 — SOV Movement / Rank over time */}
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">
            SOV Rank Movement
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={rankData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
              <YAxis reversed tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} domain={[0.5, 5.5]} label={{ value: 'Rank', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: 'var(--text-tertiary)' } }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '10px' }} />
              {Object.keys(SOV_COLORS).map((d) => (
                <Line key={d} type="monotone" dataKey={d} stroke={SOV_COLORS[d]} strokeWidth={d === 'lovable.dev' ? 2.5 : 1.5} dot={{ r: d === 'lovable.dev' ? 4 : 2 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
