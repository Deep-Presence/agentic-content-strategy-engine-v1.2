// ─── Gap Statement ──────────────────────────────────────────────────────────

export const GAP_DATA = {
  siteHealth: { score: 95, label: 'Fast load times, clean code, strong security' },
  aiCitationReady: { score: 38.7, label: 'Missing: question headings, FAQ sections, comparison tables, llms.txt' },
  narrative: {
    title: 'THE GAP',
    body: 'Your site is healthy — but AI engines can\'t extract useful answers from it.',
    focus: 'question headings, FAQ sections, comparison tables, and llms.txt',
    estimate: '65+',
  },
};

// ─── Priority Fixes ─────────────────────────────────────────────────────────

export type Severity = 'critical' | 'high' | 'medium' | 'low';
export type Effort = 'low' | 'medium' | 'high';

export interface PriorityFix {
  rank: number;
  severity: Severity;
  title: string;
  current: string;
  target: string;
  why: string;
  impact: string;
  effort: Effort;
  pages: number;
  dimension: string;
}

export const PRIORITY_FIXES: PriorityFix[] = [
  {
    rank: 1,
    severity: 'critical',
    title: 'Add question headings to 62 pages',
    current: '14.8% of pages have question headings',
    target: '30%+ (what top-cited content looks like)',
    why: 'AI engines extract answers from question-heading pairs. Pages without question headings are essentially invisible to AI citation.',
    impact: '+15-20% citation rate',
    effort: 'medium',
    pages: 62,
    dimension: 'Extractability',
  },
  {
    rank: 2,
    severity: 'critical',
    title: 'Rephrase 30%+ of headings as questions',
    current: 'Only 14.8% of headings are question-format',
    target: '30%+ question headings across all content',
    why: 'AI engines are trained to match questions to answers. Question-format headings dramatically increase the chance your content becomes a cited answer.',
    impact: '+12-15% citation rate',
    effort: 'medium',
    pages: 200,
    dimension: 'Extractability',
  },
  {
    rank: 3,
    severity: 'high',
    title: 'Create llms.txt file',
    current: 'Missing — not implemented',
    target: 'Present at /llms.txt with citation guidance',
    why: "llms.txt tells AI engines how to reference your content. It's the robots.txt equivalent for AI citation. Without it, engines decide on their own how (or whether) to cite you.",
    impact: '+5-8% citation rate',
    effort: 'low',
    pages: 1,
    dimension: 'Crawlability',
  },
  {
    rank: 4,
    severity: 'high',
    title: 'Add FAQ schema to pages with FAQ content',
    current: '0 pages have FAQ schema markup',
    target: 'All pages with FAQ sections should have FAQPage schema',
    why: 'FAQ schema helps AI engines identify question-answer pairs in your content. Pages with FAQ schema are 2.3x more likely to be cited with a direct link.',
    impact: '+8-12% citation rate',
    effort: 'low',
    pages: 28,
    dimension: 'Schema Markup',
  },
  {
    rank: 5,
    severity: 'high',
    title: 'Add Article/BlogPosting schema to blog posts',
    current: '28 blog posts missing structured data',
    target: 'Every blog post has Article or BlogPosting JSON-LD',
    why: "Structured data helps AI engines understand your content's authorship, publication date, and topic. Missing schema = missing context.",
    impact: '+5-8% citation rate',
    effort: 'low',
    pages: 28,
    dimension: 'Schema Markup',
  },
  {
    rank: 6,
    severity: 'high',
    title: 'Fix pages with no H1 heading',
    current: '7 pages have no H1 tag',
    target: 'Exactly one H1 per page describing the main topic',
    why: 'AI engines use H1 as the primary signal for what a page is about. Missing H1 means the engine has to guess — and often guesses wrong.',
    impact: '+3-5% for affected pages',
    effort: 'low',
    pages: 7,
    dimension: 'On-Page SEO',
  },
  {
    rank: 7,
    severity: 'medium',
    title: 'Shorten titles over 60 characters',
    current: '87 pages have titles exceeding 60 characters',
    target: 'All titles under 60 characters for clean AI citation',
    why: 'When AI engines cite your content, they often use the page title. Long titles get truncated, making citations less clickable.',
    impact: '+2-3% click-through on citations',
    effort: 'low',
    pages: 87,
    dimension: 'On-Page SEO',
  },
];

// ─── Dimensions ─────────────────────────────────────────────────────────────

export interface Dimension {
  name: string;
  score: number;
  weight: string;
  findings: number;
  status: 'pass' | 'warning' | 'fail';
  explanation: string;
}

export const DIMENSIONS: Dimension[] = [
  { name: 'Crawlability', score: 100, weight: '20%', findings: 4, status: 'pass', explanation: 'AI bots can access all your pages' },
  { name: 'Performance', score: 88, weight: '10%', findings: 899, status: 'warning', explanation: 'Pages load fast enough for AI crawlers' },
  { name: 'On-Page SEO', score: 84, weight: '15%', findings: 458, status: 'warning', explanation: 'Some pages missing meta descriptions and H1 tags' },
  { name: 'Extractability', score: 95, weight: '20%', findings: 377, status: 'pass', explanation: 'AI engines CAN extract content — but structure is weak' },
  { name: 'Schema Markup', score: 98, weight: '10%', findings: 228, status: 'pass', explanation: 'Your structured data helps engines understand content' },
  { name: 'E-E-A-T', score: 100, weight: '15%', findings: 28, status: 'pass', explanation: 'Your authority signals are strong' },
  { name: 'Freshness', score: 100, weight: '5%', findings: 41, status: 'pass', explanation: 'Content is regularly updated' },
  { name: 'Security', score: 97, weight: '5%', findings: 600, status: 'pass', explanation: 'HTTPS everywhere' },
];

// ─── Bot Access ─────────────────────────────────────────────────────────────

export interface BotAccessEntry {
  name: string;
  company: string;
  domain: string;
  status: 'allowed' | 'blocked';
  robotsTxt: boolean;
  lastCrawl: string;
}

export const BOT_ACCESS: BotAccessEntry[] = [
  { name: 'GPTBot', company: 'OpenAI', domain: 'openai.com', status: 'allowed', robotsTxt: true, lastCrawl: '2h ago' },
  { name: 'ClaudeBot', company: 'Anthropic', domain: 'anthropic.com', status: 'allowed', robotsTxt: true, lastCrawl: '4h ago' },
  { name: 'PerplexityBot', company: 'Perplexity', domain: 'perplexity.ai', status: 'allowed', robotsTxt: true, lastCrawl: '1h ago' },
  { name: 'Google-Extended', company: 'Google', domain: 'google.com', status: 'allowed', robotsTxt: true, lastCrawl: '6h ago' },
  { name: 'CCBot', company: 'Common Crawl', domain: 'commoncrawl.org', status: 'allowed', robotsTxt: true, lastCrawl: '12h ago' },
];

export const CRITICAL_FILES = [
  { name: 'robots.txt', present: true, description: 'Allows all AI bots' },
  { name: 'llms.txt', present: false, description: "AI engines don't know how to cite you properly" },
  { name: 'Sitemap', present: true, description: '847 URLs indexed' },
];

// ─── Platform Citation Preferences ──────────────────────────────────────────

export type EngineKey = 'chatgpt' | 'claude' | 'perplexity' | 'google_ai' | 'gemini';

export interface EnginePreferences {
  name: string;
  domain: string;
  preferences: Record<string, number>;
  yourScores: Record<string, number>;
  overallScore: number;
  summary: string;
}

export const SIGNAL_KEYS = ['faq', 'tables', 'headers', 'wordCount', 'lists', 'schema', 'citations', 'readingLevel'] as const;

export const SIGNAL_LABELS: Record<string, string> = {
  faq: 'FAQ Sections',
  tables: 'Tables',
  headers: 'Headers',
  wordCount: 'Word Count',
  lists: 'Lists',
  schema: 'Schema',
  citations: 'Citations',
  readingLevel: 'Reading Level',
};

export const ENGINE_PREFERENCES: Record<EngineKey, EnginePreferences> = {
  chatgpt: {
    name: 'ChatGPT',
    domain: 'openai.com',
    preferences: { faq: 72, tables: 65, headers: 88, wordCount: 78, lists: 70, schema: 45, citations: 82, readingLevel: 60 },
    yourScores: { faq: 65, tables: 45, headers: 82, wordCount: 70, lists: 60, schema: 35, citations: 78, readingLevel: 90 },
    overallScore: 68,
    summary: 'ChatGPT favors content with FAQ sections (72% of top-cited content has them) and external citations (82%). Your content scores well on headers (82%) and reading level, but needs more FAQ sections (you: 65%, target: 72%) and comparison tables (you: 45%, target: 65%).',
  },
  claude: {
    name: 'Claude',
    domain: 'anthropic.com',
    preferences: { faq: 55, tables: 70, headers: 82, wordCount: 85, lists: 65, schema: 40, citations: 90, readingLevel: 55 },
    yourScores: { faq: 65, tables: 45, headers: 82, wordCount: 70, lists: 60, schema: 35, citations: 78, readingLevel: 90 },
    overallScore: 71,
    summary: "Claude heavily weights external citations (90%) and word count (85%). Your citation game is decent (78%) but your content is shorter than Claude prefers (you: 70%, target: 85%). Claude also values comparison tables highly.",
  },
  perplexity: {
    name: 'Perplexity',
    domain: 'perplexity.ai',
    preferences: { faq: 68, tables: 60, headers: 75, wordCount: 72, lists: 80, schema: 55, citations: 88, readingLevel: 65 },
    yourScores: { faq: 65, tables: 45, headers: 82, wordCount: 70, lists: 60, schema: 35, citations: 78, readingLevel: 90 },
    overallScore: 65,
    summary: "Perplexity prefers well-structured content with lots of lists (80%) and external citations (88%). Your list usage is below target (60% vs 80%). Perplexity also values schema markup more than other engines.",
  },
  google_ai: {
    name: 'Google AI',
    domain: 'google.com',
    preferences: { faq: 80, tables: 75, headers: 90, wordCount: 70, lists: 60, schema: 85, citations: 75, readingLevel: 70 },
    yourScores: { faq: 65, tables: 45, headers: 82, wordCount: 70, lists: 60, schema: 35, citations: 78, readingLevel: 90 },
    overallScore: 62,
    summary: "Google AI strongly prefers schema markup (85%) and FAQ sections (80%). Your schema implementation is weak (35% vs 85% target) — this is your biggest gap on Google AI. Adding FAQ schema alone could significantly improve your Google AI citations.",
  },
  gemini: {
    name: 'Gemini',
    domain: 'gemini.google.com',
    preferences: { faq: 60, tables: 55, headers: 78, wordCount: 80, lists: 72, schema: 50, citations: 70, readingLevel: 68 },
    yourScores: { faq: 65, tables: 45, headers: 82, wordCount: 70, lists: 60, schema: 35, citations: 78, readingLevel: 90 },
    overallScore: 70,
    summary: "Gemini values word count (80%) and lists (72%) more than FAQ sections. Your content is slightly shorter than Gemini prefers. Gemini is your fastest-growing engine — first citations on 3 new pages this month.",
  },
};

export const ENGINE_LIST: { key: EngineKey; name: string; domain: string }[] = [
  { key: 'chatgpt', name: 'ChatGPT', domain: 'openai.com' },
  { key: 'claude', name: 'Claude', domain: 'anthropic.com' },
  { key: 'perplexity', name: 'Perplexity', domain: 'perplexity.ai' },
  { key: 'google_ai', name: 'Google AI', domain: 'google.com' },
  { key: 'gemini', name: 'Gemini', domain: 'gemini.google.com' },
];

// ─── Bot Crawl Activity (28 days) ───────────────────────────────────────────

function seedRandom(seed: number) {
  return () => {
    seed = (seed * 16807 + 0) % 2147483647;
    return (seed - 1) / 2147483646;
  };
}

const rand = seedRandom(42);

export const BOT_CRAWL_DATA = Array.from({ length: 28 }, (_, i) => ({
  date: `Mar ${i + 1}`,
  GPTBot: Math.floor(280 + rand() * 40 + i * 2),
  ClaudeBot: Math.floor(260 + rand() * 30 + i * 3),
  PerplexityBot: Math.floor(220 + rand() * 40 + i * 4),
  'Google-Extended': Math.floor(300 + rand() * 20 + i * 1),
  Gemini: Math.floor(180 + rand() * 30 + i * 2),
}));

export const BOT_COLORS: Record<string, string> = {
  GPTBot: '#10A37F',
  ClaudeBot: '#D4A574',
  PerplexityBot: '#4A90D9',
  'Google-Extended': '#34A853',
  Gemini: '#8E75B2',
};

export const BOT_DOMAINS: Record<string, string> = {
  GPTBot: 'openai.com',
  ClaudeBot: 'anthropic.com',
  PerplexityBot: 'perplexity.ai',
  'Google-Extended': 'google.com',
  Gemini: 'gemini.google.com',
};

export const CRAWL_SUMMARY = {
  totals: {
    GPTBot: '8,400',
    ClaudeBot: '7,900',
    PerplexityBot: '7,200',
    'Google-Extended': '8,800',
    Gemini: '5,600',
  } as Record<string, string>,
  lastCrawl: {
    GPTBot: '2h ago',
    ClaudeBot: '4h ago',
    PerplexityBot: '1h ago',
    'Google-Extended': '6h ago',
    Gemini: '12h ago',
  } as Record<string, string>,
};

export const BOT_KEYS = ['GPTBot', 'ClaudeBot', 'PerplexityBot', 'Google-Extended', 'Gemini'] as const;

// ─── Snippet Readiness Distribution ─────────────────────────────────────────

export interface SnippetBand {
  range: string;
  count: number;
  label: string;
  color: string;
}

export const SNIPPET_DISTRIBUTION: SnippetBand[] = [
  { range: '0-20', count: 62, label: 'Virtually uncitable', color: '#E5484D' },
  { range: '21-40', count: 45, label: 'Needs significant work', color: '#F5A623' },
  { range: '41-60', count: 38, label: 'Room to improve', color: '#F5A623' },
  { range: '61-80', count: 32, label: 'Good, minor improvements', color: '#5BA4C4' },
  { range: '81-100', count: 23, label: 'Citation-ready', color: '#34B27B' },
];

// ─── Affected Pages (for drawers) ───────────────────────────────────────────

export interface AffectedPage {
  url: string;
  title: string;
  score: number;
  missing: string[];
  published: string;
}

export const AFFECTED_PAGES: AffectedPage[] = [
  { url: '/blog/security-ai-apps', title: 'Security in AI-Generated Applications', score: 12, missing: ['question headings', 'FAQ'], published: 'Jan 14, 2026' },
  { url: '/blog/rbac-ai-apps', title: 'RBAC in AI-Generated Applications', score: 15, missing: ['question headings', 'FAQ', 'schema'], published: 'Jan 23, 2026' },
  { url: '/docs/api-reference', title: 'API Reference Documentation', score: 18, missing: ['question headings'], published: 'Jan 17, 2026' },
  { url: '/blog/vibe-coding-intro', title: 'Introduction to Vibe Coding', score: 11, missing: ['question headings', 'FAQ'], published: 'Feb 3, 2026' },
  { url: '/docs/deployment', title: 'Deployment Guide', score: 22, missing: ['FAQ', 'schema'], published: 'Feb 10, 2026' },
  { url: '/blog/ai-trends-2026', title: 'AI Trends to Watch in 2026', score: 14, missing: ['question headings', 'comparison tables'], published: 'Jan 28, 2026' },
  { url: '/docs/authentication', title: 'Authentication Setup', score: 19, missing: ['question headings', 'FAQ'], published: 'Feb 5, 2026' },
  { url: '/blog/team-update', title: 'Team Update — Q1 2026', score: 8, missing: ['question headings', 'FAQ', 'schema'], published: 'Mar 1, 2026' },
  { url: '/docs/webhooks', title: 'Webhooks Integration', score: 20, missing: ['question headings'], published: 'Feb 15, 2026' },
  { url: '/docs/database-setup', title: 'Database Setup Guide', score: 16, missing: ['question headings', 'FAQ'], published: 'Jan 20, 2026' },
  { url: '/blog/getting-started', title: 'Getting Started with Lovable', score: 12, missing: ['question headings', 'FAQ', 'schema'], published: 'Jan 10, 2026' },
  { url: '/blog/changelog-march', title: 'March 2026 Changelog', score: 8, missing: ['question headings', 'FAQ'], published: 'Mar 5, 2026' },
];
