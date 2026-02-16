"""Fact Enricher worker — Step 3 of the worker chain.

Uses Perplexity sonar-pro for web-grounded fact verification and enrichment.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

import httpx

from core.config.settings import settings
from core.content_engine.prompts.enricher_prompts import (
    ENRICHER_SYSTEM_PROMPT,
    build_enricher_user_prompt,
)
from core.content_engine.tracing import create_span, end_span, log_generation
from core.content_engine.utils import _retry_async_anthropic
from core.models.content_generation import ContentBrief, ContentDraft, EnrichedDraft

logger = logging.getLogger(__name__)

_PERPLEXITY_BASE_URL = "https://api.perplexity.ai"


async def enrich_with_facts(
    draft: ContentDraft,
    brief: ContentBrief,
    company_name: str,
    domain: str,
    *,
    trace: Optional[object] = None,
) -> EnrichedDraft:
    """Enrich a draft with verified facts using Perplexity sonar-pro.

    Args:
        draft: The raw content draft.
        brief: Original content brief for context.
        company_name: Company name for search context.
        domain: Company domain.
        trace: Langfuse trace for instrumentation.

    Returns:
        EnrichedDraft with fact-checked and enriched content.
    """
    model = settings.content_engine_fact_enricher_model
    span = create_span(
        trace, "fact_enricher",
        metadata={"brief_id": brief.brief_id, "model": model},
        input={
            "brief_id": brief.brief_id,
            "title": brief.title,
            "company_name": company_name,
            "domain": domain,
            "draft_word_count": draft.word_count,
        },
    )

    user_prompt = build_enricher_user_prompt(
        draft_markdown=draft.markdown,
        title=brief.title,
        key_topics=brief.key_topics,
        company_name=company_name,
        domain=domain,
    )

    api_key = settings.perplexity_api_key
    if not api_key:
        logger.warning("PERPLEXITY_API_KEY not set — skipping fact enrichment")
        end_span(span, output="Skipped: no API key")
        return EnrichedDraft(
            brief_id=draft.brief_id,
            title=draft.title,
            markdown=draft.markdown,
            word_count=draft.word_count,
            facts_added=[],
        )

    async def _call():
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{_PERPLEXITY_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": ENRICHER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 8192,
                },
            )
            response.raise_for_status()
            return response.json()

    result = await _retry_async_anthropic(_call, max_retries=2, base_delay=3.0)

    enriched_text = ""
    try:
        enriched_text = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        logger.warning("Unexpected Perplexity response format: %s", result)
        enriched_text = draft.markdown

    # Clean up code fences
    if enriched_text.startswith("```markdown"):
        enriched_text = enriched_text[len("```markdown") :].strip()
    if enriched_text.startswith("```"):
        enriched_text = enriched_text[3:].strip()
    if enriched_text.endswith("```"):
        enriched_text = enriched_text[:-3].strip()

    # Detect added facts (citations in [Source, Year] format)
    citations_found = re.findall(r"\[([^\]]+?,\s*\d{4})\]", enriched_text)
    facts_added: List[Dict[str, str]] = [
        {"citation": c} for c in citations_found
    ]

    word_count = len(enriched_text.split())

    # Langfuse logging
    usage_info = result.get("usage", {})
    log_generation(
        trace,
        name="fact_enricher",
        model=model,
        input_text=user_prompt,
        output_text=enriched_text,
        parent_span=span,
        model_parameters={"max_tokens": 8192},
        usage={
            "input": usage_info.get("prompt_tokens", 0),
            "output": usage_info.get("completion_tokens", 0),
        },
    )
    end_span(span, output={
        "facts_added": len(facts_added),
        "word_count": word_count,
    })

    logger.info(
        "Fact Enricher: %s → %d facts added, %d words",
        brief.brief_id,
        len(facts_added),
        word_count,
    )

    return EnrichedDraft(
        brief_id=draft.brief_id,
        title=draft.title,
        markdown=enriched_text,
        word_count=word_count,
        facts_added=facts_added,
    )
