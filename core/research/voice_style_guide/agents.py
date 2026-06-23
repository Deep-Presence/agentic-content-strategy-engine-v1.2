"""Voice Style Guide agents — Discovery (LiteLLM), Research (Perplexity), Synthesis (LiteLLM).

Agent 1 — run_author_discovery(): Gemini Flash via LiteLLM → JSON AuthorBriefs
Agent 2 — run_author_research(): Perplexity sonar-deep-research → author style analysis MD
Agent 3 — run_voice_synthesis(): Claude Sonnet via LiteLLM → voice style guide MD
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import litellm
except ImportError:
    litellm = None  # type: ignore[assignment]

from core.config.settings import settings
from core.model_config.runtime import actual_provider, resolve_model_config_for_agent
from core.models.voice_style_guide import (
    VSG_MIN_AUTHORS,
    AuthorBrief,
    AuthorResearchResult,
    VoiceStyleGuideInput,
    WorkPersonaMapping,
)
from core.research.prompts.voice_style_guide.author_discovery import (
    build_author_discovery_user_prompt,
    get_author_discovery_system_prompt,
)
from core.research.prompts.voice_style_guide.author_research import (
    build_author_research_user_prompt,
    get_author_research_system_prompt,
)
from core.research.prompts.voice_style_guide.voice_synthesis import (
    build_voice_synthesis_user_prompt,
    get_voice_synthesis_system_prompt,
)
from core.research.tools import perplexity_client
from core.shared_tools.tracing import create_span, end_span, extract_provider, log_generation

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)
_MAX_PAUSE_TURNS = 3


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences wrapping JSON output."""
    m = _CODE_FENCE_RE.match(text.strip())
    return m.group(1).strip() if m else text.strip()


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


def _extract_assistant_continuation_content(response: Any, fallback_text: str) -> Any:
    """Extract Anthropic-native assistant content blocks from LiteLLM response."""
    hidden = getattr(response, "_hidden_params", None)
    if isinstance(hidden, dict):
        original = hidden.get("original_response")
        if isinstance(original, list) and original:
            return original
    return fallback_text


async def _run_discovery_completion(
    *,
    model: str,
    api_key: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    tools: Optional[List[Dict[str, Any]]],
    timeout_s: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, str]:
    """Run completion and continue on Anthropic pause_turn when needed."""
    convo = list(messages)
    response: Any = None
    raw_text = ""

    _kwargs: Dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "messages": convo,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tools": tools,
    }
    if metadata is not None:
        _kwargs["metadata"] = metadata

    from core.shared_tools.cost_tracker import extract_usage_litellm, track_llm_cost
    from core.shared_tools.tracing import extract_provider

    _total_pt, _total_ct = 0, 0
    for turn in range(_MAX_PAUSE_TURNS + 1):
        _kwargs["messages"] = convo
        response = await asyncio.wait_for(
            litellm.acompletion(**_kwargs),
            timeout=timeout_s,
        )
        _pt, _ct = extract_usage_litellm(response)
        _total_pt += _pt
        _total_ct += _ct
        track_llm_cost(
            model=model, provider=extract_provider(model),
            pipeline="voice_style_guide",
            pipeline_step=f"author_discovery/turn-{turn}",
            prompt_tokens=_pt, completion_tokens=_ct,
            call_site="core.research.voice_style_guide.agents",
        )
        choice = response.choices[0]
        raw_text = _extract_text_content(choice.message.content)
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason != "pause_turn":
            if turn > 0:
                track_llm_cost(
                    model=model, provider=extract_provider(model),
                    pipeline="voice_style_guide",
                    pipeline_step="author_discovery/total",
                    prompt_tokens=_total_pt, completion_tokens=_total_ct,
                    call_site="core.research.voice_style_guide.agents",
                )
            return response, raw_text

        if turn >= _MAX_PAUSE_TURNS:
            logger.warning(
                "Author discovery hit pause_turn limit (%d); returning partial response.",
                _MAX_PAUSE_TURNS,
            )
            track_llm_cost(
                model=model, provider=extract_provider(model),
                pipeline="voice_style_guide",
                pipeline_step="author_discovery/total",
                prompt_tokens=_total_pt, completion_tokens=_total_ct,
                call_site="core.research.voice_style_guide.agents",
            )
            return response, raw_text

        assistant_content = _extract_assistant_continuation_content(response, raw_text)
        convo.append({"role": "assistant", "content": assistant_content})
        logger.info("Author discovery received pause_turn; continuing (turn=%d).", turn + 1)

    return response, raw_text


def _extract_authors_from_per_persona(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract unique authors from per-persona discovery schema.

    Handles: {"personas": [{"recommended_authors": [...]}], "metadata": {...}}
    Deduplicates by author_name (case-insensitive, keeps first occurrence).
    Falls back to metadata.authors_requiring_research if personas yield 0 authors.
    """
    personas = parsed.get("personas")
    if not isinstance(personas, list):
        return []

    seen_names: set[str] = set()
    authors: List[Dict[str, Any]] = []

    for persona in personas:
        if not isinstance(persona, dict):
            continue
        rec_authors = persona.get("recommended_authors")
        if not isinstance(rec_authors, list):
            continue
        for raw_author in rec_authors:
            if not isinstance(raw_author, dict):
                continue
            name = raw_author.get("author_name", raw_author.get("name", ""))
            if not isinstance(name, str) or not name.strip():
                continue
            name_key = name.strip().lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            authors.append(_map_discovery_author(raw_author))

    # Fallback: if personas yielded 0 authors, try metadata.authors_requiring_research
    if not authors:
        metadata = parsed.get("metadata")
        if isinstance(metadata, dict):
            research_list = metadata.get("authors_requiring_research")
            if isinstance(research_list, list):
                for item in research_list:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("author_name", "")
                    if not isinstance(name, str) or not name.strip():
                        continue
                    name_key = name.strip().lower()
                    if name_key in seen_names:
                        continue
                    seen_names.add(name_key)
                    authors.append(_map_discovery_author(item))

    return authors


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    """Parse a JSON array from text with tolerant extraction.

    Handles three schema variants:
    1. Per-persona: {"personas": [{"recommended_authors": [...]}]}
    2. Set-level: {"recommended_authors": [...]}
    3. Flat array: [{"name": ...}, ...]

    Maps prompt field names (author_name, bio, key_works, etc.) to
    AuthorBrief-compatible field names (name, description, famous_works).
    """
    if not text or not isinstance(text, str) or not text.strip():
        logger.warning("_parse_json_array received empty text")
        return []

    parsed: Any = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try bracket extraction as fallback
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        if parsed is None:
            # Try brace extraction for top-level object
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    logger.warning(
                        "JSON parse failed on all strategies. Raw text (first 500 chars): %s",
                        text[:500],
                    )
                    return []
            else:
                logger.warning(
                    "No JSON structure found in response. Raw text (first 500 chars): %s",
                    text[:500],
                )
                return []

    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, dict):
        # Handle prompt-defined error objects ({"error": true, ...})
        if parsed.get("error"):
            logger.warning(
                "Discovery LLM returned error object: type=%s, message=%s",
                parsed.get("error_type", "unknown"),
                parsed.get("message", "unknown"),
            )
            return []

        # Schema 1: Per-persona — {"personas": [{"recommended_authors": [...]}]}
        if "personas" in parsed and isinstance(parsed["personas"], list):
            authors = _extract_authors_from_per_persona(parsed)
            if authors:
                return authors
            logger.warning(
                "Per-persona schema yielded 0 authors. Keys present: %s",
                list(parsed.keys()),
            )
            # Fall through to try recommended_authors or metadata

        # Schema 2: Set-level — {"recommended_authors": [...]}
        authors = parsed.get("recommended_authors")
        if isinstance(authors, list):
            if not authors:
                logger.warning(
                    "LLM returned empty recommended_authors array. Keys present: %s",
                    list(parsed.keys()),
                )
            return [_map_discovery_author(a) for a in authors if isinstance(a, dict)]

        # Schema 3: metadata-only fallback
        metadata = parsed.get("metadata")
        if isinstance(metadata, dict):
            research_list = metadata.get("authors_requiring_research")
            if isinstance(research_list, list) and research_list:
                return [_map_discovery_author(a) for a in research_list if isinstance(a, dict)]

        logger.warning(
            "No recognized author schema in response dict. Keys present: %s",
            list(parsed.keys()),
        )
        return [parsed]

    return []


def _map_discovery_author(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map discovery prompt schema fields to AuthorBrief schema."""
    mapped: Dict[str, Any] = {}
    mapped["name"] = raw.get("author_name", raw.get("name", ""))
    mapped["description"] = raw.get("bio", raw.get("description", ""))
    mapped["resonance_rationale"] = raw.get(
        "selection_rationale", raw.get("resonance_rationale", ""),
    )

    # key_works (list of dicts with title) → famous_works (list of strings)
    key_works = raw.get("key_works")
    if isinstance(key_works, list):
        mapped["famous_works"] = [
            w["title"] if isinstance(w, dict) and "title" in w else str(w)
            for w in key_works
        ]
    else:
        mapped["famous_works"] = raw.get("famous_works", [])

    # Pass through fields that already match
    for field in ("author_id", "source", "work_persona_mapping"):
        if field in raw:
            mapped[field] = raw[field]

    return mapped


def _slugify_name(name: str) -> str:
    """Convert an author name to a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return slug.strip("-") or "unknown"


def _validate_author_briefs(
    raw: List[Dict[str, Any]],
    max_authors: int,
) -> Tuple[List[AuthorBrief], List[str]]:
    """Validate raw JSON dicts → AuthorBrief models.

    Returns (valid_briefs, error_messages).
    Deduplicates by name and assigns author_id slugs.
    """
    valid: List[AuthorBrief] = []
    errors: List[str] = []
    seen_names: set[str] = set()

    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"Author {i}: not a dict")
            continue

        name_raw = item.get("name", "")
        if not isinstance(name_raw, str):
            errors.append(f"Author {i}: name is not a string")
            continue
        name = name_raw.strip()
        if not name:
            errors.append(f"Author {i}: missing required field 'name'")
            continue

        name_lower = name.lower()
        if name_lower in seen_names:
            errors.append(f"Author {i}: duplicate name '{name}'")
            continue
        seen_names.add(name_lower)

        try:
            brief = AuthorBrief.model_validate(item)
        except Exception as exc:
            errors.append(f"Author {i} ({name}): validation error: {exc}")
            continue

        if not brief.author_id:
            brief.author_id = _slugify_name(name)
        brief.source = "agent"
        valid.append(brief)

    if len(valid) > max_authors:
        valid = valid[:max_authors]

    return valid, errors


# ---------------------------------------------------------------------------
# Agent 1 — Author Discovery (LiteLLM → Gemini Flash)
# ---------------------------------------------------------------------------


async def run_author_discovery(
    input_data: VoiceStyleGuideInput,
    company_context_md: str,
    persona_mds: List[str],
    parent_span: Optional[Any] = None,
    timeout_s: float = 300.0,
) -> Tuple[List[AuthorBrief], float]:
    """Discover influential authors using Gemini Flash via LiteLLM.

    Returns (briefs, execution_time_s). Validates and retries once on malformed output.
    Never raises — returns empty list on failure.
    """
    span = create_span(
        parent_span,
        "agent/vsg-author-discovery",
        input_data={"company": input_data.company_name},
    )
    start = time.time()

    try:
        system_prompt = get_author_discovery_system_prompt()
        user_prompt = build_author_discovery_user_prompt(
            input_data, company_context_md, persona_mds,
        )

        model = settings.voice_style_guide_discovery_model
        api_key = settings.anthropic_api_key

        # Web search tool for real-time author verification.
        # Incompatible with response_format=json_object (citations conflict),
        # so we rely on the system prompt for JSON instruction instead.
        _web_search_tool = {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }

        _disc_meta = {
            "pipeline": "voice_style_guide",
            "pipeline_step": "author_discovery",
            "provider": extract_provider(model),
            "model": model,
            "company_slug": input_data.company_slug or "",
        }
        _, raw_text = await _run_discovery_completion(
            model=model,
            api_key=api_key,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=8192,
            tools=[_web_search_tool],
            timeout_s=timeout_s,
            metadata=_disc_meta,
        )
        log_generation(
            span, "vsg-author-discovery", model,
            user_prompt[:2000], raw_text[:2000],
            metadata=_disc_meta,
        )

        cleaned = _strip_code_fences(raw_text)
        briefs_raw = _parse_json_array(cleaned)
        valid_briefs, errors = _validate_author_briefs(briefs_raw, input_data.max_authors)

        # Retry once if validation fails — pass full conversation context
        if len(valid_briefs) < VSG_MIN_AUTHORS or errors:
            logger.warning(
                "Author discovery first attempt: %d valid briefs (need %d), "
                "parse returned %d raw items, errors: %s. Retrying with context.",
                len(valid_briefs), VSG_MIN_AUTHORS, len(briefs_raw), errors,
            )
            repair_prompt = (
                f"Your previous response had issues: {'; '.join(errors) or 'no valid authors extracted'}. "
                f"Please return a valid JSON object with a 'recommended_authors' array "
                f"containing {input_data.max_authors} author objects. "
                f"Each author must have: author_name, bio, key_works (list of "
                f"{{title, type, relevance}}), selection_rationale, per_persona_resonance."
            )
            try:
                _, retry_text = await _run_discovery_completion(
                    model=model,
                    api_key=api_key,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": raw_text},
                        {"role": "user", "content": repair_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=8192,
                    tools=[_web_search_tool],
                    timeout_s=timeout_s,
                    metadata=_disc_meta,
                )
                logger.info(
                    "Author discovery retry response length=%d, first 500 chars: %s",
                    len(retry_text), retry_text[:500],
                )
                retry_cleaned = _strip_code_fences(retry_text)
                retry_raw = _parse_json_array(retry_cleaned)
                retry_briefs, retry_errors = _validate_author_briefs(
                    retry_raw, input_data.max_authors,
                )
                if len(retry_briefs) >= VSG_MIN_AUTHORS:
                    valid_briefs = retry_briefs
                    errors = retry_errors
                else:
                    logger.warning(
                        "Retry also returned insufficient authors: %d valid, errors: %s",
                        len(retry_briefs), retry_errors,
                    )
            except Exception as retry_exc:
                logger.warning("Retry also failed: %s. Using partial results.", retry_exc)

        elapsed = time.time() - start
        end_span(span, output={"author_count": len(valid_briefs)})
        return valid_briefs, elapsed

    except asyncio.TimeoutError:
        elapsed = time.time() - start
        end_span(span, error=f"Timeout after {timeout_s}s")
        logger.error("Author discovery timed out after %ss", timeout_s)
        return [], elapsed
    except Exception as exc:
        elapsed = time.time() - start
        end_span(span, error=f"APIError: {exc}")
        logger.error("Author discovery failed: %s", exc)
        return [], elapsed


# ---------------------------------------------------------------------------
# Agent 2 — Author Research (Perplexity sonar-deep-research)
# ---------------------------------------------------------------------------


async def run_author_research(
    brief: AuthorBrief,
    input_data: VoiceStyleGuideInput,
    company_context_md: str,
    persona_summaries: str,
    parent_span: Optional[Any] = None,
    timeout_s: float = 900.0,
) -> AuthorResearchResult:
    """Deep-research an author's writing style via Perplexity sonar-deep-research.

    Returns AuthorResearchResult with content_md or error. Never raises.
    """
    span = create_span(
        parent_span,
        f"agent/vsg-author-research/{brief.author_id}",
        input_data={"author_id": brief.author_id, "author": brief.name},
    )
    start = time.time()

    try:
        system_prompt = get_author_research_system_prompt()
        user_prompt = build_author_research_user_prompt(
            brief, input_data, company_context_md, persona_summaries,
        )
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        resolved = None
        if input_data.workspace_id:
            resolved = await resolve_model_config_for_agent(
                workspace_id=input_data.workspace_id,
                workspace_slug=input_data.workspace_slug or input_data.company_slug or "",
                agent_key="research.vsg.author_research",
            )
        effective_model = (
            resolved.model
            if resolved is not None
            else settings.perplexity_deep_research_model
        )
        resolved_timeout = getattr(resolved, "timeout_s", None) if resolved is not None else None
        effective_timeout_s = (
            resolved_timeout if isinstance(resolved_timeout, (int, float)) else timeout_s
        )
        result_md, _pplx_usage = await asyncio.wait_for(
            asyncio.to_thread(
                perplexity_client.research,
                query=full_prompt,
                timeout_s=effective_timeout_s,
                model=effective_model,
                pipeline="voice_style_guide",
                pipeline_step="author_research",
                company_slug=input_data.company_slug or "",
                api_key=getattr(resolved, "api_key", None),
                base_url=getattr(resolved, "base_url", None),
                workspace_id=input_data.workspace_id if resolved is not None else None,
                agent_key="research.vsg.author_research" if resolved is not None else "",
                credential_id=getattr(resolved, "credential_id", None),
                model_config_id=getattr(resolved, "model_config_id", None),
                actual_provider=actual_provider(effective_model) if resolved is not None else "",
                workspace_billed=resolved is not None,
            ),
            timeout=effective_timeout_s,
        )

        log_generation(
            span, f"vsg-author-research-{brief.author_id}",
            effective_model,
            full_prompt[:2000], result_md[:2000] if result_md else "",
            metadata={
                "pipeline": "voice_style_guide",
                "pipeline_step": "author_research",
                "provider": "perplexity",
                "model": effective_model,
                "company_slug": input_data.company_slug or "",
            },
            usage=_pplx_usage,
        )
        end_span(span, output={"word_count": len(result_md.split()) if result_md else 0})

        return AuthorResearchResult(
            author_id=brief.author_id,
            name=brief.name,
            content_md=result_md,
            word_count=len(result_md.split()) if result_md else 0,
            execution_time_s=time.time() - start,
        )
    except asyncio.TimeoutError:
        end_span(span, error=f"Timeout after {timeout_s}s")
        return AuthorResearchResult(
            author_id=brief.author_id,
            name=brief.name,
            error=f"Timeout after {timeout_s}s",
            execution_time_s=time.time() - start,
        )
    except Exception as exc:
        end_span(span, error=f"APIError: {exc}")
        return AuthorResearchResult(
            author_id=brief.author_id,
            name=brief.name,
            error=str(exc),
            execution_time_s=time.time() - start,
        )


# ---------------------------------------------------------------------------
# Agent 3 — Voice Synthesis (LiteLLM → Claude Sonnet)
# ---------------------------------------------------------------------------


async def run_voice_synthesis(
    author_research_mds: Dict[str, str],
    company_context_md: str,
    persona_mds: List[str],
    input_data: VoiceStyleGuideInput,
    parent_span: Optional[Any] = None,
    timeout_s: float = 180.0,
) -> Tuple[str, float]:
    """Synthesize a voice style guide from author research via Claude Sonnet.

    Returns (guide_md, execution_time_s). Never raises — returns empty string on failure.
    """
    span = create_span(
        parent_span,
        "agent/vsg-voice-synthesis",
        input_data={"company": input_data.company_name, "author_count": len(author_research_mds)},
    )
    start = time.time()

    try:
        system_prompt = get_voice_synthesis_system_prompt()
        user_prompt = build_voice_synthesis_user_prompt(
            author_research_mds, company_context_md, persona_mds, input_data,
        )

        model = settings.voice_style_guide_synthesis_model

        _synth_meta = {
            "pipeline": "voice_style_guide",
            "pipeline_step": "voice_synthesis",
            "provider": extract_provider(model),
            "model": model,
            "company_slug": input_data.company_slug or "",
        }
        if input_data.workspace_id:
            from core.content_engine.llm_client import llm_call_for_agent

            response = await llm_call_for_agent(
                workspace_id=input_data.workspace_id,
                workspace_slug=input_data.workspace_slug or input_data.company_slug or "",
                agent_key="research.vsg.synthesis",
                system=system_prompt,
                user=user_prompt,
                temperature=0.3,
                max_tokens=8192,
                metadata=_synth_meta,
            )
            guide_md = response.content
            response_model = response.model or model
        else:
            from core.shared_tools.openrouter_client import get_async_client
            or_client = get_async_client()
            response = await asyncio.wait_for(
                or_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=8192,
                    extra_body={"metadata": _synth_meta},
                ),
                timeout=timeout_s,
            )
            guide_md = response.choices[0].message.content or ""
            response_model = getattr(response, "model", None) or model
        log_generation(
            span, "vsg-voice-synthesis", response_model,
            user_prompt[:2000], guide_md[:2000],
            metadata=_synth_meta,
        )
        end_span(span, output={"word_count": len(guide_md.split()) if guide_md else 0})

        elapsed = time.time() - start
        return guide_md, elapsed

    except asyncio.TimeoutError:
        elapsed = time.time() - start
        end_span(span, error=f"Timeout after {timeout_s}s")
        logger.error("Voice synthesis timed out after %ss", timeout_s)
        return "", elapsed
    except Exception as exc:
        elapsed = time.time() - start
        end_span(span, error=f"APIError: {exc}")
        logger.error("Voice synthesis failed: %s", exc)
        return "", elapsed
