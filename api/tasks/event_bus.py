"""EventBusProtocol and SSE formatting helper.

The concrete EventBus class was removed in Phase 6 (filesystem fallback removal).
Production uses RedisEventBus exclusively. Tests use InMemoryEventBus from
tests/_support/event_bus.py.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class EventBusProtocol(Protocol):
    """Structural type for event bus implementations (RedisEventBus)."""

    def publish(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None: ...
    def get_history(self, task_id: str) -> List[Dict[str, Any]]: ...
    def is_terminal(self, task_id: str) -> bool: ...
    async def stream(
        self, task_id: str, last_event_id: Optional[int] = None,
        task_status_fn: Optional[Callable[[str], Optional[str]]] = None,
    ) -> AsyncGenerator[str, None]: ...


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
