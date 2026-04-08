"""Tests for core.events.company_event_bus — in-memory company-wide pub/sub."""

import asyncio

import pytest

from core.events.company_event_bus import CompanyEvent, CompanyEventBus


class TestCompanyEventBus:
    def test_subscribe_creates_queue(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        assert isinstance(queue, asyncio.Queue)

    def test_emit_to_subscriber(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        event = CompanyEvent(event_type="state_changed", data={"hint": "briefing"})
        bus.emit("acme", event)
        assert not queue.empty()
        received = queue.get_nowait()
        assert received.event_type == "state_changed"
        assert received.data["hint"] == "briefing"

    def test_emit_no_subscribers_is_noop(self):
        bus = CompanyEventBus()
        # Should not raise
        bus.emit("unknown", CompanyEvent(event_type="test", data={}))

    def test_unsubscribe_removes_queue(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        bus.unsubscribe("acme", queue)
        bus.emit("acme", CompanyEvent(event_type="test", data={}))
        assert queue.empty()  # No longer subscribed

    def test_unsubscribe_cleans_up_empty_list(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        bus.unsubscribe("acme", queue)
        assert "acme" not in bus._subscribers

    def test_multiple_subscribers_receive_same_event(self):
        bus = CompanyEventBus()
        q1 = bus.subscribe("acme")
        q2 = bus.subscribe("acme")
        event = CompanyEvent(event_type="notification", data={"type": "test"})
        bus.emit("acme", event)
        assert not q1.empty()
        assert not q2.empty()

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
        # Fill the queue (maxsize=100)
        for i in range(100):
            bus.emit("acme", CompanyEvent(event_type="fill", data={"i": i}))
        assert queue.full()

        # Emit one more — should drop oldest and add new
        bus.emit("acme", CompanyEvent(event_type="overflow", data={"i": 100}))
        assert queue.qsize() == 100
        # The first event should have been dropped; peek first item
        first = queue.get_nowait()
        assert first.data["i"] == 1  # index 0 was dropped

    @pytest.mark.asyncio
    async def test_async_consumer(self):
        bus = CompanyEventBus()
        queue = bus.subscribe("acme")
        bus.emit("acme", CompanyEvent(event_type="test", data={"key": "val"}))
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event.event_type == "test"
        assert event.data["key"] == "val"
