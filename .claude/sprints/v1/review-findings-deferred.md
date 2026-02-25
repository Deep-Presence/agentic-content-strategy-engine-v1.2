# Deferred Review Findings — Phase 1 + Phase 2

> **Source:** Comprehensive code review of feat/front-back branch (Phase 1 Auth + Phase 2 Gap Data)
> **Date:** 2026-02-25
> **Status:** Deferred — fix before production

---

## CRITICAL (Deferred — Fix Before Production)

### C5. `update_company` allows overwriting `id`, `created_at`, `slug` via `**kwargs`

**File:** `api/auth/store.py:183`

No allowlist on `setattr` — caller can corrupt internal state. Needs an allowlist of mutable fields (`name`, `domain`, `additional_domains`, `products`).

### C6. Module-level `_CACHE` has non-atomic read-modify-write race

**File:** `api/services/gap_data_service.py:45-72`

FastAPI runs sync endpoints in a thread pool. The compound operation (check length, delete oldest, insert) is not atomic under concurrent load. Add `threading.Lock` around cache mutations, or switch to `cachetools.TTLCache`.

### C7. `_PATTERN_FLAGS` includes `has_comparison_table` which doesn't exist on `GapContentBrief`

**File:** `api/services/gap_data_service.py:190`

Real `GapContentBrief` has `has_tables` not `has_comparison_table`. That flag only exists on `StructuralSignals`. Test fixtures mask this mismatch. Remove `("has_comparison_table", "Tables")` from `_PATTERN_FLAGS` and update test fixtures to use `has_tables: 0.9`.

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

### CX-1. CRITICAL — Symlink path traversal bypass in content stage reader

**File:** `api/services/content_data_service.py:408-411`
**Reproduced:** Yes — symlinked `brief-1 → ../webflow-escape/brief-1` passes `startswith` check.
**Fix:** Replace `str(resolved).startswith(str(content_root.resolve()))` with `resolved.is_relative_to(content_root.resolve())`. Also reject symlinks on brief_dir.

### CX-2. HIGH — Corrupted JSON returns empty 200 instead of error (DESIGN DECISION)

**File:** `gap_data_service.py:68-72`, `content_data_service.py:49-53`
**Status:** INTENTIONAL — we want graceful degradation when artifacts are in-flight. Logging is sufficient.
**Disposition:** REJECT — keep current behavior (log warning, return defaults).

### CX-3. MEDIUM — Sort by string field crashes with mixed str/int types

**File:** `api/services/gap_data_service.py:761`
**Reproduced:** `sort_by=query_text` with missing `query_text` → `getattr(...) or 0` returns `0` (int) for blank string, but `"abc"` (str) for populated — `TypeError: '<' not supported`.
**Fix:** Type-aware sort key: `str(getattr(r, sort_by, ""))` for string fields, `float(getattr(r, sort_by, 0) or 0)` for numeric.

### CX-4. MEDIUM — `_compute_citability_score` crashes on `overall_score: null`

**File:** `api/services/content_data_service.py:205-206`
**Reproduced:** `{'cycles': [{'overall_score': None}]}` → `None * 100` → `TypeError`.
**Fix:** Filter `None` values: `scores = [c.get("overall_score") for c in cycles]; valid = [s for s in scores if isinstance(s, (int, float))]`.

### CX-5. MEDIUM — Platform similarity assumes numeric, crashes on string values

**File:** `api/services/gap_data_service.py:883-886`
**Reproduced:** `best_paragraphs: [{"similarity": "0.9"}]` → `sum(sims)` mixes int + str → `TypeError`.
**Fix:** Add `isinstance(sim, (int, float))` guard before `ed["sims"].append(sim)`.

### CX-6. MEDIUM — NaN in enriched citations → 500 on JSON serialization

**File:** `api/services/gap_data_service.py:278-287, 317-324`
**Reproduced:** `structural_signals: {"word_count": NaN}` → propagates through averages → `json.dumps(NaN)` → `ValueError`.
**Fix:** Add `safe_float()` helper: `return val if isinstance(val, (int, float)) and math.isfinite(val) else 0.0`.

### CX-7. MEDIUM — `/embeddings` unhandled `ValidationError` on malformed points

**File:** `api/services/gap_data_service.py:1013`
**Reproduced:** `{"x": "abc"}` in projection JSON → `EmbeddingPoint(**p)` → unhandled `ValidationError`.
**Fix:** Wrap in `try/except ValidationError` → HTTPException(422, "Malformed embedding projection data").

### CX-8. MEDIUM — JSON stage fallback returns raw string with `application/json` content_type

**File:** `api/services/content_data_service.py:421-427`
**Status:** Low risk — only happens with corrupted `outline.json` or `eval_history.json`.
**Fix:** Return 422 on parse failure instead of falling back to raw string.

### CX-9. LOW — TOCTOU race between `is_file()` and `stat()` in cache loaders

**File:** `gap_data_service.py:58-62`, `content_data_service.py:39-43`
**Fix:** Wrap `stat()` + `read_text()` in single `try/except (FileNotFoundError, OSError)`.

### CX-10. LOW — Test coverage gaps for negative paths

**File:** Multiple test files
**Fix:** Add tests for: symlink traversal, mixed-type sort keys, null/NaN numeric payloads, malformed projection points.
