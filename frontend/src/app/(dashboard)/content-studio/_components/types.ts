export type ContentType = 'HOW_TO' | 'COMPARISON' | 'GUIDE' | 'LONG_BLOG' | 'PILLAR_PAGE';
export type Priority = 'P0' | 'P1' | 'P2';
export type Column = 'queue' | 'human' | 'agent';

export type ContentStage =
  | 'queue'
  | 'planning'
  | 'brief_generation'
  | 'brief_review'
  | 'writing'
  | 'evaluating'
  | 'article_review'
  | 'published';

export interface AgentProgress {
  pct: number;
  currentTask: string;
  wordsCurrent?: number;
  wordsTarget?: number;
  sectionsComplete?: number;
  sectionsTotal?: number;
}

export interface BriefSource {
  name: string;
  domain: string;
  engines: number;
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

export interface ContentCard {
  id: string;
  title: string;
  type: ContentType;
  cluster: string;
  gap: number;
  score: number;
  priority: Priority;
  readTime: number;
  competitor: string;
  column: Column;
  stage: ContentStage;
  stageLabel: string;
  agentProgress?: AgentProgress;
  briefContent?: BriefContent;
  articleContent?: ArticleContent;
  metadata?: ContentMetadata;
}

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
