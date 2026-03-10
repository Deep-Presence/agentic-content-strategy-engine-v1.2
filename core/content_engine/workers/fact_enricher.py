"""Fact Enricher worker — Step 3 of the worker chain.

Uses Perplexity sonar-pro for web-grounded fact verification and enrichment.
All LLM calls route through LiteLLM via llm_client.llm_call().
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from core.config.settings import settings
from core.content_engine.llm_client import llm_call
from core.content_engine.prompts.enricher_prompts import (
    ENRICHER_SYSTEM_PROMPT,
    build_enricher_user_prompt,
)
from core.content_engine.tracing_v13 import create_span, end_span, log_generation
from core.content_engine.utils import truncate_to_token_limit
from core.models.content_generation import ContentBrief, ContentDraft, EnrichedDraft

logger = logging.getLogger(__name__)


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
        trace: Trace span for instrumentation.

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
    # Truncate to sonar-pro context budget (127k tokens); leave headroom for system + response
    user_prompt = truncate_to_token_limit(
        user_prompt, max_tokens=120_000, label="fact_enricher_user"
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

    try:
        response = await llm_call(
            model=model,
            system=ENRICHER_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=8192,
            metadata={"agent": "fact_enricher", "brief_id": brief.brief_id},
            max_retries=2,
            base_delay=3.0,
        )

        enriched_text = response.content

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

        log_generation(
            span,
            name="fact_enricher",
            model=model,
            input_text=user_prompt,
            output_text=enriched_text,
            model_parameters={"max_tokens": 8192},
            usage={
                "prompt_tokens": response.input_tokens,
                "completion_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
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
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        raise
