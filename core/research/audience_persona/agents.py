"""Audience Persona agents — Suggester (Gemini Flash) + Profile Generator (Perplexity).

Agent 1 — run_persona_suggester(): Gemini Flash via raw google.genai SDK → JSON PersonaBriefs
Agent 2 — run_persona_profile_generator(): Perplexity sonar-deep-research → persona profile MD
Helper — _load_knowledge_docs(): Load + concatenate uploaded knowledge doc texts
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types as genai_types

from core.config.settings import settings
from core.models.audience_persona import (
    AudiencePersonaInput,
    PersonaAgentResult,
    PersonaBrief,
)
from core.research.prompts.persona_generator import (
    build_persona_generator_user_prompt,
    get_persona_generator_system_prompt,
)
from core.research.prompts.persona_suggester import (
    build_persona_suggester_user_prompt,
    get_persona_suggester_system_prompt,
)
from core.research.tools import perplexity_client
from core.shared_tools.tracing import create_span, end_span, log_generation

logger = logging.getLogger(__name__)

_MIN_BRIEFS = 3

# Regex to strip markdown code fences from LLM JSON responses.
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_gemini_api_key() -> str:
    """Resolve Google API key for audience persona pipeline.

    Fallback chain: google_api_key_audience_persona → google_api_key_persona_research_deepagent.
    """
    key = settings.google_api_key_audience_persona or settings.google_api_key_persona_research_deepagent
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY_AUDIENCE_PERSONA (or GOOGLE_API_KEY_PERSONA_RESEARCH_DEEPAGENT) "
            "is not set. Add it to .env.local to enable the persona suggester."
        )
    return key


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences wrapping JSON output."""
    m = _CODE_FENCE_RE.match(text.strip())
    return m.group(1).strip() if m else text.strip()


def _validate_briefs(
    raw: List[Dict[str, Any]],
    max_personas: int,
) -> Tuple[List[PersonaBrief], List[str]]:
    """Validate raw JSON dicts → PersonaBrief models.

    Returns (valid_briefs, error_messages).
    """
    valid: List[PersonaBrief] = []
    errors: List[str] = []
    seen_names: set[str] = set()

    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"Brief {i}: not a dict")
            continue

        name_raw = item.get("persona_name", "")
        if not isinstance(name_raw, str):
            errors.append(f"Brief {i}: persona_name is not a string (got {type(name_raw).__name__})")
            continue
        name = name_raw.strip()
        if not name:
            errors.append(f"Brief {i}: missing required field 'persona_name'")
            continue

        name_lower = name.lower()
        if name_lower in seen_names:
            errors.append(f"Brief {i}: duplicate persona_name '{name}'")
            continue
        seen_names.add(name_lower)

        try:
            brief = PersonaBrief.model_validate(item)
        except Exception as exc:
            errors.append(f"Brief {i} ({name}): validation error: {exc}")
            continue

        if not brief.brief_id:
            brief.brief_id = f"pb-{uuid.uuid4().hex[:8]}"
        brief.source = "agent"
        valid.append(brief)

    if len(valid) > max_personas:
        valid = valid[:max_personas]

    return valid, errors


async def _load_knowledge_docs(
    storage: "StorageBackend",
    effective_slug: str,
    company_slug: str,
    max_chars: int = 50_000,
) -> str:
    """Load and concatenate text from uploaded knowledge docs.

    Follows effective_slug → company_slug fallback chain.
    Returns empty string if no docs uploaded.

    Phase 6 (R2 migration): reads via StorageBackend instead of filesystem.
    """
    from core.shared_tools.knowledge_doc_metadata import doc_storage_key, load_metadata
    from core.shared_tools.text_extraction import extract_text_from_bytes

    docs = load_metadata(effective_slug, storage=storage)
    used_slug = effective_slug
    if not docs and effective_slug != company_slug:
        docs = load_metadata(company_slug, storage=storage)
        used_slug = company_slug
    if not docs:
        return ""

    parts: List[str] = []

    for doc in docs:
        key = doc_storage_key(used_slug, doc.stored_filename)
        file_bytes = storage.read_bytes(key)
        if file_bytes is None:
            continue
        try:
            from pathlib import Path as _Path
            suffix = _Path(doc.stored_filename).suffix.lower()
            text = extract_text_from_bytes(file_bytes, suffix)
        except Exception:
            logger.warning("Failed to extract text from %s", key)
            continue
        if not text:
            continue
        section = f"### {doc.filename}\n\n{text}"
        parts.append(section)

    result = "\n\n".join(parts)
    if len(result) > max_chars:
        logger.warning(
            "Knowledge docs truncated from %d to %d chars", len(result), max_chars,
        )
        result = result[:max_chars]
    return result


# ---------------------------------------------------------------------------
# Agent 1 — Persona Suggester (Gemini Flash)
# ---------------------------------------------------------------------------


async def run_persona_suggester(
    input_data: AudiencePersonaInput,
    company_context_md: str,
    customer_reviews_md: str,
    knowledge_docs_text: str = "",
    parent_span: Optional[Any] = None,
    timeout_s: float = 120.0,
) -> Tuple[List[PersonaBrief], float]:
    """Generate persona brief suggestions using Gemini Flash.

    Returns (briefs, execution_time_s). Validates and retries once on malformed output.
    Never raises — returns empty list on failure.
    """
    span = create_span(
        parent_span,
        "agent/persona-suggester",
        input_data={"company": input_data.company_name},
    )
    start = time.time()

    try:
        api_key = _get_gemini_api_key()
        client = genai.Client(api_key=api_key)

        system_prompt = get_persona_suggester_system_prompt().format(
            max_personas=input_data.max_personas,
        )
        user_prompt = build_persona_suggester_user_prompt(
            input_data, company_context_md, customer_reviews_md, knowledge_docs_text,
        )

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.7,
            max_output_tokens=4096,
        )

        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=settings.audience_persona_suggester_model,
                contents=user_prompt,
                config=config,
            ),
            timeout=timeout_s,
        )

        raw_text = response.text or ""
        log_generation(
            span, "persona-suggester", settings.audience_persona_suggester_model,
            user_prompt[:2000], raw_text[:2000],
            metadata={
                "pipeline": "audience_persona",
                "pipeline_step": "persona_suggester",
                "provider": "google",
                "model": settings.audience_persona_suggester_model,
                "company_slug": input_data.company_slug or "",
            },
        )

        # Parse JSON with tolerant extraction
        cleaned = _strip_code_fences(raw_text)
        briefs_raw = _parse_json_array(cleaned)
        valid_briefs, errors = _validate_briefs(briefs_raw, input_data.max_personas)

        # Retry once if validation fails
        if len(valid_briefs) < _MIN_BRIEFS or errors:
            logger.warning("Suggester first attempt had issues: %s. Retrying.", errors)
            repair_prompt = (
                f"Your previous response had issues: {'; '.join(errors)}. "
                f"Please return a valid JSON array of {input_data.max_personas} persona briefs. "
                f"Each must have: persona_name, tagline, description, rationale (list of strings)."
            )
            try:
                retry_response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=settings.audience_persona_suggester_model,
                        contents=repair_prompt,
                        config=config,
                    ),
                    timeout=timeout_s,
                )
                retry_text = retry_response.text or ""
                retry_cleaned = _strip_code_fences(retry_text)
                retry_raw = _parse_json_array(retry_cleaned)
                retry_briefs, retry_errors = _validate_briefs(retry_raw, input_data.max_personas)
                if len(retry_briefs) >= _MIN_BRIEFS:
                    valid_briefs = retry_briefs
                    errors = retry_errors
            except Exception as retry_exc:
                logger.warning("Retry also failed: %s. Using partial results.", retry_exc)

        elapsed = time.time() - start
        end_span(span, output={"brief_count": len(valid_briefs)})
        return valid_briefs, elapsed

    except asyncio.TimeoutError:
        elapsed = time.time() - start
        end_span(span, error=f"Timeout: after {timeout_s}s")
        logger.error("Persona suggester timed out after %ss", timeout_s)
        return [], elapsed
    except Exception as exc:
        elapsed = time.time() - start
        end_span(span, error=f"APIError: {exc}")
        logger.error("Persona suggester failed: %s", exc)
        return [], elapsed


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    """Parse a JSON array from text with tolerant extraction."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        return [parsed]
    except json.JSONDecodeError:
        pass

    # Tolerant extraction: find first [ to last ]
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


# ---------------------------------------------------------------------------
# Agent 2 — Persona Profile Generator (Perplexity)
# ---------------------------------------------------------------------------


async def run_persona_profile_generator(
    brief: PersonaBrief,
    input_data: AudiencePersonaInput,
    company_context_md: str,
    customer_reviews_md: str,
    knowledge_docs_text: str = "",
    parent_span: Optional[Any] = None,
    timeout_s: float = 300.0,
    revision_note: Optional[str] = None,
) -> PersonaAgentResult:
    """Generate detailed persona profile from an approved brief via Perplexity deep research."""
    span = create_span(
        parent_span,
        f"agent/persona-generator/{brief.persona_name}",
        input_data={"brief_id": brief.brief_id, "persona": brief.persona_name},
    )
    start = time.time()

    try:
        system_prompt = get_persona_generator_system_prompt()
        user_prompt = build_persona_generator_user_prompt(
            brief, input_data, company_context_md, customer_reviews_md,
            knowledge_docs_text, revision_note=revision_note,
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
            span, f"persona-generator-{brief.persona_name}",
            settings.audience_persona_generator_model,
            full_prompt[:2000], result_md[:2000] if result_md else "",
            metadata={
                "pipeline": "audience_persona",
                "pipeline_step": "persona_generator",
                "provider": "perplexity",
                "model": settings.audience_persona_generator_model,
                "company_slug": input_data.company_slug or "",
            },
        )
        end_span(span, output={"word_count": len(result_md.split()) if result_md else 0})

        return PersonaAgentResult(
            brief_id=brief.brief_id,
            persona_name=brief.persona_name,
            content_md=result_md,
            word_count=len(result_md.split()) if result_md else 0,
            execution_time_s=time.time() - start,
        )
    except asyncio.TimeoutError:
        end_span(span, error=f"Timeout: after {timeout_s}s")
        return PersonaAgentResult(
            brief_id=brief.brief_id,
            persona_name=brief.persona_name,
            error=f"Timeout: after {timeout_s}s",
            execution_time_s=time.time() - start,
        )
    except Exception as exc:
        end_span(span, error=f"APIError: {exc}")
        return PersonaAgentResult(
            brief_id=brief.brief_id,
            persona_name=brief.persona_name,
            error=str(exc),
            execution_time_s=time.time() - start,
        )
