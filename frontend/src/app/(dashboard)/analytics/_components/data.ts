// ─── Citation Intelligence V2 — Mock Data & Types ───────────────────────────

// ─── Platform Config ─────────────────────────────────────────────────────────

export const PLATFORM_COLORS: Record<string, string> = {
  ChatGPT: '#10A37F',
  Claude: '#D4A574',
  Perplexity: '#4A90D9',
  'Google AI': '#34A853',
  Gemini: '#8E75B2',
};

export const PLATFORM_DOMAINS: Record<string, string> = {
  ChatGPT: 'openai.com',
  Claude: 'anthropic.com',
  Perplexity: 'perplexity.ai',
  'Google AI': 'google.com',
  Gemini: 'gemini.google.com',
};

export const PLATFORM_KEYS = ['ChatGPT', 'Claude', 'Perplexity', 'Google AI', 'Gemini'] as const;
export type PlatformKey = (typeof PLATFORM_KEYS)[number];

// ─── KPI Data ────────────────────────────────────────────────────────────────

export const KPIS = {
  totalCitations: 847,
  citationsDelta: 124,
  citationRate: 67,
  citationRatePrev: 52,
  mentionToCitationGap: 22,
  uncitedQueries: 11,
  avgPosition: 2.3,
  avgPositionPrev: 3.1,
};

// ─── Citation Momentum (28 days, per platform) ──────────────────────────────

export const generateMomentumData = () => {
  const seed = (i: number, base: number, growth: number) =>
    Math.floor(base + (Math.sin(i * 0.7 + base) * 0.5 + 0.5) * 3 + i * growth);

  return Array.from({ length: 28 }, (_, i) => ({
    date: `Mar ${i + 1}`,
    ChatGPT: seed(i, 8, 0.3),
    Claude: seed(i, 5, 0.2),
    Perplexity: seed(i, 4, 0.25),
    'Google AI': seed(i, 3, 0.15),
    Gemini: seed(i, 2, 0.1),
    sov: parseFloat((8.1 + i * 0.16 + (Math.sin(i * 0.5) * 0.3)).toFixed(1)),
  }));
};

// ─── Chart Events ────────────────────────────────────────────────────────────

export interface ChartEvent {
  date: string;
  label: string;
  type: 'publish' | 'citation' | 'loss';
  color: string;
}

export const CHART_EVENTS: ChartEvent[] = [
  { date: 'Mar 5', label: 'Published: Vibe Coding Guide', type: 'publish', color: '#34B27B' },
  { date: 'Mar 12', label: '+3 new ChatGPT citations', type: 'citation', color: '#10A37F' },
  { date: 'Mar 18', label: "Lost 'vibe coding meaning' to cursor.com", type: 'loss', color: '#E5484D' },
  { date: 'Mar 23', label: 'Perplexity started citing Enterprise guide', type: 'citation', color: '#4A90D9' },
];

// ─── Competitor Leaderboard ──────────────────────────────────────────────────

export interface LeaderboardEntry {
  domain: string;
  name: string;
  sov: number;
  citations: number;
  delta: number;
  isYou?: boolean;
}

export const LEADERBOARD: LeaderboardEntry[] = [
  { domain: 'bolt.new', name: 'Bolt.new', sov: 18.2, citations: 1420, delta: -0.8 },
  { domain: 'lovable.dev', name: 'Lovable', sov: 12.4, citations: 847, delta: 4.3, isYou: true },
  { domain: 'cursor.com', name: 'Cursor', sov: 11.8, citations: 921, delta: 1.2 },
  { domain: 'replit.com', name: 'Replit', sov: 9.1, citations: 710, delta: -2.1 },
  { domain: 'v0.dev', name: 'V0.dev', sov: 7.3, citations: 571, delta: 0.9 },
  { domain: 'emergent.sh', name: 'Emergent', sov: 5.2, citations: 406, delta: 3.1 },
  { domain: 'retool.com', name: 'Retool', sov: 4.8, citations: 375, delta: 0.4 },
  { domain: 'webflow.com', name: 'Webflow', sov: 4.2, citations: 328, delta: -0.3 },
];

// ─── Uncited Queries (Visibility Pipeline) ──────────────────────────────────

export interface UncitedQuery {
  query: string;
  engines: string[];
  note: string;
  action: 'improve' | 'create';
}

export const UNCITED_QUERIES: UncitedQuery[] = [
  { query: 'no-code AI app security audit', engines: ['chatgpt', 'claude'], note: "Link to your security page — content exists but isn't linked", action: 'improve' },
  { query: 'AI app builder deployment guide', engines: ['perplexity', 'gemini'], note: 'No deployment content exists — create new', action: 'create' },
  { query: 'prompt-to-app platform comparison', engines: ['chatgpt'], note: 'Your comparison page needs FAQ sections to earn citation', action: 'improve' },
  { query: 'enterprise AI builder compliance', engines: ['claude', 'google_ai'], note: 'Missing compliance content — enterprise blocker', action: 'create' },
  { query: 'AI generated app performance testing', engines: ['perplexity'], note: 'No testing content — niche opportunity', action: 'create' },
  { query: 'no-code backend integration patterns', engines: ['chatgpt', 'claude'], note: 'Your backend guide is too short (800 words vs 2,200 avg)', action: 'improve' },
  { query: 'AI app builder for agencies', engines: ['gemini'], note: 'No agency-specific content exists', action: 'create' },
  { query: 'code export from AI builders', engines: ['chatgpt', 'perplexity'], note: 'Your export docs need examples and comparison table', action: 'improve' },
  { query: 'AI app builder GDPR compliance', engines: ['claude', 'google_ai'], note: 'No GDPR content — regulatory gap', action: 'create' },
  { query: 'scaling AI generated applications', engines: ['perplexity', 'gemini'], note: 'No scaling content exists', action: 'create' },
  { query: 'AI app builder team collaboration', engines: ['chatgpt'], note: 'Mentioned in passing but no dedicated page', action: 'create' },
];

// ─── Visibility Pipeline Stats ──────────────────────────────────────────────

export const VISIBILITY = {
  totalQueries: 47,
  cited: 31,
  mentioned: 42,
  citedPct: 67,
  mentionedPct: 89,
  gapPct: 22,
  notAppearingPct: 11,
  notAppearing: 5,
};

// ─── Sentiment Data ─────────────────────────────────────────────────────────

export interface SentimentCategory {
  name: string;
  percentage: number;
  color: string;
  description: string;
  examplePhrase: string;
}

export const SENTIMENT_CATEGORIES: SentimentCategory[] = [
  { name: 'Recommendation', percentage: 42, color: 'var(--success)', description: 'AI engines actively suggest you', examplePhrase: '"We recommend Lovable for..."' },
  { name: 'Comparison', percentage: 28, color: 'var(--accent)', description: 'Used in competitive context', examplePhrase: '"Compared to alternatives, Lovable..."' },
  { name: 'Feature mention', percentage: 18, color: '#4A90D9', description: 'Factual capability description', examplePhrase: '"Lovable offers features like..."' },
  { name: 'Criticism', percentage: 6, color: 'var(--error)', description: 'Negative context, primarily pricing', examplePhrase: '"However, Lovable lacks..."' },
  { name: 'Neutral', percentage: 6, color: 'var(--text-tertiary)', description: 'Mentioned without opinion or context', examplePhrase: '' },
];

export const SENTIMENT_SUMMARY =
  "When AI engines mention you, the context is overwhelmingly positive (72%). You're most commonly recommended as a solution for non-technical teams. The 6% negative mentions primarily relate to pricing transparency and enterprise tier costs. Consider publishing a transparent pricing comparison to address this.";

export const generateSentimentTrend = () =>
  Array.from({ length: 28 }, (_, i) => ({
    date: `Mar ${i + 1}`,
    positive: 68 + Math.floor(Math.sin(i * 0.4) * 4 + i * 0.15),
    neutral: 20 + Math.floor(Math.sin(i * 0.6 + 1) * 3),
    negative: 8 - Math.floor(i * 0.07),
  }));

// ─── Platform Intelligence ──────────────────────────────────────────────────

export interface PlatformIntel {
  name: string;
  domain: string;
  citations: number;
  sov: number;
  avgRank: number;
  coverage: number;
  sentiment: string;
  color: string;
  isTop: boolean;
  strength: string;
  weakness: string;
  topQueries: number;
  sparklineData: number[];
}

export const PLATFORMS: PlatformIntel[] = [
  { name: 'ChatGPT', domain: 'openai.com', citations: 312, sov: 14.2, avgRank: 2.1, coverage: 78, sentiment: 'Positive', color: '#10A37F', isTop: true, strength: 'Best reach (36.8%)', weakness: 'Low security coverage', topQueries: 12, sparklineData: Array.from({ length: 28 }, (_, i) => Math.floor(8 + Math.sin(i * 0.5) * 3 + i * 0.3)) },
  { name: 'Claude', domain: 'anthropic.com', citations: 189, sov: 11.8, avgRank: 2.8, coverage: 62, sentiment: 'Positive', color: '#D4A574', isTop: false, strength: 'Fastest growing — +18% citations this month', weakness: 'Not citing your comparison guides', topQueries: 9, sparklineData: Array.from({ length: 28 }, (_, i) => Math.floor(4 + Math.sin(i * 0.6) * 2 + i * 0.25)) },
  { name: 'Perplexity', domain: 'perplexity.ai', citations: 156, sov: 13.1, avgRank: 1.9, coverage: 71, sentiment: 'Positive', color: '#4A90D9', isTop: false, strength: "Highest rank (1.9) — you're their #1 pick", weakness: 'Only 71% coverage, missing enterprise queries', topQueries: 8, sparklineData: Array.from({ length: 28 }, (_, i) => Math.floor(3 + Math.sin(i * 0.4) * 2 + i * 0.2)) },
  { name: 'Google AI', domain: 'google.com', citations: 118, sov: 9.4, avgRank: 3.2, coverage: 55, sentiment: 'Neutral', color: '#34A853', isTop: false, strength: 'Strong schema recognition — your structured content wins', weakness: 'Lowest SOV (9.4%) — underrepresented', topQueries: 6, sparklineData: Array.from({ length: 28 }, (_, i) => Math.floor(2 + Math.sin(i * 0.3) * 2 + i * 0.15)) },
  { name: 'Gemini', domain: 'gemini.google.com', citations: 72, sov: 8.7, avgRank: 3.5, coverage: 48, sentiment: 'Positive', color: '#8E75B2', isTop: false, strength: 'Growing coverage — first citations this month on 3 pages', weakness: 'Lowest coverage (48%) and citations (72)', topQueries: 5, sparklineData: Array.from({ length: 28 }, (_, i) => Math.floor(1 + Math.sin(i * 0.5) * 1.5 + i * 0.1)) },
];

// ─── Platform Drawer Detail Data ────────────────────────────────────────────

export interface PlatformDrawerQuery {
  query: string;
  citations: number;
  rank: number | null;
}

export interface PlatformDrawerURL {
  url: string;
  citations: number;
}

export interface PlatformDrawerCompetitor {
  domain: string;
  name: string;
  sov: number;
}

export interface PlatformStructuralPrefs {
  faqSections: number;
  avgWordCount: number;
  comparisonTables: number;
  externalCitations: number;
  yourScore: number;
  mainGaps: string[];
}

export const PLATFORM_DRAWER_DATA: Record<string, {
  queries: PlatformDrawerQuery[];
  urls: PlatformDrawerURL[];
  competitors: PlatformDrawerCompetitor[];
  prefs: PlatformStructuralPrefs;
}> = {
  ChatGPT: {
    queries: [
      { query: 'AI app builder comparison', citations: 14, rank: 1 },
      { query: 'lovable vs cursor', citations: 9, rank: 2 },
      { query: 'best no-code builder', citations: 7, rank: 3 },
      { query: 'AI app builder pricing', citations: 6, rank: 4 },
      { query: 'enterprise AI app builder', citations: 5, rank: null },
    ],
    urls: [
      { url: '/blog/ai-app-builder-comparison', citations: 23 },
      { url: '/blog/lovable-vs-cursor', citations: 12 },
      { url: '/docs/getting-started', citations: 8 },
    ],
    competitors: [
      { domain: 'bolt.new', name: 'Bolt.new', sov: 42.3 },
      { domain: 'lovable.dev', name: 'You', sov: 14.2 },
      { domain: 'cursor.com', name: 'Cursor', sov: 12.8 },
    ],
    prefs: { faqSections: 72, avgWordCount: 2200, comparisonTables: 65, externalCitations: 84, yourScore: 45, mainGaps: ['FAQ sections (0% of your pages)', 'comparison tables (30%)'] },
  },
  Claude: {
    queries: [
      { query: 'vibe coding for enterprise', citations: 12, rank: 1 },
      { query: 'AI builder security best practices', citations: 8, rank: 2 },
      { query: 'no-code enterprise compliance', citations: 6, rank: 3 },
    ],
    urls: [
      { url: '/blog/vibe-coding-enterprise', citations: 12 },
      { url: '/blog/security-ai-apps', citations: 8 },
      { url: '/docs/api-reference', citations: 6 },
    ],
    competitors: [
      { domain: 'bolt.new', name: 'Bolt.new', sov: 38.1 },
      { domain: 'cursor.com', name: 'Cursor', sov: 15.4 },
      { domain: 'lovable.dev', name: 'You', sov: 11.8 },
    ],
    prefs: { faqSections: 58, avgWordCount: 2400, comparisonTables: 52, externalCitations: 78, yourScore: 52, mainGaps: ['Longer-form content needed', 'Add code examples'] },
  },
  Perplexity: {
    queries: [
      { query: 'best AI app builder 2026', citations: 10, rank: 1 },
      { query: 'no-code platform comparison', citations: 8, rank: 1 },
      { query: 'AI builder RBAC features', citations: 6, rank: 2 },
    ],
    urls: [
      { url: '/blog/ai-app-builder-comparison', citations: 14 },
      { url: '/blog/lovable-vs-cursor', citations: 12 },
      { url: '/blog/rbac-ai-apps', citations: 10 },
    ],
    competitors: [
      { domain: 'bolt.new', name: 'Bolt.new', sov: 35.2 },
      { domain: 'lovable.dev', name: 'You', sov: 13.1 },
      { domain: 'replit.com', name: 'Replit', sov: 11.9 },
    ],
    prefs: { faqSections: 65, avgWordCount: 1800, comparisonTables: 70, externalCitations: 90, yourScore: 61, mainGaps: ['More external citations needed', 'Add data tables'] },
  },
  'Google AI': {
    queries: [
      { query: 'AI app builder features', citations: 8, rank: 2 },
      { query: 'no-code app security', citations: 6, rank: 3 },
      { query: 'enterprise no-code platform', citations: 4, rank: 4 },
    ],
    urls: [
      { url: '/blog/ai-app-builder-comparison', citations: 11 },
      { url: '/blog/vibe-coding-enterprise', citations: 9 },
      { url: '/blog/security-ai-apps', citations: 6 },
    ],
    competitors: [
      { domain: 'bolt.new', name: 'Bolt.new', sov: 44.1 },
      { domain: 'cursor.com', name: 'Cursor', sov: 14.8 },
      { domain: 'lovable.dev', name: 'You', sov: 9.4 },
    ],
    prefs: { faqSections: 80, avgWordCount: 2500, comparisonTables: 55, externalCitations: 72, yourScore: 38, mainGaps: ['Schema markup missing', 'FAQ JSON-LD needed'] },
  },
  Gemini: {
    queries: [
      { query: 'AI app builder for beginners', citations: 6, rank: 2 },
      { query: 'no-code platform for startups', citations: 4, rank: 3 },
      { query: 'AI builder alternatives 2026', citations: 3, rank: 4 },
    ],
    urls: [
      { url: '/blog/non-tech-founder-guide', citations: 8 },
      { url: '/blog/bolt-new-alternatives', citations: 6 },
      { url: '/docs/getting-started', citations: 4 },
    ],
    competitors: [
      { domain: 'bolt.new', name: 'Bolt.new', sov: 40.5 },
      { domain: 'replit.com', name: 'Replit', sov: 16.2 },
      { domain: 'lovable.dev', name: 'You', sov: 8.7 },
    ],
    prefs: { faqSections: 60, avgWordCount: 2000, comparisonTables: 48, externalCitations: 68, yourScore: 42, mainGaps: ['Add structured data', 'More beginner-friendly content'] },
  },
};

// ─── Citation URL Table ─────────────────────────────────────────────────────

export interface CitationURL {
  url: string;
  title: string;
  citations: number;
  platforms: { chatgpt: number; claude: number; perplexity: number; google_ai: number; gemini: number };
  queries: number;
  cps: number;
  firstCited: string;
  velocity: number;
  velocityTrend: 'up' | 'down' | 'flat';
}

export const CITATION_URLS: CitationURL[] = [
  { url: 'lovable.dev/blog/ai-app-builder-comparison', title: 'AI App Builder Comparison Guide', citations: 63, platforms: { chatgpt: 23, claude: 15, perplexity: 14, google_ai: 11, gemini: 0 }, queries: 12, cps: 0.713, firstCited: 'Jan 14, 2026', velocity: 4.8, velocityTrend: 'up' },
  { url: 'lovable.dev/blog/lovable-vs-cursor', title: 'Lovable vs Cursor: Honest Review', citations: 38, platforms: { chatgpt: 14, claude: 0, perplexity: 12, google_ai: 8, gemini: 4 }, queries: 8, cps: 0.654, firstCited: 'Jan 21, 2026', velocity: 3.9, velocityTrend: 'up' },
  { url: 'lovable.dev/blog/vibe-coding-enterprise', title: 'Vibe Coding for Enterprise Teams', citations: 31, platforms: { chatgpt: 0, claude: 12, perplexity: 10, google_ai: 9, gemini: 0 }, queries: 6, cps: 0.649, firstCited: 'Jan 31, 2026', velocity: 3.2, velocityTrend: 'up' },
  { url: 'lovable.dev/blog/bolt-new-alternatives', title: 'Bolt.new Alternatives in 2026', citations: 29, platforms: { chatgpt: 15, claude: 0, perplexity: 8, google_ai: 0, gemini: 6 }, queries: 9, cps: 0.521, firstCited: 'Feb 13, 2026', velocity: 1.4, velocityTrend: 'down' },
  { url: 'lovable.dev/blog/security-ai-apps', title: 'Security in AI-Generated Apps', citations: 24, platforms: { chatgpt: 10, claude: 8, perplexity: 0, google_ai: 6, gemini: 0 }, queries: 5, cps: 0.482, firstCited: 'Feb 7, 2026', velocity: 2.1, velocityTrend: 'flat' },
  { url: 'lovable.dev/blog/non-tech-founder-guide', title: "Non-Technical Founder's Guide", citations: 22, platforms: { chatgpt: 8, claude: 6, perplexity: 0, google_ai: 0, gemini: 8 }, queries: 7, cps: 0.538, firstCited: 'Feb 19, 2026', velocity: 2.9, velocityTrend: 'up' },
  { url: 'lovable.dev/docs/getting-started', title: 'Getting Started Guide', citations: 19, platforms: { chatgpt: 8, claude: 6, perplexity: 3, google_ai: 2, gemini: 0 }, queries: 4, cps: 0.521, firstCited: 'Jan 9, 2026', velocity: 1.5, velocityTrend: 'flat' },
  { url: 'lovable.dev/blog/rbac-ai-apps', title: 'RBAC in AI-Generated Applications', citations: 18, platforms: { chatgpt: 0, claude: 0, perplexity: 10, google_ai: 4, gemini: 4 }, queries: 3, cps: 0.459, firstCited: 'Feb 24, 2026', velocity: 0.8, velocityTrend: 'down' },
  { url: 'lovable.dev/docs/api-reference', title: 'API Reference Documentation', citations: 14, platforms: { chatgpt: 4, claude: 6, perplexity: 0, google_ai: 4, gemini: 0 }, queries: 2, cps: 0.612, firstCited: 'Jan 17, 2026', velocity: 1.2, velocityTrend: 'flat' },
  { url: 'lovable.dev/blog/soc2-compliance', title: 'SOC 2 for AI Dev Platforms', citations: 8, platforms: { chatgpt: 0, claude: 4, perplexity: 0, google_ai: 2, gemini: 2 }, queries: 2, cps: 0.385, firstCited: 'Mar 4, 2026', velocity: 0.5, velocityTrend: 'down' },
];

// ─── URL Drawer Structural Signals ──────────────────────────────────────────

export interface StructuralSignal {
  label: string;
  value: string;
}

export interface ImprovementItem {
  text: string;
  good: boolean;
  detail: string;
}

export interface URLDrawerDetail {
  structuralSignals: StructuralSignal[];
  improvements: ImprovementItem[];
  estimatedImpact: string;
  queriesCiting: { query: string; platforms: string[] }[];
  trendData: number[];
}

export const URL_DRAWER_DATA: Record<string, URLDrawerDetail> = {
  'lovable.dev/blog/ai-app-builder-comparison': {
    structuralSignals: [
      { label: 'Word count', value: '3,200' },
      { label: 'Headers', value: '14' },
      { label: 'FAQ sections', value: '2' },
      { label: 'Tables', value: '3' },
      { label: 'Lists', value: '8' },
      { label: 'External citations', value: '12' },
      { label: 'Reading level', value: '9.8' },
    ],
    improvements: [
      { text: 'Word count is above average (3,200 vs 2,200 avg)', good: true, detail: 'good' },
      { text: 'Headers are strong (14 vs 12 avg)', good: true, detail: 'good' },
      { text: 'Missing: Schema markup (FAQ/HowTo JSON-LD)', good: false, detail: '68% of top content has this' },
      { text: 'Stats and data points are below average (4 vs 8 avg)', good: false, detail: 'Could improve' },
      { text: 'External citations are strong (12 vs 10 avg)', good: true, detail: 'good' },
      { text: 'Missing on Gemini', good: false, detail: 'Consider Gemini-specific optimization' },
    ],
    estimatedImpact: '+15-20% more citations',
    queriesCiting: [
      { query: 'best AI app builder comparison', platforms: ['ChatGPT', 'Claude', 'Perplexity'] },
      { query: 'AI app builder features comparison', platforms: ['ChatGPT', 'Google AI'] },
      { query: 'lovable vs bolt.new vs cursor', platforms: ['Claude', 'Perplexity'] },
      { query: 'no-code app builder review 2026', platforms: ['ChatGPT'] },
    ],
    trendData: Array.from({ length: 28 }, (_, i) => Math.floor(1.5 + Math.sin(i * 0.4) * 0.8 + i * 0.08)),
  },
};

// Generate default drawer data for URLs not explicitly defined
export const getURLDrawerDetail = (url: string): URLDrawerDetail => {
  if (URL_DRAWER_DATA[url]) return URL_DRAWER_DATA[url];
  const entry = CITATION_URLS.find((u) => u.url === url);
  const c = entry?.citations ?? 10;
  return {
    structuralSignals: [
      { label: 'Word count', value: `${1200 + Math.floor(c * 25)}` },
      { label: 'Headers', value: `${Math.floor(6 + c * 0.1)}` },
      { label: 'FAQ sections', value: `${c > 30 ? 2 : c > 15 ? 1 : 0}` },
      { label: 'Tables', value: `${Math.floor(1 + c * 0.04)}` },
      { label: 'Lists', value: `${Math.floor(3 + c * 0.08)}` },
      { label: 'External citations', value: `${Math.floor(4 + c * 0.12)}` },
      { label: 'Reading level', value: `${(8 + Math.random() * 2).toFixed(1)}` },
    ],
    improvements: [
      { text: `Word count is ${c > 25 ? 'above' : 'below'} average`, good: c > 25, detail: c > 25 ? 'good' : 'Expand content to 2,200+ words' },
      { text: 'Missing: Schema markup (FAQ/HowTo JSON-LD)', good: false, detail: '68% of top content has this' },
      { text: `External citations are ${c > 20 ? 'strong' : 'weak'}`, good: c > 20, detail: c > 20 ? 'good' : 'Add 4-6 more authoritative sources' },
    ],
    estimatedImpact: `+${Math.floor(10 + (40 - c) * 0.5)}-${Math.floor(15 + (40 - c) * 0.5)}% more citations`,
    queriesCiting: [
      { query: `query related to ${entry?.title ?? 'this content'}`, platforms: ['ChatGPT', 'Claude'] },
    ],
    trendData: Array.from({ length: 28 }, (_, i) => Math.max(0, Math.floor(c / 28 + Math.sin(i * 0.5) * 0.5))),
  };
};

// ─── Engine key to display name ─────────────────────────────────────────────

export const ENGINE_DISPLAY: Record<string, string> = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  perplexity: 'Perplexity',
  google_ai: 'Google AI',
  gemini: 'Gemini',
};

export const ENGINE_DOMAINS: Record<string, string> = {
  chatgpt: 'openai.com',
  claude: 'anthropic.com',
  perplexity: 'perplexity.ai',
  google_ai: 'google.com',
  gemini: 'gemini.google.com',
};
