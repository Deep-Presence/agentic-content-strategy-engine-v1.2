export interface ResearchStartInput {
  company_name: string;
  domain: string;
  seed_urls?: string[];
  stages?: ('company' | 'persona' | 'style_guide')[];
  max_personas?: number;
  auto_approve?: boolean;
  language?: string;
  region?: string;
  internal_sources?: string[];
  additional_constraints?: string;
}

export interface ResearchApproval {
  decision: 'approve' | 'revise' | 'reject';
  revision_note?: string;
}

export type ResearchStage = 'company' | 'persona' | 'style_guide';

export type ResearchEvent =
  | 'company_start' | 'company_draft' | 'company_approved'
  | 'persona_start' | 'persona_draft' | 'persona_approved'
  | 'style_guide_start' | 'style_guide_draft' | 'style_guide_approved'
  | 'completed' | 'failed' | 'cancelled';
