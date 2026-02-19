"""Tests for async embedding client — TDD: written BEFORE implementation."""
from __future__ import annotations

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

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
        "openai_api_key": "test-key",
        "embedding_model": "text-embedding-3-small",
    }
    defaults.update(overrides)
    mock_s = MagicMock(**defaults)
    return patch("core.shared_tools.async_embedding_client.settings", mock_s)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAsyncEmbedTexts:
    """Tests for async_embed_texts()."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        """Calling with empty list should return empty immediately, no API call."""
        from core.shared_tools.async_embedding_client import async_embed_texts

        result = await async_embed_texts([])
        assert result == []

    @pytest.mark.asyncio
    async def test_single_batch(self):
        """Texts fitting in a single batch should make exactly 1 API call."""
        texts = ["hello", "world"]

        async def fake_create(*, model, input, **kw):
            return _make_response(input)

        mock_client = MagicMock()
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(side_effect=fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
            from core.shared_tools.async_embedding_client import async_embed_texts

            result = await async_embed_texts(texts, batch_size=64)

        assert len(result) == 2
        assert mock_client.embeddings.create.await_count == 1

    @pytest.mark.asyncio
    async def test_multiple_batches(self):
        """Texts exceeding batch_size should split into multiple API calls."""
        texts = [f"text_{i}" for i in range(10)]

        async def fake_create(*, model, input, **kw):
            return _make_response(input)

        mock_client = MagicMock()
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(side_effect=fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
            from core.shared_tools.async_embedding_client import async_embed_texts

            result = await async_embed_texts(texts, batch_size=3)

        assert len(result) == 10
        # 10 texts / batch_size 3 = 4 batches (3+3+3+1)
        assert mock_client.embeddings.create.await_count == 4

    @pytest.mark.asyncio
    async def test_preserves_order_via_index(self):
        """Embeddings should be ordered by response.data[i].index, not position."""
        texts = ["aaa", "bb", "c"]

        async def fake_create_shuffled(*, model, input, **kw):
            # Return data in REVERSE index order to test index-based reordering
            data = [
                FakeEmbeddingData(embedding=[float(len(t))] * 4, index=idx)
                for idx, t in enumerate(input)
            ]
            data.reverse()  # Shuffle — implementation must sort by .index
            return FakeEmbeddingResponse(data=data)

        mock_client = MagicMock()
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock(side_effect=fake_create_shuffled)

        with _patch_settings(), \
             patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
            from core.shared_tools.async_embedding_client import async_embed_texts

            result = await async_embed_texts(texts, batch_size=64)

        # result[0] should correspond to "aaa" (len=3), result[1] to "bb" (len=2), etc.
        assert result[0][0] == 3.0  # "aaa"
        assert result[1][0] == 2.0  # "bb"
        assert result[2][0] == 1.0  # "c"

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self):
        """Should raise RuntimeError when OPENAI_API_KEY is not set."""
        with _patch_settings(openai_api_key=None):
            from core.shared_tools.async_embedding_client import async_embed_texts

            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                await async_embed_texts(["test"])

    @pytest.mark.asyncio
    async def test_missing_model_raises(self):
        """Should raise RuntimeError when EMBEDDING_MODEL is not set."""
        with _patch_settings(embedding_model=None):
            from core.shared_tools.async_embedding_client import async_embed_texts

            with pytest.raises(RuntimeError, match="EMBEDDING_MODEL"):
                await async_embed_texts(["test"])


class TestRetryAsync:
    """Tests for the _retry_async helper."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Should retry on 429 errors with backoff."""
        from openai import RateLimitError

        call_count = 0

        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError(
                    message="Rate limit exceeded",
                    response=MagicMock(status_code=429),
                    body=None,
                )
            return "success"

        from core.shared_tools.async_embedding_client import _retry_async

        result = await _retry_async(flaky_fn, max_retries=3, base_delay=0.01)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self):
        """Should raise after max retries exhausted."""
        from openai import RateLimitError

        async def always_fails():
            raise RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None,
            )

        from core.shared_tools.async_embedding_client import _retry_async

        with pytest.raises(RateLimitError):
            await _retry_async(always_fails, max_retries=2, base_delay=0.01)
