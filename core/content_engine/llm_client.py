"""Unified LLM client via OpenRouter for the v1.3 content pipeline.

All LLM calls in the v1.3 pipeline route through this module, providing:
  - Model abstraction (Anthropic, OpenAI, Perplexity, Google via one interface)
  - Retry logic with jittered exponential backoff
  - Token budget enforcement
  - Tracing via per-caller log_generation() calls (LangSmith)

The module uses the ``openai`` SDK pointed at OpenRouter's base URL.
Model strings use provider-prefixed format:
  - "anthropic/claude-sonnet-4-6"
  - "anthropic/claude-haiku-4-5"
  - "perplexity/sonar-pro"
  - "openai/gpt-5.2-2025-12-11"
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional

from core.models.content_generation_v13 import LLMResponse
from core.model_config.resolver import ModelConfigResolver
from core.model_config.schemas import ResolvedModelConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model prefix helper (canonical implementation in openrouter_client)
# ---------------------------------------------------------------------------

from core.shared_tools.openrouter_client import _ensure_model_prefix  # noqa: E402
from core.shared_tools.cost_tracker import track_llm_cost  # noqa: E402

# Backward-compatible alias
_ensure_litellm_model = _ensure_model_prefix


# ---------------------------------------------------------------------------
# OpenRouter configuration
# ---------------------------------------------------------------------------


def configure_openrouter() -> None:
    """Validate OpenRouter API key and pre-warm the client.

    Should be called once at pipeline startup.
    """
    from core.shared_tools.openrouter_client import get_async_client

    try:
        get_async_client()
        logger.info("OpenRouter client configured")
    except RuntimeError as exc:
        logger.warning("OpenRouter not configured: %s", exc)


# Backward-compatible alias for existing call sites
configure_litellm_callbacks = configure_openrouter


# ---------------------------------------------------------------------------
# Main LLM call function
# ---------------------------------------------------------------------------


async def llm_call(
    *,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    response_format: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> LLMResponse:
    """Make a unified LLM call through OpenRouter with retry and tracing.

    Args:
        model: Provider-prefixed model string (e.g. "anthropic/claude-sonnet-4-6").
        system: System prompt.
        user: User prompt.
        max_tokens: Maximum output tokens.
        temperature: Sampling temperature.
        response_format: Optional dict (e.g. {"type": "json_object"}) passed
            through as-is. None → no structured output constraint.
        metadata: Optional metadata dict (passed via extra_body for tracing).
        max_retries: Maximum retry attempts on transient failures.
        base_delay: Base delay in seconds for exponential backoff.

    Returns:
        LLMResponse with content, model, token counts, and finish reason.

    Raises:
        RuntimeError: If OpenRouter API key is not configured.
        Exception: If all retries exhausted.
    """
    from core.shared_tools.openrouter_client import get_async_client

    model = _ensure_model_prefix(model)
    client = get_async_client()

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    extra_body: Dict[str, Any] = {}
    if metadata:
        extra_body["metadata"] = metadata
    if extra_body:
        kwargs["extra_body"] = extra_body

    if response_format is not None:
        kwargs["response_format"] = response_format

    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(**kwargs)

            # Extract response fields
            choice = response.choices[0]
            usage = response.usage

            # Cost tracking (never raises)
            _meta = metadata or {}
            track_llm_cost(
                model=response.model or model,
                provider="openrouter",
                pipeline=_meta.get("pipeline", ""),
                pipeline_step=_meta.get("pipeline_step", ""),
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                company_slug=_meta.get("company_slug", ""),
                call_site="core.content_engine.llm_client",
                source="openrouter",
            )

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model or model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                finish_reason=choice.finish_reason or "",
            )

        except Exception as exc:
            last_error = exc

            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, base_delay)
                logger.warning(
                    "LLM call failed (attempt %d/%d, model=%s): %s. "
                    "Retrying in %.1fs",
                    attempt + 1,
                    max_retries,
                    model,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "LLM call failed after %d attempts (model=%s): %s",
                    max_retries,
                    model,
                    exc,
                )

    raise last_error  # type: ignore[misc]


async def llm_call_for_agent(
    *,
    workspace_id: str,
    workspace_slug: str,
    agent_key: str,
    system: str,
    user: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    response_format: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    resolver: ModelConfigResolver | None = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> LLMResponse:
    """Make a BYOK OpenRouter call by resolving workspace + agent config."""
    resolved = await _resolve_for_agent(
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
        agent_key=agent_key,
        resolver=resolver,
    )
    from core.shared_tools.openrouter_client import build_async_client_for_key

    client = build_async_client_for_key(
        resolved.api_key,
        base_url=resolved.base_url,
        timeout_s=resolved.timeout_s,
    )
    effective_max_tokens = (
        max_tokens
        if max_tokens is not None
        else resolved.max_tokens
        if resolved.max_tokens is not None
        else 4096
    )
    effective_temperature = (
        temperature
        if temperature is not None
        else resolved.temperature
        if resolved.temperature is not None
        else 0.0
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    kwargs: Dict[str, Any] = {
        "model": resolved.model,
        "messages": messages,
        "max_tokens": effective_max_tokens,
        "temperature": effective_temperature,
    }
    extra_body: Dict[str, Any] = dict(resolved.extra_body or {})
    if metadata:
        extra_body["metadata"] = metadata
    if extra_body:
        kwargs["extra_body"] = extra_body
    if response_format is not None:
        kwargs["response_format"] = response_format

    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            usage = response.usage
            _meta = metadata or {}
            response_model = response.model or resolved.model
            track_llm_cost(
                model=response_model,
                provider="openrouter",
                pipeline=_meta.get("pipeline", ""),
                pipeline_step=_meta.get("pipeline_step", ""),
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                company_slug=_meta.get("company_slug", workspace_slug),
                call_site="core.content_engine.llm_client.llm_call_for_agent",
                source="openrouter",
                run_id=_meta.get("run_id"),
                workspace_id=workspace_id,
                agent_key=agent_key,
                credential_id=resolved.credential_id,
                model_config_id=resolved.model_config_id,
                actual_provider=_actual_provider(response_model),
                workspace_billed=True,
            )
            return LLMResponse(
                content=choice.message.content or "",
                model=response_model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                finish_reason=choice.finish_reason or "",
            )
        except Exception as exc:
            last_error = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, base_delay)
                logger.warning(
                    "BYOK LLM call failed (attempt %d/%d, agent=%s, model=%s): %s. Retrying in %.1fs",
                    attempt + 1,
                    max_retries,
                    agent_key,
                    resolved.model,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "BYOK LLM call failed after %d attempts (agent=%s, model=%s): %s",
                    max_retries,
                    agent_key,
                    resolved.model,
                    exc,
                )
    raise last_error  # type: ignore[misc]


async def _resolve_for_agent(
    *,
    workspace_id: str,
    workspace_slug: str,
    agent_key: str,
    resolver: ModelConfigResolver | None,
) -> ResolvedModelConfig:
    if resolver is not None:
        return await resolver.resolve(workspace_id, workspace_slug, agent_key)

    from core.db.engine import get_session_factory
    from core.db.repositories.model_config_repo import (
        WorkspaceAgentModelConfigRepository,
        WorkspaceLLMCredentialRepository,
    )
    from core.model_config.credentials import resolve_fernet_key

    factory = get_session_factory()
    async with factory() as session:
        default_resolver = ModelConfigResolver(
            credential_repo=WorkspaceLLMCredentialRepository(session),
            config_repo=WorkspaceAgentModelConfigRepository(session),
            fernet_key=resolve_fernet_key(),
        )
        return await default_resolver.resolve(workspace_id, workspace_slug, agent_key)


def _actual_provider(model: str) -> str:
    return model.split("/", 1)[0] if "/" in model else ""


# ---------------------------------------------------------------------------
# Embedding helper (pass-through to existing shared tools)
# ---------------------------------------------------------------------------


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed texts using the existing async embedding client.

    This is a pass-through to the existing shared_tools embedding client,
    keeping all embedding calls consistent across v1.0 and v1.3.
    """
    from core.shared_tools.async_embedding_client import async_embed_texts

    return await async_embed_texts(texts)
