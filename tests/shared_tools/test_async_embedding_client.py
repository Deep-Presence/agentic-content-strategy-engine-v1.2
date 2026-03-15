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
        "gap_analysis_s5_embed_batch_size": 256,
        "gap_analysis_s5_embed_concurrent_batches": 4,
    }
    defaults.update(overrides)
    mock_s = MagicMock(**defaults)
    return patch("core.shared_tools.async_embedding_client.settings", mock_s)


def _make_mock_client(create_side_effect):
    """Build a MagicMock AsyncOpenAI client with async context manager support."""
    mock_client = MagicMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = AsyncMock(side_effect=create_side_effect)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


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

        mock_client = _make_mock_client(fake_create)

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

        mock_client = _make_mock_client(fake_create)

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

        mock_client = _make_mock_client(fake_create_shuffled)

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


class TestConcurrentBatchDispatch:
    """Tests for Phase 4: concurrent batch dispatch."""

    @pytest.mark.asyncio
    async def test_concurrent_batches_fire_in_parallel(self):
        """Multiple batches should execute concurrently, not sequentially."""
        import time

        texts = [f"text_{i}" for i in range(12)]
        call_times: list[float] = []

        async def fake_create(*, model, input, **kw):
            call_times.append(time.monotonic())
            await asyncio.sleep(0.05)  # Simulate API latency
            return _make_response(input)

        mock_client = _make_mock_client(fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
            from core.shared_tools.async_embedding_client import async_embed_texts

            start = time.monotonic()
            result = await async_embed_texts(texts, batch_size=3, max_concurrent_batches=4)
            elapsed = time.monotonic() - start

        assert len(result) == 12
        # 12 texts / batch_size 3 = 4 batches, all concurrent (max_concurrent=4)
        # If sequential: 4 * 0.05s = 0.2s. If concurrent: ~0.05s.
        assert elapsed < 0.15, f"Batches appear sequential: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_order_preserved_across_concurrent_batches(self):
        """Embeddings must maintain input order across concurrent batches."""
        texts = [f"len{i:03d}" for i in range(20)]

        async def fake_create(*, model, input, **kw):
            await asyncio.sleep(0.01)  # Simulate varying latency
            return _make_response(input)

        mock_client = _make_mock_client(fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
            from core.shared_tools.async_embedding_client import async_embed_texts

            result = await async_embed_texts(texts, batch_size=4, max_concurrent_batches=3)

        assert len(result) == 20
        # Each embedding's first value is float(len(text) + 0) = float(len(text))
        # "len000" has len 6, "len001" has len 6, etc.
        # All texts have same length (6), so all embeddings[0] should be 6.0
        for i, emb in enumerate(result):
            assert emb[0] == float(len(texts[i])), (
                f"Order broken at index {i}: expected {float(len(texts[i]))}, got {emb[0]}"
            )

    @pytest.mark.asyncio
    async def test_backward_compat_explicit_batch_size(self):
        """Old callers passing batch_size=64 should still work."""
        texts = ["hello", "world"]

        async def fake_create(*, model, input, **kw):
            return _make_response(input)

        mock_client = _make_mock_client(fake_create)

        with _patch_settings(), \
             patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
            from core.shared_tools.async_embedding_client import async_embed_texts

            result = await async_embed_texts(texts, batch_size=64)

        assert len(result) == 2
        assert mock_client.embeddings.create.await_count == 1

    @pytest.mark.asyncio
    async def test_concurrency_semaphore_respected(self):
        """Should never exceed max_concurrent_batches simultaneous API calls."""
        texts = [f"text_{i}" for i in range(20)]
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def tracking_create(*, model, input, **kw):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.02)
            async with lock:
                current_concurrent -= 1
            return _make_response(input)

        mock_client = _make_mock_client(tracking_create)

        with _patch_settings(), \
             patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
            from core.shared_tools.async_embedding_client import async_embed_texts

            await async_embed_texts(texts, batch_size=4, max_concurrent_batches=2)

        assert max_concurrent <= 2, f"Max concurrent was {max_concurrent}, expected <= 2"


class TestClientLifecycle:
    """Tests for Fix 7: AsyncOpenAI client lifecycle management."""

    @pytest.mark.asyncio
    async def test_client_used_as_context_manager(self):
        """AsyncOpenAI should be entered/exited via async with for proper cleanup."""
        texts = ["hello"]

        async def fake_create(*, model, input, **kw):
            return _make_response(input)

        mock_client = _make_mock_client(fake_create)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _patch_settings(), \
             patch("core.shared_tools.async_embedding_client.AsyncOpenAI", return_value=mock_client):
            from core.shared_tools.async_embedding_client import async_embed_texts

            result = await async_embed_texts(texts, batch_size=64)

        assert len(result) == 1
        mock_client.__aenter__.assert_awaited_once()
        mock_client.__aexit__.assert_awaited_once()


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
