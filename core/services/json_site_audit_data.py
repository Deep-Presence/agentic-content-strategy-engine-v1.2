"""JsonSiteAuditDataService — filesystem-backed implementation of
SiteAuditDataServiceProtocol.

Reads audit results from:
  ``artifacts/site_audit/{company_slug}/{audit_id}/audit_result.json``

Uses a module-level FIFO cache (10 entries) to avoid redundant JSON reads
on repeated requests within the same process.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

_logger = logging.getLogger(__name__)

# ── Caching (Redis-backed, Session 6) ────────────────────────────────

from core.cache import cache_get, cache_set
from core.redis import get_sync_redis_or_none

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


def _load_audit_result(audit_dir: Path) -> dict[str, Any]:
    """Load audit_result.json — Redis cache first, file fallback.

    Derives slug and audit_id from the directory path for cache key.
    Returns an empty dict when the file is missing or unparseable.
    """
    redis = get_sync_redis_or_none()

    # Derive slug and audit_id from path: .../site_audit/{slug}/{audit_id}/
    audit_id = audit_dir.name
    slug = audit_dir.parent.name

    if redis is not None and slug and audit_id:
        cache_key = f"cache:audit:{slug}:{audit_id}"
        cached = cache_get(redis, cache_key)
        if cached is not None:
            return cached

    # File read (fallback or cache miss)
    result_file = audit_dir / "audit_result.json"
    if not result_file.exists():
        return {}

    try:
        data = json.loads(result_file.read_text(encoding="utf-8"))
    except Exception as exc:
        _logger.warning("Failed to parse %s: %s", result_file, exc)
        return {}

    # Populate cache
    if redis is not None and slug and audit_id:
        cache_set(redis, cache_key, data, ttl=600)

    return data


def _validate_audit_id(audit_id: str) -> None:
    """Raise HTTP 400 for invalid or path-traversal audit IDs.

    Accepts only lowercase UUID4 hex strings (``xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx``).
    """
    if not _AUDIT_ID_RE.match(audit_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audit ID: '{audit_id}'",
        )


def _audit_dir(artifacts_root: Path, company_slug: str, audit_id: str) -> Path:
    """Return the canonical path for a single audit run's output directory.

    Validates *audit_id* format and enforces a path-containment check as
    defense-in-depth against symlink escapes.
    """
    _validate_audit_id(audit_id)
    company_root = artifacts_root / "site_audit" / company_slug
    candidate = company_root / audit_id
    # Defense-in-depth: resolve symlinks and verify containment
    if not candidate.resolve().is_relative_to(company_root.resolve()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audit ID: '{audit_id}'",
        )
    return candidate


def _company_audit_root(artifacts_root: Path, company_slug: str) -> Path:
    """Return the root directory that contains all audits for a company."""
    return artifacts_root / "site_audit" / company_slug


# ---------------------------------------------------------------------------
# Sync helper functions — wrapped in asyncio.to_thread() by the service
# ---------------------------------------------------------------------------


def _sync_get_audit_summary(
    artifacts_root: Path, company_slug: str, audit_id: str
) -> dict[str, Any]:
    """Return a lightweight summary dict for one audit run."""
    _validate_slug(company_slug)
    d = _audit_dir(artifacts_root, company_slug, audit_id)
    data = _load_audit_result(d)
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
    artifacts_root: Path, company_slug: str, audit_id: str
) -> dict[str, Any]:
    """Return the full audit result dict (minus per-page details)."""
    _validate_slug(company_slug)
    d = _audit_dir(artifacts_root, company_slug, audit_id)
    data = _load_audit_result(d)
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
    artifacts_root: Path, company_slug: str, limit: int
) -> list[dict[str, Any]]:
    """Return summary dicts for the most recent *limit* audit runs."""
    _validate_slug(company_slug)
    root = _company_audit_root(artifacts_root, company_slug)
    if not root.exists():
        return []

    # Each sub-directory is an audit_id; sort by mtime descending (most recent first)
    audit_dirs = sorted(
        (p for p in root.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]

    results: list[dict[str, Any]] = []
    for d in audit_dirs:
        data = _load_audit_result(d)
        if not data:
            continue
        started = data.get("started_at") or ""
        completed = data.get("completed_at") or ""
        if hasattr(started, "isoformat"):
            started = started.isoformat()
        if hasattr(completed, "isoformat"):
            completed = completed.isoformat()
        results.append(
            {
                "audit_id": data.get("audit_id", d.name),
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
    artifacts_root: Path,
    company_slug: str,
    audit_id: str,
    severity: Optional[str],
    dimension: Optional[str],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Return paginated, optionally filtered findings."""
    _validate_slug(company_slug)
    d = _audit_dir(artifacts_root, company_slug, audit_id)
    data = _load_audit_result(d)
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
    artifacts_root: Path,
    company_slug: str,
    audit_id: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Return paginated per-page audit results."""
    _validate_slug(company_slug)
    d = _audit_dir(artifacts_root, company_slug, audit_id)
    data = _load_audit_result(d)
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
    artifacts_root: Path, company_slug: str, domain: str
) -> bool:
    """True when at least one completed audit exists for the given domain."""
    root = _company_audit_root(artifacts_root, company_slug)
    if not root.exists():
        return False
    for d in root.iterdir():
        if not d.is_dir():
            continue
        data = _load_audit_result(d)
        if data.get("domain") == domain and data.get("status") == "completed":
            return True
    return False


def _sync_get_latest_audit_id(
    artifacts_root: Path, company_slug: str, domain: str
) -> Optional[str]:
    """Return the audit_id of the most recent completed audit for *domain*."""
    root = _company_audit_root(artifacts_root, company_slug)
    if not root.exists():
        return None

    best: Optional[tuple[float, str]] = None  # (mtime, audit_id)
    for d in root.iterdir():
        if not d.is_dir():
            continue
        data = _load_audit_result(d)
        if data.get("domain") == domain and data.get("status") == "completed":
            mtime = d.stat().st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, data.get("audit_id", d.name))

    return best[1] if best is not None else None


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class JsonSiteAuditDataService:
    """Filesystem-backed site audit data service.

    All methods delegate to synchronous helper functions via
    ``asyncio.to_thread()`` so routers can be ``async def``.

    Args:
        artifacts_root: Root artifacts directory (e.g. ``Path("artifacts")``)
    """

    def __init__(self, artifacts_root: Path) -> None:
        self._artifacts_root = artifacts_root

    async def get_audit_summary(self, company_slug: str, audit_id: str) -> dict:
        """Return a lightweight summary dict for one audit run.

        Args:
            company_slug: The company's URL slug.
            audit_id: The unique audit run identifier.

        Returns:
            Dict matching AuditSummaryResponse fields.

        Raises:
            HTTPException(404): When the audit does not exist on disk.
            HTTPException(400): When the slug is invalid.
        """
        return await asyncio.to_thread(
            _sync_get_audit_summary,
            self._artifacts_root,
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
            self._artifacts_root,
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
            self._artifacts_root,
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
            self._artifacts_root,
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
            self._artifacts_root,
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
            True if a completed audit for *domain* exists on disk.
        """
        return await asyncio.to_thread(
            _sync_audit_exists,
            self._artifacts_root,
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
            self._artifacts_root,
            company_slug,
            domain,
        )
