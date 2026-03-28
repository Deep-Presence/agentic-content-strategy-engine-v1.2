"""JsonSiteAuditDataService — StorageBackend-backed implementation of
SiteAuditDataServiceProtocol.

Reads audit results from:
  ``site_audit/{company_slug}/{audit_id}/audit_result.json``

Uses a module-level FIFO cache (10 entries) as L2 fallback when Redis
is unavailable.  Redis is the L1 cache (Session 6).
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from fastapi import HTTPException

if TYPE_CHECKING:
    from core.storage.backends.base import StorageBackend

_logger = logging.getLogger(__name__)

# ── Caching (Redis-backed, Session 6) ────────────────────────────────

from core.cache import cache_get, cache_set
from core.redis import get_sync_redis_or_none

# Module-level FIFO cache (L2 fallback when Redis unavailable):
# key -> (monotonic_ts, data).
# Max 10 entries; oldest evicted when full.
# Protected by _CACHE_LOCK for thread safety (asyncio.to_thread callers).
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_MAX = 10
_CACHE_TTL_S = 600  # 10 minutes — audit data is write-once
_CACHE_LOCK = threading.Lock()

# Slug validation: bare slug OR effective slug (slug__product-slug)
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")

# Audit ID validation: strict lowercase UUID4 format
_AUDIT_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _validate_slug(slug: str) -> None:
    """Raise HTTP 400 for invalid / path-traversal slugs."""
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid company slug: '{slug}'",
        )


def _evict_if_full() -> None:
    """Remove the oldest cache entry when the cache is full.

    Caller MUST hold ``_CACHE_LOCK``.
    """
    if len(_CACHE) >= _CACHE_MAX:
        oldest_key = next(iter(_CACHE))
        del _CACHE[oldest_key]


def _sort_timestamp(data: dict[str, Any]) -> str:
    """Return a sortable timestamp string from audit data.

    Prefers ``completed_at``, falls back to ``started_at``, then empty string.
    ISO 8601 strings sort lexicographically, so no datetime parsing needed.
    """
    ts = data.get("completed_at") or data.get("started_at") or ""
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()
    return str(ts)


def _validate_audit_id(audit_id: str) -> None:
    """Raise HTTP 400 for invalid or path-traversal audit IDs.

    Accepts only lowercase UUID4 hex strings (``xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx``).
    """
    if not _AUDIT_ID_RE.match(audit_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audit ID: '{audit_id}'",
        )


def _load_audit_result(
    backend: "StorageBackend", company_slug: str, audit_id: str,
) -> dict[str, Any]:
    """Load audit_result.json — Redis L1, in-memory L2, StorageBackend L3.

    Returns an empty dict when the file is missing or unparseable.
    Uses TTL-based in-memory cache invalidation as L2 fallback.
    All ``_CACHE`` access is protected by ``_CACHE_LOCK`` for thread
    safety under ``asyncio.to_thread()``.
    """
    redis = get_sync_redis_or_none()

    # L1: Redis cache
    cache_key = f"cache:audit:{company_slug}:{audit_id}"
    if redis is not None and company_slug and audit_id:
        cached = cache_get(redis, cache_key)
        if cached is not None:
            return cached

    # L2: in-memory FIFO cache (fallback when Redis unavailable)
    storage_key = f"site_audit/{company_slug}/{audit_id}/audit_result.json"
    mem_cache_key = storage_key
    now = time.monotonic()
    with _CACHE_LOCK:
        mem_cached = _CACHE.get(mem_cache_key)
        if mem_cached is not None and (now - mem_cached[0]) < _CACHE_TTL_S:
            return mem_cached[1]

    # L3: StorageBackend read (R2 or local)
    content = backend.read(storage_key)
    if content is None:
        return {}

    try:
        data = json.loads(content)
    except Exception as exc:
        _logger.warning("Failed to parse %s: %s", storage_key, exc)
        return {}

    # Populate Redis cache (L1)
    if redis is not None and company_slug and audit_id:
        cache_set(redis, cache_key, data, ttl=600)

    # Populate in-memory cache (L2)
    with _CACHE_LOCK:
        _evict_if_full()
        _CACHE[mem_cache_key] = (now, data)

    return data


def _discover_audit_ids(
    backend: "StorageBackend", company_slug: str,
) -> list[str]:
    """Discover audit ID subdirectories via StorageBackend.list_dir().

    Returns a list of valid UUID audit IDs found under
    ``site_audit/{company_slug}/``.
    """
    prefix = f"site_audit/{company_slug}"
    try:
        entries = backend.list_dir(prefix)
    except Exception:
        return []
    if not entries:
        return []

    # list_dir returns paths relative to storage root, e.g.
    # "site_audit/test-co/uuid-1" on local, or key suffixes on R2.
    # Strip the prefix to extract the UUID audit ID component.
    prefix_slash = prefix.rstrip("/") + "/"
    audit_ids: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        stripped = entry.strip("/")
        # Remove prefix to get the child name
        if stripped.startswith(prefix_slash):
            name = stripped[len(prefix_slash):].split("/")[0]
        else:
            # Fallback: take the last path component
            name = stripped.rsplit("/", 1)[-1]
        if name and _AUDIT_ID_RE.match(name) and name not in seen:
            audit_ids.append(name)
            seen.add(name)
    return audit_ids


# ---------------------------------------------------------------------------
# Sync helper functions — wrapped in asyncio.to_thread() by the service
# ---------------------------------------------------------------------------


def _sync_get_audit_summary(
    backend: "StorageBackend", company_slug: str, audit_id: str,
) -> dict[str, Any]:
    """Return a lightweight summary dict for one audit run."""
    _validate_slug(company_slug)
    _validate_audit_id(audit_id)
    data = _load_audit_result(backend, company_slug, audit_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Audit '{audit_id}' not found for company '{company_slug}'",
        )

    started = data.get("started_at") or ""
    completed = data.get("completed_at") or ""
    # datetime objects serialise to ISO strings; handle both str and None
    if hasattr(started, "isoformat"):
        started = started.isoformat()
    if hasattr(completed, "isoformat"):
        completed = completed.isoformat()

    return {
        "audit_id": data.get("audit_id", audit_id),
        "domain": data.get("domain", ""),
        "overall_score": data.get("overall_score", 0.0),
        "grade": data.get("grade", "F"),
        "pages_crawled": data.get("pages_crawled", 0),
        "total_findings": data.get("total_findings", 0),
        "status": data.get("status", "pending"),
        "started_at": str(started),
        "completed_at": str(completed),
    }


def _sync_get_audit_detail(
    backend: "StorageBackend", company_slug: str, audit_id: str,
) -> dict[str, Any]:
    """Return the full audit result dict (minus per-page details)."""
    _validate_slug(company_slug)
    _validate_audit_id(audit_id)
    data = _load_audit_result(backend, company_slug, audit_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Audit '{audit_id}' not found for company '{company_slug}'",
        )

    # Serialise timestamps to strings for the response model
    started = data.get("started_at") or ""
    completed = data.get("completed_at") or ""
    if hasattr(started, "isoformat"):
        started = started.isoformat()
    if hasattr(completed, "isoformat"):
        completed = completed.isoformat()

    return {
        "audit_id": data.get("audit_id", audit_id),
        "domain": data.get("domain", ""),
        "overall_score": data.get("overall_score", 0.0),
        "grade": data.get("grade", "F"),
        "pages_crawled": data.get("pages_crawled", 0),
        "pages_discovered": data.get("pages_discovered", 0),
        "duration_seconds": data.get("duration_seconds", 0.0),
        "dimension_scores": data.get("dimension_scores", []),
        "ai_bot_access": data.get("ai_bot_access", {}),
        "sitemap_health": data.get("sitemap_health", {}),
        "total_findings": data.get("total_findings", 0),
        "findings_by_severity": data.get("findings_by_severity", {}),
        "findings_by_dimension": data.get("findings_by_dimension", {}),
        "avg_snippet_readiness": data.get("avg_snippet_readiness", 0.0),
        "pages_with_schema": data.get("pages_with_schema", 0),
        "avg_question_heading_ratio": data.get("avg_question_heading_ratio", 0.0),
        "status": data.get("status", "pending"),
        "error_message": data.get("error_message"),
        "started_at": str(started),
        "completed_at": str(completed),
    }


def _sync_list_audits(
    backend: "StorageBackend", company_slug: str, limit: int,
) -> list[dict[str, Any]]:
    """Return summary dicts for the most recent *limit* audit runs."""
    _validate_slug(company_slug)
    audit_ids = _discover_audit_ids(backend, company_slug)
    if not audit_ids:
        return []

    # Load all audit data (cached via Redis + in-memory FIFO), sort by
    # completed_at/started_at from JSON (R2-compatible — no filesystem stat).
    id_data_pairs: list[tuple[str, dict[str, Any]]] = []
    for aid in audit_ids:
        data = _load_audit_result(backend, company_slug, aid)
        if data:
            id_data_pairs.append((aid, data))

    id_data_pairs.sort(key=lambda pair: _sort_timestamp(pair[1]), reverse=True)
    id_data_pairs = id_data_pairs[:limit]

    results: list[dict[str, Any]] = []
    for aid, data in id_data_pairs:
        started = data.get("started_at") or ""
        completed = data.get("completed_at") or ""
        if hasattr(started, "isoformat"):
            started = started.isoformat()
        if hasattr(completed, "isoformat"):
            completed = completed.isoformat()
        results.append(
            {
                "audit_id": data.get("audit_id", aid),
                "domain": data.get("domain", ""),
                "overall_score": data.get("overall_score", 0.0),
                "grade": data.get("grade", "F"),
                "pages_crawled": data.get("pages_crawled", 0),
                "total_findings": data.get("total_findings", 0),
                "status": data.get("status", "pending"),
                "started_at": str(started),
                "completed_at": str(completed),
            }
        )
    return results


def _sync_get_findings(
    backend: "StorageBackend",
    company_slug: str,
    audit_id: str,
    severity: Optional[str],
    dimension: Optional[str],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Return paginated, optionally filtered findings."""
    _validate_slug(company_slug)
    _validate_audit_id(audit_id)
    data = _load_audit_result(backend, company_slug, audit_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Audit '{audit_id}' not found for company '{company_slug}'",
        )

    # Collect all findings from page_results
    all_findings: list[dict[str, Any]] = []
    for page_data in data.get("page_results", []):
        for f in page_data.get("findings", []):
            all_findings.append(f)

    # Also include top_findings (site-level findings may live here)
    for f in data.get("top_findings", []):
        all_findings.append(f)

    # Filter
    if severity:
        all_findings = [
            f for f in all_findings if f.get("severity", "") == severity
        ]
    if dimension:
        all_findings = [
            f for f in all_findings if f.get("dimension", "") == dimension
        ]

    total = len(all_findings)
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    start = (page - 1) * page_size
    end = start + page_size
    page_items = all_findings[start:end]

    return {
        "findings": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def _sync_get_page_results(
    backend: "StorageBackend",
    company_slug: str,
    audit_id: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Return paginated per-page audit results."""
    _validate_slug(company_slug)
    _validate_audit_id(audit_id)
    data = _load_audit_result(backend, company_slug, audit_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Audit '{audit_id}' not found for company '{company_slug}'",
        )

    all_pages: list[dict[str, Any]] = data.get("page_results", [])
    total = len(all_pages)
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    start = (page - 1) * page_size
    end = start + page_size

    page_items = []
    for p in all_pages[start:end]:
        page_items.append(
            {
                "url": p.get("url", ""),
                "status_code": p.get("status_code", 0),
                "crawl_depth": p.get("crawl_depth", 0),
                "title": p.get("title", ""),
                "word_count": p.get("word_count", 0),
                "reading_level": p.get("reading_level", 0.0),
                "has_https": p.get("has_https", True),
                "is_noindex": p.get("is_noindex", False),
                # Accept both field name ("schema_result") and alias ("schema")
                "schema": p.get("schema_result", p.get("schema", {})),
                "aeo": p.get("aeo", {}),
                "finding_count": len(p.get("findings", [])),
            }
        )

    return {
        "pages": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def _sync_audit_exists(
    backend: "StorageBackend", company_slug: str, domain: str,
) -> bool:
    """True when at least one completed audit exists for the given domain."""
    audit_ids = _discover_audit_ids(backend, company_slug)
    for aid in audit_ids:
        data = _load_audit_result(backend, company_slug, aid)
        if data.get("domain") == domain and data.get("status") == "completed":
            return True
    return False


def _sync_get_latest_audit_id(
    backend: "StorageBackend", company_slug: str, domain: str,
) -> Optional[str]:
    """Return the audit_id of the most recent completed audit for *domain*."""
    audit_ids = _discover_audit_ids(backend, company_slug)
    if not audit_ids:
        return None

    best: Optional[tuple[str, str]] = None  # (sort_ts, audit_id)
    for aid in audit_ids:
        data = _load_audit_result(backend, company_slug, aid)
        if data.get("domain") == domain and data.get("status") == "completed":
            ts = _sort_timestamp(data)
            if best is None or ts > best[0]:
                best = (ts, data.get("audit_id", aid))

    return best[1] if best is not None else None


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class JsonSiteAuditDataService:
    """StorageBackend-backed site audit data service.

    All methods delegate to synchronous helper functions via
    ``asyncio.to_thread()`` so routers can be ``async def``.

    Args:
        artifacts_root: Root artifacts directory (e.g. ``Path("artifacts")``)
        backend: Optional StorageBackend. When omitted, created via factory
            (respects ``STORAGE_BACKEND`` setting — R2 or local).
    """

    def __init__(
        self,
        artifacts_root: Path,
        *,
        backend: Optional["StorageBackend"] = None,
    ) -> None:
        self._artifacts_root = artifacts_root
        if backend is not None:
            self._backend = backend
        else:
            from core.storage import get_storage_backend
            self._backend = get_storage_backend(artifacts_root)

    async def get_audit_summary(self, company_slug: str, audit_id: str) -> dict:
        """Return a lightweight summary dict for one audit run.

        Args:
            company_slug: The company's URL slug.
            audit_id: The unique audit run identifier.

        Returns:
            Dict matching AuditSummaryResponse fields.

        Raises:
            HTTPException(404): When the audit does not exist.
            HTTPException(400): When the slug is invalid.
        """
        return await asyncio.to_thread(
            _sync_get_audit_summary,
            self._backend,
            company_slug,
            audit_id,
        )

    async def get_audit_detail(self, company_slug: str, audit_id: str) -> dict:
        """Return the full audit result dict.

        Args:
            company_slug: The company's URL slug.
            audit_id: The unique audit run identifier.

        Returns:
            Dict matching AuditDetailResponse fields.

        Raises:
            HTTPException(404): When the audit does not exist.
            HTTPException(400): When the slug is invalid.
        """
        return await asyncio.to_thread(
            _sync_get_audit_detail,
            self._backend,
            company_slug,
            audit_id,
        )

    async def list_audits(self, company_slug: str, limit: int = 20) -> list[dict]:
        """Return summary dicts for the most recent *limit* audit runs.

        Args:
            company_slug: The company's URL slug.
            limit: Maximum number of audit summaries to return.

        Returns:
            List of dicts matching AuditSummaryResponse fields, sorted by
            most recent first.

        Raises:
            HTTPException(400): When the slug is invalid.
        """
        return await asyncio.to_thread(
            _sync_list_audits,
            self._backend,
            company_slug,
            limit,
        )

    async def get_findings(
        self,
        company_slug: str,
        audit_id: str,
        severity: str | None = None,
        dimension: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Return paginated, optionally filtered findings for one audit.

        Args:
            company_slug: The company's URL slug.
            audit_id: The unique audit run identifier.
            severity: Optional severity filter (``"critical"``, ``"high"``, etc.).
            dimension: Optional dimension filter (``"crawlability"``, etc.).
            page: 1-based page number.
            page_size: Number of findings per page.

        Returns:
            Dict matching AuditFindingsResponse fields.

        Raises:
            HTTPException(404): When the audit does not exist.
            HTTPException(400): When the slug is invalid.
        """
        return await asyncio.to_thread(
            _sync_get_findings,
            self._backend,
            company_slug,
            audit_id,
            severity,
            dimension,
            page,
            page_size,
        )

    async def get_page_results(
        self,
        company_slug: str,
        audit_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Return paginated per-page audit results.

        Args:
            company_slug: The company's URL slug.
            audit_id: The unique audit run identifier.
            page: 1-based page number.
            page_size: Number of page results per response page.

        Returns:
            Dict matching AuditPageResultsResponse fields.

        Raises:
            HTTPException(404): When the audit does not exist.
            HTTPException(400): When the slug is invalid.
        """
        return await asyncio.to_thread(
            _sync_get_page_results,
            self._backend,
            company_slug,
            audit_id,
            page,
            page_size,
        )

    async def audit_exists(self, company_slug: str, domain: str) -> bool:
        """True when at least one completed audit exists for the given domain.

        Args:
            company_slug: The company's URL slug.
            domain: Domain string to match against stored audit results.

        Returns:
            True if a completed audit for *domain* exists.
        """
        return await asyncio.to_thread(
            _sync_audit_exists,
            self._backend,
            company_slug,
            domain,
        )

    async def get_latest_audit_id(
        self, company_slug: str, domain: str
    ) -> str | None:
        """Return the audit_id of the most recent completed audit for *domain*.

        Args:
            company_slug: The company's URL slug.
            domain: Domain string to match.

        Returns:
            The audit_id string, or None if no completed audit exists.
        """
        return await asyncio.to_thread(
            _sync_get_latest_audit_id,
            self._backend,
            company_slug,
            domain,
        )
