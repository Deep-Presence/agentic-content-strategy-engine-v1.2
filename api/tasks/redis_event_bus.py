"""Redis Streams-backed event bus for SSE streaming.

Drop-in replacement for EventBus. Uses Redis Streams (XADD/XREAD/XRANGE)
for cross-worker event delivery, persistence, and replay.

publish() is synchronous (fire-and-forget async write) to maintain
compatibility with all existing callers (~40+ call sites).

Event IDs: Globally monotonic via ``INCR sse:counter:{task_id}`` in Redis.
Atomic Lua script ensures INCR + XADD + EXPIRE execute as a single Redis
operation — no interleaving between concurrent coroutines.

In-memory mirror: Local counters for same-worker get_history()/is_terminal().
Mirror reads are thread-safe (``self._lock``). Mirror is bounded to
``_MAX_MIRROR_TASKS`` entries with oldest-terminal-first eviction.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from typing import Any, AsyncGenerator, Dict, List, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_TERMINAL_TYPES = {"completed", "failed", "cancelled"}
_STREAM_TTL = 86400  # 24 hours
_MAX_MIRROR_TASKS = 1000  # Max task entries in in-memory mirror

# Lua script: atomic INCR + XADD + 2x EXPIRE in single Redis round trip.
# Eliminates out-of-order writes when concurrent coroutines publish to the
# same task_id. Returns the globally monotonic event seq.
_PUBLISH_LUA = """\
local counter_key = KEYS[1]
local stream_key  = KEYS[2]
local event_type  = ARGV[1]
local event_data  = ARGV[2]
local max_len     = tonumber(ARGV[3])

local seq = redis.call('INCR', counter_key)
redis.call('XADD', stream_key, 'MAXLEN', '~', tostring(max_len), '*',
           'seq', tostring(seq), 'type', event_type, 'data', event_data)
redis.call('EXPIRE', stream_key, 86400)
redis.call('EXPIRE', counter_key, 86400)
return seq
"""


def _format_sse_from_fields(seq: int, fields: dict) -> str:
    """Format Redis Stream fields as an SSE string.

    MUST produce identical output to ``_format_sse()`` in event_bus.py.
    ``fields['data']`` is already JSON-serialized (stored by ``_apublish``).
    """
    lines = [
        f"id: {seq}",
        f"event: {fields['type']}",
        f"data: {fields['data']}",
        "",
        "",
    ]
    return "\n".join(lines)


class RedisEventBus:
    """Redis Streams-backed event bus — drop-in replacement for EventBus.

    Publishes events to a per-task Redis Stream (``sse:{task_id}``).
    Event IDs are globally monotonic via atomic Lua script
    (INCR + XADD + EXPIRE in single Redis call).

    Thread-safety: ``publish()`` acquires ``_lock`` around in-memory
    mirror updates. ``get_history()`` and ``is_terminal()`` also acquire
    the lock for safe concurrent reads. The async Redis write is
    fire-and-forget.

    Mirror eviction: Bounded to ``_MAX_MIRROR_TASKS``. When exceeded,
    oldest terminal task is evicted first; if none, oldest task regardless.
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        max_history: int = 200,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self._redis = redis
        self._max_history = max_history
        self._loop = loop  # Main event loop — captured at lifespan init
        self._lock = threading.Lock()  # Thread-safe mirror reads and writes
        # In-memory mirror for sync get_history()/is_terminal()
        self._history: Dict[str, deque] = {}
        self._counters: Dict[str, int] = {}
        self._task_order: List[str] = []  # FIFO for eviction
        # Register atomic Lua publish script
        self._publish_script = redis.register_script(_PUBLISH_LUA)

    # ── publish (synchronous) ──────────────────────────────────────

    def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Publish an event. Updates in-memory mirror synchronously, then
        fires-and-forgets an async Lua script (INCR + XADD + EXPIRE).

        Safe to call from both async context and worker threads
        (``asyncio.to_thread``).
        """
        # 1. Update in-memory mirror — thread-safe (local seq for mirror only)
        with self._lock:
            if task_id not in self._counters:
                self._counters[task_id] = 0
                self._history[task_id] = deque(maxlen=self._max_history)
                self._task_order.append(task_id)
                # Evict if over capacity
                if len(self._history) > _MAX_MIRROR_TASKS:
                    self._evict_one()
            self._counters[task_id] += 1
            local_seq = self._counters[task_id]
            event: Dict[str, Any] = {"id": local_seq, "type": event_type, "data": data}
            self._history[task_id].append(event)

        # 2. Fire-and-forget async Redis write (atomic Lua script)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._apublish(task_id, event_type, data))
        except RuntimeError:
            # Worker thread (asyncio.to_thread) — schedule on main loop
            if self._loop is not None and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._apublish(task_id, event_type, data),
                    self._loop,
                )
            else:
                logger.warning(
                    "No event loop available — Redis publish dropped for %s",
                    task_id,
                )

    async def _apublish(
        self,
        task_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Atomic Redis write via Lua: INCR → XADD → 2× EXPIRE."""
        counter_key = f"sse:counter:{task_id}"
        stream_key = f"sse:{task_id}"
        try:
            await self._publish_script(
                keys=[counter_key, stream_key],
                args=[event_type, json.dumps(data), self._max_history],
            )
        except Exception:
            logger.warning(
                "Redis publish failed for task %s",
                task_id,
                exc_info=True,
            )

    # ── eviction (called under self._lock) ─────────────────────────

    def _evict_one(self) -> None:
        """Evict one task from mirror. Prefer oldest terminal, else oldest any.

        MUST be called while ``self._lock`` is held.
        """
        # Prefer evicting oldest terminal task
        for tid in self._task_order:
            hist = self._history.get(tid)
            if hist and hist[-1].get("type", "") in _TERMINAL_TYPES:
                self._task_order.remove(tid)
                del self._history[tid]
                del self._counters[tid]
                return
        # No terminal found — evict oldest task regardless
        if self._task_order:
            tid = self._task_order.pop(0)
            self._history.pop(tid, None)
            self._counters.pop(tid, None)

    # ── stream (async generator) ───────────────────────────────────

    async def stream(
        self,
        task_id: str,
        last_event_id: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE-formatted event strings.

        Phase 1: Replay from Redis Stream via XRANGE.
        Phase 2: Live tail via XREAD with 15s heartbeat keepalive.
        Terminates after emitting a terminal event (completed/failed/cancelled).

        Redis errors are caught and logged — the SSE connection closes
        gracefully so the client can reconnect with Last-Event-ID.
        """
        key = f"sse:{task_id}"
        cutoff = last_event_id or 0

        try:
            # Phase 1: Replay from Redis Stream history.
            # XRANGE full-scan bounded by MAXLEN ~200 (sub-millisecond).
            # No way to map monotonic seq → Redis stream ID without reading.
            entries = await self._redis.xrange(key, min="-", max="+")
            for stream_id, fields in entries:
                seq = int(fields.get("seq", "0"))
                if seq > cutoff:
                    yield _format_sse_from_fields(seq, fields)
                    if fields.get("type") in _TERMINAL_TYPES:
                        return

            # Phase 2: Live tail via XREAD (block=15s for heartbeat)
            last_stream_id = entries[-1][0] if entries else "0"
            while True:
                results = await self._redis.xread(
                    {key: last_stream_id}, block=15000, count=10
                )
                if not results:
                    # 15s timeout — send SSE comment as keepalive
                    yield ": heartbeat\n\n"
                    continue
                for _, messages in results:
                    for stream_id, fields in messages:
                        last_stream_id = stream_id
                        seq = int(fields.get("seq", "0"))
                        if seq > cutoff:
                            yield _format_sse_from_fields(seq, fields)
                            if fields.get("type") in _TERMINAL_TYPES:
                                return
        except Exception:
            logger.exception(
                "Redis stream error for task %s — closing SSE connection",
                task_id,
            )
            # Generator ends — SSE connection closes, client can reconnect

    # ── get_history / is_terminal (thread-safe mirror reads) ───────

    def get_history(self, task_id: str) -> List[Dict[str, Any]]:
        """Return event history (from in-memory mirror, thread-safe).

        Note: Mirror uses local seq IDs. For cross-worker history,
        read from the Redis Stream directly.
        """
        with self._lock:
            if task_id not in self._history:
                return []
            return list(self._history[task_id])

    def is_terminal(self, task_id: str) -> bool:
        """Check if last event is terminal (thread-safe, independent lock)."""
        with self._lock:
            hist = self._history.get(task_id)
            if not hist:
                return False
            return hist[-1].get("type", "") in _TERMINAL_TYPES

    # ── subscribe / unsubscribe (no-ops) ───────────────────────────

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """No-op — RedisEventBus.stream() uses XREAD directly."""
        logger.debug(
            "subscribe() is a no-op on RedisEventBus — stream() uses XREAD"
        )
        return asyncio.Queue()

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        """No-op — RedisEventBus.stream() uses XREAD directly."""
        pass
