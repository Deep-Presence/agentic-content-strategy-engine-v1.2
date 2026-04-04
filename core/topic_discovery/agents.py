"""Topic Discovery agents — S1 source generators, S2 merge, S3 expansion.

All agent functions are async, use OpenRouter (via openai SDK) for LLM calls,
and return result objects (errors are captured, never fatal).

Statistical functions (capture-recapture, Chao1, sample coverage) are
pure Python — no LLM calls.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.config.settings import settings
from core.shared_tools.tracing import (
    create_span,
    end_span,
    extract_provider,
    log_generation,
    log_score,
)
from core.models.topic_discovery import (
    BuyerStage,
    CaptureRecaptureResult,
    IntentType,
    PerSourceCoverage,
    RelevanceCell,
    SourceResult,
    SubdomainCandidate,
    SubdomainNode,
    TaxonomyTree,
    TDSource,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicDiscoveryStatus,
)
from core.topic_discovery.prompts.source_a_company import (
    build_source_a_user_prompt,
    get_source_a_system_prompt,
)
from core.topic_discovery.prompts.source_b_persona import (
    build_source_b_user_prompt,
    get_source_b_system_prompt,
)
from core.topic_discovery.prompts.source_c_deep_research import (
    build_source_c_user_prompt,
    get_source_c_system_prompt,
)
from core.topic_discovery.prompts.source_d_adversarial import (
    build_source_d_user_prompt,
    get_source_d_system_prompt,
)
from core.topic_discovery.prompts.hierarchy_construction import (
    build_hierarchy_user_prompt,
    get_hierarchy_system_prompt,
)
from core.topic_discovery.prompts.relevance_filtering import (
    build_relevance_user_prompt,
    get_relevance_system_prompt,
)
from core.topic_discovery.prompts.topic_generation import (
    build_topic_generation_user_prompt,
    get_topic_generation_system_prompt,
)

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


_EMBEDDING_BATCH_SIZE = 64


@dataclass
class DeduplicationResult:
    """Result of deduplication with cluster metadata for coverage computation."""

    kept: List[SubdomainCandidate] = field(default_factory=list)
    clusters: List[List[int]] = field(default_factory=list)
    embeddings: List[List[float]] = field(default_factory=list)
    source_of: List[TDSource] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences wrapping JSON output.

    Three-tier extraction strategy:
    1. Anchored regex (exact fence wrapping entire string)
    2. Non-anchored regex (fence anywhere with preamble/suffix text)
    3. Bracket extraction (first {/[ to last }/])
    """
    stripped = text.strip()
    # Tier 1: exact fence match (original behavior)
    m = _CODE_FENCE_RE.match(stripped)
    if m:
        return m.group(1).strip()
    # Tier 2: fence anywhere in the string
    m2 = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
    if m2:
        return m2.group(1).strip()
    # Tier 3: extract bare JSON between first {/[ and last }/]
    obj_start = stripped.find("{")
    arr_start = stripped.find("[")
    if obj_start >= 0 and (arr_start < 0 or obj_start <= arr_start):
        obj_end = stripped.rfind("}")
        if obj_end > obj_start:
            return stripped[obj_start : obj_end + 1]
    if arr_start >= 0:
        arr_end = stripped.rfind("]")
        if arr_end > arr_start:
            return stripped[arr_start : arr_end + 1]
    return stripped


def _extract_text_content(content: Any) -> str:
    """Normalize LiteLLM message.content into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content)


async def _run_completion(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 16384,
    timeout_s: float = 120.0,
    response_format: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, str]:
    """Run OpenRouter completion via the async OpenAI client.

    Returns (response, raw_text) tuple. Signature unchanged from LiteLLM era.
    """
    from core.shared_tools.openrouter_client import get_async_client

    client = get_async_client()

    # Build kwargs — only include response_format when explicitly set
    completion_kwargs: Dict[str, Any] = {
        "model": model,
        "messages": list(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        completion_kwargs["response_format"] = response_format
    if metadata is not None:
        completion_kwargs["extra_body"] = {"metadata": metadata}

    response = await asyncio.wait_for(
        client.chat.completions.create(**completion_kwargs),
        timeout=timeout_s,
    )

    # Cost tracking (never raises)
    from core.shared_tools.cost_tracker import track_llm_cost

    _meta = metadata or {}
    _usage = getattr(response, "usage", None)
    track_llm_cost(
        model=model,
        provider="openrouter",
        pipeline=_meta.get("pipeline", ""),
        pipeline_step=_meta.get("pipeline_step", ""),
        prompt_tokens=getattr(_usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(_usage, "completion_tokens", 0) or 0,
        company_slug=_meta.get("company_slug", ""),
        call_site="core.topic_discovery.agents",
        source="openrouter",
    )

    choice = response.choices[0]
    raw_text = _extract_text_content(choice.message.content)
    return response, raw_text


def _repair_truncated_json(text: str) -> Optional[str]:
    """Attempt to repair JSON truncated by max_tokens.

    Closes any open brackets/braces and strips trailing partial values.
    Returns repaired string, or None if unrecoverable.
    """
    # Strip trailing incomplete key-value (partial string after last comma)
    text = text.rstrip()
    # Remove trailing comma if present
    if text.endswith(","):
        text = text[:-1]
    # Remove incomplete string value (unclosed quote after colon)
    while text and text[-1] not in "{}[]\"0123456789truefalsn":
        text = text[:-1]
    if not text:
        return None

    # Count open/close brackets and braces
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()

    # Close remaining open brackets/braces
    closers = {"[": "]", "{": "}"}
    for opener in reversed(stack):
        text += closers.get(opener, "")

    return text


def _parse_json_response(raw_text: str) -> Any:
    """Parse JSON from LLM response, stripping code fences.

    Attempts repair on truncated JSON before giving up.
    Returns None on parse failure (logged, never fatal).
    """
    cleaned = _strip_code_fences(raw_text)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try repairing truncated JSON
    repaired = _repair_truncated_json(cleaned)
    if repaired:
        try:
            result = json.loads(repaired)
            logger.info("TD: repaired truncated JSON response successfully")
            return result
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("TD: failed to parse LLM JSON response: %.200s", cleaned)
    return None


def _safe_float(value: Any, default: float = 0.5) -> float:
    """Coerce a value to float, returning default on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_usage(response: Any) -> Dict[str, int]:
    """Extract token usage from a LiteLLM response safely."""
    if response and hasattr(response, "usage") and response.usage:
        return {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
        }
    return {}


# ---------------------------------------------------------------------------
# S1: Multi-Source Subdomain Generation
# ---------------------------------------------------------------------------


async def run_source_a_company_brainstorm(
    company_context: str,
    *,
    max_rounds: int = 4,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
    revision_note: Optional[str] = None,
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> SourceResult:
    """Source A: Company-perspective subdomain brainstorm (iterative expansion)."""
    model = model or settings.topic_discovery_brainstorm_model
    t0 = time.monotonic()
    all_candidates: List[SubdomainCandidate] = []
    previous_names: List[str] = []
    rounds_executed = 0
    span = create_span(parent_span, "td-source-a", input_data={"max_rounds": max_rounds})

    try:
        for round_num in range(1, max_rounds + 1):
            rounds_executed += 1
            messages = [
                {"role": "system", "content": get_source_a_system_prompt()},
                {
                    "role": "user",
                    "content": build_source_a_user_prompt(
                        company_context,
                        round_number=round_num,
                        previous_subdomains=previous_names if round_num > 1 else None,
                        revision_note=revision_note,
                    ),
                },
            ]
            _meta_a = {
                "pipeline": "topic_discovery",
                "pipeline_step": "source_a",
                "provider": extract_provider(model),
                "model": model,
                "company_slug": company_slug,
            }
            response, raw_text = await _run_completion(
                model=model, messages=messages, timeout_s=timeout_s,
                metadata=_meta_a,
            )
            log_generation(
                span, f"round-{round_num}", model,
                messages[-1]["content"][:2000], raw_text[:2000],
                metadata=_meta_a,
                usage=_extract_usage(response),
            )
            parsed = _parse_json_response(raw_text)
            if parsed is None:
                break
            subdomains = parsed.get("subdomains", [])
            if not isinstance(subdomains, list):
                subdomains = []

            for sd in subdomains:
                if isinstance(sd, dict):
                    c = SubdomainCandidate(
                        name=sd.get("name", ""),
                        description=sd.get("description", ""),
                        source=TDSource.source_a,
                        round_number=round_num,
                        confidence=_safe_float(sd.get("confidence", 0.5)),
                    )
                    all_candidates.append(c)
                    previous_names.append(c.name)

            if not subdomains:
                break

        singletons, doubletons = _count_frequency_classes_by_round(all_candidates)
        unique_names = {c.name.lower().strip() for c in all_candidates if c.name}
        observed = len(unique_names)
        total_obs = _count_total_round_observations(all_candidates)
        chao1 = compute_chao1_lower_bound(observed, singletons, doubletons)
        sc = compute_sample_coverage(singletons, total_obs)
        log_score(span, "chao1_estimate", chao1)
        log_score(span, "sample_coverage", sc)
        log_score(span, "candidate_count", float(len(all_candidates)))
        end_span(span, output={"candidates": len(all_candidates), "rounds": rounds_executed})
        return SourceResult(
            source=TDSource.source_a,
            candidates=all_candidates,
            total_rounds=rounds_executed,
            singletons=singletons,
            doubletons=doubletons,
            chao1_estimate=chao1,
            source_sample_coverage=sc,
            execution_time_s=time.monotonic() - t0,
        )
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        return SourceResult(
            source=TDSource.source_a,
            candidates=all_candidates,
            total_rounds=rounds_executed,
            execution_time_s=time.monotonic() - t0,
            error=str(exc),
        )


def _resolve_persona_ids(
    raw_names: List[str],
    name_to_id: Dict[str, str],
) -> List[str]:
    """Fuzzy-match persona names from LLM output to known persona_ids.

    Tries exact match first, then case-insensitive, then substring.
    """
    resolved: List[str] = []
    if not name_to_id:
        return resolved
    # Build lower-case lookup
    lower_map = {k.lower().strip(): v for k, v in name_to_id.items()}
    for raw in raw_names:
        if not isinstance(raw, str) or not raw.strip():
            continue
        raw_lower = raw.lower().strip()
        # Exact match
        if raw in name_to_id:
            resolved.append(name_to_id[raw])
        # Case-insensitive match
        elif raw_lower in lower_map:
            resolved.append(lower_map[raw_lower])
        else:
            # Substring match (e.g. "David" matches "David the Founder")
            for key_lower, pid in lower_map.items():
                if raw_lower in key_lower or key_lower in raw_lower:
                    resolved.append(pid)
                    break
    return list(dict.fromkeys(resolved))  # deduplicate preserving order


async def run_source_b_persona_brainstorm(
    persona_profiles: str,
    company_context: str,
    *,
    max_rounds: int = 4,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
    revision_note: Optional[str] = None,
    persona_name_to_id: Optional[Dict[str, str]] = None,
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> SourceResult:
    """Source B: Audience-perspective subdomain brainstorm (iterative expansion)."""
    model = model or settings.topic_discovery_brainstorm_model
    t0 = time.monotonic()
    all_candidates: List[SubdomainCandidate] = []
    previous_names: List[str] = []
    rounds_executed = 0
    span = create_span(parent_span, "td-source-b", input_data={"max_rounds": max_rounds})

    try:
        for round_num in range(1, max_rounds + 1):
            rounds_executed += 1
            messages = [
                {"role": "system", "content": get_source_b_system_prompt()},
                {
                    "role": "user",
                    "content": build_source_b_user_prompt(
                        persona_profiles,
                        company_context,
                        round_number=round_num,
                        previous_subdomains=previous_names if round_num > 1 else None,
                        revision_note=revision_note,
                    ),
                },
            ]
            _meta_b = {
                "pipeline": "topic_discovery",
                "pipeline_step": "source_b",
                "provider": extract_provider(model),
                "model": model,
                "company_slug": company_slug,
            }
            response, raw_text = await _run_completion(
                model=model, messages=messages, timeout_s=timeout_s,
                metadata=_meta_b,
            )
            log_generation(
                span, f"round-{round_num}", model,
                messages[-1]["content"][:2000], raw_text[:2000],
                metadata=_meta_b,
                usage=_extract_usage(response),
            )
            parsed = _parse_json_response(raw_text)
            if parsed is None:
                break
            subdomains = parsed.get("subdomains", [])
            if not isinstance(subdomains, list):
                subdomains = []

            for sd in subdomains:
                if isinstance(sd, dict):
                    # Resolve persona names from LLM output to persona_ids
                    raw_personas = sd.get("source_personas", [])
                    if not isinstance(raw_personas, list):
                        raw_personas = []
                    resolved_ids = _resolve_persona_ids(
                        raw_personas, persona_name_to_id or {},
                    )
                    raw_pains = sd.get("pain_points_addressed", [])
                    if not isinstance(raw_pains, list):
                        raw_pains = []
                    c = SubdomainCandidate(
                        name=sd.get("name", ""),
                        description=sd.get("description", ""),
                        source=TDSource.source_b,
                        round_number=round_num,
                        confidence=_safe_float(sd.get("confidence", 0.5)),
                        persona_ids=resolved_ids,
                        pain_points=[str(p) for p in raw_pains if p],
                    )
                    all_candidates.append(c)
                    previous_names.append(c.name)

            if not subdomains:
                break

        singletons, doubletons = _count_frequency_classes_by_round(all_candidates)
        unique_names = {c.name.lower().strip() for c in all_candidates if c.name}
        observed = len(unique_names)
        total_obs = _count_total_round_observations(all_candidates)
        chao1 = compute_chao1_lower_bound(observed, singletons, doubletons)
        sc = compute_sample_coverage(singletons, total_obs)
        log_score(span, "chao1_estimate", chao1)
        log_score(span, "sample_coverage", sc)
        log_score(span, "candidate_count", float(len(all_candidates)))
        end_span(span, output={"candidates": len(all_candidates), "rounds": rounds_executed})
        return SourceResult(
            source=TDSource.source_b,
            candidates=all_candidates,
            total_rounds=rounds_executed,
            singletons=singletons,
            doubletons=doubletons,
            chao1_estimate=chao1,
            source_sample_coverage=sc,
            execution_time_s=time.monotonic() - t0,
        )
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        return SourceResult(
            source=TDSource.source_b,
            candidates=all_candidates,
            total_rounds=rounds_executed,
            execution_time_s=time.monotonic() - t0,
            error=str(exc),
        )


async def run_source_c_deep_research(
    company_context: str,
    competitor_landscape: str,
    domain: str,
    *,
    model: Optional[str] = None,
    timeout_s: float = 900.0,
    revision_note: Optional[str] = None,
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> SourceResult:
    """Source C: Deep research competitive content landscape via Perplexity."""
    from core.research.tools import perplexity_client

    # Guard: skip API call if no context available at all
    if not (company_context or "").strip() and not (competitor_landscape or "").strip():
        logger.info("TD Source C: no company context or competitor data, skipping")
        return SourceResult(
            source=TDSource.source_c,
            candidates=[],
            total_rounds=0,
            execution_time_s=0.0,
        )

    model = model or settings.topic_discovery_source_c_model
    t0 = time.monotonic()
    span = create_span(parent_span, "td-source-c", input_data={"domain": domain, "model": model})

    try:
        system_prompt = get_source_c_system_prompt()
        user_prompt = build_source_c_user_prompt(
            company_context, competitor_landscape, domain,
            revision_note=revision_note,
        )
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        raw_text, _pplx_usage = await asyncio.wait_for(
            asyncio.to_thread(
                perplexity_client.research,
                query=full_prompt,
                timeout_s=timeout_s,
                model=model,
            ),
            timeout=timeout_s,
        )
        # Manual log_generation — Perplexity bypasses LiteLLM callbacks
        _meta_c = {
            "pipeline": "topic_discovery",
            "pipeline_step": "source_c",
            "provider": "perplexity",
            "model": model,
            "company_slug": company_slug,
        }
        log_generation(span, "deep-research", model, full_prompt[:2000], raw_text[:2000],
                       metadata=_meta_c, usage=_pplx_usage)

        # Strip Perplexity citations section before JSON parsing
        if "\n\nSources:\n" in raw_text:
            raw_text = raw_text[: raw_text.index("\n\nSources:\n")]

        parsed = _parse_json_response(raw_text)
        if parsed is None:
            log_score(span, "candidate_count", 0.0)
            end_span(span, output={"candidates": 0})
            return SourceResult(
                source=TDSource.source_c,
                candidates=[],
                total_rounds=1,
                execution_time_s=time.monotonic() - t0,
            )
        subdomains = parsed.get("subdomains", [])
        if not isinstance(subdomains, list):
            subdomains = []

        candidates = []
        for sd in subdomains:
            if isinstance(sd, dict):
                candidates.append(
                    SubdomainCandidate(
                        name=sd.get("name", ""),
                        description=sd.get("description", ""),
                        source=TDSource.source_c,
                        round_number=1,
                        confidence=_safe_float(sd.get("confidence", 0.5)),
                    )
                )

        singletons, doubletons = _count_frequency_classes_by_round(candidates)
        unique_names = {c.name.lower().strip() for c in candidates if c.name}
        observed = len(unique_names)
        total_obs = _count_total_round_observations(candidates)
        chao1 = compute_chao1_lower_bound(observed, singletons, doubletons)
        sc = compute_sample_coverage(singletons, total_obs)
        log_score(span, "candidate_count", float(len(candidates)))
        end_span(span, output={"candidates": len(candidates)})
        return SourceResult(
            source=TDSource.source_c,
            candidates=candidates,
            total_rounds=1,
            singletons=singletons,
            doubletons=doubletons,
            chao1_estimate=chao1,
            source_sample_coverage=sc,
            execution_time_s=time.monotonic() - t0,
        )
    except asyncio.TimeoutError:
        end_span(span, error=f"Timeout after {timeout_s}s")
        return SourceResult(
            source=TDSource.source_c,
            total_rounds=1,
            execution_time_s=time.monotonic() - t0,
            error=f"Timeout after {timeout_s}s",
        )
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        return SourceResult(
            source=TDSource.source_c,
            total_rounds=1,
            execution_time_s=time.monotonic() - t0,
            error=str(exc),
        )


async def run_source_d_adversarial(
    company_context: str,
    existing_subdomains: List[str],
    *,
    specialist_lenses: Optional[List[str]] = None,
    max_rounds: int = 4,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
    revision_note: Optional[str] = None,
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> SourceResult:
    """Source D: Adversarial diversity pass using specialist lenses."""
    model = model or settings.topic_discovery_brainstorm_model
    t0 = time.monotonic()
    all_candidates: List[SubdomainCandidate] = []
    previous_names = list(existing_subdomains)
    rounds_executed = 0

    if specialist_lenses is None:
        specialist_lenses = [
            "regulatory compliance expert",
            "enterprise procurement specialist",
            "accessibility advocate",
            "customer success advocate",
            "security & risk analyst",
        ]

    span = create_span(parent_span, "td-source-d", input_data={
        "lenses": len(specialist_lenses), "max_rounds": max_rounds,
    })

    try:
        for round_num, lens in enumerate(specialist_lenses, 1):
            if round_num > max_rounds:
                break
            rounds_executed += 1
            messages = [
                {"role": "system", "content": get_source_d_system_prompt()},
                {
                    "role": "user",
                    "content": build_source_d_user_prompt(
                        company_context,
                        lens,
                        round_number=round_num,
                        previous_subdomains=previous_names,
                        revision_note=revision_note,
                    ),
                },
            ]
            _meta_d = {
                "pipeline": "topic_discovery",
                "pipeline_step": "source_d",
                "provider": extract_provider(model),
                "model": model,
                "company_slug": company_slug,
            }
            response, raw_text = await _run_completion(
                model=model, messages=messages, timeout_s=timeout_s,
                metadata=_meta_d,
            )
            log_generation(
                span, f"lens-{round_num}-{lens[:20]}", model,
                messages[-1]["content"][:2000], raw_text[:2000],
                metadata=_meta_d,
                usage=_extract_usage(response),
            )
            parsed = _parse_json_response(raw_text)
            if parsed is None:
                continue
            subdomains = parsed.get("subdomains", [])
            if not isinstance(subdomains, list):
                subdomains = []

            for sd in subdomains:
                if isinstance(sd, dict):
                    c = SubdomainCandidate(
                        name=sd.get("name", ""),
                        description=sd.get("description", ""),
                        source=TDSource.source_d,
                        round_number=round_num,
                        specialist_lens=lens,
                        confidence=_safe_float(sd.get("confidence", 0.5)),
                    )
                    all_candidates.append(c)
                    previous_names.append(c.name)

        singletons, doubletons = _count_frequency_classes_by_round(all_candidates)
        unique_names = {c.name.lower().strip() for c in all_candidates if c.name}
        observed = len(unique_names)
        total_obs = _count_total_round_observations(all_candidates)
        chao1 = compute_chao1_lower_bound(observed, singletons, doubletons)
        sc = compute_sample_coverage(singletons, total_obs)
        log_score(span, "chao1_estimate", chao1)
        log_score(span, "sample_coverage", sc)
        log_score(span, "candidate_count", float(len(all_candidates)))
        end_span(span, output={"candidates": len(all_candidates), "rounds": rounds_executed})
        return SourceResult(
            source=TDSource.source_d,
            candidates=all_candidates,
            total_rounds=rounds_executed,
            singletons=singletons,
            doubletons=doubletons,
            chao1_estimate=chao1,
            source_sample_coverage=sc,
            execution_time_s=time.monotonic() - t0,
        )
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        return SourceResult(
            source=TDSource.source_d,
            candidates=all_candidates,
            total_rounds=rounds_executed,
            execution_time_s=time.monotonic() - t0,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# S2: Deduplication + Hierarchy
# ---------------------------------------------------------------------------


async def deduplicate_subdomains_with_clusters(
    candidates: List[SubdomainCandidate],
    *,
    threshold: float = 0.85,
    parent_span: Optional[Any] = None,
) -> DeduplicationResult:
    """Deduplicate subdomains via embedding cosine similarity.

    Returns a ``DeduplicationResult`` with cluster metadata, embeddings,
    and source provenance so coverage metrics can reuse the embedding work.
    """
    if not candidates:
        return DeduplicationResult()

    span = create_span(parent_span, "td-s2-dedup", input_data={"candidate_count": len(candidates)})

    from core.shared_tools.embedding_client import embed_texts

    names = [c.name for c in candidates]

    # Batch embeddings
    all_embeddings: List[List[float]] = []
    for i in range(0, len(names), _EMBEDDING_BATCH_SIZE):
        batch = names[i : i + _EMBEDDING_BATCH_SIZE]
        batch_embeddings = await asyncio.to_thread(embed_texts, batch)
        all_embeddings.extend(batch_embeddings)

    source_of = [c.source for c in candidates]

    # Compute pairwise cosine similarity, mark duplicates, and track clusters
    n = len(candidates)
    is_duplicate = [False] * n
    # Map each kept candidate to the list of original indices it absorbed
    cluster_map: Dict[int, List[int]] = {i: [i] for i in range(n)}

    for i in range(n):
        if is_duplicate[i]:
            continue
        for j in range(i + 1, n):
            if is_duplicate[j]:
                continue
            sim = _cosine_similarity(all_embeddings[i], all_embeddings[j])
            if sim >= threshold:
                is_duplicate[j] = True
                cluster_map[i].append(j)

    kept = [c for c, dup in zip(candidates, is_duplicate) if not dup]
    clusters = [cluster_map[i] for i in range(n) if not is_duplicate[i]]

    # Merge persona_ids and pain_points from absorbed candidates into kept
    for kept_idx, cluster_indices in enumerate(clusters):
        merged_pids: set[str] = set(kept[kept_idx].persona_ids)
        merged_pains: list[str] = list(kept[kept_idx].pain_points)
        for member_idx in cluster_indices:
            if member_idx == cluster_indices[0]:
                continue  # skip self (the kept candidate is always first)
            merged_pids.update(candidates[member_idx].persona_ids)
            merged_pains.extend(candidates[member_idx].pain_points)
        kept[kept_idx].persona_ids = sorted(merged_pids)
        # Deduplicate pain_points preserving order
        kept[kept_idx].pain_points = list(dict.fromkeys(merged_pains))

    dedup_ratio = 1.0 - (len(kept) / len(candidates)) if candidates else 0.0
    log_score(span, "dedup_ratio", round(dedup_ratio, 4))
    log_score(span, "total_kept", float(len(kept)))
    end_span(span, output={"kept": len(kept), "dedup_ratio": round(dedup_ratio, 4)})

    return DeduplicationResult(
        kept=kept,
        clusters=clusters,
        embeddings=all_embeddings,
        source_of=source_of,
    )


async def deduplicate_subdomains(
    candidates: List[SubdomainCandidate],
    *,
    threshold: float = 0.85,
) -> List[SubdomainCandidate]:
    """Deduplicate subdomains — backward-compatible wrapper.

    Returns only the kept candidates (without cluster metadata).
    """
    result = await deduplicate_subdomains_with_clusters(candidates, threshold=threshold)
    return result.kept


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors.

    Delegates to ``core.shared_tools.math_utils.cosine_similarity``.
    Kept as a module-private alias for backward compatibility.
    """
    from core.shared_tools.math_utils import cosine_similarity

    return cosine_similarity(a, b)


async def run_hierarchy_construction(
    subdomains: List[str],
    company_domain: str,
    *,
    model: Optional[str] = None,
    timeout_s: float = 480.0,
    company_slug: str = "",
) -> TaxonomyTree:
    """Organize flat subdomains into a hierarchical taxonomy tree via LLM.

    Uses response_format=json_object to enforce valid JSON output.
    Retries once on parse failure with a repair prompt before raising.
    """
    model = model or settings.topic_discovery_brainstorm_model

    system_prompt = get_hierarchy_system_prompt()
    user_prompt = build_hierarchy_user_prompt(subdomains, company_domain)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    _meta_hier = {
        "pipeline": "topic_discovery",
        "pipeline_step": "hierarchy_construction",
        "provider": extract_provider(model),
        "model": model,
        "company_slug": company_slug,
    }

    # Attempt 1
    _, raw_text = await _run_completion(
        model=model,
        messages=messages,
        timeout_s=timeout_s,
        response_format={"type": "json_object"},
        metadata=_meta_hier,
    )
    parsed = _parse_json_response(raw_text)
    nodes = _extract_taxonomy_nodes(parsed)

    if nodes is not None:
        return _build_taxonomy_tree(nodes, company_domain)

    # Attempt 2: retry with conversation context + repair prompt
    logger.warning(
        "TD hierarchy construction: first attempt failed to parse. "
        "Retrying with repair prompt. Raw (first 300 chars): %.300s",
        raw_text,
    )
    repair_prompt = (
        "Your previous response could not be parsed as valid JSON. "
        "Please return ONLY a valid JSON object with a 'taxonomy' key "
        "containing an array of nodes. Each node must have 'name' (string), "
        "'description' (string), and optional 'children' (array of nodes). "
        "No markdown, no code fences, no preamble — just the JSON object."
    )
    retry_messages = messages + [
        {"role": "assistant", "content": raw_text},
        {"role": "user", "content": repair_prompt},
    ]
    _, retry_text = await _run_completion(
        model=model,
        messages=retry_messages,
        timeout_s=timeout_s,
        response_format={"type": "json_object"},
        metadata=_meta_hier,
    )
    retry_parsed = _parse_json_response(retry_text)
    retry_nodes = _extract_taxonomy_nodes(retry_parsed)

    if retry_nodes is not None:
        logger.info("TD hierarchy construction: retry succeeded.")
        return _build_taxonomy_tree(retry_nodes, company_domain)

    # Both attempts failed — raise
    raise RuntimeError(
        f"Hierarchy construction failed after 2 attempts. "
        f"Could not parse LLM response into a valid taxonomy. "
        f"First response (300 chars): {raw_text[:300]}. "
        f"Retry response (300 chars): {retry_text[:300]}."
    )


async def run_unified_hierarchy_and_scoring(
    subdomains: List[str],
    company_domain: str,
    company_context: str,
    persona_profiles: List[Tuple[str, str]],
    *,
    model: Optional[str] = None,
    timeout_s: float = 600.0,
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> TaxonomyTree:
    """Unified S2: build hierarchy + score subdomains + persona affinity.

    Single LLM call that combines taxonomy construction with priority scoring
    (4 dimensions) and per-persona affinity scoring.  Uses the prompt from
    ``prompts/unified_s2.py``.

    Args:
        subdomains: Flat list of deduplicated subdomain names.
        company_domain: Primary domain/industry of the company.
        company_context: Full company context markdown.
        persona_profiles: List of (persona_id, profile_markdown) tuples.
        model: LLM model override (defaults to settings).
        timeout_s: Timeout for LLM call.
        parent_span: Optional parent trace span for LangSmith.

    Returns:
        TaxonomyTree with priority_score, priority_factors, persona_affinity,
        and metadata populated on every node from LLM reasoning.
    """
    from core.topic_discovery.prompts.unified_s2 import (
        build_unified_s2_user_prompt,
        get_unified_s2_system_prompt,
    )

    model = model or settings.topic_discovery_unified_s2_model
    span = create_span(parent_span, "td-s2-unified", input_data={
        "subdomain_count": len(subdomains),
    })

    system_prompt = get_unified_s2_system_prompt()
    user_prompt = build_unified_s2_user_prompt(
        company_context=company_context,
        persona_profiles=persona_profiles,
        deduped_subdomains=subdomains,
        domain=company_domain,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    _meta_us2 = {
        "pipeline": "topic_discovery",
        "pipeline_step": "unified_s2",
        "provider": extract_provider(model),
        "model": model,
        "company_slug": company_slug,
    }

    # Attempt 1 — larger max_tokens for scoring + persona affinity output
    response, raw_text = await _run_completion(
        model=model,
        messages=messages,
        timeout_s=timeout_s,
        max_tokens=32768,
        response_format={"type": "json_object"},
        metadata=_meta_us2,
    )
    log_generation(
        span, "hierarchy-scoring", model,
        user_prompt[:2000], raw_text[:2000],
        metadata=_meta_us2,
        usage=_extract_usage(response),
    )
    parsed = _parse_json_response(raw_text)
    nodes = _extract_taxonomy_nodes(parsed)

    if nodes is not None:
        tree = _build_taxonomy_tree(nodes, company_domain)
        warnings = _validate_and_fix_composites(tree.root_nodes)
        if warnings:
            logger.info(
                "TD unified S2: fixed %d composite scores: %s",
                len(warnings), "; ".join(warnings[:5]),
            )
        log_score(span, "total_subdomains", float(tree.total_subdomains))
        log_score(span, "max_depth", float(tree.max_depth))
        end_span(span, output={"total_subdomains": tree.total_subdomains, "retried": False})
        return tree

    # Attempt 2: retry with repair prompt
    logger.warning(
        "TD unified S2: first attempt failed to parse. "
        "Retrying with repair prompt. Raw (first 300 chars): %.300s",
        raw_text,
    )
    repair_prompt = (
        "Your previous response could not be parsed as valid JSON. "
        "Please return ONLY a valid JSON object with a 'hierarchy' key "
        "containing an array of pillar objects. Each pillar must have "
        "'pillar_name', 'pillar_description', 'priority_scoring', "
        "'persona_affinity', and 'subdomains'. "
        "No markdown, no code fences, no preamble — just the JSON object."
    )
    retry_messages = messages + [
        {"role": "assistant", "content": raw_text},
        {"role": "user", "content": repair_prompt},
    ]
    retry_response, retry_text = await _run_completion(
        model=model,
        messages=retry_messages,
        timeout_s=timeout_s,
        max_tokens=32768,
        response_format={"type": "json_object"},
        metadata=_meta_us2,
    )
    log_generation(
        span, "hierarchy-scoring-retry", model,
        repair_prompt[:2000], retry_text[:2000],
        metadata=_meta_us2,
        usage=_extract_usage(retry_response),
    )
    retry_parsed = _parse_json_response(retry_text)
    retry_nodes = _extract_taxonomy_nodes(retry_parsed)

    if retry_nodes is not None:
        logger.info("TD unified S2: retry succeeded.")
        tree = _build_taxonomy_tree(retry_nodes, company_domain)
        _validate_and_fix_composites(tree.root_nodes)
        log_score(span, "total_subdomains", float(tree.total_subdomains))
        log_score(span, "max_depth", float(tree.max_depth))
        end_span(span, output={"total_subdomains": tree.total_subdomains, "retried": True})
        return tree

    end_span(span, error="Unified S2 failed after 2 attempts")
    raise RuntimeError(
        f"Unified S2 failed after 2 attempts. "
        f"Could not parse LLM response into a valid taxonomy. "
        f"First response (300 chars): {raw_text[:300]}. "
        f"Retry response (300 chars): {retry_text[:300]}."
    )


def _parse_hierarchy_nodes(
    nodes_data: List[Any], depth: int = 0
) -> List[SubdomainNode]:
    """Recursively parse hierarchy JSON into SubdomainNode list.

    Tolerates both the prompt schema (pillar_name/subdomains/sub_subdomains)
    and the legacy schema (name/children) for backward compatibility.
    """
    result = []
    if not isinstance(nodes_data, list):
        return result
    for i, nd in enumerate(nodes_data):
        if not isinstance(nd, dict):
            continue
        # Tolerate prompt keys (pillar_name/pillar_description) and legacy (name/description)
        name = nd.get("pillar_name") or nd.get("name", "")
        description = nd.get("pillar_description") or nd.get("description", "")
        # Tolerate prompt keys (subdomains/sub_subdomains) and legacy (children)
        children_data = (
            nd.get("subdomains")
            or nd.get("sub_subdomains")
            or nd.get("children", [])
        )
        children = _parse_hierarchy_nodes(children_data, depth + 1)
        # Source provenance: prompt uses "sources" (list), legacy uses "source_provenance" (dict)
        raw_sources = nd.get("sources", nd.get("source_provenance", {}))
        # Convert list to dict if needed (model expects Dict[str, bool])
        if isinstance(raw_sources, list):
            sources = {s: True for s in raw_sources if isinstance(s, str)}
        else:
            sources = raw_sources
        node = SubdomainNode(
            name=name,
            description=description,
            depth=depth,
            sort_order=i,
            children=children,
            source_provenance=sources,
            confidence=_safe_float(nd.get("confidence", 0.5)),
        )

        # --- Unified S2: Extract priority scoring (if present) ---
        ps = nd.get("priority_scoring") or nd.get("scoring")
        if isinstance(ps, dict):
            sc = _safe_float(ps.get("strategic_centrality", 0.0), 0.0)
            co = _safe_float(ps.get("citation_opportunity", 0.0), 0.0)
            ca = _safe_float(ps.get("content_authority", 0.0), 0.0)
            cp = _safe_float(ps.get("conversion_potential", 0.0), 0.0)
            llm_composite = 0.35 * sc + 0.25 * co + 0.20 * ca + 0.20 * cp
            llm_composite = round(llm_composite, 4)
            node.priority_factors = {
                "strategic_centrality": round(sc, 4),
                "citation_opportunity": round(co, 4),
                "content_authority": round(ca, 4),
                "conversion_potential": round(cp, 4),
            }
            node.priority_score = llm_composite
            node.metadata["llm_composite"] = llm_composite
            node.metadata["scoring_rationale"] = ps.get("scoring_rationale", "")
            node.metadata["scoring_source"] = "llm"

        # --- Unified S2: Extract persona affinity (if present) ---
        pa = nd.get("persona_affinity")
        if isinstance(pa, list):
            affinity_map: Dict[str, float] = {}
            rationale_map: Dict[str, str] = {}
            for entry in pa:
                if isinstance(entry, dict):
                    pid = entry.get("persona_id", "")
                    score = _safe_float(entry.get("score", 0.0), 0.0)
                    rationale = entry.get("rationale", "")
                    if pid:
                        affinity_map[pid] = round(score, 4)
                        if rationale:
                            rationale_map[pid] = rationale
            if affinity_map:
                node.persona_affinity = affinity_map
            if rationale_map:
                node.metadata["persona_rationale"] = rationale_map

        result.append(node)
    return result


def _extract_taxonomy_nodes(parsed: Any) -> Optional[List[Any]]:
    """Extract taxonomy node list from parsed JSON, tolerating key variants.

    The prompt uses ``"hierarchy"`` but legacy code/artifacts may use
    ``"taxonomy"``.  Returns the node list if found and non-empty, else None.
    """
    if parsed is None:
        return None
    if isinstance(parsed, dict):
        nodes = parsed.get("hierarchy") or parsed.get("taxonomy")
        if isinstance(nodes, list) and nodes:
            return nodes
        return None
    # Bare list fallback (unlikely but defensive)
    if isinstance(parsed, list) and parsed:
        return parsed
    return None


def _build_taxonomy_tree(
    nodes_data: List[Any], company_domain: str
) -> TaxonomyTree:
    """Build TaxonomyTree from parsed node data."""
    root_nodes = _parse_hierarchy_nodes(nodes_data)
    total, max_depth = _count_tree_stats(root_nodes)
    return TaxonomyTree(
        domain_name=company_domain,
        root_nodes=root_nodes,
        total_subdomains=total,
        max_depth=max_depth,
        status=TopicDiscoveryStatus.draft,
    )


def _count_tree_stats(
    nodes: List[SubdomainNode],
) -> Tuple[int, int]:
    """Count total nodes and max depth in the tree."""
    if not nodes:
        return 0, 0
    total = 0
    max_depth = 0
    for node in nodes:
        total += 1
        max_depth = max(max_depth, node.depth)
        child_total, child_depth = _count_tree_stats(node.children)
        total += child_total
        max_depth = max(max_depth, child_depth)
    return total, max_depth


def _validate_and_fix_composites(
    nodes: List[SubdomainNode],
    tolerance: float = 0.02,
) -> List[str]:
    """Verify LLM composite scores match the weighted formula; fix silently.

    Walks all nodes recursively.  If ``metadata["llm_composite"]`` differs
    from the recomputed value by more than *tolerance*, it is corrected and
    a warning string is returned.

    Returns:
        List of warning strings (empty if all composites were correct).
    """
    warnings: List[str] = []
    for node in nodes:
        pf = node.priority_factors
        if pf and node.metadata.get("scoring_source") == "llm":
            expected = round(
                0.35 * pf.get("strategic_centrality", 0.0)
                + 0.25 * pf.get("citation_opportunity", 0.0)
                + 0.20 * pf.get("content_authority", 0.0)
                + 0.20 * pf.get("conversion_potential", 0.0),
                4,
            )
            current = node.metadata.get("llm_composite", 0.0)
            if abs(current - expected) > tolerance:
                node.priority_score = expected
                node.metadata["llm_composite"] = expected
                warnings.append(
                    f"Corrected composite for '{node.name}': "
                    f"{current} → {expected}"
                )
        # Recurse into children
        warnings.extend(_validate_and_fix_composites(node.children, tolerance))
    return warnings


# ---------------------------------------------------------------------------
# S3: Dimensionality Expansion
# ---------------------------------------------------------------------------


async def run_relevance_filtering(
    subdomain: str,
    dimensions: List[Dict[str, str]],
    company_context: str,
    *,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> List[Dict[str, Any]]:
    """Classify dimension combinations as relevant/marginal/irrelevant."""
    model = model or settings.topic_discovery_dedup_model
    span = create_span(parent_span, "td-relevance-filter", input_data={
        "subdomain": subdomain, "dimensions": len(dimensions),
    })

    messages = [
        {"role": "system", "content": get_relevance_system_prompt()},
        {
            "role": "user",
            "content": build_relevance_user_prompt(
                subdomain, dimensions, company_context
            ),
        },
    ]
    _meta_rf = {
        "pipeline": "topic_discovery",
        "pipeline_step": "relevance_filter",
        "provider": extract_provider(model),
        "model": model,
        "company_slug": company_slug,
    }
    response, raw_text = await _run_completion(
        model=model, messages=messages, temperature=0.3, timeout_s=timeout_s,
        metadata=_meta_rf,
    )
    log_generation(
        span, "relevance-filter", model,
        messages[-1]["content"][:2000], raw_text[:2000],
        metadata=_meta_rf,
        usage=_extract_usage(response),
    )
    parsed = _parse_json_response(raw_text)
    if parsed is None:
        end_span(span, output={"classifications": 0})
        return []
    results = parsed.get("classifications", [])
    if not isinstance(results, list):
        end_span(span, output={"classifications": 0})
        return []
    end_span(span, output={"classifications": len(results)})
    return results


async def run_topic_generation(
    subdomain: str,
    buyer_stage: str,
    intent_type: str,
    audience_segment: str,
    company_context: str,
    *,
    model: Optional[str] = None,
    timeout_s: float = 120.0,
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> List[TopicAssignment]:
    """Generate 2-5 topic assignments for a relevant dimension cell."""
    model = model or settings.topic_discovery_brainstorm_model
    span = create_span(parent_span, "td-topic-gen", input_data={
        "subdomain": subdomain, "buyer_stage": buyer_stage, "intent_type": intent_type,
    })

    messages = [
        {"role": "system", "content": get_topic_generation_system_prompt()},
        {
            "role": "user",
            "content": build_topic_generation_user_prompt(
                subdomain, buyer_stage, intent_type, audience_segment,
                company_context,
            ),
        },
    ]
    _meta_tg = {
        "pipeline": "topic_discovery",
        "pipeline_step": "topic_generation",
        "provider": extract_provider(model),
        "model": model,
        "company_slug": company_slug,
    }
    response, raw_text = await _run_completion(
        model=model, messages=messages, timeout_s=timeout_s,
        metadata=_meta_tg,
    )
    log_generation(
        span, "topic-gen", model,
        messages[-1]["content"][:2000], raw_text[:2000],
        metadata=_meta_tg,
        usage=_extract_usage(response),
    )
    parsed = _parse_json_response(raw_text)
    if parsed is None:
        end_span(span, output={"assignments": 0})
        return []
    topics = parsed.get("topics", [])
    if not isinstance(topics, list):
        end_span(span, output={"assignments": 0})
        return []

    assignments = []
    for t in topics:
        if not isinstance(t, dict):
            continue
        assignments.append(
            TopicAssignment(
                subdomain_name=subdomain,
                topic_text=t.get("topic_text", t.get("title", "")),
                buyer_stage=BuyerStage(buyer_stage),
                intent_type=IntentType(intent_type),
                audience_segment=audience_segment,
                relevance=RelevanceCell.relevant,
                priority_score=_safe_float(t.get("priority_score", 0.5)),
                priority_factors=t.get("priority_factors", {}),
            )
        )
    end_span(span, output={"assignments": len(assignments)})
    return assignments


async def run_subdomain_expansion(
    subdomain_name: str,
    subdomain_description: str,
    buyer_stages: List[str],
    intent_types: List[str],
    audience_segments: List[Tuple[str, str]],
    company_context: str,
    *,
    persona_context: Optional[str] = None,
    model: Optional[str] = None,
    timeout_s: float = 180.0,
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> List[TopicAssignment]:
    """Expand a single subdomain into topic assignments in ONE LLM call.

    Replaces the old two-pass (relevance_filtering + topic_generation) flow.
    The LLM simultaneously prunes irrelevant combos and generates topics.

    Args:
        subdomain_name: Name of the subdomain.
        subdomain_description: Description of the subdomain.
        buyer_stages: List of buyer stage values (e.g. ["tofu", "mofu", "bofu"]).
        intent_types: List of intent type values.
        audience_segments: (persona_id, persona_name) tuples.
        company_context: Company overview markdown.
        persona_context: Optional persona markdown for focused expansion.
        model: LLM model override.
        timeout_s: Per-call timeout.
        parent_span: Optional parent trace span for LangSmith.

    Returns:
        List of TopicAssignment objects (empty on failure).
    """
    from core.topic_discovery.prompts.subdomain_expansion import (
        build_subdomain_expansion_user_prompt,
        get_subdomain_expansion_system_prompt,
    )

    model = model or settings.topic_discovery_brainstorm_model
    span = create_span(parent_span, f"td-expand/{subdomain_name[:50]}", input_data={
        "subdomain": subdomain_name,
    })

    messages = [
        {"role": "system", "content": get_subdomain_expansion_system_prompt()},
        {
            "role": "user",
            "content": build_subdomain_expansion_user_prompt(
                subdomain_name=subdomain_name,
                subdomain_description=subdomain_description,
                buyer_stages=buyer_stages,
                intent_types=intent_types,
                audience_segments=audience_segments,
                company_context=company_context,
                persona_context=persona_context,
            ),
        },
    ]
    _meta_exp = {
        "pipeline": "topic_discovery",
        "pipeline_step": "subdomain_expansion",
        "provider": extract_provider(model),
        "model": model,
        "company_slug": company_slug,
    }
    response, raw_text = await _run_completion(
        model=model, messages=messages, timeout_s=timeout_s,
        metadata=_meta_exp,
    )
    log_generation(
        span, "expansion", model,
        messages[-1]["content"][:2000], raw_text[:2000],
        metadata=_meta_exp,
        usage=_extract_usage(response),
    )
    parsed = _parse_json_response(raw_text)
    if parsed is None:
        log_score(span, "assignments_count", 0.0)
        end_span(span, output={"assignments": 0})
        return []

    topics = parsed.get("topics", [])
    if not isinstance(topics, list):
        log_score(span, "assignments_count", 0.0)
        end_span(span, output={"assignments": 0})
        return []

    assignments: List[TopicAssignment] = []
    for t in topics:
        if not isinstance(t, dict):
            continue
        # Map buyer stage string to enum
        bs_raw = t.get("buyer_stage", "tofu")
        try:
            bs = BuyerStage(bs_raw)
        except ValueError:
            bs = BuyerStage.TOFU
        # Map intent type string to enum (handle LLM alias)
        it_raw = t.get("intent_type", "informational")
        if it_raw == "commercial_investigation":
            it_raw = "commercial"
        try:
            it = IntentType(it_raw)
        except ValueError:
            it = IntentType.informational

        persona_id = t.get("persona_id", "")
        persona_name = t.get("persona_name", "")

        assignments.append(
            TopicAssignment(
                subdomain_name=subdomain_name,
                topic_text=t.get("title", t.get("topic_text", "")),
                buyer_stage=bs,
                intent_type=it,
                audience_segment=persona_name,
                relevance=RelevanceCell.relevant,
                priority_score=0.0,  # Will be set by compute_topic_priority
                persona_id=persona_id,
                persona_name=persona_name,
                metadata={
                    k: t.get(k)
                    for k in (
                        "slug",
                        "angle",
                        "description",
                        "target_keywords",
                        "ai_citation_potential",
                        "content_format",
                        "estimated_word_count",
                    )
                    if t.get(k) is not None
                },
            )
        )
    log_score(span, "assignments_count", float(len(assignments)))
    end_span(span, output={"assignments": len(assignments)})
    return assignments


# ---------------------------------------------------------------------------
# Statistical Functions (pure Python)
# ---------------------------------------------------------------------------


def compute_capture_recapture(
    source_a_count: int,
    source_b_count: int,
    overlap: int,
) -> float:
    """Compute Lincoln-Petersen capture-recapture estimate.

    N̂ = (n₁ × n₂) / m  where m = overlap count.
    Returns 0.0 if overlap is 0 (undefined).
    """
    if overlap <= 0:
        return 0.0
    return (source_a_count * source_b_count) / overlap


def compute_chao1_lower_bound(
    observed: int,
    singletons: int,
    doubletons: int,
) -> float:
    """Compute Chao1 lower-bound species richness estimate.

    S_obs + (f₁² / 2f₂)  where f₁=singletons, f₂=doubletons.
    If doubletons==0, uses S_obs + f₁*(f₁-1)/2 (bias-corrected form).
    """
    if singletons == 0:
        return float(observed)
    if doubletons == 0:
        return observed + (singletons * (singletons - 1)) / 2.0
    return observed + (singletons ** 2) / (2.0 * doubletons)


def compute_sample_coverage(
    singletons: int,
    total: int,
) -> float:
    """Compute Good-Turing sample coverage estimate.

    Ĉ = 1 − (f₁ / N)  where f₁=singletons, N=total observations.
    Returns 0.0 if total is 0.
    """
    if total <= 0:
        return 0.0
    return 1.0 - (singletons / total)


def compute_semantic_frequency_classes(
    candidates: List[SubdomainCandidate],
    embeddings: List[List[float]],
    *,
    similarity_threshold: float = 0.70,
) -> Tuple[int, int]:
    """Count semantic singletons/doubletons across rounds within a single source.

    Instead of requiring exact name repetition (which prompts forbid),
    two candidates from *different* rounds are considered a "re-discovery"
    if their embedding cosine similarity >= ``similarity_threshold``.

    Uses union-find to build connected components, then counts how many
    distinct rounds each component spans.

    Returns ``(singletons, doubletons)``.
    """
    if not candidates:
        return 0, 0

    n = len(candidates)

    # Union-Find
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    # Merge candidates from DIFFERENT rounds with high similarity
    for i in range(n):
        for j in range(i + 1, n):
            if candidates[i].round_number == candidates[j].round_number:
                # Same round — still union if similar (they're the same concept
                # within a round, so the component spans only that round)
                if _cosine_similarity(embeddings[i], embeddings[j]) >= similarity_threshold:
                    union(i, j)
            else:
                if _cosine_similarity(embeddings[i], embeddings[j]) >= similarity_threshold:
                    union(i, j)

    # Gather components: map root → set of rounds
    from collections import defaultdict
    component_rounds: Dict[int, set] = defaultdict(set)
    for i in range(n):
        root = find(i)
        component_rounds[root].add(candidates[i].round_number)

    singletons = sum(1 for rounds in component_rounds.values() if len(rounds) == 1)
    doubletons = sum(1 for rounds in component_rounds.values() if len(rounds) == 2)
    return singletons, doubletons


def compute_cluster_based_overlap(
    clusters: List[List[int]],
    source_of: List[TDSource],
) -> Dict[str, int]:
    """Compute pairwise source overlap from dedup cluster membership.

    For each cluster (group of original indices merged by dedup), check
    which sources contributed.  Two sources in the same cluster = one
    overlap unit for that pair.

    Returns dict keyed by ``"{source_a}_{source_b}"`` (sorted) with counts.
    """
    from collections import defaultdict
    from itertools import combinations

    overlap: Dict[str, int] = defaultdict(int)

    for cluster in clusters:
        # Unique sources in this cluster
        sources_in_cluster = {source_of[idx] for idx in cluster if idx < len(source_of)}
        if len(sources_in_cluster) < 2:
            continue
        # Count one overlap for every pair of sources present
        for sa, sb in combinations(sorted(sources_in_cluster, key=lambda s: s.value), 2):
            key = f"{sa.value}_{sb.value}"
            overlap[key] += 1

    return dict(overlap)


def compute_all_coverage_metrics(
    source_results: List[SourceResult],
    *,
    dedup_result: Optional[DeduplicationResult] = None,
    semantic_sim_threshold: float = 0.70,
) -> CaptureRecaptureResult:
    """Compute all coverage metrics from source results.

    When ``dedup_result`` is provided, uses:
    - Cluster-based overlap for between-source capture-recapture
    - Semantic frequency classes for within-source coverage

    When ``dedup_result`` is None, falls back to:
    - Exact name matching for between-source CR
    - Pre-computed singletons/doubletons from SourceResult
    """
    use_clusters = dedup_result is not None

    # Name sets per source (used for observed count + legacy CR path)
    source_name_sets: Dict[str, set] = {}
    for sr in source_results:
        names = {c.name.lower().strip() for c in sr.candidates if c.name}
        source_name_sets[sr.source.value] = names

    # ---- Between-source pairwise CR ----
    sources = sorted(source_name_sets.keys())
    pairwise: Dict[str, float] = {}

    if use_clusters:
        cluster_overlap = compute_cluster_based_overlap(
            dedup_result.clusters, dedup_result.source_of,
        )
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                sa, sb = sources[i], sources[j]
                key = f"{sa}_{sb}"
                overlap = cluster_overlap.get(key, 0)
                n_a = len(source_name_sets.get(sa, set()))
                n_b = len(source_name_sets.get(sb, set()))
                est = compute_capture_recapture(n_a, n_b, overlap)
                if est > 0:
                    pairwise[key] = est
    else:
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                sa, sb = sources[i], sources[j]
                set_a, set_b = source_name_sets[sa], source_name_sets[sb]
                overlap = len(set_a & set_b)
                est = compute_capture_recapture(len(set_a), len(set_b), overlap)
                if est > 0:
                    pairwise[f"{sa}_{sb}"] = est

    # Median estimate
    estimates = sorted(pairwise.values())
    median = 0.0
    if estimates:
        mid = len(estimates) // 2
        if len(estimates) % 2 == 0:
            median = (estimates[mid - 1] + estimates[mid]) / 2.0
        else:
            median = estimates[mid]

    # Observed unique count
    all_names: set = set()
    for names in source_name_sets.values():
        all_names |= names
    observed = len(all_names)

    # ---- Within-source coverage ----
    per_source: Dict[str, PerSourceCoverage] = {}

    if use_clusters:
        # Map: source_value → list of original indices into dedup_result
        source_indices: Dict[str, List[int]] = {}
        for idx, src in enumerate(dedup_result.source_of):
            source_indices.setdefault(src.value, []).append(idx)

        for sr in source_results:
            if sr.total_rounds <= 0:
                continue
            sv = sr.source.value
            indices = source_indices.get(sv, [])
            obs = len(source_name_sets.get(sv, set()))
            total_obs = _count_total_round_observations(sr.candidates)

            # Compute semantic frequency classes if embeddings are available
            if indices and len(dedup_result.embeddings) >= max(indices) + 1:
                src_embeds = [dedup_result.embeddings[i] for i in indices]
                sem_sing, sem_doub = compute_semantic_frequency_classes(
                    sr.candidates, src_embeds,
                    similarity_threshold=semantic_sim_threshold,
                )
            else:
                sem_sing, sem_doub = sr.singletons, sr.doubletons

            # Recompute Chao1 and sample coverage using semantic frequency
            chao1 = compute_chao1_lower_bound(obs, sem_sing, sem_doub)
            sample_cov = compute_sample_coverage(sem_sing, total_obs)

            per_source[sv] = PerSourceCoverage(
                source=sr.source,
                singletons=sr.singletons,
                doubletons=sr.doubletons,
                observed=obs,
                total_observations=total_obs,
                chao1_estimate=chao1,
                sample_coverage=sample_cov,
                semantic_singletons=sem_sing,
                semantic_doubletons=sem_doub,
                semantic_sim_threshold=semantic_sim_threshold,
            )
    else:
        for sr in source_results:
            if sr.total_rounds > 0:
                per_source[sr.source.value] = PerSourceCoverage(
                    source=sr.source,
                    singletons=sr.singletons,
                    doubletons=sr.doubletons,
                    observed=len(source_name_sets.get(sr.source.value, set())),
                    total_observations=_count_total_round_observations(sr.candidates),
                    chao1_estimate=sr.chao1_estimate,
                    sample_coverage=sr.source_sample_coverage,
                )

    # Aggregate: use minimum per-source coverage (most conservative)
    coverages = [
        psc.sample_coverage for psc in per_source.values()
        if psc.sample_coverage > 0
    ]
    agg_coverage = min(coverages) if coverages else 0.0

    chao1_ratios = [
        psc.observed / psc.chao1_estimate
        for psc in per_source.values()
        if psc.chao1_estimate > 0
    ]
    agg_chao1_ratio = min(chao1_ratios) if chao1_ratios else 0.0

    # Deprecated fields — sum for backward compat
    total_singletons = sum(sr.singletons for sr in source_results)
    total_doubletons = sum(sr.doubletons for sr in source_results)

    return CaptureRecaptureResult(
        pairwise_estimates=pairwise,
        median_estimate=median,
        estimate_range=[min(estimates, default=0.0), max(estimates, default=0.0)],
        chao1_lower_bound=max(
            (psc.chao1_estimate for psc in per_source.values()), default=0.0,
        ),
        sample_coverage=agg_coverage,
        observed_count=observed,
        total_singletons=total_singletons,
        total_doubletons=total_doubletons,
        coverage_target=0.95,
        meets_target=agg_coverage >= 0.95,
        per_source_coverage=per_source,
        aggregate_sample_coverage=agg_coverage,
        aggregate_chao1_ratio=agg_chao1_ratio,
        cluster_based_overlap=use_clusters,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _count_frequency_classes(
    candidates: List[SubdomainCandidate],
) -> Tuple[int, int]:
    """Count singletons and doubletons from candidate names (raw frequency)."""
    from collections import Counter

    name_counts = Counter(c.name.lower().strip() for c in candidates if c.name)
    singletons = sum(1 for v in name_counts.values() if v == 1)
    doubletons = sum(1 for v in name_counts.values() if v == 2)
    return singletons, doubletons


def _count_frequency_classes_by_round(
    candidates: List[SubdomainCandidate],
) -> Tuple[int, int]:
    """Count singletons/doubletons by round presence (not raw frequency).

    A singleton = a unique name that appeared in exactly 1 round.
    A doubleton = a unique name that appeared in exactly 2 rounds.
    This is the correct unit for Chao1 within a single source,
    where each expansion round is a repeated draw from the same process.
    """
    from collections import defaultdict

    name_rounds: Dict[str, set] = defaultdict(set)
    for c in candidates:
        if c.name:
            name_rounds[c.name.lower().strip()].add(c.round_number)

    singletons = sum(1 for rounds in name_rounds.values() if len(rounds) == 1)
    doubletons = sum(1 for rounds in name_rounds.values() if len(rounds) == 2)
    return singletons, doubletons


def _count_total_round_observations(
    candidates: List[SubdomainCandidate],
) -> int:
    """Count total (name, round) incidences — denominator N for Good-Turing.

    Each unique name contributes the number of distinct rounds it appeared in.
    Duplicates within the same round are counted once.
    """
    from collections import defaultdict

    name_rounds: Dict[str, set] = defaultdict(set)
    for c in candidates:
        if c.name:
            name_rounds[c.name.lower().strip()].add(c.round_number)

    return sum(len(rounds) for rounds in name_rounds.values())
