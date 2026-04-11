"""Tests for core.events.company_event_bus."""
from __future__ import annotations

import asyncio
import itertools
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.exceptions as redis_exceptions

from core.events.company_event_bus import (
    CompanyEvent,
    CompanyEventBus,
    StreamedCompanyEvent,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    r = AsyncMock()
    counter = itertools.count(1)
    mock_script = AsyncMock(side_effect=lambda keys=None, args=None: next(counter))
    r.register_script = MagicMock(return_value=mock_script)
    r.xrange = AsyncMock(return_value=[])
    r.xread = AsyncMock(return_value=None)
    return r


class TestCompanyEventBusLocal:
    def test_subscribe_creates_queue(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        assert isinstance(queue, asyncio.Queue)

    def test_emit_to_subscriber(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        bus.emit("acme", CompanyEvent(event_type="state_changed", data={"hint": "briefing"}))
        received = queue.get_nowait()
        assert isinstance(received, StreamedCompanyEvent)
        assert received.seq == 1
        assert received.event_type == "state_changed"
        assert received.data["hint"] == "briefing"

    def test_emit_no_subscribers_is_noop(self):
        bus = CompanyEventBus()
        bus.emit("unknown", CompanyEvent(event_type="test", data={}))

    def test_unsubscribe_removes_queue(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        bus.unsubscribe("acme", queue)
        bus.emit("acme", CompanyEvent(event_type="test", data={}))
        assert queue.empty()

    def test_multiple_subscribers_receive_same_event(self):
        bus = CompanyEventBus()
        q1 = bus.subscribe("acme")
        q2 = bus.subscribe("acme")
        bus.emit("acme", CompanyEvent(event_type="notification", data={"type": "test"}))
        assert q1.get_nowait().event_type == "notification"
        assert q2.get_nowait().event_type == "notification"

    def test_different_companies_isolated(self):
        bus = CompanyEventBus()
        q_acme = bus.subscribe("acme")
        q_beta = bus.subscribe("beta")
        bus.emit("acme", CompanyEvent(event_type="test", data={}))
        assert not q_acme.empty()
        assert q_beta.empty()

    def test_queue_full_drops_oldest(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        for i in range(100):
            bus.emit("acme", CompanyEvent(event_type="fill", data={"i": i}))
        assert queue.full()
        bus.emit("acme", CompanyEvent(event_type="overflow", data={"i": 100}))
        first = queue.get_nowait()
        assert first.data["i"] == 1

    @pytest.mark.asyncio
    async def test_local_stream_yields_event_and_heartbeat(self):
        bus = CompanyEventBus()
        stream = bus.stream("acme", heartbeat_interval_s=1)
        first_item = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        bus.emit("acme", CompanyEvent(event_type="test", data={"ok": True}))
        event = await first_item
        assert event is not None
        assert event.event_type == "test"
        delayed = bus.stream("beta", heartbeat_interval_s=0.01)
        heartbeat = await anext(delayed)
        assert heartbeat is None


class TestCompanyEventBusRedis:
    @pytest.mark.asyncio
    async def test_register_script_called_on_configure(self, mock_redis: AsyncMock):
        bus = CompanyEventBus()
        bus.configure(redis=mock_redis, loop=asyncio.get_running_loop())
        mock_redis.register_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_schedules_redis_publish(self, mock_redis: AsyncMock):
        bus = CompanyEventBus(redis=mock_redis, loop=asyncio.get_running_loop())
        bus.emit("acme", CompanyEvent(event_type="state_changed", data={"hint": "briefing"}))
        await asyncio.sleep(0.05)
        bus._publish_script.assert_awaited_once()
        keys = bus._publish_script.call_args.kwargs["keys"]
        args = bus._publish_script.call_args.kwargs["args"]
        assert keys == ["company_sse:counter:acme", "company_sse:acme"]
        assert args[0] == "state_changed"
        assert json.loads(args[1]) == {"hint": "briefing"}

    @pytest.mark.asyncio
    async def test_emit_from_worker_thread_uses_stored_loop(self, mock_redis: AsyncMock):
        bus = CompanyEventBus(redis=mock_redis, loop=asyncio.get_running_loop())

        def sync_publish():
            bus.emit("acme", CompanyEvent(event_type="notification", data={"m": 1}))

        await asyncio.to_thread(sync_publish)
        await asyncio.sleep(0.05)
        assert bus._publish_script.await_count >= 1

    @pytest.mark.asyncio
    async def test_stream_replays_from_redis(self, mock_redis: AsyncMock):
        bus = CompanyEventBus(redis=mock_redis, loop=asyncio.get_running_loop())
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "state_changed", "data": '{"hint":"gap_analysis"}'}),
            ("2-0", {"seq": "2", "type": "notification", "data": '{"message":"done"}'}),
        ]

        events = []
        async for item in bus.stream("acme"):
            if item is not None:
                events.append(item)
            if len(events) == 2:
                break

        assert [e.seq for e in events] == [1, 2]
        assert events[0].event_type == "state_changed"
        assert events[1].data["message"] == "done"

    @pytest.mark.asyncio
    async def test_stream_skips_below_last_event_id(self, mock_redis: AsyncMock):
        bus = CompanyEventBus(redis=mock_redis, loop=asyncio.get_running_loop())
        mock_redis.xrange.return_value = [
            ("1-0", {"seq": "1", "type": "state_changed", "data": "{}"}),
            ("2-0", {"seq": "2", "type": "state_changed", "data": "{}"}),
            ("3-0", {"seq": "3", "type": "notification", "data": '{"message":"new"}'}),
        ]

        events = []
        async for item in bus.stream("acme", last_event_id=2):
            if item is not None:
                events.append(item)
            if len(events) == 1:
                break

        assert len(events) == 1
        assert events[0].seq == 3

    @pytest.mark.asyncio
    async def test_stream_emits_heartbeat_then_live_event(self, mock_redis: AsyncMock):
        bus = CompanyEventBus(redis=mock_redis, loop=asyncio.get_running_loop())
        mock_redis.xrange.return_value = []
        mock_redis.xread.side_effect = [
            None,
            [("company_sse:acme", [("1-0", {"seq": "1", "type": "state_changed", "data": '{"hint":"briefing"}'})])],
        ]

        stream = bus.stream("acme", heartbeat_interval_s=0)
        heartbeat = await anext(stream)
        event = await anext(stream)

        assert heartbeat is None
        assert event is not None
        assert event.seq == 1
        assert event.data["hint"] == "briefing"

    @pytest.mark.asyncio
    async def test_stream_treats_redis_timeout_as_heartbeat_and_uses_safe_block(
        self,
        mock_redis: AsyncMock,
    ):
        bus = CompanyEventBus(redis=mock_redis, loop=asyncio.get_running_loop())
        mock_redis.xrange.return_value = []
        mock_redis.xread.side_effect = [
            redis_exceptions.TimeoutError("Timeout reading from localhost:6379"),
            [("company_sse:acme", [("1-0", {"seq": "1", "type": "state_changed", "data": '{"hint":"briefing"}'})])],
        ]

        with patch("core.events.company_event_bus.settings.redis_socket_timeout", 20.0):
            stream = bus.stream("acme", heartbeat_interval_s=30)
            heartbeat = await anext(stream)
            event = await anext(stream)

        assert heartbeat is None
        assert event is not None
        assert event.seq == 1
        assert event.data["hint"] == "briefing"
        first_call = mock_redis.xread.await_args_list[0]
        assert first_call.kwargs["block"] == 19000

    @pytest.mark.asyncio
    async def test_stream_handles_redis_error_gracefully(self, mock_redis: AsyncMock):
        bus = CompanyEventBus(redis=mock_redis, loop=asyncio.get_running_loop())
        mock_redis.xrange.side_effect = ConnectionError("Redis down")

        events = []
        async for item in bus.stream("acme"):
            events.append(item)

        assert events == []

    def test_emit_no_loop_available_still_updates_local_queue(self, mock_redis: AsyncMock):
        bus = CompanyEventBus(redis=mock_redis, loop=None)
        queue = bus.subscribe("acme")
        with patch("core.events.company_event_bus.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no loop")
            bus.emit("acme", CompanyEvent(event_type="state_changed", data={"hint": "briefing"}))
        received = queue.get_nowait()
        assert received.event_type == "state_changed"
