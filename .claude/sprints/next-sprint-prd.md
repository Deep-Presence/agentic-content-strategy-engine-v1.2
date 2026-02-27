# PRD — Next Sprint
**Status:** DRAFT — Pending Aryan Approval
**Date:** 2026-02-28
**Preceding Sprint:** auth-migration-phase2 (1168 tests, Phase 1 + Phase 2 complete)
**Branch:** feat/front-back

---

## Current State

**SQLAlchemy Phase 1 + Auth Migration Phase 2 are COMPLETE.** The full DB infrastructure and auth service layer are in place:

### Phase 1 (complete)
- 31 ORM tables across 10 model files (`core/db/models/`)
- 12 Postgres enum types (`core/db/enums.py`)
- Hand-written Alembic migrations (0001 schema + 0002 HNSW indexes)
- Generic repo base + 8 domain repositories (`core/db/repositories/`)
- FastAPI DI wiring (`core/db/dependencies.py`)
- 44 DB tests (auto-skip without `TEST_DATABASE_URL`)

### Phase 2 (complete)
- Pure utility extraction: `core/auth/utils/` (passwords, tokens, domain)
- `AuthServiceProtocol` (runtime_checkable Protocol) — the new interface contract
- `JsonAuthService` wrapping AuthStore (backward compat, used by all tests)
- `DbAuthService` using DB repos (production path when `DATABASE_URL` set)
- 3 new repos: invite, product, pipeline_defaults
- DI switch: `get_auth_service()` returns appropriate implementation
- Middleware decoupled from AuthStore — uses `verify_token` utility directly
- All 8 routers + runner migrated from sync `AuthStore` to async `AuthServiceProtocol`
- 96 new tests (1080 passed + 88 skipped = 1168 total)

### What remains:
- **Phase 2B-services:** Wire service layers (GapData, ContentData, BrandData) to DB repos
- **Phase 2C-taskstore:** Migrate TaskStore from JSON files to DB
- **Phase 3:** Wire repos into FastAPI routes via DI (artifact reads from DB)
- **Backlog cleanup:** 34 deferred items in `.claude/sprints/pending/backlog.md`

---

## Sprint Options

Four possible directions. Pick one or combine.

---

## Option A — Review-Issues Cleanup Sprint

**Goal:** Burn down deferred review findings from the backlog. Harden the API layer before external usage.

**Effort estimate:** Small (1 session). Well-understood, scoped fixes.

### Tasks (Priority Order)

#### P0 — Security / Correctness

**T-pb34-me-auth:** PB-34 — `/me` endpoint missing `require_auth` dependency
- `api/routers/auth.py` — manually reads `request.state.user_id` instead of `Depends(require_auth)`
- Misses `is_active` check — deactivated users can query `/me`
- Fix: replace manual state read with `Depends(require_auth)`
- Add 1 test

**T-pb26-docstring:** PB-26 — Register endpoint docstring still says domain auto-join works
- Stale after Codex C1 hardening
- Fix: update docstring

**T-pb27-login-dead-code:** PB-27 — Login company lookup dead code path
- Login endpoint may have stale company lookup code
- Fix: remove dead code path

#### P1 — API Correctness

**T-pb9-pagination:** PB-9 — page > total_pages allowed
- Clamp: `page = max(1, min(page, max(1, total_pages)))`
- Add 1 test

**T-pb6-sort-literal:** PB-6 — `sort_dir` accepts any string
- Change to `Literal["asc", "desc"]`
- Add 1 test

**T-pb7-classification-sort:** PB-7 — classification sort is alphabetical, not severity-ranked
- Add severity rank mapping

#### P2 — Cleanup

**T-pb16-unused-import:** PB-16 — Unused `Field` import
**T-pb17-base64-import:** PB-17 — `base64` imported inside method
**T-pb18-derive-slug-dup:** PB-18 — `_derive_slug` duplicated across routers (now use `core.auth.utils.domain.derive_slug`)
**T-pb35-stale-grace-mode:** PB-35 — Stale grace-mode docstrings

### Tests Added
~5-7 new tests. Total would reach ~1173-1175.

---

## Option B — SQLAlchemy Phase 2B: Service Layer Migration

**Goal:** Migrate file-backed data services (GapData, ContentData, BrandData) to use DB repositories. This is the next step toward full DB-backed data access.

**Effort estimate:** Medium (1-2 sessions).

### Scope

- `GapDataService` → reads gap analysis artifacts from DB repos instead of filesystem
- `ContentDataService` → reads content artifacts from DB repos
- `BrandDataService` → reads research artifacts from DB repos
- `KnowledgeDocService` → metadata in DB instead of `_metadata.json` sidecar
- File-backed mtime caching (`_CACHE`) replaced by DB queries
- **Backward compat:** Filesystem reads as fallback when DB has no data
- **Tests:** Existing 61 gap data + 85 content data + 57 brand data tests must pass

### Risk
- Needs pipeline runners to WRITE to DB (not just read) — may need Phase 3 coordination
- Transaction boundaries for bulk writes during pipeline execution

### Tests Added
~30-40 new tests. Total would reach ~1198-1208.

---

## Option C — SQLAlchemy Phase 2C: TaskStore Migration

**Goal:** Migrate JSON-file-backed TaskStore to PostgreSQL. Enables horizontal scaling and persistent task history.

**Effort estimate:** Small-Medium (1 session).

### Scope
- `PipelineRunRepo` replaces `artifacts/_jobs/*.json` persistence
- Task creation, status updates, approval records → DB
- SSE event bus remains in-memory (acceptable for single-server)
- Slug locks move to DB advisory locks
- **Backward compat:** JSON fallback for tests without `TEST_DATABASE_URL`
- **Tests:** Existing task/runner tests must pass

### Risk
- Advisory lock semantics differ from in-memory locks
- Need to handle JSON → DB migration for existing task data

### Tests Added
~15-20 new tests. Total would reach ~1183-1188.

---

## Option D — Hybrid: Cleanup (Option A) + TaskStore (Option C)

**Goal:** Quick cleanup sprint to resolve security/correctness backlog items, then migrate TaskStore to DB.

**Recommended sequencing:**
1. PB-34 `/me` auth fix (security, 15 min)
2. PB-26, PB-27 cleanup (10 min)
3. PB-18 `_derive_slug` dedup — now use `core.auth.utils.domain.derive_slug` (10 min)
4. PB-9, PB-6, PB-7 API correctness (30 min)
5. TaskStore DB migration (Phase 2C)

---

## Recommendation

**Option D (Hybrid)** — Fix PB-34 (security) and the quick cleanup items first (leveraging the new `core.auth.utils.domain.derive_slug` to eliminate duplication), then tackle TaskStore migration. The `/me` auth bypass is a real security gap that should be closed before any external usage. TaskStore migration is the most self-contained DB migration step (no dependencies on Phase 2B or Phase 3).

Phase 2B (services) requires pipeline writers to store data in DB, which is a larger coordination effort better suited for a dedicated sprint. Phase 3 (route wiring) comes after Phase 2B+2C are stable.

---

## Constraints (Unchanged)

- Backward compatibility with existing artifacts
- All Pydantic fields must have defaults
- Raw SDK clients for LLM calls (no LangChain wrappers)
- LangGraph >=1.0 interrupt model: check `__interrupt__` in result dict
- No Supabase — own PostgreSQL database
- `email-validator` required for auth models (`EmailStr`)
- Password `min_length=8`, `max_length=128`
- Double-underscore separator for effective slugs: `{company}__{product}`
- DB layer is opt-in via `DATABASE_URL` — no engine creation at import time
- Repos flush only, DI session generator owns commit/rollback
- Native `PgUUID(as_uuid=True)` for PKs — repo layer handles str↔uuid conversion
- **NEW:** `AuthServiceProtocol` is the contract — all routers use `get_auth_service` dependency
- **NEW:** Middleware uses `verify_token` utility + `app.state.secret_key` (no AuthStore dependency)

---

## Pre-Sprint Checklist

Before starting work:
- [ ] Aryan approves sprint direction (A, B, C, or D)
- [ ] Read `_memory/` files (progress, failures, decisions, context)
- [ ] Run `pytest tests/ -v` — confirm 1168 collected (1080 passed + 88 skipped)
- [ ] Verify `core/auth/` and `core/db/` files are committed on feat/front-back
