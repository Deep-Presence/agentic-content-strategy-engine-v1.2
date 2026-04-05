// ─── Competitive Position v4 — Full Data + Computed Insights ─────────────────

// ─── Core Types ─────────────────────────────────────────────────────────────

export interface Competitor {
  domain: string;
  name: string;
  sov: number;
  citations: number;
  delta: number;
  winRate: number;
  trend: 'growing' | 'declining' | 'stable';
  sparkline: number[];
  delta7d: number;
  delta14d: number;
  delta28d: number;
}

export interface LandscapeBrand {
  domain: string;
  name: string;
  sov: number;
  citations: number;
  delta?: number;
  label?: string;
  category: 'you' | 'direct' | 'mindshare' | 'authority';
}

export interface ClusterRanking {
  cluster: string;
  yourRank: number | null;
  yourShare: number;
  leaderDomain: string;
  leaderShare: number;
  gap: number | null;
  coverage: string;
  coveragePct: number;
  totalQueries: number;
  status: 'winning' | 'competitive' | 'losing';
  opportunityScore: number;
}

export interface CitationItem {
  query: string;
  status: 'lost' | 'at_risk' | 'stable' | 'never_had';
  competitor?: string;
  engine?: string;
  engines?: number;
  daysAgo?: number;
  detail?: string;
  reason?: string;
  recaptureProbability?: 'high' | 'medium' | 'low';
  quickFix?: string;
}

export interface PlatformSOV {
  platform: string;
  domain: string;
  sov: number;
  rank: number;
  delta: number;
  leaderSov: number;
  leaderDomain: string;
}

export interface DivergenceRow {
  query: string;
  citations: Record<string, string>;
  yourCoverage: number; // out of 5
}

export interface SOVDataPoint {
  date: string;
  you: number;
  'bolt.new': number;
  'cursor.com': number;
  'replit.com': number;
  'v0.dev': number;
  'emergent.sh': number;
  [key: string]: string | number;
}

export interface RadarDimension {
  dimension: string;
  you: number;
  competitor: number;
  fullMark: 100;
}

export interface ThreatPoint {
  domain: string;
  name: string;
  winRate: number;
  delta: number;
  citations: number;
  quadrant: string;
}

export interface PriorityAction {
  action: string;
  impact: number;
  competitor: string;
  competitorDomain: string;
}

export interface CompetitorDetail {
  domain: string;
  winRate: number;
  totalShared: number;
  queriesYouWin: { query: string; platforms: string[] }[];
  queriesYouLose: { query: string; platforms: string[]; count: number }[];
  whyTheyWin: string[];
  howToClose: { action: string; impact: string }[];
}

export interface ClusterDetail {
  cluster: string;
  totalCitations: number;
  totalDomains: number;
  queries: { query: string; topCited: { domain: string; platforms: string[] }[]; yourContent: string | null; gap: number }[];
  strategy: string;
}

// ─── Constants ──────────────────────────────────────────────────────────────

export const PLATFORMS = ['ChatGPT', 'Claude', 'Perplexity', 'Gemini', 'Google AI'] as const;

export const ENGINE_DOMAINS: Record<string, string> = {
  ChatGPT: 'openai.com', Claude: 'anthropic.com', Perplexity: 'perplexity.ai',
  'Google AI': 'google.com', Gemini: 'gemini.google.com',
};

// ─── Your Data ──────────────────────────────────────────────────────────────

export const YOUR_DATA = {
  domain: 'lovable.dev', name: 'Lovable',
  sov: 12.4, sovStart: 8.1, sovDelta: 4.3,
  rank: 2, previousRank: 4, totalTracked: 14,
  citations: 847, winRate: 39,
  gapsClosed: 4, gapsOpened: 2, gapsNet: 2,
  atRisk: 4, lost: 3,
  sparkline: [8.1, 8.5, 9.0, 9.4, 10.1, 10.8, 11.4, 11.9, 12.4],
  strongestPlatform: 'Perplexity',
  weakestPlatform: 'Claude',
  biggestOpportunity: 'Category Comparison',
};

// ─── SOV Trend (28 days) ────────────────────────────────────────────────────

function genTrend(): SOVDataPoint[] {
  const pts: SOVDataPoint[] = [];
  const t = { you: [8.1, 12.4], 'bolt.new': [18.5, 17.1], 'cursor.com': [11.5, 11.8], 'replit.com': [9.5, 8.8], 'v0.dev': [7.1, 7.4], 'emergent.sh': [5.0, 5.3] };
  let seed = 42;
  const rnd = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646 - 0.5; };
  for (let i = 0; i < 28; i++) {
    const p = i / 27;
    const r: SOVDataPoint = { date: `Mar ${i + 1}`, you: 0, 'bolt.new': 0, 'cursor.com': 0, 'replit.com': 0, 'v0.dev': 0, 'emergent.sh': 0 };
    for (const [k, [s, e]] of Object.entries(t)) r[k] = +(s + (e - s) * p + rnd() * 0.4).toFixed(1);
    pts.push(r);
  }
  return pts;
}
export const SOV_TREND = genTrend();

// Compute rank at each time point for rank history view
export const RANK_HISTORY = SOV_TREND.map((pt) => {
  const vals = [
    { key: 'you', val: pt.you }, { key: 'bolt.new', val: pt['bolt.new'] },
    { key: 'cursor.com', val: pt['cursor.com'] }, { key: 'replit.com', val: pt['replit.com'] },
    { key: 'v0.dev', val: pt['v0.dev'] }, { key: 'emergent.sh', val: pt['emergent.sh'] },
  ].sort((a, b) => b.val - a.val);
  const ranks: Record<string, number> = {};
  vals.forEach((v, i) => ranks[v.key] = i + 1);
  return { date: pt.date, ...ranks };
});

export const MILESTONES = [
  { date: 'Mar 5', type: 'positive' as const, label: 'Published: Vibe Coding Guide', color: '#34B27B' },
  { date: 'Mar 12', type: 'positive' as const, label: '+3 new ChatGPT citations', color: '#34B27B' },
  { date: 'Mar 18', type: 'negative' as const, label: "Lost 'vibe coding meaning'", color: '#E5484D' },
  { date: 'Mar 23', type: 'neutral' as const, label: 'Perplexity citing Enterprise guide', color: '#6CB8D2' },
];

// ─── Competitors (with computed momentum) ───────────────────────────────────

function computeSparkline(key: string): number[] {
  const indices = [0, 3, 7, 11, 15, 19, 23, 27];
  return indices.map((i) => (SOV_TREND[i]?.[key] as number) || 0);
}

function computeDeltas(key: string): [number, number, number] {
  const d = SOV_TREND;
  return [
    +(((d[27]?.[key] as number) || 0) - ((d[20]?.[key] as number) || 0)).toFixed(1), // 7d
    +(((d[27]?.[key] as number) || 0) - ((d[13]?.[key] as number) || 0)).toFixed(1), // 14d
    +(((d[27]?.[key] as number) || 0) - ((d[0]?.[key] as number) || 0)).toFixed(1),  // 28d
  ];
}

export const COMPETITORS: Competitor[] = [
  { domain: 'bolt.new', name: 'Bolt.new', sov: 18.2, citations: 1420, delta: -0.8, winRate: 22, trend: 'declining', sparkline: computeSparkline('bolt.new'), ...(() => { const [d7, d14, d28] = computeDeltas('bolt.new'); return { delta7d: d7, delta14d: d14, delta28d: d28 }; })() },
  { domain: 'cursor.com', name: 'Cursor', sov: 11.8, citations: 921, delta: 1.2, winRate: 38, trend: 'growing', sparkline: computeSparkline('cursor.com'), ...(() => { const [d7, d14, d28] = computeDeltas('cursor.com'); return { delta7d: d7, delta14d: d14, delta28d: d28 }; })() },
  { domain: 'replit.com', name: 'Replit', sov: 9.1, citations: 710, delta: -2.1, winRate: 52, trend: 'declining', sparkline: computeSparkline('replit.com'), ...(() => { const [d7, d14, d28] = computeDeltas('replit.com'); return { delta7d: d7, delta14d: d14, delta28d: d28 }; })() },
  { domain: 'v0.dev', name: 'V0.dev', sov: 7.3, citations: 571, delta: 0.9, winRate: 68, trend: 'stable', sparkline: computeSparkline('v0.dev'), ...(() => { const [d7, d14, d28] = computeDeltas('v0.dev'); return { delta7d: d7, delta14d: d14, delta28d: d28 }; })() },
  { domain: 'emergent.sh', name: 'Emergent', sov: 5.2, citations: 406, delta: 3.1, winRate: 15, trend: 'growing', sparkline: computeSparkline('emergent.sh'), ...(() => { const [d7, d14, d28] = computeDeltas('emergent.sh'); return { delta7d: d7, delta14d: d14, delta28d: d28 }; })() },
  { domain: 'retool.com', name: 'Retool', sov: 4.8, citations: 375, delta: 0.4, winRate: 45, trend: 'stable', sparkline: [4.5, 4.5, 4.6, 4.6, 4.7, 4.7, 4.8, 4.8], delta7d: 0.1, delta14d: 0.2, delta28d: 0.4 },
];

// ─── Platform SOV ───────────────────────────────────────────────────────────

export const PLATFORM_SOV: PlatformSOV[] = [
  { platform: 'ChatGPT', domain: 'openai.com', sov: 14.2, rank: 2, delta: 2.1, leaderSov: 19.8, leaderDomain: 'bolt.new' },
  { platform: 'Claude', domain: 'anthropic.com', sov: 8.1, rank: 5, delta: 0.4, leaderSov: 15.2, leaderDomain: 'cursor.com' },
  { platform: 'Perplexity', domain: 'perplexity.ai', sov: 18.6, rank: 1, delta: 4.8, leaderSov: 18.6, leaderDomain: 'lovable.dev' },
  { platform: 'Gemini', domain: 'gemini.google.com', sov: 10.3, rank: 3, delta: -0.2, leaderSov: 16.4, leaderDomain: 'bolt.new' },
  { platform: 'Google AI', domain: 'google.com', sov: 11.2, rank: 3, delta: 1.1, leaderSov: 14.6, leaderDomain: 'bolt.new' },
];

// ─── Landscape Brands ───────────────────────────────────────────────────────

export const MINDSHARE: LandscapeBrand[] = [
  { domain: 'g2.com', name: 'G2', sov: 3.2, citations: 249, label: 'Review aggregator', category: 'mindshare' },
  { domain: 'producthunt.com', name: 'Product Hunt', sov: 2.1, citations: 164, label: 'Product directory', category: 'mindshare' },
  { domain: 'techcrunch.com', name: 'TechCrunch', sov: 1.8, citations: 140, label: 'Tech news', category: 'mindshare' },
  { domain: 'forbes.com', name: 'Forbes', sov: 1.4, citations: 109, label: 'Business media', category: 'mindshare' },
  { domain: 'capterra.com', name: 'Capterra', sov: 1.2, citations: 94, label: 'Software comparison', category: 'mindshare' },
];

export const AUTHORITY: LandscapeBrand[] = [
  { domain: 'cms.gov', name: 'CMS.gov', sov: 4.4, citations: 343, label: 'Government', category: 'authority' },
  { domain: 'owasp.org', name: 'OWASP', sov: 2.8, citations: 218, label: 'Security standards', category: 'authority' },
  { domain: 'arxiv.org', name: 'arXiv', sov: 2.1, citations: 164, label: 'Research papers', category: 'authority' },
  { domain: 'hhs.gov', name: 'HHS.gov', sov: 1.9, citations: 148, label: 'Government', category: 'authority' },
  { domain: 'nature.com', name: 'Nature', sov: 1.7, citations: 132, label: 'Research journal', category: 'authority' },
];

// All brands for treemap
export const ALL_BRANDS: LandscapeBrand[] = [
  { domain: YOUR_DATA.domain, name: YOUR_DATA.name, sov: YOUR_DATA.sov, citations: YOUR_DATA.citations, category: 'you' },
  ...COMPETITORS.map((c) => ({ domain: c.domain, name: c.name, sov: c.sov, citations: c.citations, category: 'direct' as const })),
  ...MINDSHARE,
  ...AUTHORITY,
];

// ─── Cluster Rankings (with computed opportunity scores) ────────────────────

function parseCoverage(cov: string): [number, number] {
  const [n, t] = cov.split('/').map(Number);
  return [n, t];
}

const RAW_CLUSTERS = [
  { cluster: 'Branded Evaluation', yourRank: 1 as number | null, yourShare: 4.5, leaderDomain: 'bolt.new', leaderShare: 3.8, gap: 0.7 as number | null, coverage: '13/17', status: 'winning' as const },
  { cluster: 'Boundary', yourRank: 1 as number | null, yourShare: 1.6, leaderDomain: 'censinet.com', leaderShare: 1.4, gap: 0.2 as number | null, coverage: '8/16', status: 'winning' as const },
  { cluster: 'Mechanism', yourRank: 3 as number | null, yourShare: 1.2, leaderDomain: 'emergent.sh', leaderShare: 2.8, gap: -1.6 as number | null, coverage: '12/16', status: 'competitive' as const },
  { cluster: 'Feature Verification', yourRank: 5 as number | null, yourShare: 0.6, leaderDomain: 'knack.com', leaderShare: 2.1, gap: -1.5 as number | null, coverage: '10/15', status: 'competitive' as const },
  { cluster: 'Category Comparison', yourRank: 4 as number | null, yourShare: 0.8, leaderDomain: 'cursor.com', leaderShare: 5.2, gap: -4.4 as number | null, coverage: '6/14', status: 'competitive' as const },
  { cluster: 'Definition', yourRank: 6 as number | null, yourShare: 0.5, leaderDomain: 'designrev.com', leaderShare: 2.4, gap: -1.9 as number | null, coverage: '3/12', status: 'losing' as const },
  { cluster: 'Decision Criteria', yourRank: 8 as number | null, yourShare: 0.2, leaderDomain: 'alloy.app', leaderShare: 2.8, gap: -2.6 as number | null, coverage: '4/15', status: 'losing' as const },
  { cluster: 'Problem/Awareness', yourRank: null, yourShare: 0, leaderDomain: 'cms.gov', leaderShare: 4.4, gap: null, coverage: '0/16', status: 'losing' as const },
  { cluster: 'Best-of/Consideration', yourRank: null, yourShare: 0, leaderDomain: 'rocket.new', leaderShare: 3.2, gap: null, coverage: '0/14', status: 'losing' as const },
];

export const CLUSTER_RANKINGS: ClusterRanking[] = RAW_CLUSTERS.map((c) => {
  const [covered, total] = parseCoverage(c.coverage);
  const coveragePct = total > 0 ? Math.round((covered / total) * 100) : 0;
  const absGap = c.gap !== null ? Math.abs(c.gap) : c.leaderShare;
  const opportunityScore = Math.round(absGap * (total / 17) * 10); // higher = bigger opportunity
  return { ...c, coveragePct, totalQueries: total, opportunityScore };
});

// ─── Platform Divergence ────────────────────────────────────────────────────

export const DIVERGENCE_DATA: DivergenceRow[] = [
  { query: 'best AI app builder 2026', citations: { ChatGPT: 'bolt.new', Claude: 'bolt.new', Perplexity: 'lovable.dev', Gemini: 'bolt.new', 'Google AI': 'bolt.new' } },
  { query: 'vibe coding meaning', citations: { ChatGPT: 'cursor.com', Claude: 'cursor.com', Perplexity: 'lovable.dev', Gemini: 'lovable.dev', 'Google AI': 'cursor.com' } },
  { query: 'AI code generation security', citations: { ChatGPT: 'snyk.io', Claude: 'snyk.io', Perplexity: 'owasp.org', Gemini: 'lovable.dev', 'Google AI': 'snyk.io' } },
  { query: 'lovable vs bolt.new', citations: { ChatGPT: 'lovable.dev', Claude: 'lovable.dev', Perplexity: 'lovable.dev', Gemini: 'bolt.new', 'Google AI': 'g2.com' } },
  { query: 'no-code AI app builder', citations: { ChatGPT: 'bolt.new', Claude: 'lovable.dev', Perplexity: 'lovable.dev', Gemini: 'bolt.new', 'Google AI': 'replit.com' } },
  { query: 'AI app builder pricing', citations: { ChatGPT: 'bolt.new', Claude: 'bolt.new', Perplexity: 'lovable.dev', Gemini: 'bolt.new', 'Google AI': 'capterra.com' } },
  { query: 'deploy AI app to production', citations: { ChatGPT: 'cursor.com', Claude: 'lovable.dev', Perplexity: 'lovable.dev', Gemini: 'replit.com', 'Google AI': 'cursor.com' } },
  { query: 'AI app builder for startups', citations: { ChatGPT: 'lovable.dev', Claude: 'lovable.dev', Perplexity: 'lovable.dev', Gemini: 'bolt.new', 'Google AI': 'producthunt.com' } },
  { query: 'AI app builder enterprise', citations: { ChatGPT: 'retool.com', Claude: 'retool.com', Perplexity: 'retool.com', Gemini: 'retool.com', 'Google AI': 'lovable.dev' } },
  { query: 'rapid prototyping AI tools', citations: { ChatGPT: 'bolt.new', Claude: 'v0.dev', Perplexity: 'lovable.dev', Gemini: 'cursor.com', 'Google AI': 'bolt.new' } },
].map((row) => ({
  ...row,
  yourCoverage: Object.values(row.citations).filter((d) => d === YOUR_DATA.domain).length,
}));

// ─── Citations Watchlist ────────────────────────────────────────────────────

export const CITATIONS: CitationItem[] = [
  { query: 'vibe coding meaning', status: 'lost', competitor: 'cursor.com', engine: 'ChatGPT', daysAgo: 3, reason: 'New guide published (2,800 words, FAQ, comparison tables)', recaptureProbability: 'high', quickFix: 'Add FAQ section + update data' },
  { query: 'AI code generation security risks', status: 'lost', competitor: 'snyk.io', engine: 'Claude', daysAgo: 5, reason: 'Stronger structural signals (FAQ, headers, schema)', recaptureProbability: 'medium', quickFix: 'Add schema markup + FAQ' },
  { query: 'enterprise AI app builder features', status: 'lost', competitor: 'retool.com', engine: 'Gemini', daysAgo: 7, reason: 'Expanded page from 1,800 to 3,200 words', recaptureProbability: 'medium', quickFix: 'Expand to 2,500+ words' },
  { query: 'no-code AI app security audit', status: 'at_risk', engine: 'Perplexity', daysAgo: 2, detail: 'Dropped from #1 to #3', recaptureProbability: 'high', quickFix: 'Update with fresh data' },
  { query: 'deploy AI-generated app to production', status: 'at_risk', competitor: 'cursor.com', engine: 'Google AI', daysAgo: 4, detail: 'Cited 3 of last 7 days', recaptureProbability: 'medium', quickFix: 'Add deployment guide section' },
  { query: 'prompt-to-app platform comparison', status: 'at_risk', engine: 'ChatGPT', daysAgo: 6, detail: 'Was #2, now #4', recaptureProbability: 'low' },
  { query: 'bolt.new vs lovable comparison', status: 'stable', detail: '3 platforms · 14+ days' },
  { query: 'best AI app builder for startups', status: 'stable', detail: '2 platforms · 21+ days' },
  { query: 'lovable AI app builder review', status: 'stable', detail: '4 platforms · 28+ days' },
  { query: 'AI app builder data privacy', status: 'never_had', competitor: 'owasp.org', engines: 4 },
  { query: 'RBAC in AI-generated applications', status: 'never_had', competitor: 'auth0.com', engines: 3 },
];

// ─── Radar Dimensions (computed for any competitor) ─────────────────────────

export function getRadarData(competitorDomain: string): RadarDimension[] {
  const c = COMPETITORS.find((x) => x.domain === competitorDomain);
  if (!c) return [];
  const clustersWithPresence = CLUSTER_RANKINGS.filter((cl) => cl.yourRank !== null).length;
  const totalClusters = CLUSTER_RANKINGS.length;
  const platformsTop3 = PLATFORM_SOV.filter((p) => p.rank <= 3).length;
  const stableCitations = CITATIONS.filter((ct) => ct.status === 'stable').length;
  const totalCitations = CITATIONS.length;

  return [
    { dimension: 'SOV Share', you: Math.min(YOUR_DATA.sov / 20 * 100, 100), competitor: Math.min(c.sov / 20 * 100, 100), fullMark: 100 },
    { dimension: 'Win Rate', you: YOUR_DATA.winRate, competitor: c.winRate, fullMark: 100 },
    { dimension: 'Platform Reach', you: (platformsTop3 / 5) * 100, competitor: Math.round(Math.random() * 40 + 30), fullMark: 100 },
    { dimension: 'Cluster Coverage', you: (clustersWithPresence / totalClusters) * 100, competitor: Math.round(Math.random() * 30 + 40), fullMark: 100 },
    { dimension: 'Momentum', you: Math.min(YOUR_DATA.sovDelta / 5 * 100, 100), competitor: Math.min(Math.max(c.delta / 5 * 100, 0), 100), fullMark: 100 },
    { dimension: 'Citation Stability', you: (stableCitations / totalCitations) * 100, competitor: Math.round(Math.random() * 30 + 30), fullMark: 100 },
  ];
}

// ─── Threat Matrix Points ───────────────────────────────────────────────────

export const THREAT_POINTS: ThreatPoint[] = [
  ...COMPETITORS.map((c) => ({
    domain: c.domain, name: c.name, winRate: c.winRate, delta: c.delta, citations: c.citations,
    quadrant: c.delta > 0 && c.winRate < 40 ? 'Growing Threat' : c.delta > 0 && c.winRate >= 40 ? 'Strong & Growing' : c.delta <= 0 && c.winRate < 40 ? 'Fading' : 'Strong & Stable',
  })),
  { domain: YOUR_DATA.domain, name: 'You', winRate: YOUR_DATA.winRate, delta: YOUR_DATA.sovDelta, citations: YOUR_DATA.citations, quadrant: 'You' },
];

// ─── Priority Actions (aggregated from all competitors) ─────────────────────

export const PRIORITY_ACTIONS: PriorityAction[] = [
  { action: 'Add FAQ sections to your top 5 pages', impact: 12, competitor: 'Bolt.new', competitorDomain: 'bolt.new' },
  { action: 'Add structured data (FAQ, HowTo schema) to top 10 pages', impact: 15, competitor: 'Cursor', competitorDomain: 'cursor.com' },
  { action: 'Create developer-focused comparison content', impact: 10, competitor: 'Cursor', competitorDomain: 'cursor.com' },
  { action: 'Create tutorial-style content for beginners', impact: 10, competitor: 'Replit', competitorDomain: 'replit.com' },
  { action: 'Enter Mechanism cluster with 3 technical deep-dives', impact: 20, competitor: 'Emergent', competitorDomain: 'emergent.sh' },
  { action: 'Create enterprise case studies with specific metrics', impact: 12, competitor: 'Retool', competitorDomain: 'retool.com' },
  { action: 'Create content for 3 uncovered queries', impact: 8, competitor: 'Bolt.new', competitorDomain: 'bolt.new' },
  { action: 'Highlight full-stack advantage vs UI-only tools', impact: 8, competitor: 'V0.dev', competitorDomain: 'v0.dev' },
].sort((a, b) => b.impact - a.impact);

// ─── Competitor Details (drawers) ───────────────────────────────────────────

export const COMPETITOR_DETAILS: Record<string, CompetitorDetail> = {
  'bolt.new': {
    domain: 'bolt.new', winRate: 22, totalShared: 14,
    queriesYouWin: [
      { query: 'lovable vs bolt.new comparison', platforms: ['ChatGPT', 'Claude'] },
      { query: 'lovable pricing vs bolt.new', platforms: ['Perplexity'] },
      { query: 'AI app builder for non-technical teams', platforms: ['Claude', 'Google AI'] },
    ],
    queriesYouLose: [
      { query: 'best AI app builder 2026', platforms: ['ChatGPT', 'Claude', 'Perplexity', 'Gemini'], count: 4 },
      { query: 'no-code app builder features', platforms: ['ChatGPT', 'Perplexity', 'Gemini'], count: 3 },
      { query: 'AI app builder pricing', platforms: ['ChatGPT', 'Claude', 'Gemini'], count: 3 },
    ],
    whyTheyWin: ['2.3x more content pages in Competitive Landscape cluster', 'Content averages 2,400 words vs your 1,800', '85% of pages have FAQ sections vs 20% of yours'],
    howToClose: [{ action: 'Add FAQ sections to your top 5 pages', impact: '+12% win rate' }, { action: 'Create content for 3 uncovered queries', impact: '+8% win rate' }, { action: 'Expand comparison pages to 2,500+ words', impact: '+5% win rate' }],
  },
  'cursor.com': {
    domain: 'cursor.com', winRate: 38, totalShared: 11,
    queriesYouWin: [{ query: 'lovable vs cursor for non-developers', platforms: ['ChatGPT', 'Perplexity'] }, { query: 'no-code AI app builder', platforms: ['Claude'] }, { query: 'AI app builder for startups', platforms: ['ChatGPT', 'Perplexity'] }],
    queriesYouLose: [{ query: 'best AI coding assistant 2026', platforms: ['ChatGPT', 'Claude', 'Gemini'], count: 3 }, { query: 'developer AI tools comparison', platforms: ['ChatGPT', 'Claude', 'Perplexity', 'Google AI'], count: 4 }, { query: 'vibe coding meaning', platforms: ['ChatGPT'], count: 1 }],
    whyTheyWin: ['Stronger developer credibility — content targets engineers directly', 'Pages load 1.2s vs your 2.8s — AI crawlers prefer faster sites', '92% of pages have structured data vs 35% of yours'],
    howToClose: [{ action: 'Add structured data (FAQ, HowTo schema) to top 10 pages', impact: '+15% win rate' }, { action: 'Create developer-focused comparison content', impact: '+10% win rate' }, { action: 'Improve page load speed to under 2 seconds', impact: '+5% win rate' }],
  },
  'replit.com': {
    domain: 'replit.com', winRate: 52, totalShared: 9,
    queriesYouWin: [{ query: 'lovable vs replit', platforms: ['ChatGPT', 'Claude'] }, { query: 'AI app builder for businesses', platforms: ['Perplexity', 'Google AI'] }, { query: 'AI app builder security features', platforms: ['ChatGPT', 'Claude'] }],
    queriesYouLose: [{ query: 'online IDE AI features', platforms: ['ChatGPT', 'Claude', 'Perplexity'], count: 3 }, { query: 'learn to code with AI', platforms: ['ChatGPT', 'Perplexity', 'Gemini', 'Google AI'], count: 4 }],
    whyTheyWin: ['Established brand in education and learning-to-code space', 'Community-generated content creates organic citation signals', '4x more indexed pages in educational content clusters'],
    howToClose: [{ action: 'Create tutorial-style content for beginners', impact: '+10% win rate' }, { action: 'Build comparison pages for education use cases', impact: '+8% win rate' }],
  },
  'v0.dev': {
    domain: 'v0.dev', winRate: 68, totalShared: 8,
    queriesYouWin: [{ query: 'AI app builder full stack', platforms: ['ChatGPT', 'Claude', 'Perplexity'] }, { query: 'lovable vs v0', platforms: ['ChatGPT', 'Claude'] }, { query: 'AI prototype to production', platforms: ['Perplexity', 'Google AI'] }],
    queriesYouLose: [{ query: 'AI UI component generator', platforms: ['ChatGPT', 'Claude'], count: 2 }, { query: 'vercel AI tools', platforms: ['ChatGPT', 'Perplexity', 'Gemini'], count: 3 }],
    whyTheyWin: ['Closely associated with Vercel — benefits from ecosystem citations', 'UI-specific content is more targeted than your broader positioning'],
    howToClose: [{ action: 'Create dedicated UI generation comparison content', impact: '+5% win rate' }, { action: 'Highlight full-stack advantage vs UI-only tools', impact: '+8% win rate' }],
  },
  'emergent.sh': {
    domain: 'emergent.sh', winRate: 15, totalShared: 7,
    queriesYouWin: [{ query: 'AI app builder comparison 2026', platforms: ['Perplexity'] }],
    queriesYouLose: [{ query: 'AI mechanism design tools', platforms: ['ChatGPT', 'Claude', 'Perplexity'], count: 3 }, { query: 'automated AI code review', platforms: ['Claude', 'Gemini'], count: 2 }, { query: 'AI for technical debt analysis', platforms: ['ChatGPT', 'Perplexity', 'Google AI'], count: 3 }],
    whyTheyWin: ['Deep technical content that resonates with AI engines', 'Weekly research papers get heavily cited', 'Covers mechanism design — a cluster you have zero presence in'],
    howToClose: [{ action: 'Enter Mechanism cluster with 3 technical deep-dives', impact: '+20% win rate' }, { action: 'Publish technical comparisons showing full-stack advantage', impact: '+10% win rate' }],
  },
  'retool.com': {
    domain: 'retool.com', winRate: 45, totalShared: 10,
    queriesYouWin: [{ query: 'AI app builder for startups', platforms: ['ChatGPT', 'Perplexity'] }, { query: 'lovable vs retool', platforms: ['ChatGPT', 'Claude'] }, { query: 'no-code AI prototyping', platforms: ['Claude', 'Google AI'] }],
    queriesYouLose: [{ query: 'enterprise internal tools AI', platforms: ['ChatGPT', 'Claude', 'Perplexity', 'Gemini'], count: 4 }, { query: 'no-code enterprise platform', platforms: ['ChatGPT', 'Perplexity', 'Google AI'], count: 3 }],
    whyTheyWin: ['Owns the "internal tools" narrative — deeply established positioning', 'Enterprise case studies are 3x more detailed than yours', 'Dedicated landing pages for every enterprise use case'],
    howToClose: [{ action: 'Create enterprise case studies with specific metrics', impact: '+12% win rate' }, { action: 'Build landing pages for top 5 enterprise use cases', impact: '+8% win rate' }],
  },
};

// ─── Cluster Details (drawers) ──────────────────────────────────────────────

export const CLUSTER_DETAILS: Record<string, ClusterDetail> = {
  'Problem/Awareness': {
    cluster: 'Problem/Awareness', totalCitations: 229, totalDomains: 159,
    queries: [
      { query: 'How to improve HCC risk adjustment accuracy?', topCited: [{ domain: 'healthcatalyst.com', platforms: ['ChatGPT', 'Claude'] }, { domain: 'cms.gov', platforms: ['Gemini', 'Perplexity'] }], yourContent: null, gap: 26.7 },
      { query: 'How to operationalize SDoH data?', topCited: [{ domain: 'innovaccer.com', platforms: ['ChatGPT', 'Perplexity'] }, { domain: 'nature.com', platforms: ['Claude'] }], yourContent: null, gap: 25.9 },
    ],
    strategy: "Dominated by government/institutional sources (50%). Create practitioner-focused implementation guides — 'How-to' format, 2000+ words, FAQ sections.",
  },
  'Best-of/Consideration': {
    cluster: 'Best-of/Consideration', totalCitations: 185, totalDomains: 120,
    queries: [
      { query: 'Best AI app builders in 2026', topCited: [{ domain: 'rocket.new', platforms: ['ChatGPT', 'Claude'] }, { domain: 'g2.com', platforms: ['Perplexity'] }], yourContent: null, gap: 28.3 },
      { query: 'Top no-code platforms for startups', topCited: [{ domain: 'capterra.com', platforms: ['ChatGPT', 'Perplexity'] }, { domain: 'producthunt.com', platforms: ['Claude'] }], yourContent: null, gap: 24.1 },
    ],
    strategy: "Dominated by review aggregators. Get listed on G2, Capterra, Product Hunt. Create comparison tables, feature matrices, pricing breakdowns.",
  },
};

// ─── Filter Options ─────────────────────────────────────────────────────────

export const clusterOptions = [{ value: 'all', label: 'All Clusters' }, ...CLUSTER_RANKINGS.map((c) => ({ value: c.cluster, label: c.cluster }))];
export const platformOptions = [{ value: 'all', label: 'All Platforms' }, { value: 'chatgpt', label: 'ChatGPT' }, { value: 'claude', label: 'Claude' }, { value: 'perplexity', label: 'Perplexity' }, { value: 'gemini', label: 'Gemini' }, { value: 'google_ai', label: 'Google AI' }];
