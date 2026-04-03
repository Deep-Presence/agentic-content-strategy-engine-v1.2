// ─── Competitive Position v2 — Mock Data ────────────────────────────────────

export interface Competitor {
  domain: string;
  name: string;
  type: 'direct' | 'mindshare' | 'authority';
  sov: number;
  citations: number;
  delta: number;
  winRate: number;
  trend: 'growing' | 'declining' | 'stable';
  interpretation: string;
}

export interface MindShareCompetitor {
  domain: string;
  name: string;
  type: 'mindshare';
  sov: number;
  citations: number;
  label: string;
}

export interface AuthoritySource {
  domain: string;
  name: string;
  type: 'authority';
  sov: number;
  citations: number;
  label: string;
}

export interface ClusterRanking {
  cluster: string;
  yourRank: number | null;
  yourShare: number;
  leaderDomain: string;
  leaderShare: number;
  gap: number | null;
  coverage: string;
  status: 'winning' | 'competitive' | 'losing';
  assessment: string;
}

export interface CitationAtRisk {
  query: string;
  status: 'lost' | 'at_risk' | 'stable' | 'never_had';
  competitor?: string;
  engine?: string;
  engines?: number;
  daysAgo?: number;
  detail?: string;
  reason?: string;
  yourContent?: {
    url: string;
    title: string;
    words: number;
    age: number;
  };
}

export interface Milestone {
  date: string;
  type: 'positive' | 'negative' | 'neutral';
  label: string;
  color: string;
}

export interface SOVDataPoint {
  date: string;
  you: number;
  'bolt.new': number;
  'cursor.com': number;
  'replit.com': number;
  'v0.dev': number;
  'emergent.sh': number;
}

// ─── Your Data ──────────────────────────────────────────────────────────────

export const YOUR_DATA = {
  domain: 'lovable.dev',
  name: 'Lovable',
  rank: 2,
  totalTracked: 14,
  sov: 12.4,
  sovStart: 8.1,
  citations: 847,
  winRate: 39,
  atRisk: 4,
  lost: 3,
  growthDirection: 'gaining' as const,
  growthDelta: 3.2,
  previousRank: 4,
};

// ─── Direct Competitors ─────────────────────────────────────────────────────

export const COMPETITORS: Competitor[] = [
  { domain: 'bolt.new', name: 'Bolt.new', type: 'direct', sov: 18.2, citations: 1420, delta: -0.8, winRate: 22, trend: 'declining', interpretation: 'Bolt.new dominates overall — focus on differentiation, not head-to-head competition' },
  { domain: 'cursor.com', name: 'Cursor', type: 'direct', sov: 11.8, citations: 921, delta: 1.2, winRate: 38, trend: 'growing', interpretation: 'Cursor beats you on developer-focused queries — strengthen technical content' },
  { domain: 'replit.com', name: 'Replit', type: 'direct', sov: 9.1, citations: 710, delta: -2.1, winRate: 52, trend: 'declining', interpretation: 'Evenly matched — look for advantages in security and enterprise queries' },
  { domain: 'v0.dev', name: 'V0.dev', type: 'direct', sov: 7.3, citations: 571, delta: 0.9, winRate: 68, trend: 'stable', interpretation: 'You win most matchups against V0.dev — strong position to maintain' },
  { domain: 'emergent.sh', name: 'Emergent', type: 'direct', sov: 5.2, citations: 406, delta: 3.1, winRate: 15, trend: 'growing', interpretation: 'Emergent is gaining fast — defend your position in Mechanism cluster' },
  { domain: 'retool.com', name: 'Retool', type: 'direct', sov: 4.8, citations: 375, delta: 0.4, winRate: 45, trend: 'stable', interpretation: 'Close matchup — Retool competes on enterprise integration queries' },
];

// ─── Mind Share Competitors ─────────────────────────────────────────────────

export const MINDSHARE: MindShareCompetitor[] = [
  { domain: 'g2.com', name: 'G2', type: 'mindshare', sov: 3.2, citations: 249, label: 'Review aggregator' },
  { domain: 'producthunt.com', name: 'Product Hunt', type: 'mindshare', sov: 2.1, citations: 164, label: 'Product directory' },
  { domain: 'techcrunch.com', name: 'TechCrunch', type: 'mindshare', sov: 1.8, citations: 140, label: 'Tech news' },
  { domain: 'forbes.com', name: 'Forbes', type: 'mindshare', sov: 1.4, citations: 109, label: 'Business media' },
  { domain: 'capterra.com', name: 'Capterra', type: 'mindshare', sov: 1.2, citations: 94, label: 'Software comparison' },
];

// ─── Authority Sources ──────────────────────────────────────────────────────

export const AUTHORITY: AuthoritySource[] = [
  { domain: 'cms.gov', name: 'CMS.gov', type: 'authority', sov: 4.4, citations: 343, label: 'Government' },
  { domain: 'owasp.org', name: 'OWASP', type: 'authority', sov: 2.8, citations: 218, label: 'Security standards' },
  { domain: 'arxiv.org', name: 'arXiv', type: 'authority', sov: 2.1, citations: 164, label: 'Research papers' },
  { domain: 'hhs.gov', name: 'HHS.gov', type: 'authority', sov: 1.9, citations: 148, label: 'Government' },
  { domain: 'nature.com', name: 'Nature', type: 'authority', sov: 1.7, citations: 132, label: 'Research journal' },
];

// ─── Cluster Rankings ───────────────────────────────────────────────────────

export const CLUSTER_RANKINGS: ClusterRanking[] = [
  { cluster: 'Branded Evaluation', yourRank: 1, yourShare: 4.5, leaderDomain: 'bolt.new', leaderShare: 3.8, gap: 0.7, coverage: '13/17', status: 'winning', assessment: 'Strong position — defend with fresh content' },
  { cluster: 'Boundary', yourRank: 1, yourShare: 1.6, leaderDomain: 'censinet.com', leaderShare: 1.4, gap: 0.2, coverage: '8/16', status: 'winning', assessment: 'Narrow lead — competitors are close' },
  { cluster: 'Mechanism', yourRank: 3, yourShare: 1.2, leaderDomain: 'emergent.sh', leaderShare: 2.8, gap: -1.6, coverage: '12/16', status: 'competitive', assessment: 'Focus on technical deep-dives to climb' },
  { cluster: 'Feature Verification', yourRank: 5, yourShare: 0.6, leaderDomain: 'knack.com', leaderShare: 2.1, gap: -1.5, coverage: '10/15', status: 'competitive', assessment: 'Good coverage, need stronger content quality' },
  { cluster: 'Category Comparison', yourRank: 4, yourShare: 0.8, leaderDomain: 'cursor.com', leaderShare: 5.2, gap: -4.4, coverage: '6/14', status: 'competitive', assessment: 'Focus on comparison content to climb' },
  { cluster: 'Definition', yourRank: 6, yourShare: 0.5, leaderDomain: 'designrev.com', leaderShare: 2.4, gap: -1.9, coverage: '3/12', status: 'losing', assessment: 'Major gap — need 9 new content pieces' },
  { cluster: 'Decision Criteria', yourRank: 8, yourShare: 0.2, leaderDomain: 'alloy.app', leaderShare: 2.8, gap: -2.6, coverage: '4/15', status: 'losing', assessment: 'Major gap — need 11 new content pieces' },
  { cluster: 'Problem/Awareness', yourRank: null, yourShare: 0, leaderDomain: 'cms.gov', leaderShare: 4.4, gap: null, coverage: '0/16', status: 'losing', assessment: 'Enter with practitioner guides, not reference content' },
  { cluster: 'Best-of/Consideration', yourRank: null, yourShare: 0, leaderDomain: 'rocket.new', leaderShare: 3.2, gap: null, coverage: '0/14', status: 'losing', assessment: 'Comparison and evaluation content needed' },
];

// ─── Citations at Risk ──────────────────────────────────────────────────────

export const CITATIONS_AT_RISK: CitationAtRisk[] = [
  {
    query: 'vibe coding meaning',
    status: 'lost',
    competitor: 'cursor.com',
    engine: 'ChatGPT',
    daysAgo: 3,
    reason: 'cursor.com published a new guide (2,800 words, FAQ, comparison tables)',
    yourContent: { url: 'lovable.dev/blog/vibe-coding-enterprise', title: 'Vibe Coding for Enterprise Teams', words: 2100, age: 71 },
  },
  {
    query: 'AI code generation security risks',
    status: 'lost',
    competitor: 'snyk.io',
    engine: 'Claude',
    daysAgo: 5,
    reason: "snyk.io's content has stronger structural signals (FAQ, headers, schema)",
    yourContent: { url: 'lovable.dev/blog/security-ai-apps', title: 'Security in AI-Generated Apps', words: 1800, age: 73 },
  },
  {
    query: 'enterprise AI app builder features',
    status: 'lost',
    competitor: 'retool.com',
    engine: 'Gemini',
    daysAgo: 7,
    reason: 'retool.com expanded their comparison page from 1,800 to 3,200 words',
    yourContent: { url: 'lovable.dev/blog/enterprise-features', title: 'Enterprise Features Guide', words: 1600, age: 45 },
  },
  {
    query: 'no-code AI app security audit',
    status: 'at_risk',
    engine: 'Perplexity',
    detail: 'Your position dropped from #1 to #3',
    reason: 'Competitor content improving — 2 new pages published this week',
  },
  {
    query: 'how to deploy AI-generated app to production',
    status: 'at_risk',
    competitor: 'cursor.com',
    engine: 'Google AI',
    detail: 'Cited intermittently (3 of last 7 days)',
    reason: 'cursor.com and replit.com competing for this query',
  },
  {
    query: 'prompt-to-app platform comparison',
    status: 'at_risk',
    engine: 'ChatGPT',
    detail: 'Position weakening (was #2, now #4)',
    reason: '3 new competitor pages published in this space',
  },
  {
    query: 'bolt.new vs lovable comparison',
    status: 'stable',
    detail: 'Stable across 3 platforms for 14+ days',
  },
  {
    query: 'best AI app builder for startups',
    status: 'stable',
    detail: 'Stable across 2 platforms for 21+ days',
  },
  {
    query: 'lovable AI app builder review',
    status: 'stable',
    detail: 'Stable across 4 platforms for 28+ days',
  },
  {
    query: 'AI app builder data privacy',
    status: 'never_had',
    competitor: 'owasp.org',
    engines: 4,
    reason: 'You have no competing content',
  },
  {
    query: 'RBAC in AI-generated applications',
    status: 'never_had',
    competitor: 'auth0.com',
    engines: 3,
    reason: 'Your existing content scores below citation threshold',
  },
];

// ─── SOV Trend (28 days) ────────────────────────────────────────────────────

function generateSOVTrend(): SOVDataPoint[] {
  const points: SOVDataPoint[] = [];
  const startDate = new Date(2026, 2, 1); // March 1, 2026

  // Define start/end SOV for each brand
  const trends = {
    you: { start: 8.1, end: 12.4 },
    'bolt.new': { start: 18.5, end: 17.1 },
    'cursor.com': { start: 11.5, end: 11.8 },
    'replit.com': { start: 9.5, end: 8.8 },
    'v0.dev': { start: 7.1, end: 7.4 },
    'emergent.sh': { start: 5.0, end: 5.3 },
  };

  for (let i = 0; i < 28; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    const t = i / 27;
    const noise = () => (Math.random() - 0.5) * 0.6;

    const dateStr = `Mar ${date.getDate()}`;

    points.push({
      date: dateStr,
      you: +(trends.you.start + (trends.you.end - trends.you.start) * t + noise()).toFixed(1),
      'bolt.new': +(trends['bolt.new'].start + (trends['bolt.new'].end - trends['bolt.new'].start) * t + noise()).toFixed(1),
      'cursor.com': +(trends['cursor.com'].start + (trends['cursor.com'].end - trends['cursor.com'].start) * t + noise()).toFixed(1),
      'replit.com': +(trends['replit.com'].start + (trends['replit.com'].end - trends['replit.com'].start) * t + noise()).toFixed(1),
      'v0.dev': +(trends['v0.dev'].start + (trends['v0.dev'].end - trends['v0.dev'].start) * t + noise()).toFixed(1),
      'emergent.sh': +(trends['emergent.sh'].start + (trends['emergent.sh'].end - trends['emergent.sh'].start) * t + noise()).toFixed(1),
    });
  }

  return points;
}

export const SOV_TREND = generateSOVTrend();

// ─── Milestones ─────────────────────────────────────────────────────────────

export const MILESTONES: Milestone[] = [
  { date: 'Mar 5', type: 'positive', label: 'Published: Vibe Coding Guide', color: '#34B27B' },
  { date: 'Mar 12', type: 'positive', label: '+3 new ChatGPT citations', color: '#34B27B' },
  { date: 'Mar 18', type: 'negative', label: "Lost 'vibe coding meaning' to cursor.com", color: '#E5484D' },
  { date: 'Mar 23', type: 'neutral', label: 'Perplexity started citing Enterprise guide', color: '#6CB8D2' },
];

// ─── Competitor Detail (for drawers) ────────────────────────────────────────

export interface CompetitorDetail {
  domain: string;
  winRate: number;
  totalShared: number;
  queriesYouWin: { query: string; platforms: string[] }[];
  queriesYouLose: { query: string; platforms: string[]; competitorCitations: number }[];
  whyTheyWin: string[];
  howToClose: { action: string; impact: string }[];
}

export const COMPETITOR_DETAILS: Record<string, CompetitorDetail> = {
  'bolt.new': {
    domain: 'bolt.new',
    winRate: 22,
    totalShared: 14,
    queriesYouWin: [
      { query: 'lovable vs bolt.new comparison', platforms: ['ChatGPT', 'Claude'] },
      { query: 'lovable pricing vs bolt.new', platforms: ['Perplexity'] },
      { query: 'AI app builder for non-technical teams', platforms: ['Claude', 'Google AI'] },
    ],
    queriesYouLose: [
      { query: 'best AI app builder 2026', platforms: ['ChatGPT', 'Claude', 'Perplexity', 'Gemini'], competitorCitations: 4 },
      { query: 'no-code app builder features', platforms: ['ChatGPT', 'Perplexity', 'Gemini'], competitorCitations: 3 },
      { query: 'AI app builder pricing', platforms: ['ChatGPT', 'Claude', 'Gemini'], competitorCitations: 3 },
      { query: 'vibe coding tools comparison', platforms: ['ChatGPT', 'Perplexity'], competitorCitations: 2 },
      { query: 'rapid prototyping AI tools', platforms: ['Claude', 'Google AI'], competitorCitations: 2 },
    ],
    whyTheyWin: [
      'They have 2.3x more content pages in the Competitive Landscape cluster',
      'Their content averages 2,400 words vs your 1,800 words',
      '85% of their pages have FAQ sections vs 20% of yours',
      'They rank #1 on ChatGPT for 6 of 14 shared queries',
    ],
    howToClose: [
      { action: 'Add FAQ sections to your top 5 pages', impact: 'estimated +12% win rate' },
      { action: 'Create content for 3 uncovered queries', impact: 'estimated +8% win rate' },
      { action: 'Expand word count on comparison pages to 2,500+ words', impact: 'estimated +5% win rate' },
    ],
  },
  'cursor.com': {
    domain: 'cursor.com',
    winRate: 38,
    totalShared: 11,
    queriesYouWin: [
      { query: 'lovable vs cursor for non-developers', platforms: ['ChatGPT', 'Perplexity'] },
      { query: 'no-code AI app builder', platforms: ['Claude'] },
      { query: 'AI app builder for startups', platforms: ['ChatGPT', 'Perplexity'] },
      { query: 'visual AI app development', platforms: ['Google AI'] },
    ],
    queriesYouLose: [
      { query: 'best AI coding assistant 2026', platforms: ['ChatGPT', 'Claude', 'Gemini'], competitorCitations: 3 },
      { query: 'AI code generation security', platforms: ['Claude', 'Perplexity'], competitorCitations: 2 },
      { query: 'developer AI tools comparison', platforms: ['ChatGPT', 'Claude', 'Perplexity', 'Google AI'], competitorCitations: 4 },
      { query: 'vibe coding meaning', platforms: ['ChatGPT'], competitorCitations: 1 },
    ],
    whyTheyWin: [
      'Cursor has stronger developer credibility — their content targets engineers directly',
      'Their pages load faster (avg 1.2s vs your 2.8s) which AI crawlers prefer',
      '92% of their pages have structured data vs 35% of yours',
      'They publish 3x more frequently in the developer tools space',
    ],
    howToClose: [
      { action: 'Add structured data (FAQ, HowTo schema) to top 10 pages', impact: 'estimated +15% win rate' },
      { action: 'Create developer-focused comparison content', impact: 'estimated +10% win rate' },
      { action: 'Improve page load speed to under 2 seconds', impact: 'estimated +5% win rate' },
    ],
  },
  'replit.com': {
    domain: 'replit.com',
    winRate: 52,
    totalShared: 9,
    queriesYouWin: [
      { query: 'lovable vs replit', platforms: ['ChatGPT', 'Claude'] },
      { query: 'AI app builder for businesses', platforms: ['Perplexity', 'Google AI'] },
      { query: 'no-code deployment tools', platforms: ['Claude'] },
      { query: 'AI app builder security features', platforms: ['ChatGPT', 'Claude'] },
      { query: 'enterprise no-code platform', platforms: ['Google AI'] },
    ],
    queriesYouLose: [
      { query: 'online IDE AI features', platforms: ['ChatGPT', 'Claude', 'Perplexity'], competitorCitations: 3 },
      { query: 'collaborative coding AI', platforms: ['ChatGPT', 'Claude'], competitorCitations: 2 },
      { query: 'learn to code with AI', platforms: ['ChatGPT', 'Perplexity', 'Gemini', 'Google AI'], competitorCitations: 4 },
    ],
    whyTheyWin: [
      'Replit has established brand presence in education and learning-to-code space',
      'Their community-generated content creates organic citation signals',
      'They have 4x more indexed pages in educational content clusters',
    ],
    howToClose: [
      { action: 'Create tutorial-style content for beginners', impact: 'estimated +10% win rate' },
      { action: 'Build comparison pages for education use cases', impact: 'estimated +8% win rate' },
    ],
  },
  'v0.dev': {
    domain: 'v0.dev',
    winRate: 68,
    totalShared: 8,
    queriesYouWin: [
      { query: 'AI app builder full stack', platforms: ['ChatGPT', 'Claude', 'Perplexity'] },
      { query: 'lovable vs v0', platforms: ['ChatGPT', 'Claude'] },
      { query: 'AI prototype to production', platforms: ['Perplexity', 'Google AI'] },
      { query: 'no-code backend AI', platforms: ['Claude'] },
      { query: 'AI app builder with database', platforms: ['ChatGPT', 'Perplexity'] },
    ],
    queriesYouLose: [
      { query: 'AI UI component generator', platforms: ['ChatGPT', 'Claude'], competitorCitations: 2 },
      { query: 'vercel AI tools', platforms: ['ChatGPT', 'Perplexity', 'Gemini'], competitorCitations: 3 },
    ],
    whyTheyWin: [
      'V0.dev is closely associated with Vercel — they benefit from ecosystem citations',
      'Their UI-specific content is more targeted than your broader positioning',
    ],
    howToClose: [
      { action: 'Create dedicated UI generation comparison content', impact: 'estimated +5% win rate' },
      { action: 'Highlight full-stack advantage vs UI-only tools', impact: 'estimated +8% win rate' },
    ],
  },
  'emergent.sh': {
    domain: 'emergent.sh',
    winRate: 15,
    totalShared: 7,
    queriesYouWin: [
      { query: 'AI app builder comparison 2026', platforms: ['Perplexity'] },
    ],
    queriesYouLose: [
      { query: 'AI mechanism design tools', platforms: ['ChatGPT', 'Claude', 'Perplexity'], competitorCitations: 3 },
      { query: 'automated AI code review', platforms: ['Claude', 'Gemini'], competitorCitations: 2 },
      { query: 'AI-driven software architecture', platforms: ['ChatGPT', 'Claude'], competitorCitations: 2 },
      { query: 'AI for technical debt analysis', platforms: ['ChatGPT', 'Perplexity', 'Google AI'], competitorCitations: 3 },
      { query: 'enterprise AI code generation', platforms: ['Claude'], competitorCitations: 1 },
    ],
    whyTheyWin: [
      'Emergent has deep technical content that resonates with AI engines',
      'They publish weekly research papers that get heavily cited',
      'Their content covers mechanism design — a cluster you have zero presence in',
      'Growth rate of +3.1 points this month is the fastest in your space',
    ],
    howToClose: [
      { action: 'Enter the Mechanism cluster with 3 technical deep-dives', impact: 'estimated +20% win rate' },
      { action: 'Publish technical comparisons showing full-stack advantage', impact: 'estimated +10% win rate' },
      { action: 'Create a monthly research roundup to build authority', impact: 'estimated +5% win rate' },
    ],
  },
  'retool.com': {
    domain: 'retool.com',
    winRate: 45,
    totalShared: 10,
    queriesYouWin: [
      { query: 'AI app builder for startups', platforms: ['ChatGPT', 'Perplexity'] },
      { query: 'lovable vs retool', platforms: ['ChatGPT', 'Claude'] },
      { query: 'no-code AI prototyping', platforms: ['Claude', 'Google AI'] },
      { query: 'AI app builder pricing comparison', platforms: ['Perplexity'] },
    ],
    queriesYouLose: [
      { query: 'enterprise internal tools AI', platforms: ['ChatGPT', 'Claude', 'Perplexity', 'Gemini'], competitorCitations: 4 },
      { query: 'AI app builder enterprise features', platforms: ['Claude', 'Gemini'], competitorCitations: 2 },
      { query: 'no-code enterprise platform', platforms: ['ChatGPT', 'Perplexity', 'Google AI'], competitorCitations: 3 },
      { query: 'internal tools development AI', platforms: ['ChatGPT', 'Claude'], competitorCitations: 2 },
    ],
    whyTheyWin: [
      'Retool owns the "internal tools" narrative — deeply established positioning',
      'Their enterprise case studies are 3x more detailed than yours',
      'They have dedicated landing pages for every enterprise use case',
    ],
    howToClose: [
      { action: 'Create enterprise case studies with specific metrics', impact: 'estimated +12% win rate' },
      { action: 'Build landing pages for top 5 enterprise use cases', impact: 'estimated +8% win rate' },
      { action: 'Add ROI calculators and comparison tables', impact: 'estimated +5% win rate' },
    ],
  },
};

// ─── Cluster Detail (for drawers) ───────────────────────────────────────────

export interface ClusterQuery {
  query: string;
  topCited: { domain: string; platforms: string[] }[];
  yourContent: string | null;
  gap: number;
}

export interface ClusterDetail {
  cluster: string;
  totalCitations: number;
  totalDomains: number;
  queries: ClusterQuery[];
  dominators: {
    direct: { domain: string; citations: number }[];
    mindshare: { domain: string; citations: number }[];
    authority: { domain: string; citations: number }[];
  };
  strategy: string;
}

export const CLUSTER_DETAILS: Record<string, ClusterDetail> = {
  'Problem/Awareness': {
    cluster: 'Problem/Awareness',
    totalCitations: 229,
    totalDomains: 159,
    queries: [
      { query: 'How to improve HCC risk adjustment accuracy?', topCited: [{ domain: 'healthcatalyst.com', platforms: ['ChatGPT', 'Claude'] }, { domain: 'cms.gov', platforms: ['Gemini', 'Perplexity'] }], yourContent: null, gap: 26.7 },
      { query: 'How to operationalize SDoH data for interventions?', topCited: [{ domain: 'innovaccer.com', platforms: ['ChatGPT', 'Perplexity'] }, { domain: 'nature.com', platforms: ['Claude'] }], yourContent: null, gap: 25.9 },
      { query: 'What are the challenges of AI in healthcare?', topCited: [{ domain: 'nature.com', platforms: ['Claude', 'Perplexity'] }, { domain: 'cms.gov', platforms: ['Google AI'] }], yourContent: null, gap: 22.1 },
    ],
    dominators: {
      direct: [{ domain: 'healthcatalyst.com', citations: 9 }, { domain: 'innovaccer.com', citations: 5 }],
      mindshare: [{ domain: 'aafp.org', citations: 4 }, { domain: 'springer.com', citations: 4 }, { domain: 'nature.com', citations: 3 }],
      authority: [{ domain: 'cms.gov', citations: 10 }, { domain: 'cdc.gov', citations: 8 }, { domain: 'ahrq.gov', citations: 4 }],
    },
    strategy: "This cluster is dominated by government and institutional sources (50%). Don't compete with cms.gov on reference content. Instead, create practitioner-focused implementation guides that AI engines will cite alongside the authoritative sources. Target content: \"How-to\" and \"Guide\" formats, 2000+ words, FAQ sections.",
  },
  'Best-of/Consideration': {
    cluster: 'Best-of/Consideration',
    totalCitations: 185,
    totalDomains: 120,
    queries: [
      { query: 'Best AI app builders in 2026', topCited: [{ domain: 'rocket.new', platforms: ['ChatGPT', 'Claude'] }, { domain: 'g2.com', platforms: ['Perplexity'] }], yourContent: null, gap: 28.3 },
      { query: 'Top no-code platforms for startups', topCited: [{ domain: 'capterra.com', platforms: ['ChatGPT', 'Perplexity'] }, { domain: 'producthunt.com', platforms: ['Claude'] }], yourContent: null, gap: 24.1 },
    ],
    dominators: {
      direct: [{ domain: 'rocket.new', citations: 8 }, { domain: 'bolt.new', citations: 6 }],
      mindshare: [{ domain: 'g2.com', citations: 7 }, { domain: 'capterra.com', citations: 5 }, { domain: 'producthunt.com', citations: 4 }],
      authority: [{ domain: 'techcrunch.com', citations: 3 }],
    },
    strategy: "This cluster is dominated by review aggregators and comparison sites. You need to be listed and well-reviewed on G2, Capterra, and Product Hunt. Create your own comparison pages and \"best of\" roundups that position you favorably. Target content: comparison tables, feature matrices, pricing breakdowns.",
  },
};

// ─── Filter Options ─────────────────────────────────────────────────────────

export const clusterOptions = [
  { value: 'all', label: 'All Clusters' },
  ...CLUSTER_RANKINGS.map((c) => ({ value: c.cluster, label: c.cluster })),
];

export const platformOptions = [
  { value: 'all', label: 'All Platforms' },
  { value: 'chatgpt', label: 'ChatGPT' },
  { value: 'claude', label: 'Claude' },
  { value: 'perplexity', label: 'Perplexity' },
  { value: 'google_ai', label: 'Google AI' },
  { value: 'gemini', label: 'Gemini' },
];

// ─── Engine domain mapping ──────────────────────────────────────────────────

export const ENGINE_DOMAINS: Record<string, string> = {
  ChatGPT: 'openai.com',
  Claude: 'anthropic.com',
  Perplexity: 'perplexity.ai',
  'Google AI': 'google.com',
  Gemini: 'gemini.google.com',
};
