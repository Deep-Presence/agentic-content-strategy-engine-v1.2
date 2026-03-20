"""DB persistence hooks for the Audience Persona pipeline.

After each pipeline stage writes artifacts to the filesystem, the pipeline
optionally calls the corresponding ``persist_*()`` function here to write
metadata into Postgres via the AP-specific repositories.

Design principles (mirrors ``core/topic_discovery/persistence.py``):
- **Filesystem-first, DB-additive**: JSON always written first.
- **Graceful degradation**: Every function catches all exceptions — DB errors
  NEVER crash the pipeline.
- **Per-step transaction isolation**: Each function opens its own session,
  commits, and closes.
- **FK-safe ordering**: insert run → profiles.
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


async def persist_persona_run(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    *,
    product_id: _uuid.UUID | None = None,
    pipeline_run_id: _uuid.UUID | None = None,
    kb_synthesis_version: int | None = None,
) -> _uuid.UUID | None:
    """Create/update PersonaRunModel at pipeline start.

    Returns the persona_run_id (UUID) for subsequent hooks, or None if
    persistence is skipped or fails.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return None
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.enums import ResearchRunStatus
        from core.db.repositories.persona_repo import PersonaRunRepository

        async with session_factory() as session:
            repo = PersonaRunRepository(session)
            persona_run = await repo.upsert_run(
                company_id=company_id,
                effective_slug=effective_slug,
                pipeline_run_id=pipeline_run_id or run_id,
                product_id=product_id,
                kb_synthesis_version=kb_synthesis_version,
                status=ResearchRunStatus.running,
            )
            await session.commit()

        logger.info(
            "persist_persona_run: %s stored (id=%s)",
            effective_slug, persona_run.id,
        )
        return persona_run.id
    except Exception:
        logger.warning(
            "persist_persona_run failed for %s, continuing without DB",
            effective_slug, exc_info=True,
        )
        return None


# ── Profile hook ─────────────────────────────────────────────────────────


async def persist_persona_profile_doc(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    persona_run_db_id: Optional[_uuid.UUID],
    persona_id: str,
    persona_name: str,
    version: int,
    content_md: str,
    storage_key: str,
    *,
    kind: str = "secondary",
    status: str = "fresh",
) -> None:
    """Persist a persona profile document."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    if persona_run_db_id is None:
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.repositories.persona_repo import PersonaProfileRepository

        async with session_factory() as session:
            repo = PersonaProfileRepository(session)
            await repo.upsert_profile(
                persona_run_id=persona_run_db_id,
                persona_id=persona_id,
                persona_name=persona_name,
                version=version,
                storage_key=storage_key,
                kind=kind,
                status=status,
                content_hash=_sha256(content_md),
                word_count=_word_count(content_md),
                metadata_json={
                    "run_id": str(run_id),
                },
            )
            await session.commit()

        logger.info(
            "persist_persona_profile_doc: %s v%d stored",
            persona_name, version,
        )
    except Exception:
        logger.warning(
            "persist_persona_profile_doc failed for %s, continuing without DB",
            persona_name, exc_info=True,
        )


# ── Status update hook ──────────────────────────────────────────────────


async def persist_persona_status_update(
    session_factory: Optional[async_sessionmaker],
    persona_run_db_id: Optional[_uuid.UUID],
    status: str,
) -> None:
    """Update PersonaRunModel.status on transitions."""
    if session_factory is None or persona_run_db_id is None:
        return
    try:
        from core.db.enums import ResearchRunStatus
        from core.db.repositories.persona_repo import PersonaRunRepository

        run_status = ResearchRunStatus(status)
        async with session_factory() as session:
            repo = PersonaRunRepository(session)
            await repo.update_status(persona_run_db_id, run_status)
            await session.commit()
        logger.info(
            "persist_persona_status_update: %s → %s",
            persona_run_db_id, status,
        )
    except Exception:
        logger.warning(
            "persist_persona_status_update failed for %s",
            persona_run_db_id, exc_info=True,
        )
