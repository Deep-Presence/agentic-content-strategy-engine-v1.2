"""LangGraph state machine for the v1.3 content pipeline.

Three HITL checkpoints via composed sub-graphs:
  1. Topic Approval (after Strategic Planner, autonomous mode only)
  2. Brief Approval (after Brief Builder, per-blueprint)
  3. Final Content Review (after evaluator, per-content-piece)

Each checkpoint uses the same interrupt() / Command(resume=...) pattern
from core/research/graphs/company_research.py.

Design: Three independent graph-building functions, each returning a
compiled StateGraph. The pipeline orchestrator composes them sequentially.
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
from core.content_engine.tracing_v13 import create_span, end_span, get_current_span

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# State schemas — TypedDict gives each key its own LangGraph channel,
# fixing INVALID_CONCURRENT_GRAPH_UPDATE with StateGraph(dict).
# total=False: all keys optional (not all present at init).
# ═══════════════════════════════════════════════════════════════════════


class TopicApprovalState(TypedDict, total=False):
    planner_selections: list
    selection_metadata: dict
    auto_approve: bool
    topic_presented_at: int
    topic_selections_count: int
    topic_decision: str
    approved_topic_ranks: list
    topic_feedback: str


class BriefApprovalState(TypedDict, total=False):
    blueprint: dict
    auto_approve: bool
    brief_presented_at: int
    brief_id: str
    brief_title: str
    brief_decision: str
    brief_feedback: str


class ContentReviewState(TypedDict, total=False):
    content: Any
    eval_summary: dict
    auto_approve: bool
    content_presented_at: int
    content_brief_id: str
    content_decision: str
    editor_notes: str
    rethink: bool
    editor_notes_applied: bool
    finalized: bool
    finalized_at: int


# ═══════════════════════════════════════════════════════════════════════
# HITL Checkpoint 1: Topic Approval
# ═══════════════════════════════════════════════════════════════════════


def _topic_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Present planner selections for review."""
    selections = state.get("planner_selections", [])
    return {
        **state,
        "topic_presented_at": int(time.time()),
        "topic_selections_count": len(selections),
    }


def _topic_approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human topic approval via interrupt().

    Resume with:
        {
            "topic_decision": "approve" | "modify" | "reject" | "retry",
            "approved_topic_ranks": [1, 2, 3],
            "topic_feedback": "focus more on expense-tracking"
        }
    """
    parent = get_current_span()
    span = create_span(parent, "hitl-1-topic-gate")

    if state.get("auto_approve"):
        selections = state.get("planner_selections", [])
        end_span(span, output={"decision": "auto_approve"})
        return {
            **state,
            "topic_decision": "approve",
            "approved_topic_ranks": list(range(len(selections))),
        }

    end_span(span, output={"decision": "pending"})
    return interrupt(
        {
            "status": "pending_topic_approval",
            "stage": "topic_approval",
            "selections": state.get("planner_selections", []),
            "selection_metadata": state.get("selection_metadata", {}),
        }
    )


def _topic_route(state: Dict[str, Any]) -> str:
    """Route based on topic approval decision."""
    decision = state.get("topic_decision", "reject")
    if decision == "approve" or decision == "modify":
        return "approved"
    elif decision == "retry":
        return "retry"
    else:
        return "rejected"


def build_topic_approval_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Topic Approval sub-graph.

    Nodes: present → approval_gate → route
    Edges: approved → END, retry → END, rejected → END

    The pipeline orchestrator handles retry logic externally
    (re-running the Strategic Planner with feedback).
    """
    graph = StateGraph(TopicApprovalState)

    graph.add_node("present", _topic_present)
    graph.add_node("approval_gate", _topic_approval_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "approval_gate")
    graph.add_conditional_edges(
        "approval_gate",
        _topic_route,
        {
            "approved": END,
            "retry": END,
            "rejected": END,
        },
    )

    return graph.compile(checkpointer=get_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# HITL Checkpoint 2: Brief Approval
# ═══════════════════════════════════════════════════════════════════════


def _brief_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Present a content blueprint for review."""
    blueprint = state.get("blueprint", {})
    return {
        **state,
        "brief_presented_at": int(time.time()),
        "brief_id": blueprint.get("brief_id", ""),
        "brief_title": blueprint.get("title", ""),
    }


def _brief_approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human brief approval via interrupt().

    Resume with:
        {
            "brief_decision": "approve" | "feedback" | "reject",
            "brief_feedback": "emphasize the ROI angle more in section 3"
        }
    """
    parent = get_current_span()
    span = create_span(parent, "hitl-2-brief-gate")

    if state.get("auto_approve"):
        end_span(span, output={"decision": "auto_approve"})
        return {**state, "brief_decision": "approve"}

    blueprint = state.get("blueprint", {})
    end_span(span, output={"decision": "pending", "brief_id": blueprint.get("brief_id", "")})
    return interrupt(
        {
            "status": "pending_brief_approval",
            "stage": "brief_approval",
            "brief_id": blueprint.get("brief_id", ""),
            "title": blueprint.get("title", ""),
            "sections": blueprint.get("sections", []),
            "word_count_range": blueprint.get("word_count_range", [0, 0]),
            "content_format": blueprint.get("content_format", ""),
            "structural_targets": blueprint.get("structural_targets", {}),
            "must_hit_checklist": blueprint.get("must_hit_checklist", []),
        }
    )


def _brief_route(state: Dict[str, Any]) -> str:
    """Route based on brief approval decision."""
    decision = state.get("brief_decision", "reject")
    if decision == "approve":
        return "approved"
    elif decision == "feedback":
        return "feedback"
    else:
        return "rejected"


def build_brief_approval_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Brief Approval sub-graph.

    One graph instance per blueprint.

    Nodes: present → approval_gate → route
    Edges: approved → END, feedback → END, rejected → END

    The pipeline orchestrator handles the feedback loop
    (re-running Agent 2 with user feedback).
    """
    graph = StateGraph(BriefApprovalState)

    graph.add_node("present", _brief_present)
    graph.add_node("approval_gate", _brief_approval_gate)

    graph.set_entry_point("present")
    graph.add_edge("present", "approval_gate")
    graph.add_conditional_edges(
        "approval_gate",
        _brief_route,
        {
            "approved": END,
            "feedback": END,
            "rejected": END,
        },
    )

    return graph.compile(checkpointer=get_checkpointer(checkpointer))


# ═══════════════════════════════════════════════════════════════════════
# HITL Checkpoint 3: Final Content Review
# ═══════════════════════════════════════════════════════════════════════


def _content_present(state: Dict[str, Any]) -> Dict[str, Any]:
    """Present the final content piece for review."""
    content = state.get("content", {})
    eval_summary = state.get("eval_summary", {})
    return {
        **state,
        "content_presented_at": int(time.time()),
        "content_brief_id": content.get("brief_id", "")
        if isinstance(content, dict)
        else getattr(content, "brief_id", ""),
    }


def _content_approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human content review via interrupt().

    Resume with:
        {
            "content_decision": "approve" | "edit" | "reject",
            "editor_notes": "...",
            "rethink": false  # true triggers major direction change
        }
    """
    parent = get_current_span()
    span = create_span(parent, "hitl-3-content-gate")

    if state.get("auto_approve"):
        end_span(span, output={"decision": "auto_approve"})
        return {**state, "content_decision": "approve"}

    content = state.get("content", {})
    brief_id = (
        content.get("brief_id", "")
        if isinstance(content, dict)
        else getattr(content, "brief_id", "")
    )
    title = (
        content.get("title", "")
        if isinstance(content, dict)
        else getattr(content, "title", "")
    )
    markdown = (
        content.get("markdown", "")
        if isinstance(content, dict)
        else getattr(content, "markdown", "")
    )
    word_count = (
        content.get("word_count", 0)
        if isinstance(content, dict)
        else getattr(content, "word_count", 0)
    )

    end_span(span, output={"decision": "pending", "brief_id": brief_id})
    return interrupt(
        {
            "status": "pending_content_approval",
            "stage": "content_review",
            "brief_id": brief_id,
            "title": title,
            "word_count": word_count,
            "content_preview": markdown[:2000] if markdown else "",
            "eval_summary": state.get("eval_summary", {}),
        }
    )


def _content_apply_edits(state: Dict[str, Any]) -> Dict[str, Any]:
    """Record editor notes for targeted revision."""
    parent = get_current_span()
    span = create_span(parent, "hitl-3-apply-edits")
    end_span(span, output={"editor_notes_applied": True})
    return {
        **state,
        "editor_notes_applied": True,
    }


def _content_finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mark content as approved and finalized."""
    parent = get_current_span()
    span = create_span(parent, "hitl-3-finalize")
    end_span(span, output={"finalized": True})
    return {
        **state,
        "finalized": True,
        "finalized_at": int(time.time()),
    }


def _content_route(state: Dict[str, Any]) -> str:
    """Route based on content review decision."""
    decision = state.get("content_decision", "approve")
    if decision == "approve":
        return "finalize"
    elif decision == "edit":
        return "apply_edits"
    else:
        return "rejected"


def build_content_review_graph(
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the Content Review sub-graph.

    One graph instance per content piece.

    Nodes: present → approval_gate → route
           → approve → finalize → END
           → edit → apply_edits → END (returns to pipeline for revision)
           → reject → END

    The pipeline's ``while not piece_resolved`` loop (pipeline_v13.py) owns
    the edit retry logic and calls ``_apply_human_edits()`` after this graph
    returns.  The graph must exit on every decision — never loop internally.
    """
    graph = StateGraph(ContentReviewState)

    graph.add_node("present", _content_present)
    graph.add_node("approval_gate", _content_approval_gate)
    graph.add_node("apply_edits", _content_apply_edits)
    graph.add_node("finalize", _content_finalize)

    graph.set_entry_point("present")
    graph.add_edge("present", "approval_gate")
    graph.add_conditional_edges(
        "approval_gate",
        _content_route,
        {
            "finalize": "finalize",
            "apply_edits": "apply_edits",
            "rejected": END,
        },
    )
    graph.add_edge("apply_edits", END)  # Pipeline handles revision + re-presentation externally
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=get_checkpointer(checkpointer))


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


async def run_hitl_checkpoint(
    graph: Any,
    initial_state: Dict[str, Any],
    thread_id: str,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    task_id: Optional[str] = None,
    stage_name: str = "",
) -> Dict[str, Any]:
    """Run a HITL checkpoint graph, handling interrupt/resume.

    This is the generic invocation loop used by all three checkpoints.

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

    # Initial invocation — M3 FIX: run in thread to avoid blocking event loop
    result = await asyncio.to_thread(graph.invoke, initial_state, config)

    # Handle interrupt loop
    while _has_interrupt(result):
        interrupt_val = _get_interrupt_value(result)

        logger.info(
            "HITL %s: interrupt at stage=%s, status=%s",
            stage_name,
            interrupt_val.get("stage", "unknown"),
            interrupt_val.get("status", "unknown"),
        )

        # Generate a unique nonce per checkpoint interrupt for validation
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

        # Update task store with pending status + interrupt payload + nonce
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
            # C1 FIX: Use queue return value directly — it is the FIFO-ordered
            # source of truth. Do NOT re-read from task_store.get_task().approval_payload.
            approval = await task_store.wait_for_approval(task_id)

            # Normalize generic "decision" key to stage-specific keys so that
            # BRPOP timeout fallback {"decision": "reject"} propagates correctly
            # to the graph's routing functions (_topic_route, _brief_route,
            # _content_route) which read stage-specific keys.  setdefault()
            # preserves keys already set by normal frontend approvals.
            if "decision" in approval:
                _generic = approval["decision"]
                for _stage_key in ("content_decision", "topic_decision", "brief_decision"):
                    approval.setdefault(_stage_key, _generic)

            # H1 FIX: Reset status to RUNNING and clear approval_payload
            # (matches research pipeline pattern in runner.py:481)
            task_store.update_task(
                task_id,
                status=TaskStatus.RUNNING.value,
                current_step=stage_name,
                approval_payload=None,
            )
        else:
            # CLI/auto mode — shouldn't reach here (auto_approve bypasses interrupt)
            logger.warning("No task_store for HITL %s — auto-approving", stage_name)
            approval = {"topic_decision": "approve", "brief_decision": "approve", "content_decision": "approve"}

        # Publish approval received event BEFORE resuming graph
        if event_bus and task_id:
            event_bus.publish(
                task_id,
                "approval_received",
                {"stage": stage_name, "decision": approval.get("decision", "unknown")},
            )

        # M3 FIX: Resume graph in thread (matches runner.py:489)
        result = await asyncio.to_thread(graph.invoke, Command(resume=approval), config)

    return result
