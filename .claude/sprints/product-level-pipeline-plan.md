# Product-Level Pipeline Execution — Sprint Plan & Walkthrough

> **Sprint:** product-level-pipeline
> **Branch:** `feat/front-back`
> **Created:** 2026-02-26
> **Status:** COMPLETE (2026-02-26) — All 5 phases done, 882 tests passing (114 new), 0 failures
> **Goal:** Enable each product (Ramp Corporate Card, Ramp Travel, etc.) to run its own independent gap analysis, content, and research pipelines with product-specific artifact directories, lock keys, and LLM prompt context.

---

## Context

The platform previously ran all pipelines at the **company level** — one run per company, artifacts at `artifacts/gap_analysis/{company_slug}/`. Ramp (client) has multiple distinct products that compete in different AI-search citation contexts. Product-specific queries + product-specific context = better per-product citation gap analysis.

**Pre-implementation:** Codex gpt-5.3-codex plan review (high reasoning) — 6 CRITICAL + 7 WARNING + 4 INFO findings incorporated. See "Codex Review Disposition" at the bottom.

---

## Design Decisions

### D1 — Effective Slug Pattern
`artifacts/{type}/{company_slug}__{product_slug}/` — double underscore separator.

```python
# Examples
"ramp"                          # company-level (unchanged)
"ramp__ramp-corporate-card"     # product-level (new)
"ramp__ramp-travel"             # another product
```

Double underscore is unambiguous since individual slugs use `[a-z0-9-]` only — no underscores.

### D2 — Research Artifact Inheritance (Exact Fallback Chain)
Product runs share company research artifacts. Ordered fallback, stops at first match:
1. `artifacts/company_context/{effective_slug}.md` — product-specific research (optional)
2. `artifacts/company_context/{company_slug}.md` — company research (shared)
3. `None` — pipeline runs without research context

Same chain for personas and style guides. Artifacts snapshotted at run start.

### D3 — `effective_slug` Stored on `PipelineTask`
Eliminates re-derivation in all 4 teardown paths (3 pipeline runners + cancel endpoint).

```python
class PipelineTask(BaseModel):
    product_slug: Optional[str] = None      # which product (if any)
    effective_slug: Optional[str] = None    # lock key + artifact dir slug
```

Company-level lock `"ramp"` and product-level lock `"ramp__ramp-corporate-card"` are **independent** — simultaneous runs allowed.

### D4 — Central `RunScope` + `_resolve_scope()` (DRY)
All 3 runners call one function at startup:

```python
@dataclass
class RunScope:
    company_slug: str
    product_slug: Optional[str]
    effective_slug: str
    product_name: Optional[str]
    product_description: Optional[str]
    product_domain: Optional[str]

def _resolve_scope(company_slug: str, product_slug: Optional[str], auth_store: AuthStore) -> RunScope:
    """Looks up product from auth_store. Builds effective_slug."""
```

### D5 — Prompt Injection Guard
Product context injected only when `product_slug AND product_name` both non-null — prevents injection when product exists but wasn't found in auth_store.

```python
# Guard pattern used in s2_generate_queries.py and planner.py
if input_data.product_slug and input_data.product_name:
    product_context = _PRODUCT_CONTEXT_BLOCK.format(...)
else:
    product_context = ""    # zero prompt drift for company-level runs
```

---

## Phase 1 — Product CRUD (35 tests)

### Files Changed
- `api/tasks/models.py` — add `product_slug`, `effective_slug` to `PipelineTask`
- `api/auth/store.py` — add `add/get/update/remove_product()` methods
- `api/schemas/company.py` — add `ProductCreateRequest`, `ProductUpdateRequest`, `ProductDetailResponse`
- `api/routers/companies.py` — add 4 product endpoints

### New Endpoints
```
POST   /api/v1/companies/{slug}/products
GET    /api/v1/companies/{slug}/products/{product_slug}
PUT    /api/v1/companies/{slug}/products/{product_slug}
DELETE /api/v1/companies/{slug}/products/{product_slug}
```

### Key Logic
- Slug validation: `^[a-z0-9][a-z0-9-]*$` — 422 on invalid, 409 on duplicate
- **Cross-tenant check:** `product.company_id == company.id` on every endpoint (Codex CRITICAL finding)
- `add_product()` appends to `company.products` list, saves JSON

### Tests: `tests/api/test_products.py` (35 tests)
- CRUD happy paths
- 422 on invalid slug format
- 409 on duplicate slug
- 404 on missing company or product
- Ownership verification (different company cannot access)

---

## Phase 2 — Task Infrastructure (16 tests)

### Files Changed
- `api/tasks/store.py` — `create_task()` gains `product_slug`, uses effective_slug for lock
- `api/schemas/common.py` — `product_slug`, `effective_slug` on `PipelineRunResponse`, `TaskResponse`, `TaskSummary`
- `api/routers/tasks.py` — `cancel` endpoint uses `task.effective_slug or task.company_slug`

### Key Logic
```python
def create_task(self, pipeline, company_slug, product_slug=None) -> PipelineTask:
    effective = f"{company_slug}__{product_slug}" if product_slug else company_slug
    self.acquire_slug_lock(effective)   # lock on effective slug, not bare slug
    task = PipelineTask(
        ...,
        product_slug=product_slug,
        effective_slug=effective,       # stored for all 4 teardown paths
    )
```

### Tests: `tests/api/test_task_store_product.py` (16 tests)
- `create_task(product_slug=...)` uses effective_slug as lock key
- Company-level `"ramp"` and product-level `"ramp__card"` locks are independent (both 202)
- Same-product second run conflicts (409)
- `list_tasks(product_slug=...)` filter
- `effective_slug` present in response

---

## Phase 3 — Pipeline Execution Wiring (36 tests)

### Files Changed
- `core/models/gap_analysis.py`, `content_generation.py`, `artifacts.py` — add `product_slug/name/description` fields
- `api/schemas/common.py` — add `product_slug` to start request schemas
- `api/routers/gap_analysis.py`, `content.py`, `research.py` — pass `product_slug` to `create_task()` and runners
- `api/tasks/runner.py` — add `RunScope`, `_resolve_scope()`, update all 3 runners

### runner.py wiring pattern (same for all 3 pipelines)
```python
async def run_gap_pipeline_task(task_id, request, ...):
    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, 'product_slug', None)
    scope = _resolve_scope(company_slug, product_slug, auth_store)

    # Research artifacts from bare company slug (inheritance, not product)
    resolved = resolve_artifacts(company_slug, artifacts_root,
                                 effective_slug=scope.effective_slug)

    input_data = GapAnalysisInput(
        company_slug=scope.effective_slug,   # ← artifact dir uses effective slug
        product_slug=scope.product_slug,
        product_name=scope.product_name,
        product_description=scope.product_description,
        domain=scope.product_domain or request.domain,
        **resolved,
    )
    ...
    finally:
        task_store.release_slug_lock(task.effective_slug or task.company_slug)
```

### Artifact fallback chain in `resolve_artifacts()`
```python
# For each artifact type:
# 1. Try effective_slug path first (product-specific, if it exists)
# 2. Fall back to company_slug path (company-level, shared)
# 3. Return None if neither exists
```

### Tests: `tests/api/test_gap_analysis_product.py` (36 tests)
- `_derive_slug()` unit tests
- `_resolve_scope()` — product found, not found, no product_slug
- `resolve_artifacts()` fallback chain (context, personas, style)
- Start with `product_slug` → 202, effective_slug in response
- Company + product concurrent runs → both 202
- Same product second run → 409
- Conflict test pattern: patch `asyncio.create_task` to `MagicMock()` to prevent lock release

---

## Phase 4 — Product Prompts (15 tests)

### Files Changed
- `core/gap_analysis/steps/s2_generate_queries.py` — `_PRODUCT_CONTEXT_BLOCK`, `{product_context_block}` slot
- `core/content_engine/prompts/planner_prompts.py` — `_PRODUCT_FOCUS_BLOCK`, `product_context_md` param
- `core/content_engine/planner.py` — builds `product_context_md` and passes it

### s2 Prompt Change
```python
_PRODUCT_CONTEXT_BLOCK = """\

SPECIFIC PRODUCT SCOPE — This gap analysis targets a single product, not the full company:
  Product name:        {product_name}
  Product domain:      {product_domain}
  Product description: {product_description}

CRITICAL INSTRUCTIONS FOR PRODUCT-SCOPED QUERIES:
- Treat this PRODUCT as the subject, not the parent company's full portfolio
- The "category" for these queries is the product's specific niche
...
"""
```

Slot `{product_context_block}` inserted in `_QUERY_GEN_PROMPT` between COMPANY section and QUERY CLUSTER TAXONOMY. Defaults to `""` for company-level runs.

### Planner Prompt Change
```python
_PRODUCT_FOCUS_BLOCK = """\

## Specific Product Focus
**Product:** {product_name}
...
"""
```

Added `product_context_md: str = ""` param to `build_planner_user_prompt()`. Injected after `## Company` section.

### Tests: `tests/gap_analysis/steps/test_s2_product_context.py` (15 tests)
- `_PRODUCT_CONTEXT_BLOCK` has all 3 format slots
- `_build_seed_prompt()` with product context → contains block
- `_build_seed_prompt()` without → no block (zero drift)
- `generate_queries()` prompt capture with product input
- `build_planner_user_prompt()` product section position

---

## Phase 5 — Data Endpoints (12 tests)

### Files Changed
- `api/routers/gap_data.py` — `_effective()` helper, `product_slug` param on all 8 endpoints
- `api/routers/content_data.py` — same for all 3 endpoints
- `api/services/gap_data_service.py`, `content_data_service.py`, `brand_data_service.py` — updated `_SLUG_PATTERN`

### Router pattern
```python
def _effective(slug: str, product_slug: Optional[str]) -> str:
    return f"{slug}__{product_slug}" if product_slug else slug

@router.get("/summary")
def get_gap_summary(
    slug: str,
    product_slug: Optional[str] = Query(None),
    artifacts_root: Path = Depends(get_artifacts_root),
) -> GapSummaryResponse:
    return get_summary(artifacts_root, _effective(slug, product_slug))
    # service unchanged — just receives the effective slug
```

### Slug pattern update (all 3 service files)
```python
# Before: bare company slugs only
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# After: accepts effective slugs like ramp__ramp-corporate-card
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")
```

### Tests: 6 added to `test_gap_data.py` + 6 to `test_content_data.py`
- `?product_slug=` → reads from effective slug dir
- Independent company and product artifact dirs
- Missing product dir → 404 (detail) or 200 empty (list)
- All 11 endpoints accept param without 422

---

## Artifact Directory Structure

```
artifacts/
├── gap_analysis/
│   ├── ramp/                                  # Company-level (existing, unchanged)
│   └── ramp__ramp-corporate-card/             # Product-level (new)
├── content/
│   ├── ramp/
│   └── ramp__ramp-corporate-card/
├── company_context/
│   ├── ramp.md                               # Company research — shared by fallback
│   └── ramp__ramp-corporate-card.md          # Product research (optional)
├── personas/
│   └── ramp__persona-icp.md                  # Always company-level (shared)
└── style_guides/
    └── ramp.md                               # Always company-level (shared)
```

---

## Test Fixtures Lesson Learned

**Conflict test pattern:** To test that a second request for the same product returns 409, you must prevent the background async task from starting (and releasing the slug lock between requests):

```python
# BAD — task starts, completes, releases lock before second request
with patch("api.routers.gap_analysis.asyncio.create_task") as mock:
    mock.return_value = asyncio.ensure_future(some_coro())  # still runs!
    r1 = client.post("/start", json={...})
    r2 = client.post("/start", json={...})  # lock already released → 202 not 409

# GOOD — task never starts, lock held between requests
with patch("api.routers.gap_analysis.asyncio.create_task") as mock:
    mock.return_value = MagicMock()  # returns immediately, coroutine never awaited
    r1 = client.post("/start", json={...})
    r2 = client.post("/start", json={...})  # lock still held → 409 ✓
```

---

## Codex Review Disposition

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| 1 | CRITICAL | Lock teardown mismatch — `release_slug_lock(company_slug)` in 4 paths | ✅ Fixed — `task.effective_slug` on PipelineTask |
| 2 | CRITICAL | Cancel endpoint releases bare company slug | ✅ Fixed — uses `task.effective_slug or task.company_slug` |
| 3 | CRITICAL | Cross-tenant auth: product.company_id == user.company_id missing | ✅ Fixed — added to all 4 product endpoints |
| 4 | CRITICAL | Content runner uses bare slug for artifact dir | ✅ Fixed — uses `scope.effective_slug` |
| 5 | CRITICAL | Artifact inheritance fallback chain order not defined | ✅ Fixed — explicit ordered chain in D2 |
| 6 | CRITICAL | All new Pydantic fields must have Optional defaults | ✅ Confirmed throughout |
| 7 | WARNING | HITL resume path may use request scope not stored task scope | ✅ Fixed — approve reads from `task.effective_slug` |
| 8 | WARNING | Prompt guard not defined | ✅ Fixed — `product_slug AND product_name` guard |
| 9 | WARNING | effective_slug computation will drift across 11 endpoints | ✅ Fixed — `_effective()` helper in each router |
| 10 | WARNING | product_slug canonicalization not defined | ✅ Fixed — same regex as company_slug |
| 11 | WARNING | Concurrency semantics — company + product runs coexist | ✅ Confirmed — independent lock keys |
| 12 | INFO | Single scope resolver helper | ✅ Incorporated — `_resolve_scope()` in runner.py |
| 13 | INFO | Persist effective_slug on PipelineTask | ✅ Incorporated |
| 14 | INFO | GET /companies/{slug}/products/{product_slug} needed | ✅ Incorporated |

---

## Backward Compatibility

1. All new Pydantic fields are `Optional[str] = None` — existing JSON artifacts and task files deserialize without error
2. `GapAnalysisStartRequest` without `product_slug` works identically to today
3. `TaskStore.create_task(pipeline, company_slug)` call signature unchanged (product_slug is new optional kwarg)
4. S2 prompt slot `{product_context_block}` defaults to `""` — no impact on existing runs
5. Data endpoints without `?product_slug=` behave identically to today
6. Service functions receive the effective slug — no internal changes

---

## Deferred (Out of Scope for This Sprint)

- **Product comparison runs** — cross-product analysis (e.g., Corporate Card vs Travel)
- **Product-level personas** — separate persona files per product (can share company personas now)
- **Debugability endpoint** — resolved artifact/context view for a given scope
