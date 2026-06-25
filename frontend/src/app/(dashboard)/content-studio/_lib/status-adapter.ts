/**
 * Status adapter — pure mapping functions from BriefPipelineStatus to display properties.
 *
 * Maps the backend's 17-value BriefPipelineStatus enum to Kanban columns,
 * human-readable labels, badge variants, and HITL action availability.
 *
 * Source of truth: core/models/pipeline_status.py
 */

import type { BriefPipelineStatus, KanbanColumn } from '../_components/types';

// ---------------------------------------------------------------------------
// Badge variant (maps to CSS variable namespaces)
// ---------------------------------------------------------------------------

export type BadgeVariant = 'neutral' | 'teal' | 'amber' | 'success' | 'error';

// ---------------------------------------------------------------------------
// Status display properties
// ---------------------------------------------------------------------------

export interface StatusDisplay {
  /** Human-readable label for the badge / status pill */
  label: string;
  /** Badge color variant */
  badgeVariant: BadgeVariant;
  /** Whether the agent is actively processing (drives pulse animation) */
  isAgentActive: boolean;
  /** Whether to show the progress bar */
  showProgress: boolean;
  /** Whether the card needs human action */
  humanActionRequired: boolean;
}

// ---------------------------------------------------------------------------
// HITL action availability
// ---------------------------------------------------------------------------

export interface HITLActions {
  canStart: boolean;
  canStartProduction: boolean;
  canApproveBrief: boolean;
  canApproveContent: boolean;
  canReject: boolean;
  canSendBack: boolean;
  canRetry: boolean;
}

// ---------------------------------------------------------------------------
// Status → Column
// ---------------------------------------------------------------------------

const STATUS_COLUMN_MAP: Record<BriefPipelineStatus, KanbanColumn> = {
  suggested:                'triage',
  gap_analysis_pending:     'triage',
  gap_analysis:             'agent',
  gap_analysis_complete:    'triage',
  content_queued:           'triage',
  briefing:                 'agent',
  brief_review:             'human',
  pending_brief_approval:   'human',
  approved:                 'agent',
  outlining:                'agent',
  drafting:                 'agent',
  linking:                  'agent',
  enriching:                'agent',
  evaluating:               'agent',
  revising:                 'agent',
  review:                   'human',
  pending_content_approval: 'human',
  completed:                'done',
  published:                'done',
  rejected:                 'done',
  failed:                   'agent',
};

export function getColumn(status: BriefPipelineStatus): KanbanColumn {
  return STATUS_COLUMN_MAP[status] ?? 'triage';
}

// ---------------------------------------------------------------------------
// Status → Display
// ---------------------------------------------------------------------------

const STATUS_DISPLAY_MAP: Record<BriefPipelineStatus, StatusDisplay> = {
  suggested:                { label: 'Queued',                    badgeVariant: 'neutral', isAgentActive: false, showProgress: false, humanActionRequired: false },
  gap_analysis_pending:     { label: 'Analysis queued',           badgeVariant: 'neutral', isAgentActive: false, showProgress: false, humanActionRequired: false },
  gap_analysis:             { label: 'Analyzing',                 badgeVariant: 'amber',   isAgentActive: true,  showProgress: true,  humanActionRequired: false },
  gap_analysis_complete:    { label: 'Analysis ready',            badgeVariant: 'teal',    isAgentActive: false, showProgress: false, humanActionRequired: true  },
  content_queued:           { label: 'Queued for production',     badgeVariant: 'amber',   isAgentActive: false, showProgress: false, humanActionRequired: false },
  briefing:                 { label: 'Building brief',            badgeVariant: 'amber',   isAgentActive: true,  showProgress: true,  humanActionRequired: false },
  brief_review:             { label: 'Brief ready',               badgeVariant: 'teal',    isAgentActive: false, showProgress: false, humanActionRequired: true  },
  pending_brief_approval:   { label: 'Awaiting brief approval',   badgeVariant: 'teal',    isAgentActive: false, showProgress: false, humanActionRequired: true  },
  approved:                 { label: 'Approved \u2014 queued',            badgeVariant: 'amber',   isAgentActive: false, showProgress: false, humanActionRequired: false },
  outlining:                { label: 'Outlining',                  badgeVariant: 'amber',   isAgentActive: true,  showProgress: true,  humanActionRequired: false },
  drafting:                 { label: 'Drafting',                   badgeVariant: 'amber',   isAgentActive: true,  showProgress: true,  humanActionRequired: false },
  linking:                  { label: 'Linking',                    badgeVariant: 'amber',   isAgentActive: true,  showProgress: true,  humanActionRequired: false },
  enriching:                { label: 'Fact checking',              badgeVariant: 'amber',   isAgentActive: true,  showProgress: true,  humanActionRequired: false },
  evaluating:               { label: 'Evaluating',                badgeVariant: 'amber',   isAgentActive: true,  showProgress: true,  humanActionRequired: false },
  revising:                 { label: 'Revising',                   badgeVariant: 'amber',   isAgentActive: true,  showProgress: true,  humanActionRequired: false },
  review:                   { label: 'Article ready',              badgeVariant: 'teal',    isAgentActive: false, showProgress: false, humanActionRequired: true  },
  pending_content_approval: { label: 'Awaiting content approval',  badgeVariant: 'teal',    isAgentActive: false, showProgress: false, humanActionRequired: true  },
  completed:                { label: 'Completed',                  badgeVariant: 'success', isAgentActive: false, showProgress: false, humanActionRequired: false },
  published:                { label: 'Published',                  badgeVariant: 'success', isAgentActive: false, showProgress: false, humanActionRequired: false },
  rejected:                 { label: 'Rejected',                   badgeVariant: 'error',   isAgentActive: false, showProgress: false, humanActionRequired: false },
  failed:                   { label: 'Failed',                     badgeVariant: 'error',   isAgentActive: false, showProgress: false, humanActionRequired: false },
};

export function getDisplay(status: BriefPipelineStatus): StatusDisplay {
  return STATUS_DISPLAY_MAP[status] ?? STATUS_DISPLAY_MAP.suggested;
}

// ---------------------------------------------------------------------------
// Status → HITL Actions
// ---------------------------------------------------------------------------

export function getHITLActions(status: BriefPipelineStatus): HITLActions {
  const base: HITLActions = {
    canStart: false,
    canStartProduction: false,
    canApproveBrief: false,
    canApproveContent: false,
    canReject: false,
    canSendBack: false,
    canRetry: false,
  };

  switch (status) {
    case 'suggested':
      return { ...base, canStart: true };

    case 'gap_analysis_complete':
      return { ...base, canStartProduction: true };

    case 'brief_review':
    case 'pending_brief_approval':
      return { ...base, canApproveBrief: true, canSendBack: true, canReject: true };

    case 'review':
    case 'pending_content_approval':
      return { ...base, canApproveContent: true, canSendBack: true, canReject: true };

    case 'failed':
      return { ...base, canRetry: true };

    default:
      return base;
  }
}

// ---------------------------------------------------------------------------
// Worker step index (for pipeline stepper visualization)
// ---------------------------------------------------------------------------

const AGENT_STEPS: BriefPipelineStatus[] = [
  'gap_analysis',
  'briefing',
  'approved',
  'outlining',
  'drafting',
  'linking',
  'enriching',
  'evaluating',
  'revising',
];

/**
 * Returns 0-based step index for agent pipeline visualization.
 * Returns -1 if the status is not an agent-active step.
 */
export function getWorkerStepIndex(status: BriefPipelineStatus): number {
  return AGENT_STEPS.indexOf(status);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Whether this status represents a terminal (finished) state */
export function isTerminal(status: BriefPipelineStatus): boolean {
  return status === 'completed' || status === 'published' || status === 'rejected';
}

/** Whether this status represents an in-flight agent processing state */
export function isAgentProcessing(status: BriefPipelineStatus): boolean {
  return getColumn(status) === 'agent' && status !== 'failed';
}
