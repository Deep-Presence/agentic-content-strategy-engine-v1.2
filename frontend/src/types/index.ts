// === Core Entities ===
export interface Company { id: string; name: string; domain: string; createdAt: string; }
export interface User { id: string; name: string; email: string; role: 'admin' | 'editor' | 'viewer'; avatarUrl?: string; }
export interface Workspace { company: Company; projects: Project[]; }
export interface Project { id: string; name: string; domain: string; }

// === 5 AI Platforms (used everywhere) ===
export type Platform = 'chatgpt' | 'claude' | 'perplexity' | 'google_ai_overview' | 'gemini';

// === Gap Analysis ===
export interface Query {
  id: string;
  text: string;
  cluster: string;
  classification: 'significant_gap' | 'gap_to_close' | 'roughly_equal' | 'company_wins';
  gap: number;
  avgCitationSimilarity: number;
  bestCompanyUnit: { id: string; url: string; similarity: number; snippet: string; };
  citedExemplars: CitedExemplar[];
  companyCited: boolean;
  platforms: Platform[];
}
export interface CitedExemplar {
  url: string; domain: string; similarity: number; snippet: string; structure: PageStructure;
}
export interface PageStructure {
  words: number; paragraphs: number; headers: number; lists: number; stats: number; citations: number; readingLevel?: number;
}
export interface GapReport {
  summary: { spaScore: number; meanCitationSimilarity: number; meanCompanySimilarity: number; totalQueries: number; totalCitations: number; averageGap: number; };
  queries: Query[];
  clusters: Cluster[];
}
export interface Cluster {
  id: string; name: string; queryCount: number; citationsAnalyzed: number; requiredElements: string[];
  avgWordCount: number; faqRate: number; tableRate: number; dominantContentType: string; dominantAuthority: string;
}

// === Site Audit ===
export interface SiteAudit {
  overallScore: number; grade: string; pagesCrawled: number; totalFindings: number;
  dimensions: AuditDimension[]; botAccess: { bot: string; allowed: boolean; }[];
  aeoReadiness: { avgSnippetReadiness: number; pagesWithStructuredData: number; avgQuestionHeadingRatio: number; };
  findings: AuditFinding[];
}
export interface AuditDimension { name: string; score: number; weight: number; weighted: number; findings: number; }
export interface AuditFinding { severity: 'critical' | 'high' | 'medium' | 'low'; dimension: string; title: string; affectedPages: number; recommendation: string; }

// === Content Pipeline ===
export interface ContentBrief {
  id: string; title: string; targetCluster: string; targetQuery: string;
  stage: 'triage' | 'brief' | 'generating' | 'review' | 'approved' | 'published';
  personas: string[]; cpsPredict: Record<Platform, number>; cpsActual?: Record<Platform, number>;
  structuralTargets: PageStructure; createdAt: string; publishedAt?: string; publishedUrl?: string;
}
export interface ContentPiece {
  briefId: string; stage: 'outline' | 'draft' | 'enriched' | 'final' | 'formatted';
  markdown: string; wordCount: number; structuralAnalysis: PageStructure;
  voiceComplianceScore: number; interlinkSuggestions: { url: string; anchorText: string; applied: boolean; }[];
}
export interface ContentCycle { id: string; name: string; items: ContentBrief[]; startDate: string; endDate: string; }

// === Knowledge Base, Voice Guide, Personas ===
export interface Persona {
  id: string; name: string; title: string; client: string; version: string;
  sections: { title: string; content: string; }[];
}
export interface KBDocument {
  id: string; type: 'company_overview' | 'brand_perception' | 'competitor_registry' | 'customer_reviews' | 'weakness_analysis';
  client: string; version: string; markdown: string; lastUpdated: string; wordCount: number;
}
export interface VoiceGuide {
  identity: string; registers: VoiceRegister[];
  styleMetrics: Record<string, { default: string; tactical: string; analytical: string; }>;
  lexicon: { favor: LexiconItem[]; avoid: LexiconItem[]; }; antiPatterns: string[];
  workedExamples: { title: string; before: string; after: string; explanation: string; }[];
}
export interface VoiceRegister { name: 'tactical' | 'analytical' | 'empathy'; sentenceLength: string; paragraphLength: string; tone: string; pace: string; }
export interface LexiconItem { term: string; usage: string; frequency: string; }

// === Topics ===
export interface Topic {
  id: string; title: string; priority: 'high' | 'medium' | 'low'; personas: string[];
  coverage: 'covered' | 'gap' | 'partial'; cluster: string; subtopics: string[]; gapScore: number; sources: string[];
}

// === Attribution (demo) ===
export interface AttributionMetrics { aiSourcedTraffic: number; demoRequests: number; pipelineGenerated: number; revenueAttributed: number; }
export interface AttributionFunnelStep { name: string; count: number; conversionRate: number; }
export interface ContentROI { title: string; citationsEarned: number; aiReferredSessions: number; conversions: number; revenue: number; cpsPredicted: number; cpsActual: number; }

// === Embedding Space ===
export interface EmbeddingPoint { id: string; type: 'company' | 'citation' | 'query'; x: number; y: number; cluster: string; label: string; url?: string; similarity?: number; }

// === Notifications ===
export interface Notification {
  id: string; type: 'pipeline_complete' | 'hitl_ready' | 'content_published' | 'citation_gained' | 'system_alert';
  title: string; message: string; read: boolean; createdAt: string; actionUrl?: string;
}

// === Settings ===
export interface TeamMember { id: string; name: string; email: string; role: 'admin' | 'editor' | 'viewer'; status: 'active' | 'invited'; }
export interface ModelConfig { agentType: string; provider: string; model: string; apiKeySet: boolean; }
export interface Integration { id: string; type: 'cms' | 'crm' | 'analytics'; name: string; connected: boolean; lastSync?: string; }
