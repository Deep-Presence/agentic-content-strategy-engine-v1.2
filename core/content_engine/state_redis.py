"""Redis-backed pipeline state helpers.

Drop-in replacements for _write_pipeline_state / _cleanup_pipeline_state
from state_helpers.py. Used when Redis is available; file-based fallback
otherwise.

Redis Hash structure for ``pipeline_state:{effective_slug}``:
  - ``brief-001`` → ``"generating"`` (status string)
  - ``__tid:brief-001`` → ``"task-uuid"`` (task ID for HITL discovery)
  - ``ta-{uuid}`` → ``"gap_analysis"`` (GA-phase topic assignment card)
  - ``__tid:ta-{uuid}`` → ``"ga-task-uuid"`` (GA task ID for SSE)
  - ``__meta:ta-{uuid}`` → JSON ``{"title": "...", "cluster": "...", ...}``

The ``__tid:`` prefix avoids collision with brief IDs. Readers reconstruct
the ``__task_ids__`` nested dict for backward compatibility with existing
content data service code.

GA-phase cards use ``ta-{topic_assignment_id}`` keys and coexist with
``brief-NNN`` keys in the same hash. ``__meta:`` entries store topic
metadata needed to render cards before CE creates real briefs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
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
        logger.warning(
            "cleanup_stale_pipeline_state_redis_async called without task_id for slug=%r; "
            "skipping to avoid clobbering other runs' state",
            slug,
        )
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
        # No task_id → cannot scope cleanup → skip to avoid clobbering
        # other runs. Callers MUST pass task_id for safe scoped cleanup.
        logger.warning(
            "cleanup_stale_pipeline_state_redis called without task_id for slug=%r; "
            "skipping to avoid clobbering other runs' state",
            slug,
        )
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


# ── GA-phase state (sync) ────────────────────────────────────────


_META_PREFIX = "__meta:"
_GA_CARD_PREFIX = "ta-"

# Valid GA-phase status values
_GA_PHASES: frozenset[str] = frozenset({
    "gap_analysis_pending",
    "gap_analysis",
    "gap_analysis_complete",
    "content_queued",
    "briefing",
})


def _ga_meta_key(card_key: str) -> str:
    return f"{_META_PREFIX}{card_key}"


def _parse_ga_meta(raw_meta: Any) -> Dict[str, Any]:
    if not raw_meta:
        return {}
    try:
        return json.loads(raw_meta)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _merge_ga_meta(
    existing_meta: Dict[str, Any],
    incoming_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    merged = dict(existing_meta)
    if incoming_meta:
        merged.update(incoming_meta)
    merged["created_at"] = existing_meta.get("created_at") or merged.get("created_at") or now_iso
    merged["updated_at"] = now_iso
    return merged


def write_ga_phase_state(
    redis_sync: Any,
    slug: str,
    assignment_ids: List[str],
    phase: str,
    *,
    task_id: Optional[str] = None,
    topic_data: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    """Write GA-phase topic assignment card state to Redis Hash.

    Keys use ``ta-{topic_assignment_id}`` prefix to coexist with
    ``brief-NNN`` keys in the same ``pipeline_state:{slug}`` hash.

    Args:
        redis_sync: Sync Redis client.
        slug: Effective slug (company or company__product).
        assignment_ids: List of topic_assignment_id UUIDs.
        phase: One of gap_analysis_pending, gap_analysis, gap_analysis_complete,
            content_queued, briefing.
        task_id: GA task_id for SSE subscription.
        topic_data: Optional dict mapping assignment_id → metadata dict
            (keys: title, cluster, priority_score, buyer_stage, ga_run_id).
    """
    import redis.asyncio as _aioredis

    if isinstance(redis_sync, _aioredis.Redis):
        raise TypeError(
            "write_ga_phase_state requires a sync Redis client, "
            "got async. Use write_ga_phase_state_async instead."
        )

    if phase not in _GA_PHASES:
        logger.warning("write_ga_phase_state called with unknown phase %r", phase)

    key = _state_key(slug)
    pipe = redis_sync.pipeline()
    try:
        for aid in assignment_ids:
            card_key = f"{_GA_CARD_PREFIX}{aid}"
            pipe.hset(key, card_key, phase)
            if task_id:
                pipe.hset(key, f"{_TID_PREFIX}{card_key}", task_id)
            existing_meta = _parse_ga_meta(redis_sync.hget(key, _ga_meta_key(card_key)))
            merged_meta = _merge_ga_meta(
                existing_meta,
                topic_data.get(aid) if topic_data else None,
            )
            pipe.hset(
                key,
                _ga_meta_key(card_key),
                json.dumps(merged_meta, default=str),
            )
        pipe.expire(key, _STATE_TTL)
        pipe.execute()
    finally:
        pass


def read_ga_phase_cards(
    redis_sync: Any,
    slug: str,
) -> List[Dict[str, Any]]:
    """Read GA-phase card entries from the pipeline state hash.

    Returns a list of dicts, each containing:
    - ``id``: ``ta-{topic_assignment_id}``
    - ``status``: gap_analysis_pending | gap_analysis | gap_analysis_complete
      | content_queued | briefing
    - ``task_id``: GA task_id (if set)
    - ``title``, ``cluster``, ``priority_score``, ``buyer_stage``, ``ga_run_id``:
      from ``__meta:ta-*`` entries (if available)

    Only returns entries whose status is in _GA_PHASES.
    """
    key = _state_key(slug)
    raw = redis_sync.hgetall(key)
    if not raw:
        return []

    # Collect card IDs, task IDs, and metadata
    ga_cards: Dict[str, str] = {}  # card_key → status
    task_ids: Dict[str, str] = {}  # card_key → task_id
    meta: Dict[str, Dict[str, Any]] = {}  # card_key → metadata

    for field, value in raw.items():
        if field.startswith(_META_PREFIX):
            card_key = field[len(_META_PREFIX):]
            if card_key.startswith(_GA_CARD_PREFIX):
                try:
                    meta[card_key] = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    meta[card_key] = {}
        elif field.startswith(_TID_PREFIX):
            target = field[len(_TID_PREFIX):]
            if target.startswith(_GA_CARD_PREFIX):
                task_ids[target] = value
        elif field.startswith(_GA_CARD_PREFIX):
            if value in _GA_PHASES:
                ga_cards[field] = value

    result: List[Dict[str, Any]] = []
    for card_key, status in ga_cards.items():
        card: Dict[str, Any] = {
            "id": card_key,
            "status": status,
            "task_id": task_ids.get(card_key),
        }
        card_meta = meta.get(card_key, {})
        card["title"] = card_meta.get("title", "")
        card["cluster"] = card_meta.get("cluster", "")
        card["priority_score"] = card_meta.get("priority_score", 0.0)
        card["buyer_stage"] = card_meta.get("buyer_stage")
        card["ga_run_id"] = card_meta.get("ga_run_id")
        card["created_at"] = card_meta.get("created_at", "")
        card["updated_at"] = card_meta.get("updated_at", card["created_at"])
        card["topic_assignment_id"] = card_key[len(_GA_CARD_PREFIX):]
        # Pass through enriched metadata for Content Studio sidebar
        for extra_key in (
            "display_id",
            "intent_type", "persona_name", "persona_id",
            "persona_affinity", "priority_factors",
            "content_format", "estimated_word_count",
            "citation_opportunity", "description",
            "target_keywords", "content_angle",
        ):
            if extra_key in card_meta:
                card[extra_key] = card_meta[extra_key]
        result.append(card)

    return result


def cleanup_ga_phase_state(
    redis_sync: Any,
    slug: str,
    assignment_ids: List[str],
) -> None:
    """Remove GA-phase entries for given assignments (graduation to CE).

    Removes ``ta-{id}``, ``__tid:ta-{id}``, and ``__meta:ta-{id}`` fields.
    """
    if not assignment_ids:
        return

    key = _state_key(slug)
    fields: List[str] = []
    for aid in assignment_ids:
        card_key = f"{_GA_CARD_PREFIX}{aid}"
        fields.append(card_key)
        fields.append(f"{_TID_PREFIX}{card_key}")
        fields.append(f"{_META_PREFIX}{card_key}")
    redis_sync.hdel(key, *fields)


# ── GA-phase state (async) ───────────────────────────────────────


async def write_ga_phase_state_async(
    redis_async: Any,
    slug: str,
    assignment_ids: List[str],
    phase: str,
    *,
    task_id: Optional[str] = None,
    topic_data: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    """Async variant of write_ga_phase_state."""
    if phase not in _GA_PHASES:
        logger.warning("write_ga_phase_state_async called with unknown phase %r", phase)

    key = _state_key(slug)
    pipe = redis_async.pipeline()
    for aid in assignment_ids:
        card_key = f"{_GA_CARD_PREFIX}{aid}"
        pipe.hset(key, card_key, phase)
        if task_id:
            pipe.hset(key, f"{_TID_PREFIX}{card_key}", task_id)
        existing_meta = _parse_ga_meta(await redis_async.hget(key, _ga_meta_key(card_key)))
        merged_meta = _merge_ga_meta(
            existing_meta,
            topic_data.get(aid) if topic_data else None,
        )
        pipe.hset(
            key,
            _ga_meta_key(card_key),
            json.dumps(merged_meta, default=str),
        )
    pipe.expire(key, _STATE_TTL)
    await pipe.execute()


async def read_ga_phase_cards_async(
    redis_async: Any,
    slug: str,
) -> List[Dict[str, Any]]:
    """Async variant of read_ga_phase_cards."""
    key = _state_key(slug)
    raw = await redis_async.hgetall(key)
    if not raw:
        return []

    ga_cards: Dict[str, str] = {}
    task_ids: Dict[str, str] = {}
    meta: Dict[str, Dict[str, Any]] = {}

    for field, value in raw.items():
        if field.startswith(_META_PREFIX):
            card_key = field[len(_META_PREFIX):]
            if card_key.startswith(_GA_CARD_PREFIX):
                try:
                    meta[card_key] = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    meta[card_key] = {}
        elif field.startswith(_TID_PREFIX):
            target = field[len(_TID_PREFIX):]
            if target.startswith(_GA_CARD_PREFIX):
                task_ids[target] = value
        elif field.startswith(_GA_CARD_PREFIX):
            if value in _GA_PHASES:
                ga_cards[field] = value

    result: List[Dict[str, Any]] = []
    for card_key, status in ga_cards.items():
        card: Dict[str, Any] = {
            "id": card_key,
            "status": status,
            "task_id": task_ids.get(card_key),
        }
        card_meta = meta.get(card_key, {})
        card["title"] = card_meta.get("title", "")
        card["cluster"] = card_meta.get("cluster", "")
        card["priority_score"] = card_meta.get("priority_score", 0.0)
        card["buyer_stage"] = card_meta.get("buyer_stage")
        card["ga_run_id"] = card_meta.get("ga_run_id")
        card["created_at"] = card_meta.get("created_at", "")
        card["updated_at"] = card_meta.get("updated_at", card["created_at"])
        card["topic_assignment_id"] = card_key[len(_GA_CARD_PREFIX):]
        # Pass through enriched metadata for Content Studio sidebar
        for extra_key in (
            "display_id",
            "intent_type", "persona_name", "persona_id",
            "persona_affinity", "priority_factors",
            "content_format", "estimated_word_count",
            "citation_opportunity", "description",
            "target_keywords", "content_angle",
        ):
            if extra_key in card_meta:
                card[extra_key] = card_meta[extra_key]
        result.append(card)

    return result


async def cleanup_ga_phase_state_async(
    redis_async: Any,
    slug: str,
    assignment_ids: List[str],
) -> None:
    """Async variant of cleanup_ga_phase_state."""
    if not assignment_ids:
        return

    key = _state_key(slug)
    fields: List[str] = []
    for aid in assignment_ids:
        card_key = f"{_GA_CARD_PREFIX}{aid}"
        fields.append(card_key)
        fields.append(f"{_TID_PREFIX}{card_key}")
        fields.append(f"{_META_PREFIX}{card_key}")
    await redis_async.hdel(key, *fields)
