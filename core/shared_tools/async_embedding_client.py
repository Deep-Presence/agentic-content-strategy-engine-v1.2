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
    texts: List[str], batch_size: int = 64
) -> List[List[float]]:
    """Embed texts using AsyncOpenAI with batching and retry.

    Args:
        texts: Texts to embed.
        batch_size: Number of texts per API call.

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

    client = AsyncOpenAI(api_key=api_key)
    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        async def _call(b=batch):
            return await client.embeddings.create(model=model, input=b)

        response = await _retry_async(_call, max_retries=3, base_delay=1.0)

        # Sort by response.data[i].index to guarantee correct ordering
        # (Codex recommendation: don't rely on positional order)
        sorted_data = sorted(response.data, key=lambda d: d.index)
        all_embeddings.extend([item.embedding for item in sorted_data])

    return all_embeddings
