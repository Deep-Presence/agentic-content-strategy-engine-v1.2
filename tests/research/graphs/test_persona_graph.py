"""Tests for persona research LangGraph: auto-approve, HITL, multi-file promotion."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from core.research.graphs.persona_research import (
    _cleanup_drafts,
    _write_and_mirror,
    build_graph,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_persona_agent(written_paths: list, notes: str = "created"):
    """Patches run_persona_agent to return given written_paths."""
    result = {"written_paths": written_paths, "notes": notes}
    return patch(
        "core.research.graphs.persona_research.run_persona_agent",
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
    def test_promotes_single_draft(
        self, isolated_artifacts, mock_supabase_mirrors, persona_input
    ):
        draft_path = "/artifacts/personas/acme-corp__persona-icp.draft.md"
        draft_file = isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.draft.md"
        draft_file.write_text("# ICP Persona\n\nDraft content.", encoding="utf-8")

        with _patch_persona_agent([draft_path]):
            graph = build_graph()
            result = graph.invoke({"input": persona_input, "auto_approve": True})

        permanent = isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.md"
        assert permanent.exists()
        assert "ICP Persona" in permanent.read_text()
        assert not draft_file.exists()
        assert "/artifacts/personas/acme-corp__persona-icp.md" in result.get("written_paths", [])

    def test_promotes_multiple_drafts(
        self, isolated_artifacts, mock_supabase_mirrors, persona_input
    ):
        drafts = [
            "/artifacts/personas/acme-corp__persona-icp.draft.md",
            "/artifacts/personas/acme-corp__persona-2.draft.md",
        ]
        for dp in drafts:
            f = isolated_artifacts / dp.lstrip("/")
            f.write_text(f"# Content for {dp}", encoding="utf-8")

        with _patch_persona_agent(drafts):
            graph = build_graph()
            result = graph.invoke({"input": persona_input, "auto_approve": True})

        assert len(result.get("written_paths", [])) == 2
        for dp in drafts:
            permanent = dp.replace(".draft.md", ".md")
            assert (isolated_artifacts / permanent.lstrip("/")).exists()

    def test_empty_draft_skipped(
        self, isolated_artifacts, mock_supabase_mirrors, persona_input
    ):
        draft_path = "/artifacts/personas/acme-corp__persona-icp.draft.md"
        draft_file = isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.draft.md"
        draft_file.write_text("   ", encoding="utf-8")  # whitespace only

        with _patch_persona_agent([draft_path]):
            graph = build_graph()
            result = graph.invoke({"input": persona_input, "auto_approve": True})

        assert result.get("written_paths", []) == []


# ---------------------------------------------------------------------------
# Interrupt/resume HITL flow
# ---------------------------------------------------------------------------

class TestInterruptResumeFlow:
    def test_interrupt_returns_draft_paths(
        self, isolated_artifacts, mock_supabase_mirrors, persona_input
    ):
        draft_path = "/artifacts/personas/acme-corp__persona-icp.draft.md"
        (isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.draft.md").write_text(
            "# Draft", encoding="utf-8"
        )

        with _patch_persona_agent([draft_path]):
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-persona-1"}}
            result = graph.invoke({"input": persona_input, "auto_approve": False}, config)

        assert "__interrupt__" in result
        payload = result["__interrupt__"][0].value
        assert payload["status"] == "pending_approval"
        assert draft_path in payload["draft_paths"]

    def test_resume_approve_promotes_all(
        self, isolated_artifacts, mock_supabase_mirrors, persona_input
    ):
        draft_path = "/artifacts/personas/acme-corp__persona-icp.draft.md"
        (isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.draft.md").write_text(
            "# ICP Persona", encoding="utf-8"
        )

        with _patch_persona_agent([draft_path]):
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-persona-approve"}}
            graph.invoke({"input": persona_input, "auto_approve": False}, config)
            result = graph.invoke(Command(resume={"approval_decision": "approve"}), config)

        permanent = isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.md"
        assert permanent.exists()

    def test_resume_reject_deletes_all(
        self, isolated_artifacts, mock_supabase_mirrors, persona_input
    ):
        draft_path = "/artifacts/personas/acme-corp__persona-icp.draft.md"
        draft_file = isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.draft.md"
        draft_file.write_text("# Draft", encoding="utf-8")

        with _patch_persona_agent([draft_path]):
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-persona-reject"}}
            graph.invoke({"input": persona_input, "auto_approve": False}, config)
            result = graph.invoke(Command(resume={"approval_decision": "reject"}), config)

        assert result.get("approval_decision") == "reject"
        assert not draft_file.exists()

    def test_resume_revise_reruns_agent(
        self, isolated_artifacts, mock_supabase_mirrors, persona_input
    ):
        draft_path = "/artifacts/personas/acme-corp__persona-icp.draft.md"
        (isolated_artifacts / "artifacts/personas/acme-corp__persona-icp.draft.md").write_text(
            "# Draft", encoding="utf-8"
        )

        with _patch_persona_agent([draft_path]):
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-persona-revise"}}
            graph.invoke({"input": persona_input, "auto_approve": False}, config)
            result = graph.invoke(
                Command(resume={"approval_decision": "revise", "revision_note": "More detail"}),
                config,
            )

        assert "__interrupt__" in result


# ---------------------------------------------------------------------------
# Node tests
# ---------------------------------------------------------------------------

class TestCleanupDrafts:
    def test_deletes_multiple_drafts(self, isolated_artifacts):
        paths = [
            "/artifacts/personas/acme-corp__persona-icp.draft.md",
            "/artifacts/personas/acme-corp__persona-2.draft.md",
        ]
        for p in paths:
            f = isolated_artifacts / p.lstrip("/")
            f.write_text("content", encoding="utf-8")

        state = {"agent_result": {"written_paths": paths}}
        _cleanup_drafts(state)

        for p in paths:
            assert not (isolated_artifacts / p.lstrip("/")).exists()

    def test_missing_drafts_no_error(self, isolated_artifacts):
        state = {"agent_result": {"written_paths": ["/artifacts/personas/nonexistent.draft.md"]}}
        result = _cleanup_drafts(state)
        assert result["approval_decision"] == "reject"

    def test_no_drafts_on_disk(self, isolated_artifacts, persona_input, mock_supabase_mirrors):
        """Agent returns paths but files don't exist — graph logs warning."""
        draft_path = "/artifacts/personas/acme-corp__persona-icp.draft.md"
        # Don't create the file on disk
        with _patch_persona_agent([draft_path]):
            graph = build_graph()
            result = graph.invoke({"input": persona_input, "auto_approve": True})
        # written_paths should be empty since no draft was found
        assert result.get("written_paths", []) == []
