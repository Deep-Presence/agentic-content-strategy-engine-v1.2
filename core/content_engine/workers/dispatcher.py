"""Worker dispatcher — parallel content production via semaphore-controlled concurrency.

v1.0 chain (dispatch_workers):
  Brief → Outliner (Sonnet) → Drafter (Sonnet) → Fact Enricher (Perplexity) → Formatter (Haiku)

v1.3 chain (dispatch_workers_v13):
  Brief → Outliner (Sonnet) → Drafter (Sonnet) → Linker (Perplexity) → Fact Checker (Perplexity)

Uses asyncio.Semaphore for concurrency control (same pattern as s3_search_platforms.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid as _uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config.settings import settings
from core.content_engine.pipeline import _brief_dir, _cli_worker_progress
from core.content_engine.state_helpers import _emit, _write_pipeline_state, _write_pipeline_state_async
from core.content_engine.tracing_v13 import create_span, create_trace, end_span, log_score, update_trace_output
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
    parent_span: Optional[object] = None,
) -> FormattedContent:
    """Run the full 4-step worker chain for a single brief.

    Args:
        brief: Content brief to process.
        worker_num: Worker number for CLI display.
        input_data: Pipeline input for company details.
        style_guide_md: Company style guide.
        company_context_md: Company context.
        session_id: Session ID.
        artifact_dir: Root artifact directory.
        semaphore: Concurrency limiter.

    Returns:
        FormattedContent for this brief.
    """
    async with semaphore:
        title_short = brief.title[:60]
        trace_name = f"Worker #{worker_num}: {title_short}"
        trace_metadata = {
            "brief_id": brief.brief_id,
            "worker_num": worker_num,
            "content_format": brief.content_format,
            "funnel_stage": brief.funnel_stage,
        }
        trace_input = {
            "brief_id": brief.brief_id,
            "title": brief.title,
            "content_format": brief.content_format,
            "funnel_stage": brief.funnel_stage,
            "word_count_range": list(brief.word_count_range),
            "target_queries": [q.query_text for q in brief.target_queries],
            "key_topics": brief.key_topics,
        }
        if parent_span is not None:
            trace = create_span(
                parent_span, trace_name,
                metadata=trace_metadata,
                input=trace_input,
            )
        else:
            trace = create_trace(
                session_id,
                trace_name,
                metadata=trace_metadata,
                input=trace_input,
                tags=[
                    "worker",
                    f"worker:{worker_num}",
                    f"format:{brief.content_format}",
                    f"funnel:{brief.funnel_stage}",
                ],
                user_id=input_data.domain,
            )
        bdir = _brief_dir(artifact_dir, brief.brief_id)
        display_title = title_short + ("..." if len(brief.title) > 60 else "")

        try:
            # Step 1: Outline
            _cli_worker_progress(f"Worker #{worker_num}: Outlining \"{display_title}\"")
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
            _cli_worker_progress(f"Worker #{worker_num}: Drafting \"{display_title}\"")
            draft = await generate_draft(
                outline=outline,
                brief=brief,
                style_guide_md=style_guide_md,
                company_context_md=company_context_md,
                trace=trace,
            )
            (bdir / "draft.md").write_text(draft.markdown, encoding="utf-8")

            # Step 3: Fact Enrichment
            _cli_worker_progress(f"Worker #{worker_num}: Enriching \"{display_title}\"")
            enriched = await enrich_with_facts(
                draft=draft,
                brief=brief,
                company_name=input_data.company_name,
                domain=input_data.domain,
                trace=trace,
            )
            (bdir / "enriched.md").write_text(enriched.markdown, encoding="utf-8")

            # Step 4: Format
            _cli_worker_progress(f"Worker #{worker_num}: Formatting \"{display_title}\"")
            formatted = await format_content(
                enriched=enriched,
                style_guide_md=style_guide_md,
                brief=brief,
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
            trace_output = {
                "brief_id": formatted.brief_id,
                "title": formatted.title,
                "word_count": formatted.word_count,
                "header_count": formatted.header_count,
                "citation_count": formatted.citation_count,
                "list_count": formatted.list_count,
                "stat_count": formatted.stat_count,
            }
            if parent_span is not None:
                end_span(trace, output=trace_output)
            else:
                # update_trace_output ends the trace internally — no end_span needed
                update_trace_output(trace, output=trace_output)

            return formatted
        except Exception as exc:
            end_span(trace, level="ERROR", status_message=str(exc)[:500])
            raise


async def dispatch_workers(
    briefs: List[ContentBrief],
    input_data: ContentGenerationInput,
    style_guide_md: str,
    company_context_md: str,
    max_concurrent: int = 3,
    *,
    session_id: str = "",
    artifact_dir: Path = Path("."),
    parent_span: Optional[object] = None,
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
        session_id: Session ID.
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
            parent_span=parent_span,
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


# ═══════════════════════════════════════════════════════════════════════
# v1.3 Dispatcher — Outliner → Drafter → Linker → Fact Checker
# ═══════════════════════════════════════════════════════════════════════


async def _run_worker_chain_v13(
    brief: ContentBrief,
    worker_num: int,
    input_data: ContentGenerationInput,
    style_guide_md: str,
    company_context_md: str,
    artifact_dir: Path,
    semaphore: asyncio.Semaphore,
    site_pages: Optional[List[str]] = None,
    parent_span: Optional[object] = None,
    storage: Any = None,  # Optional[StorageBackend]
    session_factory: Any = None,  # Optional[async_sessionmaker]
    piece_id: Optional[_uuid.UUID] = None,
    event_bus: Any = None,
    task_id: Optional[str] = None,
    redis_client: Any = None,
    effective_slug: Optional[str] = None,
) -> FormattedContent:
    """Run the v1.3 4-step worker chain for a single brief.

    Chain: Outliner → Drafter → Linker → Fact Checker
    Uses v1.3 tracing (LangSmith) and structural count computation inline.

    Args:
        brief: Content brief to process.
        worker_num: Worker number for logging.
        input_data: Pipeline input for company details.
        style_guide_md: Company style guide.
        company_context_md: Company context.
        artifact_dir: Root artifact directory.
        semaphore: Concurrency limiter.
        site_pages: Known site page URLs for internal linking.
        parent_span: LangSmith parent span.

    Returns:
        FormattedContent for this brief.
    """
    from core.content_engine.workers.formatter import _count_structural_elements
    from core.content_engine.workers.linker import link_content
    from core.models.content_generation import ContentDraft

    async with semaphore:
        title_short = brief.title[:60]
        display_title = title_short + ("..." if len(brief.title) > 60 else "")

        span = create_span(
            parent_span,
            f"worker-chain/{brief.brief_id}",
            metadata={
                "brief_id": brief.brief_id,
                "worker_num": worker_num,
                "content_format": brief.content_format,
            },
        )

        bdir = _brief_dir(artifact_dir, brief.brief_id)

        try:
            # Helper to compute relative storage path from brief dir
            def _rel(filename: str) -> str:
                return str((bdir / filename).relative_to(storage.root)) if storage else ""

            # Step 1: Outline
            await _write_pipeline_state_async(artifact_dir, [brief.brief_id], "outlining", task_id=task_id, redis_client=redis_client, effective_slug=effective_slug)
            _emit(event_bus, task_id, "worker_progress", {
                "brief_id": brief.brief_id, "step": "outlining", "worker_num": worker_num,
            })
            logger.info("Worker #%d: Outlining \"%s\"", worker_num, display_title)
            outline = await generate_outline(
                brief=brief,
                company_context_md=company_context_md,
                trace=span,
            )
            outline_json = json.dumps(outline.model_dump(mode="json"), indent=2, default=str)
            if storage:
                from core.content_engine.artifact_writer import persist_stage_artifact
                from core.db.enums import ContentArtifactStage

                await persist_stage_artifact(
                    storage=storage, session_factory=session_factory, piece_id=piece_id,
                    stage=ContentArtifactStage.outline, relative_path=_rel("outline.json"),
                    content=outline_json, content_type="application/json",
                )
            else:
                (bdir / "outline.json").write_text(outline_json, encoding="utf-8")

            # Step 2: Draft
            await _write_pipeline_state_async(artifact_dir, [brief.brief_id], "drafting", task_id=task_id, redis_client=redis_client, effective_slug=effective_slug)
            _emit(event_bus, task_id, "worker_progress", {
                "brief_id": brief.brief_id, "step": "drafting", "worker_num": worker_num,
            })
            logger.info("Worker #%d: Drafting \"%s\"", worker_num, display_title)
            draft = await generate_draft(
                outline=outline,
                brief=brief,
                style_guide_md=style_guide_md,
                company_context_md=company_context_md,
                trace=span,
            )
            if storage:
                await persist_stage_artifact(
                    storage=storage, session_factory=session_factory, piece_id=piece_id,
                    stage=ContentArtifactStage.draft, relative_path=_rel("draft.md"),
                    content=draft.markdown,
                )
            else:
                (bdir / "draft.md").write_text(draft.markdown, encoding="utf-8")

            # Step 3: Link
            await _write_pipeline_state_async(artifact_dir, [brief.brief_id], "linking", task_id=task_id, redis_client=redis_client, effective_slug=effective_slug)
            _emit(event_bus, task_id, "worker_progress", {
                "brief_id": brief.brief_id, "step": "linking", "worker_num": worker_num,
            })
            logger.info("Worker #%d: Linking \"%s\"", worker_num, display_title)
            linked = await link_content(
                draft=draft,
                brief=brief,
                company_name=input_data.company_name,
                domain=input_data.domain,
                site_pages=site_pages,
                trace=span,
            )
            if storage:
                await persist_stage_artifact(
                    storage=storage, session_factory=session_factory, piece_id=piece_id,
                    stage=ContentArtifactStage.linked, relative_path=_rel("linked.md"),
                    content=linked.markdown,
                )
            else:
                (bdir / "linked.md").write_text(linked.markdown, encoding="utf-8")

            # Step 4: Fact Check (verify-only, no new content)
            await _write_pipeline_state_async(artifact_dir, [brief.brief_id], "enriching", task_id=task_id, redis_client=redis_client, effective_slug=effective_slug)
            _emit(event_bus, task_id, "worker_progress", {
                "brief_id": brief.brief_id, "step": "enriching", "worker_num": worker_num,
            })
            logger.info("Worker #%d: Fact checking \"%s\"", worker_num, display_title)
            fact_check_draft = ContentDraft(
                brief_id=linked.brief_id,
                title=linked.title,
                markdown=linked.markdown,
                word_count=linked.word_count,
            )
            checked = await enrich_with_facts(
                draft=fact_check_draft,
                brief=brief,
                company_name=input_data.company_name,
                domain=input_data.domain,
                trace=span,
            )
            if storage:
                await persist_stage_artifact(
                    storage=storage, session_factory=session_factory, piece_id=piece_id,
                    stage=ContentArtifactStage.enriched, relative_path=_rel("enriched.md"),
                    content=checked.markdown,
                )
            else:
                (bdir / "fact_checked.md").write_text(checked.markdown, encoding="utf-8")

            # Compute structural counts inline (no formatter step)
            counts = _count_structural_elements(checked.markdown)
            word_count = len(checked.markdown.split())

            formatted = FormattedContent(
                brief_id=checked.brief_id,
                title=checked.title,
                markdown=checked.markdown,
                word_count=word_count,
                **counts,
            )

            logger.info(
                "Worker #%d: DONE (%d words, %d headers, %d citations)",
                worker_num,
                formatted.word_count,
                formatted.header_count,
                formatted.citation_count,
            )

            end_span(span, output={
                "brief_id": formatted.brief_id,
                "word_count": formatted.word_count,
                "header_count": formatted.header_count,
                "citation_count": formatted.citation_count,
                "internal_links": linked.internal_links_added,
                "external_links": linked.external_links_added,
            })

            return formatted
        except Exception as exc:
            end_span(span, error=str(exc)[:500])
            raise


async def dispatch_workers_v13(
    briefs: List[ContentBrief],
    input_data: ContentGenerationInput,
    style_guide_md: str,
    company_context_md: str,
    max_concurrent: int = 3,
    *,
    artifact_dir: Path = Path("."),
    site_pages: Optional[List[str]] = None,
    parent_span: Optional[object] = None,
    storage: Any = None,  # Optional[StorageBackend]
    session_factory: Any = None,  # Optional[async_sessionmaker]
    piece_id_map: Optional[Dict[str, _uuid.UUID]] = None,
    event_bus: Any = None,
    task_id: Optional[str] = None,
    redis_client: Any = None,
    effective_slug: Optional[str] = None,
) -> Tuple[List[Tuple[str, FormattedContent]], List[Dict[str, str]]]:
    """Dispatch v1.3 worker chains in parallel.

    Chain: Outliner → Drafter → Linker → Fact Checker
    (v1.3 replaces Enricher→Formatter with Linker→FactChecker)

    Args:
        briefs: Content briefs to process.
        input_data: Pipeline input for company details.
        style_guide_md: Company style guide.
        company_context_md: Company context.
        max_concurrent: Max concurrent workers.
        artifact_dir: Root artifact directory.
        site_pages: Known site page URLs for internal linking.
        parent_span: LangSmith parent span.

    Returns:
        Tuple of (successes, failures):
          - successes: List of (brief_id, FormattedContent) tuples
          - failures: List of {"brief_id": str, "error": str} dicts
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    pid_map = piece_id_map or {}

    tasks = [
        _run_worker_chain_v13(
            brief=brief,
            worker_num=i + 1,
            input_data=input_data,
            style_guide_md=style_guide_md,
            company_context_md=company_context_md,
            artifact_dir=artifact_dir,
            semaphore=semaphore,
            site_pages=site_pages,
            parent_span=parent_span,
            storage=storage,
            session_factory=session_factory,
            piece_id=pid_map.get(brief.brief_id),
            event_bus=event_bus,
            task_id=task_id,
            redis_client=redis_client,
            effective_slug=effective_slug,
        )
        for i, brief in enumerate(briefs)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    formatted_contents: List[Tuple[str, FormattedContent]] = []
    failed_briefs: List[Dict[str, str]] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                "v1.3 worker for brief '%s' failed: %s",
                briefs[i].brief_id,
                result,
            )
            failed_briefs.append({
                "brief_id": briefs[i].brief_id,
                "error": str(result)[:500],
            })
        else:
            formatted_contents.append((briefs[i].brief_id, result))

    logger.info(
        "v1.3 workers complete: %d/%d briefs (%d failed)",
        len(formatted_contents),
        len(briefs),
        len(failed_briefs),
    )

    return formatted_contents, failed_briefs
