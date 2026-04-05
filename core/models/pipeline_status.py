"""Canonical brief-level pipeline status values.

Each value maps 1:1 to a Kanban column + tile badge.
Written to pipeline_state.json and returned by GET /briefs.
"""

from enum import Enum


class BriefPipelineStatus(str, Enum):
    """Canonical brief-level status values.

    Each value maps 1:1 to a Kanban column + tile badge.
    Written to pipeline_state.json and returned by GET /briefs.
    """

    # Triage / Queue column — Gap Analysis phase
    GAP_ANALYSIS_PENDING = "gap_analysis_pending"  # GA queued, preflight running
    GAP_ANALYSIS = "gap_analysis"  # GA S1-S8 running
    GAP_ANALYSIS_COMPLETE = "gap_analysis_complete"  # GA done, awaiting "Start Production"

    # Triage column
    SUGGESTED = "suggested"  # Initial state, awaiting user/planner approval

    # Brief column
    BRIEFING = "briefing"  # Brief Builder running
    BRIEF_REVIEW = "brief_review"  # HITL-2 pending (autonomous only)
    PENDING_BRIEF_APPROVAL = "pending_brief_approval"  # HITL-2 interrupt active
    APPROVED = "approved"  # Brief approved, queued for workers

    # Generating column
    OUTLINING = "outlining"
    DRAFTING = "drafting"
    LINKING = "linking"
    ENRICHING = "enriching"
    EVALUATING = "evaluating"
    REVISING = "revising"  # Eval failed, drafter re-running

    # Review column
    REVIEW = "review"  # HITL-3 pending (evaluator done, entering review)
    PENDING_CONTENT_APPROVAL = "pending_content_approval"  # HITL-3 interrupt active

    # Approved column
    COMPLETED = "completed"  # HITL-3 approved, final.md written
    PUBLISHED = "published"  # Alias for completed (legacy compat)

    # Hidden
    REJECTED = "rejected"
    FAILED = "failed"  # Worker/pipeline error
