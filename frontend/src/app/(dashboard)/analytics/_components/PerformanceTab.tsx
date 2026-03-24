'use client';

import { useMemo, useState } from 'react';
import { Card, Badge, Sparkline } from '@/components/ui';
import type { Query, Cluster } from '@/types';
import {
  ResponsiveContainer,
  ComposedChart,
  LineChart,
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from 'recharts';

interface PerformanceTabProps {
  queries: Query[];
  clusters: Cluster[];
}

/* ── Demo data generators (seeded from real report data) ────────── */

const WEEKS = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];

const PLATFORM_COLORS: Record<string, string> = {
  ChatGPT: '#10A37F',
  Claude: 'var(--accent)',
  Perplexity: '#DC7B18',
  'Google AI Overview': '#4285F4',
  Gemini: '#886FBF',
};

const PLATFORM_IDS = ['ChatGPT', 'Claude', 'Perplexity', 'Google AI Overview', 'Gemini'];

function buildCitationMomentum(byPlatform: boolean) {
  const baseTotals = [180, 220, 260, 340, 420, 510, 580, 640];
  const newCitations = [180, 40, 40, 80, 80, 90, 70, 60];

  if (!byPlatform) {
    return WEEKS.map((w, i) => ({
      week: w,
      total: baseTotals[i],
      new: newCitations[i],
    }));
  }

  const splits = {
    ChatGPT: [0.28, 0.30, 0.29, 0.31, 0.30, 0.29, 0.28, 0.27],
    Claude: [0.22, 0.21, 0.23, 0.22, 0.24, 0.25, 0.26, 0.28],
    Perplexity: [0.20, 0.19, 0.18, 0.18, 0.19, 0.20, 0.21, 0.22],
    'Google AI Overview': [0.18, 0.18, 0.19, 0.18, 0.17, 0.16, 0.15, 0.14],
    Gemini: [0.12, 0.12, 0.11, 0.11, 0.10, 0.10, 0.10, 0.09],
  };

  return WEEKS.map((w, i) => {
    const entry: Record<string, string | number> = { week: w };
    Object.entries(splits).forEach(([plat, pcts]) => {
      entry[plat] = Math.round(baseTotals[i] * pcts[i]);
    });
    return entry;
  });
}

function buildSOVTrend() {
  return WEEKS.map((w, i) => ({
    week: w,
    'lovable.dev': +(8 + i * 0.63).toFixed(1),
    'bolt.new': +(18 - i * 0.8).toFixed(1),
    'replit.com': +(15 - i * 0.3).toFixed(1),
    'v0.dev': +(10 + i * 0.2).toFixed(1),
  }));
}

function buildPlatformBreakdown(queries: Query[]) {
  const platforms = [
    { id: 'chatgpt', label: 'ChatGPT', color: '#10A37F' },
    { id: 'claude', label: 'Claude', color: '#5BA4C4' },
    { id: 'perplexity', label: 'Perplexity', color: '#DC7B18' },
    { id: 'google_ai_overview', label: 'Google AI Overview', color: '#4285F4' },
    { id: 'gemini', label: 'Gemini', color: '#886FBF' },
  ];

  return platforms
    .map((p) => {
      const cited = queries.filter((q) => q.companyCited && q.platforms.includes(p.id as never)).length;
      const total = queries.length;
      return {
        platform: p.label,
        cited,
        total,
        rate: +((cited / Math.max(total, 1)) * 100).toFixed(1),
        color: p.color,
      };
    })
    .sort((a, b) => b.rate - a.rate);
}

function buildCitationAccuracy() {
  return PLATFORM_IDS.map((p) => ({
    platform: p,
    accurate: Math.floor(60 + Math.random() * 30),
    errors: Math.floor(5 + Math.random() * 15),
  }));
}

function buildCrawlActivity() {
  const bots = ['GPTBot', 'ClaudeBot', 'PerplexityBot', 'GoogleBot', 'GeminiBot'];
  return WEEKS.map((w, i) => {
    const entry: Record<string, string | number> = { week: w };
    bots.forEach((bot, bi) => {
      entry[bot] = Math.floor(200 + i * 40 + bi * 30 + Math.sin(i + bi) * 50);
    });
    return entry;
  });
}

function buildBrandSearchLift() {
  return WEEKS.map((w, i) => ({
    week: w,
    brandedSearch: 1200 + i * 180 + Math.floor(Math.sin(i) * 100),
    aiCitations: 180 + i * 65,
  }));
}

function buildPublishedContent(queries: Query[]) {
  const groups = queries.reduce<Record<string, Query[]>>((acc, q) => {
    if (!acc[q.cluster]) acc[q.cluster] = [];
    acc[q.cluster].push(q);
    return acc;
  }, {});

  return Object.entries(groups)
    .slice(0, 7)
    .map(([cluster, qs], i) => {
      const best = qs.reduce((a, b) =>
        b.bestCompanyUnit.similarity > a.bestCompanyUnit.similarity ? b : a, qs[0]);
      return {
        id: i + 1,
        title: best.text,
        cluster,
        citations: Math.floor(best.avgCitationSimilarity * 100),
        cpsScore: +(0.45 + Math.random() * 0.4).toFixed(3),
        referralSessions: Math.floor(50 + Math.random() * 200),
        velocity: +(1 + Math.random() * 5).toFixed(1),
        trend: [3, 5, 4, 7, 8, 6, 9, 11].map((v) => v + Math.floor(Math.random() * 3)),
        status: i < 5 ? 'published' : 'draft',
        date: `2025-01-${String(8 + i * 3).padStart(2, '0')}`,
      };
    });
}

const BOT_COLORS: Record<string, string> = {
  GPTBot: '#10A37F',
  ClaudeBot: '#5BA4C4',
  PerplexityBot: '#DC7B18',
  GoogleBot: '#4285F4',
  GeminiBot: '#886FBF',
};

/* ── Inline chart filter toggle ─────────────────────────────────── */
function ChartHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h3 className="text-[14px] font-semibold text-text-primary tracking-[-0.01em]">
        {title}
      </h3>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}

function InlineToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-1.5 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-3 h-3 accent-[var(--accent)] cursor-pointer"
      />
      <span className="text-[10px] font-medium text-text-secondary">{label}</span>
    </label>
  );
}

function InlineSelect({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-[24px] px-1.5 rounded-sm border border-border bg-surface text-[10px] text-text-primary outline-none cursor-pointer"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

/* ── Component ──────────────────────────────────────────────────── */

export function PerformanceTab({ queries, clusters }: PerformanceTabProps) {
  const [showByPlatform, setShowByPlatform] = useState(false);
  const [clusterFilter, setClusterFilter] = useState('all');
  const [visibleBots, setVisibleBots] = useState<Record<string, boolean>>({
    GPTBot: true, ClaudeBot: true, PerplexityBot: true, GoogleBot: true, GeminiBot: true,
  });

  const citationData = useMemo(() => buildCitationMomentum(showByPlatform), [showByPlatform]);
  const sovData = useMemo(() => buildSOVTrend(), []);
  const platformBreakdown = useMemo(() => buildPlatformBreakdown(queries), [queries]);
  const accuracyData = useMemo(() => buildCitationAccuracy(), []);
  const crawlData = useMemo(() => buildCrawlActivity(), []);
  const brandLiftData = useMemo(() => buildBrandSearchLift(), []);
  const publishedContent = useMemo(() => {
    const filtered = clusterFilter === 'all' ? queries : queries.filter((q) => q.cluster === clusterFilter);
    return buildPublishedContent(filtered);
  }, [queries, clusterFilter]);

  const clusterOptions = useMemo(() => [
    { value: 'all', label: 'All Clusters' },
    ...clusters.map((c) => ({ value: c.name, label: c.name })),
  ], [clusters]);

  const tooltipStyle = {
    backgroundColor: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    fontSize: '11px',
  };

  return (
    <div className="space-y-4">
      {/* Row 1: Citation Momentum + SOV Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 1 — Citation Momentum */}
        <Card hoverable={false}>
          <ChartHeader title="Citation Momentum">
            <InlineToggle label="By Platform" checked={showByPlatform} onChange={setShowByPlatform} />
          </ChartHeader>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={citationData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '10px' }} />
              {showByPlatform ? (
                PLATFORM_IDS.map((p) => (
                  <Line key={p} type="monotone" dataKey={p} stroke={PLATFORM_COLORS[p]} strokeWidth={2} dot={{ r: 2 }} />
                ))
              ) : (
                <>
                  <Line type="monotone" dataKey="total" stroke="var(--accent)" strokeWidth={2.5} dot={{ r: 3 }} name="Total" />
                  <Line type="monotone" dataKey="new" stroke="var(--accent)" strokeWidth={1.5} strokeDasharray="5 3" dot={{ r: 2 }} name="New" />
                </>
              )}
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Chart 2 — SOV Trend */}
        <Card hoverable={false}>
          <ChartHeader title="Share of Voice Trend" />
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={sovData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v}%`]} />
              <Legend wrapperStyle={{ fontSize: '10px' }} />
              <Line type="monotone" dataKey="lovable.dev" stroke="var(--accent)" strokeWidth={2.5} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="bolt.new" stroke="#E5484D" strokeWidth={1.5} dot={{ r: 2 }} />
              <Line type="monotone" dataKey="replit.com" stroke="#34B27B" strokeWidth={1.5} dot={{ r: 2 }} />
              <Line type="monotone" dataKey="v0.dev" stroke="#886FBF" strokeWidth={1.5} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Row 2: Platform Breakdown + Citation Accuracy */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 3 — Platform Citation Breakdown */}
        <Card hoverable={false}>
          <ChartHeader title="Platform Citation Breakdown" />
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={platformBreakdown} layout="vertical" margin={{ left: 100 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="platform" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} axisLine={false} tickLine={false} width={95} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v, name) => [name === 'rate' ? `${v}%` : v]} />
              <Bar dataKey="cited" radius={[0, 3, 3, 0]} barSize={18} name="Cited">
                {platformBreakdown.map((entry, idx) => (
                  <Cell key={idx} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-2 mt-2">
            {platformBreakdown.map((p) => (
              <span key={p.platform} className="text-[10px] font-mono text-text-secondary">
                {p.platform}: <span className="text-text-primary font-semibold">{p.rate}%</span>
              </span>
            ))}
          </div>
        </Card>

        {/* Chart 4 — Citation Accuracy */}
        <Card hoverable={false}>
          <ChartHeader title="Citation Accuracy by Platform" />
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={accuracyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="platform" tick={{ fontSize: 9, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '10px' }} />
              <Bar dataKey="accurate" fill="var(--success)" radius={[3, 3, 0, 0]} barSize={14} name="Accurate" />
              <Bar dataKey="errors" fill="var(--error)" radius={[3, 3, 0, 0]} barSize={14} name="Errors" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Row 3: Crawl Activity + Brand Search Lift */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 5 — AI Bot Crawl Activity */}
        <Card hoverable={false}>
          <ChartHeader title="AI Bot Crawl Activity">
            <div className="flex gap-1.5">
              {Object.keys(visibleBots).map((bot) => (
                <InlineToggle
                  key={bot}
                  label={bot.replace('Bot', '')}
                  checked={visibleBots[bot]}
                  onChange={(v) => setVisibleBots((prev) => ({ ...prev, [bot]: v }))}
                />
              ))}
            </div>
          </ChartHeader>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={crawlData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              {Object.entries(visibleBots).map(([bot, visible]) =>
                visible ? (
                  <Line key={bot} type="monotone" dataKey={bot} stroke={BOT_COLORS[bot]} strokeWidth={1.5} dot={{ r: 2 }} />
                ) : null
              )}
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Chart 6 — Brand Search Lift */}
        <Card hoverable={false}>
          <ChartHeader title="Brand Search Lift" />
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={brandLiftData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
              <YAxis yAxisId="left" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '10px' }} />
              <Bar yAxisId="left" dataKey="brandedSearch" fill="var(--accent)" fillOpacity={0.3} radius={[3, 3, 0, 0]} barSize={20} name="Branded Search" />
              <Line yAxisId="right" type="monotone" dataKey="aiCitations" stroke="var(--warning)" strokeWidth={2} dot={{ r: 3 }} name="AI Citations" />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Row 4: Content Published vs Citations — Full Width */}
      <Card hoverable={false}>
        <ChartHeader title="Content Published vs Citations Gained">
          <InlineSelect
            value={clusterFilter}
            onChange={setClusterFilter}
            options={clusterOptions}
          />
        </ChartHeader>
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={WEEKS.map((w, i) => ({ week: w, published: [0, 1, 0, 2, 1, 1, 1, 1][i], citations: [12, 18, 15, 28, 35, 42, 48, 56][i] }))}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
            <XAxis dataKey="week" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
            <YAxis yAxisId="left" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: '10px' }} />
            <Bar yAxisId="left" dataKey="published" fill="var(--accent)" radius={[3, 3, 0, 0]} barSize={24} name="Published" />
            <Line yAxisId="right" type="monotone" dataKey="citations" stroke="var(--warning)" strokeWidth={2} dot={{ r: 3 }} name="Citations" />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      {/* Row 5: Published Content Performance Table */}
      <Card hoverable={false}>
        <ChartHeader title="Published Content Performance">
          <InlineSelect
            value={clusterFilter}
            onChange={setClusterFilter}
            options={clusterOptions}
          />
        </ChartHeader>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                {['Title', 'Cluster', 'Citations', 'CPS Score', 'AI Referrals', 'Velocity', 'Trend', 'Status', 'Date'].map((h) => (
                  <th key={h} className="text-left p-[6px_10px] text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {publishedContent.map((item) => (
                <tr key={item.id} className="border-b border-border-subtle hover:bg-accent-subtle transition-colors cursor-pointer">
                  <td className="p-[6px_10px] text-[12px] text-text-primary truncate max-w-[240px]">{item.title}</td>
                  <td className="p-[6px_10px]"><Badge variant="info">{item.cluster}</Badge></td>
                  <td className="p-[6px_10px] text-[12px] font-mono text-text-primary text-center">{item.citations}</td>
                  <td className="p-[6px_10px] text-[12px] font-mono text-text-primary text-center">{item.cpsScore}</td>
                  <td className="p-[6px_10px] text-[12px] font-mono text-text-primary text-center">{item.referralSessions}</td>
                  <td className="p-[6px_10px] text-[12px] font-mono text-text-primary text-center">{item.velocity}/wk</td>
                  <td className="p-[6px_10px]">
                    <Sparkline data={item.trend} width={60} height={20} />
                  </td>
                  <td className="p-[6px_10px]">
                    <Badge variant={item.status === 'published' ? 'success' : 'neutral'}>{item.status}</Badge>
                  </td>
                  <td className="p-[6px_10px] text-[12px] text-text-secondary">{item.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
