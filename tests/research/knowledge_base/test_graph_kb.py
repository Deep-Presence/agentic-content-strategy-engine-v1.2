"""Tests for Knowledge Base HITL graphs — doc review + synthesis review.

Tests the two sub-graphs (doc review, synthesis review) and the
run_kb_hitl_checkpoint() invocation helper.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver

# ---------------------------------------------------------------------------
# Module-level imports (graph.py must exist for these to resolve)
# ---------------------------------------------------------------------------

from core.research.knowledge_base.graph import (
    build_kb_doc_review_graph,
    build_kb_synthesis_review_graph,
    run_kb_hitl_checkpoint,
)


@pytest.fixture(autouse=True)
def _use_memory_checkpointer(monkeypatch):
    """Use in-memory checkpointer so tests don't require Redis."""
    monkeypatch.setattr(
        "core.research.knowledge_base.graph.get_checkpointer",
        lambda override=None: override if override is not None else MemorySaver(),
    )


# ═══════════════════════════════════════════════════════════════════════
# Doc Review Graph — build + auto-approve + interrupt/resume
# ═══════════════════════════════════════════════════════════════════════


class TestBuildKBDocReviewGraph:
    """Graph builder produces a compiled graph."""

    def test_build_returns_compiled_graph(self):
        graph = build_kb_doc_review_graph()
        assert graph is not None

    def test_custom_checkpointer(self):
        from langgraph.checkpoint.memory import MemorySaver

        graph = build_kb_doc_review_graph(checkpointer=MemorySaver())
        assert graph is not None


class TestKBDocReviewAutoApprove:
    """Auto-approve skips interrupt entirely."""

    def test_auto_approve_skips_interrupt(self):
        graph = build_kb_doc_review_graph()
        doc_summaries = {
            "company_overview": {"word_count": 3000, "has_error": False},
            "customer_reviews": {"word_count": 2500, "has_error": False},
        }
        result = graph.invoke(
            {
                "doc_summaries": doc_summaries,
                "checkpoint": 1,
                "auto_approve": True,
            },
            {"configurable": {"thread_id": "test-auto-cp1"}},
        )
        assert result["decision"] == "approve"
        assert result["approved_docs"] == list(doc_summaries.keys())

    def test_auto_approve_checkpoint_2(self):
        graph = build_kb_doc_review_graph()
        doc_summaries = {
            "weakness_analysis": {"word_count": 2000, "has_error": False},
            "brand_perception": {"word_count": 1800, "has_error": False},
        }
        result = graph.invoke(
            {
                "doc_summaries": doc_summaries,
                "checkpoint": 2,
                "auto_approve": True,
            },
            {"configurable": {"thread_id": "test-auto-cp2"}},
        )
        assert result["decision"] == "approve"
        assert result["checkpoint"] == 2


class TestKBDocReviewInterrupt:
    """Manual mode triggers interrupt, resume resolves it."""

    def test_manual_interrupt_returns_payload(self):
        graph = build_kb_doc_review_graph()
        doc_summaries = {
            "company_overview": {"word_count": 3000, "has_error": False},
            "customer_reviews": {"word_count": 2500, "has_error": False},
            "competitor_registry": {"word_count": 2200, "has_error": False},
        }
        result = graph.invoke(
            {
                "doc_summaries": doc_summaries,
                "checkpoint": 1,
            },
            {"configurable": {"thread_id": "test-interrupt-cp1"}},
        )
        # Should have interrupt
        assert result.get("__interrupt__")
        interrupt_val = result["__interrupt__"][0]
        payload = interrupt_val.value if hasattr(interrupt_val, "value") else interrupt_val
        assert payload["status"] == "pending_kb_approval"
        assert payload["stage"] == "kb_checkpoint_1"
        assert payload["checkpoint"] == 1
        assert "docs" in payload

    def test_checkpoint_2_payload(self):
        graph = build_kb_doc_review_graph()
        result = graph.invoke(
            {
                "doc_summaries": {"weakness_analysis": {"word_count": 2000}},
                "checkpoint": 2,
            },
            {"configurable": {"thread_id": "test-interrupt-cp2"}},
        )
        assert result.get("__interrupt__")
        payload = result["__interrupt__"][0]
        payload = payload.value if hasattr(payload, "value") else payload
        assert payload["stage"] == "kb_checkpoint_2"

    def test_resume_with_approve(self):
        from langgraph.types import Command

        graph = build_kb_doc_review_graph()
        config = {"configurable": {"thread_id": "test-resume-approve"}}

        # First invoke — interrupt
        graph.invoke(
            {
                "doc_summaries": {"company_overview": {"word_count": 3000}},
                "checkpoint": 1,
            },
            config,
        )
        # Resume with approve
        result = graph.invoke(
            Command(resume={
                "decision": "approve",
                "approved_docs": ["company_overview"],
            }),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["decision"] == "approve"

    def test_resume_with_revise(self):
        from langgraph.types import Command

        graph = build_kb_doc_review_graph()
        config = {"configurable": {"thread_id": "test-resume-revise"}}

        graph.invoke(
            {
                "doc_summaries": {"company_overview": {"word_count": 3000}},
                "checkpoint": 1,
            },
            config,
        )
        result = graph.invoke(
            Command(resume={
                "decision": "revise",
                "revision_notes": {"company_overview": "Add more funding data"},
            }),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["decision"] == "revise"
        assert result["revision_notes"]["company_overview"] == "Add more funding data"

    def test_resume_with_reject(self):
        from langgraph.types import Command

        graph = build_kb_doc_review_graph()
        config = {"configurable": {"thread_id": "test-resume-reject"}}

        graph.invoke(
            {
                "doc_summaries": {"company_overview": {"word_count": 3000}},
                "checkpoint": 1,
            },
            config,
        )
        result = graph.invoke(
            Command(resume={"decision": "reject"}),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["decision"] == "reject"


# ═══════════════════════════════════════════════════════════════════════
# Synthesis Review Graph — build + auto-approve + interrupt/resume
# ═══════════════════════════════════════════════════════════════════════


class TestBuildKBSynthesisReviewGraph:
    """Graph builder produces a compiled graph."""

    def test_build_returns_compiled_graph(self):
        graph = build_kb_synthesis_review_graph()
        assert graph is not None


class TestKBSynthesisReviewAutoApprove:
    """Auto-approve skips interrupt."""

    def test_auto_approve_skips_interrupt(self):
        graph = build_kb_synthesis_review_graph()
        result = graph.invoke(
            {
                "synthesis_preview": "# Company Profile\n\nGreat analysis.",
                "synthesis_word_count": 4000,
                "checkpoint": 3,
                "auto_approve": True,
            },
            {"configurable": {"thread_id": "test-synth-auto"}},
        )
        assert result["decision"] == "approve"


class TestKBSynthesisReviewInterrupt:
    """Manual mode triggers interrupt, resume resolves it."""

    def test_interrupt_includes_synthesis_preview(self):
        graph = build_kb_synthesis_review_graph()
        result = graph.invoke(
            {
                "synthesis_preview": "# Company Profile\n\nContent here.",
                "synthesis_word_count": 4000,
                "checkpoint": 3,
            },
            {"configurable": {"thread_id": "test-synth-interrupt"}},
        )
        assert result.get("__interrupt__")
        payload = result["__interrupt__"][0]
        payload = payload.value if hasattr(payload, "value") else payload
        assert payload["stage"] == "kb_checkpoint_3"
        assert payload["synthesis_word_count"] == 4000

    def test_resume_with_approve(self):
        from langgraph.types import Command

        graph = build_kb_synthesis_review_graph()
        config = {"configurable": {"thread_id": "test-synth-resume-approve"}}

        graph.invoke(
            {
                "synthesis_preview": "# Profile",
                "synthesis_word_count": 3500,
                "checkpoint": 3,
            },
            config,
        )
        result = graph.invoke(
            Command(resume={"decision": "approve"}),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["decision"] == "approve"

    def test_resume_with_revise(self):
        from langgraph.types import Command

        graph = build_kb_synthesis_review_graph()
        config = {"configurable": {"thread_id": "test-synth-resume-revise"}}

        graph.invoke(
            {
                "synthesis_preview": "# Profile",
                "synthesis_word_count": 3500,
                "checkpoint": 3,
            },
            config,
        )
        result = graph.invoke(
            Command(resume={
                "decision": "revise",
                "revision_note": "Strengthen recommendations section",
            }),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["decision"] == "revise"
        assert result["revision_note"] == "Strengthen recommendations section"

    def test_resume_with_reject(self):
        from langgraph.types import Command

        graph = build_kb_synthesis_review_graph()
        config = {"configurable": {"thread_id": "test-synth-resume-reject"}}

        graph.invoke(
            {
                "synthesis_preview": "# Profile",
                "synthesis_word_count": 3500,
                "checkpoint": 3,
            },
            config,
        )
        result = graph.invoke(
            Command(resume={"decision": "reject"}),
            config,
        )
        assert not result.get("__interrupt__")
        assert result["decision"] == "reject"


# ═══════════════════════════════════════════════════════════════════════
# run_kb_hitl_checkpoint — invocation helper
# ═══════════════════════════════════════════════════════════════════════


class TestRunKBHITLCheckpoint:
    """Tests for run_kb_hitl_checkpoint() async helper."""

    @pytest.mark.asyncio
    async def test_auto_approve_returns_without_interrupt(self):
        """Auto-approve state completes without interrupt loop."""
        graph = build_kb_doc_review_graph()
        result = await run_kb_hitl_checkpoint(
            graph=graph,
            initial_state={
                "doc_summaries": {"company_overview": {"word_count": 3000}},
                "checkpoint": 1,
                "auto_approve": True,
            },
            thread_id="test-helper-auto",
            stage_name="kb_checkpoint_1",
        )
        assert result["decision"] == "approve"

    @pytest.mark.asyncio
    async def test_interrupt_publishes_sse_event(self):
        """When graph interrupts, event_bus.publish is called."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {
            "status": "pending_kb_approval",
            "stage": "kb_checkpoint_1",
            "checkpoint": 1,
            "docs": {},
        }

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"decision": "approve"},
        ]

        event_bus = MagicMock()
        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(return_value={"decision": "approve"})

        await run_kb_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-sse-kb",
            task_store=task_store,
            event_bus=event_bus,
            task_id="kb-task-001",
            stage_name="kb_checkpoint_1",
        )

        pending_calls = [
            c for c in event_bus.publish.call_args_list
            if c[0][1] == "pending_approval"
        ]
        assert len(pending_calls) == 1
        call_data = pending_calls[0][0][2]
        assert call_data["stage"] == "kb_checkpoint_1"
        assert "checkpoint_nonce" in call_data

    @pytest.mark.asyncio
    async def test_interrupt_updates_task_store(self):
        """When interrupted, task_store gets PENDING_APPROVAL then RUNNING."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending_kb_approval", "stage": "kb_checkpoint_1"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"decision": "approve"},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(return_value={"decision": "approve"})

        await run_kb_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-ts-kb",
            task_store=task_store,
            task_id="kb-task-002",
            stage_name="kb_checkpoint_1",
        )

        assert task_store.update_task.call_count == 2
        first_call = task_store.update_task.call_args_list[0]
        assert first_call[1]["status"] == "pending_approval"
        second_call = task_store.update_task.call_args_list[1]
        assert second_call[1]["status"] == "running"
        assert second_call[1]["approval_payload"] is None

    @pytest.mark.asyncio
    async def test_resume_resets_status_to_running(self):
        """After approval, task status resets to running."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"decision": "approve"},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(return_value={"decision": "approve"})

        await run_kb_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-reset-kb",
            task_store=task_store,
            task_id="kb-task-003",
            stage_name="kb_checkpoint_2",
        )

        running_calls = [
            c for c in task_store.update_task.call_args_list
            if c[1].get("status") == "running"
        ]
        assert len(running_calls) == 1

    @pytest.mark.asyncio
    async def test_publishes_approval_received_event(self):
        """After resume, approval_received event is published."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"decision": "approve"},
        ]

        event_bus = MagicMock()
        task_store = MagicMock()
        approval = {"decision": "approve"}
        task_store.wait_for_approval = AsyncMock(return_value=approval)

        await run_kb_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-ack-kb",
            task_store=task_store,
            event_bus=event_bus,
            task_id="kb-task-004",
            stage_name="kb_checkpoint_1",
        )

        event_bus.publish.assert_any_call(
            "kb-task-004",
            "approval_received",
            {"stage": "kb_checkpoint_1", "decision": "approve"},
        )

    @pytest.mark.asyncio
    async def test_no_task_store_uses_auto_approve_fallback(self):
        """Without task_store, fallback auto-approval is used."""
        mock_graph = MagicMock()
        interrupt_obj = MagicMock()
        interrupt_obj.value = {"status": "pending"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [interrupt_obj]},
            {"decision": "approve"},
        ]

        result = await run_kb_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-no-ts-kb",
            stage_name="kb_checkpoint_1",
        )
        assert result["decision"] == "approve"

    @pytest.mark.asyncio
    async def test_checkpoint_nonce_unique_per_interrupt(self):
        """Each interrupt generates a unique checkpoint_nonce."""
        mock_graph = MagicMock()
        int1 = MagicMock()
        int1.value = {"status": "pending_1"}
        int2 = MagicMock()
        int2.value = {"status": "pending_2"}

        mock_graph.invoke.side_effect = [
            {"__interrupt__": [int1]},
            {"__interrupt__": [int2]},
            {"decision": "approve"},
        ]

        task_store = MagicMock()
        task_store.wait_for_approval = AsyncMock(side_effect=[
            {"decision": "revise"},
            {"decision": "approve"},
        ])

        await run_kb_hitl_checkpoint(
            graph=mock_graph,
            initial_state={},
            thread_id="test-nonce-kb",
            task_store=task_store,
            task_id="kb-task-005",
            stage_name="kb_checkpoint_1",
        )

        pending_calls = [
            c for c in task_store.update_task.call_args_list
            if c[1].get("status") == "pending_approval"
        ]
        assert len(pending_calls) == 2
        nonce1 = pending_calls[0][1]["approval_payload"]["checkpoint_nonce"]
        nonce2 = pending_calls[1][1]["approval_payload"]["checkpoint_nonce"]
        assert nonce1 != nonce2
