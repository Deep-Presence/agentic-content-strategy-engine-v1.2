import type { ContentBrief, Platform } from '@/types';
import briefsData from '@/../data/result-draft/artifacts/content/carta/briefs.json';
import outline001 from '@/../data/result-draft/artifacts/content/carta/content/brief-001/outline.json';
import outline002 from '@/../data/result-draft/artifacts/content/carta/content/brief-002/outline.json';

const realBriefs = briefsData.briefs;

// --- Extended brief data for the board ---

export interface ExtendedBrief extends ContentBrief {
  contentFormat: string;
  funnelStage: string;
  priorityScore: number;
  gapScore: number;
  currentWordCount?: number;
  readMinutes?: number;
  whyPicked?: string[];
  successIndicators?: { label: string; value: string; sub: string }[];
  outlineSections?: { heading: string; level: number; targetWords: number; keyPoints: string[] }[];
  mustHitChecklist?: { label: string; priority: 'critical' | 'high' | 'medium' }[];
  keyAngles?: string[];
  exemplars?: { url: string; domain: string; words: number; headers: number; stats: number }[];
  sources?: { name: string; domain: string; engines: number }[];
  citationShare?: { name: string; pct: number; color: string }[];
}

export type StageId = 'triage' | 'brief' | 'generating' | 'review' | 'approved';

export const stageColumns: { id: StageId; label: string; color: 'neutral' | 'info' | 'warning' | 'error' | 'success' }[] = [
  { id: 'triage', label: 'Suggested', color: 'neutral' },
  { id: 'brief', label: 'Approved', color: 'info' },
  { id: 'generating', label: 'In Progress', color: 'warning' },
  { id: 'review', label: 'Review', color: 'error' },
  { id: 'approved', label: 'Published', color: 'success' },
];

// Build outline sections from real data
function buildOutline(outline: typeof outline001): ExtendedBrief['outlineSections'] {
  return outline.sections.map((s) => ({
    heading: s.heading,
    level: s.level,
    targetWords: s.target_word_count,
    keyPoints: s.key_points,
  }));
}

export const boardItems: ExtendedBrief[] = [
  // SUGGESTED
  {
    id: 'triage-001',
    title: 'Secrets & Environment Variables in Prompt-to-App Tools',
    targetCluster: 'Mechanism',
    targetQuery: 'How do prompt-to-app tools handle secrets and environment variables?',
    stage: 'triage',
    personas: ['arjun', 'elena'],
    cpsPredict: { chatgpt: 42, claude: 38, perplexity: 45, google_ai_overview: 30, gemini: 35 },
    structuralTargets: { words: 1700, paragraphs: 14, headers: 11, lists: 7, stats: 3, citations: 10 },
    createdAt: '2026-03-10T10:00:00Z',
    contentFormat: 'HOW-TO',
    funnelStage: 'consideration',
    priorityScore: 0.91,
    gapScore: 0.175,
    whyPicked: [
      'Competitors cited 3.2× more on this query cluster — significant gap at 0.175',
      '1 high-quality exemplar article found (Netlify: 1,224 words, 11 headers, 10 lists)',
      'How-to format has 86% citation correlation for Mechanism queries',
    ],
    successIndicators: [
      { label: 'Target Citation Share', value: '35%', sub: 'within 60 days' },
      { label: 'Similarity Target', value: '0.92', sub: 'from current 0.40' },
      { label: 'Est. AI Referral Visits', value: '2.4K', sub: 'monthly' },
      { label: 'Exemplar Count', value: '1', sub: 'top-cited article' },
    ],
  },
  {
    id: 'triage-002',
    title: 'SOC 2 + GDPR for AI Development Platforms',
    targetCluster: 'Boundary',
    targetQuery: 'What compliance certifications do AI development platforms need?',
    stage: 'triage',
    personas: ['marcus'],
    cpsPredict: { chatgpt: 35, claude: 40, perplexity: 38, google_ai_overview: 28, gemini: 32 },
    structuralTargets: { words: 1400, paragraphs: 12, headers: 21, lists: 18, stats: 4, citations: 26 },
    createdAt: '2026-03-09T14:00:00Z',
    contentFormat: 'GUIDE',
    funnelStage: 'awareness',
    priorityScore: 0.89,
    gapScore: 0.159,
    whyPicked: [
      'Company content only tangentially covers compliance — current page is business-ideas guide',
      'Exemplar (Compass ITC) has 1,400 words with 21 headers, 18 lists, 26 citations',
      'Boundary cluster has 93% header rate and 83% list rate — highly structured content wins',
    ],
    successIndicators: [
      { label: 'Target Citation Share', value: '28%', sub: 'within 45 days' },
      { label: 'Similarity Target', value: '0.88', sub: 'from current 0.31' },
      { label: 'Est. AI Referral Visits', value: '1.8K', sub: 'monthly' },
      { label: 'Exemplar Count', value: '1', sub: 'top-cited article' },
    ],
  },
  {
    id: 'triage-003',
    title: 'RBAC Accuracy in AI-Generated Applications',
    targetCluster: 'Boundary',
    targetQuery: 'How accurate is role-based access control in AI-generated apps?',
    stage: 'triage',
    personas: ['arjun'],
    cpsPredict: { chatgpt: 30, claude: 35, perplexity: 32, google_ai_overview: 25, gemini: 28 },
    structuralTargets: { words: 1600, paragraphs: 12, headers: 10, lists: 8, stats: 3, citations: 12 },
    createdAt: '2026-03-08T09:00:00Z',
    contentFormat: 'HOW-TO',
    funnelStage: 'consideration',
    priorityScore: 0.85,
    gapScore: 0.130,
    whyPicked: [
      'Only mentioned tangentially in no-code builders guide — needs dedicated article',
      'Validation framework + test cases would differentiate from existing exemplars',
      'Boundary cluster queries have 96% citation rate — strong structural signal',
    ],
    successIndicators: [
      { label: 'Target Citation Share', value: '22%', sub: 'within 60 days' },
      { label: 'Similarity Target', value: '0.85', sub: 'from current 0.35' },
      { label: 'Est. AI Referral Visits', value: '1.2K', sub: 'monthly' },
      { label: 'Exemplar Count', value: '2', sub: 'top-cited articles' },
    ],
  },
  // APPROVED (brief being generated)
  {
    id: 'brief-003',
    title: 'Audit Logs & Change History for AI App Builders',
    targetCluster: 'Boundary',
    targetQuery: 'Do AI app builders provide audit logs and change history?',
    stage: 'brief',
    personas: ['elena', 'marcus'],
    cpsPredict: { chatgpt: 50, claude: 48, perplexity: 52, google_ai_overview: 40, gemini: 42 },
    structuralTargets: { words: 2800, paragraphs: 20, headers: 9, lists: 5, stats: 3, citations: 10 },
    createdAt: '2026-03-07T11:00:00Z',
    contentFormat: 'COMPARISON',
    funnelStage: 'consideration',
    priorityScore: 0.87,
    gapScore: 0.122,
    sources: [
      { name: 'Retool Audit Guide', domain: 'retool.com', engines: 3 },
      { name: 'Zapier Change Tracking', domain: 'zapier.com', engines: 2 },
      { name: 'G2 Grid: Low-Code', domain: 'g2.com', engines: 1 },
    ],
    exemplars: [
      { url: 'retool.com/blog/audit-logs', domain: 'retool.com', words: 2847, headers: 12, stats: 7 },
      { url: 'zapier.com/change-history', domain: 'zapier.com', words: 1956, headers: 8, stats: 9 },
    ],
    citationShare: [
      { name: 'Retool', pct: 34, color: 'var(--success)' },
      { name: 'Zapier', pct: 22, color: 'var(--warning)' },
      { name: 'Appian', pct: 18, color: 'var(--error)' },
      { name: 'Others', pct: 22, color: 'var(--text-tertiary)' },
      { name: 'Lovable', pct: 4, color: 'var(--accent)' },
    ],
  },
  {
    id: 'brief-004',
    title: 'Bolt.new Alternatives 2026: Complete Comparison',
    targetCluster: 'Category Comparison',
    targetQuery: 'What are the best alternatives to Bolt.new for building apps?',
    stage: 'brief',
    personas: ['arjun', 'sabrine'],
    cpsPredict: { chatgpt: 55, claude: 60, perplexity: 58, google_ai_overview: 45, gemini: 50 },
    structuralTargets: { words: 2000, paragraphs: 16, headers: 12, lists: 8, stats: 5, citations: 15 },
    createdAt: '2026-03-06T16:00:00Z',
    contentFormat: 'COMPARISON',
    funnelStage: 'consideration',
    priorityScore: 0.92,
    gapScore: 0.141,
    sources: [
      { name: 'G2 Grid: AI Code Gen', domain: 'g2.com', engines: 3 },
      { name: 'Taskade Blog', domain: 'taskade.com', engines: 2 },
      { name: 'Reddit r/nocode', domain: 'reddit.com', engines: 2 },
    ],
    exemplars: [
      { url: 'taskade.com/blog/bolt-alternatives', domain: 'taskade.com', words: 2903, headers: 37, stats: 12 },
      { url: 'g2.com/categories/ai-code-gen', domain: 'g2.com', words: 1856, headers: 15, stats: 9 },
    ],
    citationShare: [
      { name: 'Bolt.new', pct: 28, color: 'var(--success)' },
      { name: 'Cursor', pct: 24, color: 'var(--warning)' },
      { name: 'Replit', pct: 20, color: 'var(--error)' },
      { name: 'Others', pct: 24, color: 'var(--text-tertiary)' },
      { name: 'Lovable', pct: 4, color: 'var(--accent)' },
    ],
  },
  // IN PROGRESS — real brief-001
  {
    id: 'brief-001',
    title: realBriefs[0].title,
    targetCluster: realBriefs[0].target_cluster,
    targetQuery: realBriefs[0].target_queries[0].query_text,
    stage: 'generating',
    personas: ['elena', 'marcus', 'arjun'],
    cpsPredict: { chatgpt: 62, claude: 58, perplexity: 65, google_ai_overview: 50, gemini: 55 },
    structuralTargets: {
      words: realBriefs[0].word_count_range[1],
      paragraphs: 30,
      headers: realBriefs[0].structural_targets.min_headers,
      lists: realBriefs[0].structural_targets.min_lists,
      stats: 5,
      citations: realBriefs[0].structural_targets.min_citations,
    },
    createdAt: '2026-03-05T08:00:00Z',
    contentFormat: 'PILLAR PAGE',
    funnelStage: realBriefs[0].funnel_stage,
    priorityScore: realBriefs[0].priority_score,
    gapScore: 0.175,
    currentWordCount: 2988,
    readMinutes: 12,
    outlineSections: buildOutline(outline001),
    sources: [
      { name: 'OECD Model Tax Convention', domain: 'oecd.org', engines: 3 },
      { name: 'FCA Enforcement Guidelines', domain: 'fca.org.uk', engines: 2 },
      { name: 'JD Supra Global Equity', domain: 'jdsupra.com', engines: 2 },
      { name: 'Deel Global Equity Guide', domain: 'deel.com', engines: 1 },
    ],
    exemplars: [
      { url: 'jdsupra.com/global-equity-report', domain: 'jdsupra.com', words: 3200, headers: 14, stats: 8 },
      { url: 'deel.com/equity-guide', domain: 'deel.com', words: 2800, headers: 11, stats: 6 },
    ],
  },
  // REVIEW — real brief-002
  {
    id: 'brief-002',
    title: realBriefs[1].title,
    targetCluster: realBriefs[1].target_cluster,
    targetQuery: realBriefs[1].target_queries[0].query_text,
    stage: 'review',
    personas: ['sabrine', 'elena'],
    cpsPredict: { chatgpt: 70, claude: 72, perplexity: 68, google_ai_overview: 55, gemini: 60 },
    cpsActual: { chatgpt: 68, claude: 74, perplexity: 71, google_ai_overview: 52, gemini: 58 },
    structuralTargets: {
      words: realBriefs[1].word_count_range[1],
      paragraphs: 22,
      headers: realBriefs[1].structural_targets.min_headers,
      lists: realBriefs[1].structural_targets.min_lists,
      stats: 4,
      citations: realBriefs[1].structural_targets.min_citations,
    },
    createdAt: '2026-03-04T12:00:00Z',
    contentFormat: 'LONG BLOG',
    funnelStage: realBriefs[1].funnel_stage,
    priorityScore: realBriefs[1].priority_score,
    gapScore: 0.110,
    currentWordCount: 3323,
    readMinutes: 14,
    outlineSections: buildOutline(outline002),
    mustHitChecklist: [
      { label: 'Worked numerical example (Series A → Series B)', priority: 'critical' },
      { label: 'Cap table snapshots before/after round', priority: 'critical' },
      { label: 'Founder dilution projection across 3+ rounds', priority: 'high' },
      { label: 'Super pro-rata definition and negotiation dynamics', priority: 'high' },
      { label: 'FAQ section covering common objections', priority: 'medium' },
      { label: 'Key takeaways box at end', priority: 'medium' },
    ],
    keyAngles: [
      'Founder perspective: dilution math across multiple rounds',
      'Investor perspective: portfolio return amplification via pro-rata',
      'Connection to cap table management tooling (Carta product angle)',
      'Worked examples with real numbers, not abstract formulas',
    ],
    sources: [
      { name: 'Holloway Guide to VC', domain: 'holloway.com', engines: 3 },
      { name: 'NVCA Model Term Sheet', domain: 'nvca.org', engines: 3 },
      { name: 'Carta Equity Report', domain: 'carta.com', engines: 2 },
      { name: 'PitchBook VC Data', domain: 'pitchbook.com', engines: 2 },
    ],
    exemplars: [
      { url: 'holloway.com/g/venture-capital', domain: 'holloway.com', words: 4200, headers: 18, stats: 12 },
      { url: 'carta.com/blog/pro-rata-rights', domain: 'carta.com', words: 2400, headers: 10, stats: 8 },
      { url: 'pulley.com/pro-rata-explained', domain: 'pulley.com', words: 1800, headers: 8, stats: 6 },
    ],
  },
  // PUBLISHED
  {
    id: 'approved-001',
    title: 'Cap Table Management Best Practices for Series A',
    targetCluster: 'Definition',
    targetQuery: 'What is cap table management for startups?',
    stage: 'approved',
    personas: ['sabrine', 'marcus'],
    cpsPredict: { chatgpt: 78, claude: 80, perplexity: 75, google_ai_overview: 65, gemini: 70 },
    cpsActual: { chatgpt: 76, claude: 82, perplexity: 78, google_ai_overview: 62, gemini: 68 },
    structuralTargets: { words: 2600, paragraphs: 20, headers: 8, lists: 6, stats: 4, citations: 10 },
    createdAt: '2026-02-28T10:00:00Z',
    publishedAt: '2026-03-12T09:00:00Z',
    contentFormat: 'GUIDE',
    funnelStage: 'awareness',
    priorityScore: 0.88,
    gapScore: 0.095,
    currentWordCount: 2580,
    readMinutes: 10,
  },
  {
    id: 'approved-002',
    title: 'Employee Stock Option Pool: Sizing & Strategy Guide',
    targetCluster: 'Problem/Awareness',
    targetQuery: 'How much equity should startups set aside for employee stock options?',
    stage: 'approved',
    personas: ['elena'],
    cpsPredict: { chatgpt: 72, claude: 75, perplexity: 70, google_ai_overview: 60, gemini: 65 },
    cpsActual: { chatgpt: 74, claude: 78, perplexity: 73, google_ai_overview: 58, gemini: 66 },
    structuralTargets: { words: 2400, paragraphs: 18, headers: 7, lists: 5, stats: 3, citations: 8 },
    createdAt: '2026-02-25T14:00:00Z',
    publishedAt: '2026-03-11T11:00:00Z',
    contentFormat: 'LONG BLOG',
    funnelStage: 'awareness',
    priorityScore: 0.82,
    gapScore: 0.088,
    currentWordCount: 2350,
    readMinutes: 9,
  },
];

export const agentActivities = [
  { id: '1', agent: 'Strategic Planner', action: 'Analyzing 200 query scorecards...', time: '14:20', type: 'strategy' as const },
  { id: '2', agent: 'Strategic Planner', action: 'Identified 4 source articles across 3 AI engines', time: '14:23', type: 'strategy' as const },
  { id: '3', agent: 'Brief Builder', action: 'Loaded company context (5,000 words), 2 persona profiles, full style guide', time: '14:25', type: 'writer' as const },
  { id: '4', agent: 'Brief Builder', action: 'Exemplar analysis complete — structural targets set', time: '14:28', type: 'writer' as const },
  { id: '5', agent: 'Brief Builder', action: 'Content brief generated — 7 sections, priority 0.92', time: '14:32', type: 'writer' as const },
  { id: '6', agent: 'Writer Agent', action: 'Started generation for "International Equity Grants Guide"', time: '14:35', type: 'writer' as const },
  { id: '7', agent: 'Interlink Agent', action: 'Found 4 internal link opportunities', time: '14:38', type: 'interlink' as const },
  { id: '8', agent: 'Eval Agent', action: 'Cycle 0 — structural: 0.75, semantic: 0.66, style: 0.62, factual: 0.45', time: '14:42', type: 'eval' as const },
  { id: '9', agent: 'Writer Agent', action: 'Revision cycle 1 — addressing word count and citations', time: '14:45', type: 'writer' as const },
  { id: '10', agent: 'Eval Agent', action: 'Cycle 1 — structural: 0.50, semantic: 0.68 ✓, style: 0.50, factual: 0.62', time: '14:50', type: 'eval' as const },
  { id: '11', agent: 'Writer Agent', action: 'Revision cycle 2 — word count trimmed to 2,988', time: '14:55', type: 'writer' as const },
  { id: '12', agent: 'Eval Agent', action: 'Cycle 2 — structural: 0.875 ✓, semantic: 0.66 ✓, style: 0.72 ✓, factual: 0.65', time: '15:00', type: 'eval' as const },
  { id: '13', agent: 'Interlink Agent', action: 'Applied 3 of 4 internal links', time: '15:02', type: 'interlink' as const },
  { id: '14', agent: 'Strategy Agent', action: 'Content ready for human review', time: '15:05', type: 'strategy' as const },
];

export const platformLabels: Record<Platform, string> = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  perplexity: 'Perplexity',
  google_ai_overview: 'Google AI Overview',
  gemini: 'Gemini',
};

export const platformColors: Record<Platform, string> = {
  chatgpt: 'var(--success)',
  claude: 'var(--accent)',
  perplexity: 'var(--warning)',
  google_ai_overview: 'var(--error)',
  gemini: 'var(--info)',
};
