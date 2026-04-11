# Core Events Module

> **Location:** `core/events/`
> **Owner:** Core
> **Dependencies:** asyncio
> **Dependents:** `api/routers/company_stream.py`, `core/content_engine/`, `core/orchestration/`
> **Last Updated:** 2026-04-09

## Overview

The events module provides an in-memory pub/sub system for broadcasting real-time state changes to the frontend. `CompanyEventBus` is a singleton that manages per-company subscriber queues. Pipeline code emits events (e.g., "brief status changed") and the SSE endpoint streams them to connected browsers. The frontend's `useCompanyStream` hook debounces these events and triggers data re-polls.

**Note:** This is currently single-process only. Multi-worker deployment requires replacing the internals with Redis Pub/Sub (interface stays the same).

## Architecture

```
Pipeline Code                    Frontend
     │                              ▲
     │ emit(slug, event)            │ EventSource
     ▼                              │
┌─────────────────┐         ┌──────┴──────────┐
│ CompanyEventBus │ ◄───────│ SSE Endpoint    │
│ (in-memory)     │ queue   │ /companies/     │
│ Dict[slug, Q[]] │ ──────► │ {slug}/stream   │
└─────────────────┘         └─────────────────┘
```

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `__init__.py` | Package marker | (empty) |
| `company_event_bus.py` | Event bus implementation | `CompanyEvent`, `CompanyEventBus`, `company_event_bus` |

## Detailed Reference

### `company_event_bus.py`

#### `CompanyEvent` (dataclass)

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_type` | `str` | (required) | Event category: `"state_changed"`, `"notification"` |
| `data` | `dict` | `{}` | Event payload (JSON-serializable) |

#### `CompanyEventBus`

| Attribute | Type | Description |
|-----------|------|-------------|
| `_subscribers` | `Dict[str, List[asyncio.Queue[CompanyEvent]]]` | Maps company_slug to subscriber queues |

| Method | Signature | Description |
|--------|-----------|-------------|
| `subscribe` | `(company_slug: str) -> asyncio.Queue[CompanyEvent]` | Creates queue (maxsize=100), returns it |
| `unsubscribe` | `(company_slug: str, queue: asyncio.Queue) -> None` | Removes queue, cleans up empty entries |
| `emit` | `(company_slug: str, event: CompanyEvent) -> None` | Broadcasts to all subscribers. **Sync** (uses `put_nowait`). On queue full: drops oldest, retries |

#### Singleton

```python
company_event_bus = CompanyEventBus()
```

## Event Types

| Type | Data Fields | Emitted By |
|------|------------|------------|
| `state_changed` | `changed: List[str]`, `hint: str` | Pipeline state transitions |
| `notification` | `message: str`, `level: str` | HITL review ready, completion, errors |

## Usage Patterns

**Publisher (sync, safe from any context):**
```python
from core.events.company_event_bus import company_event_bus, CompanyEvent

company_event_bus.emit(slug, CompanyEvent(
    event_type="state_changed",
    data={"changed": [brief_id], "hint": "drafting"},
))
```

**Consumer (async SSE endpoint):**
```python
queue = company_event_bus.subscribe(slug)
try:
    while True:
        event = await asyncio.wait_for(queue.get(), timeout=30)
        yield f"event: {event.event_type}\ndata: {json.dumps(event.data)}\n\n"
finally:
    company_event_bus.unsubscribe(slug, queue)
```

## Known Tech Debt

- **Single-process only** — in-memory Dict won't fan out across Uvicorn workers
- **Planned fix:** Replace internals with Redis Pub/Sub (`PUBLISH`/`SUBSCRIBE` on channel `company:{slug}:events`)
- Interface stays identical: `emit(slug, event)` + `subscribe(slug) -> queue`
