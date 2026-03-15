"""DB persistence hooks for research pipelines (KB, AP, VSG).

Backward-compatible shim layer: pipeline call sites import from HERE, but
internals delegate to the per-pipeline persistence modules:
- ``core.research.knowledge_base.persistence``
- ``core.research.audience_persona.persistence``
- ``core.research.voice_style_guide.persistence``

The dedicated modules write to pipeline-specific tables (kb_runs, persona_runs,
vsg_runs, etc.) instead of the shared research_artifacts table.

Design principles:
- **Filesystem-first, DB-additive**: JSON/Markdown always written first.
- **Graceful degradation**: Every function catches all exceptions — DB errors
  NEVER crash the pipeline.
- **Per-step transaction isolation**: Each function opens its own session,
  commits, and closes.
"""
from __future__ import annotations

import hashlib
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


# ── Helpers (re-exported for tests) ──────────────────────────────────────


def _sha256(text: str) -> str:
    """SHA-256 hex digest of a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _word_count(text: str) -> int:
    """Approximate word count."""
    return len(text.split())


# ── Guard ────────────────────────────────────────────────────────────────


def _should_persist(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
) -> bool:
    """Return True if DB persistence is configured."""
    return (
        session_factory is not None
        and run_id is not None
        and company_id is not None
    )


# ── Knowledge Base (shim → core.research.knowledge_base.persistence) ────


async def persist_kb_doc(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    doc_type: str,
    version: int,
    content_md: str,
    storage_key: str,
    *,
    content_json: dict | None = None,
) -> None:
    """Persist a KB L2 document (company_overview, customer_reviews, etc.)."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.research.knowledge_base.persistence import (
            persist_kb_document,
            persist_kb_run,
        )

        # Ensure run exists, then persist document
        kb_run_db_id = await persist_kb_run(
            session_factory, run_id, company_id, effective_slug,
        )
        await persist_kb_document(
            session_factory, run_id, company_id, kb_run_db_id,
            doc_type, version, content_md, storage_key,
        )
    except Exception:
        logger.warning(
            "persist_kb_doc failed for %s/%s, continuing without DB",
            effective_slug, doc_type, exc_info=True,
        )


async def persist_kb_synthesis(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    version: int,
    content_md: str,
    storage_key: str,
) -> None:
    """Persist KB L3 synthesis (company_context)."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.research.knowledge_base.persistence import (
            persist_kb_run,
            persist_kb_synthesis_doc,
        )

        kb_run_db_id = await persist_kb_run(
            session_factory, run_id, company_id, effective_slug,
        )
        await persist_kb_synthesis_doc(
            session_factory, run_id, company_id, kb_run_db_id,
            version, content_md, storage_key,
        )
    except Exception:
        logger.warning(
            "persist_kb_synthesis failed for %s, continuing without DB",
            effective_slug, exc_info=True,
        )


# ── Audience Persona (shim → core.research.audience_persona.persistence) ─


async def persist_persona_profile(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    persona_id: str,
    persona_name: str,
    version: int,
    content_md: str,
    storage_key: str,
    *,
    kind: str = "secondary",
    status: str = "fresh",
) -> None:
    """Persist a persona profile."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.research.audience_persona.persistence import (
            persist_persona_profile_doc,
            persist_persona_run,
        )

        persona_run_db_id = await persist_persona_run(
            session_factory, run_id, company_id, effective_slug,
        )
        await persist_persona_profile_doc(
            session_factory, run_id, company_id, persona_run_db_id,
            persona_id, persona_name, version, content_md, storage_key,
            kind=kind, status=status,
        )
    except Exception:
        logger.warning(
            "persist_persona_profile failed for %s/%s, continuing without DB",
            effective_slug, persona_name, exc_info=True,
        )


# ── Voice Style Guide (shim → core.research.voice_style_guide.persistence)


async def persist_voice_style_guide(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    version: int,
    content_md: str,
    storage_key: str,
    *,
    source_authors: list[str] | None = None,
) -> None:
    """Persist the synthesized voice style guide."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.research.voice_style_guide.persistence import (
            persist_vsg_guide_doc,
            persist_vsg_run,
        )

        vsg_run_db_id = await persist_vsg_run(
            session_factory, run_id, company_id, effective_slug,
        )
        await persist_vsg_guide_doc(
            session_factory, run_id, company_id, vsg_run_db_id,
            version, content_md, storage_key,
            source_authors=source_authors,
        )
    except Exception:
        logger.warning(
            "persist_voice_style_guide failed for %s, continuing without DB",
            effective_slug, exc_info=True,
        )


async def persist_author_research(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    author_id: str,
    name: str,
    version: int,
    content_md: str,
    storage_key: str,
) -> None:
    """Persist author research for the voice style guide pipeline."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.research.voice_style_guide.persistence import (
            persist_vsg_author_doc,
            persist_vsg_run,
        )

        vsg_run_db_id = await persist_vsg_run(
            session_factory, run_id, company_id, effective_slug,
        )
        await persist_vsg_author_doc(
            session_factory, run_id, company_id, vsg_run_db_id,
            author_id, name, version, content_md, storage_key,
        )
    except Exception:
        logger.warning(
            "persist_author_research failed for %s/%s, continuing without DB",
            effective_slug, name, exc_info=True,
        )


# ── Pipeline Run Tracking (unchanged — uses PipelineRunModel directly) ──


async def persist_pipeline_run_start(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    pipeline_type_str: str,
) -> None:
    """Create a PipelineRunModel record for a research pipeline run."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.enums import PipelineStatus, PipelineType
        from core.db.models.pipelines import PipelineRunModel

        pipeline_type = PipelineType(pipeline_type_str)
        async with session_factory() as session:
            run = PipelineRunModel(
                id=run_id,
                company_id=company_id,
                effective_slug=effective_slug,
                pipeline_type=pipeline_type,
                status=PipelineStatus.running,
                started_at=datetime.now(tz=timezone.utc),
            )
            session.add(run)
            await session.commit()
        logger.info(
            "persist_pipeline_run_start: %s run %s started for %s",
            pipeline_type_str, run_id, effective_slug,
        )
    except Exception:
        logger.warning(
            "persist_pipeline_run_start failed for %s, continuing without DB",
            effective_slug, exc_info=True,
        )


async def persist_pipeline_run_complete(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    summary: dict | None = None,
) -> None:
    """Mark a research pipeline run as completed."""
    if session_factory is None or run_id is None:
        return
    try:
        from core.db.enums import PipelineStatus
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run:
                run.status = PipelineStatus.completed
                run.completed_at = datetime.now(tz=timezone.utc)
                if summary:
                    run.summary = summary
                await session.commit()
        logger.info("persist_pipeline_run_complete: run %s completed", run_id)
    except Exception:
        logger.warning(
            "persist_pipeline_run_complete failed for run %s", run_id, exc_info=True,
        )


async def persist_pipeline_run_failed(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    error: str,
) -> None:
    """Mark a research pipeline run as failed."""
    if session_factory is None or run_id is None:
        return
    try:
        from core.db.enums import PipelineStatus
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run:
                run.status = PipelineStatus.failed
                run.error_message = error[:2000] if error else None
                run.completed_at = datetime.now(tz=timezone.utc)
                await session.commit()
        logger.info("persist_pipeline_run_failed: run %s failed", run_id)
    except Exception:
        logger.warning(
            "persist_pipeline_run_failed failed for run %s", run_id, exc_info=True,
        )
