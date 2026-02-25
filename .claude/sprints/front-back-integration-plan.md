# Backend API Completion Plan — Frontend Integration

> **Sprint:** front-back-integration
> **Branch:** `feat/front-back`
> **Created:** 2026-02-25
> **Status:** COMPLETE (2026-02-26) — All 4 phases done, 766 tests passing, 0 failures
> **Completed:** 2026-02-26
> **Goal:** Complete all backend endpoints required by the frontend, eliminate fixture/mock data dependency, and establish the company → product → employee data model.

---

## Context

The frontend dashboard (26 routes, Next.js 16) is fully built with sophisticated UI but relies on ~2,100 lines of hardcoded fixture data across 4 mock files. The backend has 17 working endpoints covering pipeline execution (start/monitor/approve) but lacks **data retrieval endpoints** for viewing results, metrics, and analytics.

**Key constraints from Aryan:**
1. **Company → Product → Employee model** — each employee belongs to one company, sees only their company's data
2. Companies can have multiple products; pipelines run at BOTH company-level and product-level
3. No Supabase/database yet — filesystem artifacts are source of truth (Supabase coming later)
4. Frontend renders its own charts from raw JSON (not iframes)
5. Pre-compute UMAP/t-SNE projections in s7 as JSON for fast reads
6. Defer Projects/Cycles entities to later sprint
7. Fix frontend types to match backend (not the other way around)
8. After content approval, background-update gap analysis embeddings (async, no full re-run)

---

## Data Model Vision (For Now + Supabase Future)

### Entity Relationships

```
Company (1)
  ├── Products (many)        — e.g., "Ramp Corporate Card", "Ramp Travel"
  ├── Employees/Users (many) — employees who log in
  │     └── Role: superuser | member | viewer
  └── Pipelines run at:
        ├── Company-level   — research, gap analysis, content for the whole company
        └── Product-level   — research, gap analysis, content for a specific product
```

### Pydantic Models

```python
class Company(BaseModel):
    id: str                              # UUID
    slug: str                            # kebab-case, used for artifact directories
    name: str                            # Display name
    domain: str                          # Primary domain
    created_at: datetime
    updated_at: datetime

class Product(BaseModel):
    id: str                              # UUID
    company_id: str                      # FK → Company.id
    slug: str                            # product-level slug
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class UserProfile(BaseModel):
    id: str                              # UUID
    company_id: str                      # FK → Company.id
    email: str
    name: str
    role: Literal["superuser", "member", "viewer"]
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
```

### Artifact Directory Structure (Current + Product Extension)

```
artifacts/
├── company_context/
│   ├── {company_slug}.md                    # Company-level
│   └── {company_slug}__{product_slug}.md    # Product-level (future)
├── personas/
│   ├── {company_slug}__persona-icp.md
│   └── {company_slug}__{product_slug}__persona-icp.md  # Future
├── style_guides/
│   ├── {company_slug}.md
│   └── {company_slug}__{product_slug}.md    # Future
├── gap_analysis/
│   ├── {company_slug}/                      # Company-level
│   └── {company_slug}__{product_slug}/      # Future
├── content/
│   ├── {company_slug}/
│   └── {company_slug}__{product_slug}/      # Future
└── _jobs/
    └── {task_id}.json
```

### Auth Model (v0 — Simple, pre-Supabase)

- JSON-file backed user store (`artifacts/_auth/users.json`)
- Password hashing with bcrypt
- JWT tokens for session management
- Middleware injects `company_slug` from JWT into request state
- v0: middleware in grace mode (doesn't block unauthenticated requests)
- Supabase migration: swap JWT for Supabase session, models → DB tables

---

## Phase 1: Foundation — Data Models, Company Profile, Auth Skeleton, API Fixes

**Status:** Complete (2026-02-25) — 423 tests
**Goal:** Core data models, company-scoped endpoint, auth skeleton, fix API mismatches.

### Endpoints

| Method | Path | Type | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/companies/{slug}` | New | Company profile with products, artifacts, latest runs |
| `GET` | `/api/v1/tasks` | Fix | Add `total` field and `company_slug` filter |
| `POST` | `/api/v1/content/start` | Fix | Add `gap_slug`, `max_concurrent_workers`, `max_revision_cycles`, `skip_stages` |

### New Files
- `core/models/organization.py` — Company, Product, UserProfile
- `api/auth/models.py` — Login/token models
- `api/auth/store.py` — JSON-backed user/company store
- `api/auth/middleware.py` — JWT middleware (grace mode)
- `api/routers/companies.py` — company profile endpoint
- `api/schemas/company.py` — response models

### Modified Files
- `api/app.py`, `api/schemas/common.py`, `api/routers/tasks.py`
- `api/tasks/store.py`, `api/routers/content.py`
- Frontend: `types/gap-analysis.ts`, `types/research.ts`, `types/content.ts`, `lib/api/gap-analysis.ts`

### Unblocks
- All pages: company data source, auth foundation

---

## Phase 2: Gap Analysis Data Endpoints

**Status:** Complete (2026-02-25) — 484 tests (before C1-C4 fixes → 500)
**Depends on:** Phase 1

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/companies/{slug}/gap-analysis/summary` | Executive summary, SPA, proximity stats |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/queries` | 72+ queries with filtering/sorting/pagination |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/clusters` | Cluster specs with centroid + SPA data |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/signals` | Structural signal averages (citation vs company) |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/platforms` | Per-platform citation breakdown |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/heatmap` | Query × cluster gap score matrix |

### New Files
- `api/routers/gap_data.py`, `api/schemas/gap_data.py`, `api/services/gap_data_service.py`

### Data Sources
- `gap_analysis_complete.json` (endpoints 2.1, 2.2, 2.3, 2.6 — pure reads + reshape)
- `enriched_citations.json` (endpoint 2.4 — new aggregation)
- `platform_results/*.jsonl` (endpoint 2.5 — cross-file aggregation)

### Unblocks
- Signal Analysis (all 6 tabs), Command Center, Embedding Lab (partial)

---

## Phase 3: Content Briefs + Embedding Projections

**Status:** Complete (2026-02-25) — 585 tests
**Depends on:** Phase 2

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/companies/{slug}/content/briefs` | Brief list with statuses + eval scores |
| `GET` | `/api/v1/companies/{slug}/content/briefs/{brief_id}` | Full detail + eval history |
| `GET` | `/api/v1/companies/{slug}/content/briefs/{brief_id}/{stage}` | Stage-specific content file |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/embeddings` | 2D UMAP/t-SNE projections |

### New Files
- `api/routers/content_data.py`, `api/schemas/content_data.py`
- `api/services/embedding_service.py`

### Pipeline Change
- `core/gap_analysis/steps/s7_visualize.py` — save `embedding_projections_{method}.json`

### Unblocks
- Content Pipeline (board/table/calendar), Embedding Lab scatter

---

## Phase 4: Brand Brain + Run History

**Status:** Complete (2026-02-26) — 766 tests (57 new)
**Depends on:** Phase 1

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/companies/{slug}/research/artifacts` | Research artifacts (context, personas, style guide) with full markdown content |
| `GET` | `/api/v1/companies/{slug}/runs` | Run history with summary metrics, pipeline/status/limit filters |
| `GET` | `/api/v1/companies/{slug}/gap-analysis/trend` | Historical SPA score trend across completed gap analysis runs |

### New Files
- `api/routers/brand_data.py` — 2 endpoints (research/artifacts, runs)
- `api/schemas/brand_data.py` — 8 response models (ArtifactContent, PersonaArtifact, ResearchArtifactsResponse, RunHistoryItem, RunHistoryResponse, SPATrendPoint, SPATrendResponse)
- `api/services/brand_data_service.py` — service layer with artifact detection, persona scanning, run history assembly, SPA trend computation, status mapping, duration formatting, step inference
- `tests/api/test_brand_data.py` — 57 TDD tests

### Modified Files
- `api/routers/gap_data.py` — added `GET /trend` endpoint (imports SPATrendResponse from brand_data schemas, get_spa_trend from brand_data_service)
- `api/app.py` — registered brand_data router

### Design Decisions
- **Status mapping:** Backend 6 statuses (running, pending_approval, completed, failed, cancelled, failed_restart) → Frontend 3 (running, completed, failed). `_STATUS_MAP` dict ensures `?status=running` catches `pending_approval` tasks too.
- **Persona file matching:** Only `{slug}__persona-*.md` files accepted (Codex CX-4 finding), not arbitrary `{slug}__*.md`.
- **Artifact priority:** `.md` (approved) > `.draft.md` (draft) > neither ("none").
- **SPA trend on gap_data router:** Semantically gap-analysis data, avoids extra router, URL prefix already exists.
- **Run history from TaskStore:** TaskStore.list_tasks() is the data source — result dict already contains `report_json` with all SPA metrics. No need to read artifact files.

### Codex Reviews
- **Plan review (gpt-5.3-codex):** 11 findings, 2 incorporated (status mapping + limit param)
- **Code review (gpt-5.3-codex):** 6 findings, 3 incorporated (status filter fix, persona prefix filter, mapped-status tests), 3 deferred

### Unblocks
- Brand Brain, Command Center trends, Signal Analysis run history

---

## Dependency Graph

```
Phase 1 (Foundation) ──┬──→ Phase 2 (Gap Data) ──→ Phase 3 (Content + Embeddings)
                       │
                       └──→ Phase 4 (Brand + History)
```

---

## Sprint Summary

| Metric | Value |
|--------|-------|
| Total endpoints added | 16 (GET) + fixes to 2 existing endpoints |
| Total response models | 50+ Pydantic models across 4 schema files |
| Total service functions | 25+ across 3 service files |
| Total new tests | 343 (Phase 1: 62, Phase 2: 61, C1-C4: 16, Phase 3: 85, Research: 109, Phase 4: 57) |
| Final test count | 766 passing, 0 failures |
| Codex reviews | 4 (2 plan reviews + 2 code reviews) |
| Findings incorporated | 13 total across all reviews |
| Files created | 18 new files |
| Files modified | 15+ existing files |

---

## Deferred Items

### From Code Reviews (fix before production)
- C5: `update_company()` allows overwriting `id`, `created_at`, `slug` via `**kwargs` — needs allowlist
- C6: `_CACHE` thread safety — non-atomic read-modify-write race under concurrent load
- C7: `_PATTERN_FLAGS` has_comparison_table → has_tables mismatch
- See `.claude/sprints/v1/review-findings-deferred.md` for full list (W1-W9, I1-I8, CX-1 through CX-10)

### From Sprint Scope
- Projects/Cycles entities — database sprint
- Product-level pipeline execution — model supports it, execution later
- Incremental embedding update after content approval — architecture ready
- Supabase integration — all models designed to migrate cleanly
- Route protection — auth middleware in grace mode
- Settings pages, knowledge doc upload
