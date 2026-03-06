"""Tests for style guide LangGraph: auto-approve, HITL, backend write fallback."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from core.research.graphs.style_guide import (
    _cleanup_drafts,
    build_graph,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_style_agent(written_paths: list, notes: str = "created"):
    result = {"written_paths": written_paths, "notes": notes}
    return patch(
        "core.research.graphs.style_guide.run_style_guide_agent",
        return_value=result,
    )


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_compiles_without_checkpointer(self):
        assert build_graph() is not None

    def test_compiles_with_checkpointer(self):
        assert build_graph(checkpointer=MemorySaver()) is not None


# ---------------------------------------------------------------------------
# Auto-approve flow
# ---------------------------------------------------------------------------

class TestAutoApproveFlow:
    def test_promotes_draft_to_permanent(
        self, isolated_artifacts, mock_supabase_mirrors, style_input
    ):
        draft_path = "/artifacts/style_guides/acme-corp.draft.md"
        draft_file = isolated_artifacts / "artifacts/style_guides/acme-corp.draft.md"
        draft_file.write_text("# Style Guide\n\nVoice & Tone section.", encoding="utf-8")

        with _patch_style_agent([draft_path]):
            graph = build_graph()
            result = graph.invoke({"input": style_input, "auto_approve": True})

        permanent = isolated_artifacts / "artifacts/style_guides/acme-corp.md"
        assert permanent.exists()
        assert "Style Guide" in permanent.read_text()
        assert not draft_file.exists()
        assert "/artifacts/style_guides/acme-corp.md" in result.get("written_paths", [])

    def test_backend_write_fallback(
        self, isolated_artifacts, mock_supabase_mirrors, style_input
    ):
        """When backend.write returns 'already exists', _overwrite_virtual_path is used."""
        draft_path = "/artifacts/style_guides/acme-corp.draft.md"
        draft_file = isolated_artifacts / "artifacts/style_guides/acme-corp.draft.md"
        draft_file.write_text("# Style Guide\n\nContent.", encoding="utf-8")

        # Pre-create the permanent file so backend.write will report "already exists"
        permanent = isolated_artifacts / "artifacts/style_guides/acme-corp.md"
        permanent.write_text("old content", encoding="utf-8")

        with _patch_style_agent([draft_path]):
            graph = build_graph()
            result = graph.invoke({"input": style_input, "auto_approve": True})

        # Should have been overwritten via fallback
        assert permanent.exists()
        assert "Style Guide" in permanent.read_text()


# ---------------------------------------------------------------------------
# Interrupt/resume HITL flow
# ---------------------------------------------------------------------------

class TestInterruptResumeFlow:
    def test_interrupt_returns_draft_paths(
        self, isolated_artifacts, mock_supabase_mirrors, style_input
    ):
        draft_path = "/artifacts/style_guides/acme-corp.draft.md"
        (isolated_artifacts / "artifacts/style_guides/acme-corp.draft.md").write_text(
            "# Draft", encoding="utf-8"
        )

        with _patch_style_agent([draft_path]):
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-style-1"}}
            result = graph.invoke({"input": style_input, "auto_approve": False}, config)

        assert "__interrupt__" in result
        payload = result["__interrupt__"][0].value
        assert payload["status"] == "pending_approval"

    def test_resume_approve_writes_permanent(
        self, isolated_artifacts, mock_supabase_mirrors, style_input
    ):
        draft_path = "/artifacts/style_guides/acme-corp.draft.md"
        (isolated_artifacts / "artifacts/style_guides/acme-corp.draft.md").write_text(
            "# Style Guide", encoding="utf-8"
        )

        with _patch_style_agent([draft_path]):
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-style-approve"}}
            graph.invoke({"input": style_input, "auto_approve": False}, config)
            result = graph.invoke(Command(resume={"approval_decision": "approve"}), config)

        permanent = isolated_artifacts / "artifacts/style_guides/acme-corp.md"
        assert permanent.exists()

    def test_resume_reject_deletes_draft(
        self, isolated_artifacts, mock_supabase_mirrors, style_input
    ):
        draft_path = "/artifacts/style_guides/acme-corp.draft.md"
        draft_file = isolated_artifacts / "artifacts/style_guides/acme-corp.draft.md"
        draft_file.write_text("# Draft", encoding="utf-8")

        with _patch_style_agent([draft_path]):
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-style-reject"}}
            graph.invoke({"input": style_input, "auto_approve": False}, config)
            result = graph.invoke(Command(resume={"approval_decision": "reject"}), config)

        assert result.get("approval_decision") == "reject"
        assert not draft_file.exists()

    def test_resume_revise_reruns_agent(
        self, isolated_artifacts, mock_supabase_mirrors, style_input
    ):
        draft_path = "/artifacts/style_guides/acme-corp.draft.md"
        (isolated_artifacts / "artifacts/style_guides/acme-corp.draft.md").write_text(
            "# Draft", encoding="utf-8"
        )

        with _patch_style_agent([draft_path]):
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-style-revise"}}
            graph.invoke({"input": style_input, "auto_approve": False}, config)
            result = graph.invoke(
                Command(resume={"approval_decision": "revise", "revision_note": "More examples"}),
                config,
            )

        assert "__interrupt__" in result


# ---------------------------------------------------------------------------
# Node tests
# ---------------------------------------------------------------------------

class TestCleanupDrafts:
    def test_deletes_draft_on_reject(self, isolated_artifacts):
        draft_path = "/artifacts/style_guides/acme-corp.draft.md"
        f = isolated_artifacts / draft_path.lstrip("/")
        f.write_text("content", encoding="utf-8")

        state = {"agent_result": {"written_paths": [draft_path]}}
        _cleanup_drafts(state)
        assert not f.exists()

    def test_empty_draft_skipped_in_promotion(
        self, isolated_artifacts, mock_supabase_mirrors, style_input
    ):
        """When backend.read() returns empty/falsy content the draft is skipped."""
        draft_path = "/artifacts/style_guides/acme-corp.draft.md"
        (isolated_artifacts / "artifacts/style_guides/acme-corp.draft.md").write_text(
            "   ", encoding="utf-8"
        )

        # Patch backend.read to return empty string (simulating truly empty content)
        with _patch_style_agent([draft_path]), \
             patch("core.research.graphs.style_guide.get_filesystem_backend") as mock_be:
            mock_be.return_value.read.return_value = ""
            graph = build_graph()
            result = graph.invoke({"input": style_input, "auto_approve": True})

        assert result.get("written_paths", []) == []
