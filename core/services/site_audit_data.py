"""SiteAuditDataServiceProtocol — async interface for site audit data retrieval."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SiteAuditDataServiceProtocol(Protocol):
    """Async interface for site audit data endpoints.

    Two implementations (planned):
    - ``JsonSiteAuditDataService``: wraps filesystem-backed functions via
      ``asyncio.to_thread()``.
    - ``DbSiteAuditDataService``: SQL queries against Postgres (future).
    """

    async def get_audit_summary(self, company_slug: str, audit_id: str) -> dict: ...

    async def get_audit_detail(self, company_slug: str, audit_id: str) -> dict: ...

    async def list_audits(self, company_slug: str, limit: int = 20) -> list[dict]: ...

    async def get_findings(
        self,
        company_slug: str,
        audit_id: str,
        severity: str | None = None,
        dimension: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict: ...

    async def get_page_results(
        self,
        company_slug: str,
        audit_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict: ...

    async def audit_exists(self, company_slug: str, domain: str) -> bool: ...

    async def get_latest_audit_id(
        self, company_slug: str, domain: str
    ) -> str | None: ...
