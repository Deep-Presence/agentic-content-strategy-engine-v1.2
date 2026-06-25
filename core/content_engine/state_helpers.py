"""Shared state helpers for the v1.3 content engine.

Extracted from pipeline_v13.py to allow both the pipeline orchestrator
and the worker dispatcher to use these without circular imports.
"""

from __future__ import annotations

import json
from pathlib import Path
import logging
from typing import Any, Dict, List, Optional

from core.models.pipeline_status import BriefPipelineStatus

logger = logging.getLogger(__name__)

# Pre-compute valid status values from the canonical enum for fast validation
_VALID_PHASES: frozenset[str] = frozenset(s.value for s in BriefPipelineStatus)


def _emit(event_bus: Any, task_id: Optional[str], event_type: str, data: Dict[str, Any]) -> None:
    """Publish an SSE event if event_bus and task_id are available."""
    if event_bus and task_id:
        event_bus.publish(task_id, event_type, data)


def _emit_company(company_slug: str, event_type: str, data: Dict[str, Any]) -> None:
    """Broadcast an event on the company-wide SSE stream.

    Sync — safe to call from both sync and async contexts.
    Best-effort: import/emit failures are logged, never propagated.
    """
    try:
        from core.events.company_event_bus import company_event_bus, CompanyEvent
        company_event_bus.emit(company_slug, CompanyEvent(event_type=event_type, data=data))
    except Exception:
        logger.debug("Company event emit failed for %s", company_slug, exc_info=True)


async def _sync_td_topic_runs_for_briefs(
    *,
    session_factory: Any,
    effective_slug: str,
    brief_ids: List[str],
    phase: str,
    task_id: str,
) -> List[Dict[str, Any]]:
    """Best-effort durable stage propagation for TD-entry Content Engine runs."""
    try:
        from core.services.content_engine_topic_runs import ContentEngineTopicRunService

        service = ContentEngineTopicRunService(session_factory)
        snapshots = await service.advance_topic_runs_by_brief_ids(
            effective_slug=effective_slug,
            brief_ids=brief_ids,
            status=phase,
            stage=phase,
            pipeline_task_id=task_id,
            match_pipeline_task_id=task_id,
            event_type="topic_run_changed",
            payload_json={"source": "pipeline_state_write"},
        )
        return [
            {
                "topic_run_id": s.topic_run_id,
                "batch_run_id": s.batch_run_id,
                "topic_assignment_id": s.topic_assignment_id,
                "display_id": s.display_id,
                "topic_text": s.topic_text,
                "brief_id": s.brief_id,
                "ga_run_id": s.ga_run_id,
                "pipeline_task_id": s.pipeline_task_id,
                "status": s.status,
                "stage": s.stage,
                "seq": s.seq,
                "content_piece_id": s.content_piece_id,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "effective_slug": effective_slug,
            }
            for s in snapshots
        ]
    except Exception:
        logger.warning(
            "Durable topic-run stage propagation failed for slug=%s phase=%s",
            effective_slug,
            phase,
            exc_info=True,
        )
        return []


def _write_pipeline_state(
    artifact_dir: Path,
    brief_ids: List[str],
    phase: str,
    *,
    task_id: Optional[str] = None,
    redis_client: Optional[Any] = None,
    effective_slug: Optional[str] = None,
) -> None:
    """Write per-brief status to pipeline_state.json (or Redis Hash).

    This file is the highest-priority status source during pipeline execution.
    It is read by content_data_service._infer_brief_status() as Phase 0
    (before pieces and file-based inference).

    Merges with existing state to support concurrent manual runs.
    Cleaned up by _cleanup_pipeline_state once run_metadata_v13.json is written.

    When *task_id* is provided, the mapping brief_id → task_id is stored under
    the reserved ``__task_ids__`` key so the frontend can discover the pipeline
    run_id for HITL approval calls.

    When *redis_client* and *effective_slug* are provided, writes to both
    Redis Hash AND file for fallback resilience.
    """
    # Try Redis (when configured) — primary state store
    redis_succeeded = False
    if redis_client is not None and effective_slug:
        try:
            from core.content_engine.state_redis import write_pipeline_state_redis

            write_pipeline_state_redis(
                redis_client, effective_slug, brief_ids, phase, task_id=task_id
            )
            redis_succeeded = True
        except Exception:
            logger.warning(
                "Redis pipeline state write failed — falling back to file",
                exc_info=True,
            )

    # File write — only when Redis is unavailable (fallback for dev/no-Redis)
    if redis_succeeded:
        return
    state_path = artifact_dir / "pipeline_state.json"
    existing: Dict[str, Any] = {}
    if state_path.is_file():
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                existing = raw
        except (json.JSONDecodeError, OSError):
            pass
    if phase not in _VALID_PHASES:
        logger.warning("_write_pipeline_state called with unknown phase %r", phase)
    for bid in brief_ids:
        existing[bid] = phase
    # Store brief_id → task_id mapping for frontend HITL approval discovery
    if task_id:
        task_map: Dict[str, str] = existing.get("__task_ids__", {})
        if not isinstance(task_map, dict):
            task_map = {}
        for bid in brief_ids:
            task_map[bid] = task_id
        existing["__task_ids__"] = task_map
    state_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _cleanup_pipeline_state(
    artifact_dir: Path,
    brief_ids: List[str],
    *,
    redis_client: Optional[Any] = None,
    effective_slug: Optional[str] = None,
) -> None:
    """Remove specific brief IDs from pipeline_state.json (or Redis Hash).

    Only deletes the file if no entries remain — concurrency-safe for parallel
    manual runs where another run may still have in-flight state.
    Also cleans up corresponding ``__task_ids__`` entries.

    When *redis_client* and *effective_slug* are provided, cleans up in Redis
    first. Falls back to file on Redis failure. On error paths, cleans BOTH
    Redis and file to prevent stale data resurrection.
    """
    # Try Redis cleanup (when configured) — primary state store
    redis_succeeded = False
    if redis_client is not None and effective_slug:
        try:
            from core.content_engine.state_redis import cleanup_pipeline_state_redis

            cleanup_pipeline_state_redis(redis_client, effective_slug, brief_ids)
            redis_succeeded = True
        except Exception:
            logger.warning(
                "Redis pipeline state cleanup failed — falling back to file",
                exc_info=True,
            )

    # File-based cleanup — only when Redis is unavailable (fallback for dev/no-Redis)
    if redis_succeeded:
        return
    state_path = artifact_dir / "pipeline_state.json"
    if not state_path.is_file():
        return
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        existing = raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        existing = {}
    for bid in brief_ids:
        existing.pop(bid, None)
    # Also clean up __task_ids__ entries
    task_map = existing.get("__task_ids__")
    if isinstance(task_map, dict):
        for bid in brief_ids:
            task_map.pop(bid, None)
        if not task_map:
            existing.pop("__task_ids__", None)
    # Check if only __task_ids__ remains (no active briefs)
    remaining_briefs = {k for k in existing if k != "__task_ids__"}
    if remaining_briefs:
        state_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    else:
        try:
            state_path.unlink()
        except OSError:
            pass


# ── Async wrappers (use async Redis, avoid blocking event loop) ──

_LOCK_TTL = 7200  # 2 hours — must match db_task_store.py


async def _write_pipeline_state_async(
    artifact_dir: Path,
    brief_ids: List[str],
    phase: str,
    *,
    task_id: Optional[str] = None,
    redis_client: Optional[Any] = None,
    effective_slug: Optional[str] = None,
    session_factory: Optional[Any] = None,
) -> None:
    """Async write: writes to Redis (primary). File only when Redis unavailable.

    Also refreshes the associated lock TTL on successful Redis write,
    preventing lock expiry during long HITL waits.

    Safety net: when *redis_client* is None but Redis is configured,
    self-acquires the async singleton so callers that forget to pass
    redis_client (e.g. orchestrator paths) still get Redis writes.

    File writes are a dev/no-Redis fallback only — never unconditional.
    Readers (get_briefs) use Redis exclusively when available; stale file
    entries from prior runs caused 4-min kanban sync lag.
    """
    # Self-acquire async Redis when caller doesn't provide one.
    _rc = redis_client
    if _rc is None and effective_slug:
        try:
            from core.config.settings import settings as _cfg
            if _cfg.redis_pipeline_state and _cfg.redis_url:
                from core.redis import get_redis_or_none
                _rc = get_redis_or_none()
        except Exception:
            pass  # Best-effort — fall through to file write

    redis_succeeded = False
    if _rc is not None and effective_slug:
        try:
            from core.content_engine.state_redis import write_pipeline_state_redis_async

            await write_pipeline_state_redis_async(
                _rc, effective_slug, brief_ids, phase, task_id=task_id
            )
            redis_succeeded = True
            # Refresh associated lock TTL (prevents expiry during HITL waits)
            try:
                await _rc.expire(
                    f"lock:content_v13:{effective_slug}", _LOCK_TTL
                )
            except Exception:
                pass  # Best-effort refresh
        except Exception:
            logger.warning(
                "Redis pipeline state write failed — falling back to file",
                exc_info=True,
            )

    # File write ONLY when Redis is unavailable (dev / no-Redis fallback)
    if not redis_succeeded:
        _write_pipeline_state(artifact_dir, brief_ids, phase, task_id=task_id)

    topic_run_events: List[Dict[str, Any]] = []
    if session_factory is not None and effective_slug and task_id:
        topic_run_events = await _sync_td_topic_runs_for_briefs(
            session_factory=session_factory,
            effective_slug=effective_slug,
            brief_ids=brief_ids,
            phase=phase,
            task_id=task_id,
        )

    # ── Company-wide SSE broadcast ──
    if effective_slug:
        try:
            company_slug = effective_slug.split("__")[0]
            for item in topic_run_events:
                _emit_company(company_slug, "topic_run_changed", item)
            _emit_company(company_slug, "state_changed", {
                "changed": brief_ids,
                "hint": phase,
            })
        except Exception:
            pass  # Best-effort — never fail the state write for an SSE emit


async def _cleanup_pipeline_state_async(
    artifact_dir: Path,
    brief_ids: List[str],
    *,
    redis_client: Optional[Any] = None,
    effective_slug: Optional[str] = None,
) -> None:
    """Async cleanup: Redis primary. File only when Redis unavailable.

    Safety net: self-acquires async Redis when *redis_client* is None
    (same pattern as ``_write_pipeline_state_async``).
    """
    _rc = redis_client
    if _rc is None and effective_slug:
        try:
            from core.config.settings import settings as _cfg
            if _cfg.redis_pipeline_state and _cfg.redis_url:
                from core.redis import get_redis_or_none
                _rc = get_redis_or_none()
        except Exception:
            pass

    redis_succeeded = False
    if _rc is not None and effective_slug:
        try:
            from core.content_engine.state_redis import cleanup_pipeline_state_redis_async

            await cleanup_pipeline_state_redis_async(
                _rc, effective_slug, brief_ids
            )
            redis_succeeded = True
        except Exception:
            logger.warning(
                "Redis pipeline state cleanup failed — falling back to file",
                exc_info=True,
            )

    # File cleanup ONLY when Redis is unavailable
    if not redis_succeeded:
        _cleanup_pipeline_state(artifact_dir, brief_ids)
