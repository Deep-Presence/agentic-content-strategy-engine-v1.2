"""Competitor Registry Extraction — structured JSON from markdown (Pass 2).

Two public functions:

``extract_competitor_registry_json``
    Async.  Calls Claude Haiku via ``llm_call()`` to extract structured
    competitor data from the markdown produced by the competitor scanner
    agent.  Returns ``None`` on any failure — never raises.

``resolve_competitors_from_kb``
    Sync.  Reads the JSON sidecar from KB storage and returns a flat
    list of competitor names for the daily tracker's mention detector.
    Returns an empty list on any failure — never raises.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def extract_competitor_registry_json(
    content_md: str,
    company_name: str = "",
    model: str | None = None,
    parent_span: Any = None,
) -> Optional[Dict[str, Any]]:
    """Extract structured competitor data from markdown via LLM.

    Uses Claude Haiku through the unified ``llm_call()`` client (OpenRouter,
    retry, cost tracking).  Temperature 0.0 for deterministic extraction.

    Args:
        content_md: Full competitor registry markdown (Pass 1 output).
        company_name: Target company name (excluded from competitor list).
        model: Override model string.  Defaults to settings value.
        parent_span: Optional LangSmith parent span for tracing.

    Returns:
        Dict conforming to ``CompetitorRegistryStructured`` schema,
        or ``None`` on any failure.
    """
    if not content_md or len(content_md) < 100:
        logger.warning("Competitor extraction skipped — markdown too short (%d chars)", len(content_md))
        return None

    try:
        from core.config.settings import settings
        from core.content_engine.llm_client import llm_call
        from core.models.knowledge_base import CompetitorRegistryStructured
        from core.research.prompts.competitor_extractor import (
            build_competitor_extractor_user_prompt,
            get_competitor_extractor_system_prompt,
        )

        extraction_model = model or settings.research_kb_competitor_extractor_model

        system_prompt = get_competitor_extractor_system_prompt()
        user_prompt = build_competitor_extractor_user_prompt(content_md, company_name)

        response = await llm_call(
            model=extraction_model,
            system=system_prompt,
            user=user_prompt,
            max_tokens=4096,
            temperature=0.0,
            metadata={
                "pipeline": "knowledge_base",
                "pipeline_step": "competitor_extraction",
                "company_slug": company_name,
            },
        )

        # Log generation to LangSmith with full token/cost metadata
        from core.shared_tools.tracing import log_generation

        log_generation(
            parent_span,
            "competitor_extraction_llm",
            response.model or extraction_model,
            user_prompt[:2000],
            response.content[:2000],
            metadata={
                "pipeline": "knowledge_base",
                "pipeline_step": "competitor_extraction",
                "provider": "anthropic",
                "model": response.model or extraction_model,
                "company_slug": company_name,
            },
            usage={
                "prompt_tokens": response.input_tokens,
                "completion_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
            },
        )

        raw = response.content.strip()

        # Handle markdown fence wrapping (Claude sometimes adds ```json ... ```)
        if raw.startswith("```"):
            first_newline = raw.index("\n")
            last_fence = raw.rfind("```")
            if last_fence > first_newline:
                raw = raw[first_newline + 1 : last_fence].strip()

        data = json.loads(raw)

        # Validate against Pydantic model
        structured = CompetitorRegistryStructured.model_validate(data)

        # Stamp extraction metadata
        structured.extraction_model = response.model or extraction_model
        structured.extraction_timestamp = datetime.now(timezone.utc).isoformat()
        structured.total_competitor_count = len(structured.all_competitor_names())

        result = structured.model_dump(mode="json")

        logger.info(
            "Competitor extraction completed: %d competitors from %d chars "
            "(model=%s)",
            structured.total_competitor_count,
            len(content_md),
            structured.extraction_model,
        )
        return result

    except json.JSONDecodeError as exc:
        logger.warning("Competitor extraction JSON parse failed: %s", exc)
        return None
    except Exception:
        logger.warning("Competitor extraction failed", exc_info=True)
        return None


def resolve_competitors_from_kb(
    company_slug: str,
    storage_backend: Any,
) -> List[str]:
    """Read competitor names from the KB JSON sidecar.

    Sync function — callers in async context should wrap with
    ``asyncio.to_thread()``.

    Args:
        company_slug: Company slug for KB storage path.
        storage_backend: ``StorageBackend`` instance (local or R2).

    Returns:
        List of competitor name strings, or empty list on any failure.
    """
    try:
        from core.models.knowledge_base import (
            CompetitorRegistryStructured,
            KBDocType,
        )
        from core.research.knowledge_base.storage import KBStorage

        kb_storage = KBStorage(company_slug, storage_backend)
        version = kb_storage.get_latest_version(KBDocType.COMPETITOR_REGISTRY)

        if version is None:
            logger.debug("No competitor registry found for %s", company_slug)
            return []

        if version.content_json is None:
            logger.debug(
                "Competitor registry for %s has no JSON sidecar (pre-extraction)",
                company_slug,
            )
            return []

        structured = CompetitorRegistryStructured.model_validate(version.content_json)
        names = structured.all_competitor_names()

        logger.debug(
            "Resolved %d competitors from KB for %s: %s",
            len(names),
            company_slug,
            ", ".join(names[:5]),
        )
        return names

    except Exception:
        logger.warning(
            "Failed to resolve competitors from KB for %s",
            company_slug,
            exc_info=True,
        )
        return []
