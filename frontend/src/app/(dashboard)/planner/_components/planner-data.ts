// Content Planner — Data Layer
// All mock data for assignments, clusters, initiatives, rejected items

export interface Competitor {
  domain: string;
  title: string;
  url: string;
  words: number;
  faq: boolean;
  tables: boolean;
  rank: number;
}

export interface RelatedQuery {
  query: string;
  fanouts: number;
  intent: 'Informational' | 'Commercial';
}

export interface ActivityEntry {
  action: string;
  date: string;
  by: string;
}

export interface Assignment {
  id: string;
  title: string;
  cluster: string;
  subcluster: string;
  stage: 'TOFU' | 'MOFU' | 'BOFU';
  intent: 'Informational' | 'Commercial' | 'Navigational' | 'Transactional';
  format: 'Guide' | 'Comparison' | 'Tutorial' | 'Listicle' | 'Case Study';
  source: 'gap' | 'strategic' | 'custom';
  initiative?: string;
  personaScores: { sf: number; pm: number; da: number; te: number };
  persona: string;
  estCitations: number;
  citationOpp: number;
  priorityScore: number;
  effort: 'low' | 'medium' | 'high';
  estDays: number;
  competitors: Competitor[];
  reasons: Array<{ title: string; text: string }>;
  relatedQueries: RelatedQuery[];
  createdAt: string;
  activityLog: ActivityEntry[];
}

export interface Cluster {
  id: string;
  name: string;
  subclusters: Array<{ id: string; name: string; citOpp: number }>;
}

export interface Initiative {
  id: string;
  name: string;
  description: string;
  personas: string[];
  assignmentCount: number;
  created: string;
}

export interface RejectedItem {
  id: string;
  title: string;
  cluster: string;
  reason: string;
  date: string;
  rejectedBy: string;
  stage?: 'TOFU' | 'MOFU' | 'BOFU';
}

// ─── Clusters ────────────────────────────────────────────

export const CLUSTERS: Cluster[] = [
  {
    id: 'cl1', name: 'Competitive Landscape', subclusters: [
      { id: 'sc1', name: 'Platform Comparisons', citOpp: 0.85 },
      { id: 'sc2', name: 'Pricing & Value', citOpp: 0.82 },
    ],
  },
  {
    id: 'cl2', name: 'Platform Capabilities', subclusters: [
      { id: 'sc3', name: 'Database & Backend Integration', citOpp: 0.78 },
      { id: 'sc4', name: 'UI/UX Generation', citOpp: 0.71 },
      { id: 'sc5', name: 'Code Generation Quality', citOpp: 0.76 },
    ],
  },
  {
    id: 'cl3', name: 'Security & Compliance', subclusters: [
      { id: 'sc6', name: 'Data Privacy & GDPR', citOpp: 0.68 },
      { id: 'sc7', name: 'SOC 2 & Enterprise Security', citOpp: 0.65 },
    ],
  },
  {
    id: 'cl4', name: 'Developer Experience', subclusters: [
      { id: 'sc8', name: 'API Integration Patterns', citOpp: 0.74 },
      { id: 'sc9', name: 'Code Export & Customization', citOpp: 0.70 },
      { id: 'sc10', name: 'Developer Documentation', citOpp: 0.66 },
    ],
  },
  {
    id: 'cl5', name: 'Deployment & Operations', subclusters: [
      { id: 'sc11', name: 'CI/CD & Hosting', citOpp: 0.72 },
      { id: 'sc12', name: 'Scaling & Performance', citOpp: 0.61 },
    ],
  },
];

// ─── Strategic Initiatives ───────────────────────────────

export const INITIATIVES: Initiative[] = [
  {
    id: 'init1',
    name: 'Technical Engineer Expansion',
    description: 'Target developers who use APIs and code export',
    personas: ['te', 'da'],
    assignmentCount: 4,
    created: 'Mar 15, 2026',
  },
  {
    id: 'init2',
    name: 'Enterprise Security Push',
    description: 'Build authority in compliance for enterprise buyers',
    personas: ['pm'],
    assignmentCount: 3,
    created: 'Mar 8, 2026',
  },
];

// ─── 10 Assignments ──────────────────────────────────────

export const ASSIGNMENTS: Assignment[] = [
  {
    id: 'IH-001',
    title: 'AI App Builder Pricing Comparison: Which Platform Offers the Best Value?',
    cluster: 'Competitive Landscape',
    subcluster: 'Pricing & Value',
    stage: 'BOFU',
    intent: 'Commercial',
    format: 'Comparison',
    source: 'gap',
    personaScores: { sf: 92, pm: 78, da: 65, te: 41 },
    persona: 'sf',
    estCitations: 22,
    citationOpp: 0.82,
    priorityScore: 0.85,
    effort: 'medium',
    estDays: 5,
    competitors: [
      { domain: 'bolt.new', title: 'Bolt.new Pricing Breakdown', url: 'bolt.new/blog/pricing-breakdown', words: 2800, faq: true, tables: true, rank: 1 },
      { domain: 'replit.com', title: 'Replit Pricing Plans Compared', url: 'replit.com/pricing', words: 1900, faq: false, tables: true, rank: 2 },
      { domain: 'v0.dev', title: 'v0 Pricing Guide', url: 'v0.dev/docs/pricing', words: 1200, faq: true, tables: false, rank: 3 },
    ],
    reasons: [
      { title: 'Highest commercial intent', text: 'Pricing queries drive 3.2x more conversions than informational queries in this space.' },
      { title: 'Weak competitor coverage', text: 'Top 3 results lack structured comparison tables — opportunity to own the SERP with better formatting.' },
      { title: 'Multi-platform citation gap', text: 'ChatGPT and Claude both struggle to give accurate pricing — your content fills this void.' },
    ],
    relatedQueries: [
      { query: 'best AI app builder pricing', fanouts: 8, intent: 'Commercial' },
      { query: 'lovable vs bolt.new cost', fanouts: 4, intent: 'Commercial' },
      { query: 'AI app builder ROI comparison', fanouts: 2, intent: 'Informational' },
    ],
    createdAt: 'Mar 18, 2026',
    activityLog: [
      { action: 'Created from gap analysis pipeline v2', date: 'Mar 18, 2026', by: 'System' },
      { action: 'Reviewed by shank keshri', date: 'Mar 26, 2026', by: 'shank keshri' },
    ],
  },
  {
    id: 'IH-002',
    title: 'Lovable vs Bolt.new vs Cursor: Complete Platform Comparison for 2026',
    cluster: 'Competitive Landscape',
    subcluster: 'Platform Comparisons',
    stage: 'MOFU',
    intent: 'Commercial',
    format: 'Comparison',
    source: 'gap',
    personaScores: { sf: 88, pm: 82, da: 71, te: 55 },
    persona: 'pm',
    estCitations: 19,
    citationOpp: 0.85,
    priorityScore: 0.82,
    effort: 'high',
    estDays: 7,
    competitors: [
      { domain: 'g2.com', title: 'AI App Builders Compared', url: 'g2.com/categories/ai-app-builders', words: 3200, faq: false, tables: true, rank: 1 },
      { domain: 'cursor.com', title: 'Cursor vs Alternatives', url: 'cursor.com/blog/alternatives', words: 2100, faq: true, tables: false, rank: 2 },
    ],
    reasons: [
      { title: 'Dominant search pattern', text: '"X vs Y" queries account for 38% of all commercial-intent searches in the AI builder category.' },
      { title: 'Platform citation opportunity', text: 'Perplexity and Google AI Overview currently cite G2 — original comparison content can displace this.' },
      { title: 'Cross-persona relevance', text: 'Scores above 70% for 3 of 4 personas, maximizing content ROI.' },
    ],
    relatedQueries: [
      { query: 'lovable vs bolt.new vs cursor', fanouts: 12, intent: 'Commercial' },
      { query: 'best AI app builder 2026', fanouts: 6, intent: 'Commercial' },
      { query: 'AI code generation platform comparison', fanouts: 3, intent: 'Informational' },
    ],
    createdAt: 'Mar 18, 2026',
    activityLog: [
      { action: 'Created from gap analysis pipeline v2', date: 'Mar 18, 2026', by: 'System' },
    ],
  },
  {
    id: 'IH-003',
    title: 'How to Connect External APIs in Lovable: A Developer\'s Guide',
    cluster: 'Developer Experience',
    subcluster: 'API Integration Patterns',
    stage: 'MOFU',
    intent: 'Informational',
    format: 'Tutorial',
    source: 'strategic',
    initiative: 'Technical Engineer Expansion',
    personaScores: { sf: 45, pm: 52, da: 68, te: 94 },
    persona: 'te',
    estCitations: 15,
    citationOpp: 0.74,
    priorityScore: 0.78,
    effort: 'medium',
    estDays: 4,
    competitors: [
      { domain: 'bolt.new', title: 'API Integration Guide', url: 'bolt.new/docs/api-integration', words: 2400, faq: true, tables: false, rank: 1 },
      { domain: 'replit.com', title: 'External APIs in Replit', url: 'replit.com/docs/external-apis', words: 1800, faq: false, tables: true, rank: 2 },
    ],
    reasons: [
      { title: 'Technical audience gap', text: 'No existing content addresses API integration patterns specific to no-code/low-code AI builders.' },
      { title: 'High developer intent', text: 'Technical engineers searching for API guides have 4.1x higher activation rates.' },
      { title: 'Strategic initiative alignment', text: 'Core content piece for the Technical Engineer Expansion initiative.' },
    ],
    relatedQueries: [
      { query: 'connect API to lovable app', fanouts: 6, intent: 'Informational' },
      { query: 'lovable API integration tutorial', fanouts: 4, intent: 'Informational' },
      { query: 'no-code API connection guide', fanouts: 3, intent: 'Informational' },
    ],
    createdAt: 'Mar 20, 2026',
    activityLog: [
      { action: 'Generated from initiative: Technical Engineer Expansion', date: 'Mar 20, 2026', by: 'System' },
    ],
  },
  {
    id: 'IH-004',
    title: 'SOC 2 Compliance for AI-Built Applications: What Enterprise Buyers Need to Know',
    cluster: 'Security & Compliance',
    subcluster: 'SOC 2 & Enterprise Security',
    stage: 'BOFU',
    intent: 'Commercial',
    format: 'Guide',
    source: 'strategic',
    initiative: 'Enterprise Security Push',
    personaScores: { sf: 35, pm: 91, da: 48, te: 62 },
    persona: 'pm',
    estCitations: 12,
    citationOpp: 0.65,
    priorityScore: 0.75,
    effort: 'high',
    estDays: 6,
    competitors: [
      { domain: 'snyk.io', title: 'SOC 2 for Modern Apps', url: 'snyk.io/blog/soc2-compliance', words: 3100, faq: true, tables: true, rank: 1 },
    ],
    reasons: [
      { title: 'Enterprise buying signal', text: 'SOC 2 queries correlate with 67% of enterprise purchase decisions in the AI platform space.' },
      { title: 'Compliance content vacuum', text: 'No AI builder has authoritative compliance content — first-mover advantage is significant.' },
      { title: 'Strategic initiative alignment', text: 'Anchors the Enterprise Security Push with decision-stage content.' },
    ],
    relatedQueries: [
      { query: 'AI app builder SOC 2 compliance', fanouts: 5, intent: 'Commercial' },
      { query: 'is lovable SOC 2 certified', fanouts: 3, intent: 'Commercial' },
      { query: 'enterprise AI builder security', fanouts: 4, intent: 'Informational' },
    ],
    createdAt: 'Mar 19, 2026',
    activityLog: [
      { action: 'Generated from initiative: Enterprise Security Push', date: 'Mar 19, 2026', by: 'System' },
      { action: 'Flagged as high priority by shank keshri', date: 'Mar 24, 2026', by: 'shank keshri' },
    ],
  },
  {
    id: 'IH-005',
    title: 'Exporting and Customizing Code from Lovable: Full Ownership Guide',
    cluster: 'Developer Experience',
    subcluster: 'Code Export & Customization',
    stage: 'TOFU',
    intent: 'Informational',
    format: 'Guide',
    source: 'strategic',
    initiative: 'Technical Engineer Expansion',
    personaScores: { sf: 58, pm: 44, da: 72, te: 89 },
    persona: 'te',
    estCitations: 14,
    citationOpp: 0.70,
    priorityScore: 0.73,
    effort: 'low',
    estDays: 3,
    competitors: [
      { domain: 'cursor.com', title: 'Code Export Features', url: 'cursor.com/docs/export', words: 1600, faq: false, tables: false, rank: 1 },
      { domain: 'v0.dev', title: 'Downloading Your v0 Code', url: 'v0.dev/docs/code-export', words: 900, faq: false, tables: false, rank: 2 },
    ],
    reasons: [
      { title: 'Vendor lock-in concern', text: 'Code ownership is the #1 objection from technical evaluators — this content directly addresses it.' },
      { title: 'Weak existing content', text: 'Competitor docs are thin (900-1600 words) and lack practical examples.' },
      { title: 'Top-of-funnel capture', text: 'Informational queries about code export reach developers early in their evaluation journey.' },
    ],
    relatedQueries: [
      { query: 'can you export code from lovable', fanouts: 7, intent: 'Informational' },
      { query: 'lovable code ownership', fanouts: 3, intent: 'Informational' },
      { query: 'AI builder vendor lock-in', fanouts: 2, intent: 'Commercial' },
    ],
    createdAt: 'Mar 20, 2026',
    activityLog: [
      { action: 'Generated from initiative: Technical Engineer Expansion', date: 'Mar 20, 2026', by: 'System' },
    ],
  },
  {
    id: 'IH-006',
    title: 'Building a SaaS MVP with Lovable: From Idea to Launch in 48 Hours',
    cluster: 'Platform Capabilities',
    subcluster: 'UI/UX Generation',
    stage: 'TOFU',
    intent: 'Informational',
    format: 'Tutorial',
    source: 'gap',
    personaScores: { sf: 95, pm: 62, da: 81, te: 38 },
    persona: 'sf',
    estCitations: 18,
    citationOpp: 0.71,
    priorityScore: 0.77,
    effort: 'medium',
    estDays: 5,
    competitors: [
      { domain: 'bolt.new', title: 'Build Your First App', url: 'bolt.new/tutorials/first-app', words: 2200, faq: true, tables: false, rank: 1 },
      { domain: 'replit.com', title: 'Ship a SaaS in a Weekend', url: 'replit.com/blog/weekend-saas', words: 2600, faq: false, tables: false, rank: 2 },
      { domain: 'v0.dev', title: 'Quick Start Guide', url: 'v0.dev/docs/quickstart', words: 1400, faq: false, tables: true, rank: 3 },
    ],
    reasons: [
      { title: 'Solo founder magnet', text: '95% persona affinity — this is the exact content solo founders search before choosing a platform.' },
      { title: 'Narrative-driven format', text: 'Tutorial content with real outcomes generates 2.8x more social shares and backlinks.' },
      { title: 'Citation momentum', text: 'Similar "build in X hours" content is already cited by ChatGPT for competitor platforms.' },
    ],
    relatedQueries: [
      { query: 'build SaaS with AI no code', fanouts: 9, intent: 'Informational' },
      { query: 'lovable tutorial build app', fanouts: 5, intent: 'Informational' },
      { query: 'fastest way to build MVP 2026', fanouts: 3, intent: 'Informational' },
    ],
    createdAt: 'Mar 18, 2026',
    activityLog: [
      { action: 'Created from gap analysis pipeline v2', date: 'Mar 18, 2026', by: 'System' },
    ],
  },
  {
    id: 'IH-007',
    title: 'GDPR Compliance for No-Code AI Platforms: A Complete Guide',
    cluster: 'Security & Compliance',
    subcluster: 'Data Privacy & GDPR',
    stage: 'MOFU',
    intent: 'Informational',
    format: 'Guide',
    source: 'strategic',
    initiative: 'Enterprise Security Push',
    personaScores: { sf: 42, pm: 86, da: 55, te: 68 },
    persona: 'pm',
    estCitations: 10,
    citationOpp: 0.68,
    priorityScore: 0.70,
    effort: 'high',
    estDays: 6,
    competitors: [
      { domain: 'snyk.io', title: 'GDPR for Developers', url: 'snyk.io/learn/gdpr', words: 2900, faq: true, tables: true, rank: 1 },
      { domain: 'replit.com', title: 'Data Privacy at Replit', url: 'replit.com/site/privacy', words: 1100, faq: false, tables: false, rank: 2 },
    ],
    reasons: [
      { title: 'Regulatory pressure', text: 'GDPR queries for AI platforms spiked 140% in Q1 2026 as EU enforcement increases.' },
      { title: 'Trust-building content', text: 'Compliance guides establish authority with product managers evaluating enterprise readiness.' },
      { title: 'Cross-platform citation gap', text: 'No AI builder has comprehensive GDPR content — Perplexity cites generic legal sites instead.' },
    ],
    relatedQueries: [
      { query: 'GDPR compliance AI app builder', fanouts: 4, intent: 'Informational' },
      { query: 'lovable data privacy policy', fanouts: 3, intent: 'Informational' },
      { query: 'no-code platform GDPR', fanouts: 2, intent: 'Commercial' },
    ],
    createdAt: 'Mar 19, 2026',
    activityLog: [
      { action: 'Generated from initiative: Enterprise Security Push', date: 'Mar 19, 2026', by: 'System' },
    ],
  },
  {
    id: 'IH-008',
    title: 'Top 10 AI App Builders for Agencies: Feature Comparison & Pricing',
    cluster: 'Competitive Landscape',
    subcluster: 'Platform Comparisons',
    stage: 'MOFU',
    intent: 'Commercial',
    format: 'Listicle',
    source: 'gap',
    personaScores: { sf: 55, pm: 61, da: 93, te: 40 },
    persona: 'da',
    estCitations: 16,
    citationOpp: 0.79,
    priorityScore: 0.76,
    effort: 'medium',
    estDays: 5,
    competitors: [
      { domain: 'g2.com', title: 'Best AI App Builders for Agencies', url: 'g2.com/best-ai-builders-agencies', words: 2800, faq: false, tables: true, rank: 1 },
      { domain: 'emergent.sh', title: 'Agency Tools Roundup', url: 'emergent.sh/blog/agency-tools-2026', words: 1900, faq: true, tables: false, rank: 2 },
    ],
    reasons: [
      { title: 'Underserved persona', text: 'Agency owners are rarely targeted by AI builder content despite high LTV and multi-seat potential.' },
      { title: 'Listicle citation format', text: 'AI engines prefer structured list content for "top X" queries — 71% of cited results are listicles.' },
      { title: 'Revenue multiplication', text: 'Agency owners represent 3-5 seats per conversion vs 1 seat for individual users.' },
    ],
    relatedQueries: [
      { query: 'best AI app builder for agencies', fanouts: 7, intent: 'Commercial' },
      { query: 'agency AI development tools', fanouts: 4, intent: 'Commercial' },
      { query: 'white label AI app builder', fanouts: 3, intent: 'Commercial' },
    ],
    createdAt: 'Mar 18, 2026',
    activityLog: [
      { action: 'Created from gap analysis pipeline v2', date: 'Mar 18, 2026', by: 'System' },
    ],
  },
  {
    id: 'IH-009',
    title: 'Integrating Stripe Payments in Lovable Apps: Step-by-Step',
    cluster: 'Platform Capabilities',
    subcluster: 'Database & Backend Integration',
    stage: 'MOFU',
    intent: 'Transactional',
    format: 'Tutorial',
    source: 'strategic',
    initiative: 'Technical Engineer Expansion',
    personaScores: { sf: 82, pm: 55, da: 70, te: 88 },
    persona: 'te',
    estCitations: 11,
    citationOpp: 0.78,
    priorityScore: 0.72,
    effort: 'low',
    estDays: 3,
    competitors: [],
    reasons: [
      { title: 'Zero competition', text: 'No authoritative content exists for Stripe integration in AI app builders — pure first-mover territory.' },
      { title: 'Transactional intent', text: 'Users searching for payment integration are actively building — highest activation signal.' },
      { title: 'Revenue enablement', text: 'Payment integration content directly correlates with users upgrading to paid plans.' },
    ],
    relatedQueries: [
      { query: 'add Stripe to lovable app', fanouts: 5, intent: 'Informational' },
      { query: 'no-code payment integration', fanouts: 4, intent: 'Commercial' },
      { query: 'lovable Stripe tutorial', fanouts: 2, intent: 'Informational' },
    ],
    createdAt: 'Mar 20, 2026',
    activityLog: [
      { action: 'Generated from initiative: Technical Engineer Expansion', date: 'Mar 20, 2026', by: 'System' },
    ],
  },
  {
    id: 'IH-010',
    title: 'How to Migrate from Bubble to Lovable: Complete Migration Playbook',
    cluster: 'Platform Capabilities',
    subcluster: 'Code Generation Quality',
    stage: 'BOFU',
    intent: 'Navigational',
    format: 'Case Study',
    source: 'custom',
    personaScores: { sf: 76, pm: 68, da: 82, te: 45 },
    persona: 'da',
    estCitations: 7,
    citationOpp: 0.61,
    priorityScore: 0.55,
    effort: 'low',
    estDays: 4,
    competitors: [
      { domain: 'bolt.new', title: 'Migrating from Bubble', url: 'bolt.new/guides/bubble-migration', words: 1800, faq: false, tables: true, rank: 1 },
    ],
    reasons: [
      { title: 'Migration capture', text: 'Bubble users actively seeking alternatives represent a high-intent audience with existing projects.' },
      { title: 'Competitive displacement', text: 'Only bolt.new has migration content — opportunity to capture this traffic with a better guide.' },
      { title: 'Case study format', text: 'Real migration stories build trust and are preferred by AI engines for recommendation queries.' },
    ],
    relatedQueries: [
      { query: 'migrate from Bubble to lovable', fanouts: 3, intent: 'Informational' },
      { query: 'Bubble alternative 2026', fanouts: 5, intent: 'Commercial' },
      { query: 'switch from Bubble to AI builder', fanouts: 2, intent: 'Informational' },
    ],
    createdAt: 'Mar 25, 2026',
    activityLog: [
      { action: 'Manually added by shank keshri', date: 'Mar 25, 2026', by: 'shank keshri' },
      { action: 'AI enrichment completed', date: 'Mar 25, 2026', by: 'System' },
    ],
  },
];

// ─── Rejected Items ──────────────────────────────────────

export const INITIAL_REJECTED: RejectedItem[] = [
  { id: 'IH-R01', title: 'Scaling AI Apps: Performance Benchmarks', cluster: 'Deployment & Operations', reason: 'Low priority — revisit Q3', date: 'Mar 22', rejectedBy: 'shank keshri', stage: 'TOFU' },
  { id: 'IH-R02', title: 'Data Privacy in AI Builders: How Platforms Handle Your Data', cluster: 'Security & Compliance', reason: 'Overlaps with GDPR guide (IH-007)', date: 'Mar 20', rejectedBy: 'shank keshri', stage: 'MOFU' },
];

// ─── Brand ID Prefix ─────────────────────────────────────

export const BRAND_PREFIX = 'IH'; // derived from workspace name "Insight Health"
export const formatId = (num: number) => `${BRAND_PREFIX}-${String(num).padStart(3, '0')}`;

// ─── Persona Labels ──────────────────────────────────────

export const PERSONA_MAP: Record<string, { short: string; full: string }> = {
  sf: { short: 'SF', full: 'Solo Founder' },
  pm: { short: 'PM', full: 'Product Manager' },
  da: { short: 'DA', full: 'Agency Owner' },
  te: { short: 'TE', full: 'Technical Engineer' },
};

// ─── Helpers ─────────────────────────────────────────────

export function getClusterForSubcluster(subclusterName: string): string | undefined {
  for (const c of CLUSTERS) {
    for (const sc of c.subclusters) {
      if (sc.name === subclusterName) return c.name;
    }
  }
  return undefined;
}

export function getAssignmentsForSubcluster(assignments: Assignment[], subclusterId: string): Assignment[] {
  const cluster = CLUSTERS.find(c => c.subclusters.some(sc => sc.id === subclusterId));
  const subcluster = cluster?.subclusters.find(sc => sc.id === subclusterId);
  if (!subcluster) return [];
  return assignments.filter(a => a.subcluster === subcluster.name);
}

export function getAssignmentsForCluster(assignments: Assignment[], clusterId: string): Assignment[] {
  const cluster = CLUSTERS.find(c => c.id === clusterId);
  if (!cluster) return [];
  const subNames = cluster.subclusters.map(sc => sc.name);
  return assignments.filter(a => subNames.includes(a.subcluster));
}
