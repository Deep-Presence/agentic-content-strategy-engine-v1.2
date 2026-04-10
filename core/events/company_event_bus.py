"""Company-wide event bus for Content Studio and planner orchestration.

Production uses Redis Streams for cross-worker fanout and replay.
Tests may instantiate the bus without Redis, in which case a bounded
in-memory queue path is used.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

import redis.asyncio as aioredis
import redis.exceptions as redis_exceptions

from core.config.settings import settings

logger = logging.getLogger(__name__)

_STREAM_TTL = 86400  # 24 hours
_DEFAULT_HISTORY = 200
_SOCKET_TIMEOUT_BUFFER_MS = 1000
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


@dataclass
class CompanyEvent:
    """Lightweight event published by pipelines for a company."""

    event_type: str
    data: dict = field(default_factory=dict)


@dataclass
class StreamedCompanyEvent:
    """Sequenced company event used by the SSE stream."""

    seq: int
    event_type: str
    data: dict = field(default_factory=dict)


class CompanyEventBus:
    """Redis Streams-backed company event bus with in-memory test fallback."""

    def __init__(
        self,
        *,
        redis: aioredis.Redis | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        max_history: int = _DEFAULT_HISTORY,
    ) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue[StreamedCompanyEvent]]] = {}
        self._local_counters: Dict[str, int] = {}
        self._redis: aioredis.Redis | None = None
        self._publish_script = None
        self._loop = loop
        self._max_history = max_history
        self._lock = threading.RLock()
        if redis is not None:
            self.configure(redis=redis, loop=loop)

    def configure(
        self,
        *,
        redis: aioredis.Redis,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Configure Redis Streams as the backing transport."""
        self._redis = redis
        if loop is not None:
            self._loop = loop
        self._publish_script = redis.register_script(_PUBLISH_LUA)

    def subscribe(self, company_slug: str) -> asyncio.Queue[StreamedCompanyEvent]:
        """Register an in-memory subscriber queue.

        Used by tests and as an emergency local fallback when Redis is not configured.
        """
        if company_slug not in self._subscribers:
            self._subscribers[company_slug] = []
        queue: asyncio.Queue[StreamedCompanyEvent] = asyncio.Queue(maxsize=100)
        self._subscribers[company_slug].append(queue)
        return queue

    def unsubscribe(
        self,
        company_slug: str,
        queue: asyncio.Queue[StreamedCompanyEvent],
    ) -> None:
        """Remove a subscriber queue."""
        if company_slug in self._subscribers:
            self._subscribers[company_slug] = [
                q for q in self._subscribers[company_slug] if q is not queue
            ]
            if not self._subscribers[company_slug]:
                del self._subscribers[company_slug]

    def emit(self, company_slug: str, event: CompanyEvent) -> None:
        """Broadcast an event to local subscribers and Redis Streams."""
        local_event = self._publish_local(company_slug, event)
        if self._redis is None or self._publish_script is None:
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._apublish(company_slug, event))
        except RuntimeError:
            if self._loop is not None and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._apublish(company_slug, event),
                    self._loop,
                )
            else:
                logger.warning(
                    "No event loop available — Redis company publish dropped for %s seq=%s",
                    company_slug,
                    local_event.seq,
                )

    def _publish_local(
        self,
        company_slug: str,
        event: CompanyEvent,
    ) -> StreamedCompanyEvent:
        """Push an event to local subscribers for tests/fallback."""
        with self._lock:
            seq = self._local_counters.get(company_slug, 0) + 1
            self._local_counters[company_slug] = seq
        streamed = StreamedCompanyEvent(
            seq=seq,
            event_type=event.event_type,
            data=event.data,
        )
        for queue in self._subscribers.get(company_slug, []):
            try:
                queue.put_nowait(streamed)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(streamed)
                except asyncio.QueueEmpty:
                    pass
        return streamed

    async def _apublish(self, company_slug: str, event: CompanyEvent) -> None:
        """Persist a company event into Redis Streams."""
        assert self._publish_script is not None
        try:
            await self._publish_script(
                keys=[
                    f"company_sse:counter:{company_slug}",
                    f"company_sse:{company_slug}",
                ],
                args=[event.event_type, json.dumps(event.data), self._max_history],
            )
        except Exception:
            logger.warning(
                "Redis company publish failed for %s event=%s",
                company_slug,
                event.event_type,
                exc_info=True,
            )

    def _xread_block_ms(self, heartbeat_interval_s: int) -> int:
        """Choose an XREAD block that stays below the Redis socket timeout."""
        requested_ms = max(1000, int(heartbeat_interval_s * 1000))
        socket_timeout_s = settings.redis_socket_timeout
        if socket_timeout_s is None or socket_timeout_s <= 0:
            return requested_ms
        safe_ms = max(1000, int(socket_timeout_s * 1000) - _SOCKET_TIMEOUT_BUFFER_MS)
        return min(requested_ms, safe_ms)

    async def stream(
        self,
        company_slug: str,
        *,
        last_event_id: int | None = None,
        heartbeat_interval_s: int = 30,
    ) -> AsyncGenerator[StreamedCompanyEvent | None, None]:
        """Yield sequenced company events, or ``None`` for heartbeat ticks."""
        if self._redis is None:
            queue = self.subscribe(company_slug)
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(
                            queue.get(),
                            timeout=heartbeat_interval_s,
                        )
                        if last_event_id is None or event.seq > last_event_id:
                            yield event
                    except asyncio.TimeoutError:
                        yield None
            finally:
                self.unsubscribe(company_slug, queue)
            return

        cutoff = last_event_id or 0
        key = f"company_sse:{company_slug}"
        block_ms = self._xread_block_ms(heartbeat_interval_s)
        try:
            entries = await self._redis.xrange(key, min="-", max="+")
            for stream_id, fields in entries:
                seq = int(fields.get("seq", "0"))
                if seq > cutoff:
                    yield StreamedCompanyEvent(
                        seq=seq,
                        event_type=fields["type"],
                        data=json.loads(fields["data"]),
                    )

            last_stream_id = entries[-1][0] if entries else "0"
            while True:
                try:
                    results = await self._redis.xread(
                        {key: last_stream_id},
                        block=block_ms,
                        count=20,
                    )
                except redis_exceptions.TimeoutError:
                    yield None
                    continue
                if not results:
                    yield None
                    continue
                for _, messages in results:
                    for stream_id, fields in messages:
                        last_stream_id = stream_id
                        seq = int(fields.get("seq", "0"))
                        if seq > cutoff:
                            yield StreamedCompanyEvent(
                                seq=seq,
                                event_type=fields["type"],
                                data=json.loads(fields["data"]),
                            )
        except Exception:
            logger.exception(
                "Company event stream error for %s — closing SSE stream",
                company_slug,
            )


company_event_bus = CompanyEventBus()
