# Core Events Module

> **Location:** `core/events/`
> **Owner:** Core
> **Dependencies:** asyncio, redis.asyncio, redis.exceptions
> **Dependents:** `api/routers/company_stream.py`, `core/content_engine/`, `core/orchestration/`
> **Last Updated:** 2026-04-24

## Overview

The events module provides a company-wide event bus for broadcasting real-time pipeline state changes to the frontend. `CompanyEventBus` is backed by **Redis Streams** in production and falls back to bounded in-memory queues in tests or when Redis is unavailable. Pipeline code emits lightweight `CompanyEvent` objects (e.g., "brief status changed") and the SSE endpoint streams sequenced `StreamedCompanyEvent` objects -- with monotonic `seq` IDs and `Last-Event-ID` replay support -- to connected browsers.

The frontend's `useCompanyStream` hook consumes the SSE stream, debounces `state_changed` events (300ms), and triggers data re-polls. The `notification` event type is used for user-facing alerts (HITL review ready, completion, errors). The `topic_run_changed` event type supports per-topic-run fanout for TD-entry parallelism.

**Single-process limitation:** The `subscribe()` in-memory queue path is per-process. With Redis Streams configured, events are persisted and replayed via `XRANGE`/`XREAD`, but in-memory subscriber fanout does not cross Uvicorn workers. Full multi-worker support requires Redis Pub/Sub for the subscriber notification layer (interface stays the same).

## Architecture

```
Pipeline Code                         Frontend
     |                                   ^
     | emit(slug, event)                 | EventSource
     v                                   |
+-----------------------+        +-------+-----------+
| CompanyEventBus       |        | SSE Endpoint      |
| +-------------------+ |        | GET /companies/   |
| | Redis Streams     | |<-------|   {slug}/stream   |
| | company_sse:{slug}| | XREAD  |                   |
| +-------------------+ |        | Last-Event-ID     |
| +-------------------+ |        | replay support    |
| | In-memory queues  | |        +-------------------+
| | (test fallback)   | |
| +-------------------+ |
+-----------------------+
```

### Dual Transport

1. **Redis Streams (production):** Events are persisted via an atomic Lua script (`INCR` counter + `XADD` + dual `EXPIRE`) and consumed via `XRANGE` (replay) + `XREAD` (live). Stream TTL is 24h with approximate MAXLEN trimming (~200).

2. **In-memory queues (test/fallback):** Each subscriber gets an `asyncio.Queue[StreamedCompanyEvent]` (maxsize=100). When Redis is not configured, `emit()` only pushes to local queues. `stream()` consumes from the queue with heartbeat timeouts.

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `__init__.py` | Package marker | (empty) |
| `company_event_bus.py` | Event bus implementation (260 lines) | `CompanyEvent`, `StreamedCompanyEvent`, `CompanyEventBus`, `company_event_bus` |

## Detailed Reference

### `company_event_bus.py`

#### `CompanyEvent` (dataclass)

Lightweight event published by pipeline code. No sequence number -- sequencing is added by the bus.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_type` | `str` | (required) | Event category: `"state_changed"`, `"notification"`, `"topic_run_changed"` |
| `data` | `dict` | `{}` | Event payload (JSON-serializable) |

#### `StreamedCompanyEvent` (dataclass)

Sequenced event returned by `_publish_local()` or deserialized from Redis Streams. Carries the monotonic `seq` ID used as the SSE `id:` field.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `seq` | `int` | (required) | Globally monotonic sequence number |
| `event_type` | `str` | (required) | Event category |
| `data` | `dict` | `{}` | Event payload |

#### `CompanyEventBus`

**Constructor:**

```python
CompanyEventBus(
    *,
    redis: aioredis.Redis | None = None,     # Optional: configure Redis immediately
    loop: asyncio.AbstractEventLoop | None = None,  # Stored for cross-thread emit
    max_history: int = 200,                   # MAXLEN cap for Redis Stream
)
```

If `redis` is passed at construction, `configure()` is called automatically.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `_subscribers` | `Dict[str, List[asyncio.Queue[StreamedCompanyEvent]]]` | Maps company_slug to subscriber queues (local path) |
| `_local_counters` | `Dict[str, int]` | Per-company monotonic counter (local path) |
| `_redis` | `aioredis.Redis | None` | Async Redis client (set via `configure()`) |
| `_publish_script` | Registered Lua script or `None` | Atomic publish script |
| `_loop` | `asyncio.AbstractEventLoop | None` | Stored loop for cross-thread `emit()` |
| `_max_history` | `int` | MAXLEN cap (default 200) |
| `_lock` | `threading.RLock` | Thread safety for local counter increments |

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `configure` | `(*, redis, loop=None) -> None` | Attach Redis Streams transport. Registers the `_PUBLISH_LUA` script. |
| `subscribe` | `(company_slug) -> asyncio.Queue[StreamedCompanyEvent]` | Creates bounded queue (maxsize=100), appends to subscribers list. |
| `unsubscribe` | `(company_slug, queue) -> None` | Removes the queue. Cleans up empty slug entries. |
| `emit` | `(company_slug, event) -> None` | **Sync.** Always pushes to local queues first via `_publish_local()`, then schedules `_apublish()` as fire-and-forget coroutine if Redis is configured. |
| `stream` | `async (company_slug, *, last_event_id=None, heartbeat_interval_s=30) -> AsyncGenerator[StreamedCompanyEvent | None, None]` | Yields sequenced events or `None` for heartbeats. Routes to Redis path or local queue path based on `_redis` availability. |

#### `emit()` Thread Safety

`emit()` is designed to be called from any context:

1. **Running event loop found:** `loop.create_task(self._apublish(...))` -- fire-and-forget.
2. **No running loop but stored `_loop` available:** `asyncio.run_coroutine_threadsafe(...)` -- for sync callers on worker threads (e.g., `_emit_company_event()` in orchestrator helpers).
3. **No loop at all:** Redis publish is dropped; local subscribers still receive the event. Logged at WARNING.

Local subscribers always receive the event regardless of Redis availability (`_publish_local()` runs first, synchronously, under `_lock`).

#### `stream()` Redis Path

When Redis is configured, `stream()` uses a two-phase approach:

1. **Replay phase:** `XRANGE(key, "-", "+")` over the full stream. Events with `seq > last_event_id` (or `seq > 0` if no `last_event_id`) are yielded. This provides reconnect replay.
2. **Live phase:** `XREAD({key: last_stream_id}, block=N, count=20)`. Empty results or `redis.TimeoutError` yield heartbeats (`None`). New messages are yielded as `StreamedCompanyEvent`.

The `XREAD` block duration is computed by `_xread_block_ms()`: clamped to the smaller of `heartbeat_interval_s * 1000` and `(redis_socket_timeout * 1000) - 1000`, with a minimum of 1000ms. This prevents socket timeout errors from masquerading as connection failures (see `company_event_bus.py:181`).

Fatal Redis errors in the stream phase cause the generator to exit cleanly (log + return), closing the SSE connection. The client reconnects and replays via `Last-Event-ID`.

#### `_PUBLISH_LUA` Script

```lua
local counter_key = KEYS[1]  -- company_sse:counter:{slug}
local stream_key  = KEYS[2]  -- company_sse:{slug}

local seq = redis.call('INCR', counter_key)
redis.call('XADD', stream_key, 'MAXLEN', '~', max_len, '*',
           'seq', seq, 'type', event_type, 'data', event_data)
redis.call('EXPIRE', stream_key, 86400)
redis.call('EXPIRE', counter_key, 86400)
return seq
```

Atomic single-Redis-round-trip: `INCR` + `XADD` + dual `EXPIRE`. Globally monotonic `seq` via per-company `INCR` counter. Approximate MAXLEN trimming keeps the stream bounded.

#### Singleton

```python
company_event_bus = CompanyEventBus()
```

Configured at app startup via `company_event_bus.configure(redis=..., loop=...)`. Without `configure()`, only the in-memory queue path is active.

### SSE Endpoint (`api/routers/company_stream.py`)

**Route:** `GET /api/v1/companies/{company_slug}/stream`

**Auth:** `require_auth` dependency + tenant isolation check (`request.state.company_slug` must match path parameter; 403 otherwise).

**Request headers:**
- `Last-Event-ID` (optional): Resume from this sequence number. Events with `seq <= last_event_id` are skipped during replay.
- `X-Correlation-ID` (optional): Bound to structlog context for the stream duration (truncated to 128 chars).

**Response format (SSE):**

```
id: 42
event: state_changed
data: {"changed": ["brief-001"], "hint": "drafting"}

: keepalive

id: 43
event: notification
data: {"message": "Content ready for review", "level": "info"}
```

- Each event includes `id:` (the monotonic `seq` number) for `Last-Event-ID` replay.
- Heartbeat comments (`: keepalive\n\n`) are sent every 30 seconds when no events arrive.
- Disconnection detected via `request.is_disconnected()` -- generator breaks cleanly.
- Response headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no` (nginx proxy compatibility).
- Structured logging: `bind_context()` on start, `clear_context()` in the generator's `finally` block.

## Event Types

| Type | Data Fields | Emitted By | Purpose |
|------|------------|------------|---------|
| `state_changed` | `changed: List[str]`, `hint: str` | Pipeline state transitions | Frontend re-polls changed brief/assignment IDs |
| `notification` | `message: str`, `level: str` | HITL review ready, completion, errors | User-facing in-app notification |
| `topic_run_changed` | `topic_run_id: str`, `status: str`, `hint: str` | TD-entry parallelism dispatcher | Per-topic-run status updates for planner UI |

### Hint Values (state_changed)

| Hint | Meaning |
|------|---------|
| `gap_analysis` | GA phase running |
| `gap_analysis_complete` | GA phase done, ready for CE |
| `briefing` | Entering Content Engine |
| `planning` | Strategic planner stage |
| `drafting` | Worker pipeline running |
| `evaluating` | Evaluator-optimizer loop |
| `complete` | Pipeline finished |
| `error` | Pipeline failed |

## Usage Patterns

**Publisher (sync, safe from any context):**
```python
from core.events.company_event_bus import company_event_bus, CompanyEvent

company_event_bus.emit(slug, CompanyEvent(
    event_type="state_changed",
    data={"changed": [brief_id], "hint": "drafting"},
))
```

**Publisher from orchestrator helper:**
```python
def _emit_company_event(effective_slug: str, event_type: str, data: dict) -> None:
    """Broadcast a company-wide SSE event. Best-effort."""
    from core.events.company_event_bus import company_event_bus, CompanyEvent
    company_slug = effective_slug.split("__")[0]  # strip product suffix
    company_event_bus.emit(company_slug, CompanyEvent(event_type=event_type, data=data))
```

**Consumer (SSE endpoint):**
```python
async for event in company_event_bus.stream(
    company_slug,
    last_event_id=last_event_id,
    heartbeat_interval_s=30,
):
    if event is None:
        yield ": keepalive\n\n"
    else:
        yield f"id: {event.seq}\nevent: {event.event_type}\ndata: {json.dumps(event.data)}\n\n"
```

## Integration Points

| Component | How It Uses Events |
|-----------|-------------------|
| `core/content_engine/state_helpers.py` | `_emit_company()` emits `state_changed` on brief status transitions |
| `core/orchestration/td_content_orchestrator.py` | `_emit_company_event()` emits GA-phase transitions and error rollbacks |
| `api/routers/company_stream.py` | SSE endpoint consuming the bus via `stream()` |
| Frontend `useCompanyStream` hook | EventSource + 300ms debounce on `state_changed` triggers re-poll |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `redis_url` | `None` | Required for Redis Streams transport |
| `redis_socket_timeout` | `20.0` | Used to compute safe XREAD block duration |

## Error Handling

- **`_apublish()` failure:** Logged at WARNING. Local subscribers already received the event. Not re-queued.
- **`emit()` no loop available:** Redis publish dropped, local subscribers still receive the event.
- **`stream()` Redis error:** Generator exits cleanly after logging. SSE connection closes. Client reconnects with `Last-Event-ID`.
- **Queue full:** Oldest event dropped (`get_nowait()` + `put_nowait()` retry), newest event inserted.
- **Redis `TimeoutError` during XREAD:** Treated as heartbeat (yields `None`), not a fatal error.

## Testing

Tests in `tests/events/test_company_event_bus.py` cover both transport paths:

- **Local path (`TestCompanyEventBusLocal`):** subscribe/unsubscribe, emit to single and multiple subscribers, company isolation, queue-full drop-oldest behavior, async `stream()` with event + heartbeat yield.
- **Redis path (`TestCompanyEventBusRedis`):** `register_script` called on `configure()`, Lua script invoked with correct keys (`company_sse:counter:acme`, `company_sse:acme`) and args, cross-thread `emit()` via stored loop, `XRANGE` replay, `Last-Event-ID` skip logic, heartbeat + live event interleaving from `XREAD`, `redis.TimeoutError` treated as heartbeat with safe block computation, `ConnectionError` closes stream gracefully, local queue still populated when no loop is available.

## Redis Key Schema

| Key Pattern | Type | TTL | Description |
|---|---|---|---|
| `company_sse:{company_slug}` | Stream | 24h (refreshed on write) | Company event stream, MAXLEN ~200 |
| `company_sse:counter:{company_slug}` | String (int) | 24h (refreshed on write) | Monotonic event ID counter |

## Known Tech Debt

- **Single-process local subscribers** -- the `_subscribers` in-memory dict does not fan out across Uvicorn workers. Redis Streams provides persistence and replay, but `subscribe()` is per-process. Full multi-worker support requires Redis Pub/Sub for subscriber notification.
- **No SSE reconnect backoff** -- if the frontend receives a 401, it may reconnect in a tight loop. The `useCompanyStream` hook should implement exponential backoff.
- **No event deduplication** -- if the same event is consumed by multiple workers' SSE endpoints, each sends it independently. Acceptable because the frontend debounces and re-polls.
