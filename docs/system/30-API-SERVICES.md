# API Services

> **Location:** `api/services/`
> **Owner:** API
> **Dependencies:** `core/services/`, StorageBackend, Redis cache
> **Dependents:** API routers
> **Last Updated:** 2026-04-09

## Overview

API-level service modules that reshape core service data into frontend-compatible formats. These are distinct from `core/services/` — they handle caching, path validation, and response formatting specific to the REST API contract.

## File Structure

| File | Purpose |
|------|---------|
| `gap_data_service.py` | Gap analysis data loading with Redis cache (TTL: 300-1200s) |
| `brand_data_service.py` | Brand research artifacts + run history with NaN/Inf handling |
| `content_data_service.py` | Content v1.3 artifacts with split TTL caching |
| `knowledge_doc_service.py` | Document upload/download via StorageBackend |
| `fallback_gap_data.py` | Fallback data provider |

## Key Patterns

- **Redis caching** with TTL per artifact type (60s-1200s)
- **Cache key format:** `cache:{domain}:{slug}:{filename}`
- **Pattern invalidation:** `cache_delete_pattern("cache:content:{slug}:*")`
- **Path traversal protection:** `is_relative_to()` + slug regex validation
- **NaN/Inf safety:** JSON-safe numeric handling for analytics data
- **Thread-safe I/O:** All filesystem reads via `asyncio.to_thread()`
