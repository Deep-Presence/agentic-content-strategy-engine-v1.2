"""Tests for core.content_engine.brief_builder — Agent 2.

Tests build_brief() and build_briefs_parallel() with mocked llm_call.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.content_generation import ContentBrief
from core.models.content_generation_v13 import (
    ContentBlueprint,
    TopicSelection,
    WorkerQueryContext,
)
from tests.content_engine.conftest import _make_llm_response


def _blueprint_json(brief_id="brief-001", title="Test Blueprint"):
    """Build a minimal valid ContentBlueprint JSON string."""
    bp = ContentBlueprint(
        brief_id=brief_id,
        title=title,
        content_format="long_blog",
        sections=[],
        key_topics=["409A", "equity"],
    )
    return json.dumps(bp.model_dump(mode="json"), default=str)


# Patch paths for tracing
_TRACING_PATCHES = [
    "core.content_engine.brief_builder.create_span",
    "core.content_engine.brief_builder.end_span",
    "core.content_engine.brief_builder.log_generation",
]


@pytest.fixture(autouse=True)
def _mock_tracing():
    """Disable LangSmith tracing for all builder tests."""
    with patch(_TRACING_PATCHES[0], return_value=MagicMock()), \
         patch(_TRACING_PATCHES[1]), \
         patch(_TRACING_PATCHES[2]):
        yield


@pytest.fixture
def topic():
    return TopicSelection(
        rank=1, query_ids=["q-001"],
        query_texts=["what is a 409A valuation"],
        cluster_name="equity",
        rationale="High gap",
    )


@pytest.fixture
def context():
    return WorkerQueryContext(
        query_gap={"query_id": "q-001", "query_text": "what is a 409A valuation"},
        cluster_spec={"cluster_name": "equity"},
        exemplars=[{"url": "https://example.com", "similarity": 0.9}],
    )


# ═══════════════════════════════════════════════════════════════════════
# build_brief
# ═══════════════════════════════════════════════════════════════════════


class TestBuildBrief:
    """Tests for build_brief()."""

    @pytest.mark.asyncio
    async def test_returns_content_blueprint(self, context, topic):
        from core.content_engine.brief_builder import build_brief

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await build_brief(context, topic)

        assert isinstance(result, ContentBlueprint)
        assert isinstance(result, ContentBrief)

    @pytest.mark.asyncio
    async def test_uses_byok_agent_call_when_workspace_present(self, context, topic):
        from core.content_engine.brief_builder import build_brief

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call_for_agent",
                   new_callable=AsyncMock, return_value=resp) as mock_byok, \
             patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock) as mock_legacy:
            result = await build_brief(
                context,
                topic,
                brief_id="brief-001",
                company_slug="test-co",
                workspace_id="workspace-123",
            )

        assert result.brief_id == "brief-001"
        mock_legacy.assert_not_called()
        mock_byok.assert_awaited_once()
        kwargs = mock_byok.await_args.kwargs
        assert kwargs["workspace_id"] == "workspace-123"
        assert kwargs["workspace_slug"] == "test-co"
        assert kwargs["agent_key"] == "content.brief_builder"
        assert kwargs["metadata"]["agent_key"] == "content.brief_builder"

    @pytest.mark.asyncio
    async def test_brief_id_set_correctly(self, context, topic):
        from core.content_engine.brief_builder import build_brief

        resp = _make_llm_response(_blueprint_json(brief_id="wrong-id"))
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await build_brief(context, topic, brief_id="brief-007")

        # build_brief overrides brief_id to the passed-in value
        assert result.brief_id == "brief-007"

    @pytest.mark.asyncio
    async def test_gap_context_attached(self, context, topic):
        from core.content_engine.brief_builder import build_brief

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await build_brief(context, topic)

        assert result.gap_context is not None
        assert result.gap_context.query_gap["query_id"] == "q-001"

    @pytest.mark.asyncio
    async def test_llm_error_propagates(self, context, topic):
        from core.content_engine.brief_builder import build_brief

        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, side_effect=RuntimeError("LLM down")):
            with pytest.raises(RuntimeError, match="LLM down"):
                await build_brief(context, topic)

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, context, topic):
        from core.content_engine.brief_builder import build_brief

        resp = _make_llm_response("Not valid JSON at all")
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            with pytest.raises((ValueError, Exception)):
                await build_brief(context, topic)


# ═══════════════════════════════════════════════════════════════════════
# build_briefs_parallel
# ═══════════════════════════════════════════════════════════════════════


class TestBuildBriefsParallel:
    """Tests for build_briefs_parallel()."""

    @pytest.mark.asyncio
    async def test_processes_multiple_topics(self):
        from core.content_engine.brief_builder import build_briefs_parallel

        contexts = {
            "q-001": WorkerQueryContext(query_gap={"query_id": "q-001"}),
            "q-002": WorkerQueryContext(query_gap={"query_id": "q-002"}),
        }
        topics = [
            TopicSelection(rank=1, query_ids=["q-001"]),
            TopicSelection(rank=2, query_ids=["q-002"]),
        ]

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            results = await build_briefs_parallel(contexts=contexts, topics=topics)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_parallel_passes_workspace_to_build_brief(self):
        from core.content_engine.brief_builder import build_briefs_parallel

        contexts = {
            "q-001": WorkerQueryContext(query_gap={"query_id": "q-001"}),
        }
        topics = [TopicSelection(rank=1, query_ids=["q-001"])]
        blueprint = ContentBlueprint(brief_id="brief-001", title="Test")

        with patch("core.content_engine.brief_builder.build_brief",
                   new_callable=AsyncMock, return_value=blueprint) as mock_build:
            results = await build_briefs_parallel(
                contexts=contexts,
                topics=topics,
                company_slug="test-co",
                workspace_id="workspace-123",
            )

        assert results == [blueprint]
        mock_build.assert_awaited_once()
        assert mock_build.await_args.kwargs["company_slug"] == "test-co"
        assert mock_build.await_args.kwargs["workspace_id"] == "workspace-123"

    @pytest.mark.asyncio
    async def test_missing_context_preserved_as_none(self):
        """Topics with missing context produce None entries (index-preserving)."""
        from core.content_engine.brief_builder import build_briefs_parallel

        contexts = {
            "q-001": WorkerQueryContext(query_gap={"query_id": "q-001"}),
            # q-002 missing
        }
        topics = [
            TopicSelection(rank=1, query_ids=["q-001"]),
            TopicSelection(rank=2, query_ids=["q-002"]),  # No context
        ]

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            results = await build_briefs_parallel(contexts=contexts, topics=topics)

        # Index-preserving: 2 entries, one non-None, one None
        assert len(results) == 2
        assert results[0] is not None  # q-001 succeeded
        assert results[1] is None  # q-002 missing context

    @pytest.mark.asyncio
    async def test_unique_brief_ids(self):
        from core.content_engine.brief_builder import build_briefs_parallel

        contexts = {
            "q-001": WorkerQueryContext(query_gap={"query_id": "q-001"}),
            "q-002": WorkerQueryContext(query_gap={"query_id": "q-002"}),
        }
        topics = [
            TopicSelection(rank=1, query_ids=["q-001"]),
            TopicSelection(rank=2, query_ids=["q-002"]),
        ]

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            results = await build_briefs_parallel(contexts=contexts, topics=topics)

        ids = [bp.brief_id for bp in results]
        assert len(set(ids)) == len(ids)
        assert "brief-001" in ids
        assert "brief-002" in ids

    @pytest.mark.asyncio
    async def test_empty_topics_returns_empty(self):
        from core.content_engine.brief_builder import build_briefs_parallel

        results = await build_briefs_parallel(contexts={}, topics=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_one_failing_does_not_cancel_others(self):
        from core.content_engine.brief_builder import build_briefs_parallel

        contexts = {
            "q-001": WorkerQueryContext(query_gap={"query_id": "q-001"}),
            "q-002": WorkerQueryContext(query_gap={"query_id": "q-002"}),
        }
        topics = [
            TopicSelection(rank=1, query_ids=["q-001"]),
            TopicSelection(rank=2, query_ids=["q-002"]),
        ]

        resp = _make_llm_response(_blueprint_json())
        call_count = 0

        async def _side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("LLM error")
            return resp

        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, side_effect=_side_effect):
            results = await build_briefs_parallel(contexts=contexts, topics=topics)

        # Index-preserving: 2 entries, one None (failed), one non-None
        assert len(results) == 2
        non_none = [r for r in results if r is not None]
        assert len(non_none) == 1

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        from core.content_engine.brief_builder import build_briefs_parallel

        max_concurrent_seen = 0
        current_concurrent = 0

        contexts = {f"q-{i}": WorkerQueryContext(query_gap={"query_id": f"q-{i}"})
                    for i in range(5)}
        topics = [TopicSelection(rank=i, query_ids=[f"q-{i}"]) for i in range(5)]

        resp = _make_llm_response(_blueprint_json())

        original_llm_call = AsyncMock(return_value=resp)

        async def _tracking_call(**kwargs):
            import asyncio
            nonlocal max_concurrent_seen, current_concurrent
            current_concurrent += 1
            max_concurrent_seen = max(max_concurrent_seen, current_concurrent)
            await asyncio.sleep(0.01)
            current_concurrent -= 1
            return resp

        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, side_effect=_tracking_call):
            results = await build_briefs_parallel(
                contexts=contexts, topics=topics, max_concurrent=2,
            )

        assert max_concurrent_seen <= 2
        assert len(results) == 5


# ═══════════════════════════════════════════════════════════════════════
# C4 Regression: brief_id_overrides prevents collision in re-brief
# ═══════════════════════════════════════════════════════════════════════


class TestBriefIdOverrides:
    """C4: build_briefs_parallel() must use brief_id_overrides when provided,
    so re-brief IDs never collide with the original 'brief-001'.
    """

    @pytest.mark.asyncio
    async def test_brief_id_override_used_when_provided(self):
        """When brief_id_overrides is supplied, the blueprint gets the override ID."""
        from core.content_engine.brief_builder import build_briefs_parallel

        contexts = {"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}
        topics = [TopicSelection(rank=1, query_ids=["q-001"])]

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            results = await build_briefs_parallel(
                contexts=contexts,
                topics=topics,
                brief_id_overrides=["rebrief-abc12345"],
            )

        assert len(results) == 1
        # Must use the override, NOT the default "brief-001"
        assert results[0].brief_id == "rebrief-abc12345", (
            f"Expected 'rebrief-abc12345', got '{results[0].brief_id}'"
        )

    @pytest.mark.asyncio
    async def test_override_does_not_collide_with_brief_001(self):
        """Re-brief must never produce brief-001, which would overwrite the original first piece."""
        from core.content_engine.brief_builder import build_briefs_parallel
        import uuid

        contexts = {"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}
        topics = [TopicSelection(rank=1, query_ids=["q-001"])]

        rebrief_id = f"rebrief-{uuid.uuid4().hex[:8]}"
        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            results = await build_briefs_parallel(
                contexts=contexts,
                topics=topics,
                brief_id_overrides=[rebrief_id],
            )

        assert results[0].brief_id != "brief-001", (
            "Re-brief must not use 'brief-001' — it would overwrite the original first piece"
        )
        assert results[0].brief_id == rebrief_id

    @pytest.mark.asyncio
    async def test_no_override_uses_default_numbering(self):
        """Without overrides, default brief-{N:03d} numbering is unchanged."""
        from core.content_engine.brief_builder import build_briefs_parallel

        contexts = {"q-001": WorkerQueryContext(query_gap={"query_id": "q-001"})}
        topics = [TopicSelection(rank=1, query_ids=["q-001"])]

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            results = await build_briefs_parallel(contexts=contexts, topics=topics)

        assert results[0].brief_id == "brief-001"

    @pytest.mark.asyncio
    async def test_partial_override_falls_back_for_remaining(self):
        """If overrides list is shorter than topics, extras use default numbering."""
        from core.content_engine.brief_builder import build_briefs_parallel

        contexts = {
            "q-001": WorkerQueryContext(query_gap={"query_id": "q-001"}),
            "q-002": WorkerQueryContext(query_gap={"query_id": "q-002"}),
        }
        topics = [
            TopicSelection(rank=1, query_ids=["q-001"]),
            TopicSelection(rank=2, query_ids=["q-002"]),
        ]

        resp = _make_llm_response(_blueprint_json())
        with patch("core.content_engine.brief_builder.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            results = await build_briefs_parallel(
                contexts=contexts,
                topics=topics,
                brief_id_overrides=["custom-id"],  # only 1 override for 2 topics
            )

        assert len(results) == 2
        ids = {bp.brief_id for bp in results}
        assert "custom-id" in ids
        assert "brief-002" in ids
