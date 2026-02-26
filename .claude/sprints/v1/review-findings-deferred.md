# Deferred Review Findings — Phase 1 + Phase 2

> **Source:** Comprehensive code review of feat/front-back branch (Phase 1 Auth + Phase 2 Gap Data)
> **Date:** 2026-02-25
> **Status:** Partially resolved — see individual items below for resolution status

---

## CRITICAL (Deferred — Fix Before Production)

### C5. `update_company` allows overwriting `id`, `created_at`, `slug` via `**kwargs`

**File:** `api/auth/store.py:183`

No allowlist on `setattr` — caller can corrupt internal state. Needs an allowlist of mutable fields (`name`, `domain`, `additional_domains`, `products`).

### C6. Module-level `_CACHE` has non-atomic read-modify-write race ✅ RESOLVED 2026-02-26

**File:** `api/services/gap_data_service.py:45-72`
**Resolution:** Added `import threading` + `_CACHE_LOCK = threading.Lock()` to both `gap_data_service.py` and `content_data_service.py`. Wrapped compound check-evict-insert in `with _CACHE_LOCK:` in both caches. Task: T-cx-9-c7-c6-cx10.

### C7. `_PATTERN_FLAGS` includes `has_comparison_table` which doesn't exist on `GapContentBrief` ✅ RESOLVED 2026-02-26

**File:** `api/services/gap_data_service.py:190`
**Resolution:** Removed `("has_comparison_table", "Tables")` from `_PATTERN_FLAGS`. Updated test fixture `_make_gap` to use `has_tables: 0.9`. Added 2 regression tests in `TestC7HasComparisonTableRemoved`. Task: T-cx-9-c7-c6-cx10.

---

## WARNING (Fix Before Production)

### W1. `_secret_key` regenerated on restart if `JWT_SECRET_KEY` not set

**File:** `api/auth/store.py:109`
**Fix:** Document requirement or add stable dev default.

### W2. Token expiry test race condition

**File:** `api/auth/store.py:336`
**Fix:** Use `expires_hours=-1` in tests, or change comparison to `>=`.

### W3. `BaseHTTPMiddleware` may break SSE streaming

**File:** `api/app.py:54`
**Fix:** Exclude `/events` path from logging middleware, or use pure ASGI middleware.

### W4. `sort_dir` accepts any string value

**File:** `api/routers/gap_data.py:54`
**Fix:** Use `Literal["asc", "desc"]` type annotation.

### W5. Classification sort is alphabetical, not by severity

**File:** `api/services/gap_data_service.py:753`
**Fix:** Add severity-rank mapping: `significant_gap=4, gap_to_close=3, roughly_equal=2, company_wins=1`.

### W6. `company_avg` always 0.0 in signal averages

**File:** `api/services/gap_data_service.py:285`
**Fix:** Requires s1 pipeline enhancement to crawl company pages for structural signals. Deferred.

### W7. Pagination allows `page > total_pages`

**File:** `api/services/gap_data_service.py:756`
**Fix:** Clamp `page = min(page, total_pages)` or return 400 for out-of-range.

### W8. No rate limiting on `/register`

**File:** `api/routers/auth.py`
**Fix:** Add simple rate limiter (slowapi or custom) before real usage.

### W9. Enriched citations ~20MB cached x 10 = 200MB memory risk

**File:** `api/services/gap_data_service.py:131`
**Fix:** Monitor, reduce `_CACHE_MAX_ENTRIES`, or add size-based eviction.

---

## INFO (Nice to Have)

### I1. Unused `Field` import in `api/auth/models.py:11`

### I2. `base64` imported inside method, not at module level in `api/auth/store.py:343`

### I3. `_derive_slug` duplicated across `api/auth/store.py:96` and `api/routers/content.py:26`

Extract to shared utility.

### I4. No test for `normalize_domain` with port numbers (`ramp.com:8080`)

### I5. No test for slug collision in registration (two companies same name, different domains)

### I6. Missing tests for gap data edge cases:
- Page beyond total_pages
- Unknown `sort_by` field fallback
- Case-insensitive search verification
- Sort by string fields (classification, query_text)

### I7. Cache eviction is FIFO not LRU in `api/services/gap_data_service.py:67`

### I8. `gap_data_service` raises `HTTPException` directly from service layer — couples to FastAPI

---

## Codex gpt-5.3 Review — 2026-02-26

> **Source:** `codex exec --model gpt-5.3-codex` review of Phase 2+3 service/router/schema/core files
> **Session:** 019c960a-cd1b-7963-b853-efc8645d5729
> **Resolved in this session:** C1 (gap_data try/except), H1 (Literal method), H3 (NaN filter)

### CX-1. CRITICAL — Symlink path traversal bypass in content stage reader ✅ RESOLVED 2026-02-26

**File:** `api/services/content_data_service.py:408-411`
**Resolution:** Uses `resolved.is_relative_to(content_root.resolve())` + symlink check. Confirmed already fixed in code via T-cx-batch-1-8 audit.

### CX-2. HIGH — Corrupted JSON returns empty 200 instead of error (DESIGN DECISION)

**File:** `gap_data_service.py:68-72`, `content_data_service.py:49-53`
**Status:** INTENTIONAL — we want graceful degradation when artifacts are in-flight. Logging is sufficient.
**Disposition:** REJECT — keep current behavior (log warning, return defaults).

### CX-3. MEDIUM — Sort by string field crashes with mixed str/int types ✅ RESOLVED 2026-02-26

**File:** `api/services/gap_data_service.py:761`
**Resolution:** Type-aware sort with `_STRING_SORT_FIELDS` / `_NUMERIC_SORT_FIELDS` sets. Confirmed already fixed via T-cx-batch-1-8 audit.

### CX-4. MEDIUM — `_compute_citability_score` crashes on `overall_score: null` ✅ RESOLVED 2026-02-26

**File:** `api/services/content_data_service.py:205-206`
**Resolution:** `walrus + isinstance` filter for None values. Confirmed already fixed via T-cx-batch-1-8 audit.

### CX-5. MEDIUM — Platform similarity assumes numeric, crashes on string values ✅ RESOLVED 2026-02-26

**File:** `api/services/gap_data_service.py:883-886`
**Resolution:** `isinstance(sim, (int, float))` guard in `get_platforms`. Confirmed already fixed via T-cx-batch-1-8 audit.

### CX-6. MEDIUM — NaN in enriched citations → 500 on JSON serialization ✅ RESOLVED 2026-02-26

**File:** `api/services/gap_data_service.py:278-287, 317-324`
**Resolution:** `_safe_float()` helper using `math.isfinite`. Confirmed already fixed via T-cx-batch-1-8 audit.

### CX-7. MEDIUM — `/embeddings` unhandled `ValidationError` on malformed points ✅ RESOLVED 2026-02-26

**File:** `api/services/gap_data_service.py:1013`
**Resolution:** `try/except ValidationError` → HTTPException(422). Confirmed already fixed via T-cx-batch-1-8 audit.

### CX-8. MEDIUM — JSON stage fallback returns raw string with `application/json` content_type ✅ RESOLVED 2026-02-26

**File:** `api/services/content_data_service.py:421-427`
**Resolution:** `JSONDecodeError` → HTTPException(422). Confirmed already fixed via T-cx-batch-1-8 audit.

### CX-9. LOW — TOCTOU race between `is_file()` and `stat()` in cache loaders ✅ RESOLVED 2026-02-26

**File:** `gap_data_service.py:58-62`, `content_data_service.py:39-43`
**Resolution:** Replaced `is_file()` + unguarded `stat()` with `try/except (FileNotFoundError, OSError)` around stat(). Task: T-cx-9-c7-c6-cx10.

### CX-10. LOW — Test coverage gaps for negative paths ✅ RESOLVED 2026-02-26

**File:** Multiple test files
**Resolution:** All negative-path tests already existed (TestCX1–8 classes). Added 2 C7 regression tests. Task: T-cx-9-c7-c6-cx10.

---

## Summary of Resolution Status (as of 2026-02-26)

| Finding | Severity | Status |
|---------|----------|--------|
| C5 — update_company allowlist | CRITICAL | ⏳ Still deferred |
| C6 — _CACHE thread safety | CRITICAL | ✅ Fixed (T-cx-9-c7-c6-cx10) |
| C7 — _PATTERN_FLAGS mismatch | CRITICAL | ✅ Fixed (T-cx-9-c7-c6-cx10) |
| W1–W9 | WARNING | ⏳ Still deferred |
| I1–I8 | INFO | ⏳ Still deferred |
| CX-1–CX-10 | CRITICAL–LOW | ✅ All fixed (T-cx-batch-1-8, T-cx-9-c7-c6-cx10) |
