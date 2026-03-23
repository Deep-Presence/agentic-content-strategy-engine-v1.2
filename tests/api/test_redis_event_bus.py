"""Tests for api.tasks.redis_event_bus — Redis Streams-backed SSE event bus."""
from __future__ import annotations

import asyncio
import itertools
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.tasks.event_bus import EventBus, EventBusProtocol, _format_sse
from api.tasks.redis_event_bus import RedisEventBus, _format_sse_from_fields


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create an AsyncMock Redis client with default stubs.

    The Lua publish script is mocked via ``register_script`` returning an
    AsyncMock callable that simulates atomic INCR (returns sequential ints).
    """
    r = AsyncMock()
    _counter = itertools.count(1)

    # Lua script mock — register_script returns an async-callable mock
    mock_script = AsyncMock(side_effect=lambda keys=None, args=None: next(_counter))
    r.register_script = MagicMock(return_value=mock_script)

    # Keep individual stubs for stream() tests (xrange/xread) and edge cases
    r.xrange = AsyncMock(return_value=[])
    r.xread = AsyncMock(return_value=None)
    return r


@pytest.fixture
async def redis_bus(mock_redis: AsyncMock) -> RedisEventBus:
    """Create a RedisEventBus with a mocked Redis client."""
    loop = asyncio.get_running_loop()
    return RedisEventBus(redis=mock_redis, max_history=200, loop=loop)


# ── Lua script publish tests (#3) ─────────────────────────────────


class TestLuaScriptPublish:
    def test_register_script_called_on_init(
        self, mock_redis: AsyncMock
    ) -> None:
        """RedisEventBus.__init__ registers the Lua publish script."""
        bus = RedisEventBus(redis=mock_redis, max_history=200)
        mock_redis.register_script.assert_called_once()
        # Verify the script text contains key Redis commands
        script_text = mock_redis.register_script.call_args[0][0]
        assert "INCR" in script_text
        assert "XADD" in script_text
        assert "EXPIRE" in script_text

    @pytest.mark.asyncio
    async def test_apublish_uses_lua_script(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """_apublish calls the registered Lua script, not individual commands."""
        redis_bus.publish("task-1", "started", {"pipeline": "test"})
        await asyncio.sleep(0.05)

        # Lua script should be called
        redis_bus._publish_script.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_script_receives_correct_keys_and_args(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """Lua script called with keys=[counter_key, stream_key] and args=[type, data, maxlen]."""
        redis_bus.publish("task-1", "progress", {"pct": 50})
        await asyncio.sleep(0.05)

        call_kwargs = redis_bus._publish_script.call_args
        keys = call_kwargs.kwargs.get("keys")
        args = call_kwargs.kwargs.get("args")

        assert keys == ["sse:counter:task-1", "sse:task-1"]
        assert args[0] == "progress"
        assert json.loads(args[1]) == {"pct": 50}
        assert args[2] == 200  # max_history

    @pytest.mark.asyncio
    async def test_script_sequential_ids(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """Multiple publishes invoke the Lua script sequentially."""
        redis_bus.publish("task-1", "started", {})
        redis_bus.publish("task-1", "progress", {"pct": 50})
        redis_bus.publish("task-1", "completed", {})
        await asyncio.sleep(0.1)

        assert redis_bus._publish_script.await_count == 3

    @pytest.mark.asyncio
    async def test_script_failure_handled_gracefully(
        self, mock_redis: AsyncMock
    ) -> None:
        """If Lua script raises, mirror still updated, no crash."""
        mock_script = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_redis.register_script = MagicMock(return_value=mock_script)

        loop = asyncio.get_running_loop()
        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=loop)
        bus.publish("task-1", "started", {"pipeline": "test"})
        await asyncio.sleep(0.05)

        # Mirror should still have the event
        history = bus.get_history("task-1")
        assert len(history) == 1
        assert history[0]["type"] == "started"


# ── Publish mirror tests ──────────────────────────────────────────


class TestRedisEventBusPublish:
    def test_publish_updates_in_memory_history(
        self, redis_bus: RedisEventBus
    ) -> None:
        """Publish 3 events → get_history() returns 3 with correct local seq IDs."""
        redis_bus.publish("task-1", "started", {"pipeline": "test"})
        redis_bus.publish("task-1", "progress", {"pct": 50})
        redis_bus.publish("task-1", "progress", {"pct": 100})

        history = redis_bus.get_history("task-1")
        assert len(history) == 3
        assert [e["id"] for e in history] == [1, 2, 3]
        assert history[0]["type"] == "started"
        assert history[1]["data"]["pct"] == 50

    @pytest.mark.asyncio
    async def test_publish_from_worker_thread(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """publish() via asyncio.to_thread() schedules on main loop."""

        def sync_publish():
            redis_bus.publish("task-1", "progress", {"pct": 50})

        await asyncio.to_thread(sync_publish)
        await asyncio.sleep(0.1)

        # Mirror should be updated (synchronous — always works)
        history = redis_bus.get_history("task-1")
        assert len(history) == 1
        assert history[0]["type"] == "progress"
        # Lua script should have been scheduled via run_coroutine_threadsafe
        assert redis_bus._publish_script.await_count >= 1

    def test_publish_no_loop_available(self, mock_redis: AsyncMock) -> None:
        """publish() with no running loop AND no stored loop → logs warning, no crash."""
        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=None)

        with patch("api.tasks.redis_event_bus.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")
            bus.publish("task-1", "started", {"pipeline": "test"})

        # Mirror still updated
        history = bus.get_history("task-1")
        assert len(history) == 1

    def test_bounded_history(self, mock_redis: AsyncMock) -> None:
        """max_history=10, publish 25 → get_history() returns last 10."""
        bus = RedisEventBus(redis=mock_redis, max_history=10, loop=None)
        with patch("api.tasks.redis_event_bus.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")
            for i in range(25):
                bus.publish("task-1", "progress", {"i": i})

        history = bus.get_history("task-1")
        assert len(history) == 10
        assert history[0]["id"] == 16
        assert history[-1]["id"] == 25

    def test_event_ids_independent_per_task(
        self, redis_bus: RedisEventBus
    ) -> None:
        """Publish to two tasks → each mirror starts at local seq 1."""
        redis_bus.publish("task-1", "started", {})
        redis_bus.publish("task-2", "started", {})

        assert redis_bus.get_history("task-1")[0]["id"] == 1
        assert redis_bus.get_history("task-2")[0]["id"] == 1


# ── Thread-safe reads (#6) ────────────────────────────────────────


class TestThreadSafeReads:
    def test_get_history_acquires_lock(
        self, redis_bus: RedisEventBus
    ) -> None:
        """get_history() acquires the threading lock."""
        redis_bus.publish("task-1", "started", {})

        original_lock = redis_bus._lock
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        redis_bus._lock = mock_lock

        redis_bus.get_history("task-1")
        mock_lock.__enter__.assert_called()

        redis_bus._lock = original_lock

    def test_is_terminal_acquires_lock(
        self, redis_bus: RedisEventBus
    ) -> None:
        """is_terminal() acquires the lock independently (no nested locking)."""
        redis_bus.publish("task-1", "completed", {})

        original_lock = redis_bus._lock
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        redis_bus._lock = mock_lock

        redis_bus.is_terminal("task-1")
        mock_lock.__enter__.assert_called()

        redis_bus._lock = original_lock

    def test_get_history_returns_snapshot_under_lock(
        self, redis_bus: RedisEventBus
    ) -> None:
        """get_history() returns a list copy, not a reference to the deque."""
        redis_bus.publish("task-1", "started", {})
        h1 = redis_bus.get_history("task-1")
        redis_bus.publish("task-1", "progress", {})
        h2 = redis_bus.get_history("task-1")

        # h1 should not be mutated by later publishes
        assert len(h1) == 1
        assert len(h2) == 2


# ── Mirror eviction (#7) ──────────────────────────────────────────


class TestMirrorEviction:
    def test_mirror_evicts_oldest_terminal_at_capacity(
        self, mock_redis: AsyncMock
    ) -> None:
        """When _MAX_MIRROR_TASKS reached, evict oldest terminal task first."""
        from api.tasks.redis_event_bus import _MAX_MIRROR_TASKS

        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=None)

        with patch("api.tasks.redis_event_bus.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")

            # Fill to capacity with terminal tasks
            for i in range(_MAX_MIRROR_TASKS):
                bus.publish(f"task-{i}", "completed", {})

            assert len(bus._history) == _MAX_MIRROR_TASKS

            # One more task should trigger eviction
            bus.publish("task-new", "started", {})

            assert len(bus._history) == _MAX_MIRROR_TASKS
            assert "task-new" in bus._history
            assert "task-0" not in bus._history

    def test_mirror_evicts_oldest_any_when_no_terminal(
        self, mock_redis: AsyncMock
    ) -> None:
        """When no terminal tasks, evict oldest task regardless."""
        from api.tasks.redis_event_bus import _MAX_MIRROR_TASKS

        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=None)

        with patch("api.tasks.redis_event_bus.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")

            for i in range(_MAX_MIRROR_TASKS):
                bus.publish(f"task-{i}", "progress", {})

            bus.publish("task-new", "started", {})

            assert len(bus._history) == _MAX_MIRROR_TASKS
            assert "task-new" in bus._history
            assert "task-0" not in bus._history

    def test_eviction_preserves_active_tasks(
        self, mock_redis: AsyncMock
    ) -> None:
        """Eviction prefers terminal tasks over active ones."""
        from api.tasks.redis_event_bus import _MAX_MIRROR_TASKS

        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=None)

        with patch("api.tasks.redis_event_bus.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")

            half = _MAX_MIRROR_TASKS // 2
            # First half: active (non-terminal) tasks
            for i in range(half):
                bus.publish(f"active-{i}", "progress", {})

            # Second half: terminal tasks
            for i in range(half, _MAX_MIRROR_TASKS):
                bus.publish(f"terminal-{i}", "completed", {})

            # Trigger eviction
            bus.publish("task-new", "started", {})

            # active-0 should survive, oldest terminal evicted
            assert f"active-0" in bus._history
            assert f"terminal-{half}" not in bus._history

    def test_eviction_cleans_counters_and_order(
        self, mock_redis: AsyncMock
    ) -> None:
        """Eviction removes task from _counters and _task_order too."""
        from api.tasks.redis_event_bus import _MAX_MIRROR_TASKS

        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=None)

        with patch("api.tasks.redis_event_bus.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")

            for i in range(_MAX_MIRROR_TASKS):
                bus.publish(f"task-{i}", "completed", {})

            bus.publish("task-new", "started", {})

            assert "task-0" not in bus._counters
            assert "task-0" not in bus._task_order


# ── Stream tests ───────────────────────────────────────────────────


class TestRedisEventBusStream:
    @pytest.mark.asyncio
    async def test_stream_replays_from_redis(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """xrange returns 3 entries, last is terminal → all 3 replayed."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "started", "data": '{"pipeline": "test"}'}),
            ("2-0", {"seq": "2", "type": "progress", "data": '{"pct": 50}'}),
            ("3-0", {"seq": "3", "type": "completed", "data": "{}"}),
        ]

        events = []
        async for chunk in redis_bus.stream("task-1"):
            events.append(chunk)

        assert len(events) == 3
        assert "event: started" in events[0]
        assert "event: progress" in events[1]
        assert "event: completed" in events[2]

    @pytest.mark.asyncio
    async def test_stream_skips_below_last_event_id(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """stream(last_event_id=3) → only events with seq > 3 yielded."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "started", "data": "{}"}),
            ("2-0", {"seq": "2", "type": "progress", "data": '{"pct": 25}'}),
            ("3-0", {"seq": "3", "type": "progress", "data": '{"pct": 50}'}),
            ("4-0", {"seq": "4", "type": "progress", "data": '{"pct": 75}'}),
            ("5-0", {"seq": "5", "type": "completed", "data": "{}"}),
        ]

        events = []
        async for chunk in redis_bus.stream("task-1", last_event_id=3):
            events.append(chunk)

        assert len(events) == 2
        assert "id: 4" in events[0]
        assert "id: 5" in events[1]

    @pytest.mark.asyncio
    async def test_stream_replay_exact_boundary(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """stream(last_event_id=2) with seq=[1,2,3] → only seq 3 replayed."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "started", "data": "{}"}),
            ("2-0", {"seq": "2", "type": "progress", "data": "{}"}),
            ("3-0", {"seq": "3", "type": "completed", "data": "{}"}),
        ]

        events = []
        async for chunk in redis_bus.stream("task-1", last_event_id=2):
            events.append(chunk)

        assert len(events) == 1
        assert "id: 3" in events[0]
        assert "event: completed" in events[0]

    @pytest.mark.asyncio
    async def test_stream_terminates_on_terminal_event(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """Stream with [started, progress, completed] exhausts after completed."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "started", "data": "{}"}),
            ("2-0", {"seq": "2", "type": "progress", "data": "{}"}),
            ("3-0", {"seq": "3", "type": "completed", "data": "{}"}),
        ]

        events = []
        async for chunk in redis_bus.stream("task-1"):
            events.append(chunk)

        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_non_terminal_events_dont_close_stream(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """sub_completed and sub_failed do NOT close the stream."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "started", "data": "{}"}),
            ("2-0", {"seq": "2", "type": "sub_completed", "data": "{}"}),
            ("3-0", {"seq": "3", "type": "sub_failed", "data": "{}"}),
            ("4-0", {"seq": "4", "type": "completed", "data": "{}"}),
        ]

        events = []
        async for chunk in redis_bus.stream("task-1"):
            events.append(chunk)

        assert len(events) == 4
        assert "sub_completed" in events[1]
        assert "sub_failed" in events[2]

    @pytest.mark.asyncio
    async def test_stream_emits_heartbeat(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """xrange empty, xread returns None then event → heartbeat yielded."""
        mock_redis.xrange.return_value = []
        mock_redis.xread.side_effect = [
            None,  # Timeout → heartbeat
            [
                (
                    "sse:task-1",
                    [("1-0", {"seq": "1", "type": "completed", "data": "{}"})],
                )
            ],
        ]

        events = []
        async for chunk in redis_bus.stream("task-1"):
            events.append(chunk)

        assert events[0] == ": heartbeat\n\n"
        assert "event: completed" in events[1]

    @pytest.mark.asyncio
    async def test_stream_handles_redis_error_gracefully(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """Redis failure during stream() closes SSE gracefully (no crash)."""
        mock_redis.xrange.side_effect = ConnectionError("Redis down")

        events = []
        async for chunk in redis_bus.stream("task-1"):
            events.append(chunk)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_stream_handles_xread_error_after_replay(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """Redis failure during XREAD (live tail) closes SSE after replaying."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "started", "data": "{}"}),
        ]
        mock_redis.xread.side_effect = ConnectionError("Redis lost")

        events = []
        async for chunk in redis_bus.stream("task-1"):
            events.append(chunk)

        assert len(events) == 1
        assert "event: started" in events[0]


# ── SSE format parity ──────────────────────────────────────────────


class TestSSEFormatParity:
    def test_sse_format_matches_original(self) -> None:
        """_format_sse_from_fields() produces identical output to _format_sse()."""
        original_event = {"id": 42, "type": "progress", "data": {"pct": 75, "step": "embed"}}
        original_sse = _format_sse(original_event)

        redis_fields = {
            "seq": "42",
            "type": "progress",
            "data": json.dumps({"pct": 75, "step": "embed"}),
        }
        redis_sse = _format_sse_from_fields(42, redis_fields)

        assert original_sse == redis_sse

    def test_sse_format_parity_with_nested_data(self) -> None:
        """Parity with nested JSON data including special chars."""
        data = {"items": [{"name": "test & co", "value": 42}], "url": "https://example.com/path?q=1"}
        original_event = {"id": 7, "type": "step_complete", "data": data}
        original_sse = _format_sse(original_event)

        redis_fields = {
            "seq": "7",
            "type": "step_complete",
            "data": json.dumps(data),
        }
        redis_sse = _format_sse_from_fields(7, redis_fields)

        assert original_sse == redis_sse


# ── Protocol compliance ────────────────────────────────────────────


class TestProtocolCompliance:
    def test_eventbus_satisfies_protocol(self) -> None:
        """EventBus satisfies EventBusProtocol."""
        bus = EventBus()
        assert isinstance(bus, EventBusProtocol)

    def test_redis_eventbus_satisfies_protocol(
        self, mock_redis: AsyncMock
    ) -> None:
        """RedisEventBus satisfies EventBusProtocol."""
        bus = RedisEventBus(redis=mock_redis, max_history=200)
        assert isinstance(bus, EventBusProtocol)


# ── SubPipelineEventProxy compatibility ────────────────────────────


class TestSubPipelineProxy:
    def test_sub_pipeline_proxy_works_with_redis_event_bus(
        self, redis_bus: RedisEventBus
    ) -> None:
        """_SubPipelineEventProxy wrapping RedisEventBus rewrites terminal events."""
        from core.research.orchestrator import _SubPipelineEventProxy

        proxy = _SubPipelineEventProxy(redis_bus)

        proxy.publish("task-1", "completed", {"pipeline": "kb"})
        history = redis_bus.get_history("task-1")
        assert len(history) == 1
        assert history[0]["type"] == "sub_completed"

        proxy.publish("task-1", "progress", {"pct": 50})
        history = redis_bus.get_history("task-1")
        assert history[1]["type"] == "progress"


# ── is_terminal ────────────────────────────────────────────────────


class TestIsTerminal:
    def test_is_terminal_false_for_no_history(
        self, redis_bus: RedisEventBus
    ) -> None:
        assert redis_bus.is_terminal("nonexistent") is False

    def test_is_terminal_false_for_non_terminal(
        self, redis_bus: RedisEventBus
    ) -> None:
        redis_bus.publish("task-1", "progress", {})
        assert redis_bus.is_terminal("task-1") is False

    def test_is_terminal_true_for_completed(
        self, redis_bus: RedisEventBus
    ) -> None:
        redis_bus.publish("task-1", "completed", {})
        assert redis_bus.is_terminal("task-1") is True

    def test_is_terminal_true_for_failed(
        self, redis_bus: RedisEventBus
    ) -> None:
        redis_bus.publish("task-1", "failed", {"error": "boom"})
        assert redis_bus.is_terminal("task-1") is True


# ── Startup toggle ─────────────────────────────────────────────────


class TestStartupToggle:
    @pytest.mark.asyncio
    async def test_redis_event_bus_selected_when_configured(self) -> None:
        """When REDIS_EVENT_BUS=true and Redis is healthy, RedisEventBus is created."""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.redis = AsyncMock()
        mock_app.state.redis_healthy = True
        mock_app.state.event_bus = None

        with patch("core.config.settings.settings") as mock_cfg:
            mock_cfg.redis_event_bus = True

            redis_client = getattr(mock_app.state, "redis", None)
            use_redis_bus = (
                redis_client is not None
                and getattr(mock_app.state, "redis_healthy", False)
                and mock_cfg.redis_event_bus
            )
            if use_redis_bus:
                loop = asyncio.get_running_loop()
                mock_app.state.event_bus = RedisEventBus(
                    redis=redis_client, max_history=200, loop=loop
                )
            else:
                mock_app.state.event_bus = EventBus()

        assert isinstance(mock_app.state.event_bus, RedisEventBus)

    @pytest.mark.asyncio
    async def test_in_memory_event_bus_when_redis_disabled(self) -> None:
        """When REDIS_EVENT_BUS=false, in-memory EventBus is used."""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.redis = AsyncMock()
        mock_app.state.redis_healthy = True
        mock_app.state.event_bus = None

        with patch("core.config.settings.settings") as mock_cfg:
            mock_cfg.redis_event_bus = False

            redis_client = getattr(mock_app.state, "redis", None)
            use_redis_bus = (
                redis_client is not None
                and getattr(mock_app.state, "redis_healthy", False)
                and mock_cfg.redis_event_bus
            )
            if use_redis_bus:
                loop = asyncio.get_running_loop()
                mock_app.state.event_bus = RedisEventBus(
                    redis=redis_client, max_history=200, loop=loop
                )
            else:
                mock_app.state.event_bus = EventBus()

        assert isinstance(mock_app.state.event_bus, EventBus)

    @pytest.mark.asyncio
    async def test_in_memory_event_bus_when_redis_unhealthy(self) -> None:
        """When Redis is unhealthy, falls back to in-memory EventBus."""
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state.redis = AsyncMock()
        mock_app.state.redis_healthy = False
        mock_app.state.event_bus = None

        with patch("core.config.settings.settings") as mock_cfg:
            mock_cfg.redis_event_bus = True

            redis_client = getattr(mock_app.state, "redis", None)
            use_redis_bus = (
                redis_client is not None
                and getattr(mock_app.state, "redis_healthy", False)
                and mock_cfg.redis_event_bus
            )
            if use_redis_bus:
                loop = asyncio.get_running_loop()
                mock_app.state.event_bus = RedisEventBus(
                    redis=redis_client, max_history=200, loop=loop
                )
            else:
                mock_app.state.event_bus = EventBus()

        assert isinstance(mock_app.state.event_bus, EventBus)


# ── Terminal event retry tests (Issue 1b) ─────────────────────────


class TestTerminalEventRetry:
    """Tests for _apublish retry logic on terminal events."""

    @pytest.mark.asyncio
    async def test_terminal_event_retries_on_failure(
        self, mock_redis: AsyncMock
    ) -> None:
        """Terminal event retries up to 3 times on failure, succeeds on 3rd."""
        call_count = 0

        async def fail_twice_then_succeed(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Redis down")
            return call_count

        mock_script = AsyncMock(side_effect=fail_twice_then_succeed)
        mock_redis.register_script = MagicMock(return_value=mock_script)

        loop = asyncio.get_running_loop()
        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=loop)

        with patch("api.tasks.redis_event_bus.asyncio.sleep", new_callable=AsyncMock):
            await bus._apublish("task-1", "completed", {})

        assert call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_terminal_event_exhausts_retries(
        self, mock_redis: AsyncMock
    ) -> None:
        """Terminal event fails all 4 attempts → ERROR logged, no crash."""
        mock_script = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_redis.register_script = MagicMock(return_value=mock_script)

        loop = asyncio.get_running_loop()
        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=loop)

        with patch("api.tasks.redis_event_bus.asyncio.sleep", new_callable=AsyncMock):
            await bus._apublish("task-1", "completed", {})

        assert mock_script.await_count == 4  # 1 initial + 3 retries

    @pytest.mark.asyncio
    async def test_non_terminal_event_no_retry(
        self, mock_redis: AsyncMock
    ) -> None:
        """Non-terminal event fails once → no retry, just warning."""
        mock_script = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_redis.register_script = MagicMock(return_value=mock_script)

        loop = asyncio.get_running_loop()
        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=loop)

        await bus._apublish("task-1", "progress", {"pct": 50})

        assert mock_script.await_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_terminal_retry_backoff_values(
        self, mock_redis: AsyncMock
    ) -> None:
        """Terminal retries use correct backoff: 0.5s, 1.0s, 2.0s."""
        mock_script = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_redis.register_script = MagicMock(return_value=mock_script)

        loop = asyncio.get_running_loop()
        bus = RedisEventBus(redis=mock_redis, max_history=200, loop=loop)

        with patch("api.tasks.redis_event_bus.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await bus._apublish("task-1", "failed", {"error": "boom"})

        assert mock_sleep.await_count == 3
        sleep_args = [call.args[0] for call in mock_sleep.await_args_list]
        assert sleep_args == [0.5, 1.0, 2.0]


# ── Stream DB fallback tests (Issue 1b) ──────────────────────────


class TestStreamDbFallback:
    """Tests for task_status_fn DB fallback in stream()."""

    @pytest.mark.asyncio
    async def test_stream_synthesizes_terminal_from_db_status(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """After 2 heartbeats, task_status_fn returns 'completed' → synthesized event."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "started", "data": "{}"}),
        ]
        mock_redis.xread.side_effect = [None, None, None]

        status_fn = MagicMock(return_value="completed")

        events = []
        async for chunk in redis_bus.stream("task-1", task_status_fn=status_fn):
            events.append(chunk)
            if len(events) > 10:
                break

        assert any("event: started" in e for e in events)
        assert any("event: completed" in e for e in events)
        synth = [e for e in events if "event: completed" in e][0]
        assert "db_fallback" in synth

    @pytest.mark.asyncio
    async def test_stream_synthesizes_terminal_on_redis_exception(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """Redis dies mid-XREAD → fallback checks DB before closing (CX-2)."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "5", "type": "started", "data": "{}"}),
        ]
        mock_redis.xread.side_effect = ConnectionError("Redis died")

        status_fn = MagicMock(return_value="completed")

        events = []
        async for chunk in redis_bus.stream("task-1", task_status_fn=status_fn):
            events.append(chunk)

        assert any("event: started" in e for e in events)
        assert any("event: completed" in e for e in events)

    @pytest.mark.asyncio
    async def test_stream_synth_id_uses_max_seen_seq(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """Synthesized event id > max seen seq from replay (CX-4)."""
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "120", "type": "started", "data": "{}"}),
        ]
        mock_redis.xread.side_effect = [None, None, None]

        status_fn = MagicMock(return_value="failed")

        events = []
        async for chunk in redis_bus.stream("task-1", task_status_fn=status_fn):
            events.append(chunk)
            if len(events) > 10:
                break

        synth = [e for e in events if "event: failed" in e]
        assert len(synth) == 1
        assert "id: 121" in synth[0]

    @pytest.mark.asyncio
    async def test_stream_no_fallback_without_status_fn(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """Without task_status_fn, stream just sends heartbeats (no synthesis)."""
        mock_redis.xrange.return_value = []
        mock_redis.xread.side_effect = [
            None,
            None,
            [("sse:task-1", [("3-0", {"seq": "1", "type": "completed", "data": "{}"})])],
        ]

        events = []
        async for chunk in redis_bus.stream("task-1", task_status_fn=None):
            events.append(chunk)

        assert events[0] == ": heartbeat\n\n"
        assert events[1] == ": heartbeat\n\n"
        assert "event: completed" in events[2]

    @pytest.mark.asyncio
    async def test_stream_fallback_tolerates_status_fn_error(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """task_status_fn raises → stream continues with heartbeats."""
        mock_redis.xrange.return_value = []
        mock_redis.xread.side_effect = [
            None, None, None,
            [("sse:task-1", [("1-0", {"seq": "1", "type": "completed", "data": "{}"})])],
        ]

        def broken_fn(tid):
            raise RuntimeError("DB down")

        events = []
        async for chunk in redis_bus.stream("task-1", task_status_fn=broken_fn):
            events.append(chunk)

        heartbeats = [e for e in events if "heartbeat" in e]
        assert len(heartbeats) >= 2
        assert any("event: completed" in e for e in events)

    @pytest.mark.asyncio
    async def test_stream_fallback_ignores_non_terminal_status(
        self, redis_bus: RedisEventBus, mock_redis: AsyncMock
    ) -> None:
        """task_status_fn returns 'running' → no synthesis, stream continues."""
        mock_redis.xrange.return_value = []
        mock_redis.xread.side_effect = [
            None, None, None,
            [("sse:task-1", [("1-0", {"seq": "1", "type": "completed", "data": "{}"})])],
        ]

        status_fn = MagicMock(return_value="running")

        events = []
        async for chunk in redis_bus.stream("task-1", task_status_fn=status_fn):
            events.append(chunk)

        heartbeats = [e for e in events if "heartbeat" in e]
        assert len(heartbeats) >= 2
        assert any("event: completed" in e for e in events)

    @pytest.mark.asyncio
    async def test_in_memory_eventbus_accepts_task_status_fn(self) -> None:
        """EventBus.stream() accepts task_status_fn kwarg without error."""
        bus = EventBus()
        bus.publish("task-1", "completed", {})

        events = []
        async for chunk in bus.stream("task-1", task_status_fn=lambda t: None):
            events.append(chunk)

        assert len(events) == 1
        assert "event: completed" in events[0]
