import type { ContentBrief, Platform } from '@/types';

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
  { id: 'triage', label: 'Triage', color: 'neutral' },
  { id: 'brief', label: 'Brief', color: 'info' },
  { id: 'generating', label: 'Generating', color: 'warning' },
  { id: 'review', label: 'Review', color: 'error' },
  { id: 'approved', label: 'Approved', color: 'success' },
];

export const agentActivities = [
  { id: '1', agent: 'Strategic Planner', action: 'Analyzing query scorecards...', time: '14:20', type: 'strategy' as const },
  { id: '2', agent: 'Brief Builder', action: 'Content brief generated', time: '14:32', type: 'writer' as const },
  { id: '3', agent: 'Writer Agent', action: 'Started generation', time: '14:35', type: 'writer' as const },
  { id: '4', agent: 'Eval Agent', action: 'Evaluation complete', time: '14:50', type: 'eval' as const },
  { id: '5', agent: 'Strategy Agent', action: 'Content ready for human review', time: '15:05', type: 'strategy' as const },
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
