# Session 1: RedisEventBus — Redis Streams for SSE

## Prerequisite

Session 0 (Redis Infrastructure Foundation) is complete. `core/redis.py` exists, `app.state.redis` is available, `/health` reports Redis status.

## Objective

Replace the in-memory `EventBus` with a Redis Streams-backed `RedisEventBus` for cross-worker SSE event delivery. The old `EventBus` stays alongside — selected by config. All existing callers (`publish()`, `stream()`) continue working without changes. The frontend receives identical SSE payloads. **Zero changes to pipeline code, runner code, orchestrators, or frontend.**

---

## 1. What the Current EventBus Does (Exact Interface to Preserve)

File: `api/tasks/event_bus.py`

The `EventBus` has exactly 6 public methods. The new `RedisEventBus` must implement all 6 with identical signatures and behavior:

```python
class EventBus:
    def __init__(self, max_history: int = 100)
    def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None
    def subscribe(self, task_id: str) -> asyncio.Queue
    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None
    def get_history(self, task_id: str) -> List[Dict[str, Any]]
    def is_terminal(self, task_id: str) -> bool
    async def stream(self, task_id: str, last_event_id: Optional[int] = None) -> AsyncGenerator[str, None]
```

### Critical behaviors to preserve:

1. **`publish()` is synchronous (non-async).** Every caller in the codebase calls it as a plain function — pipelines, runners, orchestrators, the `_emit()` helpers. The RedisEventBus `publish()` must also be synchronous. Internally it can fire-and-forget an async Redis write, but the call signature cannot be `async def`.

2. **`stream()` is async generator yielding SSE-formatted strings.** The `events.py` router passes it directly to `StreamingResponse`. Format is:
   ```
   id: {monotonic_int}\nevent: {event_type}\ndata: {json_data}\n\n
   ```

3. **`Last-Event-ID` reconnection.** The router extracts the header, parses it as `int`, and passes it to `stream(task_id, last_event_id=N)`. Events with `id > N` are replayed before live streaming begins.

4. **Terminal event detection.** `stream()` returns (closes the SSE connection) after emitting an event with type in `{"completed", "failed", "cancelled"}`. The `is_terminal()` method checks the same set.

5. **Heartbeat keepalive.** `stream()` sends `": heartbeat\n\n"` (SSE comment) every 15 seconds of inactivity to prevent proxy/browser timeout.

6. **History is bounded.** Current default is 100 events per task (`max_history`). After that, oldest events are evicted.

### Callers that use `publish()` (all synchronous):

| Location | Pattern |
|----------|---------|
| `core/content_engine/pipeline_v13.py` | `_emit(event_bus, task_id, event_type, data)` — null-safe helper |
| `core/content_engine/pipeline.py` | `event_bus.publish(task_id, ...)` directly |
| `core/onboarding/orchestrator.py` | `_emit()` null-safe helper + `_SubPipelineEventProxy` |
| `core/research/orchestrator.py` | `_emit()` null-safe helper + `_SubPipelineEventProxy` |
| `api/tasks/runner.py` | `event_bus.publish(task_id, ...)` directly (~15 call sites) |
| `api/routers/tasks.py` | `event_bus.publish(task_id, "cancelled", ...)` in cancel endpoint |
| `core/content_engine/graph_v13.py` | `event_bus.publish(task_id, "pending_approval", ...)` in HITL loop |
| `core/research/knowledge_base/graph.py` | Same HITL pattern |
| `core/research/audience_persona/graph.py` | Same HITL pattern |
| `core/research/voice_style_guide/graph.py` | Same HITL pattern |
| `core/topic_discovery/graph.py` | Same HITL pattern |

### Callers that use `subscribe()` / `unsubscribe()`:

Only `EventBus.stream()` itself. No external code calls these directly.

### Callers that use `get_history()` / `is_terminal()`:

Only `EventBus.stream()` itself.

### The `_SubPipelineEventProxy` pattern:

Two orchestrators (`core/onboarding/orchestrator.py`, `core/research/orchestrator.py`) wrap the EventBus in a proxy that rewrites terminal event types:

```python
class _SubPipelineEventProxy:
    _REWRITES = {"completed": "sub_completed", "failed": "sub_failed", "cancelled": "sub_cancelled"}
    def __init__(self, real_bus): self._real_bus = real_bus
    def publish(self, task_id, event_type, data):
        event_type = self._REWRITES.get(event_type, event_type)
        self._real_bus.publish(task_id, event_type, data)
    def __getattr__(self, name): return getattr(self._real_bus, name)
```

This proxy calls `publish()` on the real bus. It works with `RedisEventBus` unchanged because it only uses `publish()` and delegates everything else via `__getattr__`.

---

## 2. The `RedisEventBus` Implementation

### New file: `api/tasks/redis_event_bus.py`

```python
"""Redis Streams-backed event bus for SSE streaming.

Drop-in replacement for EventBus. Uses Redis Streams (XADD/XREAD/XRANGE)
for cross-worker event delivery, persistence, and replay.

publish() is synchronous (fire-and-forget async write) to maintain
compatibility with all existing callers.
"""
```

### Key design decisions:

**Stream key pattern:** `sse:{task_id}`

Each task gets its own Redis Stream. Stream keys are prefixed with `sse:` to namespace them away from other Redis usage (pipeline state, caching, etc. in future sessions).

**Event ID mapping:**

Redis Streams auto-generate IDs in `{timestamp_ms}-{seq}` format (e.g., `1711123456789-0`). But the current interface uses monotonic integers (`1`, `2`, `3`, ...) for `Last-Event-ID`. Two options:

**Option A (recommended):** Use a per-task Redis counter (`INCR sse:counter:{task_id}`) to generate monotonic integer IDs, store them as a field in the stream entry. The SSE `id:` line uses this integer. `XRANGE` replays all entries, but we filter by the integer ID field. This preserves 100% backward compatibility with the frontend's `Last-Event-ID` parsing (which does `parseInt()`).

**Option B:** Use the Redis stream ID directly as the SSE event ID. This changes the `id:` format from `3` to `1711123456789-0`. The frontend would need to send back the Redis stream ID as `Last-Event-ID` instead of an integer. The `events.py` router would need to change its `int()` parsing. **Avoid this option** — it's a breaking change to the SSE contract.

Go with **Option A**. The counter adds one extra Redis call per publish but preserves the interface contract.

**`publish()` must be synchronous:**

All ~25 call sites across the codebase call `publish()` as a plain function. Many of these are inside `asyncio.to_thread()` calls (LangGraph graph invocations run in thread pool). Making `publish()` async would require changing every caller.

Solution: `publish()` uses `asyncio.get_event_loop().create_task()` to fire-and-forget the async Redis write. If no event loop is running (shouldn't happen in the app, but safety), fall back to scheduling via a background thread.

However, there's a subtlety: some callers run inside `asyncio.to_thread()`, which means they're on a worker thread where `asyncio.get_event_loop()` returns the main loop but `create_task()` from a non-async context needs `asyncio.run_coroutine_threadsafe()`.

Implementation:

```python
def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context — create_task works
        loop.create_task(self._apublish(task_id, event_type, data))
    except RuntimeError:
        # We're in a worker thread (asyncio.to_thread) — schedule on main loop
        try:
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self._apublish(task_id, event_type, data), loop
            )
        except RuntimeError:
            logger.warning("No event loop available for Redis publish — event dropped")
```

Where `_apublish()` is the actual async method that does `INCR` + `XADD`.

**Stream TTL / cleanup:**

Set a Redis key expiry on each stream: `EXPIRE sse:{task_id} 86400` (24 hours). Refreshed on each `XADD`. After the pipeline completes and the frontend disconnects, the stream auto-expires. No manual cleanup needed. This replaces the `deque(maxlen=100)` bounded history — use `XADD ... MAXLEN ~ 200` to cap stream length (the `~` makes it approximately 200, which is more efficient than exact trimming).

**`stream()` implementation:**

```python
async def stream(self, task_id: str, last_event_id: Optional[int] = None) -> AsyncGenerator[str, None]:
    key = f"sse:{task_id}"
    cutoff = last_event_id or 0

    # Phase 1: Replay from history
    entries = await self._redis.xrange(key, min="-", max="+")
    for stream_id, fields in entries:
        seq = int(fields.get("seq", "0"))
        if seq > cutoff:
            yield self._format_sse(seq, fields)
            if fields.get("type") in _TERMINAL_TYPES:
                return

    # Phase 2: Live tail
    last_stream_id = entries[-1][0] if entries else "0"
    while True:
        results = await self._redis.xread(
            {key: last_stream_id}, block=15000, count=10
        )
        if not results:
            yield ": heartbeat\n\n"
            continue
        for _, messages in results:
            for stream_id, fields in messages:
                last_stream_id = stream_id
                seq = int(fields.get("seq", "0"))
                if seq > cutoff:
                    yield self._format_sse(seq, fields)
                    if fields.get("type") in _TERMINAL_TYPES:
                        return
```

**`get_history()` and `is_terminal()`:**

These are only used internally by the old `EventBus.stream()`. The `RedisEventBus.stream()` reads directly from the Redis Stream, so these methods become thin wrappers:

```python
def get_history(self, task_id: str) -> List[Dict[str, Any]]:
    # Synchronous — need to run async in thread
    # Only used by tests; stream() reads Redis directly
    ...

def is_terminal(self, task_id: str) -> bool:
    # Check last entry in stream
    ...
```

Since `get_history()` and `is_terminal()` are sync methods but need Redis (async), and they're only called by tests and edge cases, implement them by reading from a local in-memory mirror that `_apublish()` also updates. This avoids sync/async bridging complexity. The in-memory mirror is a nice-to-have for same-worker reads; the Redis Stream is the source of truth for cross-worker.

**`subscribe()` / `unsubscribe()`:**

Not needed externally. `RedisEventBus.stream()` uses `XREAD` directly instead of `asyncio.Queue`. Implement as no-ops that log a deprecation warning, or raise `NotImplementedError` — no external code calls them.

---

## 3. Configuration Toggle

### File: `core/config/settings.py`

Add one setting:

```python
# --- Redis ---
# ... (existing from Session 0)
redis_event_bus: bool = False  # Use RedisEventBus instead of in-memory EventBus
```

Environment variable: `REDIS_EVENT_BUS=true`

This is a simple boolean toggle. When `True` AND `redis_url` is set AND Redis is healthy, use `RedisEventBus`. Otherwise fall back to `EventBus`. This lets you deploy with Redis available but the event bus toggle off until you've validated it works.

---

## 4. App Lifespan Changes

### File: `api/app.py`

Replace the `EventBus()` initialization:

```python
# Event bus selection (Redis or in-memory)
if not hasattr(app.state, "event_bus") or app.state.event_bus is None:
    redis_client = getattr(app.state, "redis", None)
    use_redis_bus = (
        redis_client is not None
        and getattr(app.state, "redis_healthy", False)
        and settings.redis_event_bus
    )
    if use_redis_bus:
        from api.tasks.redis_event_bus import RedisEventBus
        app.state.event_bus = RedisEventBus(redis=redis_client, max_history=200)
        logger.info("Using RedisEventBus (Redis Streams)")
    else:
        app.state.event_bus = EventBus()
        logger.info("Using in-memory EventBus")
```

The `settings` import needs to be added at the top of the lifespan or imported lazily. Make sure this block runs AFTER the Redis initialization block from Session 0.

---

## 5. Events Router Changes

### File: `api/routers/events.py`

**Minimal change.** The router currently type-hints `event_bus: EventBus`. Since `RedisEventBus` is not a subclass of `EventBus`, the type hint needs to become a protocol or `Any`:

**Option A (minimal):** Change the import and type hint:

```python
# Before:
from api.tasks.event_bus import EventBus
event_bus: EventBus = Depends(get_event_bus)

# After:
event_bus = Depends(get_event_bus)  # Type inferred from dependency
```

**Option B (cleaner, recommended):** Create a Protocol. This isn't strictly necessary for this session but is good hygiene:

```python
# In api/tasks/event_bus.py, add at the top:
from typing import Protocol, runtime_checkable

@runtime_checkable
class EventBusProtocol(Protocol):
    def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None: ...
    def get_history(self, task_id: str) -> List[Dict[str, Any]]: ...
    def is_terminal(self, task_id: str) -> bool: ...
    async def stream(self, task_id: str, last_event_id: Optional[int] = None) -> AsyncGenerator[str, None]: ...
```

Then type-hint the dependency as `EventBusProtocol`. Both `EventBus` and `RedisEventBus` satisfy it.

**The `last_event_id` parsing stays the same** — the router already parses `Last-Event-ID` header as `int` and passes it through. No change needed because we're using Option A (monotonic integer IDs).

---

## 6. Dependency Injection Changes

### File: `api/dependencies.py`

**No change needed.** `get_event_bus()` already returns `request.app.state.event_bus`. The lifespan puts either `EventBus` or `RedisEventBus` on `app.state.event_bus`. The dependency function is agnostic.

If you created an `EventBusProtocol`, update the return type annotation:

```python
def get_event_bus(request: Request) -> EventBusProtocol:
    return request.app.state.event_bus
```

---

## 7. What Does NOT Change

This is critical context for Claude Code. These files are NOT modified in this session:

| File | Reason unchanged |
|------|-----------------|
| `core/content_engine/pipeline_v13.py` | Calls `_emit()` which calls `event_bus.publish()` — same interface |
| `core/content_engine/pipeline.py` | Same — calls `event_bus.publish()` directly |
| `core/onboarding/orchestrator.py` | Same — `_emit()` + `_SubPipelineEventProxy` works unchanged |
| `core/research/orchestrator.py` | Same |
| `api/tasks/runner.py` | Same — all `event_bus.publish()` calls unchanged |
| `api/routers/tasks.py` | Same — cancel endpoint's `event_bus.publish()` unchanged |
| `core/content_engine/graph_v13.py` | Same — HITL `event_bus.publish()` unchanged |
| `core/research/knowledge_base/graph.py` | Same |
| `core/research/audience_persona/graph.py` | Same |
| `core/research/voice_style_guide/graph.py` | Same |
| `core/topic_discovery/graph.py` | Same |
| `frontend/src/lib/hooks/useTaskStream.ts` | Receives same SSE format — no change |
| `frontend/src/__tests__/use-task-stream.test.ts` | Same SSE format |
| `api/tasks/event_bus.py` | **Kept as-is** — only add `EventBusProtocol` if using Option B |

---

## 8. Tests

### New file: `tests/unit/test_redis_event_bus.py`

Tests should cover:

1. **`publish()` adds entry to Redis Stream.** Mock `redis.asyncio.Redis`, verify `XADD` called with correct key, fields include `type`, `data`, `seq`.

2. **`publish()` works from sync context.** Verify fire-and-forget pattern doesn't raise. Test both "running loop" and "worker thread" code paths.

3. **`stream()` replays history then tails.** Seed a stream with 3 events via mock `XRANGE`, verify all 3 yielded as SSE strings before `XREAD` is called.

4. **`stream()` skips events below `last_event_id`.** Seed stream with events seq 1-5, call `stream(task_id, last_event_id=3)`, verify only events 4 and 5 are yielded.

5. **`stream()` terminates on terminal event.** Seed stream with `[started, progress, completed]`, verify generator exhausts after `completed`.

6. **`stream()` emits heartbeat on timeout.** Mock `XREAD` to return empty on first call, then an event. Verify `": heartbeat\n\n"` is yielded between.

7. **SSE format matches old EventBus.** Publish an event through both `EventBus` and `RedisEventBus`, compare the SSE string output character-by-character. They must be identical.

8. **`_SubPipelineEventProxy` works with `RedisEventBus`.** Create proxy wrapping `RedisEventBus`, publish through proxy, verify event type rewriting works.

### Update existing tests:

Any test that creates a `FastAPI` test app and sets `app.state.event_bus = EventBus()` should continue working unchanged. The `RedisEventBus` is only used when explicitly configured.

### Integration test (manual or CI with Redis):

```python
@pytest.mark.integration
async def test_redis_event_bus_roundtrip():
    """End-to-end: publish 3 events, stream them back, verify SSE format."""
    redis = redis.asyncio.from_url("redis://localhost:6379/1")
    bus = RedisEventBus(redis=redis, max_history=100)
    task_id = f"test-{uuid.uuid4()}"

    bus.publish(task_id, "started", {"pipeline": "test"})
    bus.publish(task_id, "progress", {"pct": 50})
    bus.publish(task_id, "completed", {"result": "ok"})

    await asyncio.sleep(0.1)  # Let fire-and-forget writes complete

    events = []
    async for sse_str in bus.stream(task_id):
        events.append(sse_str)
    
    assert len(events) == 3
    assert "event: started" in events[0]
    assert "event: progress" in events[1]
    assert "event: completed" in events[2]

    # Cleanup
    await redis.delete(f"sse:{task_id}", f"sse:counter:{task_id}")
    await redis.aclose()
```

---

## 9. Redis Key Schema (Document for Future Sessions)

This session introduces the first Redis keys. Document the key schema for consistency across sessions:

| Key Pattern | Type | TTL | Purpose | Session |
|---|---|---|---|---|
| `sse:{task_id}` | Stream | 24h (refreshed on write) | SSE event stream per task | 1 |
| `sse:counter:{task_id}` | String (integer) | 24h (refreshed on write) | Monotonic event ID counter | 1 |

Future sessions will add:
- `pipeline_state:{slug}` — Hash (Session 3)
- `lock:{pipeline}:{slug}` — String with NX (Session 3)
- `approval:{task_id}` — List (Session 4)
- `task:{task_id}` — Hash (Session 3)
- `cache:*` — String with TTL (Session 6)

---

## 10. File Summary

| File | Action | Description |
|------|--------|-------------|
| `api/tasks/redis_event_bus.py` | **Create** | `RedisEventBus` class — full implementation |
| `api/tasks/event_bus.py` | Edit (small) | Add `EventBusProtocol` (if Option B). Original `EventBus` class untouched. |
| `core/config/settings.py` | Edit | Add `redis_event_bus: bool = False` |
| `api/app.py` | Edit | EventBus selection logic in lifespan |
| `api/routers/events.py` | Edit (small) | Update type hint from `EventBus` to `EventBusProtocol` or remove explicit type |
| `api/dependencies.py` | Edit (optional) | Update return type of `get_event_bus()` if using Protocol |
| `tests/unit/test_redis_event_bus.py` | **Create** | Unit tests (8 test cases) |
| `CLAUDE.md` | Edit | Document RedisEventBus, config toggle, key schema |

---

## 11. Validation Checklist

### Without Redis (REDIS_URL unset or REDIS_EVENT_BUS=false):
1. App starts, logs "Using in-memory EventBus"
2. Start any pipeline → SSE events arrive at frontend correctly
3. All existing tests pass

### With Redis (REDIS_URL set + REDIS_EVENT_BUS=true):
4. App starts, logs "Using RedisEventBus (Redis Streams)"
5. Start a content pipeline → SSE events arrive at frontend correctly
6. In Redis CLI: `XLEN sse:{task_id}` shows events accumulating
7. Disconnect SSE, reconnect with `Last-Event-ID` header → missed events replayed
8. Terminal event ("completed") closes SSE stream
9. Heartbeat comments appear every ~15s during HITL wait (pipeline paused at approval)
10. After 24 hours, `EXISTS sse:{task_id}` returns 0 (auto-expiry)
11. Start the Research Orchestrator (KB → AP → VSG) → sub-pipeline events rewritten correctly (`sub_completed` instead of `completed`)
12. Cancel a running pipeline → `cancelled` event emitted, SSE stream closes

### Parity test:
13. Run the same pipeline twice — once with `REDIS_EVENT_BUS=false`, once with `true`. Compare the SSE event payloads received by the frontend. They must be identical in structure, field names, event types, and ID sequencing.

---

## 12. Scope Boundaries — Do NOT Do These

- Do NOT delete the old `EventBus` class
- Do NOT change any pipeline code (`_emit()` helpers, `event_bus.publish()` calls)
- Do NOT change runner code (`api/tasks/runner.py`)
- Do NOT change orchestrator code
- Do NOT change HITL graph code
- Do NOT change frontend SSE hook or tests
- Do NOT implement any other Redis service (pipeline state, locks, caching, etc.)
- Do NOT change `TaskStore` or `DbTaskStore`
- Do NOT add `langgraph-checkpoint-redis` dependency
- Do NOT make `publish()` async
