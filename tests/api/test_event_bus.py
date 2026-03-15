"""Tests for api.tasks.event_bus — in-memory pub/sub for SSE."""
from __future__ import annotations

import asyncio
import json

import pytest

from api.tasks.event_bus import EventBus


class TestEventBusPublish:
    def test_publish_adds_to_history(self) -> None:
        bus = EventBus()
        bus.publish("task-1", "step_start", {"step": 1, "name": "Embed Assets"})
        history = bus.get_history("task-1")
        assert len(history) == 1
        assert history[0]["type"] == "step_start"
        assert history[0]["data"]["step"] == 1

    def test_event_id_auto_increment(self) -> None:
        bus = EventBus()
        bus.publish("task-1", "step_start", {"step": 1})
        bus.publish("task-1", "step_complete", {"step": 1})
        bus.publish("task-1", "step_start", {"step": 2})
        history = bus.get_history("task-1")
        assert [e["id"] for e in history] == [1, 2, 3]

    def test_event_ids_independent_per_task(self) -> None:
        bus = EventBus()
        bus.publish("task-1", "start", {})
        bus.publish("task-2", "start", {})
        assert bus.get_history("task-1")[0]["id"] == 1
        assert bus.get_history("task-2")[0]["id"] == 1

    def test_bounded_history(self) -> None:
        bus = EventBus(max_history=10)
        for i in range(25):
            bus.publish("task-1", "progress", {"i": i})
        history = bus.get_history("task-1")
        assert len(history) == 10
        # Should keep the latest 10
        assert history[0]["id"] == 16
        assert history[-1]["id"] == 25


class TestEventBusSubscribe:
    async def test_subscriber_receives_events(self) -> None:
        bus = EventBus()
        queue = bus.subscribe("task-1")
        bus.publish("task-1", "step_start", {"step": 1})
        event = queue.get_nowait()
        assert event["type"] == "step_start"

    async def test_multiple_subscribers(self) -> None:
        bus = EventBus()
        q1 = bus.subscribe("task-1")
        q2 = bus.subscribe("task-1")
        bus.publish("task-1", "progress", {"pct": 50})
        e1 = q1.get_nowait()
        e2 = q2.get_nowait()
        assert e1["type"] == "progress"
        assert e2["type"] == "progress"

    async def test_unsubscribe(self) -> None:
        bus = EventBus()
        queue = bus.subscribe("task-1")
        bus.unsubscribe("task-1", queue)
        bus.publish("task-1", "progress", {"pct": 50})
        assert queue.empty()

    async def test_subscriber_does_not_receive_other_task_events(self) -> None:
        bus = EventBus()
        queue = bus.subscribe("task-1")
        bus.publish("task-2", "progress", {"pct": 50})
        assert queue.empty()


class TestEventBusStream:
    async def test_stream_yields_sse_format(self) -> None:
        bus = EventBus()
        bus.publish("task-1", "step_start", {"step": 1})
        bus.publish("task-1", "completed", {})

        events = []
        async for chunk in bus.stream("task-1"):
            events.append(chunk)
            if len(events) >= 2:
                break

        # Should be SSE-formatted
        assert events[0].startswith("id: 1\n")
        assert "event: step_start\n" in events[0]
        assert "data: " in events[0]

    async def test_stream_replays_from_last_event_id(self) -> None:
        bus = EventBus()
        for i in range(5):
            bus.publish("task-1", "progress", {"i": i})

        events = []
        async for chunk in bus.stream("task-1", last_event_id=3):
            events.append(chunk)
            if len(events) >= 2:
                break

        # Should replay events 4 and 5
        assert "id: 4\n" in events[0]
        assert "id: 5\n" in events[1]

    async def test_stream_live_events(self) -> None:
        bus = EventBus()

        async def publish_later():
            await asyncio.sleep(0.05)
            bus.publish("task-1", "progress", {"pct": 50})

        asyncio.create_task(publish_later())

        events = []
        async for chunk in bus.stream("task-1"):
            events.append(chunk)
            if len(events) >= 1:
                break

        assert "id: 1\n" in events[0]
        assert "event: progress\n" in events[0]

    async def test_empty_history_returns_nothing_until_publish(self) -> None:
        bus = EventBus()
        history = bus.get_history("nonexistent")
        assert history == []

    async def test_sub_completed_does_not_terminate_stream(self) -> None:
        """sub_completed (rewritten by proxy) must NOT close the SSE stream."""
        bus = EventBus()
        bus.publish("t1", "start", {"pipeline": "orchestrator"})
        bus.publish("t1", "sub_completed", {"pipeline": "kb"})
        bus.publish("t1", "sub_failed", {"pipeline": "ap"})
        bus.publish("t1", "progress", {"step": 3})
        bus.publish("t1", "completed", {"pipeline": "orchestrator"})

        events = []
        async for chunk in bus.stream("t1"):
            events.append(chunk)

        # All 5 events should be yielded — stream only terminates on real "completed"
        assert len(events) == 5
        assert "sub_completed" in events[1]
        assert "sub_failed" in events[2]
