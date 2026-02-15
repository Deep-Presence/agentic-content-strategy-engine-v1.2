"""Formatter worker — Step 4 of the worker chain.

Uses Haiku 4.5 for fast, lightweight formatting and polishing.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from anthropic import AsyncAnthropic

from core.config.settings import settings
from core.content_engine.prompts.formatter_prompts import (
    FORMATTER_SYSTEM_PROMPT,
    build_formatter_user_prompt,
)
from core.content_engine.tracing import create_span, end_span, log_generation
from core.content_engine.utils import _retry_async_anthropic
from core.models.content_generation import EnrichedDraft, FormattedContent

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
    trace: Optional[object] = None,
) -> FormattedContent:
    """Format and polish enriched content using Haiku 4.5.

    Args:
        enriched: Enriched draft to format.
        style_guide_md: Company writing style guide.
        trace: Langfuse trace for instrumentation.

    Returns:
        FormattedContent with polished markdown and structural counts.
    """
    model = settings.content_engine_formatter_model
    span = create_span(trace, "formatter", metadata={"brief_id": enriched.brief_id})

    user_prompt = build_formatter_user_prompt(
        enriched_markdown=enriched.markdown,
        style_guide_md=style_guide_md,
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call():
        return await client.messages.create(
            model=model,
            max_tokens=8192,
            system=FORMATTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

    response = await _retry_async_anthropic(_call, max_retries=3)

    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

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
        trace,
        name="formatter",
        model=model,
        input_text=user_prompt[:1000],
        output_text=markdown[:1000],
        parent_span=span,
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    end_span(
        span,
        output=(
            f"{word_count} words, {counts['header_count']} headers, "
            f"{counts['citation_count']} citations"
        ),
    )

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
