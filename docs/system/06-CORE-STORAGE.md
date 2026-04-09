# Core Storage Module

> **Location:** `core/storage/`
> **Owner:** Core
> **Dependencies:** boto3, redis, supabase (optional)
> **Dependents:** All pipelines (artifact I/O), `api/routers/artifacts.py`, services
> **Last Updated:** 2026-04-09

## Overview

The storage module provides an abstraction layer for artifact storage with pluggable backends. All pipeline outputs (JSON artifacts, markdown reports, generated content) are read and written through the `StorageBackend` ABC. Three implementations exist: `LocalStorageBackend` (filesystem), `R2StorageBackend` (Cloudflare R2, S3-compatible), and `CachedStorageBackend` (Redis TTL cache wrapper). A factory function selects the backend based on configuration.

## Architecture

```
                    StorageBackend (ABC)
                    ┌──────────────────┐
                    │ read()           │
                    │ write()          │
                    │ exists()         │
                    │ delete()         │
                    │ list_dir()       │
                    │ read_bytes()     │
                    │ write_bytes()    │
                    │ mkdir()          │
                    └──────┬───────────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    LocalStorage      R2Storage      CachedStorage
    (filesystem)    (S3-compat)     (wraps any backend)
                                    + Redis TTL cache
```

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `__init__.py` | Factory function | `get_storage_backend` |
| `backends/base.py` | ABC definition | `StorageBackend` |
| `backends/local.py` | Filesystem backend | `LocalStorageBackend` |
| `backends/r2.py` | Cloudflare R2 backend | `R2StorageBackend` |
| `cached_backend.py` | Redis cache wrapper | `CachedStorageBackend` |
| `supabase_client.py` | Supabase client singleton | `get_supabase_client` |
| `supabase_mirror.py` | Artifact mirroring to Supabase | `mirror_company_context_markdown`, etc. |

## Detailed Reference

### `StorageBackend` (ABC)

All paths must be relative (no leading `/`, no `..` traversal). Raises `ValueError` on invalid paths.

| Method | Signature | Description |
|--------|-----------|-------------|
| `read` | `(path: str) -> Optional[str]` | Read text. Returns `None` if not found |
| `write` | `(path: str, content: str) -> str` | Write text. Returns storage key. Uses atomic writes |
| `exists` | `(path: str) -> bool` | Check existence |
| `delete` | `(path: str) -> bool` | Idempotent delete. Returns `True` if existed |
| `list_dir` | `(prefix: str) -> list[str]` | List paths under prefix |
| `read_bytes` | `(path: str) -> Optional[bytes]` | Read binary |
| `write_bytes` | `(path: str, content: bytes) -> str` | Write binary |
| `mkdir` | `(path: str) -> None` | Ensure directory (no-op for object stores) |

### `LocalStorageBackend`

Filesystem-backed, rooted at single directory. Atomic writes via `tempfile` + `os.replace`. Path validation ensures no escape above root. Parent directories auto-created.

### `R2StorageBackend`

Cloudflare R2 (S3-compatible). Uses `boto3` sync S3 client with retry config (max_attempts=5). Handles key prefix for misconfigured endpoint URLs. Paginator for buckets >1000 keys. `mkdir()` is no-op (flat key-value store).

### `CachedStorageBackend`

Redis TTL cache wrapper. Degrades gracefully when Redis unavailable.

| Constant | Value | Purpose |
|----------|-------|---------|
| `_MAX_CACHEABLE_SIZE` | 512KB | Skip caching reads larger than this |
| `_READ_TTL` | 300s (5 min) | Read cache TTL |
| `_LIST_TTL` | 120s (2 min) | list_dir cache TTL |

Cache keys: `artifact:{path}` (text reads), `artifact_ls:{prefix}` (listings). Writes and deletes invalidate both path and parent directory caches.

### `get_storage_backend()` (Factory)

Returns configured backend based on `STORAGE_BACKEND` setting:
- `"r2"` → `R2StorageBackend` (validates R2 env vars)
- default → `LocalStorageBackend` at `{repo_root}/artifacts`

In `api/app.py`, the backend is optionally wrapped in `CachedStorageBackend` when Redis is available.

### Supabase Mirroring (Optional)

`supabase_mirror.py` provides functions to mirror artifacts to Supabase database tables with SHA256 versioning:
- `mirror_company_context_markdown()` / `mirror_company_context_if_configured()`
- `mirror_persona_markdown()` / `mirror_persona_if_configured()`
- `mirror_styleguide_markdown()` / `mirror_styleguide_if_configured()`

Each function creates/updates an artifact row and appends an immutable version snapshot.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `storage_backend` | `"r2"` | Backend selection |
| `r2_account_id` | `None` | Cloudflare account ID |
| `r2_access_key_id` | `None` | S3-compatible access key |
| `r2_secret_access_key` | `None` | S3-compatible secret key |
| `r2_bucket_name` | `None` | R2 bucket name |
| `r2_endpoint_url` | `None` | Custom endpoint (auto-derived from account_id) |

## Known Tech Debt

- ~92 direct filesystem bypasses across the codebase (gap analysis has 49)
- 3 services use mtime-based cache invalidation that breaks with R2
