# Sprint v11 PRD — DB Foundation Review Fixes

## Context

Sprint v10 implemented the DB Foundation (Phases A-I) adding DB persistence to 4 research pipelines. A critical review by **Claude (6 parallel agents) + Codex (gpt-5.3-codex)** independently identified **6 CRITICAL, 5 HIGH, and 6 MEDIUM** issues. Both reviewers converged on the same core problems.

This sprint fixes all blocking issues before the branch can be merged.

**Branch:** `research-agent-v1.2.0` (continues from v10)

---

## CRITICAL Fixes (Must Fix — Block Merge)

### C1: KB pipeline uses `manifest.docs` — field is `documents`

**Found by:** Codex
**Severity:** CRITICAL — all KB DB writes silently fail

**File:** `core/research/knowledge_base/pipeline.py:630`

**Bug:**
```python
ver = getattr(manifest.docs.get(dt.value), "version", 1) if manifest.docs else 1
```

`KBManifest` (at `core/models/knowledge_base.py:122`) has `documents: Dict[str, KBDocEntry]`, not `docs`. This raises `AttributeError`, caught by the outer `except Exception` — so **all** KB DB persistence silently fails: no doc writes, no synthesis write, no `persist_pipeline_run_complete`.

**Fix:**
```python
entry = manifest.documents.get(dt.value)
ver = entry.current_version if entry else 1
```

Also change `version` → `current_version` since `KBDocEntry` uses `current_version`.

**Tests:** Add regression test verifying persist calls use correct manifest field.

---

### C2: `upsert_artifact()` missing `company_id` in lookup key

**Found by:** Claude + Codex (independently)
**Severity:** CRITICAL — multi-tenancy data leak

**File:** `core/db/repositories/research_artifact_repo.py:106-114`

**Bug:**
```python
stmt = select(ResearchArtifactModel).where(
    ResearchArtifactModel.effective_slug == effective_slug,
    ResearchArtifactModel.artifact_type == artifact_type,
    ResearchArtifactModel.version == version,
)
```

The upsert matches on `(effective_slug, artifact_type, version, title)` but **omits `company_id`**. If two companies share a slug (e.g., both named "ramp"), Company B's persist call overwrites Company A's artifact row.

**Fix:**
```python
stmt = select(ResearchArtifactModel).where(
    ResearchArtifactModel.company_id == company_id,  # ADD THIS
    ResearchArtifactModel.effective_slug == effective_slug,
    ResearchArtifactModel.artifact_type == artifact_type,
    ResearchArtifactModel.version == version,
)
```

**Tests:** Add multi-tenancy isolation test — two companies with same slug don't collide.

---

### C3: AP/VSG persistence uses hardcoded `version=1` and wrong storage_key prefix

**Found by:** Codex
**Severity:** CRITICAL — DB rows never increment past v1, storage_key mismatch

**Files:**
- `core/research/audience_persona/pipeline.py:493-498`
- `core/research/voice_style_guide/pipeline.py:492-500`

**Bug (AP):**
```python
ver = 1  # persona storage is version-1 by default
await persist_persona_profile(
    session_factory, run_id, company_id, slug,
    pid, result.persona_name or (brief.persona_name if brief else pid),
    ver, result.content_md,
    f"audience_persona/{slug}/{pid}/v{ver}.md",  # wrong prefix
    kind=kind,
)
```

Issues:
1. `ver = 1` hardcoded — doesn't read actual version from manifest. Re-runs always overwrite v1.
2. Storage key uses `audience_persona/` but filesystem uses `audience_personas/` (plural).
3. Uses `slug` (company_slug) not `effective_slug` for product-scoped runs.

**Bug (VSG):**
```python
await persist_author_research(
    session_factory, run_id, company_id, slug,
    aid, result.name, 1, result.content_md,           # version hardcoded
    f"voice_style_guide/{slug}/authors/{aid}/v1.md",   # wrong path layout
)
await persist_voice_style_guide(
    session_factory, run_id, company_id, slug,
    1, guide_md,                                       # version hardcoded
    f"voice_style_guide/{slug}/guide/v1.md",
    source_authors=source_authors,
)
```

Issues:
1. Author + guide versions hardcoded to `1` — DB rows overwrite v1 forever.
2. Author storage key uses `/authors/{aid}/v1.md` but filesystem stores as `{aid}/v{N}.md` under author dir.

**Fix (AP):**
```python
manifest = storage.read_manifest()
for pid, result in persona_results.items():
    if result.error or not result.content_md:
        continue
    meta = (manifest.personas or {}).get(pid)
    ver = meta.current_version if meta else 1
    brief = pid_to_brief.get(pid)
    kind = "icp" if pid == id_map.get(approved_briefs[0].brief_id) else "secondary"
    await persist_persona_profile(
        session_factory, run_id, company_id, slug,
        pid, result.persona_name or (brief.persona_name if brief else pid),
        ver, result.content_md,
        f"audience_personas/{slug}/{pid}/v{ver}.md",
        kind=kind,
    )
```

**Fix (VSG):**
```python
manifest = storage.read_manifest()
for aid, result in research_results.items():
    if result.error or not result.content_md:
        continue
    author_meta = (manifest.authors or {}).get(aid)
    aver = author_meta.current_version if author_meta else 1
    await persist_author_research(
        session_factory, run_id, company_id, slug,
        aid, result.name, aver, result.content_md,
        f"voice_style_guide/{slug}/{aid}/v{aver}.md",
    )
guide_ver = manifest.guide.current_version if manifest.guide else 1
await persist_voice_style_guide(
    session_factory, run_id, company_id, slug,
    guide_ver, guide_md,
    f"voice_style_guide/{slug}/guide/v{guide_ver}.md",
    source_authors=source_authors,
)
```

**Tests:** Verify persist calls use manifest versions and correct directory prefixes.

---

### C4: `DbVSGDataService.get_guide()` missing 3 fields vs JSON counterpart

**Found by:** Claude + Codex (independently)
**Severity:** CRITICAL — router silently degrades

**File:** `core/services/db_vsg_data.py:106-109`

**Bug — DB returns:**
```python
return {
    "content_md": content_md,
    "word_count": len(content_md.split()),
}
```

**JSON returns (5 fields):**
```python
return {
    "content_md": guide_md,
    "version": manifest.guide.current_version,
    "word_count": len(guide_md.split()),
    "last_updated": manifest.guide.last_updated.isoformat() if manifest.guide.last_updated else None,
    "source_authors": manifest.guide.source_authors,
}
```

Router at `api/routers/voice_style_guide.py` accesses `result.get("version", 0)` — gets `0` instead of real version when DB service is active.

**Fix:**
```python
meta = artifact.metadata_json or {}
return {
    "content_md": content_md,
    "version": artifact.version,
    "word_count": len(content_md.split()),
    "last_updated": artifact.updated_at.isoformat() if artifact.updated_at else None,
    "source_authors": meta.get("source_authors", []),
}
```

**Tests:** Add assertion for all 5 keys in DB service test.

---

### C5: `DbKBDataService.get_summary()` shape mismatch

**Found by:** Claude + Codex (independently)
**Severity:** CRITICAL — KeyError when DB service active

**File:** `core/services/db_kb_data.py:61-66`

**Bug — DB returns:**
```python
return {
    "slug": effective_slug,
    "docs": docs,
    "synthesis_version": synthesis.version if synthesis else 0,
    "total_docs": len(docs),  # EXTRA — not in JSON
    # MISSING: company_name, last_full_refresh
}
```

**JSON returns:**
```python
return {
    "slug": effective_slug,
    "company_name": manifest.company_name,        # MISSING from DB
    "docs": docs,
    "synthesis_version": manifest.synthesis_version,
    "last_full_refresh": manifest.last_full_refresh.isoformat() if ... else None,  # MISSING from DB
}
```

**Fix:** Add `company_name` (from first artifact's metadata or empty string) and `last_full_refresh` (from pipeline run history or None). Remove `total_docs` (not in contract).

**Tests:** Assert both implementations return identical key sets.

---

### C6: DB `get_summary()` hardcodes empty/None in Persona + VSG services

**Found by:** Claude + Codex (independently)
**Severity:** CRITICAL — incorrect data returned

**Files:**
- `core/services/db_persona_data.py:123-130`
- `core/services/db_vsg_data.py:67-75`

**Bug (Persona):**
```python
return {
    "slug": effective_slug,
    "company_name": "",           # HARDCODED
    "total_personas": len(seen),
    "active_personas": active,
    "last_full_run": None,        # HARDCODED
    "kb_synthesis_version": None,  # HARDCODED
}
```

**Bug (VSG):**
```python
return {
    "slug": effective_slug,
    "company_name": "",       # HARDCODED
    ...
    "last_full_run": None,    # HARDCODED
}
```

**Fix:** Query pipeline run history for `last_full_run`. Extract `company_name` from artifact metadata. For `kb_synthesis_version`, query `research_artifacts` with `artifact_type=company_context`.

**Tests:** Assert DB summary includes non-empty `company_name` when artifacts exist.

---

## HIGH Fixes (Should Fix — Before Production)

### H1: Pipeline early returns leave runs stuck in `running` forever

**Found by:** Codex
**Severity:** HIGH — orphan `running` status rows in DB

**Files:**
- `core/research/knowledge_base/pipeline.py` (lines 265, 378, 474, 573)
- `core/research/audience_persona/pipeline.py` (line 323)
- `core/research/voice_style_guide/pipeline.py` (line 324)

**Bug:** Non-exception early returns (rejection, all-failed, empty results) never call `persist_pipeline_run_complete`. Runner only marks `failed` on exceptions. Result: pipeline_runs table accumulates `running` rows that never transition.

**Fix:** In `api/tasks/runner.py`, call `persist_pipeline_run_complete` after the pipeline function returns successfully, regardless of the pipeline's internal path:

```python
output = await run_knowledge_base_pipeline(...)
# Always mark complete after successful return
await persist_pipeline_run_complete(session_factory, run_id, {"status": "completed"})
```

This is safer than adding complete calls to every early-return path inside the pipeline.

**Tests:** Mock pipeline to return early (rejection), verify run marked complete.

---

### H2: TD pipeline writes no ORM rows but DB service queries TD tables

**Found by:** Codex
**Severity:** HIGH — empty results when DB service active

**Files:**
- `core/topic_discovery/pipeline.py:619` — only calls `persist_pipeline_run_complete`
- `core/services/db_topic_discovery_data.py` — queries `topic_discoveries`, `topic_assignments`

**Bug:** TD pipeline writes taxonomy/matrix to filesystem but never writes to TD-specific ORM tables. When `DbTopicDiscoveryDataService` is active, `get_discovery_summary()` and `list_assignments()` query these tables and find nothing.

**Fix (Option A — recommended):** Keep TD service fully JSON-backed until TD ORM write hooks exist. Remove `_build_db_td_data_service` or make it always return None.

**Fix (Option B):** Add TD-specific persist functions to write taxonomy/matrix to ORM tables.

**Tests:** Verify TD service returns correct data regardless of DATABASE_URL.

---

### H3: `DbKBDataService.get_synthesis()` missing `sha256`

**Found by:** Claude
**Severity:** HIGH — inconsistent contract

**File:** `core/services/db_kb_data.py:120-124`

**Fix:**
```python
meta = artifact.metadata_json or {}
return {
    "version": artifact.version,
    "content_md": content_md or "",
    "word_count": len((content_md or "").split()),
    "sha256": meta.get("sha256"),  # ADD THIS
}
```

---

### H4: DB `list_personas()` missing `last_updated` field

**Found by:** Claude + Codex
**Severity:** HIGH — shape mismatch

**File:** `core/services/db_persona_data.py:52-65`

**Fix:** Add `"last_updated": a.updated_at.isoformat() if a.updated_at else None` to the return dict.

---

### H5: Router endpoints still use direct Storage classes (bypass DI)

**Found by:** Claude
**Severity:** HIGH — DI layer becomes a facade

**Files:**
- `api/routers/knowledge_base.py:50-59` — `_kb_artifacts_exist()` reads manifest from disk
- `api/routers/audience_persona.py:94,332,386` — `PersonaStorage(...)` for guards
- `api/routers/voice_style_guide.py:70` — `VoiceStyleGuideStorage(...)` for manifest
- `api/routers/topic_discovery.py:72` — `TopicDiscoveryStorage(...)` for manifest

**Fix:** Defer to future sprint — guard refactoring is a larger scope change. Document as tech debt. Guards reading from filesystem is acceptable for now since filesystem is always written first.

---

## MEDIUM Fixes (Tech Debt — Track)

### M1: `get_latest_by_slug_and_type()` is redundant wrapper

**File:** `core/db/repositories/research_artifact_repo.py:41-47`

Delegates to `get_by_slug_and_type()` with no added value. Remove or document.

### M2: No input validation on `upsert_artifact()`

Empty `effective_slug`, negative `version`, path traversal `storage_key` — no validation at repo level. Add guards or document assumptions.

### M3: TD `list_assignments()` shape divergence

JSON uses `model_dump()`, DB uses explicit field extraction with `.value` on enums. Define shared assignment DTO.

### M4: JSON VSG `get_guide()` ignores `version` parameter

`version` kwarg accepted but never used — always returns latest. Implement versioned reads or remove param.

### M5: Missing multi-tenancy isolation tests

No test verifying two companies with same slug don't collide in `upsert_artifact()`.

### M6: DB services return `""` instead of `None` for missing content files

`content_md or ""` masks missing files. Downstream can't distinguish "empty" from "not found".

---

## Dependency Sequencing

```
C1 (KB manifest.docs) ──────── standalone, no deps
C2 (company_id scoping) ────── standalone, no deps
C3 (AP/VSG versions+paths) ─── standalone, no deps
C4 (DbVSG get_guide shape) ─── standalone, no deps
C5 (DbKB get_summary shape) ── standalone, no deps
C6 (DB get_summary values) ──── standalone, no deps

H1 (orphan running status) ──── after C1-C3 (touches same pipeline files)
H2 (TD service strategy) ────── standalone
H3 (synthesis sha256) ────────── standalone
H4 (persona last_updated) ───── standalone
H5 (router guards) ──────────── defer to future sprint
```

All C1-C6 and H1-H4 are **independent** — can be fixed in parallel.

---

## Test Plan

### New Tests (~15)

| Test | File | Covers |
|------|------|--------|
| `test_kb_persist_uses_documents_not_docs` | `tests/research/knowledge_base/test_pipeline_persistence.py` | C1 |
| `test_upsert_scopes_by_company_id` | `tests/db/test_research_artifact_repo.py` | C2 |
| `test_two_companies_same_slug_no_collision` | `tests/db/test_research_artifact_repo.py` | C2+M5 |
| `test_ap_persist_uses_manifest_version` | `tests/research/audience_persona/test_pipeline_persistence.py` | C3 |
| `test_ap_persist_storage_key_plural` | `tests/research/audience_persona/test_pipeline_persistence.py` | C3 |
| `test_vsg_persist_uses_manifest_version` | `tests/research/voice_style_guide/test_pipeline_persistence.py` | C3 |
| `test_db_vsg_get_guide_full_shape` | `tests/services/test_db_vsg_data.py` | C4 |
| `test_db_kb_get_summary_matches_json_keys` | `tests/services/test_db_kb_data.py` | C5 |
| `test_db_persona_get_summary_company_name` | `tests/services/test_db_persona_data.py` | C6 |
| `test_db_vsg_get_summary_company_name` | `tests/services/test_db_vsg_data.py` | C6 |
| `test_runner_marks_complete_on_early_return` | `tests/api/test_runner.py` | H1 |
| `test_db_kb_get_synthesis_has_sha256` | `tests/services/test_db_kb_data.py` | H3 |
| `test_db_persona_list_has_last_updated` | `tests/services/test_db_persona_data.py` | H4 |

### Modified Tests (~5)

Update existing tests that assert output shapes to verify key completeness.

---

## Verification

After all fixes:

```bash
# Run all sprint-affected tests
pytest tests/services/ tests/research/ tests/integration/ tests/db/ -v --tb=short

# Run full router tests
pytest tests/api/ -v --tb=short

# Verify no regressions
pytest tests/ -x -q --ignore=tests/api/test_hitl_interrupt_resume.py
```

---

## File Manifest

### Modified Files (10)

| File | Fix |
|------|-----|
| `core/research/knowledge_base/pipeline.py` | C1: `manifest.docs` → `manifest.documents`, `version` → `current_version` |
| `core/db/repositories/research_artifact_repo.py` | C2: Add `company_id` to upsert WHERE |
| `core/research/audience_persona/pipeline.py` | C3: Read version from manifest, fix storage key prefix |
| `core/research/voice_style_guide/pipeline.py` | C3: Read versions from manifest, fix storage key paths |
| `core/services/db_vsg_data.py` | C4: Add `version`, `last_updated`, `source_authors` to `get_guide()` |
| `core/services/db_kb_data.py` | C5: Add `company_name`, `last_full_refresh`; remove `total_docs`. H3: Add `sha256` to synthesis |
| `core/services/db_persona_data.py` | C6: Query metadata for `company_name`, `last_full_run`. H4: Add `last_updated` to list |
| `core/services/db_vsg_data.py` | C6: Query metadata for `company_name`, `last_full_run` |
| `api/tasks/runner.py` | H1: Add `persist_pipeline_run_complete` after successful pipeline return |
| `core/services/db_topic_discovery_data.py` | H2: Strategy decision needed (disable DB or add writes) |

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Changing upsert WHERE clause affects existing rows | Existing rows won't match new query | One-time only — no production DB rows yet |
| Pipeline persist block changes could introduce new bugs | New AttributeError if manifest field wrong | Test each persist block with mock manifests |
| DB summary queries add latency | Slower read endpoints | Latency is acceptable — these are metadata reads |
| H2 strategy decision blocks TD | TD DB reads return empty | Fallback to JSON is safe — functional, just not DB-backed |

---

## Review Attribution

| Issue | Claude | Codex |
|-------|--------|-------|
| C1: manifest.docs | - | Found |
| C2: company_id scoping | Found | Found |
| C3: hardcoded versions/paths | - | Found |
| C4: VSG get_guide shape | Found | Found |
| C5: KB get_summary shape | Found | Found |
| C6: DB summary hardcoded values | Found | Found |
| H1: orphan running status | - | Found |
| H2: TD write gap | - | Found |
| H3: synthesis sha256 | Found | - |
| H4: persona last_updated | Found | Found |
| H5: router guards bypass DI | Found | - |
