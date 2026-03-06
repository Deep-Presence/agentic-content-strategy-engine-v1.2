"""Tests for CPS model integration into Content Engine v1.3 pipeline.

Tests the _score_cps_batch helper and its integration with the pipeline.
All CPS model internals are mocked — these test the wiring, not the model.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.content_generation import (
    ContentPiece,
    ContentStatus,
    FormattedContent,
    RevisionHistory,
    TargetQuery,
)
from core.models.content_generation_v13 import ContentBlueprint


# ── Helpers ───────────────────────────────────────────────────────────


def _make_formatted(brief_id: str = "brief-001") -> FormattedContent:
    return FormattedContent(
        brief_id=brief_id,
        title="Test Article",
        markdown="# Test\n\nThis is test content with details.",
        word_count=100,
    )


def _make_blueprint(brief_id: str = "brief-001") -> ContentBlueprint:
    return ContentBlueprint(
        brief_id=brief_id,
        title="Test Article",
        content_format="long_blog",
        sections=[],
        key_topics=["testing"],
        target_queries=[
            TargetQuery(query_text="best testing tools", cluster_name="testing"),
        ],
    )


def _make_cps_result(score: float = 0.72) -> dict:
    return {
        "cps_score": score,
        "per_engine": {
            "chatgpt_search": score + 0.03,
            "claude_search": score - 0.04,
            "gemini_search": score - 0.01,
            "perplexity": score + 0.02,
        },
        "per_query": [{"query": "best testing tools", "cps_score": score}],
        "model_version": "v1",
        "feature_config": "option_b_full31",
        "target_weight": 0.5,
    }


# ── Tests ─────────────────────────────────────────────────────────────


class TestScoreCpsBatch:
    """Tests for the _score_cps_batch helper function."""

    @patch("core.content_engine.pipeline_v13.get_cps_scorer")
    async def test_skipped_when_scorer_unavailable(self, mock_get_scorer: MagicMock) -> None:
        mock_get_scorer.return_value = None
        from core.content_engine.pipeline_v13 import _score_cps_batch

        result = await _score_cps_batch(
            evaluated=[("brief-001", _make_formatted(), RevisionHistory(brief_id="brief-001", final_passed=True), "pass")],
            blueprint_by_id={"brief-001": _make_blueprint()},
            domain="test-co.com",
            parent_span=None,
            event_bus=None,
            task_id=None,
        )
        assert result == {}

    @patch("core.content_engine.pipeline_v13.get_cps_scorer")
    async def test_returns_scores_when_scorer_available(self, mock_get_scorer: MagicMock) -> None:
        mock_scorer = AsyncMock()
        mock_scorer.score_async = AsyncMock(return_value=_make_cps_result())
        mock_get_scorer.return_value = mock_scorer

        from core.content_engine.pipeline_v13 import _score_cps_batch

        result = await _score_cps_batch(
            evaluated=[("brief-001", _make_formatted(), RevisionHistory(brief_id="brief-001", final_passed=True), "pass")],
            blueprint_by_id={"brief-001": _make_blueprint()},
            domain="test-co.com",
            parent_span=None,
            event_bus=None,
            task_id=None,
        )
        assert "brief-001" in result
        assert result["brief-001"]["cps_score"] == 0.72

    @patch("core.content_engine.pipeline_v13.get_cps_scorer")
    async def test_uses_target_queries_from_blueprint(self, mock_get_scorer: MagicMock) -> None:
        mock_scorer = AsyncMock()
        mock_scorer.score_async = AsyncMock(return_value=_make_cps_result())
        mock_get_scorer.return_value = mock_scorer

        from core.content_engine.pipeline_v13 import _score_cps_batch

        bp = _make_blueprint()
        await _score_cps_batch(
            evaluated=[("brief-001", _make_formatted(), RevisionHistory(brief_id="brief-001", final_passed=True), "pass")],
            blueprint_by_id={"brief-001": bp},
            domain="test-co.com",
            parent_span=None,
            event_bus=None,
            task_id=None,
        )
        call_kwargs = mock_scorer.score_async.call_args[1]
        assert call_kwargs["query_texts"] == ["best testing tools"]

    @patch("core.content_engine.pipeline_v13.get_cps_scorer")
    async def test_uses_title_as_fallback_query(self, mock_get_scorer: MagicMock) -> None:
        mock_scorer = AsyncMock()
        mock_scorer.score_async = AsyncMock(return_value=_make_cps_result())
        mock_get_scorer.return_value = mock_scorer

        from core.content_engine.pipeline_v13 import _score_cps_batch

        bp = ContentBlueprint(
            brief_id="brief-001",
            title="Test Article",
            content_format="long_blog",
            sections=[],
            key_topics=["testing"],
            target_queries=[],  # no target queries
        )
        await _score_cps_batch(
            evaluated=[("brief-001", _make_formatted(), RevisionHistory(brief_id="brief-001", final_passed=True), "pass")],
            blueprint_by_id={"brief-001": bp},
            domain="test-co.com",
            parent_span=None,
            event_bus=None,
            task_id=None,
        )
        call_kwargs = mock_scorer.score_async.call_args[1]
        assert call_kwargs["query_texts"] == ["Test Article"]

    @patch("core.content_engine.pipeline_v13.get_cps_scorer")
    async def test_failure_does_not_block_pipeline(self, mock_get_scorer: MagicMock) -> None:
        mock_scorer = AsyncMock()
        mock_scorer.score_async = AsyncMock(side_effect=RuntimeError("model crash"))
        mock_get_scorer.return_value = mock_scorer

        from core.content_engine.pipeline_v13 import _score_cps_batch

        result = await _score_cps_batch(
            evaluated=[("brief-001", _make_formatted(), RevisionHistory(brief_id="brief-001", final_passed=True), "pass")],
            blueprint_by_id={"brief-001": _make_blueprint()},
            domain="test-co.com",
            parent_span=None,
            event_bus=None,
            task_id=None,
        )
        # Should return empty dict for failed brief, not crash
        assert "brief-001" not in result

    @patch("core.content_engine.pipeline_v13.get_cps_scorer")
    async def test_scores_multiple_pieces_in_parallel(self, mock_get_scorer: MagicMock) -> None:
        mock_scorer = AsyncMock()
        mock_scorer.score_async = AsyncMock(return_value=_make_cps_result())
        mock_get_scorer.return_value = mock_scorer

        from core.content_engine.pipeline_v13 import _score_cps_batch

        evaluated = [
            ("brief-001", _make_formatted("brief-001"), RevisionHistory(brief_id="brief-001", final_passed=True), "pass"),
            ("brief-002", _make_formatted("brief-002"), RevisionHistory(brief_id="brief-002", final_passed=True), "pass"),
        ]
        blueprints = {
            "brief-001": _make_blueprint("brief-001"),
            "brief-002": _make_blueprint("brief-002"),
        }
        result = await _score_cps_batch(
            evaluated=evaluated,
            blueprint_by_id=blueprints,
            domain="test-co.com",
            parent_span=None,
            event_bus=None,
            task_id=None,
        )
        assert "brief-001" in result
        assert "brief-002" in result
        assert mock_scorer.score_async.call_count == 2

    @patch("core.content_engine.pipeline_v13.get_cps_scorer")
    async def test_event_emitted_on_completion(self, mock_get_scorer: MagicMock) -> None:
        mock_scorer = AsyncMock()
        mock_scorer.score_async = AsyncMock(return_value=_make_cps_result())
        mock_get_scorer.return_value = mock_scorer

        mock_event_bus = MagicMock()

        from core.content_engine.pipeline_v13 import _score_cps_batch

        await _score_cps_batch(
            evaluated=[("brief-001", _make_formatted(), RevisionHistory(brief_id="brief-001", final_passed=True), "pass")],
            blueprint_by_id={"brief-001": _make_blueprint()},
            domain="test-co.com",
            parent_span=None,
            event_bus=mock_event_bus,
            task_id="task-123",
        )
        # _emit calls event_bus.publish(task_id, event_type, data)
        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        assert call_args[0][0] == "task-123"
        assert call_args[0][1] == "cps_scoring_complete"


class TestCpsInEvalSummary:
    """Test that CPS results flow into eval_summary and ContentPiece."""

    def test_cps_data_merges_into_eval_summary(self) -> None:
        eval_summary: dict = {
            "overall_score": 0.85,
            "overall_passed": True,
            "dimensions": {"structural": {"score": 0.9, "passed": True}},
        }
        cps_data = _make_cps_result()
        eval_summary["cps"] = cps_data

        assert "cps" in eval_summary
        assert eval_summary["cps"]["cps_score"] == 0.72
        # Original eval data preserved
        assert eval_summary["overall_score"] == 0.85

    def test_content_piece_with_cps_in_eval_summary(self) -> None:
        eval_summary = {"cps": _make_cps_result()}
        piece = ContentPiece(
            brief_id="brief-001",
            title="Test",
            status=ContentStatus.APPROVED,
            final_markdown="# Test",
            eval_summary=eval_summary,
        )
        assert piece.eval_summary["cps"]["cps_score"] == 0.72

    def test_content_piece_without_cps_still_valid(self) -> None:
        """Backward compat: ContentPiece works without CPS data."""
        piece = ContentPiece(
            brief_id="brief-001",
            title="Test",
            status=ContentStatus.APPROVED,
            final_markdown="# Test",
        )
        assert "cps" not in piece.eval_summary
