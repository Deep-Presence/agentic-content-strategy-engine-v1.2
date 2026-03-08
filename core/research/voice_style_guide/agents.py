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
from core.models.voice_style_guide import (
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
from core.shared_tools.tracing import create_span, end_span, log_generation

logger = logging.getLogger(__name__)

_MIN_AUTHORS = 2
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences wrapping JSON output."""
    m = _CODE_FENCE_RE.match(text.strip())
    return m.group(1).strip() if m else text.strip()


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    """Parse a JSON array from text with tolerant extraction."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        return [parsed]
    except json.JSONDecodeError:
        pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    return []


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
    timeout_s: float = 120.0,
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
        system_prompt = get_author_discovery_system_prompt().replace(
            "{max_authors}", str(input_data.max_authors),
        )
        user_prompt = build_author_discovery_user_prompt(
            input_data, company_context_md, persona_mds,
        )

        model = settings.voice_style_guide_discovery_model

        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4096,
                response_format={"type": "json_object"},
            ),
            timeout=timeout_s,
        )

        raw_text = response.choices[0].message.content or ""
        log_generation(
            span, "vsg-author-discovery", model,
            user_prompt[:2000], raw_text[:2000],
        )

        cleaned = _strip_code_fences(raw_text)
        briefs_raw = _parse_json_array(cleaned)
        valid_briefs, errors = _validate_author_briefs(briefs_raw, input_data.max_authors)

        # Retry once if validation fails
        if len(valid_briefs) < _MIN_AUTHORS or errors:
            logger.warning("Author discovery first attempt had issues: %s. Retrying.", errors)
            repair_prompt = (
                f"Your previous response had issues: {'; '.join(errors)}. "
                f"Please return a valid JSON array of {input_data.max_authors} author objects. "
                f"Each must have: name, description, famous_works (list), resonance_rationale."
            )
            try:
                retry_response = await asyncio.wait_for(
                    litellm.acompletion(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": repair_prompt},
                        ],
                        temperature=0.7,
                        max_tokens=4096,
                        response_format={"type": "json_object"},
                    ),
                    timeout=timeout_s,
                )
                retry_text = retry_response.choices[0].message.content or ""
                retry_cleaned = _strip_code_fences(retry_text)
                retry_raw = _parse_json_array(retry_cleaned)
                retry_briefs, retry_errors = _validate_author_briefs(
                    retry_raw, input_data.max_authors,
                )
                if len(retry_briefs) >= _MIN_AUTHORS:
                    valid_briefs = retry_briefs
                    errors = retry_errors
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
    timeout_s: float = 300.0,
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

        result_md = await asyncio.wait_for(
            asyncio.to_thread(
                perplexity_client.research,
                query=full_prompt,
                timeout_s=timeout_s,
            ),
            timeout=timeout_s,
        )

        log_generation(
            span, f"vsg-author-research-{brief.author_id}",
            settings.perplexity_deep_research_model,
            full_prompt[:2000], result_md[:2000] if result_md else "",
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

        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=8192,
            ),
            timeout=timeout_s,
        )

        guide_md = response.choices[0].message.content or ""
        log_generation(
            span, "vsg-voice-synthesis", model,
            user_prompt[:2000], guide_md[:2000],
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
