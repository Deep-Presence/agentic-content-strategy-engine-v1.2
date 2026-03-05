"""Knowledge Base HITL sub-graphs — doc review + synthesis review.

Two graph builders (doc review shares schema for HITL-1 and HITL-2) plus a
generic async invocation helper that mirrors graph_v13.run_hitl_checkpoint().
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
# Checkpointer helper
# ---------------------------------------------------------------------------


def _resolve_checkpointer(checkpointer: Any) -> BaseCheckpointSaver:
    """Return checkpointer if valid, otherwise default to MemorySaver."""
    if isinstance(checkpointer, BaseCheckpointSaver):
        return checkpointer
    return MemorySaver()


# ═══════════════════════════════════════════════════════════════════════
# State Schemas
# ═══════════════════════════════════════════════════════════════════════


class KBDocReviewState(TypedDict, total=False):
    """Shared state for HITL-1 and HITL-2 doc review checkpoints."""

    doc_summaries: dict  # {doc_type_value: {content_preview, word_count, has_error, error}}
    checkpoint: int  # 1 or 2
    auto_approve: bool
    presented_at: int  # timestamp
    decision: str  # "approve" | "revise" | "reject" — resume value
    revision_notes: dict  # {doc_type: "note"} — per-doc feedback
    approved_docs: list  # [doc_type_value, ...]


class KBSynthesisReviewState(TypedDict, total=False):
    """State for HITL-3 synthesis review checkpoint."""

    synthesis_preview: str
    synthesis_word_count: int
    checkpoint: int  # Always 3
    auto_approve: bool
    presented_at: int
    decision: str  # "approve" | "revise" | "reject" — resume value
    revision_note: str


# ═══════════════════════════════════════════════════════════════════════
# HITL-1/2: Doc Review Graph
# ═══════════════════════════════════════════════════════════════════════


def _doc_review_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation timestamp."""
    return {**state, "presented_at": int(time.time())}


def _doc_review_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human doc review via interrupt().

    Auto-approve returns approve decision with all docs approved.
    Manual mode fires interrupt with doc summaries payload.
    """
    if state.get("auto_approve"):
        doc_summaries = state.get("doc_summaries", {})
        return {
            **state,
            "decision": "approve",
            "approved_docs": list(doc_summaries.keys()),
        }

    checkpoint = state.get("checkpoint", 1)
    return interrupt(
        {
            "status": "pending_kb_approval",
            "stage": f"kb_checkpoint_{checkpoint}",
            "checkpoint": checkpoint,
            "docs": state.get("doc_summaries", {}),
        }
    )


def _doc_review_route(state: Dict[str, Any]) -> str:
    """Route based on doc review decision."""
    decision = state.get("decision", "approve")
    if decision == "approve":
        return "approved"
    elif decision == "revise":
        return "revise"
    return "rejected"


def build_kb_doc_review_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Doc Review sub-graph (used for HITL-1 and HITL-2).

    Nodes: present → gate → route → END
    """
    graph = StateGraph(KBDocReviewState)

    graph.add_node("present", _doc_review_present)
    graph.add_node("gate", _doc_review_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "gate")
    graph.add_conditional_edges(
        "gate",
        _doc_review_route,
        {
            "approved": END,
            "revise": END,
            "rejected": END,
        },
    )

    return graph.compile(checkpointer=_resolve_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# HITL-3: Synthesis Review Graph
# ═══════════════════════════════════════════════════════════════════════


def _synthesis_review_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation timestamp."""
    return {**state, "presented_at": int(time.time())}


def _synthesis_review_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human synthesis review via interrupt()."""
    if state.get("auto_approve"):
        return {**state, "decision": "approve"}

    return interrupt(
        {
            "status": "pending_kb_approval",
            "stage": "kb_checkpoint_3",
            "checkpoint": 3,
            "synthesis_preview": state.get("synthesis_preview", "")[:2000],
            "synthesis_word_count": state.get("synthesis_word_count", 0),
        }
    )


def _synthesis_review_route(state: Dict[str, Any]) -> str:
    """Route based on synthesis review decision."""
    decision = state.get("decision", "approve")
    if decision == "approve":
        return "approved"
    elif decision == "revise":
        return "revise"
    return "rejected"


def build_kb_synthesis_review_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Synthesis Review sub-graph (HITL-3).

    Nodes: present → gate → route → END
    """
    graph = StateGraph(KBSynthesisReviewState)

    graph.add_node("present", _synthesis_review_present)
    graph.add_node("gate", _synthesis_review_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "gate")
    graph.add_conditional_edges(
        "gate",
        _synthesis_review_route,
        {
            "approved": END,
            "revise": END,
            "rejected": END,
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


async def run_kb_hitl_checkpoint(
    graph: Any,
    initial_state: Dict[str, Any],
    thread_id: str,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    task_id: Optional[str] = None,
    stage_name: str = "",
) -> Dict[str, Any]:
    """Run a KB HITL checkpoint graph, handling interrupt/resume.

    Mirrors graph_v13.run_hitl_checkpoint() but self-contained for the KB module.

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
            "KB HITL %s: interrupt at stage=%s, status=%s",
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
            logger.warning("No task_store for KB HITL %s — auto-approving", stage_name)
            approval = {"decision": "approve"}

        # Publish approval received event
        if event_bus and task_id:
            event_bus.publish(
                task_id,
                "approval_received",
                {"stage": stage_name, "decision": approval.get("decision", "unknown")},
            )

        # Resume graph with approval data
        result = await asyncio.to_thread(graph.invoke, Command(resume=approval), config)

    return result
