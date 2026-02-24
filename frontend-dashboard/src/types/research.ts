export interface ResearchStartInput {
  company_name: string;
  domain: string;
  seed_urls?: string[];
  stages?: ('company' | 'persona' | 'style')[];
  max_personas?: number;
  auto_approve?: boolean;
}

export interface ResearchApproval {
  decision: 'approve' | 'revise' | 'reject';
  revision_note?: string;
}

export type ResearchStage = 'company' | 'persona' | 'style_guide';

export type ResearchEvent =
  | 'company_start' | 'company_draft' | 'company_approved'
  | 'persona_start' | 'persona_draft' | 'persona_approved'
  | 'style_start' | 'style_draft' | 'style_approved'
  | 'completed' | 'failed' | 'cancelled';
