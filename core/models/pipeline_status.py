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

    # Triage column
    SUGGESTED = "suggested"  # Initial state, awaiting user/planner approval

    # Brief column
    BRIEFING = "briefing"  # Brief Builder running
    BRIEF_REVIEW = "brief_review"  # HITL-2 pending (autonomous only)
    APPROVED = "approved"  # Brief approved, queued for workers

    # Generating column
    OUTLINING = "outlining"
    DRAFTING = "drafting"
    LINKING = "linking"
    ENRICHING = "enriching"
    EVALUATING = "evaluating"
    REVISING = "revising"  # Eval failed, drafter re-running

    # Review column
    REVIEW = "review"  # HITL-3 pending

    # Approved column
    COMPLETED = "completed"  # HITL-3 approved, final.md written
    PUBLISHED = "published"  # Alias for completed (legacy compat)

    # Hidden
    REJECTED = "rejected"
    FAILED = "failed"  # Worker/pipeline error
