"""Tests for core.content_engine.graph_v13 — LangGraph HITL checkpoints.

Tests the three sub-graphs (topic, brief, content) and the generic
run_hitl_checkpoint() invocation helper.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_engine.graph_v13 import (
    _brief_approval_gate,
    _brief_present,
    _brief_route,
    _content_apply_edits,
    _content_approval_gate,
    _content_finalize,
    _content_present,
    _content_route,
    _get_interrupt_value,
    _has_interrupt,
    _topic_approval_gate,
    _topic_present,
    _topic_route,
    build_brief_approval_graph,
    build_content_review_graph,
    build_topic_approval_graph,
    run_hitl_checkpoint,
)


# ═══════════════════════════════════════════════════════════════════════
# Topic Approval — Node Functions
# ═══════════════════════════════════════════════════════════════════════


class TestTopicPresent:
    """Tests for _topic_present()."""

    def test_adds_presentation_metadata(self):
        state = {"planner_selections": [{"rank": 1}, {"rank": 2}]}
        result = _topic_present(state)
        assert result["topic_selections_count"] == 2
        assert "topic_presented_at" in result

    def test_empty_selections(self):
        state = {}
        result = _topic_present(state)
        assert result["topic_selections_count"] == 0

    def test_preserves_existing_state(self):
        state = {"planner_selections": [{"rank": 1}], "extra_key": "value"}
        result = _topic_present(state)
        assert result["extra_key"] == "value"


class TestTopicApprovalGate:
    """Tests for _topic_approval_gate()."""

    def test_auto_approve_returns_state(self):
        state = {
            "auto_approve": True,
            "planner_selections": [{"rank": 0}, {"rank": 1}, {"rank": 2}],
        }
        result = _topic_approval_gate(state)
        assert result["topic_decision"] == "approve"
        assert result["approved_topic_ranks"] == [0, 1, 2]

    def test_auto_approve_empty_selections(self):
        state = {"auto_approve": True, "planner_selections": []}
        result = _topic_approval_gate(state)
        assert result["approved_topic_ranks"] == []


class TestTopicRoute:
    """Tests for _topic_route()."""

    def test_approve_routes_to_approved(self):
        assert _topic_route({"topic_decision": "approve"}) == "approved"

    def test_modify_routes_to_approved(self):
        assert _topic_route({"topic_decision": "modify"}) == "approved"

    def test_retry_routes_to_retry(self):
        assert _topic_route({"topic_decision": "retry"}) == "retry"

    def test_reject_routes_to_rejected(self):
        assert _topic_route({"topic_decision": "reject"}) == "rejected"

    def test_default_routes_to_rejected(self):
        """Missing topic_decision defaults to 'reject' (fail-safe)."""
        assert _topic_route({}) == "rejected"


# ═══════════════════════════════════════════════════════════════════════
# Brief Approval — Node Functions
# ═══════════════════════════════════════════════════════════════════════


class TestBriefPresent:
    """Tests for _brief_present()."""

    def test_adds_presentation_metadata(self):
        state = {"blueprint": {"brief_id": "b-001", "title": "409A Guide"}}
        result = _brief_present(state)
        assert result["brief_id"] == "b-001"
        assert result["brief_title"] == "409A Guide"
        assert "brief_presented_at" in result

    def test_empty_blueprint(self):
        result = _brief_present({})
        assert result["brief_id"] == ""
        assert result["brief_title"] == ""


class TestBriefApprovalGate:
    """Tests for _brief_approval_gate()."""

    def test_auto_approve_returns_state(self):
        state = {"auto_approve": True, "blueprint": {"brief_id": "b-001"}}
        result = _brief_approval_gate(state)
        assert result["brief_decision"] == "approve"


class TestBriefRoute:
    """Tests for _brief_route()."""

    def test_approve_routes_to_approved(self):
        assert _brief_route({"brief_decision": "approve"}) == "approved"

    def test_feedback_routes_to_feedback(self):
        assert _brief_route({"brief_decision": "feedback"}) == "feedback"

    def test_reject_routes_to_rejected(self):
        assert _brief_route({"brief_decision": "reject"}) == "rejected"

    def test_default_routes_to_rejected(self):
        """Missing brief_decision defaults to 'reject' (fail-safe)."""
        assert _brief_route({}) == "rejected"


# ═══════════════════════════════════════════════════════════════════════
# Content Review — Node Functions
# ═══════════════════════════════════════════════════════════════════════


class TestContentPresent:
    """Tests for _content_present()."""

    def test_dict_content_extracts_brief_id(self):
        state = {"content": {"brief_id": "b-003"}, "eval_summary": {}}
        result = _content_present(state)
        assert result["content_brief_id"] == "b-003"
        assert "content_presented_at" in result

    def test_object_content_extracts_brief_id(self):
        content_obj = MagicMock()
        content_obj.brief_id = "b-004"
        state = {"content": content_obj}
        result = _content_present(state)
        assert result["content_brief_id"] == "b-004"

    def test_empty_content(self):
        result = _content_present({})
        assert result["content_brief_id"] == ""


class TestContentApprovalGate:
    """Tests for _content_approval_gate()."""

    def test_auto_approve_returns_state(self):
        state = {"auto_approve": True, "content": {"brief_id": "b-001"}}
        result = _content_approval_gate(state)
        assert result["content_decision"] == "approve"


class TestContentApplyEdits:
    """Tests for _content_apply_edits()."""

    def test_sets_editor_notes_applied(self):
        state = {"editor_notes": "fix intro"}
        result = _content_apply_edits(state)
        assert result["editor_notes_applied"] is True

    def test_preserves_existing_state(self):
        state = {"content": {"text": "Hello"}, "extra": "value"}
        result = _content_apply_edits(state)
        assert result["extra"] == "value"


class TestContentFinalize:
    """Tests for _content_finalize()."""

    def test_sets_finalized(self):
        state = {"content": {"text": "Hello"}}
        result = _content_finalize(state)
        assert result["finalized"] is True
        assert "finalized_at" in result

    def test_finalized_at_is_recent(self):
        before = int(time.time())
        result = _content_finalize({})
        after = int(time.time())
        assert before <= result["finalized_at"] <= after


class TestContentRoute:
    """Tests for _content_route()."""

    def test_approve_routes_to_finalize(self):
        assert _content_route({"content_decision": "approve"}) == "finalize"

    def test_edit_routes_to_apply_edits(self):
        assert _content_route({"content_decision": "edit"}) == "apply_edits"

    def test_reject_routes_to_rejected(self):
        assert _content_route({"content_decision": "reject"}) == "rejected"

    def test_default_routes_to_finalize(self):
        assert _content_route({}) == "finalize"


# ═══════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════


class TestHasInterrupt:
    """Tests for _has_interrupt()."""

    def test_returns_true_when_interrupt_present(self):
        assert _has_interrupt({"__interrupt__": [{"value": "x"}]}) is True

    def test_returns_false_when_no_interrupt(self):
        assert _has_interrupt({"data": "ok"}) is False

    def test_returns_false_when_empty_list(self):
        assert _has_interrupt({"__interrupt__": []}) is False


class TestGetInterruptValue:
    """Tests for _get_interrupt_value()."""

    def test_extracts_value_attribute(self):
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}
        result = _get_interrupt_value({"__interrupt__": [interrupt_obj]})
        assert result == {"status": "pending"}

    def test_returns_dict_directly_if_no_value_attr(self):
        result = _get_interrupt_value({"__interrupt__": [{"status": "pending"}]})
        assert result == {"status": "pending"}

    def test_returns_empty_dict_when_no_interrupts(self):
        assert _get_interrupt_value({}) == {}
        assert _get_interrupt_value({"__interrupt__": []}) == {}


# ═══════════════════════════════════════════════════════════════════════
# Graph Building
# ═══════════════════════════════════════════════════════════════════════


class TestBuildGraphs:
    """Tests that graph builders produce compiled graphs."""

    def test_topic_graph_compiles(self):
        graph = build_topic_approval_graph()
        assert graph is not None

    def test_brief_graph_compiles(self):
        graph = build_brief_approval_graph()
        assert graph is not None

    def test_content_graph_compiles(self):
        graph = build_content_review_graph()
        assert graph is not None

    def test_custom_checkpointer(self):
        from langgraph.checkpoint.memory import MemorySaver

        cp = MemorySaver()
        graph = build_topic_approval_graph(checkpointer=cp)
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════════
# Auto-Approve End-to-End
# ═══════════════════════════════════════════════════════════════════════


class TestAutoApproveFlows:
    """End-to-end tests using auto_approve=True (no interrupt)."""

    def test_topic_auto_approve(self):
        graph = build_topic_approval_graph()
        result = graph.invoke(
            {
                "auto_approve": True,
                "planner_selections": [{"rank": 1}, {"rank": 2}],
            },
            {"configurable": {"thread_id": "test-topic-1"}},
        )
        assert result["topic_decision"] == "approve"
        assert result["approved_topic_ranks"] == [0, 1]

    def test_brief_auto_approve(self):
        graph = build_brief_approval_graph()
        result = graph.invoke(
            {
                "auto_approve": True,
                "blueprint": {"brief_id": "b-001", "title": "Test"},
            },
            {"configurable": {"thread_id": "test-brief-1"}},
        )
        assert result["brief_decision"] == "approve"
        assert result["brief_id"] == "b-001"

    def test_content_auto_approve(self):
        graph = build_content_review_graph()
        result = graph.invoke(
            {
                "auto_approve": True,
                "content": {"brief_id": "b-001", "markdown": "# Hello"},
            },
            {"configurable": {"thread_id": "test-content-1"}},
        )
        assert result["content_decision"] == "approve"
        assert result["finalized"] is True


# ═══════════════════════════════════════════════════════════════════════
# Content Review Graph — Edit Path (H7 regression tests)
# ═══════════════════════════════════════════════════════════════════════


class TestContentReviewGraphEditPath:
    """Regression tests for H7: edit decision must exit graph, not loop.

    Before the fix, ``apply_edits → approval_gate`` caused ``run_hitl_checkpoint``
    to spin indefinitely — the pipeline's ``_apply_human_edits()`` was never
    called and the user saw the same unchanged content on every "edit" submit.

    After the fix (``apply_edits → END``), the graph exits cleanly and returns
    ``editor_notes`` to the pipeline so it can call ``_apply_human_edits()``.
    """

    def test_edit_decision_exits_graph_with_editor_notes(self):
        """H7 regression: after 'edit', graph must exit (no second interrupt)."""
        from langgraph.types import Command

        graph = build_content_review_graph()
        config = {"configurable": {"thread_id": "test-edit-exits-h7"}}

        # Initial invoke — approval_gate fires interrupt
        result = graph.invoke(
            {
                "content": {
                    "brief_id": "b-h7",
                    "title": "Test piece",
                    "markdown": "# Hello",
                    "word_count": 2,
                },
                "eval_summary": {},
            },
            config,
        )
        assert _has_interrupt(result), "Approval gate must fire interrupt on first invoke"

        # Resume with 'edit' decision
        result = graph.invoke(
            Command(resume={"content_decision": "edit", "editor_notes": "Fix the introduction"}),
            config,
        )

        # Graph must EXIT after apply_edits — no second interrupt (was the H7 bug)
        assert not _has_interrupt(result), (
            "Graph must exit after 'edit' decision — pipeline owns the revision loop"
        )
        assert result.get("content_decision") == "edit"
        assert result.get("editor_notes") == "Fix the introduction"
        assert result.get("editor_notes_applied") is True

    def test_approve_path_still_finalizes(self):
        """Sanity check: 'approve' path unaffected by the edge change."""
        from langgraph.types import Command

        graph = build_content_review_graph()
        config = {"configurable": {"thread_id": "test-approve-sanity-h7"}}

        result = graph.invoke(
            {
                "content": {"brief_id": "b-approve", "title": "T", "markdown": "x", "word_count": 1},
                "eval_summary": {},
            },
            config,
        )
        assert _has_interrupt(result)

        result = graph.invoke(Command(resume={"content_decision": "approve"}), config)
        assert not _has_interrupt(result)
        assert result.get("finalized") is True
        assert result.get("content_decision") == "approve"

    def test_reject_path_exits_without_finalize(self):
        """Sanity check: 'reject' path unaffected by the edge change."""
        from langgraph.types import Command

        graph = build_content_review_graph()
        config = {"configurable": {"thread_id": "test-reject-sanity-h7"}}

        result = graph.invoke(
            {
                "content": {"brief_id": "b-reject", "title": "T", "markdown": "x", "word_count": 1},
                "eval_summary": {},
            },
            config,
        )
        assert _has_interrupt(result)

        result = graph.invoke(
            Command(resume={"content_decision": "reject", "editor_notes": "Wrong angle"}),
            config,
        )
        assert not _has_interrupt(result)
        assert not result.get("finalized")
        assert result.get("content_decision") == "reject"


# ═══════════════════════════════════════════════════════════════════════
# run_hitl_checkpoint
# ═══════════════════════════════════════════════════════════════════════


class TestRunHitlCheckpoint:
    """Tests for run_hitl_checkpoint() invocation helper."""

    @pytest.mark.asyncio
    async def test_auto_approve_no_interrupt(self):
        """When auto_approve=True, no interrupt occurs."""
        graph = build_topic_approval_graph()
        result = await run_hitl_checkpoint(
            graph=graph,
            initial_state={
                "auto_approve": True,
                "planner_selections": [{"rank": 1}],
            },
            thread_id="test-auto-1",
            stage_name="topic_approval",
        )
        assert result["topic_decision"] == "approve"

    @pytest.mark.asyncio
    async def test_publishes_sse_on_interrupt(self):
        """When graph interrupts, event_bus.publish is called with nonce."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending_topic_approval", "stage": "topic_approval"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"topic_decision": "approve"},
        ]

        event_bus = MagicMock()
        task_store = MagicMock()
        # C1 FIX: wait_for_approval now returns approval data directly
        task_store.wait_for_approval = AsyncMock(return_value={"topic_decision": "approve"})

        result = await run_hitl_checkpoint(
            graph=mock_graph,
            initial_state={"planner_selections": []},
            thread_id="test-sse-1",
            task_store=task_store,
            event_bus=event_bus,
            task_id="task-001",
            stage_name="topic_approval",
        )

        # Find the pending_approval call
        pending_calls = [
            c for c in event_bus.publish.call_args_list
            if c[0][1] == "pending_approval"
        ]
        assert len(pending_calls) == 1
        call_data = pending_calls[0][0][2]
        assert call_data["stage"] == "topic_approval"
        assert "checkpoint_nonce" in call_data  # Nonce included

    @pytest.mark.asyncio
    async def test_updates_task_store_on_interrupt(self):
        """When graph interrupts, update_task sets PENDING_APPROVAL then resets to RUNNING."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending", "stage": "brief_approval"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"brief_decision": "approve"},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(return_value={"brief_decision": "approve"})

        await run_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-ts-1",
            task_store=task_store,
            task_id="task-002",
            stage_name="brief_approval",
        )

        # H1 FIX: update_task called twice — once for pending, once for running reset
        assert task_store.update_task.call_count == 2
        first_call = task_store.update_task.call_args_list[0]
        assert first_call[1]["status"] == "pending_approval"
        second_call = task_store.update_task.call_args_list[1]
        assert second_call[1]["status"] == "running"
        assert second_call[1]["approval_payload"] is None

    @pytest.mark.asyncio
    async def test_resumes_with_queue_data(self):
        """C1 FIX: The graph resumes with queue return, NOT store payload."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"content_decision": "approve", "finalized": True},
        ]

        task_store = MagicMock()
        queue_data = {"content_decision": "approve", "editor_notes": "from-queue"}
        task_store.wait_for_approval = AsyncMock(return_value=queue_data)

        await run_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-resume-1",
            task_store=task_store,
            task_id="task-003",
            stage_name="content_review",
        )

        # Second call should use Command(resume=queue_data) — not store payload
        second_call = mock_graph.invoke.call_args_list[1]
        resume_cmd = second_call[0][0]
        from langgraph.types import Command
        assert isinstance(resume_cmd, Command)
        # get_task() should NOT be called (C1 fix — queue is source of truth)
        task_store.get_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_publishes_approval_received_event(self):
        """After resume, an approval_received event is published."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"topic_decision": "approve"},
        ]

        event_bus = MagicMock()
        task_store = MagicMock()
        approval = {"topic_decision": "approve", "decision": "approve"}
        task_store.wait_for_approval = AsyncMock(return_value=approval)

        await run_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-ack-1",
            task_store=task_store,
            event_bus=event_bus,
            task_id="task-004",
            stage_name="topic_approval",
        )

        event_bus.publish.assert_any_call(
            "task-004",
            "approval_received",
            {"stage": "topic_approval", "decision": "approve"},
        )

    @pytest.mark.asyncio
    async def test_no_task_store_auto_approves(self):
        """Without task_store, fallback auto-approval is used."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"topic_decision": "approve"},
        ]

        result = await run_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-no-ts-1",
            stage_name="topic_approval",
        )

        # Should still complete (fallback auto-approve)
        assert result["topic_decision"] == "approve"

    @pytest.mark.asyncio
    async def test_multiple_interrupts_loop(self):
        """run_hitl_checkpoint loops through multiple interrupts."""
        mock_graph = MagicMock()
        int1 = MagicMock()
        int1.value = {"status": "pending_1"}
        int2 = MagicMock()
        int2.value = {"status": "pending_2"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [int1]},  # First interrupt
            {"__interrupt__": [int2]},  # Second interrupt (edit loop)
            {"finalized": True},  # Final result
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(side_effect=[
            {"content_decision": "edit", "editor_notes": "fix intro"},
            {"content_decision": "approve"},
        ])

        result = await run_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-loop-1",
            task_store=task_store,
            task_id="task-005",
            stage_name="content_review",
        )

        assert result["finalized"] is True
        assert mock_graph.invoke.call_count == 3
        assert task_store.wait_for_approval.call_count == 2
        # H1 FIX: 2 interrupts × 2 calls each = 4 update_task calls
        assert task_store.update_task.call_count == 4

    @pytest.mark.asyncio
    async def test_uses_queue_data_not_store_payload(self):
        """C1 FIX: graph resumes with queue return, not stale store payload."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"stage": "topic_approval"}

        queue_data = {"topic_decision": "approve", "approved_topic_ranks": [0, 1]}
        store_data = {"topic_decision": "reject"}  # Stale/different data

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"topic_decision": "approve"},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(return_value=queue_data)

        result = await run_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-queue-vs-store",
            task_store=task_store,
            task_id="task-006",
            stage_name="topic_approval",
        )

        # Verify Command(resume=queue_data) was used, not store_data
        from langgraph.types import Command
        second_call = mock_graph.invoke.call_args_list[1]
        resume_cmd = second_call[0][0]
        assert isinstance(resume_cmd, Command)
        assert resume_cmd.resume == queue_data

    @pytest.mark.asyncio
    async def test_checkpoint_nonce_generated(self):
        """Each interrupt generates a unique checkpoint_nonce."""
        mock_graph = MagicMock()
        int1 = MagicMock()
        int1.value = {"stage": "content_review"}
        int2 = MagicMock()
        int2.value = {"stage": "content_review"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [int1]},
            {"__interrupt__": [int2]},
            {"finalized": True},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(side_effect=[{}, {}])

        await run_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-nonce",
            task_store=task_store,
            task_id="task-007",
            stage_name="content_review",
        )

        # Extract nonces from the 2 pending_approval update_task calls
        pending_calls = [
            c for c in task_store.update_task.call_args_list
            if c[1].get("status") == "pending_approval"
        ]
        assert len(pending_calls) == 2
        nonce1 = pending_calls[0][1]["approval_payload"]["checkpoint_nonce"]
        nonce2 = pending_calls[1][1]["approval_payload"]["checkpoint_nonce"]
        assert nonce1 != nonce2  # Each interrupt gets unique nonce
