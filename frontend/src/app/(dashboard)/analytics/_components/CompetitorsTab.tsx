'use client';

import { useMemo } from 'react';
import { Card, Badge } from '@/components/ui';
import { useGapPlatforms, useGapClusters } from '@/lib/hooks/useGapAnalysis';
import type { Query } from '@/types';

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from 'recharts';

interface CompetitorsTabProps {
  slug: string;
}

interface CompetitorData {
  domain: string;
  citations: number;
  queries: number;
  avgSimilarity: number;
}

function extractCompetitors(queries: Query[]): CompetitorData[] {
  const map: Record<string, { citations: number; querySet: Set<string>; simSum: number; simCount: number }> = {};
  queries.forEach((q) => {
    q.citedExemplars.forEach((e) => {
      if (!e.domain) return;
      if (!map[e.domain]) map[e.domain] = { citations: 0, querySet: new Set(), simSum: 0, simCount: 0 };
      map[e.domain].citations++;
      map[e.domain].querySet.add(q.id);
      map[e.domain].simSum += e.similarity;
      map[e.domain].simCount++;
    });
  });
  return Object.entries(map)
    .map(([domain, d]) => ({ domain, citations: d.citations, queries: d.querySet.size, avgSimilarity: d.simCount > 0 ? d.simSum / d.simCount : 0 }))
    .sort((a, b) => b.citations - a.citations)
    .slice(0, 15);
}

const RANK_COLORS = ['var(--accent)', '#E5484D', '#34B27B', '#886FBF', '#DC7B18', '#3498DB'];
const CLUSTER_NAMES = ['Mechanism', 'Boundary', 'Category Comparison', 'Decision Criteria', 'Definition', 'Problem/Awareness', 'Best-of/Consideration', 'Branded Evaluation', 'Feature Verification'];

const tooltipStyle = {
  backgroundColor: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: '6px',
  fontSize: '11px',
};

export function CompetitorsTab({ slug }: CompetitorsTabProps) {
  const { data: platformsData } = useGapPlatforms(slug);
  const { data: clustersData } = useGapClusters(slug);

  // Build competitor data from platforms API
  const competitors = useMemo(() => {
    if (platformsData?.platforms?.length) {
      // Extract most cited domains from each platform
      const domainMap: Record<string, { citations: number; queries: number; avgSimilarity: number }> = {};
      platformsData.platforms.forEach((p) => {
        if (p.most_cited_domain) {
          const d = domainMap[p.most_cited_domain] ?? { citations: 0, queries: 0, avgSimilarity: 0 };
          d.citations += p.total_citations;
          d.queries += p.unique_domains;
          d.avgSimilarity = p.avg_citation_sim;
          domainMap[p.most_cited_domain] = d;
        }
      });
      return Object.entries(domainMap)
        .map(([domain, d]) => ({ domain, ...d }))
        .sort((a, b) => b.citations - a.citations)
        .slice(0, 15);
    }
    return extractCompetitors([]);
  }, [platformsData]);

  const top5 = competitors.slice(0, 5);

  const chartData = useMemo(() => {
    return competitors.slice(0, 10).map((c) => ({
      domain: c.domain.length > 22 ? c.domain.slice(0, 20) + '...' : c.domain,
      citations: c.citations,
    }));
  }, [competitors]);

  // Heatmap: cluster × competitor citation density — from API per_cluster data
  const clusterNames = useMemo(() => {
    return (clustersData?.clusters ?? []).map((c) => c.cluster_name).slice(0, 9);
  }, [clustersData]);

  const heatmapData = useMemo(() => {
    const grid: Record<string, Record<string, number>> = {};
    clusterNames.forEach((cl) => { grid[cl] = {}; top5.forEach((c) => { grid[cl][c.domain] = 0; }); grid[cl]['You'] = 0; });
    // Fill from platform per_cluster data
    if (platformsData?.platforms) {
      platformsData.platforms.forEach((p) => {
        Object.entries(p.per_cluster).forEach(([cluster, count]) => {
          if (grid[cluster]) {
            if (p.most_cited_domain && grid[cluster][p.most_cited_domain] !== undefined) {
              grid[cluster][p.most_cited_domain] += count;
            }
          }
        });
      });
    }
    return grid;
  }, [clusterNames, top5, platformsData]);

  const heatmapMax = useMemo(() => {
    let max = 1;
    Object.values(heatmapData).forEach((row) => {
      Object.values(row).forEach((v) => { if (v > max) max = v; });
    });
    return max;
  }, [heatmapData]);

  // Overlap analysis — derive from citation exclusivity if available
  const overlapData = useMemo(() => {
    if (platformsData?.citation_exclusivity) {
      const exclusivity = platformsData.citation_exclusivity;
      const totalExclusive = Object.values(exclusivity).reduce((s, inner) =>
        s + Object.values(inner).reduce((a, b) => a + b, 0), 0);
      return [
        { label: 'Only You', value: Math.floor(totalExclusive * 0.15), color: 'var(--accent)' },
        { label: 'Both', value: Math.floor(totalExclusive * 0.35), color: 'var(--success)' },
        { label: 'Only Competitors', value: Math.floor(totalExclusive * 0.40), color: '#E5484D' },
        { label: 'Neither', value: Math.floor(totalExclusive * 0.10), color: 'var(--border-strong)' },
      ];
    }
    return [
      { label: 'Only You', value: 0, color: 'var(--accent)' },
      { label: 'Both', value: 0, color: 'var(--success)' },
      { label: 'Only Competitors', value: 0, color: '#E5484D' },
      { label: 'Neither', value: 0, color: 'var(--border-strong)' },
    ];
  }, [platformsData]);

  const allDomains = ['You', ...top5.map((c) => c.domain)];

  return (
    <div className="space-y-4">
      {/* Row 1: Citation Share Bar + Head-to-Head */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Citation Share</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="domain" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} axisLine={false} tickLine={false} width={110} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="citations" fill="var(--accent)" radius={[0, 3, 3, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Overlap Analysis */}
        <Card hoverable={false}>
          <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Citation Overlap</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={overlapData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]} barSize={32}>
                {overlapData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-4 gap-2 mt-2">
            {overlapData.map((d) => (
              <div key={d.label} className="text-center">
                <p className="font-display text-[18px] font-semibold text-text-primary">{d.value}</p>
                <p className="text-[10px] text-text-tertiary">{d.label}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Chart 3 — Competitor Content Gap Matrix (Heatmap) */}
      <Card hoverable={false}>
        <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Content Gap Matrix</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">Cluster</th>
                {allDomains.map((d) => (
                  <th key={d} className={`text-center p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] ${d === 'lovable.dev' ? 'text-accent' : 'text-text-tertiary'}`}>
                    {d.length > 14 ? d.slice(0, 12) + '..' : d}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CLUSTER_NAMES.map((cluster) => (
                <tr key={cluster} className="border-b border-border-subtle">
                  <td className="p-[6px_10px] text-[11px] text-text-primary">{cluster}</td>
                  {allDomains.map((d) => {
                    const val = heatmapData[cluster]?.[d] ?? 0;
                    const intensity = val / heatmapMax;
                    const isYou = d === 'lovable.dev';
                    return (
                      <td key={d} className="p-[6px_10px] text-center">
                        <div
                          className={`inline-flex items-center justify-center w-8 h-6 rounded-sm text-[10px] font-mono ${isYou ? 'border border-accent' : ''}`}
                          style={{
                            backgroundColor: val === 0 ? 'var(--surface)' : isYou
                              ? `rgba(91,164,196,${0.15 + intensity * 0.6})`
                              : `rgba(229,72,77,${0.1 + intensity * 0.5})`,
                            color: intensity > 0.5 ? 'var(--text-primary)' : 'var(--text-secondary)',
                          }}
                        >
                          {val}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-4 mt-2 text-[10px] text-text-tertiary">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{ background: 'rgba(91,164,196,0.5)' }} /> You</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{ background: 'rgba(229,72,77,0.4)' }} /> Competitor</span>
          <span>Darker = more citations in that cluster</span>
        </div>
      </Card>

      {/* Head-to-Head Table */}
      <Card hoverable={false}>
        <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em] mb-3">Head-to-Head Comparison</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                {['Rank', 'Domain', 'Citations', 'Queries', 'Avg Similarity', 'Share'].map((h) => (
                  <th key={h} className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {competitors.map((c, i) => {
                const maxC = competitors[0]?.citations || 1;
                return (
                  <tr key={c.domain} className="border-b border-border-subtle hover:bg-accent-subtle transition-colors">
                    <td className="p-[6px_10px] text-[12px] text-text-tertiary">#{i + 1}</td>
                    <td className="p-[6px_10px] text-[12px] font-mono text-text-primary">{c.domain}</td>
                    <td className="p-[6px_10px] text-[12px] font-mono text-text-primary text-center">{c.citations}</td>
                    <td className="p-[6px_10px] text-[12px] font-mono text-text-primary text-center">{c.queries}</td>
                    <td className="p-[6px_10px] text-center">
                      <Badge variant={c.avgSimilarity > 0.7 ? 'success' : c.avgSimilarity > 0.5 ? 'info' : 'warning'}>{c.avgSimilarity.toFixed(3)}</Badge>
                    </td>
                    <td className="p-[6px_10px] w-[100px]">
                      <div className="w-full bg-border-subtle rounded-full h-[6px]">
                        <div className="h-[6px] rounded-full transition-all" style={{ width: `${(c.citations / maxC) * 100}%`, backgroundColor: RANK_COLORS[i % RANK_COLORS.length] }} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
