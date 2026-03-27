"""Tests for HITL interrupt/resume flow with LangGraph >=1.0.

LangGraph 1.0.x changed interrupt() behavior: graph.invoke() returns normally
with __interrupt__ in the result dict instead of raising GraphInterrupt.
These tests verify the runner + graph approval gates handle this correctly.

Uses TypedDict state schema (matching production graphs) to avoid
__interrupt__ bleed-through with StateGraph(dict) in langgraph-checkpoint >=4.0.

References:
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://github.com/langchain-ai/langgraph/issues/3675
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pytest
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from core.content_engine.graph_v13 import _get_interrupt_value, _has_interrupt


# ── State schema — TypedDict avoids __interrupt__ channel bleed ──────


class _TestState(TypedDict, total=False):
    input: Any
    auto_approve: bool
    artifact_md: str
    draft_path: str
    approval_decision: str
    revision_note: str
    output_path: str


# ── Helper: minimal graph mimicking approval gate pattern ────────────


def _build_test_graph(checkpointer=None):
    """Build a minimal graph that mirrors our research approval pattern.

    Uses TypedDict state (like production graphs) so that __interrupt__
    is not stored as a regular channel in the checkpoint.
    """

    def agent(state):
        return {"artifact_md": "# Draft Content", "draft_path": "/test.draft.md"}

    def approval_gate(state):
        if state.get("auto_approve"):
            return {"approval_decision": "approve"}
        resume_value = interrupt(
            {"status": "pending_approval", "artifact_md": state.get("artifact_md")}
        )
        if isinstance(resume_value, dict):
            return resume_value
        return {"approval_decision": str(resume_value)}

    def route(state):
        return {}

    def write(state):
        return {"output_path": "/test.md"}

    g = StateGraph(_TestState)
    g.add_node("agent", agent)
    g.add_node("approval_gate", approval_gate)
    g.add_node("route", route)
    g.add_node("write", write)
    g.set_entry_point("agent")
    g.add_edge("agent", "approval_gate")
    g.add_edge("approval_gate", "route")
    g.add_conditional_edges(
        "route",
        lambda s: (s.get("approval_decision") or "").lower(),
        {"approve": "write", "revise": "agent", "reject": END},
    )
    g.add_edge("write", END)
    return g.compile(checkpointer=checkpointer)


# ── Tests ────────────────────────────────────────────────────────────


class TestInterruptDetection:
    """Verify _has_interrupt and _get_interrupt_value work with LangGraph 1.0.x."""

    def test_invoke_returns_interrupt_not_exception(self) -> None:
        """graph.invoke() must NOT raise GraphInterrupt — it returns __interrupt__."""
        ck = MemorySaver()
        graph = _build_test_graph(checkpointer=ck)
        config = {"configurable": {"thread_id": "test-no-raise"}}

        result = graph.invoke({"input": {"name": "test"}, "auto_approve": False}, config)

        assert "__interrupt__" in result, "LangGraph 1.0.x should return __interrupt__ in result"
        assert _has_interrupt(result) is True

    def test_interrupt_payload_contains_artifact_md(self) -> None:
        ck = MemorySaver()
        graph = _build_test_graph(checkpointer=ck)
        config = {"configurable": {"thread_id": "test-payload"}}

        result = graph.invoke({"input": {"name": "test"}, "auto_approve": False}, config)

        iv = _get_interrupt_value(result)
        assert iv.get("status") == "pending_approval"
        assert iv.get("artifact_md") == "# Draft Content"

    def test_no_interrupt_on_auto_approve(self) -> None:
        ck = MemorySaver()
        graph = _build_test_graph(checkpointer=ck)
        config = {"configurable": {"thread_id": "test-auto"}}

        result = graph.invoke({"input": {"name": "test"}, "auto_approve": True}, config)

        assert not _has_interrupt(result), "auto_approve=True should skip interrupt"
        assert result.get("output_path") == "/test.md"


class TestResumeFlow:
    """Verify the full interrupt → resume → complete cycle."""

    def test_approve_preserves_state_and_completes(self) -> None:
        ck = MemorySaver()
        graph = _build_test_graph(checkpointer=ck)
        config = {"configurable": {"thread_id": "test-approve"}}

        # First invoke — should pause
        r1 = graph.invoke({"input": {"name": "test"}, "auto_approve": False}, config)
        assert _has_interrupt(r1)

        # Resume with approve
        r2 = graph.invoke(Command(resume={"approval_decision": "approve"}), config)
        assert not _has_interrupt(r2), "Should complete without another interrupt"
        # State must be preserved after resume
        assert r2.get("input") == {"name": "test"}, "input must survive resume"
        assert r2.get("artifact_md") == "# Draft Content", "artifact_md must survive resume"
        assert r2.get("output_path") == "/test.md", "write node must run"
        assert r2.get("approval_decision") == "approve"

    def test_reject_ends_graph(self) -> None:
        ck = MemorySaver()
        graph = _build_test_graph(checkpointer=ck)
        config = {"configurable": {"thread_id": "test-reject"}}

        r1 = graph.invoke({"input": {"name": "test"}, "auto_approve": False}, config)
        assert _has_interrupt(r1)

        r2 = graph.invoke(Command(resume={"approval_decision": "reject"}), config)
        assert not _has_interrupt(r2)
        assert r2.get("approval_decision") == "reject"
        # write node should NOT have run
        assert r2.get("output_path") is None

    @pytest.mark.xfail(reason="PB-39: LangGraph revise→approve loop does not clear interrupt")
    def test_revise_loops_back_to_agent(self) -> None:
        ck = MemorySaver()
        graph = _build_test_graph(checkpointer=ck)
        config = {"configurable": {"thread_id": "test-revise"}}

        # First invoke — pause
        r1 = graph.invoke({"input": {"name": "test"}, "auto_approve": False}, config)
        assert _has_interrupt(r1)

        # Resume with revise — agent re-runs, hits approval_gate again
        r2 = graph.invoke(
            Command(resume={"approval_decision": "revise", "revision_note": "add more detail"}),
            config,
        )
        assert _has_interrupt(r2), "Revise should loop back to agent → approval_gate → interrupt"

        # Now approve
        r3 = graph.invoke(Command(resume={"approval_decision": "approve"}), config)
        assert not _has_interrupt(r3)
        assert r3.get("output_path") == "/test.md"


class TestHasInterruptHelper:
    """Unit tests for the _has_interrupt / _get_interrupt_value helpers."""

    def test_empty_result(self) -> None:
        assert _has_interrupt({}) is False
        assert _get_interrupt_value({}) == {}

    def test_result_without_interrupt(self) -> None:
        result = {"input": {"name": "test"}, "output_path": "/test.md"}
        assert _has_interrupt(result) is False

    def test_result_with_empty_interrupt_list(self) -> None:
        result = {"__interrupt__": []}
        assert _has_interrupt(result) is False

    def test_result_with_interrupt(self) -> None:
        # Simulate what LangGraph returns
        class FakeInterrupt:
            def __init__(self, value):
                self.value = value

        result = {"__interrupt__": [FakeInterrupt({"status": "pending_approval"})]}
        assert _has_interrupt(result) is True
        assert _get_interrupt_value(result) == {"status": "pending_approval"}
