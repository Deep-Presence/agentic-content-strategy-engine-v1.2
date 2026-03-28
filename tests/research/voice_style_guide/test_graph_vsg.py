"""Tests for Voice Style Guide HITL graph — Author Review.

Covers:
- Graph builder
- Auto-approve (skips interrupt)
- Interrupt payload structure
- Resume with approve_all / partial / reject_all
- Modified authors
- Duplicate / unknown author_ids
- run_vsg_hitl_checkpoint() helper
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver

from langgraph.types import Command

from core.research.voice_style_guide.graph import (
    build_vsg_author_review_graph,
    run_vsg_hitl_checkpoint,
    _process_author_resume,
)


@pytest.fixture(autouse=True)
def _use_memory_checkpointer(monkeypatch):
    """Use in-memory checkpointer so tests don't require Redis."""
    monkeypatch.setattr(
        "core.research.voice_style_guide.graph.get_checkpointer",
        lambda override=None: override if override is not None else MemorySaver(),
    )


# ---------------------------------------------------------------------------
# Helpers — sample data factories
# ---------------------------------------------------------------------------


def _make_authors(count: int = 3) -> list:
    """Create sample author dicts (serialized AuthorBrief)."""
    return [
        {
            "author_id": f"author-{i}",
            "name": f"Author {i}",
            "description": f"Description for author {i}",
            "famous_works": [f"Work A{i}", f"Work B{i}"],
            "resonance_rationale": f"Rationale for author {i}",
            "source": "agent",
        }
        for i in range(1, count + 1)
    ]


# ═══════════════════════════════════════════════════════════════════════
# Graph Builder
# ═══════════════════════════════════════════════════════════════════════


class TestBuildVSGAuthorReviewGraph:
    """Graph builder produces a compiled graph."""

    def test_build_returns_compiled_graph(self):
        graph = build_vsg_author_review_graph()
        assert graph is not None

    def test_custom_checkpointer(self):
        from langgraph.checkpoint.memory import MemorySaver

        graph = build_vsg_author_review_graph(checkpointer=MemorySaver())
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════════
# Auto-Approve
# ═══════════════════════════════════════════════════════════════════════


class TestVSGAuthorReviewAutoApprove:
    """Auto-approve skips interrupt entirely."""

    def test_auto_approve_returns_all_authors(self):
        graph = build_vsg_author_review_graph()
        authors = _make_authors(3)
        result = graph.invoke(
            {"authors": authors, "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "vsg-auto-1"}},
        )
        assert result["approved_authors"] == authors

    def test_auto_approve_sets_batch_decision(self):
        graph = build_vsg_author_review_graph()
        result = graph.invoke(
            {"authors": _make_authors(2), "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "vsg-auto-2"}},
        )
        assert result["batch_decision"] == "approve_all"

    def test_auto_approve_no_interrupt(self):
        graph = build_vsg_author_review_graph()
        result = graph.invoke(
            {"authors": _make_authors(2), "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "vsg-auto-3"}},
        )
        assert not result.get("__interrupt__")


# ═══════════════════════════════════════════════════════════════════════
# Interrupt + Resume
# ═══════════════════════════════════════════════════════════════════════


class TestVSGAuthorReviewInterrupt:
    """Manual mode triggers interrupt, resume resolves with per-author decisions."""

    def test_interrupt_payload_has_required_fields(self):
        graph = build_vsg_author_review_graph()
        authors = _make_authors(3)
        result = graph.invoke(
            {"authors": authors, "checkpoint": 1},
            {"configurable": {"thread_id": "vsg-int-1"}},
        )
        assert result.get("__interrupt__")
        interrupt_val = result["__interrupt__"][0].value
        assert interrupt_val["status"] == "pending_author_approval"
        assert interrupt_val["stage"] == "vsg_author_review"
        assert interrupt_val["checkpoint"] == 1
        assert len(interrupt_val["authors"]) == 3

    def test_resume_approve_all(self):
        graph = build_vsg_author_review_graph()
        authors = _make_authors(3)
        config = {"configurable": {"thread_id": "vsg-int-2"}}

        # Initial invoke → interrupt
        result = graph.invoke({"authors": authors, "checkpoint": 1}, config)
        assert result.get("__interrupt__")

        # Resume with approve_all
        result = graph.invoke(
            Command(resume={"batch_decision": "approve_all"}),
            config,
        )
        assert len(result["approved_authors"]) == 3

    def test_resume_reject_all(self):
        graph = build_vsg_author_review_graph()
        authors = _make_authors(3)
        config = {"configurable": {"thread_id": "vsg-int-3"}}

        result = graph.invoke({"authors": authors, "checkpoint": 1}, config)
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={"batch_decision": "reject_all"}),
            config,
        )
        assert len(result["approved_authors"]) == 0

    def test_resume_partial_approve_and_reject(self):
        graph = build_vsg_author_review_graph()
        authors = _make_authors(3)
        config = {"configurable": {"thread_id": "vsg-int-4"}}

        result = graph.invoke({"authors": authors, "checkpoint": 1}, config)
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "author_reviews": [
                    {"author_id": "author-1", "decision": "approve"},
                    {"author_id": "author-2", "decision": "reject"},
                    {"author_id": "author-3", "decision": "approve"},
                ],
            }),
            config,
        )
        assert len(result["approved_authors"]) == 2
        approved_ids = [a["author_id"] for a in result["approved_authors"]]
        assert "author-1" in approved_ids
        assert "author-3" in approved_ids
        assert "author-2" not in approved_ids

    def test_resume_partial_with_modify(self):
        graph = build_vsg_author_review_graph()
        authors = _make_authors(2)
        config = {"configurable": {"thread_id": "vsg-int-5"}}

        result = graph.invoke({"authors": authors, "checkpoint": 1}, config)
        assert result.get("__interrupt__")

        result = graph.invoke(
            Command(resume={
                "batch_decision": "partial",
                "author_reviews": [
                    {"author_id": "author-1", "decision": "approve"},
                    {
                        "author_id": "author-2",
                        "decision": "modify",
                        "modified_author": {
                            "name": "Better Author 2",
                            "description": "Modified description",
                        },
                    },
                ],
            }),
            config,
        )
        assert len(result["approved_authors"]) == 2
        modified = [a for a in result["approved_authors"] if a.get("name") == "Better Author 2"]
        assert len(modified) == 1
        assert modified[0]["source"] == "hybrid"
        assert modified[0]["author_id"] == "author-2"

    def test_presented_at_is_set(self):
        graph = build_vsg_author_review_graph()
        result = graph.invoke(
            {"authors": _make_authors(2), "checkpoint": 1, "auto_approve": True},
            {"configurable": {"thread_id": "vsg-int-6"}},
        )
        assert result["presented_at"] > 0


# ═══════════════════════════════════════════════════════════════════════
# Resume Processing (_process_author_resume)
# ═══════════════════════════════════════════════════════════════════════


class TestProcessAuthorResume:
    """Unit tests for _process_author_resume()."""

    def test_approve_all(self):
        authors = _make_authors(3)
        result = _process_author_resume({"batch_decision": "approve_all"}, authors)
        assert len(result) == 3

    def test_reject_all(self):
        authors = _make_authors(3)
        result = _process_author_resume({"batch_decision": "reject_all"}, authors)
        assert len(result) == 0

    def test_unknown_batch_decision_fail_closed(self):
        authors = _make_authors(3)
        result = _process_author_resume({"batch_decision": "unknown"}, authors)
        assert len(result) == 0

    def test_duplicate_author_ids_first_wins(self):
        authors = _make_authors(2)
        result = _process_author_resume(
            {
                "batch_decision": "partial",
                "author_reviews": [
                    {"author_id": "author-1", "decision": "approve"},
                    {"author_id": "author-1", "decision": "reject"},  # duplicate
                ],
            },
            authors,
        )
        assert len(result) == 1

    def test_unknown_author_id_skipped(self):
        authors = _make_authors(2)
        result = _process_author_resume(
            {
                "batch_decision": "partial",
                "author_reviews": [
                    {"author_id": "author-1", "decision": "approve"},
                    {"author_id": "nonexistent", "decision": "approve"},
                ],
            },
            authors,
        )
        assert len(result) == 1

    def test_modify_with_empty_name_treated_as_reject(self):
        authors = _make_authors(1)
        result = _process_author_resume(
            {
                "batch_decision": "partial",
                "author_reviews": [
                    {
                        "author_id": "author-1",
                        "decision": "modify",
                        "modified_author": {"name": ""},
                    },
                ],
            },
            authors,
        )
        assert len(result) == 0

    def test_unreviewed_authors_rejected(self):
        """Unreviewed authors are NOT approved (fail-closed)."""
        authors = _make_authors(3)
        result = _process_author_resume(
            {
                "batch_decision": "partial",
                "author_reviews": [
                    {"author_id": "author-1", "decision": "approve"},
                    # author-2 and author-3 not reviewed → rejected
                ],
            },
            authors,
        )
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════
# run_vsg_hitl_checkpoint() Helper
# ═══════════════════════════════════════════════════════════════════════


class TestRunVSGHitlCheckpoint:
    """Tests for the async invocation helper."""

    @pytest.mark.asyncio
    async def test_auto_approve_no_interrupt(self):
        graph = build_vsg_author_review_graph()
        authors = _make_authors(3)
        result = await run_vsg_hitl_checkpoint(
            graph,
            {"authors": authors, "checkpoint": 1, "auto_approve": True},
            thread_id="vsg-helper-1",
        )
        assert len(result["approved_authors"]) == 3

    @pytest.mark.asyncio
    async def test_with_task_store_and_event_bus(self):
        """When auto_approve is True, task_store + event_bus are not called."""
        graph = build_vsg_author_review_graph()
        authors = _make_authors(2)
        task_store = MagicMock()
        event_bus = MagicMock()

        result = await run_vsg_hitl_checkpoint(
            graph,
            {"authors": authors, "checkpoint": 1, "auto_approve": True},
            thread_id="vsg-helper-2",
            task_store=task_store,
            event_bus=event_bus,
            task_id="task-123",
        )
        assert len(result["approved_authors"]) == 2
        # No interrupts → no task_store/event_bus calls
        task_store.update_task.assert_not_called()
        event_bus.publish.assert_not_called()
