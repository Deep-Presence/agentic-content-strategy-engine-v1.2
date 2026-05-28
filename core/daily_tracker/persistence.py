"""DB + filesystem persistence hooks for the Daily Tracker pipeline.

After the orchestrator produces a DailyRunResult, the runner calls these
functions to persist the result to both the filesystem and the database.

Design principles (mirrors ``core/site_audit/persistence.py``):
- **Filesystem-first, DB-additive**: JSON artifact always written first.
- **Graceful degradation**: Every function catches all exceptions — DB errors
  NEVER crash the pipeline.
- **Two-phase DB write**: ``create_daily_run_record()`` at task start
  (status=running for in-flight visibility), ``persist_daily_run_result()``
  at completion (updates status + inserts responses).
- **String company_id**: Daily tracker uses ``company_slug`` (String), not
  UUID FK, so it works standalone before company onboarding.
"""
from __future__ import annotations

import json
import logging
import uuid as _uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


# Lazy imports — avoid circular deps at module level.
# ORM models are imported inside functions that need them.
DailyRunModel: Any = None
DailyRunResponseModel: Any = None


def _lazy_import_models() -> None:
    """Import ORM models lazily to avoid circular imports."""
    global DailyRunModel, DailyRunResponseModel
    if DailyRunModel is None:
        from core.db.models.daily_tracker import (
            DailyRunModel as _DRM,
            DailyRunResponseModel as _DRRM,
        )
        DailyRunModel = _DRM
        DailyRunResponseModel = _DRRM


# ── Guard ────────────────────────────────────────────────────────────────


def _should_persist(
    session_factory: Optional[async_sessionmaker],
    company_slug: Optional[str],
) -> bool:
    """Return True if DB persistence is configured.

    Unlike other pipelines, daily_tracker uses string company_slug
    (not UUID company_id) for its tables.
    """
    return session_factory is not None and bool(company_slug)


# ── Filesystem persistence ───────────────────────────────────────────────


async def write_run_artifact(
    artifacts_root: Path,
    company_slug: str,
    result: Any,
    mention_analyses: list[Any],
) -> Path:
    """Write run result + mention analyses to a JSON artifact.

    Path: ``artifacts/daily_tracker/{company_slug}/runs/{run_id}.json``

    Always succeeds or logs a warning. Returns the intended output path.
    """
    out_dir = artifacts_root / "daily_tracker" / company_slug / "runs"
    out_path = out_dir / f"{result.run_id}.json"

    try:
        out_dir.mkdir(parents=True, exist_ok=True)

        payload = result.model_dump(mode="json")
        payload["mention_analyses"] = [
            ma.model_dump(mode="json") for ma in mention_analyses
        ]

        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        logger.info(
            "write_run_artifact: %s written (%d responses)",
            out_path, len(result.responses),
        )
    except Exception:
        logger.warning(
            "write_run_artifact failed for %s/%s, continuing",
            company_slug, result.run_id, exc_info=True,
        )

    return out_path


# ── DB persistence: create run record at start ───────────────────────────


async def create_daily_run_record(
    session_factory: Optional[async_sessionmaker],
    company_slug: str,
    run_id_str: str,
    config_dict: dict[str, Any],
) -> None:
    """Create a DailyRunModel row with status='running' at task start.

    Enables in-flight visibility: ``GET /runs`` can show running tasks.
    Uses ``company_slug`` (string) as ``company_id``.

    Graceful degradation — never raises.
    """
    if not _should_persist(session_factory, company_slug):
        return
    assert session_factory is not None

    try:
        _lazy_import_models()

        run_uuid = _uuid.UUID(run_id_str) if not isinstance(run_id_str, _uuid.UUID) else run_id_str

        async with session_factory() as session:
            row = DailyRunModel(
                id=run_uuid,
                company_id=company_slug,
                status="running",
                config=config_dict or None,
            )
            session.add(row)
            await session.commit()

        logger.info("create_daily_run_record: run %s (company=%s) created", run_id_str, company_slug)
    except Exception:
        logger.warning(
            "create_daily_run_record failed for %s/%s, continuing",
            company_slug, run_id_str, exc_info=True,
        )


# ── DB persistence: persist completed/failed result ──────────────────────


def _validate_prompt_id(prompt_id: str) -> Optional[_uuid.UUID]:
    """Validate and convert a prompt_id string to UUID.

    Returns None if invalid (logs warning).
    """
    try:
        return _uuid.UUID(prompt_id)
    except (ValueError, AttributeError):
        logger.warning("Invalid prompt_id '%s' — skipping response", prompt_id)
        return None


async def persist_daily_run_result(
    session_factory: Optional[async_sessionmaker],
    company_slug: str,
    result: Any,
    mention_analyses: list[Any],
) -> None:
    """Persist a completed/failed DailyRunResult to the database.

    Updates the existing DailyRunModel row (created by ``create_daily_run_record``)
    and bulk-inserts DailyRunResponseModel rows with inline mention analysis.

    Args:
        session_factory: Async session factory (None = skip persistence).
        company_slug: Company slug string (used as company_id in daily_tracker tables).
        result: The ``DailyRunResult`` Pydantic model.
        mention_analyses: Index-aligned list of ``MentionAnalysis`` objects.
    """
    if not _should_persist(session_factory, company_slug):
        return
    assert session_factory is not None

    try:
        _lazy_import_models()

        run_uuid = _uuid.UUID(result.run_id) if isinstance(result.run_id, str) else result.run_id
        status_str = result.status.value if hasattr(result.status, "value") else str(result.status)

        # Phase 1: Update run row in its own commit — ensures run status
        # is persisted even if response inserts fail (FK violation etc.).
        async with session_factory() as session:
            run_row = await session.get(DailyRunModel, run_uuid)
            if run_row is None:
                run_row = DailyRunModel(
                    id=run_uuid,
                    company_id=company_slug,
                )
                session.add(run_row)

            run_row.status = status_str
            run_row.started_at = result.started_at
            run_row.completed_at = result.completed_at
            run_row.error = result.error
            run_row.prompt_count = result.prompt_count
            run_row.engine_count = result.engine_count
            await session.commit()

        # Phase 2: Insert response rows in a separate commit — a FK
        # failure on one prompt_id won't roll back the run status update.
        responses = result.responses or []
        analyses = mention_analyses or []
        persisted_count = 0

        # Fanout parent map: fanout_prompt_id → parent_prompt_id (str).
        # Populated by orchestrator when fanout queries are included.
        fanout_parent_map: dict[str, str] = getattr(
            result, "_fanout_parent_map", {}
        )

        if responses:
            try:
                async with session_factory() as session:
                    # Idempotent: remove any previously-inserted responses for
                    # this run so a retry doesn't produce duplicates.
                    await session.execute(
                        delete(DailyRunResponseModel).where(
                            DailyRunResponseModel.run_id == run_uuid
                        )
                    )

                    for i, response in enumerate(responses):
                        prompt_uuid = _validate_prompt_id(response.prompt_id)
                        if prompt_uuid is None:
                            continue

                        analysis = analyses[i] if i < len(analyses) else None

                        # Denormalized parent_prompt_id for analytics.
                        # Set when this response is from a fanout query.
                        parent_pid_str = fanout_parent_map.get(
                            response.prompt_id
                        )
                        parent_prompt_uuid = (
                            _uuid.UUID(parent_pid_str)
                            if parent_pid_str
                            else None
                        )

                        resp_row = DailyRunResponseModel(
                            id=_uuid.uuid4(),
                            run_id=run_uuid,
                            prompt_id=prompt_uuid,
                            engine=response.engine,
                            response_text=response.response_text,
                            latency_ms=response.latency_ms,
                            error=response.error,
                            brand_mentioned=analysis.brand_mentioned if analysis else False,
                            brand_mention_count=analysis.brand_mention_count if analysis else 0,
                            competitor_mentions=analysis.competitor_mentions if analysis else {},
                            citations=analysis.citations if analysis else [],
                            citation_rank=analysis.citation_rank if analysis else None,
                            parent_prompt_id=parent_prompt_uuid,
                        )
                        session.add(resp_row)
                        persisted_count += 1

                    await session.commit()
            except Exception:
                logger.warning(
                    "persist_daily_run_result: response insert failed for run %s, "
                    "run status already committed",
                    run_uuid, exc_info=True,
                )

        logger.info(
            "persist_daily_run_result: run %s stored for %s "
            "(status=%s, %d/%d responses persisted)",
            run_uuid, company_slug, status_str,
            persisted_count, len(responses),
        )

    except Exception:
        logger.warning(
            "persist_daily_run_result failed for %s, continuing without DB",
            company_slug, exc_info=True,
        )


# ── DB persistence: mark run as failed (safety net) ─────────────────────


async def mark_daily_run_failed(
    session_factory: Optional[async_sessionmaker],
    run_id_str: Optional[str],
    error: str = "Unknown error",
) -> None:
    """Mark a daily_runs row as 'failed' — safety net for unexpected exceptions.

    Called from the runner's finally block to ensure the row never stays
    in 'running' state.  Idempotent — no-op if row is already terminal.
    """
    if session_factory is None or not run_id_str:
        return

    try:
        _lazy_import_models()
        run_uuid = _uuid.UUID(run_id_str) if isinstance(run_id_str, str) else run_id_str

        async with session_factory() as session:
            run_row = await session.get(DailyRunModel, run_uuid)
            if run_row and run_row.status == "running":
                run_row.status = "failed"
                run_row.error = error[:2000] if error else None
                await session.commit()
                logger.info("mark_daily_run_failed: run %s marked failed", run_id_str)
    except Exception:
        logger.warning("mark_daily_run_failed failed for %s", run_id_str, exc_info=True)
