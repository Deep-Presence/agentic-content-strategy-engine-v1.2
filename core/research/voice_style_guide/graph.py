"""Voice Style Guide HITL sub-graph — Author Review.

Single graph for per-author approve/modify/reject decisions after
author discovery (Stage 1) and before deep research (Stage 2).

Mirrors build_ap_brief_review_graph() from audience_persona/graph.py.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from core.checkpointer import get_checkpointer
from core.shared_tools.task_status import TaskStatus

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# State Schema
# ═══════════════════════════════════════════════════════════════════════


class VSGAuthorReviewState(TypedDict, total=False):
    """State for HITL-1: per-author approval of discovered authors."""

    authors: list  # List[AuthorBrief.model_dump()]
    checkpoint: int  # Always 1
    auto_approve: bool
    presented_at: int  # Unix timestamp
    # Resume values:
    batch_decision: str  # "approve_all" | "partial" | "reject_all"
    author_reviews: list  # List[{author_id, decision, modified_author?}]
    # Computed after resume:
    approved_authors: list  # Final approved set


# ═══════════════════════════════════════════════════════════════════════
# HITL-1: Author Review Graph
# ═══════════════════════════════════════════════════════════════════════


def _author_review_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation timestamp."""
    return {**state, "presented_at": int(time.time())}


def _process_author_resume(
    resume: Dict[str, Any],
    original_authors: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Process resume payload into approved_authors list.

    Rules (fail-closed):
    - Unknown author_ids silently skipped
    - Duplicate author_ids: first-wins
    - Unreviewed authors: rejected
    - Modified authors: require non-empty name
    """
    batch_decision = resume.get("batch_decision", "")
    author_reviews = resume.get("author_reviews", [])

    originals_by_id = {
        a["author_id"]: a for a in original_authors if "author_id" in a
    }

    approved: List[Dict[str, Any]] = []

    if batch_decision == "approve_all":
        approved = list(original_authors)
    elif batch_decision == "reject_all":
        pass  # No authors approved
    elif batch_decision == "partial":
        seen_ids: set[str] = set()
        for review in author_reviews:
            aid = review.get("author_id", "")
            if not aid or aid in seen_ids:
                continue
            seen_ids.add(aid)

            if aid not in originals_by_id:
                logger.warning("Author review references unknown author_id=%s, skipping", aid)
                continue

            decision = review.get("decision", "reject")
            if decision == "approve":
                approved.append(originals_by_id[aid])
            elif decision == "modify":
                modified = review.get("modified_author")
                if modified and modified.get("name", "").strip():
                    if not modified.get("author_id"):
                        modified["author_id"] = aid
                    modified["source"] = "hybrid"
                    approved.append(modified)
                else:
                    logger.warning(
                        "Modified author for %s has empty name, treating as reject",
                        aid,
                    )
            # "reject" or unknown decision → skip (fail-closed)
    # else: unknown batch_decision → fail-closed

    return approved


def _author_review_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human author review via interrupt().

    Auto-approve returns all authors as approved.
    Manual mode fires interrupt, then processes per-author decisions.
    """
    original_authors = state.get("authors", [])

    if state.get("auto_approve"):
        return {
            **state,
            "batch_decision": "approve_all",
            "approved_authors": list(original_authors),
        }

    # Fire interrupt
    resume = interrupt(
        {
            "status": "pending_author_approval",
            "stage": "vsg_author_review",
            "checkpoint": state.get("checkpoint", 1),
            "authors": original_authors,
        }
    )

    if not isinstance(resume, dict):
        resume = {}

    approved = _process_author_resume(resume, original_authors)

    return {
        **state,
        "batch_decision": resume.get("batch_decision", ""),
        "author_reviews": resume.get("author_reviews", []),
        "approved_authors": approved,
    }


def _author_review_route(state: Dict[str, Any]) -> str:
    """Route based on whether any authors were approved."""
    approved = state.get("approved_authors", [])
    if approved:
        return "approved"
    return "rejected"


def build_vsg_author_review_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Author Review sub-graph (HITL-1).

    Nodes: present → gate → route → END
    """
    graph = StateGraph(VSGAuthorReviewState)

    graph.add_node("present", _author_review_present)
    graph.add_node("gate", _author_review_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "gate")
    graph.add_conditional_edges(
        "gate",
        _author_review_route,
        {
            "approved": END,
            "rejected": END,
        },
    )

    return graph.compile(checkpointer=get_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# Graph Invocation Helper
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


async def run_vsg_hitl_checkpoint(
    graph: Any,
    initial_state: Dict[str, Any],
    thread_id: str,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    task_id: Optional[str] = None,
    stage_name: str = "vsg_author_review",
) -> Dict[str, Any]:
    """Run a VSG HITL checkpoint graph, handling interrupt/resume.

    Mirrors run_ap_hitl_checkpoint() from audience_persona/graph.py.

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

    result = await asyncio.to_thread(graph.invoke, initial_state, config)

    while _has_interrupt(result):
        interrupt_val = _get_interrupt_value(result)

        logger.info(
            "VSG HITL %s: interrupt at stage=%s, status=%s",
            stage_name,
            interrupt_val.get("stage", "unknown"),
            interrupt_val.get("status", "unknown"),
        )

        checkpoint_nonce = str(uuid.uuid4())

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

        if task_store and task_id:
            task_store.update_task(
                task_id,
                status=TaskStatus.PENDING_APPROVAL,
                approval_payload={
                    "stage": stage_name,
                    "checkpoint_nonce": checkpoint_nonce,
                    **interrupt_val,
                },
            )

        if task_store and task_id:
            approval = await task_store.wait_for_approval(task_id)

            task_store.update_task(
                task_id,
                status=TaskStatus.RUNNING,
                current_step=stage_name,
                approval_payload=None,
            )
        else:
            logger.warning("No task_store for VSG HITL %s — auto-approving", stage_name)
            approval = {"batch_decision": "approve_all"}

        if event_bus and task_id:
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

        result = await asyncio.to_thread(graph.invoke, Command(resume=approval), config)

    return result
