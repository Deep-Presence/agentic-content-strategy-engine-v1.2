"""Cost tracking for non-OpenRouter LLM calls.

Emits structured log events with token usage and estimated cost for native
API call sites that cannot be routed through OpenRouter (web search, grounding,
reasoning APIs, LangGraph agents).  Events use the ``llm_cost`` logger and are
wired through the structlog stdlib bridge for consistent JSON output.

Usage::

    from core.shared_tools.cost_tracker import track_llm_cost, extract_usage_anthropic_http

    pt, ct = extract_usage_anthropic_http(data)
    track_llm_cost(
        model="claude-sonnet-4-6", provider="anthropic",
        pipeline="gap_analysis", pipeline_step="s3_claude_engine",
        prompt_tokens=pt, completion_tokens=ct,
    )

Last updated: 2026-03-30
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("llm_cost")

# ---------------------------------------------------------------------------
# Approximate pricing per 1M tokens (input_cost, output_cost) in USD.
# Fuzzy prefix matching: "gpt-5.2-2025-12-11" matches "gpt-5.2".
# ---------------------------------------------------------------------------

PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
    "claude-haiku-4-5": (0.80, 4.00),
    "gpt-5.2": (2.00, 8.00),
    "o1": (15.00, 60.00),
    "o3-mini": (1.10, 4.40),
    "gemini-3-flash-preview": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
    "sonar-pro": (3.00, 15.00),
    "sonar-deep-research": (2.00, 8.00),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def _match_price(model: str) -> tuple[float, float]:
    """Fuzzy-match *model* against :data:`PRICING`.

    Strips ``provider/`` prefix, then tries exact match followed by
    longest-prefix match.  Returns ``(0.0, 0.0)`` if nothing matches.
    """
    # Strip provider prefix  ("anthropic/claude-sonnet-4-6" → "claude-sonnet-4-6")
    bare = model.split("/", 1)[-1] if "/" in model else model

    # 1. Exact match
    if bare in PRICING:
        return PRICING[bare]

    # 2. Longest-prefix match (e.g. "gpt-5.2-2025-12-11" → "gpt-5.2")
    best_key = ""
    for key in PRICING:
        if bare.startswith(key) and len(key) > len(best_key):
            best_key = key
    if best_key:
        return PRICING[best_key]

    return (0.0, 0.0)


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def estimate_cost(
    *,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Return estimated USD cost.  Returns ``0.0`` if model is unknown."""
    inp_price, out_price = _match_price(model)
    if inp_price == 0.0 and out_price == 0.0:
        return 0.0
    return (prompt_tokens / 1_000_000) * inp_price + (completion_tokens / 1_000_000) * out_price


# ---------------------------------------------------------------------------
# Structured cost event
# ---------------------------------------------------------------------------


def track_llm_cost(
    *,
    model: str,
    provider: str,
    pipeline: str,
    pipeline_step: str,
    prompt_tokens: int,
    completion_tokens: int,
    company_slug: str = "",
    call_site: str = "",
    extra: dict[str, Any] | None = None,
    source: str = "native",
) -> None:
    """Emit a structured log event with cost data.  **Never raises.**

    The event is logged at INFO level on the ``llm_cost`` logger (wired
    through the structlog stdlib bridge).  All fields are attached as
    ``extra`` so they appear as top-level keys in JSON output.
    """
    try:
        cost = estimate_cost(
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        fields: dict[str, Any] = {
            "model": model,
            "provider": provider,
            "pipeline": pipeline,
            "pipeline_step": pipeline_step,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "estimated_cost_usd": cost,
            "company_slug": company_slug,
            "call_site": call_site,
            "source": source,
        }
        if extra:
            fields.update(extra)
        logger.info("llm_cost_tracked", extra=fields)
    except Exception:  # noqa: BLE001 — must never propagate
        try:
            logger.warning("track_llm_cost failed silently", exc_info=True)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Usage extractors — one per provider response format
# ---------------------------------------------------------------------------


def extract_usage_anthropic_http(data: dict) -> tuple[int, int]:
    """Extract ``(prompt_tokens, completion_tokens)`` from raw Anthropic JSON."""
    usage = data.get("usage") or {}
    return (
        usage.get("input_tokens", 0) or 0,
        usage.get("output_tokens", 0) or 0,
    )


def extract_usage_gemini_http(data: dict) -> tuple[int, int]:
    """Extract from raw Gemini JSON (``usageMetadata``)."""
    meta = data.get("usageMetadata") or {}
    return (
        meta.get("promptTokenCount", 0) or 0,
        meta.get("candidatesTokenCount", 0) or 0,
    )


def extract_usage_openai_responses(response: Any) -> tuple[int, int]:
    """Extract from OpenAI ``responses.create()`` SDK response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return (0, 0)
    return (
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
    )


def extract_usage_anthropic_sdk(response: Any) -> tuple[int, int]:
    """Extract from ``anthropic.AsyncAnthropic().messages.create()`` response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return (0, 0)
    return (
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
    )


def extract_usage_litellm(response: Any) -> tuple[int, int]:
    """Extract from a LiteLLM response object."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return (0, 0)
    return (
        getattr(usage, "prompt_tokens", 0) or 0,
        getattr(usage, "completion_tokens", 0) or 0,
    )


def extract_usage_langchain_openai(response: Any) -> tuple[int, int]:
    """Extract ``(prompt_tokens, completion_tokens)`` from a LangChain ChatOpenAI AIMessage.

    ``ChatOpenAI`` populates ``response_metadata.token_usage`` with
    OpenAI-format keys: ``prompt_tokens``, ``completion_tokens``.
    """
    meta = getattr(response, "response_metadata", {})
    usage = meta.get("token_usage", {})
    if not isinstance(usage, dict):
        return (0, 0)
    return (
        usage.get("prompt_tokens", 0) or 0,
        usage.get("completion_tokens", 0) or 0,
    )
