# API Tasks — TaskStore, EventBus, Runner

> **Location:** `api/tasks/`
> **Owner:** API
> **Dependencies:** Redis (Streams, Sorted Sets, Lists), PostgreSQL, `core/` pipelines
> **Dependents:** All pipeline routers, SSE endpoints
> **Last Updated:** 2026-04-09

## Overview

The tasks module manages the complete lifecycle of background pipeline executions: task creation with distributed locking, SSE event streaming via Redis Streams, HITL approval delivery, and 18 pipeline runner functions. `DbTaskStore` is the production implementation with Redis distributed locks, Redis semaphore (max 3 concurrent), and Redis approval queues.

## File Structure

| File | Purpose |
|------|---------|
| `runner.py` | 18 async pipeline runner functions + scope resolution + artifact resolution |
| `redis_event_bus.py` | `RedisEventBus` — Redis Streams SSE with in-memory mirror |
| `event_bus.py` | `EventBusProtocol` — abstract interface |
| `models.py` | `PipelineTask`, `ApprovalRecord`, `TaskStatus` |
| `exceptions.py` | `TaskNotFoundError`, `TaskConflictError`, `ApprovalDeliveryError` |

## RedisEventBus

Production SSE implementation using Redis Streams + in-memory mirror.

**Atomic Lua script:** `INCR counter → XADD stream → EXPIRE both` (single Redis call, no out-of-order writes)

| Method | Description |
|--------|-------------|
| `publish(task_id, event_type, data)` | Sync fire-and-forget. Updates mirror + schedules async Redis write |
| `stream(task_id, last_event_id)` | Async generator: replay (XRANGE) → live tail (XREAD) → terminal detection |
| `get_history(task_id)` | Thread-safe mirror read |
| `is_terminal(task_id)` | Check if last event is completed/failed/cancelled |

**Resilience:** Terminal events retry 3x. DB fallback every ~30s checks task status if Redis stream lost. Heartbeat keepalive every 15s.

**In-memory mirror:** Thread-safe (RLock), capped at 1000 tasks, oldest terminal evicted first.

## Pipeline Runners (18 functions)

Each runner follows the same pattern:
1. Resolve scope (company/product slug → effective_slug)
2. Create PipelineRunModel in DB
3. Publish "started" SSE event
4. Run core pipeline logic
5. On success: publish "completed", mark DB complete
6. On failure: publish "failed", log error, mark DB failed
7. Cleanup stale state (Redis + filesystem)

**Runners:** gap, site_audit, content, content_v13, knowledge_base, audience_persona, voice_style_guide, topic_discovery, topic_expansion, td_content, td_gap_analysis, td_content_production, onboarding, daily_tracker, fanout_generation, cms_sync, ga4_sync, research_orchestrator, single_persona_generator

## Task Lifecycle

```
POST /start → create_task_durable() → asyncio.create_task(runner)
    │                                      │
    ▼                                      ▼
202 { task_id }                    Pipeline running...
    │                                      │
    ▼                                      ▼
GET /tasks/{id}/events → SSE stream   publish("step_completed")
    │                                      │
    ▼                                      ▼
Receive events...                  PENDING_APPROVAL (HITL)
    │                                      │
    ▼                                      ▼
POST /{id}/approve                 wait_for_approval() → BRPOP
    │                                      │
    ▼                                      ▼
  Resume                             Continue pipeline
    │                                      │
    ▼                                      ▼
Receive "completed"                publish("completed")
```

## Approval Flow

1. Pipeline calls `task_store.update_task(status=PENDING_APPROVAL, approval_payload=...)`
2. Redis: SET nonce, publish SSE "pending_approval"
3. Frontend: poll task → display approval_payload → user decides
4. Frontend: `POST /approve` → `task_store.submit_approval(task_id, decision)`
5. Redis: check nonce (idempotent), SET flag (dedup), LPUSH payload to approval queue
6. Pipeline: `BRPOP approval:{task_id}` unblocks → resumes with decision
7. Cleanup: DELETE nonce, flag, queue keys
