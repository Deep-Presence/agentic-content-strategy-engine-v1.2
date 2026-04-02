// ─── Citation Intelligence — Mock Data & Constants ──────────────────────────

export const PLATFORM_COLORS: Record<string, string> = {
  ChatGPT: '#10A37F',
  Claude: '#D4A574',
  Perplexity: '#20B8CD',
  'Google AI': '#4285F4',
  Gemini: '#886FBF',
};

export const PLATFORM_DOMAINS: Record<string, string> = {
  ChatGPT: 'openai.com',
  Claude: 'anthropic.com',
  Perplexity: 'perplexity.ai',
  'Google AI': 'google.com',
  Gemini: 'gemini.google.com',
};

// ─── KPI Strip ──────────────────────────────────────────────────────────────

export const KPI_DATA: { label: string; value: string; trend: string; trendType: 'positive' | 'negative' | 'neutral'; sub: string }[] = [
  { label: 'Share of Voice', value: '12.4%', trend: '↑ from 8.1%', trendType: 'positive', sub: 'across all platforms' },
  { label: 'Citation Presence', value: '67%', trend: '↑ from 52%', trendType: 'positive', sub: 'queries where you appear' },
  { label: 'Avg Citation Position', value: '2.3', trend: '↑ from 3.1', trendType: 'positive', sub: 'when cited, your rank' },
  { label: 'Total Citations', value: '847', trend: '+124 this period', trendType: 'positive', sub: 'across 5 platforms' },
  { label: 'Brand Mentions', value: '1,203', trend: '+89 this period', trendType: 'positive', sub: 'mentioned without citation' },
  { label: 'Est. AI Referrals', value: '~3,200/mo', trend: '—', trendType: 'neutral', sub: 'proxy from citation volume' },
];

// ─── Citation Momentum (Hero chart) ─────────────────────────────────────────

export const generateMomentumData = () => {
  return Array.from({ length: 28 }, (_, i) => ({
    date: `Mar ${i + 1}`,
    ChatGPT: Math.floor(8 + Math.random() * 4 + i * 0.3),
    Claude: Math.floor(5 + Math.random() * 3 + i * 0.2),
    Perplexity: Math.floor(4 + Math.random() * 3 + i * 0.25),
    'Google AI': Math.floor(3 + Math.random() * 2 + i * 0.15),
    Gemini: Math.floor(2 + Math.random() * 2 + i * 0.1),
    sov: parseFloat((8.1 + i * 0.16 + (Math.random() * 0.5 - 0.25)).toFixed(1)),
  }));
};

// ─── Visibility Breakdown ───────────────────────────────────────────────────

export const VISIBILITY = {
  cited: 0.67,
  mentioned: 0.89,
  totalQueries: 47,
};

export const SENTIMENT = {
  positive: 0.72,
  neutral: 0.22,
  negative: 0.06,
};

export const CONTEXT_CATEGORIES = [
  { category: 'Recommendation', percentage: 42 },
  { category: 'Comparison', percentage: 28 },
  { category: 'Feature mention', percentage: 18 },
  { category: 'Criticism', percentage: 6 },
  { category: 'Neutral reference', percentage: 6 },
];

// ─── Competitor Leaderboard ─────────────────────────────────────────────────

export const LEADERBOARD = [
  { rank: 1, domain: 'bolt.new', name: 'Bolt.new', sov: 18.2, citations: 1420, delta: -0.8 },
  { rank: 2, domain: 'lovable.dev', name: 'Lovable', sov: 12.4, citations: 847, delta: 4.3, isYou: true },
  { rank: 3, domain: 'cursor.com', name: 'Cursor', sov: 11.8, citations: 921, delta: 1.2 },
  { rank: 4, domain: 'replit.com', name: 'Replit', sov: 9.1, citations: 710, delta: -2.1 },
  { rank: 5, domain: 'v0.dev', name: 'V0.dev', sov: 7.3, citations: 571, delta: 0.9 },
  { rank: 6, domain: 'emergent.sh', name: 'Emergent', sov: 5.2, citations: 406, delta: 3.1 },
];

// Generate 28-day competitive trend data
export const generateCompetitiveTrend = () => {
  const brands = LEADERBOARD;
  return Array.from({ length: 28 }, (_, i) => {
    const point: Record<string, number> = { day: i + 1 };
    brands.forEach((b) => {
      point[b.name] = parseFloat((b.sov + (Math.random() * 2 - 1) + (b.delta > 0 ? i * 0.05 : -i * 0.03)).toFixed(1));
    });
    return point;
  });
};

// ─── Platform Intelligence Grid ─────────────────────────────────────────────

export const PLATFORM_GRID = [
  { platform: 'ChatGPT', domain: 'openai.com', citations: 312, sov: 14.2, avgRank: 2.1, coverage: 78, sentiment: 'Positive' as const },
  { platform: 'Claude', domain: 'anthropic.com', citations: 189, sov: 11.8, avgRank: 2.8, coverage: 62, sentiment: 'Positive' as const },
  { platform: 'Perplexity', domain: 'perplexity.ai', citations: 156, sov: 13.1, avgRank: 1.9, coverage: 71, sentiment: 'Positive' as const },
  { platform: 'Google AI', domain: 'google.com', citations: 118, sov: 9.4, avgRank: 3.2, coverage: 55, sentiment: 'Neutral' as const },
  { platform: 'Gemini', domain: 'gemini.google.com', citations: 72, sov: 8.7, avgRank: 3.5, coverage: 48, sentiment: 'Positive' as const },
];

export const generatePlatformSparkline = (baseCount: number) => {
  return Array.from({ length: 28 }, (_, i) => ({
    day: i + 1,
    value: Math.max(0, Math.floor((baseCount / 28) * (0.6 + Math.random() * 0.8) + i * 0.3)),
  }));
};

// ─── Citation URL Table ─────────────────────────────────────────────────────

export interface CitationURL {
  url: string;
  title: string;
  citations: number;
  platforms: { chatgpt: boolean; claude: boolean; perplexity: boolean; google_ai: boolean; gemini: boolean };
  queries: number;
  cps: number;
  firstCited: string;
  velocity: number;
  velocityTrend: 'up' | 'down' | 'flat';
}

export const CITATION_URLS: CitationURL[] = [
  { url: 'lovable.dev/blog/ai-app-builder-comparison', title: 'AI App Builder Comparison Guide', citations: 63, platforms: { chatgpt: true, claude: true, perplexity: true, google_ai: true, gemini: false }, queries: 12, cps: 0.713, firstCited: '2026-01-15', velocity: 4.8, velocityTrend: 'up' },
  { url: 'lovable.dev/blog/lovable-vs-cursor', title: 'Lovable vs Cursor: Honest Review', citations: 38, platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: true, gemini: false }, queries: 8, cps: 0.654, firstCited: '2026-01-22', velocity: 3.9, velocityTrend: 'up' },
  { url: 'lovable.dev/blog/vibe-coding-enterprise', title: 'Vibe Coding for Enterprise Teams', citations: 31, platforms: { chatgpt: false, claude: true, perplexity: true, google_ai: true, gemini: false }, queries: 6, cps: 0.649, firstCited: '2026-02-01', velocity: 3.2, velocityTrend: 'up' },
  { url: 'lovable.dev/blog/bolt-new-alternatives', title: 'Bolt.new Alternatives in 2026', citations: 29, platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: false, gemini: false }, queries: 9, cps: 0.521, firstCited: '2026-02-14', velocity: 1.4, velocityTrend: 'down' },
  { url: 'lovable.dev/blog/security-ai-apps', title: 'Security in AI-Generated Apps', citations: 24, platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: false }, queries: 5, cps: 0.482, firstCited: '2026-02-08', velocity: 2.1, velocityTrend: 'flat' },
  { url: 'lovable.dev/blog/non-tech-founder-guide', title: "Non-Technical Founder's Guide", citations: 22, platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: true }, queries: 7, cps: 0.538, firstCited: '2026-02-20', velocity: 2.9, velocityTrend: 'up' },
  { url: 'lovable.dev/docs/getting-started', title: 'Getting Started Guide', citations: 19, platforms: { chatgpt: true, claude: false, perplexity: false, google_ai: true, gemini: true }, queries: 4, cps: 0.521, firstCited: '2026-01-10', velocity: 1.5, velocityTrend: 'flat' },
  { url: 'lovable.dev/blog/rbac-ai-apps', title: 'RBAC in AI-Generated Applications', citations: 18, platforms: { chatgpt: false, claude: false, perplexity: true, google_ai: false, gemini: false }, queries: 3, cps: 0.459, firstCited: '2026-02-25', velocity: 0.8, velocityTrend: 'down' },
  { url: 'lovable.dev/docs/api-reference', title: 'API Reference Documentation', citations: 14, platforms: { chatgpt: true, claude: true, perplexity: true, google_ai: false, gemini: false }, queries: 2, cps: 0.612, firstCited: '2026-01-18', velocity: 1.2, velocityTrend: 'flat' },
  { url: 'lovable.dev/blog/soc2-compliance', title: 'SOC 2 for AI Dev Platforms', citations: 8, platforms: { chatgpt: false, claude: false, perplexity: false, google_ai: true, gemini: false }, queries: 2, cps: 0.385, firstCited: '2026-03-05', velocity: 0.5, velocityTrend: 'down' },
];

// ─── Drawer Data ────────────────────────────────────────────────────────────

export const QUERIES_SERVED = [
  { query: 'best AI app builder comparison', platform: 'ChatGPT', position: 1 },
  { query: 'lovable vs bolt.new vs cursor', platform: 'Perplexity', position: 1 },
  { query: 'AI app builder features 2026', platform: 'Google AI', position: 2 },
  { query: 'no-code app builder review', platform: 'ChatGPT', position: 3 },
  { query: 'best tools to build apps with AI', platform: 'Claude', position: 2 },
];

export const CITATION_EXAMPLES = [
  {
    platform: 'ChatGPT',
    text: "For a comprehensive comparison of AI app builders, **Lovable's comparison guide** covers the key differences between Bolt.new, Cursor, and Replit across pricing, features, and deployment capabilities.",
  },
  {
    platform: 'Perplexity',
    text: "According to **Lovable's analysis**, the main differentiators between AI app builders are: deployment flexibility, database integration, and code export options. [Source: lovable.dev]",
  },
];

export const COMPETING_URLS = [
  { url: 'bolt.new/blog/ai-app-security', domain: 'bolt.new', sharedQueries: 3, citations: 81 },
  { url: 'lovable.dev/blog/lovable-vs-cursor', domain: 'lovable.dev', sharedQueries: 4, citations: 38, isOwn: true },
  { url: 'cursor.com/docs/enterprise-features', domain: 'cursor.com', sharedQueries: 2, citations: 74 },
];

// ─── Chart Event Milestones ─────────────────────────────────────────────────

export interface ChartEvent {
  date: string;
  sov: number;
  type: 'published' | 'gained' | 'lost';
  label: string;
  color: string;
}

export const CHART_EVENTS: ChartEvent[] = [
  { date: 'Mar 5', sov: 9.2, type: 'published', label: 'Published: Vibe Coding Guide', color: '#34B27B' },
  { date: 'Mar 12', sov: 10.8, type: 'gained', label: '+3 new ChatGPT citations', color: '#6CB8D2' },
  { date: 'Mar 18', sov: 11.4, type: 'lost', label: "Lost 'vibe coding meaning' to cursor.com", color: '#E5484D' },
  { date: 'Mar 23', sov: 12.1, type: 'gained', label: 'Perplexity started citing Enterprise guide', color: '#6CB8D2' },
];

// ─── Day Breakdown (click bar) ──────────────────────────────────────────────

export interface DayBreakdown {
  platform: string;
  domain: string;
  count: number;
  delta: number;
  topEvent: string;
}

export const generateDayBreakdown = (date: string, data: Record<string, number>): DayBreakdown[] => {
  const platformEvents: Record<string, string> = {
    ChatGPT: `Top: "AI App Builder Comparison" cited for 3 new queries`,
    Claude: `Top: "Vibe Coding Enterprise" first citation on Claude`,
    Perplexity: 'No change',
    'Google AI': 'Top: "Getting Started Guide" moved from position 3→2',
    Gemini: `Top: "Non-Technical Founder's Guide" first Gemini citation`,
  };
  return ['ChatGPT', 'Claude', 'Perplexity', 'Google AI', 'Gemini'].map((p) => ({
    platform: p,
    domain: PLATFORM_DOMAINS[p],
    count: data[p] || 0,
    delta: Math.floor(Math.random() * 5) - 1,
    topEvent: platformEvents[p],
  }));
};

// ─── Platform Insights ──────────────────────────────────────────────────────

export const PLATFORM_INSIGHTS: Record<string, { strength: string; weakness: string }> = {
  ChatGPT: {
    strength: 'Best rank (2.1) — they cite you highest',
    weakness: 'Low coverage in security queries',
  },
  Claude: {
    strength: 'Fastest growing — +18% citations this month',
    weakness: 'Not citing your comparison guides',
  },
  Perplexity: {
    strength: "Highest rank (1.9) — you're their #1 pick",
    weakness: 'Only 71% coverage, missing enterprise queries',
  },
  'Google AI': {
    strength: 'Strong schema recognition — your structured content wins',
    weakness: 'Lowest SOV (9.4%) — underrepresented here',
  },
  Gemini: {
    strength: 'Growing — first citations this month on 3 pages',
    weakness: 'Lowest coverage (48%) and citations (72)',
  },
};

// ─── Per-platform citation counts for table row expansion ───────────────────

export const PER_PLATFORM_CITATIONS: Record<string, Record<string, { citations: number; queries: number }>> = {};
CITATION_URLS.forEach((url) => {
  const activePlatforms = Object.entries(url.platforms).filter(([, v]) => v).length;
  const base = activePlatforms > 0 ? Math.floor(url.citations / activePlatforms) : 0;
  const breakdown: Record<string, { citations: number; queries: number }> = {};
  (['chatgpt', 'claude', 'perplexity', 'google_ai', 'gemini'] as const).forEach((pk) => {
    if (url.platforms[pk]) {
      const c = base + Math.floor(Math.random() * 4) - 1;
      breakdown[pk] = { citations: Math.max(1, c), queries: Math.max(1, Math.floor(url.queries / activePlatforms)) };
    } else {
      breakdown[pk] = { citations: 0, queries: 0 };
    }
  });
  PER_PLATFORM_CITATIONS[url.url] = breakdown;
});

// ─── Revenue Proxy ──────────────────────────────────────────────────────────

export const REVENUE_PROXY = [
  { label: 'Est. AI Referrals', value: '~3,200/mo', sub: 'based on citation volume × industry benchmarks', trend: '+12% vs last month', trendType: 'positive' as const },
  { label: 'Citation-to-Visit Rate', value: '8.4%', sub: 'estimated CTR from AI citations', trend: 'industry avg: 6.2%', trendType: 'positive' as const },
  { label: 'High-Intent Queries', value: '14 of 47', sub: 'queries with buying intent signals', trend: "you're cited in 9 of 14", trendType: 'positive' as const },
];

// Weekly referral data for mini bar chart
export const WEEKLY_REFERRALS = [680, 720, 760, 810, 790, 850, 890];

// Competitor leaderboard 7-day micro trends
export const MICRO_TRENDS: Record<string, number[]> = {
  'bolt.new': [18.4, 18.3, 18.2, 18.1, 18.0, 18.2, 18.2],
  'lovable.dev': [11.2, 11.5, 11.8, 12.0, 12.1, 12.3, 12.4],
  'cursor.com': [11.5, 11.6, 11.7, 11.7, 11.8, 11.8, 11.8],
  'replit.com': [9.8, 9.6, 9.5, 9.3, 9.2, 9.1, 9.1],
  'v0.dev': [7.0, 7.1, 7.1, 7.2, 7.2, 7.3, 7.3],
  'emergent.sh': [4.8, 4.9, 5.0, 5.0, 5.1, 5.1, 5.2],
};
