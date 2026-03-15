# Sprint v16 — pgvector Migration

**Sprint ID:** `pgvector-migration-v16`
**Branch:** `feat/deployment-prep-sprints`
**Date:** 2026-03-15
**Status:** COMPLETE

---

## Goal

Replace ChromaDB (local SQLite-backed, single-process) with pgvector as the PRIMARY and ONLY vector store. Full production readiness — remove ChromaDB entirely.

## Phases Completed (8/8)

1. **VectorStoreClient + Module-Level API** — `core/shared_tools/vector_store.py` (469 lines). Drop-in replacement with same function names as `async_chroma_client`. Batch processing (500 items), lazy session factory, error handling matching persistence.py pattern.

2. **DB Migration 0016** — `persona_embeddings` table, `company_slug` columns on `semantic_units` + `paragraph_embeddings`, composite HNSW indexes, `url_enrichment_id` nullable, `run_id` nullable, backfill `company_slug` from companies table.

3. **EmbeddingRepository Extensions** — 7 new methods: slug-based queries, upserts with ON CONFLICT, persona embeddings, count/delete operations.

4. **Gap Analysis Consumer Migration** — S1, S5, pipeline.py, persistence.py. persist_s1 → no-op (VectorStoreClient writes during S1). persist_s5 → query embeddings only (citation paragraphs handled by VectorStoreClient).

5. **Audience Persona Migration** — Import path change only.

6. **CPS Model Migration** — `chroma_path` optional, `database_url` added, migration 0017 (cps_training_snippets + cps_training_queries tables).

7. **ChromaDB Removal** — Deleted `chroma_client.py`, `async_chroma_client.py`, tests, `FakeChromaCollection` fixture. Removed from `requirements.txt` + `pyproject.toml`. Updated `settings.py`, `CLAUDE.md`.

8. **Data Migration Script** — `scripts/migrate_chroma_to_pgvector.py` (268 lines). Idempotent (ON CONFLICT DO NOTHING), dry-run mode, summary report.

## Codex Review (gpt-5.3-codex)

All 11 findings addressed:
- F1: Migration script kwarg mismatch (`slug=` → `company_slug=`)
- F2: Cross-tenant citation collision (added `company_slug` to `_embedding_id` hash)
- F4: S1 delete-then-upsert data loss (removed separate delete, atomic in `upsert_embeddings`)
- F5: 0016 downgrade unsafe (added DELETE null rows before NOT NULL)
- F6: Missing `company_slug` backfill (added UPDATE from companies table)
- F7: persist_s5 incorrectly no-oped (restored query embedding persistence)
- F8: S4 FK integrity bug (deterministic `uuid5` for enrichment IDs)

## Files Changed

| Action | Count |
|--------|-------|
| Created | 5 (vector_store.py, migration 0016, migration 0017, test_vector_store.py, migrate_chroma_to_pgvector.py) |
| Modified | 14 |
| Deleted | 3 (chroma_client.py, async_chroma_client.py, test_async_chroma_client.py) |
| Net lines | +904 |

## Test Impact

- 493 new tests (`test_vector_store.py`)
- 118 modified tests (`test_persistence.py`)
- 198 deleted tests (`test_async_chroma_client.py`)
- 429 gap analysis tests passing, 0 failures

## Deferred

- DB integration tests for migrations 0016/0017 (requires `TEST_DATABASE_URL`)
- Integration test for `migrate_chroma_to_pgvector.py` script
- Tests for new EmbeddingRepository methods (mocked session)
