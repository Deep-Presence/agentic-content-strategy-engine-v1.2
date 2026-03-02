# Sprint: langsmith-migration — Summary

**Date:** 2026-03-02
**Sprint Goal:** Eliminate Langfuse, unify all tracing on LangSmith, add Hub prompt registry + LangGraph Studio support
**Branch:** feat/front-back

## Completed Tasks
| Task | Description | Tests Added | Files Changed |
|------|-------------|-------------|---------------|
| Phase 0 | Extended `tracing_v13.py` — backward-compat kwargs for all 6 functions + contextvars (`set_current_span`/`get_current_span`) | +24 tests | `tracing_v13.py` |
| Phase 1 | Import swaps — 16 sites across 14 files (`tracing` → `tracing_v13`), collapsed dispatcher dual-import aliases | 0 (existing tests validate) | 14 files |
| Phase 2 | `graph_v13.py` tracing via contextvars (5 gate nodes), `pipeline_v13.py` `set_current_span()` at 4 HITL callsites | 0 (52 graph tests pass) | `graph_v13.py`, `pipeline_v13.py` |
| Phase 3 | `prompt_registry.py` (thread-safe TTL-cached Hub pull with local fallback), 2 new settings, getters in all 11 prompt files, upload script | +14 tests | `prompt_registry.py`, `settings.py`, 11 prompt files, `upload_prompts_to_hub.py` |
| Phase 4 | `langgraph.json` — 3 graph entry points for LangGraph Studio | 0 | `langgraph.json` |
| Phase 5 | Deleted `tracing.py`, removed `langfuse>=2.0` from requirements, removed 3 langfuse settings, cleaned docstrings | 0 | `tracing.py` (deleted), `requirements.txt`, `settings.py`, ~15 files docstring cleanup |

## Decisions Made
- D-LANGSMITH-1: Unify all tracing on LangSmith, eliminate Langfuse entirely
- D-LANGSMITH-2: Backward-compat kwargs shim in `tracing_v13.py` (avoids 57 callsite refactors)
- D-LANGSMITH-3: contextvars for LangGraph span propagation (avoids MemorySaver msgpack crash)
- D-LANGSMITH-4: `pull_prompt_commit()` with defensive manifest extraction (not `pull_prompt()` which returns LangChain PromptTemplate)
- D-LANGSMITH-5: Hub is opt-in via `langsmith_use_hub=False` default — local prompts remain authoritative

## Failures Encountered
- None

## Deferred to Backlog
- None

## Test Count
- Start of session: 437 content engine tests
- End of session: 437 content engine tests (+38 new, some existing reclassified)
- New test files: `test_tracing_compat.py` (24), `test_prompt_registry.py` (14)

## Key Metrics
- Tasks completed: 7 (Phases 0–5 + Phase 0 tests)
- Tasks deferred: 0
- Files changed: ~30
- Files created: 4 (`prompt_registry.py`, `test_tracing_compat.py`, `test_prompt_registry.py`, `langgraph.json`)
- Files deleted: 1 (`tracing.py`)
- Zero Langfuse imports remaining in core/api/tests
