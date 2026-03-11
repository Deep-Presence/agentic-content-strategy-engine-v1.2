# Sprint v13 — Research Orchestrator (KB → AP → VSG)

**Date:** 2026-03-11
**Branch:** `research-agent-v1.2.0`
**Tests added:** 67 (50 core + 17 API)
**Total test count:** 2659

---

## Goal

Build a single-API-call orchestrator that chains Knowledge Base → Audience Persona → Voice Style Guide pipelines as a sequential DAG, with skip logic, HITL pass-through, auto-approve distribution, and error propagation.

## What Was Built

### New Files (6)
| File | Purpose |
|------|---------|
| `core/models/research_orchestrator.py` | Pydantic models: AutoApproveConfig, PipelineSkipConfig, SubPipelineStatus/Result, ResearchOrchestratorInput/Output, OrchestratorStatus |
| `core/research/orchestrator.py` | Core orchestrator: `run_research_orchestrator()`, skip helpers, input builders, stage runners, SSE event emission |
| `api/schemas/research_orchestrator.py` | Request/response schemas with product_slug validation and max_authors constraints |
| `api/routers/research_orchestrator.py` | Router: `POST /start` (202), `GET /{run_id}/status` with tenant isolation |
| `tests/research/test_orchestrator.py` | 50 unit tests: models, skip logic, orchestration flow, error propagation, SSE events, auto-approve |
| `tests/api/test_research_orchestrator.py` | 17 router tests: start, validation, auth, tenant isolation, status |

### Modified Files (3)
| File | Change |
|------|--------|
| `api/tasks/runner.py` | Added `run_research_orchestrator_task()` with semaphore, slug lock, DB persistence, skip_fresh wiring |
| `api/tasks/models.py` | Added `"research_orchestrator"` to `PipelineTask.pipeline` Literal type |
| `api/app.py` | Added research_orchestrator router |

## Key Design Decisions

1. **HITL pass-through** — shared task_id means existing per-pipeline approval endpoints work transparently
2. **Semaphore acquired once** — sub-pipelines called directly (not via runner wrappers) to avoid deadlock
3. **Per-pipeline auto-approve** — dict-based `{"kb": [1,2,3], "ap": [1,2], "vsg": [1]}`
4. **Orchestrator's run_id passed to sub-pipelines** — valid FK for DB artifact persistence
5. **Lazy imports** in stage runners to avoid circular imports

## Codex Audit (gpt-5.3-codex) — 8 Findings

| # | Severity | Finding | Disposition |
|---|----------|---------|-------------|
| 1 | CRITICAL | Missing tenant check on status endpoint | **Fixed** — added company_slug comparison |
| 2 | CRITICAL | product_slug unvalidated (path traversal risk) | **Fixed** — added `_check_product_slug` validator |
| 3 | HIGH | Failed orchestration marked COMPLETED | **Fixed** — maps `OrchestratorStatus.failed` → `TaskStatus.FAILED` |
| 4 | HIGH | max_authors allows 5 but VSG limits to 3 | **Fixed** — aligned to `VSG_MAX_AUTHORS_LIMIT` (3) |
| 5 | MEDIUM | skip_fresh flag not wired to skip_config | **Fixed** — maps request.skip_fresh to PipelineSkipConfig |
| 6 | MEDIUM | VSG ap_manifest_version never written | **Deferred** → PB-76 (pre-existing VSG issue) |
| 7 | MEDIUM | Process-local concurrency safety | **Deferred** → PB-77 (known tech debt) |
| 8 | LOW | Test coverage gaps for fixes | **Addressed** — 4 new tests for fixes 1-4 |

## Backlog Changes

- Added: PB-76 (VSG ap_manifest_version), PB-77 (process-local concurrency)
- Total backlog items: 48
