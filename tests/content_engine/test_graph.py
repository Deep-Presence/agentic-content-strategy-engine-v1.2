"""Tests for the LangGraph HITL review graph."""
from __future__ import annotations

import pytest

from core.content_engine.graph import build_content_review_graph, run_content_review
from core.models.content_generation import (
    ContentBrief,
    ContentPiece,
    ContentStatus,
    FormattedContent,
    RevisionHistory,
)


class TestBuildGraph:
    def test_graph_compiles(self):
        """Graph should compile without errors."""
        graph = build_content_review_graph()
        assert graph is not None

    def test_auto_approve(self, sample_formatted, sample_brief, tmp_path):
        """With auto_approve=True, graph should approve without interrupting."""
        graph = build_content_review_graph()
        result = graph.invoke({
            "content": sample_formatted,
            "brief": sample_brief,
            "auto_approve": True,
            "artifact_dir": tmp_path,
        })
        assert result["approval_decision"] == "approve"
        assert result.get("finalized") is True


@pytest.mark.asyncio
async def test_run_content_review_auto_approve(sample_formatted, sample_brief, tmp_path):
    """run_content_review should auto-approve all pieces."""
    pieces = await run_content_review(
        formatted_contents=[sample_formatted],
        briefs=[sample_brief],
        revision_histories=[RevisionHistory(brief_id="brief-001", final_passed=True)],
        session_id="test",
        artifact_dir=tmp_path,
    )

    assert len(pieces) == 1
    assert pieces[0].status == ContentStatus.APPROVED
    assert pieces[0].brief_id == "brief-001"
