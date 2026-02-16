# Content Generation Engine — Implementation Plan

## Context

Pipeline 3 of the Deep Presence content strategy platform. Pipelines 1 (Research Artifacts) and 2 (Gap Analysis) are already implemented. This engine consumes their outputs — company context, persona profiles, writing style guides, gap reports, and cluster content specs — to auto-generate optimized content that fills identified AI citation gaps.

The architecture follows two proven Anthropic patterns: **Orchestrator-Workers** for parallel content production and **Evaluator-Optimizer** for automated QA. LangGraph handles HITL review (same pattern as research pipeline).

---

## Directory Structure

```
core/
├── models/
│   └── content_generation.py          # NEW — All Pydantic models
├── content_engine/
│   ├── __init__.py
│   ├── pipeline.py                    # NEW — Top-level async orchestrator
│   ├── planner.py                     # NEW — Stage 1: Strategic Planner
│   ├── tracing.py                     # NEW — Langfuse instrumentation
│   ├── graph.py                       # NEW — Stage 4: LangGraph HITL
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── dispatcher.py             # NEW — Parallel brief dispatch
│   │   ├── outliner.py               # NEW — Step 1: Outline generation
│   │   ├── drafter.py                # NEW — Step 2: Content drafting
│   │   ├── fact_enricher.py          # NEW — Step 3: Perplexity fact verification
│   │   └── formatter.py             # NEW — Step 4: Style formatting (Haiku)
│   ├── evaluator/
│   │   ├── __init__.py
│   │   ├── loop.py                   # NEW — Eval-optimize orchestrator
│   │   ├── structural.py             # NEW — Deterministic structural checks
│   │   ├── semantic.py               # NEW — Embedding proximity eval
│   │   ├── style_judge.py            # NEW — LLM style evaluation (Haiku)
│   │   └── factual_judge.py          # NEW — LLM factual grounding (Sonnet)
│   └── prompts/
│       ├── __init__.py
│       ├── planner_prompts.py        # NEW — Planner system/user prompts
│       ├── outliner_prompts.py
│       ├── drafter_prompts.py
│       ├── enricher_prompts.py
│       ├── formatter_prompts.py
│       ├── style_judge_prompts.py
│       └── factual_judge_prompts.py

scripts/
└── run_content_engine.py              # NEW — CLI entry point

tests/
└── content_engine/
    ├── __init__.py
    ├── conftest.py                    # NEW — Shared fixtures
    ├── test_models.py
    ├── test_planner.py
    ├── test_outliner.py
    ├── test_drafter.py
    ├── test_fact_enricher.py
    ├── test_formatter.py
    ├── test_dispatcher.py
    ├── test_structural.py
    ├── test_evaluator.py
    ├── test_graph.py
    └── test_integration.py

artifacts/
└── content/{company-slug}/
    ├── briefs.json                    # Planner output
    ├── content/
    │   └── brief-{N}/
    │       ├── outline.json
    │       ├── draft.md
    │       ├── enriched.md
    │       ├── formatted.md
    │       ├── eval_history.json
    │       └── final.md               # Approved content
    └── run_metadata.json
```

---

## Pydantic Models (`core/models/content_generation.py`)

### Input Model
```python
class ContentGenerationInput(BaseModel):
    company_name: str
    domain: str
    company_context_path: Optional[str] = None
    persona_paths: List[str] = Field(default_factory=list)
    style_guide_path: Optional[str] = None
    gap_report_json_path: Optional[str] = None
    generation_spec_json_path: Optional[str] = None
    analysis_json_path: Optional[str] = None
    max_briefs: int = 10
    max_concurrent_workers: int = 3
    max_revision_cycles: int = 2
    auto_approve: bool = False
    skip_stages: List[int] = Field(default_factory=list)
```

### Stage 1 Output
```python
class TargetQuery(BaseModel):
    query_text: str
    cluster_name: str
    embedding: Optional[List[float]] = None

class ContentBrief(BaseModel):
    brief_id: str
    title: str
    target_queries: List[TargetQuery] = Field(default_factory=list)
    target_cluster: str = ""
    content_format: Literal["long_blog","short_faq","pillar_page","comparison","how_to"] = "long_blog"
    funnel_stage: Literal["awareness","consideration","decision","retention"] = "awareness"
    channel: Literal["blog","help_center","landing_page","resource_hub"] = "blog"
    priority_score: float = 0.0
    target_word_count: int = 1500
    required_structural_elements: List[str] = Field(default_factory=list)
    key_topics: List[str] = Field(default_factory=list)
    key_angles: List[str] = Field(default_factory=list)
    competitor_exemplars: List[str] = Field(default_factory=list)
    semantic_threshold: float = 0.65

class PlannerOutput(BaseModel):
    briefs: List[ContentBrief] = Field(default_factory=list)
    planning_metadata: Dict[str, Any] = Field(default_factory=dict)
```

### Stage 2 Output
```python
class OutlineSection(BaseModel):
    heading: str
    level: int = 2
    key_points: List[str] = Field(default_factory=list)
    target_word_count: int = 300

class ContentOutline(BaseModel):
    brief_id: str
    title: str
    sections: List[OutlineSection] = Field(default_factory=list)
    total_target_words: int = 1500

class ContentDraft(BaseModel):
    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0

class EnrichedDraft(BaseModel):
    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0
    facts_added: List[Dict[str, str]] = Field(default_factory=list)

class FormattedContent(BaseModel):
    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0
    header_count: int = 0
    list_count: int = 0
    stat_count: int = 0
    citation_count: int = 0
```

### Stage 3 Output
```python
class DimensionResult(BaseModel):
    dimension: str  # "structural"|"semantic"|"style"|"factual"
    passed: bool = False
    score: float = 0.0
    feedback: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)

class EvalResult(BaseModel):
    brief_id: str
    cycle: int = 0
    dimensions: List[DimensionResult] = Field(default_factory=list)
    overall_passed: bool = False
    overall_score: float = 0.0

class RevisionHistory(BaseModel):
    brief_id: str
    cycles: List[EvalResult] = Field(default_factory=list)
    final_passed: bool = False
```

### Stage 4 Output
```python
class ContentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"

class ContentPiece(BaseModel):
    brief_id: str
    title: str
    status: ContentStatus = ContentStatus.PENDING
    final_markdown: str = ""
    eval_summary: Dict[str, Any] = Field(default_factory=dict)
    human_notes: Optional[str] = None
    artifact_path: Optional[str] = None

class ContentGenerationOutput(BaseModel):
    company_slug: str
    total_briefs: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    pieces: List[ContentPiece] = Field(default_factory=list)
    run_metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## Stage 1: Strategic Planner (`core/content_engine/planner.py`)

**Pattern:** Single LLM call with structured JSON output — NOT an agent.

```python
async def plan_content(input_data: ContentGenerationInput) -> PlannerOutput:
```

- **Model:** Sonnet 4.5 via `AsyncAnthropic` (raw SDK, no LangChain)
- **Inputs:** Company context (md), gap report (json), generation spec (json), persona (md)
- **Prompt:** System prompt with role + structured output instructions. User prompt with all artifacts + max_briefs constraint.
- **Output:** `PlannerOutput` parsed from JSON response via Pydantic
- **Tracing:** Single Langfuse generation logged
- **Cost:** ~$0.05-0.10, ~30s

---

## Stage 2: Orchestrator-Workers (`core/content_engine/workers/`)

**Pattern:** Semaphore-controlled parallel dispatch (reuses `s3_search_platforms.py` pattern).

### Dispatcher (`dispatcher.py`)
```python
async def dispatch_workers(
    briefs: List[ContentBrief],
    input_data: ContentGenerationInput,
    style_guide_md: str,
    company_context_md: str,
    max_concurrent: int = 3,
) -> List[FormattedContent]:
```

Uses `asyncio.Semaphore(max_concurrent)` + `asyncio.gather()`.

### Worker Chain (per brief)
```
Brief → Outliner (Sonnet) → Drafter (Sonnet) → Fact Enricher (Perplexity sonar-pro) → Formatter (Haiku)
```

| Step | File | Model | Cost | Latency |
|------|------|-------|------|---------|
| Outliner | `outliner.py` | Sonnet 4.5 | ~$0.03 | ~15s |
| Drafter | `drafter.py` | Sonnet 4.5 | ~$0.15-0.30 | ~60-90s |
| Fact Enricher | `fact_enricher.py` | Perplexity sonar-pro | ~$0.08-0.15 | ~30-45s |
| Formatter | `formatter.py` | Haiku 4.5 | ~$0.01 | ~10s |

**LLM calls:** Raw `AsyncAnthropic` for Sonnet/Haiku. Raw httpx/Perplexity SDK via `asyncio.to_thread()` for fact enrichment.

**CLI progress:**
```
  [2/4] Content Workers .....................
         Worker #1: Outlining "409A Valuation for Startups..."
         Worker #1: Drafting "409A Valuation for Startups..."
         Worker #2: Outlining "ASC 718 Explained..."
         Worker #1: DONE (2,847 words, 8 headers, 12 citations)
         Workers complete: 10/10 briefs ............ 142.5s
```

---

## Stage 3: Evaluator-Optimizer Loop (`core/content_engine/evaluator/`)

**Pattern:** 4 eval dimensions run in parallel via `asyncio.gather()`. Max 2 revision cycles.

### Evaluator Loop (`loop.py`)
```python
async def evaluate_and_optimize(
    content: FormattedContent,
    brief: ContentBrief,
    company_context_md: str,
    style_guide_md: str,
    max_cycles: int = 2,
) -> tuple[FormattedContent, RevisionHistory]:
```

### 4 Evaluation Dimensions

| Dimension | File | Type | Model | Threshold | Cost |
|-----------|------|------|-------|-----------|------|
| Structural | `structural.py` | Deterministic | None | >= 0.8 | $0 |
| Semantic | `semantic.py` | Embedding | OpenAI embed | >= 0.65 | ~$0.001 |
| Style | `style_judge.py` | LLM-as-Judge | Haiku 4.5 | >= 0.7 | ~$0.03 |
| Factual | `factual_judge.py` | LLM-as-Judge | Sonnet 4.5 | >= 0.7 | ~$0.05 |

**Structural checks (8 criteria, pure Python):** Word count range, header count, list presence, stats presence, citation count, heading hierarchy, no empty sections, required elements present.

**Semantic:** Embed content via `async_embed_texts()` (reuse from `core/shared_tools/async_embedding_client.py`), compare cosine similarity to target query embeddings.

**Revision logic:** If any dimension fails → compile feedback from failed dimensions → re-run Drafter → Fact Enricher → Formatter (skip Outliner) → re-evaluate. If still failing after 2 cycles → flag for HITL with eval results attached.

**CLI progress:**
```
  [3/4] Evaluator Loop ......................
         brief-001: Structural PASSED (0.88), Semantic PASSED (0.72),
                    Style PASSED (0.81), Factual FAILED (0.62)
         brief-001: Revision cycle 1 — fixing factual accuracy
         brief-001: ALL PASSED (overall: 0.80)
         Evaluation complete: 8/10 passed ........... 89.4s
```

---

## Stage 4: HITL with LangGraph (`core/content_engine/graph.py`)

**Pattern:** Same as `core/research/graphs/company_research.py` — `StateGraph(dict)` with `interrupt()`.

```python
def build_content_review_graph():
    graph = StateGraph(dict)
    graph.add_node("present_content", _present_content)
    graph.add_node("approval_gate", _approval_gate)       # interrupt() here
    graph.add_node("route", _route)
    graph.add_node("apply_edits", _apply_edits)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("present_content")
    graph.add_edge("present_content", "approval_gate")
    graph.add_edge("approval_gate", "route")
    graph.add_conditional_edges("route", ..., {
        "approve": "finalize",
        "edit": "apply_edits",
        "reject": END,
    })
    graph.add_edge("apply_edits", "approval_gate")  # loop back
    graph.add_edge("finalize", END)
    return graph.compile()
```

- `auto_approve` flag skips interrupt (same as research pipeline)
- Approved content saved to `artifacts/content/{slug}/content/brief-{N}/final.md`
- Resume tokens: `{"approval_decision": "approve"|"edit"|"reject", "editor_notes": "..."}`

---

## Langfuse Tracing (`core/content_engine/tracing.py`)

### Hierarchy
```
Session: content-gen-{slug}-{timestamp}
  └── Trace: planner              (Stage 1)
  │     └── Generation: plan_content
  └── Trace: worker/{brief_id}    (Stage 2, per brief)
  │     └── Span: outliner → Generation
  │     └── Span: drafter → Generation
  │     └── Span: fact_enricher → Generation(s)
  │     └── Span: formatter → Generation
  └── Trace: evaluator/{brief_id} (Stage 3, per brief)
  │     └── Span: structural_check (score attached)
  │     └── Span: semantic_check (score attached)
  │     └── Span: style_judge → Generation (score attached)
  │     └── Span: factual_judge → Generation (score attached)
  │     └── Span: revision_cycle_{n} (if needed)
  └── Trace: review/{brief_id}    (Stage 4)
        └── Span: human_decision (score attached)
```

### Scores Tracked
| Score | Type | Source |
|-------|------|--------|
| `structural_pass` | Boolean | Code |
| `semantic_similarity` | Numeric (0-1) | Embedding |
| `style_alignment` | Numeric (0-1) | LLM Judge |
| `factual_grounding` | Numeric (0-1) | LLM Judge |
| `revision_count` | Numeric (0-2) | Code |
| `human_decision` | Categorical | User |
| `total_cost` | Numeric ($) | Langfuse auto |

### Implementation
Lazy singleton `Langfuse` client. Helper functions: `create_session()`, `create_trace()`, `log_generation()`, `log_score()`. Each stage receives the `session_id` and creates its own trace.

---

## Pipeline Orchestrator (`core/content_engine/pipeline.py`)

**Pattern:** Mirrors `core/gap_analysis/pipeline.py` — async orchestrator with `skip_stages`, per-stage timing, CLI progress.

```python
async def run_content_generation(
    input_data: ContentGenerationInput,
) -> ContentGenerationOutput:
```

**CLI output:**
```
────────────────────────────────────────────────
  Content Generation Pipeline — carta
────────────────────────────────────────────────

  [1/4] Strategic Planner .................. 32.1s
  [2/4] Content Workers .................... 142.5s
  [3/4] Evaluator Loop ..................... 89.4s
  [4/4] Human Review ....................... 0.0s (auto-approved)

────────────────────────────────────────────────
  Done — 264.0s total | 10 approved, 0 rejected
────────────────────────────────────────────────
```

---

## Settings Additions (`core/config/settings.py`)

```python
# Content Generation Engine
content_engine_planner_model: str = "claude-sonnet-4-5-20250929"
content_engine_worker_model: str = "claude-sonnet-4-5-20250929"
content_engine_formatter_model: str = "claude-haiku-4-5-20250929"
content_engine_style_judge_model: str = "claude-haiku-4-5-20250929"
content_engine_factual_judge_model: str = "claude-sonnet-4-5-20250929"
content_engine_fact_enricher_model: str = "sonar-pro"

# Langfuse
langfuse_public_key: str | None = None
langfuse_secret_key: str | None = None
langfuse_host: str = "https://cloud.langfuse.com"

# Concurrency
content_engine_max_concurrent_workers: int = 3
content_engine_max_revision_cycles: int = 2
```

All have defaults — no breakage to existing `.env.local`.

---

## Dependencies

Add to `requirements.txt`:
```
langfuse>=2.0
```

Everything else already exists: `anthropic`, `openai`, `langgraph`, `httpx`, `pydantic`, `perplexityai`.

---

## CLI Entry Point (`scripts/run_content_engine.py`)

```bash
python scripts/run_content_engine.py \
  --company-name "Carta" --domain carta.com \
  --company-context-path artifacts/company_context/carta.md \
  --persona-path artifacts/personas/carta__persona-icp.md \
  --style-guide-path artifacts/style_guides/carta.md \
  --gap-slug carta \
  --max-briefs 5 --max-workers 3 --max-revisions 2 \
  --auto-approve
```

Follows exact pattern of `scripts/run_gap_analysis.py`.

---

## Reusable Existing Code

| Utility | Location | Used By |
|---------|----------|---------|
| `async_embed_texts()` | `core/shared_tools/async_embedding_client.py` | Semantic evaluator |
| `_retry_async()` | `core/shared_tools/async_embedding_client.py` | All LLM calls |
| Semaphore concurrency | `core/gap_analysis/steps/s3_search_platforms.py` | Worker dispatcher |
| CLI progress helpers | `core/gap_analysis/pipeline.py` | Pipeline orchestrator |
| LangGraph interrupt pattern | `core/research/graphs/company_research.py` | HITL graph |
| FakeChromaCollection + mock fixtures | `tests/conftest.py` | Test mocking |
| Pydantic BaseSettings | `core/config/settings.py` | New settings fields |

---

## Implementation Order

### Sprint A: Foundation (Tasks 1-5)
- T-CG-1: Define all Pydantic models (`core/models/content_generation.py`)
- T-CG-2: Write model validation tests
- T-CG-3: Add settings fields to `core/config/settings.py`
- T-CG-4: Create Langfuse tracing module (`core/content_engine/tracing.py`)
- T-CG-5: Create pipeline skeleton with CLI helpers (`core/content_engine/pipeline.py`)

### Sprint B: Strategic Planner (Tasks 6-8)
- T-CG-6: Write planner tests (TDD)
- T-CG-7: Implement Strategic Planner (`core/content_engine/planner.py`)
- T-CG-8: Wire planner into pipeline + create prompts

### Sprint C: Workers (Tasks 9-19)
- T-CG-9/10: Outliner (test → impl)
- T-CG-11/12: Drafter (test → impl)
- T-CG-13/14: Fact Enricher (test → impl)
- T-CG-15/16: Formatter (test → impl)
- T-CG-17/18: Dispatcher with parallel dispatch (test → impl)
- T-CG-19: Wire workers into pipeline

### Sprint D: Evaluator (Tasks 20-27)
- T-CG-20/21: Structural evaluator (test → impl)
- T-CG-22: Semantic evaluator
- T-CG-23: Style judge
- T-CG-24: Factual judge
- T-CG-25/26: Evaluator loop with revision logic (test → impl)
- T-CG-27: Wire evaluator into pipeline

### Sprint E: HITL + Integration (Tasks 28-33)
- T-CG-28/29: LangGraph HITL graph (test → impl)
- T-CG-30: Wire HITL into pipeline
- T-CG-31: CLI entry point (`scripts/run_content_engine.py`)
- T-CG-32: End-to-end integration test
- T-CG-33: Test conftest with shared fixtures

---

## Verification Plan

1. **Unit tests:** `pytest tests/content_engine/ -v` — every module tested with mocked LLM calls
2. **Integration test:** Full pipeline with `--auto-approve` and all LLM calls mocked
3. **Live smoke test:** Single brief with real API calls, verify:
   - Langfuse traces appear in dashboard
   - CLI shows worker progress messages
   - Artifact files created at expected paths
   - Eval scores are reasonable
4. **Regression:** Existing tests still pass (`pytest tests/ -v`)

---

## Codex Review Findings (Incorporated)

Codex (o3) reviewed the plan against the architecture doc. Key issues identified and how we'll address them:

### Critical Fixes (Must-Have)

1. **`return_exceptions=True` in `asyncio.gather()`** — Failing one worker must NOT cancel the batch. Use `return_exceptions=True` and surface per-brief errors individually.

2. **`safe_parse()` utility for LLM JSON responses** — Wrap every Pydantic `model_validate()` call with retry + truncation strategy for malformed LLM JSON. Add to `core/content_engine/tracing.py` or a new `core/content_engine/utils.py`.

3. **Extend `_retry_async()` for Anthropic errors** — Current implementation only retries OpenAI errors. Add `anthropic.RateLimitError` and `anthropic.APIError` to the retry set. Create a shared `_retry_async_anthropic()` or make the existing one provider-agnostic.

4. **Context window guard** — Pre-flight token count check before LLM calls. Truncate company context / persona to fit within model limits (~180K tokens for Sonnet 4.5). Add `_estimate_tokens()` helper.

5. **Directory creation** — All artifact paths must use `os.makedirs(..., exist_ok=True)` before writing. (Already the pattern in gap analysis — carry forward.)

6. **Early exit when `max_revision_cycles=0`** — Skip evaluator loop entirely, pass directly to HITL.

### Model Alignment with Architecture Doc

7. **Add `StructuralTargets` nested model** — Architecture doc specifies this. Add as a field on `ContentBrief` with cluster-derived structural targets (header rates, list rates, etc.). Derive from `ClusterContentSpec` in the planner.

8. **Add `word_count_range: Tuple[int, int]`** — Architecture doc uses range, not single target. Change `target_word_count` to `word_count_range` on `ContentBrief`. Structural eval checks both min and max.

### Nice-to-Have (v1.1)

- HITL timeout fallback (auto-reject after configurable timeout) — defer to v1.1
- `--offline` flag for fact enricher skip — defer to v1.1
- Cost budget cap via Langfuse — defer to v1.1

---

## Git Branch

Create `feat/content-engine-v1.0.0` before any implementation begins.
