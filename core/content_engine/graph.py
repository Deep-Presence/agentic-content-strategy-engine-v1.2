"""Stage 4: HITL Review — LangGraph state machine.

Same pattern as core/research/graphs/company_research.py:
StateGraph(dict) with interrupt() for human approval.

Graph:
  present_content → approval_gate (interrupt) → route
    → "approve" → finalize → END
    → "edit" → apply_edits → approval_gate (loop back)
    → "reject" → END
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from core.content_engine.pipeline import _brief_dir
from core.content_engine.tracing import create_trace, log_score
from core.models.content_generation import (
    ContentBrief,
    ContentPiece,
    ContentStatus,
    FormattedContent,
    RevisionHistory,
)

logger = logging.getLogger(__name__)


# ── Graph node functions ────────────────────────────────────────────


def _present_content(state: Dict[str, Any]) -> Dict[str, Any]:
    """Present the content piece for review."""
    content: FormattedContent = state["content"]
    brief: ContentBrief = state["brief"]
    history: RevisionHistory = state.get("history", RevisionHistory(brief_id=brief.brief_id))

    eval_summary = {}
    if history.cycles:
        last_eval = history.cycles[-1]
        eval_summary = {
            "overall_score": last_eval.overall_score,
            "overall_passed": last_eval.overall_passed,
            "dimensions": {
                d.dimension: {"score": d.score, "passed": d.passed}
                for d in last_eval.dimensions
            },
        }

    return {
        **state,
        "eval_summary": eval_summary,
        "presented_at": int(time.time()),
    }


def _approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause for human approval via interrupt().

    Resume with:
        {"approval_decision": "approve"|"edit"|"reject", "editor_notes": "..."}
    """
    if state.get("auto_approve"):
        return {**state, "approval_decision": "approve"}

    content: FormattedContent = state["content"]
    return interrupt(
        {
            "status": "pending_approval",
            "brief_id": content.brief_id,
            "title": content.title,
            "word_count": content.word_count,
            "eval_summary": state.get("eval_summary", {}),
            "content_preview": content.markdown[:1000],
        }
    )


def _route(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pass state through — routing done via conditional edges."""
    return state


def _apply_edits(state: Dict[str, Any]) -> Dict[str, Any]:
    """Apply human editor notes to the content.

    Currently stores notes and loops back for re-approval.
    In v1.1: could trigger an LLM revision pass with the editor notes.
    """
    editor_notes = state.get("editor_notes", "")
    content: FormattedContent = state["content"]

    logger.info(
        "Editor notes for %s: %s",
        content.brief_id,
        editor_notes[:200] if editor_notes else "(none)",
    )

    return {
        **state,
        "editor_notes_applied": True,
        "human_notes": editor_notes,
    }


def _finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize the approved content — write to disk."""
    content: FormattedContent = state["content"]
    artifact_dir: Path = state.get("artifact_dir", Path("."))

    bdir = _brief_dir(artifact_dir, content.brief_id)
    final_path = bdir / "final.md"
    final_path.write_text(content.markdown, encoding="utf-8")

    return {
        **state,
        "artifact_path": str(final_path),
        "finalized": True,
    }


def _get_decision(state: Dict[str, Any]) -> str:
    """Extract routing decision from state."""
    return (state.get("approval_decision") or "").lower()


def build_content_review_graph():
    """Build and compile the LangGraph HITL review state machine."""
    graph = StateGraph(dict)
    graph.add_node("present_content", _present_content)
    graph.add_node("approval_gate", _approval_gate)
    graph.add_node("route", _route)
    graph.add_node("apply_edits", _apply_edits)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("present_content")
    graph.add_edge("present_content", "approval_gate")
    graph.add_edge("approval_gate", "route")
    graph.add_conditional_edges(
        "route",
        _get_decision,
        {
            "approve": "finalize",
            "edit": "apply_edits",
            "reject": END,
        },
    )
    graph.add_edge("apply_edits", "approval_gate")  # Loop back for re-review
    graph.add_edge("finalize", END)
    return graph.compile()


# ── Convenience runner ──────────────────────────────────────────────


async def run_content_review(
    formatted_contents: List[FormattedContent],
    briefs: List[ContentBrief],
    revision_histories: List[RevisionHistory],
    *,
    session_id: str = "",
    artifact_dir: Path = Path("."),
) -> List[ContentPiece]:
    """Run HITL review for all content pieces.

    In auto_approve mode, skips the interrupt and approves everything.
    Otherwise, runs each piece through the LangGraph approval gate.

    Args:
        formatted_contents: Content pieces to review.
        briefs: Original briefs.
        revision_histories: Eval histories from Stage 3.
        session_id: Langfuse session ID.
        artifact_dir: Root artifact directory.

    Returns:
        List of ContentPiece with final status.
    """
    graph = build_content_review_graph()
    pieces: List[ContentPiece] = []

    brief_map = {b.brief_id: b for b in briefs}
    history_map = {h.brief_id: h for h in revision_histories}

    for content in formatted_contents:
        brief = brief_map.get(content.brief_id)
        if not brief:
            logger.warning("No brief found for %s — skipping review", content.brief_id)
            continue

        history = history_map.get(content.brief_id, RevisionHistory(brief_id=content.brief_id))
        trace = create_trace(
            session_id,
            f"review/{content.brief_id}",
            metadata={"brief_id": content.brief_id},
        )

        initial_state = {
            "content": content,
            "brief": brief,
            "history": history,
            "auto_approve": True,  # Always auto-approve in v1.0 pipeline
            "artifact_dir": artifact_dir,
        }

        # Run the graph
        final_state = graph.invoke(initial_state)

        status = ContentStatus.APPROVED
        decision = (final_state.get("approval_decision") or "").lower()
        if decision == "reject":
            status = ContentStatus.REJECTED
        elif decision == "edit":
            status = ContentStatus.EDITED

        piece = ContentPiece(
            brief_id=content.brief_id,
            title=content.title,
            status=status,
            final_markdown=content.markdown,
            eval_summary=final_state.get("eval_summary", {}),
            human_notes=final_state.get("human_notes"),
            artifact_path=final_state.get("artifact_path"),
        )
        pieces.append(piece)

        log_score(trace, "human_decision", decision or "approve")

    return pieces
