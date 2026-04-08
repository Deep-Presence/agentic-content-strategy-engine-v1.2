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

import json_repair
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


# ---------------------------------------------------------------------------
# Literal field coercion — map invalid LLM values to allowed defaults
# ---------------------------------------------------------------------------

_CONTENT_FORMAT_ALLOWED = {"long_blog", "short_faq", "pillar_page", "comparison", "how_to"}
_CONTENT_FORMAT_MAP: dict[str, str] = {
    "technical_guide": "how_to",
    "guide": "how_to",
    "tutorial": "how_to",
    "listicle": "short_faq",
    "faq": "short_faq",
    "deep_dive": "long_blog",
    "thought_leadership": "long_blog",
    "opinion": "long_blog",
    "case_study": "long_blog",
    "roundup": "comparison",
    "versus": "comparison",
    "ultimate_guide": "pillar_page",
}

_FUNNEL_STAGE_ALLOWED = {"awareness", "consideration", "decision", "retention"}
_CHANNEL_ALLOWED = {"blog", "help_center", "landing_page", "resource_hub"}


def _coerce_literal_fields(data: Any) -> Any:
    """Coerce known Literal fields to valid values before Pydantic validation.

    Handles content_format, funnel_stage, and channel — the three Literal
    fields on ContentBrief/ContentBlueprint that LLMs occasionally hallucinate.
    """
    if not isinstance(data, dict):
        return data

    cf = data.get("content_format")
    if isinstance(cf, str) and cf not in _CONTENT_FORMAT_ALLOWED:
        mapped = _CONTENT_FORMAT_MAP.get(cf, "long_blog")
        logger.warning(
            "Coerced content_format %r → %r (not in allowed set)", cf, mapped,
        )
        data["content_format"] = mapped

    fs = data.get("funnel_stage")
    if isinstance(fs, str) and fs not in _FUNNEL_STAGE_ALLOWED:
        logger.warning(
            "Coerced funnel_stage %r → 'awareness' (not in allowed set)", fs,
        )
        data["funnel_stage"] = "awareness"

    ch = data.get("channel")
    if isinstance(ch, str) and ch not in _CHANNEL_ALLOWED:
        logger.warning(
            "Coerced channel %r → 'blog' (not in allowed set)", ch,
        )
        data["channel"] = "blog"

    return data


# ---------------------------------------------------------------------------
# Null coercion — replace null values with sensible defaults
# ---------------------------------------------------------------------------

_TYPE_DEFAULTS: dict[str, Any] = {
    "string": "",
    "integer": 0,
    "number": 0.0,
    "boolean": False,
    "array": [],
    "object": {},
}


def _coerce_nulls(data: Any, model_cls: type[BaseModel]) -> Any:
    """Recursively replace null values with type-appropriate defaults.

    Without constrained decoding, LLMs may emit ``null`` for fields that
    Pydantic requires to be non-None.  This walks the data dict, consults
    the model's field annotations, and swaps nulls for safe defaults
    (empty string, 0, [], etc.) so that ``model_validate`` succeeds.
    """
    if not isinstance(data, dict):
        return data

    try:
        fields = model_cls.model_fields
    except AttributeError:
        return data

    for field_name, field_info in fields.items():
        if field_name not in data:
            continue
        if data[field_name] is not None:
            # Recurse into nested BaseModel fields
            anno = field_info.annotation
            if anno is not None:
                origin = getattr(anno, "__origin__", None)
                if origin is list and isinstance(data[field_name], list):
                    args = getattr(anno, "__args__", ())
                    if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                        data[field_name] = [
                            _coerce_nulls(item, args[0])
                            if isinstance(item, dict) else item
                            for item in data[field_name]
                        ]
                elif isinstance(anno, type) and issubclass(anno, BaseModel) and isinstance(data[field_name], dict):
                    data[field_name] = _coerce_nulls(data[field_name], anno)
            continue

        # data[field_name] is None — check if the field is Optional first
        import typing

        anno = field_info.annotation
        if anno is None:
            continue

        # If the field is Optional (Union[X, None]), None is valid — leave it
        origin = getattr(anno, "__origin__", None)
        if origin is typing.Union:
            args = getattr(anno, "__args__", ())
            if type(None) in args:
                continue  # Optional field — None is a valid value

        # Field is required and non-Optional — coerce null to a safe default
        if origin is list:
            data[field_name] = []
        elif origin is dict:
            data[field_name] = {}
        elif isinstance(anno, type):
            if issubclass(anno, str):
                data[field_name] = ""
            elif issubclass(anno, bool):
                data[field_name] = False
            elif issubclass(anno, int):
                data[field_name] = 0
            elif issubclass(anno, float):
                data[field_name] = 0.0
            elif issubclass(anno, list):
                data[field_name] = []
            elif issubclass(anno, dict):
                data[field_name] = {}
            else:
                data[field_name] = ""
        else:
            data[field_name] = ""

    return data


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

    2-layer parsing strategy:
    1. Direct parse (handles well-formed JSON — fast path)
    2. json_repair library (handles missing commas, unclosed braces,
       trailing commas, unescaped chars, truncation, etc.)

    Raises:
        ValueError: If parsing fails after all attempts.
    """
    raw = _extract_json_block(text)

    # Layer 1: direct parse (strict=False tolerates control chars in strings)
    try:
        data = json.loads(raw, strict=False)
        _coerce_literal_fields(data)
        _coerce_nulls(data, model_cls)
        return model_cls.model_validate(data)
    except (json.JSONDecodeError, Exception):
        pass

    # Layer 2: json_repair — handles missing commas, unclosed brackets,
    # trailing commas, single-line comments, truncated output, etc.
    try:
        data = json_repair.loads(raw)
        logger.info(
            "json_repair succeeded for %s (repaired malformed LLM output)",
            model_cls.__name__,
        )
        _coerce_literal_fields(data)
        _coerce_nulls(data, model_cls)
        return model_cls.model_validate(data)
    except Exception as exc:
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
