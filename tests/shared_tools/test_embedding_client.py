"""Tests for sync embedding client — TDD: written BEFORE migration to OpenRouter."""
from __future__ import annotations

import time
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import FakeEmbeddingData, FakeEmbeddingResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_response(texts: List[str], dim: int = 8) -> FakeEmbeddingResponse:
    """Build deterministic embedding response."""
    data = [
        FakeEmbeddingData(
            embedding=[float(len(t) + i) for i in range(dim)],
            index=idx,
        )
        for idx, t in enumerate(texts)
    ]
    return FakeEmbeddingResponse(data=data)


def _patch_settings(**overrides):
    """Patch settings with test defaults + any overrides."""
    defaults = {
        "embedding_model": "text-embedding-3-small",
    }
    defaults.update(overrides)
    mock_s = MagicMock(**defaults)
    return patch("core.shared_tools.embedding_client.settings", mock_s)


def _make_mock_client(create_side_effect):
    """Build a MagicMock sync OpenAI client."""
    mock_client = MagicMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = MagicMock(side_effect=create_side_effect)
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestEmbedTexts:
    """Tests for embed_texts()."""

    def test_empty_input_returns_empty(self):
        """Calling with empty list should return empty immediately, no API call."""
        from core.shared_tools.embedding_client import embed_texts

        result = embed_texts([])
        assert result == []

    def test_uses_openrouter_sync_client(self):
        """Should use get_sync_client() from OpenRouter factory."""
        texts = ["hello", "world"]

        def fake_create(*, model, input, **kw):
            return _make_response(input)

        mock_client = _make_mock_client(fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.embedding_client.get_sync_client", return_value=mock_client):
            from core.shared_tools.embedding_client import embed_texts

            result = embed_texts(texts, batch_size=64)

        assert len(result) == 2
        assert mock_client.embeddings.create.call_count == 1

    def test_model_prefix_applied(self):
        """Model passed to API should be prefixed for OpenRouter."""
        texts = ["test"]
        captured_models = []

        def fake_create(*, model, input, **kw):
            captured_models.append(model)
            return _make_response(input)

        mock_client = _make_mock_client(fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.embedding_client.get_sync_client", return_value=mock_client):
            from core.shared_tools.embedding_client import embed_texts

            embed_texts(texts)

        assert captured_models[0] == "openai/text-embedding-3-small"

    def test_batching(self):
        """Texts exceeding batch_size should split into multiple API calls."""
        texts = [f"text_{i}" for i in range(10)]

        def fake_create(*, model, input, **kw):
            return _make_response(input)

        mock_client = _make_mock_client(fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.embedding_client.get_sync_client", return_value=mock_client):
            from core.shared_tools.embedding_client import embed_texts

            result = embed_texts(texts, batch_size=3)

        assert len(result) == 10
        # 10 texts / batch_size 3 = 4 batches (3+3+3+1)
        assert mock_client.embeddings.create.call_count == 4

    def test_missing_openrouter_key_propagates(self):
        """RuntimeError from factory should propagate when OPENROUTER_API_KEY missing."""
        with _patch_settings(), \
             patch(
                 "core.shared_tools.embedding_client.get_sync_client",
                 side_effect=RuntimeError("OPENROUTER_API_KEY is not set"),
             ):
            from core.shared_tools.embedding_client import embed_texts

            with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
                embed_texts(["test"])

    def test_missing_model_raises(self):
        """Should raise RuntimeError when EMBEDDING_MODEL is not set."""
        def fake_client():
            return MagicMock()

        with _patch_settings(embedding_model=None), \
             patch("core.shared_tools.embedding_client.get_sync_client", side_effect=fake_client):
            from core.shared_tools.embedding_client import embed_texts

            with pytest.raises(RuntimeError, match="EMBEDDING_MODEL"):
                embed_texts(["test"])


class TestSyncRetry:
    """Tests for _retry_sync wrapper in sync embedding client."""

    def test_retry_on_rate_limit(self):
        """Should retry on RateLimitError with backoff."""
        from openai import RateLimitError

        call_count = 0

        def flaky_create(*, model, input, **kw):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError(
                    message="Rate limit exceeded",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            return _make_response(input)

        mock_client = _make_mock_client(flaky_create)

        with _patch_settings(), \
             patch("core.shared_tools.embedding_client.get_sync_client", return_value=mock_client):
            from core.shared_tools.embedding_client import embed_texts

            result = embed_texts(["hello"], batch_size=64)

        assert len(result) == 1
        assert call_count == 3

    def test_retry_exhausted_raises(self):
        """Should raise after max retries exhausted."""
        from openai import RateLimitError

        def always_fails(*, model, input, **kw):
            raise RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None,
            )

        mock_client = _make_mock_client(always_fails)

        with _patch_settings(), \
             patch("core.shared_tools.embedding_client.get_sync_client", return_value=mock_client):
            from core.shared_tools.embedding_client import embed_texts

            with pytest.raises(RateLimitError):
                embed_texts(["test"], batch_size=64)


class TestEmbedTextsCostTracking:
    """Verify track_llm_cost() is called per batch in embed_texts()."""

    def test_cost_tracked_per_batch(self):
        texts = ["hello", "world", "test"]

        def fake_create(*, model, input, **kw):
            resp = _make_response(input)
            resp.usage = MagicMock(prompt_tokens=len(input) * 10)
            return resp

        mock_client = _make_mock_client(fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.embedding_client.get_sync_client", return_value=mock_client), \
             patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            from core.shared_tools.embedding_client import embed_texts

            embed_texts(texts, batch_size=2)  # 2 batches: [2, 1]

        assert mock_track.call_count == 2
        kw0 = mock_track.call_args_list[0][1]
        assert kw0["pipeline"] == "embeddings"
        assert kw0["pipeline_step"] == "embed_texts"
        assert kw0["prompt_tokens"] == 20  # 2 texts * 10
        assert kw0["completion_tokens"] == 0
        assert kw0["source"] == "openrouter"

    def test_no_cost_tracked_for_empty_input(self):
        with patch("core.shared_tools.cost_tracker.track_llm_cost") as mock_track:
            from core.shared_tools.embedding_client import embed_texts

            embed_texts([])

        mock_track.assert_not_called()
