# Sprint v6 — Audience Persona Phase D (Pipeline Orchestrator)

**Date:** 2026-03-06
**Branch:** `research-agent-v1.2.0`
**Tests before:** 2479 → **Tests after:** 2524 (+45)

---

## Goal

Implement Phase D of the Audience Persona Research Pipeline — the pipeline orchestrator that wires together models, storage, agents, and HITL graphs from Phases A-C into a working end-to-end pipeline.

## Completed

### T-ap-phase-d: Pipeline Orchestrator

**Files created:**
- `core/research/audience_persona/pipeline.py` (~280 lines)
- `tests/research/audience_persona/test_pipeline_ap.py` (45 tests)

**Architecture:**
- 4-phase pipeline: Preflight → Suggester → Parallel Generators → Finalize
- 2 HITL checkpoints: Brief Approval (HITL-1) + Profile Review (HITL-2)
- Frozen ID mapping (`_build_id_map()`) for collision-safe `brief_id → persona_id`
- `asyncio.Semaphore` for parallel generator concurrency control
- `asyncio.Lock` for serializing storage writes
- SSE events via `_emit()`, task progress via `_update_task()`
- LangSmith tracing integration

**Codex Review (gpt-5.3-codex):**
- 9 findings incorporated (collision handling, graph computed fields, persona_id keying, effective_slug fallback, empty file validation, all-failures path, added briefs validation, safe KB version lookup, collision tests)
- 5 rejected with reasoning (cross-process safety, asyncio.to_thread, stage validation, API key checks, max_concurrent guard)
- 3 deferred to Phase E/F (standalone race condition, rerun semantics, HITL timeout)

**Test categories (10 classes, 45 tests):**
- A: Helpers (7) — `_resolve_slug`, `_slugify_persona_name`, `_build_id_map`
- B: Preflight (6) — missing/empty company_context, effective_slug fallback, KB version
- C: Phase 1 Suggester (3) — correct args, 0-briefs error, SSE events
- D: HITL-1 (5) — auto-approve, all-rejected, partial, manual briefs, modified briefs
- E: Phase 2 Generators (7) — parallel execution, semaphore, errors, storage writes, ICP kind
- F: HITL-2 (7) — revision reruns, reject archives, skip on all-fail, trimmed previews
- G: Phase 3 Finalize (3) — manifest updates, KB version, company_name
- H: Full Flow (3) — end-to-end, output fields, storage dir
- I: SSE + TaskStore (2) — events emitted, task updated
- J: Error Handling (2) — failed event, tracing flush

## Decisions

None requiring approval — Phase D follows the plan approved during plan mode. All architectural decisions were Codex-reviewed and documented in the plan file.

## Deferred

- Phase E: API Router + Runner (~30 tests)
- Phase F: Integration (~20 tests)

## Test Results

```
tests/research/audience_persona/ — 232 passed in 10.30s (Phases A-D combined)
```
