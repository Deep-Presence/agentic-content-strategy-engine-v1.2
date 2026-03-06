"""Formatter worker — Step 4 of the worker chain.

Uses Haiku 4.5 for fast, lightweight formatting and polishing.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core.config.settings import settings
from core.content_engine.llm_client import llm_call
from core.content_engine.prompts.formatter_prompts import (
    FORMATTER_SYSTEM_PROMPT,
    build_formatter_user_prompt,
)
from core.content_engine.tracing_v13 import create_span, end_span, log_generation
from core.content_engine.utils import truncate_to_token_limit
from core.models.content_generation import ContentBrief, EnrichedDraft, FormattedContent

logger = logging.getLogger(__name__)


def _count_structural_elements(markdown: str) -> dict:
    """Count structural elements in markdown content."""
    lines = markdown.split("\n")

    header_count = sum(1 for line in lines if re.match(r"^#{1,6}\s", line))
    list_count = sum(
        1 for line in lines if re.match(r"^\s*[-*+]\s", line) or re.match(r"^\s*\d+\.\s", line)
    )
    # Stats: lines containing numbers with % or $ or digits with context
    stat_count = sum(
        1 for line in lines if re.search(r"\d+(\.\d+)?[%$]|\$\d+|[\d,]+\s*(million|billion|percent)", line, re.IGNORECASE)
    )
    # Citations: [Source, Year] or [URL] patterns
    citation_count = len(re.findall(r"\[[^\]]+?,\s*\d{4}\]|\[https?://[^\]]+\]", markdown))

    return {
        "header_count": header_count,
        "list_count": list_count,
        "stat_count": stat_count,
        "citation_count": citation_count,
    }


async def format_content(
    enriched: EnrichedDraft,
    style_guide_md: str,
    *,
    brief: Optional[ContentBrief] = None,
    trace: Optional[object] = None,
) -> FormattedContent:
    """Format and polish enriched content using Haiku 4.5.

    Args:
        enriched: Enriched draft to format.
        style_guide_md: Company writing style guide.
        brief: Optional content brief for structural targets.
        trace: Trace span for instrumentation.

    Returns:
        FormattedContent with polished markdown and structural counts.
    """
    model = settings.content_engine_formatter_model
    span = create_span(
        trace, "formatter",
        metadata={"brief_id": enriched.brief_id, "model": model},
        input={
            "brief_id": enriched.brief_id,
            "title": enriched.title,
            "input_word_count": enriched.word_count,
        },
    )

    user_prompt = build_formatter_user_prompt(
        enriched_markdown=enriched.markdown,
        style_guide_md=style_guide_md,
        structural_targets=brief.structural_targets.model_dump() if brief else None,
    )

    user_prompt = truncate_to_token_limit(
        user_prompt, 150_000, label="formatter_prompt"
    )

    try:
        response = await llm_call(
            model=model,
            system=FORMATTER_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=8192,
            metadata={"agent": "formatter", "brief_id": enriched.brief_id},
        )

        raw_text = response.content

        # Clean up code fences
        markdown = raw_text.strip()
        if markdown.startswith("```markdown"):
            markdown = markdown[len("```markdown") :].strip()
        if markdown.startswith("```"):
            markdown = markdown[3:].strip()
        if markdown.endswith("```"):
            markdown = markdown[:-3].strip()

        word_count = len(markdown.split())
        counts = _count_structural_elements(markdown)

        log_generation(
            span,
            name="formatter",
            model=model,
            input_text=user_prompt,
            output_text=markdown,
            model_parameters={"max_tokens": 8192},
            usage={
                "prompt_tokens": response.input_tokens,
                "completion_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
            },
        )
        end_span(span, output={
            "word_count": word_count,
            "header_count": counts["header_count"],
            "list_count": counts["list_count"],
            "stat_count": counts["stat_count"],
            "citation_count": counts["citation_count"],
        })

        logger.info(
            "Formatter: %s → %d words, %d headers, %d citations",
            enriched.brief_id,
            word_count,
            counts["header_count"],
            counts["citation_count"],
        )

        return FormattedContent(
            brief_id=enriched.brief_id,
            title=enriched.title,
            markdown=markdown,
            word_count=word_count,
            **counts,
        )
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        raise
