"""Shared CLI approval helper for research pipeline scripts.

Handles LangGraph >=1.0 interrupt/resume cycle interactively in the terminal.
All research graph CLI scripts (run_company_research, run_persona_research,
run_style_guide_research, run_pipeline) use this to drive the HITL loop.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # content-strategy-engine/


def _has_interrupt(result: Dict[str, Any]) -> bool:
    """Check if a LangGraph invoke result contains an interrupt."""
    return bool(result.get("__interrupt__"))


def _get_interrupt_value(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the first interrupt payload from a LangGraph invoke result."""
    interrupts = result.get("__interrupt__", [])
    if interrupts and hasattr(interrupts[0], "value"):
        return interrupts[0].value
    return {}


def _display_interrupt(interrupt_values: Dict[str, Any]) -> None:
    """Print interrupt details for human review."""
    print("\n" + "=" * 60)
    print("  DRAFT READY FOR REVIEW")
    print("=" * 60)

    # Show draft paths
    draft_paths = interrupt_values.get("draft_paths", [])
    draft_path = interrupt_values.get("draft_path")
    if draft_path and not draft_paths:
        draft_paths = [draft_path]

    if draft_paths:
        print("\nDraft file(s):")
        for p in draft_paths:
            full = _PROJECT_ROOT / p.lstrip("/")
            exists = full.exists()
            size = f" ({full.stat().st_size:,} bytes)" if exists else " (NOT FOUND)"
            print(f"  {p}{size}")

    # Show artifact_md preview
    artifact_md = interrupt_values.get("artifact_md", "")
    if artifact_md:
        preview = artifact_md[:500]
        if len(artifact_md) > 500:
            preview += f"\n... ({len(artifact_md):,} chars total)"
        print("\nContent preview:")
        print(textwrap.indent(preview, "  "))

    # Show notes
    notes = interrupt_values.get("notes", "")
    if notes:
        print(f"\nAgent notes: {notes}")

    print("=" * 60)


def _prompt_decision() -> tuple[str, Optional[str]]:
    """Interactively prompt for approve/revise/reject decision."""
    while True:
        print("\nOptions:")
        print("  [a] Approve  — promote draft(s) to final artifact(s)")
        print("  [r] Revise   — send back to agent with revision note")
        print("  [x] Reject   — discard draft(s) and stop")
        choice = input("\nDecision [a/r/x]: ").strip().lower()

        if choice in ("a", "approve"):
            return "approve", None
        elif choice in ("r", "revise"):
            note = input("Revision note: ").strip()
            if not note:
                print("Revision note is required for revise.")
                continue
            return "revise", note
        elif choice in ("x", "reject"):
            confirm = input("Are you sure you want to reject? [y/N]: ").strip().lower()
            if confirm == "y":
                return "reject", None
            continue
        else:
            print(f"Invalid choice: '{choice}'. Enter a, r, or x.")


def run_graph_with_approval(
    build_graph_fn: Callable[..., Any],
    initial_state: Dict[str, Any],
    thread_id: str,
) -> Dict[str, Any]:
    """Invoke a research graph with interactive terminal approval loop.

    Handles the LangGraph >=1.0 interrupt/resume cycle:
    1. Build graph with MemorySaver checkpointer
    2. Invoke with initial state
    3. If interrupted (approval_gate), display drafts and prompt user
    4. Resume with Command(resume={approval_decision, revision_note})
    5. Loop until no more interrupts (handles revise cycles)

    Args:
        build_graph_fn: Graph builder function (e.g., build_graph from persona_research).
        initial_state: Initial graph state dict.
        thread_id: Unique thread ID for the checkpointer.

    Returns:
        Final graph state dict after all approvals are resolved.
    """
    checkpointer = MemorySaver()
    graph = build_graph_fn(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    # First invocation
    result = graph.invoke(initial_state, config)

    # HITL loop
    while _has_interrupt(result):
        interrupt_values = _get_interrupt_value(result)
        _display_interrupt(interrupt_values)

        decision, revision_note = _prompt_decision()

        resume_value: Dict[str, Any] = {"approval_decision": decision}
        if revision_note:
            resume_value["revision_note"] = revision_note

        print(f"\nResuming with decision: {decision}" + (f" (note: {revision_note})" if revision_note else ""))
        result = graph.invoke(Command(resume=resume_value), config)

    return result
