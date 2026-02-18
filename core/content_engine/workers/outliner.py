"""Outliner worker — Step 1 of the worker chain.

Produces a structured content outline from a content brief using Sonnet 4.5.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from core.config.settings import settings
from core.content_engine.prompts.outliner_prompts import (
    OUTLINER_SYSTEM_PROMPT,
    build_outliner_user_prompt,
)
from core.content_engine.tracing import create_span, end_span, log_generation
from core.content_engine.utils import _retry_async_anthropic, safe_parse, truncate_to_token_limit
from core.models.content_generation import ContentBrief, ContentOutline

logger = logging.getLogger(__name__)


async def generate_outline(
    brief: ContentBrief,
    company_context_md: str,
    *,
    trace: Optional[object] = None,
) -> ContentOutline:
    """Generate a structured outline from a content brief.

    Args:
        brief: The content brief to outline.
        company_context_md: Company context for grounding.
        trace: Langfuse trace for instrumentation.

    Returns:
        ContentOutline with sections and word count targets.
    """
    model = settings.content_engine_worker_model
    span = create_span(
        trace, "outliner",
        metadata={"brief_id": brief.brief_id, "model": model},
        input={
            "brief_id": brief.brief_id,
            "title": brief.title,
            "content_format": brief.content_format,
            "word_count_range": list(brief.word_count_range),
        },
    )

    user_prompt = build_outliner_user_prompt(
        brief_id=brief.brief_id,
        title=brief.title,
        target_queries=[q.model_dump() for q in brief.target_queries],
        content_format=brief.content_format,
        funnel_stage=brief.funnel_stage,
        word_count_range=brief.word_count_range,
        key_topics=brief.key_topics,
        key_angles=brief.key_angles,
        structural_targets=brief.structural_targets.model_dump(),
        company_context_snippet=company_context_md,
        exemplar_summaries=[e.model_dump() for e in brief.exemplar_summaries],
        exemplar_themes=brief.exemplar_themes,
    )

    user_prompt = truncate_to_token_limit(
        user_prompt, 150_000, label="outliner_prompt"
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call():
        return await client.messages.create(
            model=model,
            max_tokens=4096,
            system=OUTLINER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

    response = await _retry_async_anthropic(_call, max_retries=3)

    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    outline = safe_parse(raw_text, ContentOutline)

    # Ensure brief_id is set correctly
    outline.brief_id = brief.brief_id

    log_generation(
        trace,
        name="outliner",
        model=model,
        input_text=user_prompt,
        output_text=raw_text,
        parent_span=span,
        model_parameters={"max_tokens": 4096},
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    end_span(span, output={
        "sections": len(outline.sections),
        "total_target_words": outline.total_target_words,
        "section_headings": [s.heading for s in outline.sections],
    })

    logger.info(
        "Outliner: %s → %d sections, %d target words",
        brief.brief_id,
        len(outline.sections),
        outline.total_target_words,
    )

    return outline
