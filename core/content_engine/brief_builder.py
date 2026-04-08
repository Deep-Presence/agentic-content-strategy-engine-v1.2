"""Brief Builder (Agent 2) for the v1.3 content pipeline.

The content architect agent. For each approved topic, it receives full gap
analysis detail (exemplar structural signals, content briefs, cluster specs)
and produces a detailed ContentBlueprint.

ContentBlueprint extends ContentBrief, so it is accepted anywhere ContentBrief
is expected — workers, evaluators, and persistence hooks all work transparently.

Key difference from v1.0: Agent 2 has access to the FULL exemplar intelligence
for its specific queries (not a truncated summary of all 200 queries), enabling
much richer and more structurally precise briefs.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from core.config.settings import settings
from core.content_engine.context_router import format_worker_context_as_markdown
from core.content_engine.llm_client import llm_call
from core.content_engine.prompts.brief_builder_prompts import (
    BRIEF_BUILDER_SYSTEM_PROMPT,
    build_brief_builder_user_prompt,
)
from core.content_engine.tracing_v13 import create_span, end_span, extract_provider, log_generation
from core.content_engine.utils import safe_parse, truncate_to_token_limit
from core.models.content_generation_v13 import (
    ContentBlueprint,
    TopicSelection,
    WorkerQueryContext,
)

logger = logging.getLogger(__name__)


async def build_brief(
    context: WorkerQueryContext,
    topic_selection: TopicSelection,
    *,
    company_context_md: str = "",
    persona_mds: Optional[List[str]] = None,
    style_guide_md: str = "",
    brief_id: str = "brief-001",
    parent_span: Optional[Any] = None,
    company_slug: str = "",
) -> ContentBlueprint:
    """Build a detailed content blueprint from full query context.

    Args:
        context: Full WorkerQueryContext for the approved query.
        topic_selection: The TopicSelection from Agent 1 with rationale.
        company_context_md: Full company context markdown.
        persona_mds: Persona profile markdowns.
        style_guide_md: Style guide (summary used for format choice).
        brief_id: Unique brief identifier.
        parent_span: Optional LangSmith parent span.

    Returns:
        ContentBlueprint ready for downstream workers.
    """
    span = create_span(parent_span, f"brief-builder/{brief_id}")

    # Format full context as markdown
    context_md = format_worker_context_as_markdown(context)

    # Build user prompt
    user_prompt = build_brief_builder_user_prompt(
        worker_context_md=context_md,
        company_context_md=company_context_md,
        persona_mds=persona_mds,
        style_guide_summary=style_guide_md if style_guide_md else "",
        topic_rationale=topic_selection.rationale,
        topic_query_ids=topic_selection.query_ids,
        topic_query_texts=topic_selection.query_texts,
        brief_id=brief_id,
    )

    # Truncate to 150K tokens (Sonnet 4.5 has 200K window)
    user_prompt = truncate_to_token_limit(
        user_prompt, max_tokens=150_000, label="brief_builder_user"
    )

    model = settings.content_engine_v13_brief_builder_model

    logger.info(
        "Building brief %s for %d queries in cluster '%s'",
        brief_id,
        len(topic_selection.query_ids),
        topic_selection.cluster_name,
    )

    # Call LLM via LiteLLM — retry up to 2 times on JSON parse failure
    _MAX_PARSE_RETRIES = 2
    blueprint: ContentBlueprint | None = None
    last_parse_error: Exception | None = None

    for parse_attempt in range(_MAX_PARSE_RETRIES + 1):
        response = await llm_call(
            model=model,
            system=BRIEF_BUILDER_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=8192,
            temperature=0.0 if parse_attempt == 0 else 0.1,
            response_format={"type": "json_object"},
            metadata={
                "agent": "brief_builder",
                "brief_id": brief_id,
                "cluster": topic_selection.cluster_name,
                "parse_attempt": parse_attempt,
                "pipeline": "content_engine",
                "pipeline_step": "brief_builder",
                "provider": extract_provider(model),
                "model": model,
                "company_slug": company_slug,
            },
        )

        try:
            blueprint = safe_parse(response.content, ContentBlueprint)
            if parse_attempt > 0:
                logger.info(
                    "Brief %s parsed successfully on retry %d/%d",
                    brief_id, parse_attempt, _MAX_PARSE_RETRIES,
                )
            break
        except ValueError as exc:
            last_parse_error = exc
            if parse_attempt < _MAX_PARSE_RETRIES:
                logger.warning(
                    "Brief %s JSON parse failed (attempt %d/%d), retrying LLM call: %s",
                    brief_id, parse_attempt + 1, _MAX_PARSE_RETRIES + 1, str(exc)[:200],
                )
            else:
                raise

    assert blueprint is not None  # guaranteed by loop logic: either set or raised

    # Ensure brief_id is set correctly
    blueprint.brief_id = brief_id

    # Attach the gap context for downstream reference
    blueprint.gap_context = context

    # Log to LangSmith
    log_generation(
        parent=span,
        name="build_brief",
        model=model,
        input_text=user_prompt[:3000],
        output_text=response.content[:3000],
        usage={
            "prompt_tokens": response.input_tokens,
            "completion_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
        },
    )

    logger.info(
        "Built blueprint %s: %d sections, format=%s, word_range=%s",
        brief_id,
        len(blueprint.sections),
        blueprint.content_format,
        blueprint.word_count_range,
    )

    end_span(span, output={"brief_id": brief_id, "sections": len(blueprint.sections)})
    return blueprint


async def build_briefs_parallel(
    contexts: Dict[str, WorkerQueryContext],
    topics: List[TopicSelection],
    *,
    company_context_md: str = "",
    persona_mds: Optional[List[str]] = None,
    style_guide_md: str = "",
    max_concurrent: int = 3,
    parent_span: Optional[Any] = None,
    brief_id_overrides: Optional[List[str]] = None,
    company_slug: str = "",
) -> List[ContentBlueprint]:
    """Build briefs for multiple topics in parallel using semaphore control.

    Each topic gets its own Brief Builder instance running concurrently.
    Follows the same asyncio.Semaphore pattern as the existing
    workers/dispatcher.py.

    Args:
        contexts: Dict of query_id → WorkerQueryContext.
        topics: List of approved TopicSelection from Agent 1.
        company_context_md: Full company context markdown.
        persona_mds: Persona profile markdowns.
        style_guide_md: Style guide markdown.
        max_concurrent: Maximum concurrent brief builds (default 3).
        parent_span: Optional LangSmith parent span.
        brief_id_overrides: Optional list of explicit brief IDs to use instead of
            the default "brief-{N:03d}" numbering. Index-aligned with topics.
            If shorter than topics, remaining topics get default IDs.
            Use for re-briefs to prevent collision with original brief-001.

    Returns:
        List of ContentBlueprint, one per topic.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    span = create_span(parent_span, "brief-builder-parallel")

    async def _build_with_semaphore(
        topic: TopicSelection,
        idx: int,
    ) -> Optional[ContentBlueprint]:
        async with semaphore:
            brief_id = (
                brief_id_overrides[idx]
                if brief_id_overrides and idx < len(brief_id_overrides)
                else f"brief-{idx + 1:03d}"
            )

            # Get context for the first query in the topic
            # Why: Each topic may consolidate multiple queries. We use
            # the first query's full context as the primary input.
            primary_query_id = topic.query_ids[0] if topic.query_ids else ""
            context = contexts.get(primary_query_id)

            if context is None:
                logger.warning(
                    "No context found for topic rank=%d, query_id=%s",
                    topic.rank,
                    primary_query_id,
                )
                return None

            try:
                return await build_brief(
                    context=context,
                    topic_selection=topic,
                    company_context_md=company_context_md,
                    persona_mds=persona_mds,
                    style_guide_md=style_guide_md,
                    brief_id=brief_id,
                    parent_span=span,
                    company_slug=company_slug,
                )
            except Exception as exc:
                logger.error(
                    "Failed to build brief %s: %s", brief_id, exc, exc_info=True
                )
                return None

    tasks = [
        asyncio.create_task(_build_with_semaphore(topic, i))
        for i, topic in enumerate(topics)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Preserve positional alignment: return List[Optional[ContentBlueprint]]
    # so callers can zip results with their input lists by index.
    # None entries indicate failed topics (missing context or LLM error).
    blueprints: list = list(results)

    logger.info(
        "Built %d/%d blueprints in parallel (max_concurrent=%d)",
        sum(1 for bp in blueprints if bp is not None),
        len(topics),
        max_concurrent,
    )

    end_span(span, output={"blueprints_built": len(blueprints)})
    return blueprints
