"""Knowledge Base specialist agents — 4 Perplexity + 1 Brand Perception + 1 Synthesis.

Tier 1 (Agents 1-4): Perplexity sonar-deep-research via asyncio.to_thread + wait_for.
Tier 2 (Agent 5): Anthropic AsyncAnthropic + web_search_20250305 server-side tool.
Tier 3 (Synthesis): LangGraph create_react_agent + Claude Opus with read_file tool.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from core.config.settings import settings
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
    build_synthesis_user_prompt,
    get_synthesis_system_prompt,
)
from core.research.prompts.weakness_analyst import (
    build_weakness_analyst_user_prompt,
    get_weakness_analyst_system_prompt,
)
from core.research.tools import perplexity_client
from core.shared_tools.tracing import create_span, end_span, log_generation

logger = logging.getLogger(__name__)

# Maximum pause_turn continuation iterations for Brand Perception agent.
# Anthropic's server-side web_search tool can trigger pause_turn when the
# model hits its internal iteration limit. We cap retries to prevent
# unbounded loops and runaway token/cost consumption.
_MAX_PAUSE_TURNS = 5


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_model(model_string: str, **kwargs: Any) -> Any:
    """Build a LangChain chat model from a provider:model string.

    Handles three formats:
    - ``"anthropic:claude-opus-4-6"`` (colon separator)
    - ``"anthropic/claude-opus-4-6"`` (slash separator)
    - ``"gpt-4o"`` (bare model name — provider inferred)
    """
    if ":" in model_string:
        provider, model_name = model_string.split(":", 1)
        return init_chat_model(model_name, model_provider=provider, **kwargs)
    if "/" in model_string:
        provider, model_name = model_string.split("/", 1)
        return init_chat_model(model_name, model_provider=provider, **kwargs)
    return init_chat_model(model_string, **kwargs)


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
) -> KBAgentResult:
    """Shared runner for Perplexity-based agents."""
    span = create_span(
        parent_span,
        f"agent/{span_name}",
        input_data={"doc_type": doc_type.value},
    )
    start = time.time()
    try:
        result_md = await asyncio.wait_for(
            asyncio.to_thread(
                perplexity_client.research, query=full_prompt, timeout_s=timeout_s,
            ),
            timeout=timeout_s,
        )
        log_generation(
            span,
            span_name,
            settings.perplexity_deep_research_model,
            full_prompt[:2000],
            result_md[:2000] if result_md else "",
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

        is_partial = pause_turns >= _MAX_PAUSE_TURNS

        result_md = _extract_text_with_citations(response)
        log_generation(
            span,
            "brand-perception",
            settings.research_kb_brand_perception_model,
            user_prompt[:2000],
            result_md[:2000],
        )
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
    kb_base_dir: Optional[Path] = None,
    checkpointer: Optional[Any] = None,
) -> Any:
    """Build the synthesis agent using langgraph.prebuilt.create_react_agent.

    Args:
        model: LangChain chat model (default: built from settings).
        kb_base_dir: Root directory for the read_file tool.
        checkpointer: Optional LangGraph checkpointer.

    Returns:
        CompiledStateGraph ready for .ainvoke().
    """
    if model is None:
        model = _build_model(settings.research_kb_synthesis_model)
    read_file = make_read_file_tool(kb_base_dir or Path("artifacts/knowledge_base"))
    return create_react_agent(
        model,
        [read_file],
        prompt=get_synthesis_system_prompt(),
        checkpointer=checkpointer,
    )


async def run_synthesis_agent(
    input_data: KnowledgeBaseInput,
    kb_base_dir: Path,
    available_docs: Dict[str, str],
    missing_docs: List[str],
    parent_span: Optional[Any] = None,
    timeout_s: float = 600.0,
    revision_note: Optional[str] = None,
) -> KBAgentResult:
    """Run L2 → L3 synthesis — requires minimum 3 of 5 L2 docs.

    Args:
        input_data: Pipeline input with company details.
        kb_base_dir: Root directory for the read_file tool.
        available_docs: Dict mapping doc_type.value to file path.
        missing_docs: List of doc_type.value strings that are missing.
        parent_span: Optional parent tracing span.
        timeout_s: Per-call timeout in seconds.

    Returns:
        KBAgentResult with synthesized company profile or error.
    """
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

    span = create_span(
        parent_span,
        "agent/synthesis",
        input_data={
            "company": input_data.company_name,
            "available": list(available_docs.keys()),
            "missing": missing_docs,
        },
    )
    start = time.time()
    try:
        agent = build_synthesis_agent(kb_base_dir=kb_base_dir)
        user_prompt = build_synthesis_user_prompt(
            input_data, available_docs, missing_docs, revision_note=revision_note,
        )

        result = await asyncio.wait_for(
            agent.ainvoke({"messages": [("user", user_prompt)]}),
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

        log_generation(
            span,
            "synthesis",
            settings.research_kb_synthesis_model,
            user_prompt[:2000],
            output_md[:2000],
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
        end_span(span, error=str(exc))
        return KBAgentResult(
            doc_type=KBDocType.SYNTHESIS,
            error=str(exc),
            execution_time_s=time.time() - start,
        )
