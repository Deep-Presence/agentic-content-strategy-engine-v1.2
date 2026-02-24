export interface ContentStartInput {
  company_name: string;
  domain: string;
  gap_slug?: string;
  max_briefs?: number;
  max_concurrent_workers?: number;
  max_revision_cycles?: number;
  auto_approve?: boolean;
  skip_stages?: number[];
}

export interface ContentApproval {
  brief_id: string;
  decision: 'approve' | 'edit' | 'reject';
  editor_notes?: string;
}

export interface ContentBriefItem {
  id: string;
  title: string;
  status: ContentBriefStatus;
  content_type: ContentType;
  cluster: string;
  target_word_count: number;
  citability_score?: number;
  cycle_id?: string;
  created_at: string;
  updated_at: string;
}

export type ContentBriefStatus =
  | 'suggested' | 'approved' | 'research' | 'drafting'
  | 'enriching' | 'formatting' | 'evaluating' | 'review'
  | 'published' | 'draft_saved' | 'rejected';

export type ContentType = 'blog' | 'guide' | 'case_study' | 'product_page';

export interface Cycle {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  briefs: ContentBriefItem[];
  completed_count: number;
  total_count: number;
}

export type ContentEvent =
  | 'planning_start' | 'planning_complete'
  | 'worker_start' | 'worker_complete'
  | 'eval_start' | 'eval_pass' | 'eval_fail_revise'
  | 'hitl_waiting' | 'hitl_approved' | 'hitl_rejected'
  | 'completed' | 'failed' | 'cancelled';
