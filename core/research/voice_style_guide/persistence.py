"""DB persistence hooks for the Voice Style Guide pipeline.

After each pipeline stage writes artifacts to the filesystem, the pipeline
optionally calls the corresponding ``persist_*()`` function here to write
metadata into Postgres via the VSG-specific repositories.

Design principles (mirrors ``core/topic_discovery/persistence.py``):
- **Filesystem-first, DB-additive**: JSON always written first.
- **Graceful degradation**: Every function catches all exceptions — DB errors
  NEVER crash the pipeline.
- **Per-step transaction isolation**: Each function opens its own session,
  commits, and closes.
- **FK-safe ordering**: insert run → authors / guide.
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


async def persist_vsg_run(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    *,
    product_id: _uuid.UUID | None = None,
    pipeline_run_id: _uuid.UUID | None = None,
    ap_manifest_version: str | None = None,
) -> _uuid.UUID | None:
    """Create/update VSGRunModel at pipeline start.

    Returns the vsg_run_id (UUID) for subsequent hooks, or None if
    persistence is skipped or fails.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return None
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.enums import ResearchRunStatus
        from core.db.repositories.vsg_repo import VSGRunRepository

        async with session_factory() as session:
            repo = VSGRunRepository(session)
            vsg_run = await repo.upsert_run(
                company_id=company_id,
                effective_slug=effective_slug,
                pipeline_run_id=pipeline_run_id or run_id,
                product_id=product_id,
                ap_manifest_version=ap_manifest_version,
                status=ResearchRunStatus.running,
            )
            await session.commit()

        logger.info(
            "persist_vsg_run: %s stored (id=%s)",
            effective_slug, vsg_run.id,
        )
        return vsg_run.id
    except Exception:
        logger.warning(
            "persist_vsg_run failed for %s, continuing without DB",
            effective_slug, exc_info=True,
        )
        return None


# ── Author hook ──────────────────────────────────────────────────────────


async def persist_vsg_author_doc(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    vsg_run_db_id: Optional[_uuid.UUID],
    author_id: str,
    name: str,
    version: int,
    content_md: str,
    storage_key: str,
) -> None:
    """Persist an author research document."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    if vsg_run_db_id is None:
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.repositories.vsg_repo import VSGAuthorRepository

        async with session_factory() as session:
            repo = VSGAuthorRepository(session)
            await repo.upsert_author(
                vsg_run_id=vsg_run_db_id,
                author_id=author_id,
                name=name,
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
            "persist_vsg_author_doc: %s v%d stored", name, version,
        )
    except Exception:
        logger.warning(
            "persist_vsg_author_doc failed for %s, continuing without DB",
            name, exc_info=True,
        )


# ── Guide hook ───────────────────────────────────────────────────────────


async def persist_vsg_guide_doc(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    vsg_run_db_id: Optional[_uuid.UUID],
    version: int,
    content_md: str,
    storage_key: str,
    *,
    source_authors: list[str] | None = None,
) -> None:
    """Persist the synthesized voice style guide."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    if vsg_run_db_id is None:
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.repositories.vsg_repo import VSGGuideRepository

        async with session_factory() as session:
            repo = VSGGuideRepository(session)
            await repo.upsert_guide(
                vsg_run_id=vsg_run_db_id,
                version=version,
                storage_key=storage_key,
                content_hash=_sha256(content_md),
                word_count=_word_count(content_md),
                source_authors=source_authors,
                metadata_json={
                    "run_id": str(run_id),
                },
            )
            await session.commit()

        logger.info(
            "persist_vsg_guide_doc: v%d stored", version,
        )
    except Exception:
        logger.warning(
            "persist_vsg_guide_doc failed, continuing without DB",
            exc_info=True,
        )


# ── Status update hook ──────────────────────────────────────────────────


async def persist_vsg_status_update(
    session_factory: Optional[async_sessionmaker],
    vsg_run_db_id: Optional[_uuid.UUID],
    status: str,
) -> None:
    """Update VSGRunModel.status on transitions."""
    if session_factory is None or vsg_run_db_id is None:
        return
    try:
        from core.db.enums import ResearchRunStatus
        from core.db.repositories.vsg_repo import VSGRunRepository

        run_status = ResearchRunStatus(status)
        async with session_factory() as session:
            repo = VSGRunRepository(session)
            await repo.update_status(vsg_run_db_id, run_status)
            await session.commit()
        logger.info(
            "persist_vsg_status_update: %s → %s", vsg_run_db_id, status,
        )
    except Exception:
        logger.warning(
            "persist_vsg_status_update failed for %s",
            vsg_run_db_id, exc_info=True,
        )
