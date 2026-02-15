"""Drafter worker — Step 2 of the worker chain.

Produces a full markdown draft from a content outline using Sonnet 4.5.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from anthropic import AsyncAnthropic

from core.config.settings import settings
from core.content_engine.prompts.drafter_prompts import (
    DRAFTER_SYSTEM_PROMPT,
    build_drafter_user_prompt,
)
from core.content_engine.tracing import create_span, end_span, log_generation
from core.content_engine.utils import _retry_async_anthropic, truncate_to_token_limit
from core.models.content_generation import ContentBrief, ContentDraft, ContentOutline

logger = logging.getLogger(__name__)

_MAX_INPUT_TOKENS = 100_000


async def generate_draft(
    outline: ContentOutline,
    brief: ContentBrief,
    style_guide_md: str,
    company_context_md: str,
    *,
    trace: Optional[object] = None,
) -> ContentDraft:
    """Generate a full markdown draft from an outline.

    Args:
        outline: Structured outline to follow.
        brief: Original content brief for context.
        style_guide_md: Company writing style guide.
        company_context_md: Company context markdown.
        trace: Langfuse trace for instrumentation.

    Returns:
        ContentDraft with full markdown and word count.
    """
    model = settings.content_engine_worker_model
    span = create_span(trace, "drafter", metadata={"brief_id": brief.brief_id})

    outline_json = json.dumps(outline.model_dump(mode="json"), indent=2)

    user_prompt = build_drafter_user_prompt(
        brief_id=brief.brief_id,
        title=brief.title,
        outline_json=outline_json,
        style_guide_md=style_guide_md,
        company_context_snippet=company_context_md,
        target_queries=[q.model_dump() for q in brief.target_queries],
    )

    user_prompt = truncate_to_token_limit(
        user_prompt, _MAX_INPUT_TOKENS, label="drafter_prompt"
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call():
        return await client.messages.create(
            model=model,
            max_tokens=8192,
            system=DRAFTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

    response = await _retry_async_anthropic(_call, max_retries=3, base_delay=2.0)

    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    # Clean up: remove code fences if the model wrapped output
    markdown = raw_text.strip()
    if markdown.startswith("```markdown"):
        markdown = markdown[len("```markdown") :].strip()
    if markdown.startswith("```"):
        markdown = markdown[3:].strip()
    if markdown.endswith("```"):
        markdown = markdown[:-3].strip()

    word_count = len(markdown.split())

    log_generation(
        trace,
        name="drafter",
        model=model,
        input_text=user_prompt[:1000],
        output_text=markdown[:1000],
        parent_span=span,
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    end_span(span, output=f"{word_count} words")

    logger.info("Drafter: %s → %d words", brief.brief_id, word_count)

    return ContentDraft(
        brief_id=brief.brief_id,
        title=brief.title,
        markdown=markdown,
        word_count=word_count,
    )


async def revise_draft(
    current_markdown: str,
    brief: ContentBrief,
    feedback: str,
    style_guide_md: str,
    company_context_md: str,
    *,
    trace: Optional[object] = None,
) -> ContentDraft:
    """Revise an existing draft based on evaluator feedback.

    Used during the evaluator-optimizer loop (Stage 3) when a dimension fails.

    Args:
        current_markdown: The current draft to revise.
        brief: Original content brief.
        feedback: Compiled feedback from failed evaluation dimensions.
        style_guide_md: Company writing style guide.
        company_context_md: Company context markdown.
        trace: Langfuse trace for instrumentation.

    Returns:
        Revised ContentDraft.
    """
    model = settings.content_engine_worker_model
    span = create_span(trace, "revision_drafter", metadata={"brief_id": brief.brief_id})

    user_prompt = f"""\
## Current Draft

{current_markdown}

## Evaluation Feedback (fix these issues)

{feedback}

## Target Queries
{chr(10).join(f'- "{q.query_text}"' for q in brief.target_queries)}

## Style Guide
{style_guide_md[:3000] if style_guide_md else 'Not provided.'}

Revise the draft to address ALL feedback issues. Maintain the existing structure
but improve content quality where flagged. Return the complete revised article
in Markdown.
"""

    user_prompt = truncate_to_token_limit(
        user_prompt, _MAX_INPUT_TOKENS, label="revision_prompt"
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call():
        return await client.messages.create(
            model=model,
            max_tokens=8192,
            system=DRAFTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

    response = await _retry_async_anthropic(_call, max_retries=3, base_delay=2.0)

    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    markdown = raw_text.strip()
    if markdown.startswith("```markdown"):
        markdown = markdown[len("```markdown") :].strip()
    if markdown.startswith("```"):
        markdown = markdown[3:].strip()
    if markdown.endswith("```"):
        markdown = markdown[:-3].strip()

    word_count = len(markdown.split())

    log_generation(
        trace,
        name="revision_drafter",
        model=model,
        input_text=user_prompt[:1000],
        output_text=markdown[:1000],
        parent_span=span,
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    end_span(span, output=f"Revised: {word_count} words")

    logger.info("Revision Drafter: %s → %d words", brief.brief_id, word_count)

    return ContentDraft(
        brief_id=brief.brief_id,
        title=brief.title,
        markdown=markdown,
        word_count=word_count,
    )
