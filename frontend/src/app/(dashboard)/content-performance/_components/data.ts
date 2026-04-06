// Content Performance — Types & Config (no mock data)

export type LifecycleStage = 'growing' | 'peaking' | 'stable' | 'declining' | 'stale';
export type VelocityTrend = 'up' | 'down' | 'flat';
export type ImpactLevel = 'critical' | 'high' | 'medium' | 'low';

export interface PlatformCitations {
  chatgpt: boolean;
  claude: boolean;
  perplexity: boolean;
  google_ai: boolean;
  gemini: boolean;
}

export interface ContentPiece {
  id: string;
  title: string;
  cluster: string;
  clusterColor: string;
  citations: number;
  cps: number;
  velocity: number;
  velocityTrend: VelocityTrend;
  traffic: number;
  structuralScore: number;
  freshnessDays: number;
  lifecycle: LifecycleStage;
  platforms: PlatformCitations;
  cannibalization: number;
  aiReferrals: number;
  publishedAt: string;
  url: string;
  queriesCovered: number;
  exemplarSimilarity: number;
  briefCompliance: number;
}

export interface StructuralSignal {
  signal: string;
  r: number;
  citedAvg: number;
  yours: number;
  impact: ImpactLevel;
}

export interface VelocityDatum {
  title: string;
  velocity: number;
  lifecycle: LifecycleStage;
  cluster: string;
}

export interface CPSScatterDatum {
  title: string;
  predicted: number;
  actual: number;
  citations: number;
}

export interface QueryCoverage {
  query: string;
  gapScore: number;
  classification: 'aligned' | 'company_leads' | 'moderate_gap' | 'significant_gap';
}

export interface StructuralDetail {
  signal: string;
  citedAvg: string;
  yours: string;
  gap: string;
  status: 'above' | 'match' | 'below' | 'missing';
}

export interface CannibalizationEntry {
  title: string;
  url: string;
  similarity: number;
}

export interface BriefCompliance {
  wordCountTarget: number;
  wordCountActual: number;
  requiredElements: { element: string; present: boolean; note?: string }[];
  readingLevelTarget: string;
  readingLevelActual: string;
}

// --- Lifecycle config ---

export const LIFECYCLE_CONFIG: Record<LifecycleStage, { label: string; icon: string; badgeVariant: 'success' | 'warning' | 'error' | 'info' | 'neutral' }> = {
  growing: { label: 'Growing', icon: '\u2191', badgeVariant: 'success' },
  peaking: { label: 'Peaking', icon: '\u25C6', badgeVariant: 'warning' },
  stable: { label: 'Stable', icon: '\u2014', badgeVariant: 'neutral' },
  declining: { label: 'Declining', icon: '\u2193', badgeVariant: 'warning' },
  stale: { label: 'Stale', icon: '\u26A0', badgeVariant: 'error' },
};

export const PLATFORM_LIST: { key: keyof PlatformCitations; name: string; domain: string }[] = [
  { key: 'chatgpt', name: 'ChatGPT', domain: 'openai.com' },
  { key: 'claude', name: 'Claude', domain: 'anthropic.com' },
  { key: 'perplexity', name: 'Perplexity', domain: 'perplexity.ai' },
  { key: 'google_ai', name: 'Google AI', domain: 'google.com' },
  { key: 'gemini', name: 'Gemini', domain: 'gemini.google.com' },
];

// --- Platform detail for drawer ---

export interface PlatformDetail {
  platform: string;
  domain: string;
  cited: boolean;
  citations: number;
}

// --- Traffic sources for drawer ---

export interface TrafficSource {
  source: string;
  sessions: number;
  pct: number;
}

// --- Format traffic numbers ---

export function formatTraffic(n: number): string {
  if (n >= 10000) return `${(n / 1000).toFixed(1)}K`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}
