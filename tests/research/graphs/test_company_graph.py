"""Tests for company research LangGraph: auto-approve, HITL interrupt/resume, helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from core.research.graphs.company_research import (
    _cleanup_drafts,
    _extract_final_markdown,
    _overwrite_virtual_path,
    _write_temp_draft,
    build_graph,
)


# ---------------------------------------------------------------------------
# Helpers to mock the agent node so graph tests don't need real LLM calls
# ---------------------------------------------------------------------------

def _patch_company_agent(response_md: str = "# Acme Corp\n\nComprehensive analysis."):
    """Context manager: patches get_agent() to return a mock that produces response_md."""
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "messages": [
            {"role": "user", "content": "prompt"},
            {"role": "assistant", "content": response_md},
        ]
    }
    return patch("core.research.graphs.company_research.get_agent", return_value=mock_agent)


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_compiles_without_checkpointer(self):
        graph = build_graph()
        assert graph is not None

    def test_compiles_with_memory_saver(self):
        graph = build_graph(checkpointer=MemorySaver())
        assert graph is not None


# ---------------------------------------------------------------------------
# Auto-approve flow (no interrupt)
# ---------------------------------------------------------------------------

class TestAutoApproveFlow:
    def test_writes_final_artifact(
        self, isolated_artifacts, mock_supabase_mirrors, mock_research_settings, company_input
    ):
        with _patch_company_agent():
            graph = build_graph()
            result = graph.invoke({"input": company_input, "auto_approve": True})

        assert result["output_path"] == "/artifacts/company_context/acme-corp.md"
        final_file = isolated_artifacts / "artifacts/company_context/acme-corp.md"
        assert final_file.exists()
        assert "Acme Corp" in final_file.read_text()

    def test_deletes_draft_after_promotion(
        self, isolated_artifacts, mock_supabase_mirrors, mock_research_settings, company_input
    ):
        with _patch_company_agent():
            graph = build_graph()
            graph.invoke({"input": company_input, "auto_approve": True})

        draft_file = isolated_artifacts / "artifacts/company_context/acme-corp.draft.md"
        assert not draft_file.exists()

    def test_sets_output_path_and_mirrored(
        self, isolated_artifacts, mock_supabase_mirrors, mock_research_settings, company_input
    ):
        with _patch_company_agent():
            graph = build_graph()
            result = graph.invoke({"input": company_input, "auto_approve": True})

        assert result["output_path"] == "/artifacts/company_context/acme-corp.md"
        assert result["mirrored"] is True


# ---------------------------------------------------------------------------
# Interrupt/resume HITL flow
# ---------------------------------------------------------------------------

class TestInterruptResumeFlow:
    def test_interrupt_returns_pending_approval(
        self, isolated_artifacts, mock_supabase_mirrors, mock_research_settings, company_input
    ):
        with _patch_company_agent():
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-company-1"}}
            result = graph.invoke({"input": company_input, "auto_approve": False}, config)

        assert "__interrupt__" in result
        interrupt_val = result["__interrupt__"][0].value
        assert interrupt_val["status"] == "pending_approval"
        assert "draft_path" in interrupt_val
        assert "artifact_md" in interrupt_val

    def test_resume_approve_writes_artifact(
        self, isolated_artifacts, mock_supabase_mirrors, mock_research_settings, company_input
    ):
        with _patch_company_agent():
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-company-approve"}}
            # Phase 1: invoke to interrupt
            graph.invoke({"input": company_input, "auto_approve": False}, config)
            # Phase 2: resume with approve
            result = graph.invoke(
                Command(resume={"approval_decision": "approve"}), config
            )

        assert result.get("output_path") == "/artifacts/company_context/acme-corp.md"
        final_file = isolated_artifacts / "artifacts/company_context/acme-corp.md"
        assert final_file.exists()

    def test_resume_reject_deletes_draft(
        self, isolated_artifacts, mock_supabase_mirrors, mock_research_settings, company_input
    ):
        with _patch_company_agent():
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-company-reject"}}
            # Phase 1: invoke to interrupt
            graph.invoke({"input": company_input, "auto_approve": False}, config)
            # Verify draft exists
            draft = isolated_artifacts / "artifacts/company_context/acme-corp.draft.md"
            assert draft.exists()
            # Phase 2: resume with reject
            result = graph.invoke(
                Command(resume={"approval_decision": "reject"}), config
            )

        assert result.get("approval_decision") == "reject"
        assert not draft.exists()

    def test_resume_revise_reruns_agent(
        self, isolated_artifacts, mock_supabase_mirrors, mock_research_settings, company_input
    ):
        with _patch_company_agent():
            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": "test-company-revise"}}
            # Phase 1: invoke to interrupt
            graph.invoke({"input": company_input, "auto_approve": False}, config)
            # Phase 2: resume with revise → should loop back to agent and interrupt again
            result = graph.invoke(
                Command(resume={"approval_decision": "revise", "revision_note": "Add competitors"}),
                config,
            )

        # Should hit interrupt again after re-running agent
        assert "__interrupt__" in result


# ---------------------------------------------------------------------------
# Node unit tests
# ---------------------------------------------------------------------------

class TestWriteTempDraft:
    def test_writes_to_correct_path(self, isolated_artifacts, mock_research_settings, company_input):
        state = {"input": company_input, "artifact_md": "# Draft\n\nContent."}
        with patch("core.research.graphs.company_research.get_filesystem_backend") as mock_be:
            mock_result = MagicMock()
            mock_result.error = None
            mock_be.return_value.write.return_value = mock_result
            result = _write_temp_draft(state)
        assert result["draft_path"] == "/artifacts/company_context/acme-corp.draft.md"

    def test_overwrites_existing_draft(self, isolated_artifacts, company_input):
        # Pre-create draft
        draft = isolated_artifacts / "artifacts/company_context/acme-corp.draft.md"
        draft.write_text("old content", encoding="utf-8")

        state = {"input": company_input, "artifact_md": "# New Draft\n\nNew content."}
        # Use "already exists" error path
        with patch("core.research.graphs.company_research.get_filesystem_backend") as mock_be:
            mock_result = MagicMock()
            mock_result.error = "File already exists"
            mock_be.return_value.write.return_value = mock_result
            _write_temp_draft(state)

        assert "New content" in draft.read_text()


class TestCleanupDrafts:
    def test_deletes_draft(self, isolated_artifacts):
        draft = isolated_artifacts / "artifacts/company_context/acme-corp.draft.md"
        draft.write_text("content", encoding="utf-8")
        state = {"draft_path": "/artifacts/company_context/acme-corp.draft.md"}
        _cleanup_drafts(state)
        assert not draft.exists()

    def test_missing_file_no_error(self, isolated_artifacts):
        state = {"draft_path": "/artifacts/company_context/nonexistent.draft.md"}
        result = _cleanup_drafts(state)
        assert result["approval_decision"] == "reject"


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestOverwriteVirtualPath:
    def test_creates_dirs_and_writes(self, isolated_artifacts):
        _overwrite_virtual_path("/artifacts/company_context/test.md", "hello world")
        f = isolated_artifacts / "artifacts/company_context/test.md"
        assert f.exists()
        assert f.read_text() == "hello world"

    def test_creates_nested_dirs(self, isolated_artifacts):
        _overwrite_virtual_path("/artifacts/new_dir/nested/file.md", "data")
        f = isolated_artifacts / "artifacts/new_dir/nested/file.md"
        assert f.exists()


class TestExtractFinalMarkdownListBlocks:
    def test_list_content_blocks(self):
        """Agent returns content as list of dicts with 'text' key."""
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {"text": "# Section 1\n\nContent."},
                    {"text": "## Section 2\n\nMore content."},
                ],
            }
        ]
        result = _extract_final_markdown(msgs)
        assert "Section 1" in result
        assert "Section 2" in result
