"""DB persistence hooks for the content generation pipeline.

After the content pipeline writes its JSON/filesystem artifacts, optionally
persist the same data into Postgres tables so ``DbContentDataService``
serves real data to the dashboard API.

Design principles match ``core/gap_analysis/persistence.py``:
- Filesystem-first, DB-additive
- Graceful degradation — DB errors NEVER crash the pipeline
- Per-function transaction isolation
- Idempotent re-persist via delete-before-insert
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Optional

# delete import removed — persist_content_pieces now uses upsert, not delete-recreate
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


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


def _map_content_status(status_value: str) -> Any:
    """Map Pydantic ContentStatus to ORM ContentPieceStatus."""
    from core.db.enums import ContentPieceStatus

    status_map = {
        "approved": ContentPieceStatus.approved,
        "rejected": ContentPieceStatus.review,  # no 'rejected' in ORM — map to review
        "edited": ContentPieceStatus.approved,   # edited → approved
        "draft": ContentPieceStatus.drafting,
    }
    try:
        return status_map.get(status_value.lower(), ContentPieceStatus.planned)
    except (AttributeError, ValueError):
        return ContentPieceStatus.planned


async def persist_blueprints_early(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    blueprints: list,
) -> None:
    """Persist blueprint placeholders to content_pieces BEFORE HITL-2.

    Creates minimal ContentPiece records so ``DbContentDataService.get_briefs()``
    returns them during the HITL-2 approval pause. Pipeline state in Redis
    overrides the display status to ``pending_brief_approval``.

    Uses upsert by (effective_slug, brief_id) — safe to call even if records
    already exist from a previous run.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.repositories.content_repo import ContentRepository
        from core.db.enums import ContentPieceStatus

        async with session_factory() as session:
            repo = ContentRepository(session)
            for bp in blueprints:
                brief_id = bp.brief_id if hasattr(bp, "brief_id") else bp.get("brief_id", "")
                title = bp.title if hasattr(bp, "title") else bp.get("title", "")
                content_format = (
                    bp.content_format if hasattr(bp, "content_format")
                    else bp.get("content_format", "long_blog")
                )
                cluster = (
                    bp.target_cluster if hasattr(bp, "target_cluster")
                    else bp.get("target_cluster", "")
                )
                ta_id_raw = getattr(bp, "topic_assignment_id", None) or bp.get("topic_assignment_id") if isinstance(bp, dict) else getattr(bp, "topic_assignment_id", None)
                ta_id: _uuid.UUID | None = None
                if ta_id_raw:
                    try:
                        ta_id = _uuid.UUID(str(ta_id_raw))
                    except (ValueError, AttributeError):
                        ta_id = None

                # Extract brief metadata for the detail endpoint
                # so it works without the blueprints.json fallback
                # (concurrent pipelines cause file race conditions).
                _bp_dict = bp if isinstance(bp, dict) else (
                    bp.model_dump(mode="json") if hasattr(bp, "model_dump") else {}
                )
                eval_data = {}
                if _bp_dict.get("key_topics"):
                    eval_data["key_topics"] = _bp_dict["key_topics"]
                if _bp_dict.get("key_angles"):
                    eval_data["key_angles"] = _bp_dict["key_angles"]
                wc = _bp_dict.get("word_count_range")
                if wc:
                    if isinstance(wc, (list, tuple)) and len(wc) >= 2:
                        eval_data["word_count_range"] = {"min": wc[0], "max": wc[1]}
                    elif isinstance(wc, dict):
                        eval_data["word_count_range"] = wc
                if _bp_dict.get("priority_score") is not None:
                    eval_data["priority_score"] = _bp_dict["priority_score"]
                if _bp_dict.get("structural_targets") is not None:
                    eval_data["structural_targets"] = _bp_dict["structural_targets"]

                existing = await repo.get_by_slug_and_brief_id(slug, brief_id)
                if existing:
                    existing.run_id = run_id
                    existing.title = title
                    existing.company_id = company_id
                    existing.cluster_name = cluster
                    existing.content_type = content_format
                    existing.topic_assignment_id = ta_id
                    if eval_data:
                        existing.evaluation_results = {
                            **(existing.evaluation_results or {}),
                            **eval_data,
                        }
                    await session.flush()
                else:
                    await repo.create_piece(
                        run_id=run_id,
                        effective_slug=slug,
                        brief_id=brief_id,
                        company_id=company_id,
                        title=title,
                        status=ContentPieceStatus.planned,
                        content_type=content_format,
                        cluster_name=cluster,
                        topic_assignment_id=ta_id,
                        evaluation_results=eval_data or None,
                    )
            await session.commit()
        logger.info(
            "persist_blueprints_early: %d placeholders stored for %s",
            len(blueprints), slug,
        )
    except Exception:
        logger.warning(
            "persist_blueprints_early failed for %s, continuing without DB",
            slug, exc_info=True,
        )


async def persist_content_pieces(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    pieces: list,
) -> None:
    """Persist content pieces → content_pieces table.

    Uses upsert by (effective_slug, brief_id) to preserve existing IDs
    and FK relationships (e.g., query_gaps.targeted_by_content_id,
    content_artifacts.piece_id). No DELETE — only update-or-insert.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.repositories.content_repo import ContentRepository

        async with session_factory() as session:
            repo = ContentRepository(session)
            for piece in pieces:
                status_val = piece.status.value if hasattr(piece.status, "value") else str(piece.status)
                eval_summary = getattr(piece, "eval_summary", None)
                if eval_summary and hasattr(eval_summary, "model_dump"):
                    eval_summary = eval_summary.model_dump(mode="json")

                ta_id_raw = getattr(piece, "topic_assignment_id", None)
                ta_id: _uuid.UUID | None = None
                if ta_id_raw:
                    try:
                        ta_id = _uuid.UUID(str(ta_id_raw))
                    except (ValueError, AttributeError):
                        ta_id = None

                word_count = len(piece.final_markdown.split()) if piece.final_markdown else 0
                mapped_status = _map_content_status(status_val)

                # Upsert: find existing by (slug, brief_id), patch fields, preserve ID
                existing = await repo.get_by_slug_and_brief_id(slug, piece.brief_id)
                if existing:
                    existing.run_id = run_id
                    existing.title = piece.title
                    existing.status = mapped_status
                    existing.storage_key = getattr(piece, "artifact_path", None)
                    existing.word_count = word_count
                    existing.evaluation_results = eval_summary
                    existing.topic_assignment_id = ta_id
                    existing.company_id = company_id
                    await session.flush()
                else:
                    await repo.create_piece(
                        run_id=run_id,
                        effective_slug=slug,
                        brief_id=piece.brief_id,
                        company_id=company_id,
                        title=piece.title,
                        status=mapped_status,
                        storage_key=getattr(piece, "artifact_path", None),
                        word_count=word_count,
                        evaluation_results=eval_summary,
                        revision_count=0,
                        topic_assignment_id=ta_id,
                    )
            await session.commit()
        logger.info(
            "persist_content_pieces: %d pieces stored for %s", len(pieces), slug
        )
    except Exception:
        logger.warning(
            "persist_content_pieces failed for %s, continuing without DB",
            slug, exc_info=True,
        )


async def persist_content_run_summary(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    total_briefs: int,
    total_approved: int,
    total_rejected: int,
) -> None:
    """Update PipelineRunModel with content generation summary."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.enums import PipelineStatus
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run is None:
                logger.warning(
                    "persist_content_run_summary: PipelineRunModel %s not found",
                    run_id,
                )
                return

            run.summary = {
                "total_briefs": total_briefs,
                "total_approved": total_approved,
                "total_rejected": total_rejected,
            }
            run.status = PipelineStatus.completed
            run.completed_at = datetime.now(tz=timezone.utc)
            run.stages_executed = [
                "stage1_planner", "stage2_workers",
                "stage3_evaluator", "stage4_review",
            ]
            await session.commit()
        logger.info("persist_content_run_summary: run updated for %s", slug)
    except Exception:
        logger.warning(
            "persist_content_run_summary failed for %s, continuing without DB",
            slug, exc_info=True,
        )


# ── v1.3 persistence hooks ───────────────────────────────────────────


async def persist_v13_planner_output(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    planner_output: dict,
    approval_decision: str,
    approved_topic_ranks: list,
) -> None:
    """Persist Strategic Planner output + HITL-1 decision to PipelineRunModel.config JSONB.

    Writes to ``config["v13_planner"]`` so it doesn't collide with
    existing config fields.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run is None:
                logger.warning(
                    "persist_v13_planner_output: PipelineRunModel %s not found", run_id
                )
                return

            config = dict(run.config or {})
            config["v13_planner"] = {
                "selections": planner_output,
                "approval_decision": approval_decision,
                "approved_topic_ranks": approved_topic_ranks,
            }
            run.config = config
            await session.commit()
        logger.info("persist_v13_planner_output: stored for %s", slug)
    except Exception:
        logger.warning(
            "persist_v13_planner_output failed for %s, continuing without DB",
            slug, exc_info=True,
        )


async def persist_v13_brief_approval(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    blueprints: list,
    approval_decisions: list,
) -> None:
    """Persist Brief Builder output + HITL-2 decisions to PipelineRunModel.config JSONB.

    Writes to ``config["v13_briefs"]``.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run is None:
                logger.warning(
                    "persist_v13_brief_approval: PipelineRunModel %s not found", run_id
                )
                return

            config = dict(run.config or {})
            config["v13_briefs"] = {
                "blueprints": blueprints,
                "approval_decisions": approval_decisions,
            }
            run.config = config
            await session.commit()
        logger.info("persist_v13_brief_approval: stored for %s", slug)
    except Exception:
        logger.warning(
            "persist_v13_brief_approval failed for %s, continuing without DB",
            slug, exc_info=True,
        )
