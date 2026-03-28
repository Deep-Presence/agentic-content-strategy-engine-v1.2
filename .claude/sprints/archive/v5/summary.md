# Sprint v5 — Summary

**Date:** 2026-03-06
**Sprint Goal:** Knowledge Base Phase 5 — Synthesis & Living Document: delta synthesis mode, DAG-aware staleness tracking with propagation, health/refresh-stale endpoints, write-before-approve fix

## Completed Tasks
| Task ID | Description | Tests Added | Files Changed |
|---------|-------------|-------------|---------------|
| T1 | Models — DAG + staleness constants + health models | +7 tests | core/models/knowledge_base.py |
| T2 | Storage — dependencies, staleness report, propagation, atomic writes | +15 tests | core/research/knowledge_base/storage.py |
| T3 | Delta synthesis prompt | +5 tests | core/research/prompts/synthesis.py |
| T4 | Synthesis agent delta mode | +5 tests (+3 fixes) | core/research/knowledge_base/agents.py |
| T5 | Pipeline integration — delta synthesis + staleness + write-before-approve fix | +7 tests | core/research/knowledge_base/pipeline.py |
| T6 | Health endpoint | +5 tests | api/routers/knowledge_base.py, api/schemas/common.py |
| T7 | Refresh-stale endpoint | +6 tests | api/routers/knowledge_base.py, api/schemas/common.py |

## Decisions Made
- D-KB-P5-1: DAG as Python constant (KB_DEPENDENCY_GRAPH) — structural to pipeline, no manifest migration needed
- D-KB-P5-2: Delta synthesis via read_file tool — consistent with full-mode synthesis
- D-KB-P5-3: Per-doc staleness thresholds as constant — overview=90d, reviews=30d, competitor=90d, weakness=60d, brand=45d
- D-KB-P5-4: Health/refresh endpoints on /{slug}/ path — registered before dynamic routes to avoid collision
- D-KB-P5-5: External cron for scheduled refresh — no in-process scheduler

## Failures Encountered
- F1: 3 agent tests failing — patched stale `build_synthesis_agent` but agents.py was refactored to build inline. Fixed by patching `create_react_agent` + `_build_model`
- F2: `doc_review_graph` unbound in pipeline.py — only defined inside `if cp1_doc_types:` block but HITL-2 referenced it unconditionally. Fixed by moving graph build before conditional
- F3: `_capture_delta_prompt(**kw)` couldn't accept positional args — fixed to `*args, **kw`

## Deferred to Backlog
- Product-level inheritance in staleness (future sprint)
- Delta synthesis structured output fields (sections_changed, confidence_scores) — marginal value for v1
- In-process scheduler — external cron sufficient

## Codex Review Summary
Codex gpt-5.3-codex plan review completed. All 5 CRITICAL/HIGH findings addressed:
1. CRITICAL: Write-before-approve fix — company_context only written on HITL-3 approve (regression test)
2. HIGH: De-scoped duplicate synthesis agent build (already implemented in Phase 3)
3. HIGH: staleness_threshold_days wired into stale-doc resolution
4. HIGH: Dependencies populated from DAG constant
5. HIGH: Atomic manifest writes via temp-file + os.replace

## Test Count
- Start of session: ~2429 tests
- End of session: ~2479 tests (+50 new)
- KB-specific: 260 tests (214 core + 46 API)

## Key Metrics
- Tasks completed: 7
- Tasks deferred: 0
- Files changed: 13 (7 core + 2 API + 4 test files)
- Bugs fixed: 3 (stale test mocks, unbound variable, positional args)
- Pre-existing bugs fixed: 1 (doc_review_graph unbound)
