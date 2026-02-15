"""Worker dispatcher — parallel content production via semaphore-controlled concurrency.

Dispatches the 4-step worker chain per brief:
  Brief → Outliner (Sonnet) → Drafter (Sonnet) → Fact Enricher (Perplexity) → Formatter (Haiku)

Uses asyncio.Semaphore for concurrency control (same pattern as s3_search_platforms.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from core.config.settings import settings
from core.content_engine.pipeline import _brief_dir, _cli_worker_progress
from core.content_engine.tracing import create_trace, log_score
from core.content_engine.workers.drafter import generate_draft
from core.content_engine.workers.fact_enricher import enrich_with_facts
from core.content_engine.workers.formatter import format_content
from core.content_engine.workers.outliner import generate_outline
from core.models.content_generation import (
    ContentBrief,
    ContentGenerationInput,
    FormattedContent,
)

logger = logging.getLogger(__name__)


async def _run_worker_chain(
    brief: ContentBrief,
    worker_num: int,
    input_data: ContentGenerationInput,
    style_guide_md: str,
    company_context_md: str,
    session_id: str,
    artifact_dir: Path,
    semaphore: asyncio.Semaphore,
) -> FormattedContent:
    """Run the full 4-step worker chain for a single brief.

    Args:
        brief: Content brief to process.
        worker_num: Worker number for CLI display.
        input_data: Pipeline input for company details.
        style_guide_md: Company style guide.
        company_context_md: Company context.
        session_id: Langfuse session ID.
        artifact_dir: Root artifact directory.
        semaphore: Concurrency limiter.

    Returns:
        FormattedContent for this brief.
    """
    async with semaphore:
        trace = create_trace(
            session_id,
            f"worker/{brief.brief_id}",
            metadata={"brief_id": brief.brief_id, "worker_num": worker_num},
        )
        bdir = _brief_dir(artifact_dir, brief.brief_id)
        title_short = brief.title[:50] + ("..." if len(brief.title) > 50 else "")

        # Step 1: Outline
        _cli_worker_progress(f"Worker #{worker_num}: Outlining \"{title_short}\"")
        outline = await generate_outline(
            brief=brief,
            company_context_md=company_context_md,
            trace=trace,
        )
        (bdir / "outline.json").write_text(
            json.dumps(outline.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )

        # Step 2: Draft
        _cli_worker_progress(f"Worker #{worker_num}: Drafting \"{title_short}\"")
        draft = await generate_draft(
            outline=outline,
            brief=brief,
            style_guide_md=style_guide_md,
            company_context_md=company_context_md,
            trace=trace,
        )
        (bdir / "draft.md").write_text(draft.markdown, encoding="utf-8")

        # Step 3: Fact Enrichment
        _cli_worker_progress(f"Worker #{worker_num}: Enriching \"{title_short}\"")
        enriched = await enrich_with_facts(
            draft=draft,
            brief=brief,
            company_name=input_data.company_name,
            domain=input_data.domain,
            trace=trace,
        )
        (bdir / "enriched.md").write_text(enriched.markdown, encoding="utf-8")

        # Step 4: Format
        _cli_worker_progress(f"Worker #{worker_num}: Formatting \"{title_short}\"")
        formatted = await format_content(
            enriched=enriched,
            style_guide_md=style_guide_md,
            trace=trace,
        )
        (bdir / "formatted.md").write_text(formatted.markdown, encoding="utf-8")

        _cli_worker_progress(
            f"Worker #{worker_num}: DONE ({formatted.word_count:,} words, "
            f"{formatted.header_count} headers, {formatted.citation_count} citations)"
        )

        log_score(trace, "word_count", formatted.word_count)
        log_score(trace, "header_count", formatted.header_count)
        log_score(trace, "citation_count", formatted.citation_count)

        return formatted


async def dispatch_workers(
    briefs: List[ContentBrief],
    input_data: ContentGenerationInput,
    style_guide_md: str,
    company_context_md: str,
    max_concurrent: int = 3,
    *,
    session_id: str = "",
    artifact_dir: Path = Path("."),
) -> List[FormattedContent]:
    """Dispatch worker chains in parallel with concurrency control.

    Uses asyncio.Semaphore + asyncio.gather(return_exceptions=True)
    so one failing worker doesn't cancel the batch.

    Args:
        briefs: Content briefs to process.
        input_data: Pipeline input for company details.
        style_guide_md: Company style guide.
        company_context_md: Company context.
        max_concurrent: Max concurrent workers.
        session_id: Langfuse session ID.
        artifact_dir: Root artifact directory.

    Returns:
        List of FormattedContent (one per successful brief).
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    tasks = [
        _run_worker_chain(
            brief=brief,
            worker_num=i + 1,
            input_data=input_data,
            style_guide_md=style_guide_md,
            company_context_md=company_context_md,
            session_id=session_id,
            artifact_dir=artifact_dir,
            semaphore=semaphore,
        )
        for i, brief in enumerate(briefs)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Separate successes from errors
    formatted_contents: List[FormattedContent] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                "Worker for brief '%s' failed: %s",
                briefs[i].brief_id,
                result,
            )
            _cli_worker_progress(
                f"Worker #{i + 1}: FAILED — {type(result).__name__}: {result}"
            )
        else:
            formatted_contents.append(result)

    _cli_worker_progress(
        f"Workers complete: {len(formatted_contents)}/{len(briefs)} briefs"
    )

    return formatted_contents
