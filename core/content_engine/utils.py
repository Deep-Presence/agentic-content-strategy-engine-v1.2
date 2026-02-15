"""Shared utilities for the Content Generation Engine.

- safe_parse: robust JSON → Pydantic parsing with retry/truncation
- _retry_async_anthropic: retry wrapper for Anthropic SDK calls
- _estimate_tokens: pre-flight context window guard
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Any, Callable, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


# ---------------------------------------------------------------------------
# safe_parse — robust LLM JSON → Pydantic
# ---------------------------------------------------------------------------


def _extract_json_block(text: str) -> str:
    """Extract JSON from markdown code fences or bare JSON."""
    # Try ```json ... ``` first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try bare { ... } or [ ... ]
    for start, end in [("{", "}"), ("[", "]")]:
        idx_start = text.find(start)
        idx_end = text.rfind(end)
        if idx_start != -1 and idx_end > idx_start:
            return text[idx_start : idx_end + 1]
    return text.strip()


def safe_parse(text: str, model_cls: Type[M]) -> M:
    """Parse LLM text output into a Pydantic model.

    Handles:
    - JSON wrapped in markdown code fences
    - Trailing commas, comments
    - Falls back to re-extraction on first failure

    Raises:
        ValueError: If parsing fails after all attempts.
    """
    raw = _extract_json_block(text)

    # Attempt 1: direct parse
    try:
        data = json.loads(raw)
        return model_cls.model_validate(data)
    except (json.JSONDecodeError, Exception):
        pass

    # Attempt 2: strip trailing commas + single-line comments
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
    cleaned = re.sub(r"//.*$", "", cleaned, flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
        return model_cls.model_validate(data)
    except (json.JSONDecodeError, Exception) as exc:
        raise ValueError(
            f"Failed to parse LLM output into {model_cls.__name__}: {exc}\n"
            f"Raw (first 500 chars): {text[:500]}"
        ) from exc


# ---------------------------------------------------------------------------
# _retry_async_anthropic — retry with jittered backoff
# ---------------------------------------------------------------------------


async def _retry_async_anthropic(
    fn: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """Retry an async callable with jittered exponential backoff.

    Handles both Anthropic and OpenAI retryable errors.
    """
    import anthropic
    from openai import APIError as OpenAIAPIError
    from openai import RateLimitError as OpenAIRateLimitError

    retryable = (
        anthropic.RateLimitError,
        anthropic.APIError,
        anthropic.APIConnectionError,
        OpenAIRateLimitError,
        OpenAIAPIError,
    )

    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return await fn()
        except retryable as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, base_delay)
                logger.warning(
                    "Retry %d/%d after %s: %.1fs delay",
                    attempt + 1,
                    max_retries,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Token estimation — context window guard
# ---------------------------------------------------------------------------

# Rough approximation: 1 token ≈ 4 characters for English text.
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text length (rough heuristic)."""
    return len(text) // _CHARS_PER_TOKEN


def truncate_to_token_limit(
    text: str, max_tokens: int, *, label: str = "text"
) -> str:
    """Truncate text to fit within a token budget.

    Returns the original text if within budget, otherwise truncates
    with an appended note.
    """
    estimated = _estimate_tokens(text)
    if estimated <= max_tokens:
        return text
    max_chars = max_tokens * _CHARS_PER_TOKEN
    truncated = text[:max_chars]
    logger.warning(
        "Truncated %s from ~%d to ~%d tokens",
        label,
        estimated,
        max_tokens,
    )
    return truncated + f"\n\n[... truncated from ~{estimated} tokens to fit context window]"
