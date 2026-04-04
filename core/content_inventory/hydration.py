"""Content Inventory hydration from Site Audit results.

Called from the task runner AFTER ``persist_site_audit_result`` completes.
Follows the same design principles as ``core/site_audit/persistence.py``:
- **Graceful degradation**: Catches all exceptions — DB errors NEVER crash
  the pipeline.
- **Per-step transaction isolation**: Opens its own session, commits, closes.
- **Filesystem-first, DB-additive**: Audit JSON is already written.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


def _should_hydrate(
    session_factory: Optional[async_sessionmaker],
    company_id: Optional[_uuid.UUID],
    pipeline_run_id: Optional[_uuid.UUID],
) -> bool:
    """Return True if DB hydration is configured."""
    return (
        session_factory is not None
        and company_id is not None
        and pipeline_run_id is not None
    )


async def hydrate_content_inventory_from_site_audit(
    session_factory: Optional[async_sessionmaker],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    pipeline_run_id: Optional[_uuid.UUID],
    audit_result: Any,
) -> dict[str, int] | None:
    """Upsert crawled pages from a Site Audit into the content inventory.

    Args:
        session_factory: Async session factory (None = skip hydration).
        company_id: Company UUID.
        effective_slug: Effective slug for artifact scoping.
        pipeline_run_id: Pipeline run UUID used as ingestion_run_id.
        audit_result: The ``SiteAuditResult`` Pydantic model.

    Returns:
        ``{"upserted": N, "skipped": N}`` on success, ``None`` on skip/failure.
    """
    if not _should_hydrate(session_factory, company_id, pipeline_run_id):
        return None

    # Guard: no page results to hydrate
    page_results = getattr(audit_result, "page_results", None)
    if not page_results:
        return None

    assert session_factory is not None
    assert company_id is not None
    assert pipeline_run_id is not None

    try:
        from core.db.repositories.content_inventory_repo import (
            ContentInventoryRepository,
        )
        from core.services.content_inventory_service import ContentInventoryService

        # Build a synthetic discovery_output-like object so
        # ingest_from_site_audit can process the data.
        # SiteAuditResult.page_results has all URL/SEO data needed.
        # sitemap_lastmod_map is not available here (only in S1DiscoveryOutput),
        # but it's optional — CMS sync will backfill content_modified_at.
        from types import SimpleNamespace

        pages_with_html = [
            (getattr(pr, "url", ""), "")  # HTML not needed for ingestion
            for pr in page_results
            if getattr(pr, "url", "")
        ]
        discovery_proxy = SimpleNamespace(
            pages_with_html=pages_with_html,
            sitemap_lastmod_map={},
        )

        async with session_factory() as session:
            repo = ContentInventoryRepository(session)
            svc = ContentInventoryService(inventory_repo=repo)

            result = await svc.ingest_from_site_audit(
                company_id=company_id,
                effective_slug=effective_slug,
                pipeline_run_id=pipeline_run_id,
                discovery_output=discovery_proxy,
                page_results=page_results,
            )

            await session.commit()

        logger.info(
            "content_inventory.site_audit_hydrated",
            extra={
                "company_id": str(company_id),
                "effective_slug": effective_slug,
                "upserted": result.get("upserted", 0),
                "skipped": result.get("skipped", 0),
            },
        )
        return result

    except Exception:
        logger.warning(
            "content_inventory.site_audit_hydration_failed",
            extra={
                "company_id": str(company_id) if company_id else None,
                "effective_slug": effective_slug,
            },
            exc_info=True,
        )
        return None
