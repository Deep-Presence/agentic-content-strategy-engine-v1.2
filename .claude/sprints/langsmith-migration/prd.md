# Sprint: langsmith-migration — PRD (v2, Codex-reviewed)

**Date:** 2026-03-02
**Branch:** feat/langsmith-migration
**Codex verdict:** REJECT on v1 → revised as v2 with 6 critical corrections

---

## Context

The content engine currently has a split-brain tracing problem:
- v1.0 pipeline (`pipeline.py` and 13 other files) → emits to **Langfuse**
- v1.3 pipeline (`pipeline_v13.py` and 5 other files) → emits to **LangSmith**
- Stage 3 evaluators (`loop.py`, `eeat_judge.py`) → called by `pipeline_v13.py` but still emit to **Langfuse**
- `graph_v13.py` (Stage 4 HITL) → **no tracing at all**

Target state:
1. All tracing goes to LangSmith. Langfuse removed entirely.
2. `tracing_v13.py` becomes the single tracing module with **full API compatibility** with old `tracing.py` kwargs.
3. All 11 agent system prompts registered in LangSmith Hub with commit-hash pinning, local fallback.
4. `graph_v13.py` has LangSmith tracing via `contextvars` (not state injection).
5. `langgraph.json` for Studio — only referencing graphs that actually exist.

---

## Codex v1 Rejection Findings (all incorporated into v2)

### C1 — API signatures are NOT identical (INCORPORATE)
My v1 plan claimed `tracing.py` and `tracing_v13.py` have "identical signatures". They don't:
- `tracing.create_span()` takes `input=` kwarg; `tracing_v13.create_span()` takes `input_data=`
- `tracing.end_span()` accepts `level=` and `status_message=` kwargs; `tracing_v13.end_span()` does not
- `tracing.log_score()` old code logs string decisions (e.g. `graph.py:262`); semantics differ

**Fix:** Before doing any import swaps, first extend `tracing_v13` to accept all old kwargs (add `**kwargs` absorbers or explicit compat params). This is Phase 0.

### C2 — Hidden import in pipeline.py:175 (INCORPORATE)
`pipeline.py` has a local import inside a function at line 175 that was not in my "files to change" list:
```python
from core.content_engine.tracing import create_span, end_span, log_score, update_trace_output
```
Must be caught and swapped too.

### C3 — Execution order wrong (INCORPORATE)
v1 plan: "Phase 5 cleanup first (settings + requirements)." Removing Langfuse settings before old tracing.py is gone would break `tracing.py` at import time.

**Fix:** Correct order:
1. Phase 0: Extend `tracing_v13` API compat
2. Phase 1: All import swaps (14 files + hidden line 175)
3. Phase 2: `graph_v13.py` tracing (contextvars)
4. Phase 3: Prompt registry
5. Phase 4: `langgraph.json`
6. **Phase 5 last**: Delete `tracing.py`, remove Langfuse from settings + requirements

### C4 — `langgraph.json` references non-existent file (INCORPORATE)
v1 plan referenced `core/research/graphs/combined_pipeline.py` which does not exist. The research pipeline entrypoint is `core/research/graphs/pipeline.py` and its function is not a named graph factory — it doesn't expose a `StateGraph` for Studio to latch onto.

**Fix:** `langgraph.json` only lists `graph_v13.py` entrypoints initially. Research graph can be added later when confirmed.

### C5 — `RunTree` in LangGraph state fails with `MemorySaver` (INCORPORATE — critical)
Codex ran your actual code and reproduced:
```
TypeError: Type is not msgpack serializable: X
```
MemorySaver tries to msgpack-serialize all state fields including any Python objects. Putting `RunTree` in a TypedDict state field will crash the checkpointer.

**Fix:** Use `contextvars.ContextVar` to propagate parent spans. Each pipeline stage sets the span in a contextvar before calling graph functions. Node functions read it from the contextvar, never from state.

```python
# core/content_engine/tracing_v13.py — add at module level
_current_span: ContextVar[Optional[Any]] = ContextVar("langsmith_span", default=None)

def set_current_span(span: Optional[Any]) -> None:
    _current_span.set(span)

def get_current_span() -> Optional[Any]:
    return _current_span.get()
```

This is completely safe in asyncio — each task has its own context, so concurrent pipeline runs don't interfere.

### C6 — Hub `pull_prompt()` does NOT return a raw string (INCORPORATE — critical)
`Client.pull_prompt()` returns a LangChain `PromptTemplate` object (requires `langchain-core`). It is NOT a string. The proposed `get_prompt() -> str` contract would fail at runtime.

**Fix:** Use `Client.pull_prompt_commit()` which returns a `PromptCommit` with a `manifest: dict[str, Any]`. Extract the system message text from the manifest. OR use `Client.get_prompt()` which returns a `Prompt` schema and walk the messages. Safer approach: `pull_prompt_commit()` → `manifest["messages"][0]["kwargs"]["content"]`.

**Alternatively:** Use the raw HTTP API to fetch the prompt text directly, which is simpler and avoids the LangChain dependency. `requests.get(f"https://api.smith.langchain.com/api/v1/commits/{org}/{name}:{tag}")` with the API key.

Hub pulls are also synchronous — wrapping in `asyncio.to_thread()` required for async pipeline.

**Hub cache:** Process-global dict (not session-level as I said) is actually fine since prompt content doesn't change between runs. Add TTL (e.g. 5 minutes) and a `threading.Lock` for thundering herd protection. Pin by commit hash, not mutable `production` tag, for determinism.

---

## Revised Scope (v2)

### Phase 0 — Extend `tracing_v13.py` for full backward compat

Before touching any call site, update `tracing_v13.py` so every function it exports accepts all kwargs that the old `tracing.py` functions accepted. The old kwargs are silently ignored (LangSmith has no equivalent concept for some of them).

**Changes to `tracing_v13.py`:**
- `create_span(parent, name, metadata, input_data, *, input=None, **kwargs)` — accept `input=` as alias for `input_data=`
- `end_span(span, output, error, *, level=None, status_message=None, metadata=None, **kwargs)` — absorb old kwargs
- `log_generation(parent, name, model, input_text, output_text, metadata, usage, *, user_id=None, model_parameters=None, **kwargs)` — absorb old kwargs
- `log_score(parent, name, value, comment, *, data_type=None, **kwargs)` — absorb old kwargs
- Add `contextvars` support: `set_current_span()`, `get_current_span()`
- Rename module docstring to reflect it is now THE tracing module (not just v1.3)

No functional changes to LangSmith behaviour — purely absorbs extra kwargs.

### Phase 1 — Import swaps (14 files + 1 hidden)

Pure mechanical import path changes. After Phase 0, the signatures match, so no call-site changes needed.

| File | Change |
|------|--------|
| `core/content_engine/pipeline.py` (top-level import) | `tracing` → `tracing_v13` |
| `core/content_engine/pipeline.py:175` (local import inside function) | `tracing` → `tracing_v13` |
| `core/content_engine/planner.py` | `tracing` → `tracing_v13` |
| `core/content_engine/graph.py` | `tracing` → `tracing_v13` |
| `core/content_engine/workers/dispatcher.py` | collapse dual-mode aliases → single `tracing_v13` import |
| `core/content_engine/workers/drafter.py` | `tracing` → `tracing_v13` |
| `core/content_engine/workers/outliner.py` | `tracing` → `tracing_v13` |
| `core/content_engine/workers/formatter.py` | `tracing` → `tracing_v13` |
| `core/content_engine/workers/fact_enricher.py` | `tracing` → `tracing_v13` |
| `core/content_engine/evaluator/loop.py` | `tracing` → `tracing_v13` |
| `core/content_engine/evaluator/structural.py` | `tracing` → `tracing_v13` |
| `core/content_engine/evaluator/semantic.py` | `tracing` → `tracing_v13` |
| `core/content_engine/evaluator/style_judge.py` | `tracing` → `tracing_v13` |
| `core/content_engine/evaluator/factual_judge.py` | `tracing` → `tracing_v13` |
| `core/content_engine/evaluator/eeat_judge.py` | `tracing` → `tracing_v13` |

After Phase 1, run full test suite. If all pass, proceed.

### Phase 2 — `graph_v13.py` tracing via contextvars

**Pattern:** `pipeline_v13.py` already owns the root trace. Before calling any graph, it calls `set_current_span(pipeline_trace)`. Inside each graph node, the node reads `get_current_span()` and creates a child span from it.

```python
# In pipeline_v13.py — before run_hitl_checkpoint()
set_current_span(pipeline_trace)

# In graph_v13.py node functions
from core.content_engine.tracing_v13 import get_current_span, create_span, end_span

def _topic_approval_node(state: TopicApprovalState) -> dict:
    parent = get_current_span()
    span = create_span(parent, "hitl-topic-approval", input_data={...})
    # ... existing logic ...
    end_span(span, output={...})
    return {...}
```

Nodes to instrument in `graph_v13.py`:
- `_request_topic_approval` → span `"hitl-1-topic-approval"`
- `_request_brief_approval` → span `"hitl-2-brief-approval"`
- `_request_content_review` → span `"hitl-3-content-review"`
- `_apply_content_edits` → span `"hitl-3-apply-edits"`
- `_finalize_content` → span + `log_score` for final piece

State TypedDict stays clean — no `parent_span` field.

### Phase 3 — LangSmith Hub prompt registry

#### New file: `core/content_engine/prompt_registry.py`

```python
import asyncio
import threading
import time
from typing import Optional
import requests  # already in requirements

_CACHE: dict[str, tuple[str, float]] = {}  # key → (text, fetched_at)
_CACHE_TTL = 300  # 5 minutes
_LOCK = threading.Lock()

def get_prompt(hub_name: str, local_fallback: str, tag: str = "production") -> str:
    """Pull prompt text from LangSmith Hub or return local fallback."""
    ...
```

**`pull_prompt_commit()` extraction chain:**
```python
commit = Client().pull_prompt_commit(f"{hub_name}:{tag}")
# commit.manifest is dict[str, Any]
messages = commit.manifest.get("messages", [])
# Find the first SystemMessage
for msg in messages:
    if msg.get("type") == "system":
        return msg["kwargs"]["content"]  # or msg["content"]
```

Need to verify manifest shape against real Hub response — add error handling for missing keys.

**Async safety:** Wrap `Client().pull_prompt_commit()` in `asyncio.to_thread()` when called from async context.

**Cache design:**
- Key: `f"{hub_name}:{tag}"`
- Value: `(text, fetched_at_timestamp)`
- TTL: 5 min
- Lock: `threading.Lock()` for thundering herd — first caller fetches, others wait
- On error: log warning, return local fallback (never raise)

**Startup script: `scripts/upload_prompts_to_hub.py`**
- One-time script to push all 11 local prompts to Hub
- Uses `Client().push_prompt()`
- Tags initial version as `production`
- Idempotent — creates or updates
- Prints commit hash for each upload (for deterministic pinning in `.env`)

**Settings addition:**
```python
langsmith_use_hub: bool = False
langsmith_hub_tag: str = "production"  # override to pin a commit hash
```

**Usage in prompt files:** Each `*_SYSTEM_PROMPT` constant stays. Workers call:
```python
_STRATEGIC_PLANNER_SYSTEM_PROMPT_HUB = "deep-presence/strategic-planner-system"

def get_strategic_planner_system_prompt() -> str:
    return get_prompt(_STRATEGIC_PLANNER_SYSTEM_PROMPT_HUB, STRATEGIC_PLANNER_SYSTEM_PROMPT)
```

Each worker calls the getter once at pipeline start, caches in a local variable for the run.

### Phase 4 — `langgraph.json` (Studio compatibility)

```json
{
  "dependencies": ["."],
  "graphs": {
    "content_topic_approval": "./core/content_engine/graph_v13.py:build_topic_approval_graph",
    "content_brief_approval": "./core/content_engine/graph_v13.py:build_brief_approval_graph",
    "content_review": "./core/content_engine/graph_v13.py:build_content_review_graph"
  },
  "env": ".env.local"
}
```

No research graph reference — that entrypoint is not a named factory.

### Phase 5 — Cleanup (LAST, after all tests pass)

Only after Phases 0-4 are done and all tests green:
1. Delete `core/content_engine/tracing.py`
2. Update all test mocks: `patch("core.content_engine.tracing.X")` → `patch("core.content_engine.tracing_v13.X")`
3. Remove `langfuse>=2.0` from `requirements.txt`
4. Remove `langfuse_public_key`, `langfuse_secret_key`, `langfuse_host` from `core/config/settings.py`
5. Update `docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md`
6. Update `_memory/context.json` — remove `langfuse 3.14.1 installed`

---

## Risks (updated)

| Risk | Severity | Mitigation |
|------|----------|------------|
| `tracing_v13` compat kwargs miss one caller | HIGH | After Phase 0, run `python -c "from core.content_engine import pipeline"` — import errors surface immediately |
| Manifest shape for `pull_prompt_commit()` differs from expected | MEDIUM | Add `try/except KeyError` in extraction, fallback to local, log the raw manifest for debugging |
| contextvars not propagated across `asyncio.create_task` boundaries | MEDIUM | `asyncio.create_task` copies context by default in Python 3.7+ — verified safe |
| `MemorySaver` serialization crash if span leaks into state | HIGH | Codex confirmed this is real. Phase 2 uses contextvars explicitly to avoid it. Add a checkpoint serialization test as a regression guard |
| Langfuse references in docs/sprint files break acceptance grep | LOW | Acceptance criterion: `grep -r "langfuse" core/ api/ tests/ requirements.txt` (scope to code only) |

---

## Test Changes Required

### Existing test mocks (Phase 5)
```bash
# Files to update (all 3 have Langfuse mock paths):
tests/content_engine/test_eeat_judge.py  # patch("core.content_engine.evaluator.eeat_judge.log_generation")
# (this already patches the name in the module under test — safe, no path change needed)
```
Actually: `patch("core.content_engine.evaluator.eeat_judge.log_generation")` patches the NAME as imported into eeat_judge, not the source module. After import swap in Phase 1, this still works with no change.

### New tests needed
1. **`tracing_v13` compat test** — call every function with old Langfuse kwargs, assert no `TypeError`
2. **Checkpoint serialization guard** — assert `build_topic_approval_graph().invoke(state_with_non_serializable, config)` raises early with clear error (not silently corrupting)
3. **`prompt_registry.py`** — unit tests: Hub success, Hub timeout, Hub key error (bad manifest), concurrent requests (lock), TTL expiry, local fallback
4. **`langgraph.json` import test** — assert all 3 graph entrypoints in the JSON are importable
5. **contextvars propagation test** — assert `get_current_span()` returns the span set by `set_current_span()` in a child coroutine

---

## Execution Order (v2)

```
Phase 0: tracing_v13 compat kwargs extension
    → run: python -c "from core.content_engine import pipeline" (smoke test)
Phase 1: import swaps (14 files + hidden line 175)
    → run: pytest tests/content_engine/ -v (full suite must pass)
Phase 2: graph_v13.py tracing (contextvars)
    → run: pytest tests/content_engine/test_graph_v13.py -v
Phase 3: prompt_registry.py + upload script
    → run: pytest tests/content_engine/test_prompt_registry.py -v (new tests)
Phase 4: langgraph.json
    → manual: langgraph dev (visual check)
Phase 5: cleanup — delete tracing.py, remove Langfuse from requirements + settings
    → run: pytest tests/ -v (full suite)
    → run: grep -r "langfuse" core/ api/ tests/ requirements.txt (must be zero hits)
```

---

## Files Changed Summary

### New
- `core/content_engine/prompt_registry.py`
- `scripts/upload_prompts_to_hub.py`
- `langgraph.json`
- `tests/content_engine/test_prompt_registry.py`

### Modified
- `core/content_engine/tracing_v13.py` (Phase 0 compat + contextvars)
- `core/content_engine/pipeline.py` (Phase 1 — 2 import sites)
- `core/content_engine/pipeline_v13.py` (Phase 2 — set_current_span calls)
- `core/content_engine/graph_v13.py` (Phase 2 — contextvars-based tracing in nodes)
- `core/content_engine/planner.py` (Phase 1)
- `core/content_engine/graph.py` (Phase 1)
- `core/content_engine/workers/dispatcher.py` (Phase 1)
- `core/content_engine/workers/drafter.py` (Phase 1)
- `core/content_engine/workers/outliner.py` (Phase 1)
- `core/content_engine/workers/formatter.py` (Phase 1)
- `core/content_engine/workers/fact_enricher.py` (Phase 1)
- `core/content_engine/evaluator/loop.py` (Phase 1)
- `core/content_engine/evaluator/structural.py` (Phase 1)
- `core/content_engine/evaluator/semantic.py` (Phase 1)
- `core/content_engine/evaluator/style_judge.py` (Phase 1)
- `core/content_engine/evaluator/factual_judge.py` (Phase 1)
- `core/content_engine/evaluator/eeat_judge.py` (Phase 1)
- Each `*_prompts.py` file — add `get_*_system_prompt()` getter (Phase 3)
- `core/config/settings.py` (Phase 5 — remove langfuse, add hub settings)
- `requirements.txt` (Phase 5 — remove langfuse)

### Deleted
- `core/content_engine/tracing.py` (Phase 5 — only after all tests green)

---

## Acceptance Criteria

- [ ] `grep -r "langfuse" core/ api/ tests/ requirements.txt` → zero hits
- [ ] `core/content_engine/tracing.py` deleted
- [ ] All 15 migrated files import from `tracing_v13`
- [ ] `tracing_v13` accepts all old Langfuse kwargs without `TypeError`
- [ ] `graph_v13.py` nodes create child spans via contextvars (no `parent_span` in state)
- [ ] `prompt_registry.py` with Hub pull, TTL cache, threadsafe lock, local fallback
- [ ] `scripts/upload_prompts_to_hub.py` uploads all 11 prompts
- [ ] `langgraph.json` exists with 3 graph entries (all importable)
- [ ] `langsmith_use_hub` setting added with `False` default
- [ ] All existing tests pass (`pytest tests/ -v`)
- [ ] New tests for `prompt_registry.py` pass
- [ ] Checkpoint serialization guard test passes
