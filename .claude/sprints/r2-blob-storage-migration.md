# Cloudflare R2 Blob Storage Migration Spec

## Deep Presence Backend — March 2026

---

## 1. Corrected Understanding of Current Directory Layout

```
artifacts/
├── knowledge_base/{slug}/              ← INTERMEDIATE pipeline files (research outputs)
│   ├── _manifest.json
│   ├── company_overview/v1.md, v1.json
│   ├── customer_reviews/
│   ├── competitor_registry/
│   ├── brand_perception/
│   ├── synthesis/
│   └── weakness_analysis/
│
├── company_context/{slug}.md           ← FINAL KB artifact (synthesized profile)
│
├── voice_style_guide/{slug}/           ← INTERMEDIATE VSG pipeline files
│   ├── _manifest.json
│   ├── discovery/
│   ├── guide/
│   └── {influencer_slug}/
│
├── style_guides/{slug}.md              ← FINAL VSG artifact (approved style guide)
│
├── audience_personas/{slug}/           ← Persona pipeline (intermediate + final in same dir)
│   ├── _manifest.json
│   └── {persona_name}/
│
├── gap_analysis/{slug}/                ← Gap Analysis (write-once-read-many)
│   ├── queries.json
│   ├── analysis.json
│   ├── gap_report.json / gap_report.md
│   ├── generation_spec.json / generation_spec.md
│   ├── enriched_citations.json         ← Can be ~20MB
│   ├── company_embeddings.json
│   ├── company_page_analysis.json
│   ├── embeddings/
│   ├── platform_results/
│   ├── site_discovery/
│   └── visualizations/
│
├── topic_discovery/{slug}/             ← Topic Discovery
│   ├── _manifest.json
│   ├── raw/
│   ├── taxonomy/
│   ├── scoring/
│   ├── matrix/
│   └── persona_affinity/
│
├── content/{slug}/                     ← Content Engine v1.3
│   ├── pipeline_state.json             ← Ephemeral in-flight status (→ Redis, NOT R2)
│   ├── blueprints.json                 ← Brief registry
│   ├── run_metadata_v13.json           ← Run-level metadata
│   ├── run_metadata_v13_{brief_id}.json
│   └── content/{brief_id}/
│       ├── outline.json
│       ├── draft.md
│       ├── eval_history.json
│       └── final.md
│
├── site_audit/{slug}/                  ← Site Audit
│   └── {run_id}/
│       ├── audit_result.json
│       └── report.md
│
├── _jobs/{task_id}.json                ← TaskStore (NOT blob storage — goes to Redis)
├── _auth/                              ← Auth (NOT blob storage — already in PostgreSQL)
└── _logs/                              ← NOT blob storage
```

**Key insight: the intermediate/final split between `knowledge_base/` → `company_context/` and `voice_style_guide/` → `style_guides/` is intentional pipeline design. Preserve it.**

---

## 2. What Does NOT Go to R2 (Ephemeral / Coordination State)

| Item | Current Location | Correct Target | Reason |
|------|-----------------|----------------|--------|
| `pipeline_state.json` | `content/{slug}/` | Redis HSET | Ephemeral, sub-second writes |
| `_jobs/{task_id}.json` | `_jobs/` | Redis + PostgreSQL | TaskStore coordination state |
| `_auth/` | `_auth/` | PostgreSQL (already migrated) | — |
| `_manifest.json` files | Various | PostgreSQL (future) | Version index, queryable metadata |
| `chroma_db/` | Root | DELETE (pgvector replaced it) | — |
| `.zip` files | Various | DELETE (export artifacts) | — |

R2 only gets **durable content artifacts** — stuff written once and read many times.

---

## 3. Keep the Current Key Patterns (Don't Restructure)

**Don't flip to company-first.** Keep the existing pipeline-first key patterns.

1. **The StorageBackend abstraction means keys are just strings.** Whether the key is `knowledge_base/webflow/company_overview/v1.md` (pipeline-first) or `webflow/research/knowledge-base/company_overview/v1.md` (company-first) is irrelevant to R2 — it's a flat key-value store.

2. **Every storage class would need key generation changes.** `KBStorage`, `PersonaStorage`, `VoiceStyleGuideStorage`, `TopicDiscoveryStorage` all build keys relative to a base path. Restructuring means updating every key path in 5 storage classes.

3. **~116 bypass points also hardcode paths.** All those direct `Path(artifact_dir) / ...` calls would need updating too. Double the refactoring for zero functional gain.

4. **The benefit is marginal right now.** With 0 clients in production, "delete all company data" is not an operation you need today.

5. **You can always rename keys later.** R2 supports copy+delete. A one-time migration script can restructure when you actually need it.

**The only change**: strip the `artifacts/` prefix. `artifacts/knowledge_base/webflow/...` becomes `knowledge_base/webflow/...` in R2.

---

## 4. Exhaustive Filesystem Bypass Audit (~116 bypasses)

### 4A. WRITES through StorageBackend (already abstracted — swap "just works")

These start writing to R2 with zero code changes when `R2StorageBackend` is added:

| Storage Class | File | What It Writes |
|--------------|------|----------------|
| `KBStorage` | `core/research/knowledge_base/storage.py` | All KB docs: `knowledge_base/{slug}/{doc_type}/v{n}.md`, `_manifest.json` |
| `PersonaStorage` | `core/research/audience_persona/storage.py` | Persona docs: `audience_personas/{slug}/{persona}/` |
| `VoiceStyleGuideStorage` | `core/research/voice_style_guide/storage.py` | VSG docs: `voice_style_guide/{slug}/discovery/`, `guide/` |
| `TopicDiscoveryStorage` | `core/topic_discovery/storage.py` | TD outputs: `topic_discovery/{slug}/raw/`, `taxonomy/`, `scoring/` |
| `persist_stage_artifact()` | `core/content_engine/artifact_writer.py` | Per-brief stage files: `content/{slug}/content/{brief_id}/outline.json`, `draft.md`, `final.md` |

### 4B. Gap Analysis — 49 bypasses (WORST offender, ZERO StorageBackend usage)

The entire gap analysis pipeline predates StorageBackend. No file in `core/gap_analysis/` uses the abstraction.

#### `pipeline.py` — 19 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 187 | WRITE | `mkdir()` artifact dir |
| 334-337 | WRITE | `queries.json` |
| 499-501 | WRITE | `analysis.json` |
| 532-534 | WRITE | `visualization_paths.json` |
| 631, 690-693, 741-744, 766-774 | WRITE | topic-scoped: dir, `queries.json`, `analysis.json`, `topic_metrics.json` |
| 214-216, 331, 363-369, 468-478, 489, 523-527, 556-564, 649-673 | READ | skip-resume reads of all step outputs |

#### `s1_embed_assets.py` — 7 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 109 | WRITE | `mkdir()` |
| 1251-1258 | WRITE | `discovered_pages.json` |
| 1261-1268 | WRITE | `site_tree.json` |
| 1282-1285 | WRITE | `discovery_summary.json` |
| 1326-1333 | WRITE | `company_page_analysis.json` |
| 1154, 1159, 1172 | READ | `_metadata.json`, knowledge docs |

#### `s3_search_platforms.py` — 2 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 424 | WRITE | `mkdir()` platform_results dir |
| 431 | WRITE | `{engine}_results.jsonl` via `open("w")` |

#### `s4_enrich_citations.py` — 2 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 590 | WRITE | `mkdir()` |
| 592 | WRITE | `enriched_citations.json` |

#### `s5_embed_content.py` — 3 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 358 | WRITE | `mkdir()` |
| 361 | WRITE | `queries_with_embeddings.json` |
| 366 | WRITE | `citations_with_embeddings.json` |

#### `s7_visualize.py` — 12+ bypasses

| Line(s) | Op | Artifact | Note |
|---------|-----|---------|------|
| 33 | WRITE | `mkdir()` helper | |
| 222-674 | WRITE | 10× `fig.write_html()` | Plotly visualizations — **binary HTML, needs `write_bytes()` on ABC** |
| 674 | WRITE | `embedding_projections_{method}.json` | |

#### `s8_generate_report.py` — 6 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 452 | WRITE | `mkdir()` |
| 454 | WRITE | `gap_report.md` |
| 455-457 | WRITE | `gap_report.json` |
| 459-461 | WRITE | `generation_spec.md` |
| 462-464 | WRITE | `generation_spec.json` |
| 477-479 | WRITE | `gap_analysis_complete.json` |

#### Service/Router reads — 3 bypasses

| File | Line(s) | Op | Artifact |
|------|---------|-----|---------|
| `gap_data_service.py` | 75 | READ | gap JSON artifacts (mtime-cached) |
| `gap_context_helper.py` | 37, 47 | READ | `analysis.json` (mtime-cached, duplicate cache!) |
| `gap_analysis.py` router | 33 | READ | dual-sentinel `.exists()` check |

### 4C. Content Engine v1.3 — 28 bypasses (partial StorageBackend, v1.0 path excluded as dead code)

**Pre-requisite cleanup: Delete the v1.0 dispatcher path** (lines 113-148 in `workers/dispatcher.py`). This is dead code — 4 bypasses removed for free.

#### `pipeline_v13.py` — 10 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 163 | WRITE | `mkdir()` `artifacts/content/{slug}/` |
| 170 | WRITE | `mkdir()` `content/{brief_id}/` |
| 139, 1181 | READ | `blueprints.json` via `json.loads(bp_path.read_text())` |
| 150 | WRITE | `blueprints.json` via `bp_path.write_text(json.dumps(...))` |
| 558 | WRITE | `run_metadata_v13.json` via `meta_path.write_text(output.model_dump_json())` |
| 764, 808 | WRITE | `planner_selections.json` |
| 892 | READ | `planner_selections.json` |
| 1346 | READ | gap `analysis.json` (cross-pipeline read) |
| 1716, 1868 | WRITE | `final.md` |

#### `state_helpers.py` — 5 bypasses (LEAVE AS-IS → Redis later)

| Line(s) | Op | Artifact | Migration target |
|---------|-----|---------|-----------------|
| 52, 83 | READ | `pipeline_state.json` | Redis HSET |
| 69, 99 | WRITE | `pipeline_state.json` | Redis HSET |
| 102 | DELETE | `pipeline_state.json` via `unlink()` | Redis HDEL |

**Do NOT move these to R2. Leave on local filesystem until Redis branch merges.**

#### `workers/dispatcher.py` — 4 bypasses (v1.3 else-fallback only)

| Line(s) | Op | Artifact | Note |
|---------|-----|---------|------|
| 335, 357, 380, 408 | WRITE | `outline.json`, `draft.md`, `linked.md`, `fact_checked.md` | Only fires when `storage=None`. Fix: ensure storage is always injected. |

#### `content_data_service.py` — 7 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 57 | READ | various JSON metadata |
| 189-206 | READ | 6× `.exists()` checks on stage files (`final.md`, `eval_history.json`, `draft.md`, etc.) |
| 417 | WRITE | `mkdir()` content root |
| 424 | READ | `blueprints.json` |
| 457 | WRITE | `blueprints.json` |
| 623-628 | READ | stage content files |

#### `db_content_data.py` — 2 bypasses (fallback)

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 112 | READ | `pipeline_state.json` (leave for Redis) |
| 253 | READ | `blueprints.json` |

### 4D. Site Audit — ~~24 bypasses~~ **RESOLVED: Migrated to DB-primary (not R2)**

> **Decision (2026-03-24):** Site audit data is fully structured (scores,
> findings, page metrics) with no large text blobs. It runs daily/multiple
> times per day. PostgreSQL is a better fit than blob storage. The module
> was migrated to DB-primary storage in sprint `feat/front-back`.
>
> **What changed:**
> - `runner.py` — DB persistence is now the required write path; filesystem
>   only when `DATABASE_URL` is not set (local dev fallback)
> - `pipeline.py` — s6_report step skips filesystem writes when
>   `output_dir=None` (the default for production runner calls)
> - `site_audit.py` router — guard converted from FS scan to DB query
>   (`audit_exists_for_slug()` via `SiteAuditDataServiceProtocol`)
> - `onboarding/orchestrator.py` — added `persist_site_audit_result()` call
> - `db_site_audit_data.py` — FS fallback methods have deprecation warnings
> - `json_site_audit_data.py` — retained for no-DB local dev only
> - New migration `0021` adds `UNIQUE(audit_id, page_index)` on page results
> - Backfill script: `scripts/backfill_site_audit_db.py`
>
> **All 24 bypasses are eliminated from the R2 migration scope.**
> The remaining FS code in `json_site_audit_data.py` is dev-only fallback
> and will be removed after backfill verification (Phase 4b, deferred).

~~#### `s6_report.py` — 3 bypasses~~

~~| Line(s) | Op | Artifact |~~
~~|---------|-----|---------|~~
~~| 228 | WRITE | `mkdir()` report dir |~~
~~| 233 | WRITE | `report.md` |~~
~~| 239-240 | WRITE | `audit_result.json` |~~

~~#### `runner.py` (site audit section) — 2 bypasses~~

~~| Line(s) | Op | Artifact |~~
~~|---------|-----|---------|~~
~~| 518 | WRITE | `mkdir()` output dir |~~
~~| 519-520 | WRITE | `audit_result.json` |~~

~~#### `site_audit.py` router — 4 bypasses~~

~~| Line(s) | Op | Artifact |~~
~~|---------|-----|---------|~~
~~| 54 | READ | `.exists()` audit dir |~~
~~| 56 | READ | `.iterdir()` subdirs |~~
~~| 60 | READ | `.exists()` `audit_result.json` |~~
~~| 64 | READ | `.read_text()` `audit_result.json` |~~

~~#### `json_site_audit_data.py` — 10 bypasses~~

~~| Line(s) | Op | Artifact |~~
~~|---------|-----|---------|~~
| 71, 217, 364, 380 | READ | `.exists()` checks |
| 81 | READ | `.read_text()` `audit_result.json` |
| 222, 366, 384 | READ | `.iterdir()` directory scans |

**Note**: `.iterdir()` pattern needs translation to `StorageBackend.list_dir()` → R2 `list_objects_v2` with prefix.

### 4E. Audience Persona, VSG & Cross-Pipeline — 15 bypasses

These pipelines use their Storage classes internally, but **callers and cross-pipeline code bypass them**.

#### `runner.py` — `resolve_artifacts()` — 5 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 137 | READ | `company_context/{slug}.md` `.exists()` |
| 145 | READ | `audience_personas/{slug}/_manifest.json` `.exists()` |
| 161 | READ | legacy `personas/` `.exists()` |
| 164 | READ | `.glob("*__persona-*.md")` |
| 174 | READ | `style_guides/{slug}.md` `.exists()` |

#### `brand_data_service.py` — 5 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 107 | READ | `company_context/{slug}.md` `.read_text()` |
| 119 | READ | `company_context/{slug}.draft.md` `.read_text()` |
| 152 | READ | persona `v{N}.md` `.exists()` |
| 155 | READ | persona `.read_text()` |
| 183 | READ | legacy personas `.iterdir()` |

#### `companies.py` — 2 bypasses

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 58-72 | READ | legacy `personas/` `.iterdir()` + glob |
| 92 | READ | `style_guides/` artifact status check |

#### `knowledge_base.py` router — 1 bypass

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 54-57 | READ | `_manifest.json` `.exists()` + `.read_text()` |

#### `audience_persona.py` router — 1 bypass

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 108-110 | READ | KB `_manifest.json` cross-pipeline staleness check |

#### `prompt_library.py` — 1 bypass

| Line(s) | Op | Artifact |
|---------|-----|---------|
| 203, 208 | READ | gap `queries.json` import |

### 4F. Filesystem-Based Caches (need invalidation strategy change)

| Cache | File | What It Caches | Invalidation | Lock? |
|-------|------|---------------|-------------|-------|
| Gap Data Cache | `gap_data_service.py` | `analysis.json`, `enriched_citations.json`, etc. | mtime-based | Yes |
| Gap Context Cache | `gap_context_helper.py` | `analysis.json` (duplicate of above!) | mtime-based | Yes |
| ~~Site Audit Cache~~ | ~~`json_site_audit_data.py`~~ | ~~`audit_result.json`~~ | ~~mtime-based~~ | ~~Yes~~ |
| Brand Data Cache | `brand_data_service.py` | Artifact detection results | mtime-based | **NO lock — race condition** |

> **Site Audit Cache removed (2026-03-24):** Site audit reads from PostgreSQL
> now. The `json_site_audit_data.py` cache is only used in no-DB local dev
> and will be removed after backfill verification.

**Problem**: mtime-based invalidation doesn't work with R2. Switch to TTL-based. Also fix the missing `threading.Lock` on `brand_data_service.py`.

### 4G. Summary by Pipeline

| Pipeline | Total Bypasses | StorageBackend Usage | Verdict |
|----------|---------------|---------------------|---------|
| Gap Analysis | ~49 | Zero | Entirely filesystem-direct |
| Content Engine v1.3 | ~28 | Partial (dispatcher v1.3 has conditional) | Pipeline + services all direct |
| ~~Site Audit~~ | ~~24~~ → **0** | ~~Zero~~ → **DB-primary** | **Migrated to PostgreSQL (2026-03-24). Not R2.** |
| AP / VSG / Cross-Pipeline | ~15 | Internal storage classes used, callers bypass | Cross-pipeline reads all direct |
| **Total** | **~~116~~ → ~92** | — | — |

### 4H. Bypass Pattern Categories

The ~116 bypasses fall into 3 architectural categories:

1. **Pipeline writers** (gap analysis steps, content workers, runner) — construct `Path` objects and call `.write_text()` / `.mkdir()` directly. These are the **producers**. *(Site audit writers removed — migrated to DB-primary.)*

2. **Service layer readers** (content_data_service, gap_data_service, brand_data_service, gap_context_helper) — construct `Path` objects and call `.read_text()` / `.exists()` / `.iterdir()` directly. These are the **consumers**. *(json_site_audit_data removed — site audit reads from DB now.)*

3. **Router/runner discovery** (resolve_artifacts, completion checks in routers) — use `.exists()` and `.glob()` to detect artifact presence. These are the **discovery layer**.

**Writers must be fixed first** — they determine the key format. Readers adapt to whatever keys the writers produce. Discovery (`.exists()` / `.glob()` / `.iterdir()`) is the trickiest because R2 `list_objects_v2` with prefix replaces `.iterdir()`, but `.glob()` patterns need translation.

---

## 5. Migration Roadmap — Complete Filesystem Elimination

### Pre-requisite: Delete Dead Code (0.5 day)

Before starting migration:
1. **Delete v1.0 dispatcher path** in `workers/dispatcher.py` (lines 113-148). Dead code, 4 bypasses removed.
2. **Delete legacy persona paths** in `runner.py` (line 161, 164) and `companies.py` (lines 58-72) if `PersonaStorage` is authoritative. Removes ~4 bypasses.

### Phase 0: R2 Setup + StorageBackend Implementation (1 day)

**Goal**: R2 bucket exists, `R2StorageBackend` implements the ABC, factory wiring in place.

1. Create Cloudflare R2 bucket: `deep-presence-prod`
2. Generate API token (R2 read/write scope)
3. Add env vars to Railway: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `STORAGE_BACKEND=r2`

4. Implement `R2StorageBackend` in `core/storage/backends/r2.py`:
   ```python
   class R2StorageBackend(StorageBackend):
       # Implements: read(), write(), exists(), delete(), list_dir()
       # Uses aiobotocore for async S3-compatible operations
       # IMPORTANT: Add binary read/write support (current ABC is text-only)
   ```

5. Update `StorageBackend` ABC to support binary:
   ```python
   # Add to base.py:
   def read_bytes(self, path: str) -> Optional[bytes]: ...
   def write_bytes(self, path: str, content: bytes) -> str: ...
   ```

6. Update factory in `get_storage_backend()`:
   ```python
   if settings.STORAGE_BACKEND == "r2":
       return R2StorageBackend(...)
   return LocalStorageBackend(...)
   ```

7. Keep `STORAGE_BACKEND=local` default for local dev.

**At this point**: All pipeline WRITES via StorageBackend (Section 4A) automatically go to R2 in production. Zero pipeline code changes.

### Phase 1: Gap Analysis Retrofit (3-4 days)

**Goal**: Retrofit the entire gap analysis pipeline to use StorageBackend. This is the biggest phase — 49 bypasses across 7 step files + 3 service/router files, with zero existing abstraction.

**Files to change (writers — fix first):**
- `core/gap_analysis/pipeline.py` — 19 bypasses. Replace all `Path().write_text()` and `mkdir()` with `StorageBackend.write()`. Replace skip-resume `Path().read_text()` reads.
- `core/gap_analysis/s1_embed_assets.py` — 7 bypasses. Same pattern. Also fix the knowledge doc reads (lines 1154, 1159, 1172).
- `core/gap_analysis/s3_search_platforms.py` — 2 bypasses. `open("w")` → `StorageBackend.write()`.
- `core/gap_analysis/s4_enrich_citations.py` — 2 bypasses.
- `core/gap_analysis/s5_embed_content.py` — 3 bypasses.
- `core/gap_analysis/s7_visualize.py` — 12+ bypasses. **Special case**: Plotly `fig.write_html()` produces binary HTML. Must use `write_bytes()` or serialize to string first via `fig.to_html()`.
- `core/gap_analysis/s8_generate_report.py` — 6 bypasses.

**Files to change (readers):**
- `api/services/gap_data_service.py` — Replace mtime-cached filesystem reads with `StorageBackend.read()` + TTL cache.
- `core/services/gap_context_helper.py` — Same. Also: consider eliminating this duplicate cache of `analysis.json`.
- `api/routers/gap_analysis.py` — Replace `.exists()` sentinel check with `StorageBackend.exists()`.

**Pattern for all step files:**
```python
# BEFORE (repeated ~49 times across gap analysis)
output_dir = Path(artifact_dir) / "gap_analysis" / slug
output_dir.mkdir(parents=True, exist_ok=True)
(output_dir / "queries.json").write_text(json.dumps(data, indent=2))

# AFTER
key = f"gap_analysis/{slug}/queries.json"
storage.write(key, json.dumps(data, indent=2))
```

**Note**: `mkdir()` calls become no-ops with R2 (flat key-value store, no directories). Either delete them or make `StorageBackend.mkdir()` a no-op in R2 implementation.

### Phase 2: Content Engine v1.3 (2-3 days)

**Goal**: Fix 28 bypasses (after v1.0 dead code deletion). Leave `pipeline_state.json` (5 bypasses in `state_helpers.py`) untouched for Redis.

**Actionable bypasses: ~23** (28 total minus 5 `pipeline_state.json` left for Redis)

**Files to change (writers):**
- `core/content_engine/pipeline_v13.py` — 10 bypasses. Replace `_load_artifact_text()`, `_load_artifact_json()` to use `StorageBackend`. Replace `blueprints.json`, `run_metadata_v13.json`, `planner_selections.json` writes. Replace `final.md` writes (lines 1716, 1868). Replace cross-pipeline gap `analysis.json` read (line 1346).
- `workers/dispatcher.py` — 4 bypasses (v1.3 else-fallback). **Fix**: ensure `storage` is always injected so the fallback path never fires. Then delete the fallback.

**Files to change (readers):**
- `api/services/content_data_service.py` — 7 bypasses. Replace 6× `.exists()` stage file checks, `blueprints.json` read/write, stage content reads.
- `core/services/db_content_data.py` — 1 actionable bypass (`blueprints.json` read at line 253). The `pipeline_state.json` read at line 112 stays for Redis.

### ~~Phase 3: Site Audit (1-2 days)~~ — COMPLETE (DB-primary, not R2)

> **Resolved 2026-03-24.** Site audit was migrated to DB-primary storage
> instead of R2 blob storage. All 24 bypasses eliminated. See Section 4D
> for details. This phase is **removed from the R2 migration scope**.

### Phase 4: AP/VSG Cross-Pipeline Callers (1 day)

**Goal**: Fix 15 bypasses in code that reads research artifacts from *outside* the storage classes.

**Files to change:**
- `api/tasks/runner.py` — `resolve_artifacts()` — 5 bypasses (3 after legacy deletion). Replace `.exists()` and `.glob()` with `StorageBackend.exists()` and `StorageBackend.list_dir()`.
- `api/services/brand_data_service.py` — 5 bypasses. Replace all `.read_text()`, `.exists()`, `.iterdir()` with StorageBackend calls.
- `api/routers/companies.py` — 2 bypasses (0 after legacy deletion). Replace legacy persona `.iterdir()` + glob.
- `api/routers/knowledge_base.py` — 1 bypass. `_manifest.json` read.
- `api/routers/audience_persona.py` — 1 bypass. Cross-pipeline KB `_manifest.json` staleness check.
- `core/content_engine/prompt_library.py` — 1 bypass. Gap `queries.json` import.

### Phase 5: Cache Invalidation (1 day)

**Goal**: Replace mtime-based caching with TTL-based. Fix missing lock.

**Problem**: Current caches check `os.stat(path).st_mtime_ns` to invalidate. R2 doesn't have local mtime.

**Solution**: TTL-based caching. Gap analysis, site audit, and KB data are write-once-read-many — they don't change after pipeline completion. A 5-minute TTL is sufficient.

```python
# BEFORE
if cached_mtime < os.stat(path).st_mtime_ns:
    reload()

# AFTER
if time.monotonic() - cached_at > TTL_SECONDS:
    reload()
```

**Files to change:**
- `gap_data_service.py` — 4 cache instances
- `gap_context_helper.py` — 1 cache instance (consider merging with gap_data_service cache to eliminate duplication)
- `json_site_audit_data.py` — 1 cache instance
- `brand_data_service.py` — 1 cache instance + **add missing `threading.Lock`** (currently the only cache without thread safety)

### Phase 6: Binary Upload Path + Asset Loader (0.5 day)

**Goal**: Fix remaining edge cases.

- `knowledge_doc_service.py` — `upload_document()` writes raw bytes directly. Use new `write_bytes()` from Phase 0.
- `core/content_engine/s1_embed_assets.py` — `_load_knowledge_doc_units()` reads knowledge docs via direct Path. Use `StorageBackend.read()`.

### Phase 7: DB Service Fallback Removal (0.5 day)

**Goal**: Remove "falling back to filesystem" codepaths in DB services.

- `core/services/db_content_data.py` — Remove filesystem fallback in `get_brief_stage_content()`
- `core/services/db_kb_data.py` — Remove "Delegate to filesystem" in `get_health()`
- `core/services/db_persona_data.py` — Remove filesystem content reads

**Pattern**: DB metadata is authoritative. Content reads go through `StorageBackend` (R2 in prod). No filesystem fallback needed.

### Phase 8: Cleanup (0.5 day)

1. Remove `artifacts/` from `.gitignore` (no longer a runtime directory in production)
2. Update `CLAUDE.md` and `.claude/skills/` to reflect R2 storage
3. Add `STORAGE_BACKEND=local` to `.env.example` for dev setup
4. Update onboarding docs
5. Verify `LocalStorageBackend` still works for local dev

---

## 6. Total Effort Estimate

| Phase | Bypasses Fixed | Effort | Dependencies |
|-------|---------------|--------|-------------|
| Pre-req: Dead code deletion | ~8 removed | 0.5 day | None |
| Phase 0: R2 + Backend | 0 (infra) | 1 day | Cloudflare account |
| Phase 1: Gap Analysis retrofit | ~49 | 3-4 days | Phase 0 |
| Phase 2: Content Engine v1.3 | ~23 | 2-3 days | Phase 0 |
| ~~Phase 3: Site Audit~~ | ~~24~~ → **0** | **Done** | **DB-primary (2026-03-24)** |
| Phase 4: AP/VSG cross-pipeline | ~15 | 1 day | Phase 0 |
| Phase 5: Cache invalidation | 3 caches | 1 day | Phases 1-2, 4 |
| Phase 6: Binary + asset loader | ~2 | 0.5 day | Phase 0 |
| Phase 7: DB fallback removal | ~3 | 0.5 day | Phases 1-2, 4 |
| Phase 8: Cleanup | 0 | 0.5 day | All above |
| **Total** | **~92** | **~9-11 days** | |

### Parallelization

Phases 1, 2, and 4 touch completely different files and can be parallelized:
- **Person A**: Phase 1 (Gap Analysis) = 3-4 days
- **Person B**: Phase 2 (Content Engine) + Phase 4 (AP/VSG) = 3-4 days

With two people, critical path is **~5-6 days** including Phase 0 and cleanup.

> **Note:** Site Audit (former Phase 3) is no longer part of this migration.
> It was migrated to PostgreSQL DB-primary storage on 2026-03-24 — structured
> data with no large blobs, running daily, better served by SQL than blob storage.

### Deploy Strategy

**Phase 0 should be deployed immediately** after implementation. Since all pipeline writes via StorageBackend (Section 4A) already work, swapping the backend means new pipeline runs start writing to R2 right away. The read-side migration (Phases 1-7) happens incrementally while production runs.

---

## 7. Key Architectural Decision: Hydration Pattern for Pipeline Execution

When the content engine runs, it reads company context, personas, and style guide potentially dozens of times across parallel workers. You don't want each worker hitting R2 independently for the same files.

**Solution: Pre-fetch at pipeline start.**

```python
async def hydrate_artifacts_for_pipeline(
    company_slug: str,
    storage: StorageBackend,
    work_dir: Path
) -> dict[str, Path]:
    """Pre-fetch all artifacts from R2 to local temp dir at pipeline start."""
    paths = {}
    for key_pattern in REQUIRED_ARTIFACTS:
        key = key_pattern.format(slug=company_slug)
        content = storage.read(key)
        if content:
            local_path = work_dir / Path(key).name
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(content)
            paths[key] = local_path
    return paths
```

This means pipeline workers continue reading from local file paths (zero refactoring of agent prompts), but the files come from R2 instead of a persistent filesystem. The temp directory is cleaned up after the run.

This is especially important for Railway, where the filesystem is ephemeral anyway — container restarts lose everything on disk.

---

## 8. Implementation on Deployed Branch

This migration goes on the **deployed branch**, not the Redis integration branch.

**Rationale:**
- R2 migration has zero dependency on Redis
- `pipeline_state.json` stays as-is on local filesystem until Redis branch merges
- Stacking two infrastructure changes on one undeployed branch creates unnecessary coupling
- R2 can ship to production independently; Redis merges later
- When Redis lands, `pipeline_state.json` moves from local filesystem → Redis HSET. Clean handoff.

**Sequence:** R2 on deployed branch → ship → Redis branch merges later → `pipeline_state.json` migrates to Redis at that point.
