// Content Planner — Data Layer
// Types for assignments, clusters, initiatives, rejected items
// + mock data for InitiativesSidebar (only remaining mock consumer)

export interface TargetKeywords {
  primary: string;
  secondary: string[];
}

export interface RelatedQuery {
  query: string;
  intent: 'Informational' | 'Commercial' | 'Navigational' | 'Transactional';
}

export interface ActivityEntry {
  action: string;
  date: string | null;
  by: string;
}

export interface Assignment {
  id: string;
  displayId: string;
  title: string;
  description: string;
  cluster: string;
  subcluster: string;
  stage: 'TOFU' | 'MOFU' | 'BOFU';
  intent: 'Informational' | 'Commercial' | 'Navigational' | 'Transactional';
  format: string | null;
  source: 'gap' | 'strategic' | 'custom';
  initiative?: string;
  personaScores: Record<string, number>;
  persona: string;
  citationOpp: number;
  priorityScore: number;
  effort: 'low' | 'medium' | 'high' | null;
  estDays: number | null;
  wordCount: number | null;
  contentFormat: string | null;
  targetKeywords: TargetKeywords;
  reasons: Array<{ title: string; text: string }>;
  relatedQueries: RelatedQuery[];
  createdAt: string;
  activityLog: ActivityEntry[];
  priorityFactors: Record<string, number>;
}

export interface Cluster {
  id: string;
  name: string;
  subclusters: Array<{ id: string; name: string; description: string; citOpp: number }>;
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

// ─── Mock Assignments (used ONLY by InitiativesSidebar) ──

export const ASSIGNMENTS: Assignment[] = [
  {
    id: 'mock-003',
    displayId: 'IH-003',
    title: 'How to Connect External APIs in Lovable: A Developer\'s Guide',
    description: 'Step-by-step tutorial for integrating external REST APIs into Lovable-built applications.',
    cluster: 'Developer Experience',
    subcluster: 'API Integration Patterns',
    stage: 'MOFU',
    intent: 'Informational',
    format: 'How-to Guide',
    source: 'strategic',
    initiative: 'Technical Engineer Expansion',
    personaScores: { sf: 45, pm: 52, da: 68, te: 94 } as Record<string, number>,
    persona: 'te',
    citationOpp: 0.74,
    priorityScore: 0.78,
    effort: 'medium',
    estDays: 4,
    wordCount: 2200,
    contentFormat: 'how_to_guide',
    targetKeywords: { primary: 'lovable API integration', secondary: ['connect API to lovable app', 'lovable API integration tutorial', 'no-code API connection guide'] },
    reasons: [
      { title: 'Content Angle', text: 'Step-by-step tutorial for integrating external REST APIs into Lovable-built applications.' },
      { title: 'Strong conversion potential', text: 'Scores 95% \u2014 strong conversion signal from this topic' },
    ],
    relatedQueries: [
      { query: 'connect API to lovable app', intent: 'Informational' },
      { query: 'lovable API integration tutorial', intent: 'Informational' },
      { query: 'no-code API connection guide', intent: 'Informational' },
    ],
    createdAt: 'Mar 20, 2026',
    activityLog: [{ action: 'Discovered by topic discovery pipeline', date: null, by: 'System' }],
    priorityFactors: { strategic_centrality: 0.7, citation_opportunity: 0.74, content_authority: 0.6, conversion_potential: 0.95 },
  },
  {
    id: 'mock-004',
    displayId: 'IH-004',
    title: 'SOC 2 Compliance for AI-Built Applications: What Enterprise Buyers Need to Know',
    description: 'Comprehensive guide covering SOC 2 compliance requirements for applications built with AI platforms.',
    cluster: 'Security & Compliance',
    subcluster: 'SOC 2 & Enterprise Security',
    stage: 'BOFU',
    intent: 'Commercial',
    format: 'Comprehensive Guide',
    source: 'strategic',
    initiative: 'Enterprise Security Push',
    personaScores: { sf: 35, pm: 91, da: 48, te: 62 } as Record<string, number>,
    persona: 'pm',
    citationOpp: 0.65,
    priorityScore: 0.75,
    effort: 'high',
    estDays: 5,
    wordCount: 2800,
    contentFormat: 'comprehensive_guide',
    targetKeywords: { primary: 'AI app builder SOC 2 compliance', secondary: ['is lovable SOC 2 certified', 'enterprise AI builder security'] },
    reasons: [
      { title: 'Content Angle', text: 'Comprehensive guide covering SOC 2 compliance requirements for applications built with AI platforms.' },
      { title: 'Strong conversion potential', text: 'Scores 90% \u2014 strong conversion signal from this topic' },
    ],
    relatedQueries: [
      { query: 'AI app builder SOC 2 compliance', intent: 'Commercial' },
      { query: 'is lovable SOC 2 certified', intent: 'Commercial' },
      { query: 'enterprise AI builder security', intent: 'Informational' },
    ],
    createdAt: 'Mar 19, 2026',
    activityLog: [{ action: 'Discovered by topic discovery pipeline', date: null, by: 'System' }],
    priorityFactors: { strategic_centrality: 0.8, citation_opportunity: 0.65, content_authority: 0.7, conversion_potential: 0.9 },
  },
  {
    id: 'mock-005',
    displayId: 'IH-005',
    title: 'Exporting and Customizing Code from Lovable: Full Ownership Guide',
    description: 'Guide addressing code ownership concerns for developers evaluating Lovable.',
    cluster: 'Developer Experience',
    subcluster: 'Code Export & Customization',
    stage: 'TOFU',
    intent: 'Informational',
    format: 'Comprehensive Guide',
    source: 'strategic',
    initiative: 'Technical Engineer Expansion',
    personaScores: { sf: 58, pm: 44, da: 72, te: 89 } as Record<string, number>,
    persona: 'te',
    citationOpp: 0.70,
    priorityScore: 0.73,
    effort: 'low',
    estDays: 2,
    wordCount: 1200,
    contentFormat: 'comprehensive_guide',
    targetKeywords: { primary: 'lovable code export', secondary: ['can you export code from lovable', 'lovable code ownership', 'AI builder vendor lock-in'] },
    reasons: [
      { title: 'Content Angle', text: 'Guide addressing code ownership concerns for developers evaluating Lovable.' },
      { title: 'Strong content authority', text: 'Scores 85% \u2014 strong content authority potential' },
    ],
    relatedQueries: [
      { query: 'can you export code from lovable', intent: 'Informational' },
      { query: 'lovable code ownership', intent: 'Informational' },
      { query: 'AI builder vendor lock-in', intent: 'Commercial' },
    ],
    createdAt: 'Mar 20, 2026',
    activityLog: [{ action: 'Discovered by topic discovery pipeline', date: null, by: 'System' }],
    priorityFactors: { strategic_centrality: 0.65, citation_opportunity: 0.70, content_authority: 0.85, conversion_potential: 0.6 },
  },
  {
    id: 'mock-007',
    displayId: 'IH-007',
    title: 'GDPR Compliance for No-Code AI Platforms: A Complete Guide',
    description: 'Comprehensive GDPR compliance guide for AI-powered no-code platforms.',
    cluster: 'Security & Compliance',
    subcluster: 'Data Privacy & GDPR',
    stage: 'MOFU',
    intent: 'Informational',
    format: 'Comprehensive Guide',
    source: 'strategic',
    initiative: 'Enterprise Security Push',
    personaScores: { sf: 42, pm: 86, da: 55, te: 68 } as Record<string, number>,
    persona: 'pm',
    citationOpp: 0.68,
    priorityScore: 0.70,
    effort: 'high',
    estDays: 5,
    wordCount: 2900,
    contentFormat: 'comprehensive_guide',
    targetKeywords: { primary: 'GDPR compliance AI app builder', secondary: ['lovable data privacy policy', 'no-code platform GDPR'] },
    reasons: [
      { title: 'Content Angle', text: 'Comprehensive GDPR compliance guide for AI-powered no-code platforms.' },
      { title: 'Strong citation opportunity', text: 'Scores 68% \u2014 high likelihood of being cited by AI engines' },
    ],
    relatedQueries: [
      { query: 'GDPR compliance AI app builder', intent: 'Informational' },
      { query: 'lovable data privacy policy', intent: 'Informational' },
      { query: 'no-code platform GDPR', intent: 'Commercial' },
    ],
    createdAt: 'Mar 19, 2026',
    activityLog: [{ action: 'Discovered by topic discovery pipeline', date: null, by: 'System' }],
    priorityFactors: { strategic_centrality: 0.7, citation_opportunity: 0.68, content_authority: 0.75, conversion_potential: 0.6 },
  },
  {
    id: 'mock-009',
    displayId: 'IH-009',
    title: 'Integrating Stripe Payments in Lovable Apps: Step-by-Step',
    description: 'Step-by-step tutorial for adding Stripe payment processing to Lovable applications.',
    cluster: 'Platform Capabilities',
    subcluster: 'Database & Backend Integration',
    stage: 'MOFU',
    intent: 'Transactional',
    format: 'How-to Guide',
    source: 'strategic',
    initiative: 'Technical Engineer Expansion',
    personaScores: { sf: 82, pm: 55, da: 70, te: 88 } as Record<string, number>,
    persona: 'te',
    citationOpp: 0.78,
    priorityScore: 0.72,
    effort: 'low',
    estDays: 2,
    wordCount: 1200,
    contentFormat: 'how_to_guide',
    targetKeywords: { primary: 'add Stripe to lovable app', secondary: ['no-code payment integration', 'lovable Stripe tutorial'] },
    reasons: [
      { title: 'Content Angle', text: 'Step-by-step tutorial for adding Stripe payment processing to Lovable applications.' },
      { title: 'Strong citation opportunity', text: 'Scores 78% \u2014 high likelihood of being cited by AI engines' },
    ],
    relatedQueries: [
      { query: 'add Stripe to lovable app', intent: 'Informational' },
      { query: 'no-code payment integration', intent: 'Commercial' },
      { query: 'lovable Stripe tutorial', intent: 'Informational' },
    ],
    createdAt: 'Mar 20, 2026',
    activityLog: [{ action: 'Discovered by topic discovery pipeline', date: null, by: 'System' }],
    priorityFactors: { strategic_centrality: 0.6, citation_opportunity: 0.78, content_authority: 0.65, conversion_potential: 0.85 },
  },
];

// ─── Rejected Items ──────────────────────────────────────

export const INITIAL_REJECTED: RejectedItem[] = [
  { id: 'IH-R01', title: 'Scaling AI Apps: Performance Benchmarks', cluster: 'Deployment & Operations', reason: 'Low priority \u2014 revisit Q3', date: 'Mar 22', rejectedBy: 'shank keshri', stage: 'TOFU' },
  { id: 'IH-R02', title: 'Data Privacy in AI Builders: How Platforms Handle Your Data', cluster: 'Security & Compliance', reason: 'Overlaps with GDPR guide (IH-007)', date: 'Mar 20', rejectedBy: 'shank keshri', stage: 'MOFU' },
];

// ─── Brand ID Prefix ─────────────────────────────────────

/**
 * Derive a short prefix from the company name for human-readable IDs.
 * Multi-word → initials (e.g. "Insight Health" → "IH")
 * Single-word → first two letters uppercased (e.g. "Webflow" → "WE")
 */
export function deriveCompanyPrefix(companyName: string): string {
  const words = companyName.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return 'DP';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words.map(w => w[0]).join('').toUpperCase();
}

export const formatDisplayId = (prefix: string, num: number) =>
  `${prefix}-${String(num).padStart(3, '0')}`;

// ─── Persona Labels ──────────────────────────────────────

/**
 * Capitalize a persona_id into a display name.
 * e.g. "david" → "David", "sarah_chen" → "Sarah Chen"
 */
export function formatPersonaName(personaId: string): string {
  return personaId
    .split(/[_\s]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// ─── Helpers ─────────────────────────────────────────────

export function getClusterForSubcluster(subclusterName: string, clusters: Cluster[]): string | undefined {
  for (const c of clusters) {
    for (const sc of c.subclusters) {
      if (sc.name === subclusterName) return c.name;
    }
  }
  return undefined;
}

export function getAssignmentsForSubcluster(
  assignments: Assignment[],
  subclusterId: string,
  clusters: Cluster[],
): Assignment[] {
  const cluster = clusters.find(c => c.subclusters.some(sc => sc.id === subclusterId));
  const subcluster = cluster?.subclusters.find(sc => sc.id === subclusterId);
  if (!subcluster) return [];
  return assignments.filter(a => a.subcluster === subcluster.name);
}

export function getAssignmentsForCluster(assignments: Assignment[], clusterId: string, clusters: Cluster[]): Assignment[] {
  const cluster = clusters.find(c => c.id === clusterId);
  if (!cluster) return [];
  const subNames = cluster.subclusters.map(sc => sc.name);
  return assignments.filter(a => subNames.includes(a.subcluster));
}
