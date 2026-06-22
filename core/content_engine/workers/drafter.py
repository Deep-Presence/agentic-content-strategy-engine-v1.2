
"""Drafter worker — Step 2 of the worker chain.

Produces a full markdown draft from a content outline using Sonnet 4.5.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from core.config.settings import settings
from core.content_engine.llm_client import llm_call, llm_call_for_agent
from core.content_engine.prompts.drafter_prompts import (
    DRAFTER_SYSTEM_PROMPT,
    REVISION_SYSTEM_PROMPT,
    build_drafter_user_prompt,
)
from core.content_engine.tracing_v13 import create_span, end_span, extract_provider, log_generation
from core.content_engine.utils import truncate_to_token_limit
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
    company_slug: str = "",
    workspace_id: str = "",
) -> ContentDraft:
    """Generate a full markdown draft from an outline.

    Args:
        outline: Structured outline to follow.
        brief: Original content brief for context.
        style_guide_md: Company writing style guide.
        company_context_md: Company context markdown.
        trace: Trace span for instrumentation.

    Returns:
        ContentDraft with full markdown and word count.
    """
    model = settings.content_engine_worker_model
    span = create_span(
        trace, "drafter",
        metadata={"brief_id": brief.brief_id, "model": model},
        input={
            "brief_id": brief.brief_id,
            "title": brief.title,
            "outline_sections": len(outline.sections),
        },
    )

    outline_json = json.dumps(outline.model_dump(mode="json"), indent=2)

    user_prompt = build_drafter_user_prompt(
        brief_id=brief.brief_id,
        title=brief.title,
        outline_json=outline_json,
        style_guide_md=style_guide_md,
        company_context_snippet=company_context_md,
        target_queries=[q.model_dump() for q in brief.target_queries],
        structural_targets=brief.structural_targets.model_dump(),
        exemplar_summaries=[e.model_dump() for e in brief.exemplar_summaries],
        exemplar_themes=brief.exemplar_themes,
        word_count_range=brief.word_count_range,
        voice_tone_description=getattr(outline, "voice_tone_description", ""),
    )

    user_prompt = truncate_to_token_limit(
        user_prompt, _MAX_INPUT_TOKENS, label="drafter_prompt"
    )

    try:
        metadata = {
            "agent": "drafter",
            "agent_key": "content.worker.drafter",
            "brief_id": brief.brief_id,
            "pipeline": "content_engine",
            "pipeline_step": "drafter",
            "provider": extract_provider(model),
            "model": model,
            "company_slug": company_slug,
        }
        if workspace_id:
            response = await llm_call_for_agent(
                workspace_id=workspace_id,
                workspace_slug=company_slug,
                agent_key="content.worker.drafter",
                system=DRAFTER_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=8192,
                metadata=metadata,
                base_delay=2.0,
            )
        else:
            response = await llm_call(
                model=model,
                system=DRAFTER_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=8192,
                metadata=metadata,
                base_delay=2.0,
            )

        raw_text = response.content

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
            span,
            name="drafter",
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
        end_span(span, output={"word_count": word_count, "brief_id": brief.brief_id})

        logger.info("Drafter: %s → %d words", brief.brief_id, word_count)

        return ContentDraft(
            brief_id=brief.brief_id,
            title=brief.title,
            markdown=markdown,
            word_count=word_count,
        )
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        raise


async def revise_draft(
    current_markdown: str,
    brief: ContentBrief,
    feedback: str,
    style_guide_md: str,
    company_context_md: str,
    *,
    trace: Optional[object] = None,
    company_slug: str = "",
    workspace_id: str = "",
) -> ContentDraft:
    """Revise an existing draft based on evaluator feedback.

    Used during the evaluator-optimizer loop (Stage 3) when a dimension fails.

    Args:
        current_markdown: The current draft to revise.
        brief: Original content brief.
        feedback: Compiled feedback from failed evaluation dimensions.
        style_guide_md: Company writing style guide.
        company_context_md: Company context markdown.
        trace: Trace span for instrumentation.

    Returns:
        Revised ContentDraft.
    """
    model = settings.content_engine_worker_model
    span = create_span(
        trace, "revision_drafter",
        metadata={"brief_id": brief.brief_id, "model": model},
        input={
            "brief_id": brief.brief_id,
            "feedback_length": len(feedback),
            "current_word_count": len(current_markdown.split()),
        },
    )

    # Build structural targets section for revision
    st = brief.structural_targets.model_dump()
    wc_range = brief.word_count_range
    structural_section = f"""\
## Structural Blueprint (must be met after revision)

**Word count target: {wc_range[0]}-{wc_range[1]} words**
- Min headers: {st.get('min_headers', 3)}
- Min lists: {st.get('min_lists', 1)}
- Min citations: {st.get('min_citations', 2)}
- Min stats: {st.get('min_stats', 2)}
- Min paragraphs: {st.get('min_paragraphs', 8)}
- Target paragraph length: {st.get('avg_paragraph_word_count', 80)} words avg
- Min self-contained claims: {st.get('min_self_contained_claims', 5)}"""

    user_prompt = f"""\
## Current Draft

{current_markdown}

## Evaluation Feedback (fix these issues)

{feedback}

{structural_section}

## Target Queries
{chr(10).join(f'- "{q.query_text}"' for q in brief.target_queries)}

## Style Guide
{style_guide_md if style_guide_md else 'Not provided.'}

Revise the draft to address ALL feedback issues. You CAN add new sections (FAQ, \
tables, key takeaways) if the feedback requires it. Never shrink below the word \
count target. Return the complete revised article in Markdown.
"""

    user_prompt = truncate_to_token_limit(
        user_prompt, _MAX_INPUT_TOKENS, label="revision_prompt"
    )

    try:
        metadata = {
            "agent": "revision_drafter",
            "agent_key": "content.worker.reviser",
            "brief_id": brief.brief_id,
            "pipeline": "content_engine",
            "pipeline_step": "revision_drafter",
            "provider": extract_provider(model),
            "model": model,
            "company_slug": company_slug,
        }
        if workspace_id:
            response = await llm_call_for_agent(
                workspace_id=workspace_id,
                workspace_slug=company_slug,
                agent_key="content.worker.reviser",
                system=REVISION_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=8192,
                metadata=metadata,
                base_delay=2.0,
            )
        else:
            response = await llm_call(
                model=model,
                system=REVISION_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=8192,
                metadata=metadata,
                base_delay=2.0,
            )

        raw_text = response.content

        markdown = raw_text.strip()
        if markdown.startswith("```markdown"):
            markdown = markdown[len("```markdown") :].strip()
        if markdown.startswith("```"):
            markdown = markdown[3:].strip()
        if markdown.endswith("```"):
            markdown = markdown[:-3].strip()

        word_count = len(markdown.split())

        log_generation(
            span,
            name="revision_drafter",
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
        end_span(span, output={"word_count": word_count, "revised": True})

        logger.info("Revision Drafter: %s → %d words", brief.brief_id, word_count)

        return ContentDraft(
            brief_id=brief.brief_id,
            title=brief.title,
            markdown=markdown,
            word_count=word_count,
        )
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        raise
