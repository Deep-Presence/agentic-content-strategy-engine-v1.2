// ─── Mock Data for Competitive Position Page ─────────────────────────────────
// Exact data from AGENT-COMPETITIVE-POSITION spec. Structured for easy API swap-in.

// ─── Platform Domains ────────────────────────────────────────────────────────

export const PLATFORM_DOMAINS: Record<string, string> = {
  chatgpt: 'openai.com',
  claude: 'anthropic.com',
  perplexity: 'perplexity.ai',
  google_ai: 'google.com',
  gemini: 'gemini.google.com',
  ChatGPT: 'openai.com',
  Claude: 'anthropic.com',
  Perplexity: 'perplexity.ai',
  'Google AI': 'google.com',
  Gemini: 'gemini.google.com',
};

// ─── Head-to-Head Daily SOV (28 days) ────────────────────────────────────────

export interface BattleDataPoint {
  date: string;
  'lovable.dev': number;
  'bolt.new': number;
  'cursor.com': number;
  'replit.com': number;
  'v0.dev': number;
}

export function generateBattleData(): BattleDataPoint[] {
  const data: BattleDataPoint[] = [];
  const startDate = new Date('2026-02-28');
  for (let i = 0; i < 28; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    data.push({
      date: date.toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' }),
      'lovable.dev': +(8.1 + i * 0.16 + (Math.sin(i * 1.7) * 0.6)).toFixed(1),
      'bolt.new': +(18.2 - i * 0.04 + (Math.sin(i * 1.3) * 0.5)).toFixed(1),
      'cursor.com': +(11.8 + i * 0.02 + (Math.sin(i * 2.1) * 0.4)).toFixed(1),
      'replit.com': +(9.1 - i * 0.03 + (Math.sin(i * 0.9) * 0.3)).toFixed(1),
      'v0.dev': +(7.0 + i * 0.05 + (Math.sin(i * 1.5) * 0.35)).toFixed(1),
    });
  }
  return data;
}

// Pre-generate once for stable renders
export const battleData = generateBattleData();

// ─── Win Rate Data ───────────────────────────────────────────────────────────

export interface WinRateEntry {
  domain: string;
  rate: number;
}

export const WIN_RATES: WinRateEntry[] = [
  { domain: 'v0.dev', rate: 0.68 },
  { domain: 'replit.com', rate: 0.52 },
  { domain: 'cursor.com', rate: 0.38 },
  { domain: 'bolt.new', rate: 0.22 },
  { domain: 'emergent.sh', rate: 0.15 },
];

// ─── Gap Trend (8 weeks) ─────────────────────────────────────────────────────

export interface GapTrendPoint {
  week: string;
  gap: number;
}

export const GAP_TREND: GapTrendPoint[] = [
  { week: 'Jan 26', gap: -7.9 },
  { week: 'Feb 2', gap: -7.5 },
  { week: 'Feb 9', gap: -7.1 },
  { week: 'Feb 16', gap: -6.8 },
  { week: 'Feb 23', gap: -6.5 },
  { week: 'Mar 2', gap: -6.2 },
  { week: 'Mar 9', gap: -6.0 },
  { week: 'Mar 16', gap: -5.8 },
];

// ─── Cluster SOV Data ────────────────────────────────────────────────────────

export interface ClusterSOV {
  cluster: string;
  you: number;
  comp: number;
  compDomain: string;
  action: 'defend' | 'close_gap' | 'invest' | 'priority';
}

export const CLUSTER_SOV: ClusterSOV[] = [
  { cluster: 'Branded Evaluation', you: 72, comp: 68, compDomain: 'bolt.new', action: 'defend' },
  { cluster: 'Category Comparison', you: 58, comp: 71, compDomain: 'cursor.com', action: 'close_gap' },
  { cluster: 'Mechanism', you: 45, comp: 67, compDomain: 'emergent.sh', action: 'invest' },
  { cluster: 'Boundary', you: 38, comp: 62, compDomain: 'snyk.io', action: 'invest' },
  { cluster: 'Definition', you: 34, comp: 55, compDomain: 'designrev.com', action: 'invest' },
  { cluster: 'Feature Verification', you: 31, comp: 48, compDomain: 'knack.com', action: 'invest' },
  { cluster: 'Decision Criteria', you: 28, comp: 52, compDomain: 'alloy.app', action: 'priority' },
  { cluster: 'Problem/Awareness', you: 25, comp: 45, compDomain: 'dev.to', action: 'priority' },
  { cluster: 'Best-of/Consideration', you: 18, comp: 58, compDomain: 'rocket.new', action: 'priority' },
];

// ─── Citation Drift Tracker ──────────────────────────────────────────────────

export type DriftStatus = 'lost' | 'at_risk' | 'stable' | 'never_had';

export interface DriftEntry {
  id: string;
  query: string;
  drift: number;
  tookOver: string | null;
  lostOn: string | null;
  status: DriftStatus;
}

export const DRIFT_DATA: DriftEntry[] = [
  { id: 'd1', query: 'vibe coding meaning', drift: 0.22, tookOver: 'cursor.com', lostOn: 'ChatGPT', status: 'lost' },
  { id: 'd2', query: 'AI code generation security risks', drift: 0.18, tookOver: 'snyk.io', lostOn: 'Claude', status: 'lost' },
  { id: 'd3', query: 'enterprise AI app builder features', drift: 0.15, tookOver: 'retool.com', lostOn: 'Gemini', status: 'lost' },
  { id: 'd4', query: 'no-code AI app security audit', drift: 0.11, tookOver: null, lostOn: null, status: 'at_risk' },
  { id: 'd5', query: 'how to deploy AI-generated app to prod', drift: 0.08, tookOver: null, lostOn: null, status: 'at_risk' },
  { id: 'd6', query: 'prompt-to-app platform comparison', drift: 0.05, tookOver: null, lostOn: null, status: 'at_risk' },
  { id: 'd7', query: 'bolt.new vs lovable comparison', drift: 0.03, tookOver: null, lostOn: null, status: 'stable' },
  { id: 'd8', query: 'best AI app builder for startups', drift: 0.01, tookOver: null, lostOn: null, status: 'stable' },
  { id: 'd9', query: 'AI app builder data privacy', drift: 0.19, tookOver: 'owasp.org', lostOn: null, status: 'never_had' },
  { id: 'd10', query: 'RBAC in AI-generated applications', drift: 0.12, tookOver: 'auth0.com', lostOn: null, status: 'never_had' },
];

const STATUS_ORDER: Record<DriftStatus, number> = { lost: 0, at_risk: 1, stable: 2, never_had: 3 };

export const sortedDriftData = [...DRIFT_DATA].sort((a, b) => {
  const so = STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
  if (so !== 0) return so;
  return b.drift - a.drift;
});

// ─── Most-Cited Competitor URLs ──────────────────────────────────────────────

export interface CompetitorURL {
  url: string;
  domain: string;
  influence: number;
  platforms: string[];
  overlap: string;
  overlapRatio: number;
}

export const MOST_CITED_URLS: CompetitorURL[] = [
  { url: 'bolt.new/blog/ai-app-security', domain: 'bolt.new', influence: 81, platforms: ['chatgpt', 'perplexity'], overlap: '2/6', overlapRatio: 0.33 },
  { url: 'cursor.com/docs/enterprise-features', domain: 'cursor.com', influence: 74, platforms: ['claude', 'chatgpt', 'perplexity'], overlap: '1/5', overlapRatio: 0.20 },
  { url: 'owasp.org/ai-security-guide', domain: 'owasp.org', influence: 72, platforms: ['chatgpt', 'claude', 'perplexity'], overlap: '0/3', overlapRatio: 0.00 },
  { url: 'snyk.io/learn/ai-code-security', domain: 'snyk.io', influence: 68, platforms: ['chatgpt', 'claude', 'google_ai'], overlap: '0/4', overlapRatio: 0.00 },
  { url: 'replit.com/blog/vibe-coding-guide', domain: 'replit.com', influence: 65, platforms: ['perplexity', 'gemini'], overlap: '3/7', overlapRatio: 0.43 },
  { url: 'auth0.com/blog/rbac-best-practices', domain: 'auth0.com', influence: 62, platforms: ['chatgpt', 'claude'], overlap: '0/3', overlapRatio: 0.00 },
  { url: 'dev.to/t/ai-app-builders', domain: 'dev.to', influence: 59, platforms: ['perplexity'], overlap: '1/4', overlapRatio: 0.25 },
  { url: 'retool.com/blog/ai-app-builder-comparison', domain: 'retool.com', influence: 55, platforms: ['google_ai', 'chatgpt'], overlap: '2/5', overlapRatio: 0.40 },
];

// ─── Filter Options ──────────────────────────────────────────────────────────

export const clusterOptions = [
  { value: 'all', label: 'All Clusters' },
  { value: 'branded-evaluation', label: 'Branded Evaluation' },
  { value: 'category-comparison', label: 'Category Comparison' },
  { value: 'mechanism', label: 'Mechanism' },
  { value: 'boundary', label: 'Boundary' },
  { value: 'definition', label: 'Definition' },
  { value: 'feature-verification', label: 'Feature Verification' },
  { value: 'decision-criteria', label: 'Decision Criteria' },
  { value: 'problem-awareness', label: 'Problem/Awareness' },
  { value: 'best-of-consideration', label: 'Best-of/Consideration' },
];

export const platformOptions = [
  { value: 'all', label: 'All Platforms' },
  { value: 'chatgpt', label: 'ChatGPT' },
  { value: 'claude', label: 'Claude' },
  { value: 'perplexity', label: 'Perplexity' },
  { value: 'google_ai', label: 'Google AI' },
  { value: 'gemini', label: 'Gemini' },
];

// ─── Competitor Drawer Data ──────────────────────────────────────────────────

export interface CompetitorDetailData {
  domain: string;
  sovByClusters: { cluster: string; them: number; you: number }[];
  topURLs: { url: string; citations: number; platforms: string[] }[];
  structuralComparison: { signal: string; theirAvg: string; yourAvg: string; gap: string; gapDirection: 'behind' | 'ahead' | 'neutral' }[];
  trajectory: { date: string; citations: number }[];
  threatScore: 'HIGH' | 'MEDIUM' | 'LOW';
  threatSummary: string[];
  contentVelocity: string;
}

export function getCompetitorDetail(domain: string): CompetitorDetailData {
  const clusters = CLUSTER_SOV.filter((c) => c.compDomain === domain).map((c) => ({
    cluster: c.cluster,
    them: c.comp,
    you: c.you,
  }));

  // If no direct clusters, show all with estimated values
  const sovClusters = clusters.length > 0
    ? clusters
    : CLUSTER_SOV.map((c) => ({
        cluster: c.cluster,
        them: Math.floor(Math.sin(c.you * 0.1 + domain.length) * 15 + 40),
        you: c.you,
      }));

  const threatScore: 'HIGH' | 'MEDIUM' | 'LOW' = domain === 'bolt.new' ? 'HIGH' : domain === 'cursor.com' ? 'HIGH' : 'MEDIUM';
  const piecesCount = domain === 'bolt.new' ? 4 : domain === 'cursor.com' ? 3 : 1;
  const defendCount = domain === 'bolt.new' ? 2 : domain === 'cursor.com' ? 1 : 0;

  return {
    domain,
    sovByClusters: sovClusters,
    topURLs: [
      { url: `${domain}/blog/ai-app-security`, citations: 14, platforms: ['chatgpt', 'perplexity'] },
      { url: `${domain}/docs/enterprise-features`, citations: 11, platforms: ['claude', 'chatgpt'] },
      { url: `${domain}/blog/comparison-guide`, citations: 8, platforms: ['perplexity'] },
      { url: `${domain}/pricing`, citations: 5, platforms: ['chatgpt'] },
      { url: `${domain}/docs/getting-started`, citations: 3, platforms: ['gemini'] },
    ],
    structuralComparison: [
      { signal: 'Word Count', theirAvg: '2,450', yourAvg: '1,380', gap: '-1,070', gapDirection: 'behind' },
      { signal: 'Headers per 500w', theirAvg: '4.2', yourAvg: '2.1', gap: '-2.1', gapDirection: 'behind' },
      { signal: 'FAQ Sections', theirAvg: '68%', yourAvg: '20%', gap: '-48%', gapDirection: 'behind' },
      { signal: 'Comparison Tables', theirAvg: '55%', yourAvg: '30%', gap: '-25%', gapDirection: 'behind' },
      { signal: 'External Citations', theirAvg: '82%', yourAvg: '38%', gap: '-44%', gapDirection: 'behind' },
      { signal: 'Reading Level', theirAvg: '9.8', yourAvg: '11.2', gap: '+1.4', gapDirection: 'ahead' },
    ],
    trajectory: Array.from({ length: 28 }, (_, i) => {
      const d = new Date('2026-03-01');
      d.setDate(d.getDate() + i);
      return {
        date: d.toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' }),
        citations: Math.floor(12 + Math.sin(i / 4 + domain.length) * 3 + Math.cos(i / 2) * 1.5),
      };
    }),
    threatScore,
    threatSummary: [
      `${domain} published ${piecesCount} new content pieces in your clusters this month`,
      defendCount > 0 ? `${defendCount} of those target clusters where you currently DEFEND` : 'No direct challenge to your DEFEND clusters yet',
    ],
    contentVelocity: domain === 'bolt.new' ? '3.2 pages/week' : domain === 'cursor.com' ? '2.1 pages/week' : '0.8 pages/week',
  };
}

// ─── Query Drawer Data ───────────────────────────────────────────────────────

export interface QueryDetailData {
  query: string;
  yourContent: {
    url: string;
    similarity: number;
    wordCount: number;
    headers: number;
    faq: boolean;
    tables: number;
    externalCitations: number;
  };
  theirContent: {
    url: string;
    domain: string;
    similarity: number;
    wordCount: number;
    headers: number;
    faq: boolean;
    faqCount: number;
    tables: number;
    externalCitations: number;
  };
  structuralGaps: { text: string; type: 'missing' | 'has' }[];
}

export function getQueryDetail(query: string): QueryDetailData {
  const driftEntry = DRIFT_DATA.find((d) => d.query === query);
  const competitorDomain = driftEntry?.tookOver || 'snyk.io';

  return {
    query,
    yourContent: {
      url: 'lovable.dev/blog/ai-app-security-best-practices',
      similarity: 0.72,
      wordCount: 1200,
      headers: 4,
      faq: false,
      tables: 0,
      externalCitations: 0,
    },
    theirContent: {
      url: `${competitorDomain}/learn/ai-code-security`,
      domain: competitorDomain,
      similarity: 0.91,
      wordCount: 2800,
      headers: 8,
      faq: true,
      faqCount: 3,
      tables: 2,
      externalCitations: 8,
    },
    structuralGaps: [
      { text: 'Missing FAQ section (they have 3 FAQs)', type: 'missing' },
      { text: 'Word count 1,200 vs their 2,800', type: 'missing' },
      { text: 'You have comparison tables (they don\'t)', type: 'has' },
      { text: 'Missing external citations (they cite 8 sources)', type: 'missing' },
    ],
  };
}
