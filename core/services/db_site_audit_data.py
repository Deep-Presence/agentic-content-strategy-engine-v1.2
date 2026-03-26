"""DbSiteAuditDataService — DB-first site audit data service.

Implements ``SiteAuditDataServiceProtocol``.

**DB-first with per-audit filesystem fallback:**  When ``DATABASE_URL`` is
set and the audit has enriched data (``overall_score IS NOT NULL``), all
reads come from DB columns / child tables.  Pre-migration audits (thin
rows) or partial-persist failures fall back to the filesystem per-audit.

Methods:
- ``audit_exists`` — DB COUNT query
- ``get_latest_audit_id`` — DB ORDER BY query
- ``list_audits`` — DB query, score/grade from enriched columns
- ``get_audit_summary`` — DB-first, FS fallback per-audit
- ``get_audit_detail`` — DB-first, FS fallback per-audit
- ``get_findings`` — DB paginated query, FS fallback per-audit
- ``get_page_results`` — DB paginated query, FS fallback per-audit
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
import uuid as _uuid
from pathlib import Path
from typing import Any

from core.db.repositories.company_repo import CompanyRepository
from core.db.repositories.site_audit_repo import SiteAuditRepository

_logger = logging.getLogger(__name__)

# UUID validation (same pattern as JsonSiteAuditDataService)
_AUDIT_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _is_valid_uuid(audit_id: str) -> bool:
    """Return True if audit_id is a valid lowercase UUID4 string."""
    return bool(_AUDIT_ID_RE.match(audit_id))


def _is_enriched(audit: Any) -> bool:
    """True when the audit row has been fully persisted (post-migration).

    Sentinel: ``overall_score IS NOT NULL`` — set by
    ``persist_site_audit_result()`` only after all enriched columns
    are written.
    """
    return getattr(audit, "overall_score", None) is not None


def _ts(val: Any) -> str:
    """Coerce a datetime-ish value to an ISO string (or empty string)."""
    if val is None:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _audit_to_summary_dict(audit: Any) -> dict[str, Any]:
    """Convert a SiteAuditModel row to a summary dict with null coalescing."""
    status_val = (
        audit.status.value
        if hasattr(audit.status, "value")
        else str(audit.status or "pending")
    )
    return {
        "audit_id": str(audit.id),
        "domain": audit.site_domain or "",
        "overall_score": audit.overall_score or 0.0,
        "grade": audit.grade or "F",
        "pages_crawled": audit.pages_crawled or 0,
        "total_findings": audit.findings_count or 0,
        "status": status_val,
        "started_at": _ts(audit.started_at),
        "completed_at": _ts(audit.completed_at),
    }


def _audit_to_detail_dict(audit: Any) -> dict[str, Any]:
    """Convert a SiteAuditModel row to a full detail dict with null coalescing."""
    status_val = (
        audit.status.value
        if hasattr(audit.status, "value")
        else str(audit.status or "pending")
    )
    return {
        "audit_id": str(audit.id),
        "domain": audit.site_domain or "",
        "overall_score": audit.overall_score or 0.0,
        "grade": audit.grade or "F",
        "pages_crawled": audit.pages_crawled or 0,
        "pages_discovered": audit.pages_discovered or 0,
        "duration_seconds": audit.duration_seconds or 0.0,
        "dimension_scores": audit.dimension_scores or [],
        "ai_bot_access": audit.ai_bot_access or {},
        "sitemap_health": audit.sitemap_health or {},
        "total_findings": audit.findings_count or 0,
        "findings_by_severity": audit.findings_by_severity or {},
        "findings_by_dimension": audit.findings_by_dimension or {},
        "avg_snippet_readiness": audit.avg_snippet_readiness or 0.0,
        "pages_with_schema": audit.pages_with_schema or 0,
        "avg_question_heading_ratio": audit.avg_question_heading_ratio or 0.0,
        "status": status_val,
        "error_message": audit.error_message,
        "started_at": _ts(audit.started_at),
        "completed_at": _ts(audit.completed_at),
    }


def _finding_to_dict(finding: Any) -> dict[str, Any]:
    """Convert an AuditFindingModel row to a dict."""
    sev = finding.severity
    if hasattr(sev, "value"):
        sev = sev.value
    return {
        "finding_type": finding.finding_type or "",
        "dimension": finding.dimension or "",
        "severity": str(sev or "info"),
        "message": finding.message or "",
        "recommendation": finding.recommendation or "",
        "url": finding.page_url or "",
        "details": finding.details,
    }


def _page_result_to_dict(pr: Any) -> dict[str, Any]:
    """Convert an AuditPageResultModel row to a dict."""
    return {
        "url": pr.url or "",
        "status_code": pr.status_code or 0,
        "crawl_depth": pr.crawl_depth or 0,
        "title": pr.title or "",
        "word_count": pr.word_count or 0,
        "reading_level": pr.reading_level or 0.0,
        "has_https": pr.has_https if pr.has_https is not None else True,
        "is_noindex": pr.is_noindex if pr.is_noindex is not None else False,
        "schema": (pr.result_json or {}).get("schema_result", (pr.result_json or {}).get("schema", {})),
        "aeo": (pr.result_json or {}).get("aeo", {}),
        "finding_count": pr.finding_count or 0,
    }


class DbSiteAuditDataService:
    """DB-first site audit data service with per-audit filesystem fallback.

    Reads enriched audits from DB columns / child tables. Falls back to
    filesystem for pre-migration audits (``overall_score IS NULL``) or
    when the audit row is missing entirely.

    Args:
        audit_repo: SiteAuditRepository for DB queries.
        company_repo: CompanyRepository for slug → company_id resolution.
        artifacts_root: Root artifacts directory (e.g. ``Path("artifacts")``).
    """

    def __init__(
        self,
        audit_repo: SiteAuditRepository,
        company_repo: CompanyRepository,
        artifacts_root: Path,
    ) -> None:
        self._audit_repo = audit_repo
        self._company_repo = company_repo
        self._artifacts_root = artifacts_root

    async def _resolve_company_id(self, company_slug: str) -> Any:
        """Resolve company_slug → company UUID via CompanyRepository."""
        company = await self._company_repo.get_by_slug(company_slug)
        if company is None:
            return None
        return company.id

    # ── audit_exists / get_latest_audit_id (unchanged — already DB-backed) ──

    async def audit_exists(self, company_slug: str, domain: str) -> bool:
        """True when at least one completed audit exists for the given domain."""
        company_id = await self._resolve_company_id(company_slug)
        if company_id is None:
            return False
        return await self._audit_repo.exists_for_domain(company_id, domain)

    async def audit_exists_for_slug(
        self, effective_slug: str, domain: str
    ) -> bool:
        """True when a completed/degraded audit exists for *slug* + *domain*."""
        return await self._audit_repo.exists_for_slug_and_domain(
            effective_slug, domain,
        )

    async def get_latest_audit_id(
        self, company_slug: str, domain: str
    ) -> str | None:
        """Return the audit_id of the most recent completed audit for *domain*."""
        company_id = await self._resolve_company_id(company_slug)
        if company_id is None:
            return None
        audit = await self._audit_repo.get_latest_for_domain(company_id, domain)
        return str(audit.id) if audit else None

    # ── list_audits — DB-first, score/grade from enriched columns ────────

    async def list_audits(
        self, company_slug: str, limit: int = 20
    ) -> list[dict]:
        """Return summary dicts for the most recent *limit* audit runs.

        DB-first: score/grade come from enriched DB columns (no FS enrichment
        needed for post-migration audits). Falls back to filesystem for
        pre-migration data.
        """
        company_id = await self._resolve_company_id(company_slug)
        if company_id is None:
            return await self._fs_list_audits(company_slug, limit)

        audits = await self._audit_repo.list_for_company(company_id, limit=limit)
        if not audits:
            return await self._fs_list_audits(company_slug, limit)

        results: list[dict[str, Any]] = []
        for audit in audits:
            if _is_enriched(audit):
                # DB has all data — no filesystem read needed
                results.append(_audit_to_summary_dict(audit))
            else:
                # Pre-migration thin row — enrich from filesystem
                fs_summary = await self._fs_get_audit_summary_safe(
                    company_slug, str(audit.id)
                )
                results.append({
                    "audit_id": str(audit.id),
                    "domain": audit.site_domain or "",
                    "overall_score": fs_summary.get("overall_score", 0.0),
                    "grade": fs_summary.get("grade", "F"),
                    "pages_crawled": audit.pages_crawled or 0,
                    "total_findings": audit.findings_count or 0,
                    "status": (
                        audit.status.value
                        if hasattr(audit.status, "value")
                        else str(audit.status or "pending")
                    ),
                    "started_at": _ts(audit.started_at),
                    "completed_at": _ts(audit.completed_at),
                })
        return results

    # ── get_audit_summary — DB-first, FS fallback per-audit ──────────────

    async def get_audit_summary(
        self, company_slug: str, audit_id: str
    ) -> dict:
        """Return a lightweight summary dict for one audit run.

        DB-first: if the audit row is enriched, return from DB.
        Otherwise, fall back to filesystem.
        """
        if not _is_valid_uuid(audit_id):
            # Invalid UUID — skip DB, let FS service return 400
            return await self._fs_get_audit_summary(company_slug, audit_id)

        audit = await self._audit_repo.get_by_slug_and_audit_id(
            company_slug, audit_id
        )
        if audit is not None and _is_enriched(audit):
            return _audit_to_summary_dict(audit)

        # Fallback: filesystem
        return await self._fs_get_audit_summary(company_slug, audit_id)

    # ── get_audit_detail — DB-first, FS fallback per-audit ───────────────

    async def get_audit_detail(
        self, company_slug: str, audit_id: str
    ) -> dict:
        """Return the full audit result dict.

        DB-first: if the audit row is enriched, return all columns
        from DB (dimension_scores, ai_bot_access, sitemap_health, etc.).
        Otherwise, fall back to filesystem.
        """
        if not _is_valid_uuid(audit_id):
            return await self._fs_get_audit_detail(company_slug, audit_id)

        audit = await self._audit_repo.get_by_slug_and_audit_id(
            company_slug, audit_id
        )
        if audit is not None and _is_enriched(audit):
            return _audit_to_detail_dict(audit)

        # Fallback: filesystem
        return await self._fs_get_audit_detail(company_slug, audit_id)

    # ── get_findings — DB paginated query, FS fallback ───────────────────

    async def get_findings(
        self,
        company_slug: str,
        audit_id: str,
        severity: str | None = None,
        dimension: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Return paginated, optionally filtered findings.

        DB-first: queries AuditFindingModel with optional severity/dimension
        filters. Falls back to filesystem for pre-migration audits.
        """
        if not _is_valid_uuid(audit_id):
            return await self._fs_get_findings(
                company_slug, audit_id, severity, dimension, page, page_size
            )

        # Check if this audit is enriched in DB
        enriched = await self._audit_repo.has_enriched_data(audit_id)
        if enriched:
            offset = (page - 1) * page_size
            findings, total = await self._audit_repo.get_findings_for_audit(
                audit_id,
                severity=severity,
                dimension=dimension,
                limit=page_size,
                offset=offset,
            )
            total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
            return {
                "findings": [_finding_to_dict(f) for f in findings],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }

        # Fallback: filesystem
        return await self._fs_get_findings(
            company_slug, audit_id, severity, dimension, page, page_size
        )

    # ── get_page_results — DB paginated query, FS fallback ───────────────

    async def get_page_results(
        self,
        company_slug: str,
        audit_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Return paginated per-page audit results.

        DB-first: queries AuditPageResultModel ordered by page_index.
        Falls back to filesystem for pre-migration audits.
        """
        if not _is_valid_uuid(audit_id):
            return await self._fs_get_page_results(
                company_slug, audit_id, page, page_size
            )

        enriched = await self._audit_repo.has_enriched_data(audit_id)
        if enriched:
            offset = (page - 1) * page_size
            pages, total = await self._audit_repo.get_page_results_for_audit(
                audit_id,
                limit=page_size,
                offset=offset,
            )
            total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
            return {
                "pages": [_page_result_to_dict(pr) for pr in pages],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }

        # Fallback: filesystem
        return await self._fs_get_page_results(
            company_slug, audit_id, page, page_size
        )

    # ── Filesystem fallback helpers ──────────────────────────────────────

    async def _fs_list_audits(
        self, company_slug: str, limit: int
    ) -> list[dict]:
        """Filesystem fallback for list_audits."""
        from core.services.json_site_audit_data import _sync_list_audits

        return await asyncio.to_thread(
            _sync_list_audits,
            self._artifacts_root,
            company_slug,
            limit,
        )

    async def _fs_get_audit_summary_safe(
        self, company_slug: str, audit_id: str
    ) -> dict:
        """Load audit summary from filesystem, returning empty dict on error."""
        try:
            from core.services.json_site_audit_data import _sync_get_audit_summary

            return await asyncio.to_thread(
                _sync_get_audit_summary,
                self._artifacts_root,
                company_slug,
                audit_id,
            )
        except Exception:
            _logger.debug(
                "Failed to load audit summary from filesystem for %s/%s",
                company_slug,
                audit_id,
            )
            return {}

    async def _fs_get_audit_summary(
        self, company_slug: str, audit_id: str
    ) -> dict:
        """Filesystem fallback for get_audit_summary (raises on 404)."""
        from core.services.json_site_audit_data import _sync_get_audit_summary

        return await asyncio.to_thread(
            _sync_get_audit_summary,
            self._artifacts_root,
            company_slug,
            audit_id,
        )

    async def _fs_get_audit_detail(
        self, company_slug: str, audit_id: str
    ) -> dict:
        """Filesystem fallback for get_audit_detail (raises on 404)."""
        from core.services.json_site_audit_data import _sync_get_audit_detail

        return await asyncio.to_thread(
            _sync_get_audit_detail,
            self._artifacts_root,
            company_slug,
            audit_id,
        )

    async def _fs_get_findings(
        self,
        company_slug: str,
        audit_id: str,
        severity: str | None,
        dimension: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        """Filesystem fallback for get_findings."""
        from core.services.json_site_audit_data import _sync_get_findings

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

    async def _fs_get_page_results(
        self,
        company_slug: str,
        audit_id: str,
        page: int,
        page_size: int,
    ) -> dict:
        """Filesystem fallback for get_page_results."""
        from core.services.json_site_audit_data import _sync_get_page_results

        return await asyncio.to_thread(
            _sync_get_page_results,
            self._artifacts_root,
            company_slug,
            audit_id,
            page,
            page_size,
        )
