"""DB persistence hooks for the Knowledge Base pipeline.

After each pipeline stage writes artifacts to the filesystem, the pipeline
optionally calls the corresponding ``persist_*()`` function here to write
metadata into Postgres via the KB-specific repositories.

Design principles (mirrors ``core/topic_discovery/persistence.py``):
- **Filesystem-first, DB-additive**: JSON always written first.
- **Graceful degradation**: Every function catches all exceptions — DB errors
  NEVER crash the pipeline.
- **Per-step transaction isolation**: Each function opens its own session,
  commits, and closes.
- **FK-safe ordering**: insert run → documents → synthesis.
"""
from __future__ import annotations

import hashlib
import logging
import uuid as _uuid
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _word_count(text: str) -> int:
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


# ── Run hook ─────────────────────────────────────────────────────────────


async def persist_kb_run(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    *,
    product_id: _uuid.UUID | None = None,
    pipeline_run_id: _uuid.UUID | None = None,
    mode: str | None = None,
) -> _uuid.UUID | None:
    """Create/update KBRunModel at pipeline start.

    Returns the kb_run_id (UUID) for subsequent hooks, or None if
    persistence is skipped or fails.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return None
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.enums import ResearchRunStatus
        from core.db.repositories.kb_repo import KBRunRepository

        async with session_factory() as session:
            repo = KBRunRepository(session)
            kb_run = await repo.upsert_run(
                company_id=company_id,
                effective_slug=effective_slug,
                pipeline_run_id=pipeline_run_id or run_id,
                product_id=product_id,
                mode=mode,
                status=ResearchRunStatus.running,
            )
            await session.commit()

        logger.info(
            "persist_kb_run: %s stored (id=%s)", effective_slug, kb_run.id,
        )
        return kb_run.id
    except Exception:
        logger.warning(
            "persist_kb_run failed for %s, continuing without DB",
            effective_slug, exc_info=True,
        )
        return None


# ── Document hook ────────────────────────────────────────────────────────


async def persist_kb_document(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    kb_run_db_id: Optional[_uuid.UUID],
    doc_type: str,
    version: int,
    content_md: str,
    storage_key: str,
) -> None:
    """Persist a KB document (company_overview, customer_reviews, etc.)."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    if kb_run_db_id is None:
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.repositories.kb_repo import KBDocumentRepository

        async with session_factory() as session:
            repo = KBDocumentRepository(session)
            await repo.upsert_document(
                kb_run_id=kb_run_db_id,
                doc_type=doc_type,
                version=version,
                storage_key=storage_key,
                status="fresh",
                content_hash=_sha256(content_md),
                word_count=_word_count(content_md),
                metadata_json={
                    "run_id": str(run_id),
                },
            )
            await session.commit()

        logger.info(
            "persist_kb_document: %s v%d stored", doc_type, version,
        )
    except Exception:
        logger.warning(
            "persist_kb_document failed for %s, continuing without DB",
            doc_type, exc_info=True,
        )


# ── Synthesis hook ───────────────────────────────────────────────────────


async def persist_kb_synthesis_doc(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    kb_run_db_id: Optional[_uuid.UUID],
    version: int,
    content_md: str,
    storage_key: str,
) -> None:
    """Persist KB synthesis and update synthesis_version on the run."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    if kb_run_db_id is None:
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.repositories.kb_repo import (
            KBRunRepository,
            KBSynthesisRepository,
        )

        async with session_factory() as session:
            synth_repo = KBSynthesisRepository(session)
            run_repo = KBRunRepository(session)

            await synth_repo.upsert_synthesis(
                kb_run_id=kb_run_db_id,
                version=version,
                storage_key=storage_key,
                content_hash=_sha256(content_md),
                word_count=_word_count(content_md),
                metadata_json={
                    "run_id": str(run_id),
                },
            )

            await run_repo.update_synthesis_version(kb_run_db_id, version)
            await session.commit()

        logger.info(
            "persist_kb_synthesis_doc: v%d stored", version,
        )
    except Exception:
        logger.warning(
            "persist_kb_synthesis_doc failed, continuing without DB",
            exc_info=True,
        )


# ── Status update hook ──────────────────────────────────────────────────


async def persist_kb_status_update(
    session_factory: Optional[async_sessionmaker],
    kb_run_db_id: Optional[_uuid.UUID],
    status: str,
) -> None:
    """Update KBRunModel.status on transitions."""
    if session_factory is None or kb_run_db_id is None:
        return
    try:
        from core.db.enums import ResearchRunStatus
        from core.db.repositories.kb_repo import KBRunRepository

        run_status = ResearchRunStatus(status)
        async with session_factory() as session:
            repo = KBRunRepository(session)
            await repo.update_status(kb_run_db_id, run_status)
            await session.commit()
        logger.info(
            "persist_kb_status_update: %s → %s", kb_run_db_id, status,
        )
    except Exception:
        logger.warning(
            "persist_kb_status_update failed for %s",
            kb_run_db_id, exc_info=True,
        )
