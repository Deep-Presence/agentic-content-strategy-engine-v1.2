"""Knowledge Base specialist agents — 4 Perplexity + 1 Brand Perception + 1 Synthesis.

Tier 1 (Agents 1-4): Perplexity sonar-deep-research via asyncio.to_thread + wait_for.
Tier 2 (Agent 5): Anthropic AsyncAnthropic + web_search_20250305 server-side tool.
Tier 3 (Synthesis): LangGraph create_react_agent + Claude Opus via OpenRouter (ChatOpenAI) with read_file tool.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.storage.backends.base import StorageBackend

import anthropic
from langgraph.prebuilt import create_react_agent

from core.shared_tools.openrouter_client import (
    build_chat_openai_for_key,
    build_chat_openai_via_openrouter,
)

from core.config.settings import settings
from core.model_config.runtime import actual_provider, resolve_model_config_for_agent
from core.models.knowledge_base import KBAgentResult, KBDocType, KnowledgeBaseInput
from core.research.knowledge_base.tools import make_read_file_tool
from core.research.prompts.brand_perception import (
    build_brand_perception_user_prompt,
    get_brand_perception_system_prompt,
)
from core.research.prompts.company_overview import (
    build_company_overview_user_prompt,
    get_company_overview_system_prompt,
)
from core.research.prompts.competitor_scanner import (
    build_competitor_scanner_user_prompt,
    get_competitor_scanner_system_prompt,
)
from core.research.prompts.customer_reviews import (
    build_customer_reviews_user_prompt,
    get_customer_reviews_system_prompt,
)
from core.research.prompts.synthesis import (
    build_delta_synthesis_user_prompt,
    build_synthesis_user_prompt,
    get_delta_synthesis_system_prompt,
    get_synthesis_system_prompt,
)
from core.research.prompts.weakness_analyst import (
    build_weakness_analyst_user_prompt,
    get_weakness_analyst_system_prompt,
)
from core.research.tools import perplexity_client
from core.shared_tools.tracing import create_span, end_span, extract_provider, log_generation

logger = logging.getLogger(__name__)

# Maximum pause_turn continuation iterations for Brand Perception agent.
# Anthropic's server-side web_search tool can trigger pause_turn when the
# model hits its internal iteration limit. We cap retries to prevent
# unbounded loops and runaway token/cost consumption.
_MAX_PAUSE_TURNS = 5


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_synthesis_output(messages: Optional[List[Any]]) -> str:
    """Extract the last AI message text from create_react_agent output.

    Handles both string content and list-of-dicts content blocks.
    """
    if not messages:
        return ""
    for msg in reversed(messages):
        if getattr(msg, "type", None) != "ai":
            continue
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
            return "\n\n".join(parts)
    return ""


def _extract_text_with_citations(response: Any) -> str:
    """Extract text blocks from an Anthropic messages.create() response.

    Filters out non-text blocks (server_tool_use, etc.) and joins text blocks.
    """
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Tier 1 — Perplexity Deep Research (Agents 1-4)
# ---------------------------------------------------------------------------


async def _run_perplexity_agent(
    doc_type: KBDocType,
    full_prompt: str,
    parent_span: Optional[Any] = None,
    timeout_s: float = 500.0,
    span_name: str = "agent",
    model: Optional[str] = None,
    company_slug: str = "",
    workspace_id: str = "",
    workspace_slug: str = "",
    agent_key: str = "",
) -> KBAgentResult:
    """Shared runner for Perplexity-based agents."""
    span = create_span(
        parent_span,
        f"agent/{span_name}",
        input_data={"doc_type": doc_type.value},
    )
    start = time.time()
    try:
        resolved = None
        if workspace_id and agent_key:
            resolved = await resolve_model_config_for_agent(
                workspace_id=workspace_id,
                workspace_slug=workspace_slug or company_slug,
                agent_key=agent_key,
            )
        effective_model = resolved.model if resolved is not None else model
        resolved_timeout = getattr(resolved, "timeout_s", None) if resolved is not None else None
        effective_timeout_s = (
            resolved_timeout if isinstance(resolved_timeout, (int, float)) else timeout_s
        )
        result_md, _pplx_usage = await asyncio.wait_for(
            asyncio.to_thread(
                perplexity_client.research, query=full_prompt, timeout_s=effective_timeout_s,
                model=effective_model,
                pipeline="knowledge_base",
                pipeline_step=doc_type.value,
                company_slug=company_slug,
                api_key=getattr(resolved, "api_key", None),
                base_url=getattr(resolved, "base_url", None),
                workspace_id=workspace_id if resolved is not None else None,
                agent_key=agent_key if resolved is not None else "",
                credential_id=getattr(resolved, "credential_id", None),
                model_config_id=getattr(resolved, "model_config_id", None),
                actual_provider=actual_provider(effective_model or "") if resolved is not None else "",
                workspace_billed=resolved is not None,
            ),
            timeout=effective_timeout_s,
        )
        _effective_model = effective_model or settings.perplexity_deep_research_model
        _kb_meta = {
            "pipeline": "knowledge_base",
            "pipeline_step": doc_type.value,
            "provider": "perplexity",
            "model": _effective_model,
            "company_slug": company_slug,
        }
        log_generation(
            span,
            span_name,
            _effective_model,
            full_prompt[:2000],
            result_md[:2000] if result_md else "",
            metadata=_kb_meta,
            usage=_pplx_usage,
        )
        end_span(span, output={"word_count": len(result_md.split()) if result_md else 0})
        return KBAgentResult(
            doc_type=doc_type,
            content_md=result_md,
            word_count=len(result_md.split()) if result_md else 0,
            execution_time_s=time.time() - start,
        )
    except asyncio.TimeoutError:
        end_span(span, error=f"Timeout after {timeout_s}s")
        return KBAgentResult(
            doc_type=doc_type,
            error=f"Timeout after {timeout_s}s",
            execution_time_s=time.time() - start,
        )
    except Exception as exc:
        end_span(span, error=str(exc))
        return KBAgentResult(
            doc_type=doc_type,
            error=str(exc),
            execution_time_s=time.time() - start,
        )


async def run_company_overview_agent(
    input_data: KnowledgeBaseInput,
    parent_span: Optional[Any] = None,
    timeout_s: float = 300.0,
    revision_note: Optional[str] = None,
) -> KBAgentResult:
    """Agent 1 — Company overview via Perplexity deep research."""
    system_prompt = get_company_overview_system_prompt()
    user_prompt = build_company_overview_user_prompt(input_data, revision_note=revision_note)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    return await _run_perplexity_agent(
        KBDocType.COMPANY_OVERVIEW, full_prompt, parent_span, timeout_s, "company-overview",
        model=settings.research_kb_company_overview_model,
        company_slug=input_data.company_slug or "",
        workspace_id=input_data.workspace_id,
        workspace_slug=input_data.workspace_slug,
        agent_key="research.kb.company_overview",
    )


async def run_customer_reviews_agent(
    input_data: KnowledgeBaseInput,
    parent_span: Optional[Any] = None,
    timeout_s: float = 300.0,
    revision_note: Optional[str] = None,
) -> KBAgentResult:
    """Agent 2 — Customer reviews via Perplexity deep research."""
    system_prompt = get_customer_reviews_system_prompt()
    user_prompt = build_customer_reviews_user_prompt(input_data, revision_note=revision_note)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    return await _run_perplexity_agent(
        KBDocType.CUSTOMER_REVIEWS, full_prompt, parent_span, timeout_s, "customer-reviews",
        model=settings.research_kb_customer_reviews_model,
        company_slug=input_data.company_slug or "",
        workspace_id=input_data.workspace_id,
        workspace_slug=input_data.workspace_slug,
        agent_key="research.kb.customer_reviews",
    )


async def run_competitor_scanner_agent(
    input_data: KnowledgeBaseInput,
    company_overview_md: str,
    parent_span: Optional[Any] = None,
    timeout_s: float = 300.0,
    revision_note: Optional[str] = None,
) -> KBAgentResult:
    """Agent 3 — Competitive landscape via Perplexity with upstream context."""
    system_prompt = get_competitor_scanner_system_prompt()
    user_prompt = build_competitor_scanner_user_prompt(
        input_data, company_overview_md, revision_note=revision_note,
    )
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    return await _run_perplexity_agent(
        KBDocType.COMPETITOR_REGISTRY, full_prompt, parent_span, timeout_s, "competitor-scanner",
        model=settings.research_kb_competitor_scanner_model,
        company_slug=input_data.company_slug or "",
        workspace_id=input_data.workspace_id,
        workspace_slug=input_data.workspace_slug,
        agent_key="research.kb.competitor_scanner",
    )


async def run_weakness_analyst_agent(
    input_data: KnowledgeBaseInput,
    company_overview_md: str,
    competitor_registry_md: str,
    parent_span: Optional[Any] = None,
    timeout_s: float = 300.0,
    revision_note: Optional[str] = None,
) -> KBAgentResult:
    """Agent 4 — Competitor weakness analysis via Perplexity with 2 upstream docs."""
    system_prompt = get_weakness_analyst_system_prompt()
    user_prompt = build_weakness_analyst_user_prompt(
        input_data, company_overview_md, competitor_registry_md,
        revision_note=revision_note,
    )
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    return await _run_perplexity_agent(
        KBDocType.WEAKNESS_ANALYSIS, full_prompt, parent_span, timeout_s, "weakness-analyst",
        model=settings.research_kb_weakness_analyst_model,
        company_slug=input_data.company_slug or "",
        workspace_id=input_data.workspace_id,
        workspace_slug=input_data.workspace_slug,
        agent_key="research.kb.weakness_analyst",
    )


# ---------------------------------------------------------------------------
# Tier 2 — Anthropic SDK + Native Web Search (Agent 5)
# ---------------------------------------------------------------------------


async def run_brand_perception_agent(
    input_data: KnowledgeBaseInput,
    upstream_docs: Dict[str, str],
    parent_span: Optional[Any] = None,
    timeout_s: float = 300.0,
    max_web_searches: int = 10,
    revision_note: Optional[str] = None,
) -> KBAgentResult:
    """Agent 5 — Brand perception via Anthropic SDK + web_search_20250305."""
    span = create_span(
        parent_span,
        "agent/brand-perception",
        input_data={"company": input_data.company_name},
    )
    start = time.time()
    try:
        system_prompt = get_brand_perception_system_prompt()
        user_prompt = build_brand_perception_user_prompt(
            input_data, upstream_docs, revision_note=revision_note,
        )

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        messages = [{"role": "user", "content": user_prompt}]
        tool_spec = {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_web_searches,
        }

        response = await asyncio.wait_for(
            client.messages.create(
                model=settings.research_kb_brand_perception_model,
                max_tokens=8192,
                system=system_prompt,
                messages=messages,
                tools=[tool_spec],
            ),
            timeout=timeout_s,
        )
        bp_model = settings.research_kb_brand_perception_model
        _bp_meta = {
            "pipeline": "knowledge_base",
            "pipeline_step": "brand_perception",
            "provider": "anthropic",
            "model": bp_model,
            "company_slug": input_data.company_slug or "",
        }
        from core.shared_tools.cost_tracker import extract_usage_anthropic_sdk, track_llm_cost

        _pt, _ct = extract_usage_anthropic_sdk(response)
        _total_pt, _total_ct = _pt, _ct
        track_llm_cost(
            model=bp_model, provider="anthropic", pipeline="knowledge_base",
            pipeline_step="brand_perception/turn-0", prompt_tokens=_pt,
            completion_tokens=_ct, company_slug=input_data.company_slug or "",
            call_site="core.research.knowledge_base.agents",
        )
        log_generation(
            span, "brand-perception/turn-0", bp_model,
            user_prompt[:2000], _extract_text_with_citations(response)[:2000],
            metadata=_bp_meta,
        )

        # Handle pause_turn loop — Claude hit server-side iteration limit.
        # Cap at _MAX_PAUSE_TURNS to prevent unbounded loops / runaway cost.
        pause_turns = 0
        while response.stop_reason == "pause_turn":
            pause_turns += 1
            if pause_turns >= _MAX_PAUSE_TURNS:
                logger.warning(
                    "Brand perception agent hit pause_turn limit (%d) for %s",
                    _MAX_PAUSE_TURNS,
                    input_data.company_name,
                )
                break
            messages.append({"role": "assistant", "content": response.content})
            response = await asyncio.wait_for(
                client.messages.create(
                    model=settings.research_kb_brand_perception_model,
                    max_tokens=8192,
                    system=system_prompt,
                    messages=messages,
                    tools=[tool_spec],
                ),
                timeout=timeout_s,
            )
            _pt, _ct = extract_usage_anthropic_sdk(response)
            _total_pt += _pt
            _total_ct += _ct
            track_llm_cost(
                model=bp_model, provider="anthropic", pipeline="knowledge_base",
                pipeline_step=f"brand_perception/turn-{pause_turns}",
                prompt_tokens=_pt, completion_tokens=_ct,
                company_slug=input_data.company_slug or "",
                call_site="core.research.knowledge_base.agents",
            )
            log_generation(
                span, f"brand-perception/turn-{pause_turns}", bp_model,
                "(continuation)", _extract_text_with_citations(response)[:2000],
                metadata=_bp_meta,
            )

        track_llm_cost(
            model=bp_model, provider="anthropic", pipeline="knowledge_base",
            pipeline_step="brand_perception/total",
            prompt_tokens=_total_pt, completion_tokens=_total_ct,
            company_slug=input_data.company_slug or "",
            call_site="core.research.knowledge_base.agents",
        )
        is_partial = pause_turns >= _MAX_PAUSE_TURNS

        result_md = _extract_text_with_citations(response)
        end_span(span, output={"word_count": len(result_md.split()) if result_md else 0})
        return KBAgentResult(
            doc_type=KBDocType.BRAND_PERCEPTION,
            content_md=result_md,
            word_count=len(result_md.split()) if result_md else 0,
            execution_time_s=time.time() - start,
            is_partial=is_partial,
        )
    except asyncio.TimeoutError:
        end_span(span, error=f"Timeout after {timeout_s}s")
        return KBAgentResult(
            doc_type=KBDocType.BRAND_PERCEPTION,
            error=f"Timeout after {timeout_s}s",
            execution_time_s=time.time() - start,
        )
    except Exception as exc:
        end_span(span, error=str(exc))
        return KBAgentResult(
            doc_type=KBDocType.BRAND_PERCEPTION,
            error=str(exc),
            execution_time_s=time.time() - start,
        )


# ---------------------------------------------------------------------------
# Tier 3 — LangGraph Synthesis Agent
# ---------------------------------------------------------------------------


def build_synthesis_agent(
    model: Optional[Any] = None,
    *,
    storage_backend: Optional[StorageBackend] = None,
    storage_prefix: str = "knowledge_base/",
    checkpointer: Optional[Any] = None,
    # Deprecated — ignored when storage_backend is provided
    kb_base_dir: Optional[Path] = None,
) -> Any:
    """Build the synthesis agent using langgraph.prebuilt.create_react_agent.

    Args:
        model: LangChain chat model (default: built from settings).
        storage_backend: StorageBackend instance for reading KB artifacts.
        storage_prefix: Key prefix (e.g. ``knowledge_base/{slug}/``).
        checkpointer: Optional LangGraph checkpointer.
        kb_base_dir: **Deprecated** — kept for backward compat with tests.

    Returns:
        CompiledStateGraph ready for .ainvoke().
    """
    if model is None:
        model = build_chat_openai_via_openrouter(settings.research_kb_synthesis_model)

    if storage_backend is None:
        from core.storage import get_storage_backend
        storage_backend = get_storage_backend(kb_base_dir or Path("artifacts"))

    read_file = make_read_file_tool(storage_backend, storage_prefix)
    return create_react_agent(
        model,
        [read_file],
        prompt=get_synthesis_system_prompt(),
        checkpointer=checkpointer,
    )


async def run_synthesis_agent(
    input_data: KnowledgeBaseInput,
    kb_base_dir: Optional[Path] = None,
    available_docs: Optional[Dict[str, str]] = None,
    missing_docs: Optional[List[str]] = None,
    parent_span: Optional[Any] = None,
    timeout_s: float = 600.0,
    revision_note: Optional[str] = None,
    delta_mode: bool = False,
    changed_docs: Optional[Dict[str, str]] = None,
    previous_synthesis_path: Optional[str] = None,
    *,
    storage_backend: Optional[StorageBackend] = None,
    storage_prefix: str = "knowledge_base/",
) -> KBAgentResult:
    """Run L2 → L3 synthesis — requires minimum 3 of 5 L2 docs.

    Args:
        input_data: Pipeline input with company details.
        kb_base_dir: **Deprecated** — kept for backward compat.
        available_docs: Dict mapping doc_type.value to file path.
        missing_docs: List of doc_type.value strings that are missing.
        parent_span: Optional parent tracing span.
        timeout_s: Per-call timeout in seconds.
        revision_note: Optional reviewer feedback from a previous version.
        delta_mode: If True, use incremental synthesis (only read changed docs).
        changed_docs: Dict mapping doc_type.value to file path for changed docs
            (required when delta_mode=True).
        previous_synthesis_path: Relative path to previous synthesis file
            (required when delta_mode=True).
        storage_backend: StorageBackend instance for reading KB artifacts.
        storage_prefix: Key prefix (e.g. ``knowledge_base/{slug}/``).

    Returns:
        KBAgentResult with synthesized company profile or error.
    """
    available_docs = available_docs or {}
    missing_docs = missing_docs or []
    # Partial failure policy (CX-14): minimum 3/5 L2 docs
    if len(available_docs) < 3:
        return KBAgentResult(
            doc_type=KBDocType.SYNTHESIS,
            error=(
                f"Synthesis requires minimum 3/5 L2 docs, "
                f"but only {len(available_docs)} available: "
                f"{list(available_docs.keys())}. "
                f"Missing: {missing_docs}"
            ),
        )

    # Delta mode validation
    if delta_mode and not previous_synthesis_path:
        return KBAgentResult(
            doc_type=KBDocType.SYNTHESIS,
            error="Delta mode requires previous_synthesis_path",
        )

    span = create_span(
        parent_span,
        "agent/synthesis",
        input_data={
            "company": input_data.company_name,
            "available": list(available_docs.keys()),
            "missing": missing_docs,
            "delta_mode": delta_mode,
        },
    )
    start = time.time()
    try:
        # Build agent with appropriate system prompt
        system_prompt = (
            get_delta_synthesis_system_prompt() if delta_mode
            else get_synthesis_system_prompt()
        )
        resolved = None
        if input_data.workspace_id:
            resolved = await resolve_model_config_for_agent(
                workspace_id=input_data.workspace_id,
                workspace_slug=input_data.workspace_slug or input_data.company_slug or "",
                agent_key="research.kb.synthesis",
            )
        if resolved is not None:
            model_kwargs: Dict[str, Any] = {}
            if resolved.temperature is not None:
                model_kwargs["temperature"] = resolved.temperature
            if resolved.max_tokens is not None:
                model_kwargs["max_tokens"] = resolved.max_tokens
            model = build_chat_openai_for_key(
                resolved.api_key,
                resolved.model,
                base_url=resolved.base_url,
                **model_kwargs,
            )
            synthesis_model = resolved.model
        else:
            model = build_chat_openai_via_openrouter(settings.research_kb_synthesis_model)
            synthesis_model = settings.research_kb_synthesis_model

        # Resolve storage backend — prefer explicit, fall back for compat
        if storage_backend is None:
            from core.storage import get_storage_backend
            storage_backend = get_storage_backend(kb_base_dir or Path("artifacts"))

        read_file = make_read_file_tool(storage_backend, storage_prefix)
        agent = create_react_agent(model, [read_file], prompt=system_prompt)

        # Build user prompt based on mode
        if delta_mode:
            unchanged_docs = {
                k: v for k, v in available_docs.items()
                if k not in (changed_docs or {})
            }
            user_prompt = build_delta_synthesis_user_prompt(
                input_data,
                previous_synthesis_path=previous_synthesis_path or "",
                changed_docs=changed_docs or {},
                unchanged_docs=unchanged_docs,
                missing_docs=missing_docs,
                revision_note=revision_note,
            )
        else:
            user_prompt = build_synthesis_user_prompt(
                input_data, available_docs, missing_docs,
                revision_note=revision_note,
            )

        # Propagate tracing into the react agent so internal LLM calls
        # appear as children of this span in LangSmith.  We use
        # LangChainTracer (a proper BaseCallbackHandler) rather than
        # passing the RunTree directly — RunTree lacks the `run_inline`
        # attribute that langchain-core's callback manager requires.
        _synth_meta = {
            "pipeline": "knowledge_base",
            "pipeline_step": "synthesis",
            "provider": extract_provider(synthesis_model),
            "model": synthesis_model,
            "company_slug": input_data.company_slug or "",
        }
        invoke_config: Dict[str, Any] = {"metadata": _synth_meta}
        if span is not None:
            try:
                import os

                from langchain_core.tracers.langchain import LangChainTracer

                tracer = LangChainTracer(
                    project_name=os.environ.get(
                        "LANGCHAIN_PROJECT",
                        os.environ.get("LANGSMITH_PROJECT"),
                    ),
                    parent_run_id=str(span.id),
                )
                invoke_config["callbacks"] = [tracer]
            except Exception:
                # Tracing is best-effort; never block synthesis.
                pass

        result = await asyncio.wait_for(
            agent.ainvoke({"messages": [("user", user_prompt)]}, invoke_config),
            timeout=timeout_s,
        )

        output_md = _extract_synthesis_output(result.get("messages", []))
        if not output_md.strip():
            end_span(span, error="Synthesis produced empty output")
            return KBAgentResult(
                doc_type=KBDocType.SYNTHESIS,
                error="Synthesis produced empty output",
                execution_time_s=time.time() - start,
            )

        from core.shared_tools.cost_tracker import track_llm_cost

        # Extract real token counts from the last AI message (OpenRouter via ChatOpenAI).
        # In multi-step ReAct, this captures only the final call; OpenRouter dashboard
        # tracks all calls server-side for accurate total cost.
        _pt, _ct, _method = 0, 0, "char_count"
        for msg in reversed(result.get("messages", [])):
            if getattr(msg, "type", None) == "ai":
                _meta = getattr(msg, "response_metadata", {})
                _usage = _meta.get("token_usage", {}) if isinstance(_meta, dict) else {}
                if isinstance(_usage, dict):
                    _pt = _usage.get("prompt_tokens", 0) or 0
                    _ct = _usage.get("completion_tokens", 0) or 0
                if _pt or _ct:
                    _method = "sdk"
                break
        if not (_pt or _ct):
            _pt = len(user_prompt) // 4
            _ct = len(output_md) // 4

        track_llm_cost(
            model=synthesis_model,
            provider=extract_provider(synthesis_model),
            pipeline="knowledge_base", pipeline_step="synthesis",
            prompt_tokens=_pt, completion_tokens=_ct,
            company_slug=input_data.company_slug or "",
            call_site="core.research.knowledge_base.agents",
            source="openrouter",
            workspace_id=input_data.workspace_id if resolved is not None else None,
            agent_key="research.kb.synthesis" if resolved is not None else "",
            credential_id=getattr(resolved, "credential_id", None),
            model_config_id=getattr(resolved, "model_config_id", None),
            actual_provider=actual_provider(synthesis_model) if resolved is not None else "",
            workspace_billed=resolved is not None,
            extra={"estimation_method": _method},
        )

        log_generation(
            span,
            "synthesis",
            synthesis_model,
            user_prompt[:2000],
            output_md[:2000],
            metadata=_synth_meta,
        )
        end_span(span, output={"word_count": len(output_md.split())})
        return KBAgentResult(
            doc_type=KBDocType.SYNTHESIS,
            content_md=output_md,
            word_count=len(output_md.split()),
            execution_time_s=time.time() - start,
        )
    except asyncio.TimeoutError:
        end_span(span, error=f"Timeout after {timeout_s}s")
        return KBAgentResult(
            doc_type=KBDocType.SYNTHESIS,
            error=f"Timeout after {timeout_s}s",
            execution_time_s=time.time() - start,
        )
    except Exception as exc:
        logger.error("Synthesis agent error: %s", exc, exc_info=True)
        end_span(span, error=str(exc))
        return KBAgentResult(
            doc_type=KBDocType.SYNTHESIS,
            error=str(exc),
            execution_time_s=time.time() - start,
        )
