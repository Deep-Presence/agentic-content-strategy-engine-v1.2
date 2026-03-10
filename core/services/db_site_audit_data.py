"""DbSiteAuditDataService — hybrid DB + filesystem site audit data service.

Implements ``SiteAuditDataServiceProtocol``.

DB-backed methods (fast queries, no filesystem scan):
- ``audit_exists`` — single COUNT query
- ``get_latest_audit_id`` — single ORDER BY query
- ``list_audits`` — paginated query + filesystem enrichment for score/grade

Filesystem-delegated methods (need full audit result JSON):
- ``get_audit_summary`` — reads audit_result.json
- ``get_audit_detail`` — reads audit_result.json
- ``get_findings`` — reads page_results + top_findings from JSON
- ``get_page_results`` — reads page_results from JSON

This hybrid approach mirrors ``DbContentDataService`` which delegates
stage content reads to the filesystem while serving metadata from DB.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from core.db.repositories.company_repo import CompanyRepository
from core.db.repositories.site_audit_repo import SiteAuditRepository

_logger = logging.getLogger(__name__)


class DbSiteAuditDataService:
    """Hybrid DB + filesystem site audit data service.

    Uses DB for audit discovery and existence checks (O(1) queries
    instead of filesystem scans). Delegates data-heavy methods to
    the filesystem helpers from ``json_site_audit_data``.

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

    # ── DB-backed methods ─────────────────────────────────────────────

    async def audit_exists(self, company_slug: str, domain: str) -> bool:
        """True when at least one completed audit exists for the given domain.

        Uses a single COUNT query — O(1) vs filesystem scan.
        """
        company_id = await self._resolve_company_id(company_slug)
        if company_id is None:
            return False
        return await self._audit_repo.exists_for_domain(company_id, domain)

    async def get_latest_audit_id(
        self, company_slug: str, domain: str
    ) -> str | None:
        """Return the audit_id of the most recent completed audit for *domain*.

        Uses a single ORDER BY query — O(1) vs filesystem scan.
        """
        company_id = await self._resolve_company_id(company_slug)
        if company_id is None:
            return None
        audit = await self._audit_repo.get_latest_for_domain(company_id, domain)
        return str(audit.id) if audit else None

    async def list_audits(
        self, company_slug: str, limit: int = 20
    ) -> list[dict]:
        """Return summary dicts for the most recent *limit* audit runs.

        Uses DB for audit discovery (ordered by created_at desc),
        then enriches each audit with score/grade from filesystem.
        Falls back to pure filesystem when company not found in DB.
        """
        company_id = await self._resolve_company_id(company_slug)
        if company_id is None:
            # Company not in DB — fall back to filesystem
            return await self._fs_list_audits(company_slug, limit)

        audits = await self._audit_repo.list_for_company(company_id, limit=limit)
        if not audits:
            # No audits in DB — fall back to filesystem (may have legacy data)
            return await self._fs_list_audits(company_slug, limit)

        results: list[dict[str, Any]] = []
        for audit in audits:
            # Enrich from filesystem for score/grade (not stored in DB yet)
            fs_summary = await self._fs_get_audit_summary_safe(
                company_slug, str(audit.id)
            )
            started = audit.started_at
            completed = audit.completed_at
            if hasattr(started, "isoformat") and started:
                started = started.isoformat()
            if hasattr(completed, "isoformat") and completed:
                completed = completed.isoformat()

            results.append({
                "audit_id": str(audit.id),
                "domain": audit.site_domain,
                "overall_score": fs_summary.get("overall_score", 0.0),
                "grade": fs_summary.get("grade", "F"),
                "pages_crawled": audit.pages_crawled or 0,
                "total_findings": audit.findings_count or 0,
                "status": (
                    audit.status.value
                    if hasattr(audit.status, "value")
                    else str(audit.status or "pending")
                ),
                "started_at": str(started or ""),
                "completed_at": str(completed or ""),
            })
        return results

    # ── Filesystem-delegated methods ──────────────────────────────────

    async def get_audit_summary(
        self, company_slug: str, audit_id: str
    ) -> dict:
        """Return a lightweight summary dict for one audit run.

        Delegates to filesystem — needs overall_score, grade, and other
        fields not yet stored in DB columns.
        """
        from core.services.json_site_audit_data import _sync_get_audit_summary

        return await asyncio.to_thread(
            _sync_get_audit_summary,
            self._artifacts_root,
            company_slug,
            audit_id,
        )

    async def get_audit_detail(
        self, company_slug: str, audit_id: str
    ) -> dict:
        """Return the full audit result dict.

        Delegates to filesystem — the full audit result is a large blob
        with dimension scores, bot access data, sitemap health, etc.
        """
        from core.services.json_site_audit_data import _sync_get_audit_detail

        return await asyncio.to_thread(
            _sync_get_audit_detail,
            self._artifacts_root,
            company_slug,
            audit_id,
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

        Delegates to filesystem — findings are nested within page_results
        and top_findings in the JSON audit result.
        """
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

    async def get_page_results(
        self,
        company_slug: str,
        audit_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Return paginated per-page audit results.

        Delegates to filesystem — page results are large blobs
        with per-page schema, AEO, and finding data.
        """
        from core.services.json_site_audit_data import _sync_get_page_results

        return await asyncio.to_thread(
            _sync_get_page_results,
            self._artifacts_root,
            company_slug,
            audit_id,
            page,
            page_size,
        )

    # ── Internal helpers ──────────────────────────────────────────────

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
