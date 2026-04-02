// ─── KPI Data ────────────────────────────────────────────────────────────────

export const KPI_DATA = {
  siteHealth: { value: 95, max: 100, grade: 'A' },
  aeoReadiness: { value: 38.7, max: 100, grade: 'F' },
  snippetReadiness: { value: 38.7, label: '/100 avg across pages' },
  questionHeadings: { value: 14.8, target: 30, label: '% vs 30% target' },
  criticalIssues: { value: 7, label: 'findings blocking citation' },
  llmsTxt: { status: 'Missing', label: 'not implemented' },
};

// ─── Dimensions ──────────────────────────────────────────────────────────────

export interface Dimension {
  name: string;
  score: number;
  weight: string;
  findings: number;
  status: 'pass' | 'warn' | 'fail';
}

export const DIMENSIONS: Dimension[] = [
  { name: 'Crawlability', score: 100, weight: '20%', findings: 4, status: 'pass' },
  { name: 'Performance', score: 88, weight: '10%', findings: 899, status: 'warn' },
  { name: 'On-Page SEO', score: 84, weight: '15%', findings: 458, status: 'warn' },
  { name: 'Extractability', score: 95, weight: '20%', findings: 377, status: 'pass' },
  { name: 'Schema Markup', score: 98, weight: '10%', findings: 228, status: 'pass' },
  { name: 'E-E-A-T', score: 100, weight: '15%', findings: 28, status: 'pass' },
  { name: 'Freshness', score: 100, weight: '5%', findings: 41, status: 'pass' },
  { name: 'Security', score: 97, weight: '5%', findings: 600, status: 'pass' },
];

// ─── Bot Access ──────────────────────────────────────────────────────────────

export interface BotAccessEntry {
  name: string;
  company: string;
  domain: string;
  status: 'allowed' | 'blocked';
  robotsTxt: boolean;
}

export const BOT_ACCESS: BotAccessEntry[] = [
  { name: 'GPTBot', company: 'OpenAI', domain: 'openai.com', status: 'allowed', robotsTxt: true },
  { name: 'ClaudeBot', company: 'Anthropic', domain: 'anthropic.com', status: 'allowed', robotsTxt: true },
  { name: 'PerplexityBot', company: 'Perplexity', domain: 'perplexity.ai', status: 'allowed', robotsTxt: true },
  { name: 'Google-Extended', company: 'Google', domain: 'google.com', status: 'allowed', robotsTxt: true },
  { name: 'CCBot', company: 'Common Crawl', domain: 'commoncrawl.org', status: 'allowed', robotsTxt: true },
];

export const SITE_FILES = {
  robotsTxt: true,
  llmsTxt: false,
  sitemap: { found: true, urls: 847 },
};

// ─── Snippet Distribution ────────────────────────────────────────────────────

export interface SnippetBand {
  range: string;
  count: number;
  label: string;
  color: string;
}

export const SNIPPET_DISTRIBUTION: SnippetBand[] = [
  { range: '0-20', count: 62, label: 'Uncitable', color: '#E5484D' },
  { range: '21-40', count: 45, label: 'Poor', color: '#E87C3F' },
  { range: '41-60', count: 38, label: 'Fair', color: '#F5A623' },
  { range: '61-80', count: 32, label: 'Good', color: '#6CB8D2' },
  { range: '81-100', count: 23, label: 'Excellent', color: '#34B27B' },
];

// ─── Bot Crawl Activity (28 days) ────────────────────────────────────────────

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
  PerplexityBot: '#20B8CD',
  'Google-Extended': '#4285F4',
  Gemini: '#886FBF',
};

export const BOT_DOMAINS: Record<string, string> = {
  GPTBot: 'openai.com',
  ClaudeBot: 'anthropic.com',
  PerplexityBot: 'perplexity.ai',
  'Google-Extended': 'google.com',
  Gemini: 'gemini.google.com',
};

export const CRAWL_SUMMARY = {
  totals: { GPTBot: '8,400', ClaudeBot: '7,900', PerplexityBot: '7,200', 'Google-Extended': '8,800', Gemini: '5,600' } as Record<string, string>,
  lastCrawl: { GPTBot: '2h ago', ClaudeBot: '4h ago', PerplexityBot: '1h ago', 'Google-Extended': '6h ago', Gemini: '12h ago' } as Record<string, string>,
};

export const BOT_KEYS = ['GPTBot', 'ClaudeBot', 'PerplexityBot', 'Google-Extended', 'Gemini'] as const;

// ─── Platform Citation Preferences ───────────────────────────────────────────

export type PlatformKey = 'chatgpt' | 'claude' | 'perplexity' | 'google_ai' | 'gemini';

export interface PlatformMeta {
  key: PlatformKey;
  label: string;
  domain: string;
  color: string;
}

export const PLATFORMS: PlatformMeta[] = [
  { key: 'chatgpt', label: 'ChatGPT', domain: 'openai.com', color: '#10A37F' },
  { key: 'claude', label: 'Claude', domain: 'anthropic.com', color: '#D4A574' },
  { key: 'perplexity', label: 'Perplexity', domain: 'perplexity.ai', color: '#20B8CD' },
  { key: 'google_ai', label: 'Google AI', domain: 'google.com', color: '#4285F4' },
  { key: 'gemini', label: 'Gemini', domain: 'gemini.google.com', color: '#886FBF' },
];

export interface PreferenceSignal {
  signal: string;
  value: number;
}

export const PLATFORM_PREFERENCES: Record<PlatformKey, PreferenceSignal[]> = {
  chatgpt: [
    { signal: 'FAQ Sections', value: 72 },
    { signal: 'Tables', value: 65 },
    { signal: 'Headers', value: 88 },
    { signal: 'Word Count', value: 78 },
    { signal: 'Lists', value: 70 },
    { signal: 'Schema', value: 45 },
    { signal: 'Citations', value: 82 },
    { signal: 'Reading Level', value: 60 },
  ],
  claude: [
    { signal: 'FAQ Sections', value: 55 },
    { signal: 'Tables', value: 48 },
    { signal: 'Headers', value: 92 },
    { signal: 'Word Count', value: 85 },
    { signal: 'Lists', value: 58 },
    { signal: 'Schema', value: 35 },
    { signal: 'Citations', value: 90 },
    { signal: 'Reading Level', value: 75 },
  ],
  perplexity: [
    { signal: 'FAQ Sections', value: 80 },
    { signal: 'Tables', value: 72 },
    { signal: 'Headers', value: 78 },
    { signal: 'Word Count', value: 65 },
    { signal: 'Lists', value: 82 },
    { signal: 'Schema', value: 55 },
    { signal: 'Citations', value: 88 },
    { signal: 'Reading Level', value: 70 },
  ],
  google_ai: [
    { signal: 'FAQ Sections', value: 68 },
    { signal: 'Tables', value: 58 },
    { signal: 'Headers', value: 85 },
    { signal: 'Word Count', value: 72 },
    { signal: 'Lists', value: 65 },
    { signal: 'Schema', value: 78 },
    { signal: 'Citations', value: 75 },
    { signal: 'Reading Level', value: 82 },
  ],
  gemini: [
    { signal: 'FAQ Sections', value: 62 },
    { signal: 'Tables', value: 55 },
    { signal: 'Headers', value: 80 },
    { signal: 'Word Count', value: 88 },
    { signal: 'Lists', value: 60 },
    { signal: 'Schema', value: 42 },
    { signal: 'Citations', value: 85 },
    { signal: 'Reading Level', value: 68 },
  ],
};

export const PLATFORM_INSIGHTS: Record<PlatformKey, string> = {
  chatgpt: "ChatGPT favors content with strong header hierarchy (88%) and external citations (82%). Your content's FAQ rate (20%) is well below ChatGPT's preference (72%).",
  claude: "Claude heavily weights word count (85%) and external citations (90%). It's less concerned with Schema markup (35%). Focus on depth and sourcing.",
  perplexity: "Perplexity strongly prefers external citations (88%) and list formatting (82%). FAQ sections (80%) are also highly valued. It rewards well-structured, reference-heavy content.",
  google_ai: "Google AI Mode weights Schema markup (78%) highest among all platforms. Headers (85%) and reading level accessibility (82%) are also key drivers.",
  gemini: "Gemini prioritizes word count depth (88%) and external citations (85%). It's the least Schema-dependent platform (42%). Long-form, well-cited content wins.",
};

// ─── Findings ────────────────────────────────────────────────────────────────

export interface Finding {
  id: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  dimension: string;
  affectedPages: number;
  fix: string;
  impact: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  pages: { url: string; score?: number }[];
  steps: string[];
  impactPoints: number;
}

const AFFECTED_PAGES_SNIPPET: { url: string; score: number }[] = [
  { url: '/blog/getting-started', score: 12 },
  { url: '/docs/api-reference', score: 18 },
  { url: '/blog/changelog-march', score: 8 },
  { url: '/docs/deployment', score: 22 },
  { url: '/blog/team-update', score: 15 },
  { url: '/docs/authentication', score: 19 },
  { url: '/blog/vibe-coding-intro', score: 11 },
  { url: '/docs/webhooks', score: 20 },
  { url: '/blog/ai-trends-2026', score: 14 },
  { url: '/docs/database-setup', score: 16 },
];

export const FINDINGS: Finding[] = [
  {
    id: 'f1',
    severity: 'critical',
    title: 'AEO snippet readiness < 25/100',
    dimension: 'Extractability',
    affectedPages: 62,
    fix: 'Add question headings + direct answers',
    impact: 'critical',
    description: 'These 62 pages have snippet readiness scores so low that AI engines cannot extract useful answers from them. Without extractable content, your pages are invisible to citation engines.',
    pages: AFFECTED_PAGES_SNIPPET,
    steps: [
      'Add question-format H2 headings that match user queries\n   Example: "How does AI handle patient phone calls?"',
      'Follow each question heading with a direct 2-3 sentence answer\n   The first sentence should directly answer the question.',
      'Add FAQ sections with 3-5 common questions per page\n   Use <details> or dedicated FAQ blocks.',
      'Include comparison tables where relevant\n   Side-by-side feature comparisons increase citation likelihood.',
      'Add key takeaways section at top or bottom\n   Summarize the 3-5 most important points.',
      'Ensure external citations link to authoritative sources\n   Reference studies, documentation, or industry reports.',
    ],
    impactPoints: 12,
  },
  {
    id: 'f2',
    severity: 'critical',
    title: 'Question-heading ratio < 30%',
    dimension: 'Extractability',
    affectedPages: 200,
    fix: 'Rephrase 30%+ headings as questions',
    impact: 'critical',
    description: 'Only 14.8% of headings across your site are phrased as questions. AI engines strongly prefer question-answer format for citations. This is the single largest gap in your AEO readiness.',
    pages: [
      { url: '/docs/api-reference' },
      { url: '/blog/getting-started' },
      { url: '/features/overview' },
      { url: '/docs/deployment' },
      { url: '/blog/best-practices' },
      { url: '/docs/authentication' },
      { url: '/features/collaboration' },
      { url: '/blog/product-roadmap' },
      { url: '/docs/database-setup' },
      { url: '/blog/ai-trends-2026' },
    ],
    steps: [
      'Identify declarative headings that could be rephrased as questions',
      'Convert "Installation Guide" \u2192 "How do I install Lovable?"',
      'Convert "API Authentication" \u2192 "How does API authentication work?"',
      'Ensure the paragraph immediately following answers the question directly',
      'Target at least 30% of all H2/H3 headings as questions',
    ],
    impactPoints: 8,
  },
  {
    id: 'f3',
    severity: 'high',
    title: 'Page has no H1 heading',
    dimension: 'On-Page SEO',
    affectedPages: 7,
    fix: 'Add exactly one H1 tag per page',
    impact: 'high',
    description: 'These 7 pages are missing an H1 heading entirely. Without an H1, AI engines cannot identify the primary topic of the page, reducing citation likelihood.',
    pages: [
      { url: '/blog/getting-started' },
      { url: '/docs/api-reference' },
      { url: '/blog/changelog-march' },
      { url: '/features/collaboration' },
      { url: '/pricing/enterprise' },
    ],
    steps: [
      'Audit each page to identify the primary topic',
      'Add a single, descriptive H1 tag at the top of the content area',
      'Ensure the H1 contains the primary keyword or question the page answers',
      'Verify no page has more than one H1 tag',
    ],
    impactPoints: 2,
  },
  {
    id: 'f4',
    severity: 'high',
    title: 'Missing Article/BlogPosting schema',
    dimension: 'Schema Markup',
    affectedPages: 28,
    fix: 'Add JSON-LD with headline, author, date',
    impact: 'high',
    description: 'Blog posts and articles are missing structured data markup. Adding Article or BlogPosting schema helps AI engines understand content type, authorship, and recency.',
    pages: [
      { url: '/blog/getting-started' },
      { url: '/blog/changelog-march' },
      { url: '/blog/team-update' },
      { url: '/blog/product-roadmap' },
      { url: '/blog/case-study-acme' },
    ],
    steps: [
      'Add JSON-LD script tags with Article or BlogPosting schema to each blog page',
      'Include headline, author, datePublished, and dateModified fields',
      'Add publisher information with logo',
      'Validate with Google Rich Results Test',
    ],
    impactPoints: 3,
  },
  {
    id: 'f5',
    severity: 'high',
    title: 'Title too long (>60 chars)',
    dimension: 'On-Page SEO',
    affectedPages: 87,
    fix: 'Shorten to 60 characters',
    impact: 'medium',
    description: 'Pages with titles longer than 60 characters get truncated in AI engine responses, reducing clarity and citation quality.',
    pages: [
      { url: '/docs/getting-started-with-lovable-platform-complete-guide' },
      { url: '/blog/how-to-build-production-apps-with-ai-comprehensive' },
      { url: '/features/real-time-collaboration-and-team-management' },
    ],
    steps: [
      'Audit all pages with titles exceeding 60 characters',
      'Rewrite titles to be concise yet descriptive within 60 characters',
      'Front-load the most important keywords',
      'Test truncation in search results preview tools',
    ],
    impactPoints: 1,
  },
  {
    id: 'f6',
    severity: 'high',
    title: 'Images missing alt text',
    dimension: 'On-Page SEO',
    affectedPages: 45,
    fix: 'Add descriptive alt text',
    impact: 'medium',
    description: 'Images without alt text reduce page accessibility and prevent AI engines from understanding visual content context.',
    pages: [
      { url: '/features/editor' },
      { url: '/blog/product-launch' },
      { url: '/docs/components' },
    ],
    steps: [
      'Identify all images missing alt attributes',
      'Write descriptive alt text that explains the image content',
      'Include relevant keywords naturally in alt text',
      'Avoid generic text like "image" or "screenshot"',
    ],
    impactPoints: 1,
  },
  {
    id: 'f7',
    severity: 'medium',
    title: 'Meta description too short (<120)',
    dimension: 'On-Page SEO',
    affectedPages: 84,
    fix: 'Expand to 120-160 characters',
    impact: 'low',
    description: 'Short meta descriptions provide insufficient context for AI engines to understand page content and relevance.',
    pages: [
      { url: '/features/editor' },
      { url: '/pricing' },
      { url: '/docs/quickstart' },
    ],
    steps: [
      'Review all pages with meta descriptions under 120 characters',
      'Expand descriptions to 120-160 characters',
      'Include the primary keyword and a clear value proposition',
      'Make each description unique and specific to the page',
    ],
    impactPoints: 1,
  },
  {
    id: 'f8',
    severity: 'medium',
    title: 'No FAQ schema on pages with FAQ content',
    dimension: 'Schema Markup',
    affectedPages: 15,
    fix: 'Add FAQPage JSON-LD',
    impact: 'medium',
    description: 'Pages that contain FAQ-style content lack FAQPage structured data, missing an opportunity for rich results and AI citations.',
    pages: [
      { url: '/docs/faq' },
      { url: '/pricing' },
      { url: '/support/common-questions' },
    ],
    steps: [
      'Identify all pages containing Q&A formatted content',
      'Add FAQPage JSON-LD schema with question/answer pairs',
      'Ensure questions match actual heading text',
      'Validate with Google Rich Results Test',
    ],
    impactPoints: 2,
  },
  {
    id: 'f9',
    severity: 'medium',
    title: 'Internal link depth > 3 clicks',
    dimension: 'Crawlability',
    affectedPages: 34,
    fix: 'Flatten site structure',
    impact: 'low',
    description: 'Pages buried more than 3 clicks deep from the homepage are less likely to be crawled by AI bots.',
    pages: [
      { url: '/docs/advanced/plugins/custom-auth' },
      { url: '/docs/guides/migration/v1-to-v2' },
      { url: '/blog/archive/2024/january/update' },
    ],
    steps: [
      'Map current site architecture to identify deep pages',
      'Add internal links from higher-level pages to deep content',
      'Create hub pages that link to related deep content',
      'Ensure all important pages are reachable within 3 clicks from homepage',
    ],
    impactPoints: 1,
  },
  {
    id: 'f10',
    severity: 'medium',
    title: 'Avg HTML size > 200KB',
    dimension: 'Performance',
    affectedPages: 23,
    fix: 'Remove unused scripts/styles',
    impact: 'low',
    description: 'Large HTML payloads slow down AI bot crawling and may cause incomplete page parsing.',
    pages: [
      { url: '/features/overview' },
      { url: '/docs/components' },
      { url: '/blog/comprehensive-guide' },
    ],
    steps: [
      'Audit pages with HTML size exceeding 200KB',
      'Remove unused CSS and JavaScript from page bundles',
      'Defer non-critical scripts',
      'Minify inline styles and scripts',
      'Consider lazy loading below-the-fold content',
    ],
    impactPoints: 1,
  },
  {
    id: 'f11',
    severity: 'low',
    title: 'No llms.txt file present',
    dimension: 'Crawlability',
    affectedPages: 1,
    fix: 'Create llms.txt with citation guidance',
    impact: 'medium',
    description: 'Your site lacks an llms.txt file. This emerging standard lets you communicate citation preferences directly to AI engines.',
    pages: [
      { url: '/ (root)' },
    ],
    steps: [
      'Create an llms.txt file in the root directory',
      'Include your brand name and preferred citation format',
      'List key pages you want AI engines to prioritize',
      'Add context about your expertise areas',
      'Reference the llms.txt specification for format guidelines',
    ],
    impactPoints: 1,
  },
  {
    id: 'f12',
    severity: 'low',
    title: 'External resources > 50 per page',
    dimension: 'Performance',
    affectedPages: 18,
    fix: 'Reduce third-party scripts',
    impact: 'low',
    description: 'Pages loading more than 50 external resources create dependency on third-party availability and slow bot crawling.',
    pages: [
      { url: '/features/overview' },
      { url: '/blog/product-launch' },
      { url: '/pricing' },
    ],
    steps: [
      'Audit external resource usage with Chrome DevTools Network tab',
      'Identify and remove unused third-party scripts',
      'Consolidate analytics and tracking scripts',
      'Self-host critical external resources where possible',
      'Use async/defer attributes for remaining external scripts',
    ],
    impactPoints: 1,
  },
];
