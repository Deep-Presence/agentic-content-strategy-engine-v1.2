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
) -> None:
    """Async write: writes to both async Redis AND sync file for resilience.

    Also refreshes the associated lock TTL on successful Redis write,
    preventing lock expiry during long HITL waits.
    """
    if redis_client is not None and effective_slug:
        try:
            from core.content_engine.state_redis import write_pipeline_state_redis_async

            await write_pipeline_state_redis_async(
                redis_client, effective_slug, brief_ids, phase, task_id=task_id
            )
            # Refresh associated lock TTL (prevents expiry during HITL waits)
            try:
                await redis_client.expire(
                    f"lock:content_v13:{effective_slug}", _LOCK_TTL
                )
            except Exception:
                pass  # Best-effort refresh
        except Exception:
            logger.warning(
                "Redis pipeline state write failed — file write still proceeds",
                exc_info=True,
            )

    # File write (ALWAYS runs — ensures fallback is never stale)
    _write_pipeline_state(artifact_dir, brief_ids, phase, task_id=task_id)


async def _cleanup_pipeline_state_async(
    artifact_dir: Path,
    brief_ids: List[str],
    *,
    redis_client: Optional[Any] = None,
    effective_slug: Optional[str] = None,
) -> None:
    """Async cleanup: tries async Redis first, always cleans file too."""
    if redis_client is not None and effective_slug:
        try:
            from core.content_engine.state_redis import cleanup_pipeline_state_redis_async

            await cleanup_pipeline_state_redis_async(
                redis_client, effective_slug, brief_ids
            )
        except Exception:
            logger.warning(
                "Redis pipeline state cleanup failed — falling back to file",
                exc_info=True,
            )

    # File-based cleanup (always runs as safety net)
    _cleanup_pipeline_state(artifact_dir, brief_ids)
