"""In-memory pub/sub event bus for SSE streaming."""
from __future__ import annotations

import asyncio
import json
from collections import deque
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class EventBusProtocol(Protocol):
    """Structural type for event bus implementations (EventBus, RedisEventBus)."""

    def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None: ...
    def get_history(self, task_id: str) -> List[Dict[str, Any]]: ...
    def is_terminal(self, task_id: str) -> bool: ...
    async def stream(
        self, task_id: str, last_event_id: Optional[int] = None,
        task_status_fn: Optional[Callable[[str], Optional[str]]] = None,
    ) -> AsyncGenerator[str, None]: ...


class EventBus:
    """Publishes pipeline events and streams them as SSE to subscribers.

    Each task has independent event history and subscriber queues.
    Supports Last-Event-ID reconnection via bounded event replay.
    """

    def __init__(self, max_history: int = 100) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._history: Dict[str, deque] = {}
        self._counters: Dict[str, int] = {}
        self._max_history = max_history

    def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Publish an event for a task. Adds to history and pushes to subscriber queues."""
        if task_id not in self._counters:
            self._counters[task_id] = 0
            self._history[task_id] = deque(maxlen=self._max_history)

        self._counters[task_id] += 1
        event = {
            "id": self._counters[task_id],
            "type": event_type,
            "data": data,
        }

        self._history[task_id].append(event)

        for queue in self._subscribers.get(task_id, []):
            queue.put_nowait(event)

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """Subscribe to events for a task. Returns a queue that receives events."""
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[task_id].append(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass

    def get_history(self, task_id: str) -> List[Dict[str, Any]]:
        """Return the event history for a task."""
        if task_id not in self._history:
            return []
        return list(self._history[task_id])

    def is_terminal(self, task_id: str) -> bool:
        """Check if the last event for a task is a terminal event (completed/failed/cancelled)."""
        history = self.get_history(task_id)
        if not history:
            return False
        last_type = history[-1].get("type", "")
        return last_type in {"completed", "failed", "cancelled"}

    async def stream(
        self,
        task_id: str,
        last_event_id: Optional[int] = None,
        task_status_fn: Optional[Callable[[str], Optional[str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE-formatted event strings.

        If last_event_id is provided, replays missed events before streaming live.
        Terminates after emitting a terminal event (completed/failed/cancelled).
        ``task_status_fn`` is accepted for protocol compatibility but unused
        (in-memory EventBus delivers events reliably within a single process).
        """
        _TERMINAL_TYPES = {"completed", "failed", "cancelled"}

        # Replay events from history
        # If last_event_id is None, replay all history; otherwise replay after that ID
        cutoff = last_event_id if last_event_id is not None else 0
        for event in self.get_history(task_id):
            if event["id"] > cutoff:
                yield _format_sse(event)
                if event["type"] in _TERMINAL_TYPES:
                    return

        # Subscribe for live events with heartbeat keepalive
        queue = self.subscribe(task_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Send SSE comment as keepalive to prevent proxy/browser timeout
                    yield ": heartbeat\n\n"
                    continue
                yield _format_sse(event)
                if event["type"] in _TERMINAL_TYPES:
                    return
        finally:
            self.unsubscribe(task_id, queue)


def _format_sse(event: Dict[str, Any]) -> str:
    """Format an event dict as an SSE string."""
    lines = [
        f"id: {event['id']}",
        f"event: {event['type']}",
        f"data: {json.dumps(event['data'])}",
        "",
        "",
    ]
    return "\n".join(lines)
