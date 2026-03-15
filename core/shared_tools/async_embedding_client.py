"""Async OpenAI embedding client.

Async counterpart of embedding_client.py for the async-first pipeline.
Uses AsyncOpenAI with semaphore-controlled batching and retry with jittered backoff.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Callable, List, TypeVar

from openai import AsyncOpenAI, APIError, RateLimitError

from core.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def _retry_async(
    fn: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    *,
    retryable_exceptions: tuple = (RateLimitError, APIError),
) -> T:
    """Retry an async callable with jittered exponential backoff.

    Args:
        fn: Async callable to retry.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds (doubles each retry + jitter).
        retryable_exceptions: Exception types that trigger a retry.

    Returns:
        Result of the callable.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return await fn()
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
                logger.warning(
                    "Retry %d/%d after %s: %.1fs delay",
                    attempt + 1,
                    max_retries,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def async_embed_texts(
    texts: List[str],
    batch_size: int | None = None,
    max_concurrent_batches: int | None = None,
) -> List[List[float]]:
    """Embed texts using AsyncOpenAI with concurrent batching and retry.

    Dispatches multiple batches concurrently for speed, with a semaphore
    to cap API pressure. Results are reassembled in input order.

    Args:
        texts: Texts to embed.
        batch_size: Number of texts per API call (default: settings).
        max_concurrent_batches: Max batches in flight (default: settings).

    Returns:
        List of embedding vectors, one per input text, in the same order as input.
    """
    if not texts:
        return []

    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env.local to enable embeddings."
        )
    model = settings.embedding_model
    if not model:
        raise RuntimeError("EMBEDDING_MODEL is not set. Add it to .env.local.")

    effective_batch_size = batch_size if batch_size is not None else settings.gap_analysis_s5_embed_batch_size
    effective_concurrency = (
        max_concurrent_batches
        if max_concurrent_batches is not None
        else settings.gap_analysis_s5_embed_concurrent_batches
    )

    async with AsyncOpenAI(api_key=api_key) as client:
        batches = [texts[i : i + effective_batch_size] for i in range(0, len(texts), effective_batch_size)]
        sem = asyncio.Semaphore(effective_concurrency)

        async def _embed_batch(
            batch: List[str], batch_idx: int
        ) -> tuple[int, List[List[float]]]:
            async def _call():
                return await client.embeddings.create(model=model, input=batch)

            async with sem:
                response = await _retry_async(_call, max_retries=3, base_delay=1.0)
                sorted_data = sorted(response.data, key=lambda d: d.index)
                return batch_idx, [item.embedding for item in sorted_data]

        results = await asyncio.gather(
            *[_embed_batch(b, i) for i, b in enumerate(batches)]
        )

        # Sort by batch_idx to maintain input order across concurrent batches
        results_sorted = sorted(results, key=lambda x: x[0])
        return [emb for _, batch_embs in results_sorted for emb in batch_embs]
