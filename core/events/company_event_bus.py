"""In-memory pub/sub per company for real-time UI notifications.

Designed to be swapped to Redis Pub/Sub later — keep the interface clean:
``emit(company_slug, event)`` and ``subscribe(company_slug) → queue``.

Usage (publish side — sync, safe from any context):
    from core.events.company_event_bus import company_event_bus, CompanyEvent
    company_event_bus.emit(slug, CompanyEvent(
        event_type="state_changed",
        data={"changed": [brief_id], "hint": new_status},
    ))

Usage (consumer side — async SSE endpoint):
    queue = company_event_bus.subscribe(slug)
    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=30)
            yield f"event: {event.event_type}\\ndata: {json.dumps(event.data)}\\n\\n"
    finally:
        company_event_bus.unsubscribe(slug, queue)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class CompanyEvent:
    """A lightweight event broadcast to all subscribers for a company."""

    event_type: str  # "state_changed" or "notification"
    data: dict = field(default_factory=dict)


class CompanyEventBus:
    """In-memory pub/sub per company. Replace internals with Redis Pub/Sub later."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue[CompanyEvent]]] = {}

    def subscribe(self, company_slug: str) -> asyncio.Queue[CompanyEvent]:
        """Register a subscriber queue for a company. Returns the queue."""
        if company_slug not in self._subscribers:
            self._subscribers[company_slug] = []
        queue: asyncio.Queue[CompanyEvent] = asyncio.Queue(maxsize=100)
        self._subscribers[company_slug].append(queue)
        return queue

    def unsubscribe(self, company_slug: str, queue: asyncio.Queue[CompanyEvent]) -> None:
        """Remove a subscriber queue."""
        if company_slug in self._subscribers:
            self._subscribers[company_slug] = [
                q for q in self._subscribers[company_slug] if q is not queue
            ]
            # Clean up empty lists
            if not self._subscribers[company_slug]:
                del self._subscribers[company_slug]

    def emit(self, company_slug: str, event: CompanyEvent) -> None:
        """Broadcast an event to all subscribers for a company.

        Sync method — ``put_nowait()`` is non-blocking. Safe to call from
        both sync helpers (``_emit()``) and async pipeline code.
        """
        if company_slug not in self._subscribers:
            return
        for queue in self._subscribers[company_slug]:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event if queue is full
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass


# Singleton — import this directly
company_event_bus = CompanyEventBus()
