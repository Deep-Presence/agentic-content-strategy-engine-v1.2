import type { GapContextSummaryAPI } from '../_lib/types';

// ---------------------------------------------------------------------------
// Backend-aligned status enum (mirrors core/models/pipeline_status.py)
// ---------------------------------------------------------------------------

export type BriefPipelineStatus =
  | 'suggested'
  | 'gap_analysis_pending'
  | 'gap_analysis'
  | 'gap_analysis_complete'
  | 'content_queued'
  | 'briefing'
  | 'brief_review'
  | 'pending_brief_approval'
  | 'approved'
  | 'outlining'
  | 'drafting'
  | 'linking'
  | 'enriching'
  | 'evaluating'
  | 'revising'
  | 'review'
  | 'pending_content_approval'
  | 'completed'
  | 'published'
  | 'rejected'
  | 'failed';

// ---------------------------------------------------------------------------
// Kanban columns (derived from status via status-adapter)
// ---------------------------------------------------------------------------

export type KanbanColumn = 'triage' | 'agent' | 'human' | 'done';

// ---------------------------------------------------------------------------
// Content metadata types
// ---------------------------------------------------------------------------

export type ContentType = 'HOW_TO' | 'COMPARISON' | 'GUIDE' | 'LONG_BLOG' | 'PILLAR_PAGE';
export type Priority = 'P0' | 'P1' | 'P2';

export interface AgentProgress {
  pct: number;
  currentTask: string;
  wordsCurrent?: number;
  wordsTarget?: number;
  sectionsComplete?: number;
  sectionsTotal?: number;
  gaStepName?: string;
  gaStepNum?: number;
  gaTotalSteps?: number;
}

export interface BriefSource {
  name: string;
  domain: string;
  engines: number;
  url?: string;
  authorityType?: string;
  wordCount?: number;
}

export interface BriefContent {
  sections: string[];
  targetWords: number;
  exemplarCount: number;
  sources: BriefSource[];
  reasons: string[];
}

export interface ArticleSection {
  heading: string;
  words: number;
  content: string;
}

export interface CitPrediction {
  engine: string;
  score: number;
}

export interface ComplianceItem {
  label: string;
  current: number;
  target: number;
}

export interface EEATScore {
  overall: number;
  experience: number;
  expertise: number;
  authoritativeness: number;
  trustworthiness: number;
}

export interface InterlinkItem {
  title: string;
  path: string;
  linked: boolean;
}

export interface ArticleContent {
  wordCount: number;
  targetWords: number;
  voiceCompliance: number;
  sections: ArticleSection[];
  citPrediction: CitPrediction[];
  compliance: ComplianceItem[];
  eeat: EEATScore;
  interlinks: InterlinkItem[];
}

export interface ContentMetadata {
  slug: string;
  metaTitle: string;
  metaDescription: string;
  ogImageUrl?: string;
  canonicalUrl: string;
  schemaMarkup: boolean;
  publishDate?: string;
  author?: string;
  tags: string[];
}

// ---------------------------------------------------------------------------
// Content card — column & label derived from status via status-adapter
// ---------------------------------------------------------------------------

export interface ContentCard {
  id: string;
  /** Human-readable display ID from Topic Discovery (e.g. "WE-003") */
  displayId?: string;
  /** Durable TD-entry topic-run identity */
  topicRunId?: string;
  /** Durable TD-entry batch identity */
  batchRunId?: string;
  /** Monotonic durable topic-run sequence for out-of-order protection */
  topicRunSeq?: number;
  title: string;
  type: ContentType;
  cluster: string;
  gap: number;
  score: number;
  priority: Priority;
  readTime: number;
  competitor: string;

  /** Raw backend BriefPipelineStatus — single source of truth for card state */
  status: BriefPipelineStatus;

  /** Pipeline task_id for SSE subscription + HITL API calls */
  taskId?: string;

  /** Topic assignment ID from planner (for GA-phase cards) */
  topicAssignmentId?: string;
  /** Buyer stage from planner (TOFU/MOFU/BOFU) */
  buyerStage?: string;
  /** Origin: manual entry, planner approval, or autonomous pipeline */
  source?: 'manual' | 'planner' | 'autonomous';
  /** Gap analysis run ID (set after GA completes, used to start CE) */
  gaRunId?: string;
  /** Effective slug scope (company or company__product, used in startProduction) */
  effectiveSlug?: string;
  /** Intent type from planner (informational/commercial/navigational/transactional) */
  intentType?: string;
  /** Primary target persona display name */
  personaName?: string;
  /** Persona identifier */
  personaId?: string;
  /** Persona affinity scores: {persona_id: 0-1} */
  personaAffinity?: Record<string, number>;
  /** Priority factor scores: {factor_name: 0-1} */
  priorityFactors?: Record<string, number>;
  /** Content format from planner (e.g. comprehensive_guide) */
  contentFormat?: string;
  /** Estimated word count from planner */
  estimatedWordCount?: number;
  /** Citation opportunity score (0-1) */
  citationOpp?: number;
  /** Topic description */
  description?: string;
  /** Target keywords: {primary, secondary[]} */
  targetKeywords?: { primary?: string; secondary?: string[] };
  /** Content angle — why this topic */
  contentAngle?: string;

  /** Full gap context from gap analysis (preserved from brief list API) */
  gapContext?: GapContextSummaryAPI;

  /** Backend cycle/session identifier */
  cycleId?: string;
  targetWordCount?: number;
  createdAt?: string;
  updatedAt?: string;

  agentProgress?: AgentProgress;
  briefContent?: BriefContent;
  articleContent?: ArticleContent;
  metadata?: ContentMetadata;
}

// ---------------------------------------------------------------------------
// Cycle (time-based content grouping)
// ---------------------------------------------------------------------------

export interface Cycle {
  id: string;
  name: string;
  weekOf: string;
  status: 'active' | 'archived';
  stats: {
    total: number;
    queue: number;
    humanReview: number;
    agentWork: number;
    published: number;
    avgCitationScore: number;
    completionPct: number;
  };
}

// ---------------------------------------------------------------------------
// Inline review comments (HITL-3 feedback)
// ---------------------------------------------------------------------------

export interface ReviewComment {
  id: string;
  selectedText: string;
  feedback: string;
  createdAt: string;
}
