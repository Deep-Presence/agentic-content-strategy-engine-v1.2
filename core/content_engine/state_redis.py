"""Redis-backed pipeline state helpers.

Drop-in replacements for _write_pipeline_state / _cleanup_pipeline_state
from state_helpers.py. Used when Redis is available; file-based fallback
otherwise.

Redis Hash structure for ``pipeline_state:{effective_slug}``:
  - ``brief-001`` → ``"generating"`` (status string)
  - ``__tid:brief-001`` → ``"task-uuid"`` (task ID for HITL discovery)

The ``__tid:`` prefix avoids collision with brief IDs. Readers reconstruct
the ``__task_ids__`` nested dict for backward compatibility with existing
content data service code.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.models.pipeline_status import BriefPipelineStatus

logger = logging.getLogger(__name__)

_PIPELINE_STATE_PREFIX = "pipeline_state:"
_TID_PREFIX = "__tid:"
_STATE_TTL = 86400  # 24 hours
_MAX_SLUG_LENGTH = 256  # Defense-in-depth: prevent excessively long Redis keys

# Pre-compute valid status values for fast validation
_VALID_PHASES: frozenset[str] = frozenset(s.value for s in BriefPipelineStatus)


def _state_key(slug: str) -> str:
    """Build validated Redis key for pipeline state hash.

    Centralizes key construction and enforces length limits to prevent
    keyspace abuse from malformed slugs.
    """
    if len(slug) > _MAX_SLUG_LENGTH:
        raise ValueError(f"Slug too long for Redis key: {len(slug)} > {_MAX_SLUG_LENGTH}")
    return f"{_PIPELINE_STATE_PREFIX}{slug}"


# ── Write (sync) ──────────────────────────────────────────────────


def write_pipeline_state_redis(
    redis_sync: Any,
    slug: str,
    brief_ids: List[str],
    phase: str,
    *,
    task_id: Optional[str] = None,
) -> None:
    """Write per-brief status to Redis Hash (atomic via pipeline).

    Equivalent to ``_write_pipeline_state()`` in state_helpers.py.
    Validates phase against ``BriefPipelineStatus`` (warns but does not
    fail on unknown values, matching file-based behavior).
    """
    # Guard: detect async client passed by mistake (causes silent coroutine leak)
    import redis.asyncio as _aioredis

    if isinstance(redis_sync, _aioredis.Redis):
        raise TypeError(
            "write_pipeline_state_redis requires a sync Redis client, "
            "got async. Use write_pipeline_state_redis_async instead."
        )

    if phase not in _VALID_PHASES:
        logger.warning("write_pipeline_state_redis called with unknown phase %r", phase)

    key = _state_key(slug)
    pipe = redis_sync.pipeline()
    try:
        for bid in brief_ids:
            pipe.hset(key, bid, phase)
        if task_id:
            for bid in brief_ids:
                pipe.hset(key, f"{_TID_PREFIX}{bid}", task_id)
        pipe.expire(key, _STATE_TTL)
        pipe.execute()
    finally:
        # Ensure pipeline resources are released
        pass


# ── Cleanup (sync) ────────────────────────────────────────────────


def cleanup_pipeline_state_redis(
    redis_sync: Any,
    slug: str,
    brief_ids: List[str],
) -> None:
    """Remove specific brief IDs from Redis Hash.

    Equivalent to ``_cleanup_pipeline_state()`` in state_helpers.py.
    TTL handles final expiry — no explicit DELETE needed when hash empties.
    """
    if not brief_ids:
        return

    key = _state_key(slug)
    # Build field list: each brief_id + its __tid: counterpart
    fields = []
    for bid in brief_ids:
        fields.append(bid)
        fields.append(f"{_TID_PREFIX}{bid}")
    redis_sync.hdel(key, *fields)


# ── Write (async — for pipeline code running in event loop) ───────


async def write_pipeline_state_redis_async(
    redis_async: Any,
    slug: str,
    brief_ids: List[str],
    phase: str,
    *,
    task_id: Optional[str] = None,
) -> None:
    """Async write per-brief status to Redis Hash.

    Same logic as sync version but uses async Redis client. Avoids blocking
    the event loop in pipeline_v13/dispatcher/evaluator hot paths.
    """
    if phase not in _VALID_PHASES:
        logger.warning("write_pipeline_state_redis_async called with unknown phase %r", phase)

    key = _state_key(slug)
    pipe = redis_async.pipeline()
    for bid in brief_ids:
        pipe.hset(key, bid, phase)
    if task_id:
        for bid in brief_ids:
            pipe.hset(key, f"{_TID_PREFIX}{bid}", task_id)
    pipe.expire(key, _STATE_TTL)
    await pipe.execute()


# ── Cleanup (async) ──────────────────────────────────────────────


async def cleanup_pipeline_state_redis_async(
    redis_async: Any,
    slug: str,
    brief_ids: List[str],
) -> None:
    """Async remove specific brief IDs from Redis Hash."""
    if not brief_ids:
        return

    key = _state_key(slug)
    fields = []
    for bid in brief_ids:
        fields.append(bid)
        fields.append(f"{_TID_PREFIX}{bid}")
    await redis_async.hdel(key, *fields)


# ── Stale cleanup (async) ────────────────────────────────────────


async def cleanup_stale_pipeline_state_redis_async(
    redis_async: Any,
    slug: str,
    task_id: Optional[str] = None,
) -> None:
    """Async version: remove THIS run's brief entries from pipeline state hash.

    Same task-scoped logic as sync version.
    """
    key = _state_key(slug)
    if task_id is None:
        await redis_async.delete(key)
        return

    raw = await redis_async.hgetall(key)
    if not raw:
        return

    fields_to_delete: List[str] = []
    for field, value in raw.items():
        if field.startswith(_TID_PREFIX) and value == task_id:
            brief_id = field[len(_TID_PREFIX):]
            fields_to_delete.append(brief_id)
            fields_to_delete.append(field)

    if fields_to_delete:
        await redis_async.hdel(key, *fields_to_delete)


# ── Read (sync) ───────────────────────────────────────────────────


def read_pipeline_state_redis(
    redis_sync: Any,
    slug: str,
) -> Dict[str, Any]:
    """Read pipeline state from Redis Hash (sync).

    Returns dict in the same shape as what ``_infer_brief_status()`` expects:
    ``{"brief-001": "generating", "__task_ids__": {"brief-001": "task-uuid"}}``.

    Reconstructs ``__task_ids__`` from ``__tid:*`` fields for backward
    compatibility with existing reader code.
    """
    key = _state_key(slug)
    raw = redis_sync.hgetall(key)
    if not raw:
        return {}
    return _reconstruct_state(raw)


# ── Read (async) ──────────────────────────────────────────────────


async def read_pipeline_state_redis_async(
    redis_async: Any,
    slug: str,
) -> Dict[str, Any]:
    """Read pipeline state from Redis Hash (async).

    Same logic as ``read_pipeline_state_redis`` but uses async Redis client.
    For use in ``db_content_data.py`` which has async methods.
    """
    key = _state_key(slug)
    raw = await redis_async.hgetall(key)
    if not raw:
        return {}
    return _reconstruct_state(raw)


# ── Stale cleanup (sync) ──────────────────────────────────────────


def cleanup_stale_pipeline_state_redis(
    redis_sync: Any,
    slug: str,
    task_id: Optional[str] = None,
) -> None:
    """Remove THIS run's brief entries from pipeline state hash.

    Unlike the file-based version (which deletes the whole file), the Redis
    version only removes briefs belonging to ``task_id`` — identified via
    ``__tid:{brief_id}`` fields. This prevents clobbering other parallel
    manual runs sharing the same slug.

    Falls back to full ``DELETE`` only when ``task_id`` is None (unknown run).
    """
    key = _state_key(slug)
    if task_id is None:
        # No task_id → cannot scope cleanup → full delete (legacy behavior)
        redis_sync.delete(key)
        return

    # Scan hash for briefs belonging to this task_id
    raw = redis_sync.hgetall(key)
    if not raw:
        return

    fields_to_delete: List[str] = []
    for field, value in raw.items():
        if field.startswith(_TID_PREFIX):
            # This is a __tid:brief-001 → task_id mapping
            if value == task_id:
                brief_id = field[len(_TID_PREFIX):]
                fields_to_delete.append(brief_id)
                fields_to_delete.append(field)
        # Also check if a non-__tid field has no owner (orphaned from crash)
        # — leave it alone, it belongs to another run

    if fields_to_delete:
        redis_sync.hdel(key, *fields_to_delete)


# ── Internal helpers ──────────────────────────────────────────────


def _reconstruct_state(raw: Dict[str, str]) -> Dict[str, Any]:
    """Reconstruct pipeline state dict from flat Redis Hash fields.

    Separates ``__tid:*`` fields into a ``__task_ids__`` nested dict.
    """
    result: Dict[str, Any] = {}
    task_ids: Dict[str, str] = {}

    for field, value in raw.items():
        if field.startswith(_TID_PREFIX):
            brief_id = field[len(_TID_PREFIX):]
            task_ids[brief_id] = value
        else:
            result[field] = value

    if task_ids:
        result["__task_ids__"] = task_ids

    return result
