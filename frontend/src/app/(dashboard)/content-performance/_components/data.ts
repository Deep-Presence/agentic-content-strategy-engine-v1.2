// Content Performance — Data & Types (spec-exact)

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

// --- Content Pieces (7 rows, spec-exact) ---

export const CONTENT_PIECES: ContentPiece[] = [
  {
    id: 'c1', title: 'AI App Builder Comparison Guide', cluster: 'Branded Evaluation', clusterColor: '#5BA4C4',
    citations: 63, cps: 0.713, velocity: 4.8, velocityTrend: 'up', traffic: 12100, structuralScore: 72,
    freshnessDays: 80, lifecycle: 'peaking',
    platforms: { chatgpt: true, claude: true, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 1, aiReferrals: 247, publishedAt: '2026-01-08', url: 'lovable.dev/blog/ai-app-builder-comparison',
    queriesCovered: 12, exemplarSimilarity: 0.72, briefCompliance: 88,
  },
  {
    id: 'c2', title: 'Lovable vs Cursor: Honest Review', cluster: 'Branded Evaluation', clusterColor: '#5BA4C4',
    citations: 38, cps: 0.654, velocity: 3.9, velocityTrend: 'up', traffic: 8400, structuralScore: 65,
    freshnessDays: 77, lifecycle: 'growing',
    platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 1, aiReferrals: 124, publishedAt: '2026-01-11', url: 'lovable.dev/blog/lovable-vs-cursor',
    queriesCovered: 8, exemplarSimilarity: 0.68, briefCompliance: 82,
  },
  {
    id: 'c3', title: 'Security in AI-Generated Applications', cluster: 'Boundary', clusterColor: '#DC7B18',
    citations: 31, cps: 0.482, velocity: 2.1, velocityTrend: 'flat', traffic: 3200, structuralScore: 48,
    freshnessDays: 73, lifecycle: 'stable',
    platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: false },
    cannibalization: 0, aiReferrals: 56, publishedAt: '2026-01-14', url: 'lovable.dev/blog/security-ai-apps',
    queriesCovered: 5, exemplarSimilarity: 0.55, briefCompliance: 64,
  },
  {
    id: 'c4', title: 'Vibe Coding for Enterprise Teams', cluster: 'Category Comparison', clusterColor: '#34B27B',
    citations: 24, cps: 0.649, velocity: 3.2, velocityTrend: 'up', traffic: 5600, structuralScore: 68,
    freshnessDays: 70, lifecycle: 'growing',
    platforms: { chatgpt: false, claude: true, perplexity: true, google_ai: true, gemini: false },
    cannibalization: 0, aiReferrals: 123, publishedAt: '2026-01-17', url: 'lovable.dev/blog/vibe-coding-enterprise',
    queriesCovered: 6, exemplarSimilarity: 0.65, briefCompliance: 78,
  },
  {
    id: 'c5', title: 'Bolt.new Alternatives in 2026', cluster: 'Branded Evaluation', clusterColor: '#5BA4C4',
    citations: 29, cps: 0.521, velocity: 1.4, velocityTrend: 'down', traffic: 4100, structuralScore: 55,
    freshnessDays: 67, lifecycle: 'declining',
    platforms: { chatgpt: true, claude: false, perplexity: true, google_ai: false, gemini: false },
    cannibalization: 2, aiReferrals: 89, publishedAt: '2026-01-20', url: 'lovable.dev/blog/bolt-new-alternatives',
    queriesCovered: 9, exemplarSimilarity: 0.58, briefCompliance: 71,
  },
  {
    id: 'c6', title: 'RBAC in AI-Generated Applications', cluster: 'Boundary', clusterColor: '#DC7B18',
    citations: 18, cps: 0.459, velocity: 0.8, velocityTrend: 'down', traffic: 1900, structuralScore: 35,
    freshnessDays: 64, lifecycle: 'stale',
    platforms: { chatgpt: false, claude: false, perplexity: true, google_ai: false, gemini: false },
    cannibalization: 0, aiReferrals: 183, publishedAt: '2026-01-23', url: 'lovable.dev/blog/rbac-ai-apps',
    queriesCovered: 3, exemplarSimilarity: 0.48, briefCompliance: 55,
  },
  {
    id: 'c7', title: "Non-Technical Founder's Guide to AI App Builders", cluster: 'Problem/Awareness', clusterColor: '#8B7EC8',
    citations: 22, cps: 0.538, velocity: 2.9, velocityTrend: 'up', traffic: 6800, structuralScore: 60,
    freshnessDays: 61, lifecycle: 'growing',
    platforms: { chatgpt: true, claude: true, perplexity: false, google_ai: false, gemini: true },
    cannibalization: 0, aiReferrals: 177, publishedAt: '2026-01-26', url: 'lovable.dev/blog/non-tech-founder-guide',
    queriesCovered: 7, exemplarSimilarity: 0.62, briefCompliance: 84,
  },
];

// --- Velocity chart data (spec-exact ordering) ---

export const VELOCITY_DATA: VelocityDatum[] = [
  { title: 'AI App Builder Comparison Guide', velocity: 4.8, lifecycle: 'peaking', cluster: 'Branded Evaluation' },
  { title: 'Lovable vs Cursor: Honest Review', velocity: 3.9, lifecycle: 'growing', cluster: 'Branded Evaluation' },
  { title: 'Vibe Coding for Enterprise Teams', velocity: 3.2, lifecycle: 'growing', cluster: 'Category Comparison' },
  { title: "Non-Technical Founder's Guide", velocity: 2.9, lifecycle: 'growing', cluster: 'Problem/Awareness' },
  { title: 'Security in AI-Generated Apps', velocity: 2.1, lifecycle: 'stable', cluster: 'Boundary' },
  { title: 'Bolt.new Alternatives in 2026', velocity: 1.4, lifecycle: 'declining', cluster: 'Branded Evaluation' },
  { title: 'RBAC in AI-Generated Applications', velocity: 0.8, lifecycle: 'stale', cluster: 'Boundary' },
];

// --- CPS Scatter data (spec-exact) ---

export const CPS_SCATTER: CPSScatterDatum[] = [
  { title: 'AI App Builder Comparison Guide', predicted: 0.68, actual: 0.85, citations: 63 },
  { title: 'Lovable vs Cursor: Honest Review', predicted: 0.62, actual: 0.75, citations: 38 },
  { title: 'Vibe Coding for Enterprise Teams', predicted: 0.55, actual: 0.65, citations: 24 },
  { title: 'Security in AI-Generated Apps', predicted: 0.60, actual: 0.45, citations: 31 },
  { title: "Non-Technical Founder's Guide", predicted: 0.48, actual: 0.55, citations: 22 },
  { title: 'Bolt.new Alternatives in 2026', predicted: 0.58, actual: 0.42, citations: 29 },
  { title: 'RBAC in AI-Generated Applications', predicted: 0.52, actual: 0.35, citations: 18 },
];

// --- Structural Signals (all 20, spec-exact) ---

export const STRUCTURAL_SIGNALS: StructuralSignal[] = [
  { signal: 'FAQ Section', r: 0.82, citedAvg: 78, yours: 20, impact: 'critical' },
  { signal: 'Comparison Table', r: 0.79, citedAvg: 85, yours: 30, impact: 'critical' },
  { signal: 'Word Count 2000+', r: 0.74, citedAvg: 92, yours: 45, impact: 'high' },
  { signal: 'Headers per 500w \u2265 3', r: 0.71, citedAvg: 80, yours: 44, impact: 'high' },
  { signal: 'Ordered Lists', r: 0.68, citedAvg: 72, yours: 35, impact: 'high' },
  { signal: 'Schema (FAQ/HowTo)', r: 0.65, citedAvg: 68, yours: 15, impact: 'high' },
  { signal: 'External Citations', r: 0.62, citedAvg: 84, yours: 38, impact: 'medium' },
  { signal: 'Key Takeaways', r: 0.58, citedAvg: 55, yours: 22, impact: 'medium' },
  { signal: 'Reading Grade 8-12', r: 0.54, citedAvg: 88, yours: 82, impact: 'low' },
  { signal: 'Stats/Data Points', r: 0.51, citedAvg: 64, yours: 28, impact: 'medium' },
  { signal: 'Definition Opening', r: 0.47, citedAvg: 52, yours: 40, impact: 'low' },
  { signal: 'Code Blocks', r: 0.42, citedAvg: 38, yours: 55, impact: 'low' },
  // Additional 8 for "Show all 20"
  { signal: 'Step-by-Step Guide', r: 0.39, citedAvg: 45, yours: 30, impact: 'low' },
  { signal: 'Expert Quotes', r: 0.36, citedAvg: 32, yours: 10, impact: 'low' },
  { signal: 'Research References', r: 0.34, citedAvg: 48, yours: 25, impact: 'low' },
  { signal: 'Infographics/Images', r: 0.31, citedAvg: 55, yours: 40, impact: 'low' },
  { signal: 'Table of Contents', r: 0.28, citedAvg: 62, yours: 50, impact: 'low' },
  { signal: 'Meta Description', r: 0.25, citedAvg: 95, yours: 90, impact: 'low' },
  { signal: 'Canonical URL', r: 0.22, citedAvg: 98, yours: 100, impact: 'low' },
  { signal: 'Mobile Responsive', r: 0.18, citedAvg: 99, yours: 100, impact: 'low' },
];

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

// --- Drawer detail data keyed by content piece ID ---

export const QUERY_COVERAGE: Record<string, QueryCoverage[]> = {
  c1: [
    { query: 'best AI app builder comparison', gapScore: 0.15, classification: 'aligned' },
    { query: 'lovable vs bolt.new vs cursor', gapScore: 0.08, classification: 'company_leads' },
    { query: 'AI app builder features comparison', gapScore: 0.32, classification: 'moderate_gap' },
    { query: 'no-code app builder review 2026', gapScore: 0.28, classification: 'moderate_gap' },
    { query: 'which ai coding tool is best', gapScore: 0.15, classification: 'aligned' },
    { query: 'ai web app generator review', gapScore: 0.18, classification: 'aligned' },
    { query: 'no-code ai builder comparison', gapScore: 0.25, classification: 'moderate_gap' },
    { query: 'ai app builder for startups', gapScore: 0.30, classification: 'moderate_gap' },
    { query: 'lovable dev review 2026', gapScore: 0.05, classification: 'company_leads' },
    { query: 'best tool to build saas with ai', gapScore: 0.28, classification: 'moderate_gap' },
    { query: 'compare ai app builders features', gapScore: 0.19, classification: 'aligned' },
    { query: 'top ai development platforms ranked', gapScore: 0.21, classification: 'moderate_gap' },
  ],
  c2: [
    { query: 'lovable vs cursor', gapScore: 0.10, classification: 'company_leads' },
    { query: 'cursor alternative for non-coders', gapScore: 0.35, classification: 'moderate_gap' },
    { query: 'lovable vs cursor review', gapScore: 0.08, classification: 'company_leads' },
    { query: 'ai code editor vs ai app builder', gapScore: 0.22, classification: 'moderate_gap' },
    { query: 'cursor vs lovable which is better', gapScore: 0.12, classification: 'aligned' },
    { query: 'best ai tool for building apps', gapScore: 0.28, classification: 'moderate_gap' },
    { query: 'lovable dev vs cursor comparison', gapScore: 0.06, classification: 'company_leads' },
    { query: 'ai coding assistants compared', gapScore: 0.20, classification: 'moderate_gap' },
  ],
  c3: [
    { query: 'security ai generated apps', gapScore: 0.15, classification: 'aligned' },
    { query: 'is ai generated code secure', gapScore: 0.32, classification: 'moderate_gap' },
    { query: 'ai app builder security risks', gapScore: 0.28, classification: 'moderate_gap' },
    { query: 'secure ai development practices', gapScore: 0.20, classification: 'moderate_gap' },
    { query: 'ai code generation security audit', gapScore: 0.55, classification: 'significant_gap' },
  ],
  c4: [
    { query: 'vibe coding enterprise', gapScore: 0.18, classification: 'aligned' },
    { query: 'ai coding for teams', gapScore: 0.25, classification: 'moderate_gap' },
    { query: 'enterprise ai app builder', gapScore: 0.30, classification: 'moderate_gap' },
    { query: 'vibe coding meaning', gapScore: 0.12, classification: 'aligned' },
    { query: 'ai development team workflow', gapScore: 0.22, classification: 'moderate_gap' },
    { query: 'enterprise vibe coding tools', gapScore: 0.20, classification: 'moderate_gap' },
  ],
  c5: [
    { query: 'bolt.new alternatives', gapScore: 0.08, classification: 'company_leads' },
    { query: 'bolt.new vs lovable', gapScore: 0.12, classification: 'aligned' },
    { query: 'best bolt.new replacement', gapScore: 0.15, classification: 'aligned' },
    { query: 'alternatives to bolt new 2026', gapScore: 0.10, classification: 'company_leads' },
    { query: 'bolt new competitors', gapScore: 0.18, classification: 'aligned' },
    { query: 'ai app builder like bolt new', gapScore: 0.22, classification: 'moderate_gap' },
    { query: 'bolt.new review and alternatives', gapScore: 0.14, classification: 'aligned' },
    { query: 'stackblitz bolt alternatives', gapScore: 0.25, classification: 'moderate_gap' },
    { query: 'best ai web app builders 2026', gapScore: 0.20, classification: 'moderate_gap' },
  ],
  c6: [
    { query: 'rbac ai generated apps', gapScore: 0.55, classification: 'significant_gap' },
    { query: 'role based access control ai apps', gapScore: 0.48, classification: 'moderate_gap' },
    { query: 'ai app permissions management', gapScore: 0.62, classification: 'significant_gap' },
  ],
  c7: [
    { query: 'non technical founder build app', gapScore: 0.20, classification: 'moderate_gap' },
    { query: 'build app without coding', gapScore: 0.15, classification: 'aligned' },
    { query: 'ai app builder for beginners', gapScore: 0.22, classification: 'moderate_gap' },
    { query: 'no-code app builder guide', gapScore: 0.18, classification: 'aligned' },
    { query: 'startup founder build software ai', gapScore: 0.25, classification: 'moderate_gap' },
    { query: 'how to build saas without developers', gapScore: 0.30, classification: 'moderate_gap' },
    { query: 'non-technical founder app development', gapScore: 0.19, classification: 'aligned' },
  ],
};

// Structural details for drawer Section C (8 signals per spec)
export const STRUCTURAL_DETAILS: Record<string, StructuralDetail[]> = {
  c1: [
    { signal: 'Word Count', citedAvg: '2,017', yours: '2,450', gap: '+433', status: 'above' },
    { signal: 'Headers', citedAvg: '14', yours: '16', gap: '+2', status: 'above' },
    { signal: 'FAQ Sections', citedAvg: '42%', yours: '100%', gap: '+58%', status: 'above' },
    { signal: 'Comparison Tables', citedAvg: '41%', yours: '100%', gap: '+59%', status: 'above' },
    { signal: 'External Citations', citedAvg: '94%', yours: '80%', gap: '-14%', status: 'below' },
    { signal: 'Reading Level', citedAvg: '10.2', yours: '11.5', gap: '+1.3', status: 'above' },
    { signal: 'Key Takeaways', citedAvg: '38%', yours: '100%', gap: '+62%', status: 'above' },
    { signal: 'Lists (ordered)', citedAvg: '65%', yours: '80%', gap: '+15%', status: 'above' },
  ],
  c2: [
    { signal: 'Word Count', citedAvg: '2,017', yours: '1,850', gap: '-167', status: 'below' },
    { signal: 'Headers', citedAvg: '14', yours: '12', gap: '-2', status: 'below' },
    { signal: 'FAQ Sections', citedAvg: '42%', yours: '0%', gap: '-42%', status: 'missing' },
    { signal: 'Comparison Tables', citedAvg: '41%', yours: '100%', gap: '+59%', status: 'above' },
    { signal: 'External Citations', citedAvg: '94%', yours: '85%', gap: '-9%', status: 'below' },
    { signal: 'Reading Level', citedAvg: '10.2', yours: '9.8', gap: '-0.4', status: 'match' },
    { signal: 'Key Takeaways', citedAvg: '38%', yours: '0%', gap: '-38%', status: 'missing' },
    { signal: 'Lists (ordered)', citedAvg: '65%', yours: '40%', gap: '-25%', status: 'below' },
  ],
  c3: [
    { signal: 'Word Count', citedAvg: '2,017', yours: '1,450', gap: '-567', status: 'missing' },
    { signal: 'Headers', citedAvg: '14', yours: '8', gap: '-6', status: 'below' },
    { signal: 'FAQ Sections', citedAvg: '42%', yours: '0%', gap: '-42%', status: 'missing' },
    { signal: 'Comparison Tables', citedAvg: '41%', yours: '0%', gap: '-41%', status: 'missing' },
    { signal: 'External Citations', citedAvg: '94%', yours: '60%', gap: '-34%', status: 'missing' },
    { signal: 'Reading Level', citedAvg: '10.2', yours: '13.2', gap: '+3.0', status: 'below' },
    { signal: 'Key Takeaways', citedAvg: '38%', yours: '0%', gap: '-38%', status: 'missing' },
    { signal: 'Lists (ordered)', citedAvg: '65%', yours: '20%', gap: '-45%', status: 'missing' },
  ],
  c4: [
    { signal: 'Word Count', citedAvg: '2,017', yours: '1,920', gap: '-97', status: 'below' },
    { signal: 'Headers', citedAvg: '14', yours: '13', gap: '-1', status: 'match' },
    { signal: 'FAQ Sections', citedAvg: '42%', yours: '100%', gap: '+58%', status: 'above' },
    { signal: 'Comparison Tables', citedAvg: '41%', yours: '0%', gap: '-41%', status: 'missing' },
    { signal: 'External Citations', citedAvg: '94%', yours: '90%', gap: '-4%', status: 'match' },
    { signal: 'Reading Level', citedAvg: '10.2', yours: '10.8', gap: '+0.6', status: 'match' },
    { signal: 'Key Takeaways', citedAvg: '38%', yours: '100%', gap: '+62%', status: 'above' },
    { signal: 'Lists (ordered)', citedAvg: '65%', yours: '60%', gap: '-5%', status: 'match' },
  ],
  c5: [
    { signal: 'Word Count', citedAvg: '2,017', yours: '1,680', gap: '-337', status: 'below' },
    { signal: 'Headers', citedAvg: '14', yours: '10', gap: '-4', status: 'below' },
    { signal: 'FAQ Sections', citedAvg: '42%', yours: '0%', gap: '-42%', status: 'missing' },
    { signal: 'Comparison Tables', citedAvg: '41%', yours: '100%', gap: '+59%', status: 'above' },
    { signal: 'External Citations', citedAvg: '94%', yours: '70%', gap: '-24%', status: 'below' },
    { signal: 'Reading Level', citedAvg: '10.2', yours: '9.5', gap: '-0.7', status: 'match' },
    { signal: 'Key Takeaways', citedAvg: '38%', yours: '0%', gap: '-38%', status: 'missing' },
    { signal: 'Lists (ordered)', citedAvg: '65%', yours: '30%', gap: '-35%', status: 'missing' },
  ],
  c6: [
    { signal: 'Word Count', citedAvg: '2,017', yours: '1,200', gap: '-817', status: 'missing' },
    { signal: 'Headers', citedAvg: '14', yours: '6', gap: '-8', status: 'missing' },
    { signal: 'FAQ Sections', citedAvg: '42%', yours: '0%', gap: '-42%', status: 'missing' },
    { signal: 'Comparison Tables', citedAvg: '41%', yours: '0%', gap: '-41%', status: 'missing' },
    { signal: 'External Citations', citedAvg: '94%', yours: '40%', gap: '-54%', status: 'missing' },
    { signal: 'Reading Level', citedAvg: '10.2', yours: '14.1', gap: '+3.9', status: 'missing' },
    { signal: 'Key Takeaways', citedAvg: '38%', yours: '0%', gap: '-38%', status: 'missing' },
    { signal: 'Lists (ordered)', citedAvg: '65%', yours: '10%', gap: '-55%', status: 'missing' },
  ],
  c7: [
    { signal: 'Word Count', citedAvg: '2,017', yours: '1,780', gap: '-237', status: 'below' },
    { signal: 'Headers', citedAvg: '14', yours: '11', gap: '-3', status: 'below' },
    { signal: 'FAQ Sections', citedAvg: '42%', yours: '100%', gap: '+58%', status: 'above' },
    { signal: 'Comparison Tables', citedAvg: '41%', yours: '0%', gap: '-41%', status: 'missing' },
    { signal: 'External Citations', citedAvg: '94%', yours: '75%', gap: '-19%', status: 'below' },
    { signal: 'Reading Level', citedAvg: '10.2', yours: '8.5', gap: '-1.7', status: 'match' },
    { signal: 'Key Takeaways', citedAvg: '38%', yours: '100%', gap: '+62%', status: 'above' },
    { signal: 'Lists (ordered)', citedAvg: '65%', yours: '50%', gap: '-15%', status: 'below' },
  ],
};

export const CANNIBALIZATION_DATA: Record<string, CannibalizationEntry[]> = {
  c1: [{ title: 'Lovable vs Cursor: Honest Review', url: 'lovable.dev/blog/lovable-vs-cursor', similarity: 0.87 }],
  c2: [{ title: 'AI App Builder Comparison Guide', url: 'lovable.dev/blog/ai-app-builder-comparison', similarity: 0.87 }],
  c5: [
    { title: 'AI App Builder Comparison Guide', url: 'lovable.dev/blog/ai-app-builder-comparison', similarity: 0.72 },
    { title: 'Lovable vs Cursor: Honest Review', url: 'lovable.dev/blog/lovable-vs-cursor', similarity: 0.65 },
  ],
};

export const BRIEF_COMPLIANCE: Record<string, BriefCompliance> = {
  c1: {
    wordCountTarget: 2200, wordCountActual: 2450,
    requiredElements: [
      { element: 'Comparison table', present: true },
      { element: 'External citations (8 sources)', present: true },
      { element: 'FAQ section', present: true },
      { element: 'Key takeaways', present: true },
      { element: 'Headers per 500w \u2265 3', present: true },
      { element: 'Schema markup', present: false },
    ],
    readingLevelTarget: '10-12', readingLevelActual: '11.5',
  },
  c2: {
    wordCountTarget: 2000, wordCountActual: 1850,
    requiredElements: [
      { element: 'Comparison table', present: true },
      { element: 'External citations (5+)', present: true },
      { element: 'FAQ section', present: false },
      { element: 'Key takeaways', present: false },
      { element: 'Headers per 500w \u2265 3', present: true },
      { element: 'Schema markup', present: false },
    ],
    readingLevelTarget: '10-12', readingLevelActual: '9.8',
  },
  c3: {
    wordCountTarget: 2000, wordCountActual: 1450,
    requiredElements: [
      { element: 'Comparison table', present: false },
      { element: 'External citations (5+)', present: true },
      { element: 'FAQ section', present: false },
      { element: 'Key takeaways', present: false },
      { element: 'Headers per 500w \u2265 3', present: false },
      { element: 'Schema markup', present: false },
    ],
    readingLevelTarget: '10-12', readingLevelActual: '13.2',
  },
  c4: {
    wordCountTarget: 2000, wordCountActual: 1920,
    requiredElements: [
      { element: 'Comparison table', present: false },
      { element: 'External citations (5+)', present: true },
      { element: 'FAQ section', present: true },
      { element: 'Key takeaways', present: true },
      { element: 'Headers per 500w \u2265 3', present: true },
      { element: 'Schema markup', present: true },
    ],
    readingLevelTarget: '10-12', readingLevelActual: '10.8',
  },
  c5: {
    wordCountTarget: 2000, wordCountActual: 1680,
    requiredElements: [
      { element: 'Comparison table', present: true },
      { element: 'External citations (5+)', present: true },
      { element: 'FAQ section', present: false },
      { element: 'Key takeaways', present: false },
      { element: 'Headers per 500w \u2265 3', present: false },
      { element: 'Schema markup', present: false },
    ],
    readingLevelTarget: '10-12', readingLevelActual: '9.5',
  },
  c6: {
    wordCountTarget: 2000, wordCountActual: 1200,
    requiredElements: [
      { element: 'Comparison table', present: false },
      { element: 'External citations (5+)', present: false },
      { element: 'FAQ section', present: false },
      { element: 'Key takeaways', present: false },
      { element: 'Headers per 500w \u2265 3', present: false },
      { element: 'Schema markup', present: false },
    ],
    readingLevelTarget: '10-12', readingLevelActual: '14.1',
  },
  c7: {
    wordCountTarget: 1800, wordCountActual: 1780,
    requiredElements: [
      { element: 'Comparison table', present: false },
      { element: 'External citations (5+)', present: true },
      { element: 'FAQ section', present: true },
      { element: 'Key takeaways', present: true },
      { element: 'Headers per 500w \u2265 3', present: false },
      { element: 'Schema markup', present: false },
    ],
    readingLevelTarget: '8-10', readingLevelActual: '8.5',
  },
};

// Generate daily citation timeline data for drawer
export function generateCitationTimeline(totalCitations: number): { date: string; citations: number }[] {
  return Array.from({ length: 28 }, (_, i) => ({
    date: `Mar ${i + 1}`,
    citations: Math.max(0, Math.floor(totalCitations / 28 * (0.5 + Math.sin(i * 0.7 + totalCitations) * 0.3 + 0.3))),
  }));
}

// Platform detail for drawer
export interface PlatformDetail {
  platform: string;
  domain: string;
  cited: boolean;
  citations: number;
}

export function getPlatformDetails(piece: ContentPiece): PlatformDetail[] {
  const totalCited = PLATFORM_LIST.filter((p) => piece.platforms[p.key]).length;
  return PLATFORM_LIST.map((p) => {
    const cited = piece.platforms[p.key];
    const baseCitations = cited ? Math.round(piece.citations / totalCited) : 0;
    const adj = cited ? Math.round(Math.sin(piece.citations * 0.3 + PLATFORM_LIST.indexOf(p)) * 3) : 0;
    return {
      platform: p.name,
      domain: p.domain,
      cited,
      citations: Math.max(0, baseCitations + adj),
    };
  });
}

// --- Traffic timeline data for drawer Section B ---
export function generateTrafficTimeline(traffic: number): { date: string; pageviews: number }[] {
  return Array.from({ length: 28 }, (_, i) => {
    const dailyBase = traffic / 30;
    const pv = Math.max(0, Math.round(dailyBase * (0.7 + Math.sin(i * 0.5 + traffic * 0.001) * 0.3 + Math.random() * 0.2)));
    return { date: `Mar ${i + 1}`, pageviews: pv };
  });
}

// --- Traffic sources for drawer Section I ---
export interface TrafficSource {
  source: string;
  sessions: number;
  pct: number;
}

export function getTrafficSources(piece: ContentPiece): TrafficSource[] {
  const t = piece.traffic;
  const organic = Math.round(t * 0.42);
  const direct = Math.round(t * 0.18);
  const aiRef = piece.aiReferrals;
  const social = Math.round(t * 0.12);
  const referral = t - organic - direct - aiRef - social;
  const total = t;
  return [
    { source: 'Organic Search', sessions: organic, pct: Math.round((organic / total) * 100) },
    { source: 'Direct', sessions: direct, pct: Math.round((direct / total) * 100) },
    { source: 'AI Referral (est.)', sessions: aiRef, pct: Math.round((aiRef / total) * 100) },
    { source: 'Social', sessions: social, pct: Math.round((social / total) * 100) },
    { source: 'Referral', sessions: Math.max(0, referral), pct: Math.max(0, Math.round((referral / total) * 100)) },
  ];
}

// --- Format traffic numbers ---
export function formatTraffic(n: number): string {
  if (n >= 10000) return `${(n / 1000).toFixed(1)}K`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}
