"""Audience Persona HITL sub-graphs — brief review + profile review.

Two graph builders for per-item HITL decisions plus a generic async
invocation helper that mirrors run_kb_hitl_checkpoint().

Graph 1 (HITL-1): Brief Review — per-brief approve/modify/reject + manual add
Graph 2 (HITL-2): Profile Review — per-profile approve/revise/reject
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from core.shared_tools.task_status import TaskStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkpointer helper (copied from KB graph — module independence)
# ---------------------------------------------------------------------------


def _resolve_checkpointer(checkpointer: Any) -> BaseCheckpointSaver:
    """Return checkpointer if valid, otherwise default to MemorySaver."""
    if isinstance(checkpointer, BaseCheckpointSaver):
        return checkpointer
    return MemorySaver()


# ═══════════════════════════════════════════════════════════════════════
# State Schemas
# ═══════════════════════════════════════════════════════════════════════


class APBriefReviewState(TypedDict, total=False):
    """State for HITL-1: per-brief approval of persona suggestions."""

    briefs: list  # List[PersonaBrief.model_dump()]
    checkpoint: int  # Always 1
    auto_approve: bool
    presented_at: int  # Unix timestamp
    # Resume values:
    batch_decision: str  # "approve_all" | "partial" | "reject_all"
    brief_reviews: list  # List[{brief_id, decision, modified_brief?}]
    added_briefs: list  # List[PersonaBrief.model_dump()] — manual entries
    # Computed after resume:
    approved_briefs: list  # Final approved set


class APProfileReviewState(TypedDict, total=False):
    """State for HITL-2: per-profile review of generated persona profiles."""

    profile_summaries: dict  # {persona_id: {content_preview, word_count, has_error, storage_path}}
    checkpoint: int  # Always 2
    auto_approve: bool
    presented_at: int
    # Resume values:
    profile_reviews: list  # List[{persona_id, decision, revision_note?}]
    # Computed after resume:
    approved_profiles: list  # [persona_id, ...]
    revision_requests: dict  # {persona_id: revision_note}
    rejected_profiles: list  # [persona_id, ...]


# ═══════════════════════════════════════════════════════════════════════
# HITL-1: Brief Review Graph
# ═══════════════════════════════════════════════════════════════════════


def _brief_review_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation timestamp."""
    return {**state, "presented_at": int(time.time())}


def _process_brief_resume(
    resume: Dict[str, Any],
    original_briefs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Process resume payload into approved_briefs list.

    Rules (fail-closed):
    - Unknown brief_ids silently skipped
    - Duplicate brief_ids: first-wins
    - Unreviewed briefs: rejected
    - Modified briefs: require non-empty persona_name
    - Added briefs: get unique IDs, source="manual"
    """
    batch_decision = resume.get("batch_decision", "")
    brief_reviews = resume.get("brief_reviews", [])
    added_briefs = resume.get("added_briefs", [])

    originals_by_id = {
        b["brief_id"]: b for b in original_briefs if "brief_id" in b
    }

    approved: List[Dict[str, Any]] = []

    if batch_decision == "approve_all":
        approved = list(original_briefs)
    elif batch_decision == "reject_all":
        pass  # No originals approved
    elif batch_decision == "partial":
        seen_ids: set[str] = set()
        for review in brief_reviews:
            bid = review.get("brief_id", "")
            if not bid or bid in seen_ids:
                continue  # Skip empty or duplicate IDs
            seen_ids.add(bid)

            if bid not in originals_by_id:
                logger.warning("Brief review references unknown brief_id=%s, skipping", bid)
                continue

            decision = review.get("decision", "reject")
            if decision == "approve":
                approved.append(originals_by_id[bid])
            elif decision == "modify":
                modified = review.get("modified_brief")
                if modified and modified.get("persona_name", "").strip():
                    if not modified.get("brief_id"):
                        modified["brief_id"] = bid
                    modified["source"] = "hybrid"
                    approved.append(modified)
                else:
                    logger.warning(
                        "Modified brief for %s has empty persona_name, treating as reject",
                        bid,
                    )
            # "reject" or unknown decision → skip (fail-closed)
    # else: unknown batch_decision → fail-closed, no originals approved

    # Append manually added briefs
    for added in added_briefs:
        if not isinstance(added, dict):
            continue
        if not added.get("brief_id"):
            added["brief_id"] = f"pb-manual-{uuid.uuid4().hex[:8]}"
        added["source"] = "manual"
        approved.append(added)

    return approved


def _brief_review_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human brief review via interrupt().

    Auto-approve returns all briefs as approved.
    Manual mode fires interrupt, then processes per-brief decisions.
    """
    original_briefs = state.get("briefs", [])

    if state.get("auto_approve"):
        return {
            **state,
            "batch_decision": "approve_all",
            "approved_briefs": list(original_briefs),
        }

    # Fire interrupt — returns resume value when human responds
    resume = interrupt(
        {
            "status": "pending_persona_brief_approval",
            "stage": "persona_brief_review",
            "checkpoint": state.get("checkpoint", 1),
            "briefs": original_briefs,
        }
    )

    # Process the resume value
    if not isinstance(resume, dict):
        resume = {}

    approved = _process_brief_resume(resume, original_briefs)

    return {
        **state,
        "batch_decision": resume.get("batch_decision", ""),
        "brief_reviews": resume.get("brief_reviews", []),
        "added_briefs": resume.get("added_briefs", []),
        "approved_briefs": approved,
    }


def _brief_review_route(state: Dict[str, Any]) -> str:
    """Route based on whether any briefs were approved."""
    approved = state.get("approved_briefs", [])
    if approved:
        return "approved"
    return "rejected"


def build_ap_brief_review_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Brief Review sub-graph (HITL-1).

    Nodes: present → gate → route → END
    """
    graph = StateGraph(APBriefReviewState)

    graph.add_node("present", _brief_review_present)
    graph.add_node("gate", _brief_review_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "gate")
    graph.add_conditional_edges(
        "gate",
        _brief_review_route,
        {
            "approved": END,
            "rejected": END,
        },
    )

    return graph.compile(checkpointer=_resolve_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# HITL-2: Profile Review Graph
# ═══════════════════════════════════════════════════════════════════════


def _profile_review_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation timestamp."""
    return {**state, "presented_at": int(time.time())}


def _process_profile_resume(
    resume: Dict[str, Any],
    valid_persona_ids: set[str],
) -> tuple[list[str], dict[str, str], list[str]]:
    """Process profile review resume into categorized lists.

    Returns (approved_profiles, revision_requests, rejected_profiles).

    Rules:
    - Unknown persona_ids silently skipped
    - Duplicate persona_ids: first-wins
    - Unreviewed profiles: treated as approved (fail-open, profiles already generated)
    """
    profile_reviews = resume.get("profile_reviews", [])
    approved: list[str] = []
    revisions: dict[str, str] = {}
    rejected: list[str] = []

    seen_ids: set[str] = set()
    reviewed_ids: set[str] = set()

    for review in profile_reviews:
        pid = review.get("persona_id", "")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)

        if pid not in valid_persona_ids:
            logger.warning("Profile review references unknown persona_id=%s, skipping", pid)
            continue

        reviewed_ids.add(pid)
        decision = review.get("decision", "approve")

        if decision == "approve":
            approved.append(pid)
        elif decision == "revise":
            revisions[pid] = review.get("revision_note", "")
        elif decision == "reject":
            rejected.append(pid)
        else:
            # Unknown decision → approve (fail-open for generated profiles)
            approved.append(pid)

    # Unreviewed profiles are approved (fail-open)
    for pid in valid_persona_ids:
        if pid not in reviewed_ids:
            approved.append(pid)

    return approved, revisions, rejected


def _profile_review_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human profile review via interrupt().

    Auto-approve returns all profiles as approved.
    Manual mode fires interrupt, then processes per-profile decisions.
    Empty profile_summaries skips interrupt entirely.
    """
    profile_summaries = state.get("profile_summaries", {})
    valid_ids = set(profile_summaries.keys())

    # Empty summaries — nothing to review
    if not valid_ids:
        return {
            **state,
            "approved_profiles": [],
            "revision_requests": {},
            "rejected_profiles": [],
        }

    if state.get("auto_approve"):
        return {
            **state,
            "approved_profiles": list(valid_ids),
            "revision_requests": {},
            "rejected_profiles": [],
        }

    # Fire interrupt — returns resume value when human responds
    resume = interrupt(
        {
            "status": "pending_persona_profile_approval",
            "stage": "persona_profile_review",
            "checkpoint": state.get("checkpoint", 2),
            "profiles": profile_summaries,
        }
    )

    if not isinstance(resume, dict):
        resume = {}

    approved, revisions, rejected = _process_profile_resume(resume, valid_ids)

    return {
        **state,
        "profile_reviews": resume.get("profile_reviews", []),
        "approved_profiles": approved,
        "revision_requests": revisions,
        "rejected_profiles": rejected,
    }


def _profile_review_route(state: Dict[str, Any]) -> str:
    """Route to END — pipeline reads categorized lists from state."""
    return "done"


def build_ap_profile_review_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Profile Review sub-graph (HITL-2).

    Nodes: present → gate → route → END
    """
    graph = StateGraph(APProfileReviewState)

    graph.add_node("present", _profile_review_present)
    graph.add_node("gate", _profile_review_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "gate")
    graph.add_conditional_edges(
        "gate",
        _profile_review_route,
        {
            "done": END,
        },
    )

    return graph.compile(checkpointer=_resolve_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# Graph Invocation Helpers
# ═══════════════════════════════════════════════════════════════════════


def _has_interrupt(result: Dict[str, Any]) -> bool:
    """Check if the graph result contains an interrupt."""
    return bool(result.get("__interrupt__"))


def _get_interrupt_value(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the interrupt payload from the graph result."""
    interrupts = result.get("__interrupt__", [])
    if interrupts and len(interrupts) > 0:
        first = interrupts[0]
        return first.value if hasattr(first, "value") else first
    return {}


async def run_ap_hitl_checkpoint(
    graph: Any,
    initial_state: Dict[str, Any],
    thread_id: str,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    task_id: Optional[str] = None,
    stage_name: str = "",
) -> Dict[str, Any]:
    """Run an Audience Persona HITL checkpoint graph, handling interrupt/resume.

    Mirrors run_kb_hitl_checkpoint() but self-contained for the AP module.

    Args:
        graph: Compiled LangGraph StateGraph.
        initial_state: Initial state dict.
        thread_id: Unique thread ID for checkpointing.
        task_store: Optional task store for approval flow.
        event_bus: Optional event bus for SSE events.
        task_id: Optional task ID for task store updates.
        stage_name: Human-readable stage name for logging.

    Returns:
        Final state dict after all interrupts are resolved.
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Initial invocation — run in thread to avoid blocking event loop
    result = await asyncio.to_thread(graph.invoke, initial_state, config)

    # Handle interrupt loop
    while _has_interrupt(result):
        interrupt_val = _get_interrupt_value(result)

        logger.info(
            "AP HITL %s: interrupt at stage=%s, status=%s",
            stage_name,
            interrupt_val.get("stage", "unknown"),
            interrupt_val.get("status", "unknown"),
        )

        # Generate a unique nonce per checkpoint interrupt
        checkpoint_nonce = str(uuid.uuid4())

        # Publish SSE event
        if event_bus and task_id:
            event_bus.publish(
                task_id,
                "pending_approval",
                {
                    "stage": stage_name,
                    "checkpoint_nonce": checkpoint_nonce,
                    **interrupt_val,
                },
            )

        # Update task store with pending status
        if task_store and task_id:
            task_store.update_task(
                task_id,
                status=TaskStatus.PENDING_APPROVAL.value,
                approval_payload={
                    "stage": stage_name,
                    "checkpoint_nonce": checkpoint_nonce,
                    **interrupt_val,
                },
            )

        # Wait for human decision
        if task_store and task_id:
            approval = await task_store.wait_for_approval(task_id)

            # Reset status to RUNNING and clear approval_payload
            task_store.update_task(
                task_id,
                status=TaskStatus.RUNNING.value,
                current_step=stage_name,
                approval_payload=None,
            )
        else:
            # CLI/auto mode fallback
            logger.warning("No task_store for AP HITL %s — auto-approving", stage_name)
            approval = {"batch_decision": "approve_all"}

        # Publish approval received event
        if event_bus and task_id:
            # Extract a representative decision for the event
            decision = (
                approval.get("batch_decision")
                or approval.get("decision")
                or "unknown"
            )
            event_bus.publish(
                task_id,
                "approval_received",
                {"stage": stage_name, "decision": decision},
            )

        # Resume graph with approval data
        result = await asyncio.to_thread(graph.invoke, Command(resume=approval), config)

    return result
