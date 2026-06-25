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
    html_map: Optional[dict[str, str]] = None,
    workspace_id: Optional[_uuid.UUID] = None,
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
                html_map=html_map,
                workspace_id=workspace_id,
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


async def hydrate_content_inventory_from_gap_analysis(
    session_factory: Optional[async_sessionmaker],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    pipeline_run_id: Optional[_uuid.UUID],
    storage: Any,
    ga_prefix: str,
    workspace_id: Optional[_uuid.UUID] = None,
) -> dict[str, int] | None:
    """Upsert crawled pages from Gap Analysis S1 into the content inventory.

    Reads ``company_page_analysis.json`` (written by ``embed_company_assets``)
    and ``discovered_pages.json`` for page metadata.  Structural signals are
    already pre-computed by S1 via ``compute_structural_signals()``.

    Args:
        session_factory: Async session factory (None = skip hydration).
        company_id: Company UUID.
        effective_slug: Effective slug for artifact scoping.
        pipeline_run_id: Pipeline run UUID used as ingestion_run_id.
        storage: ``StorageBackend`` instance for reading artifacts.
        ga_prefix: Artifact prefix (e.g. ``gap_analysis/{slug}``).

    Returns:
        ``{"upserted": N, "skipped": N}`` on success, ``None`` on skip/failure.
    """
    if not _should_hydrate(session_factory, company_id, pipeline_run_id):
        return None

    assert session_factory is not None
    assert company_id is not None
    assert pipeline_run_id is not None

    try:
        import json as _json

        from core.content_inventory.models import CrawledPageData
        from core.db.enums import ContentIngestionSource
        from core.db.repositories.content_inventory_repo import (
            ContentInventoryRepository,
        )
        from core.models.gap_analysis import CompanyPageAnalysis, DiscoveredPage
        from core.services.content_inventory_service import (
            ContentInventoryService,
            _classify_content_type,
        )

        # Read pre-computed page analyses from storage
        pa_path = f"{ga_prefix}/company_page_analysis.json"
        if not storage.exists(pa_path):
            logger.info(
                "content_inventory.ga_hydration_skipped_no_artifact",
                extra={"path": pa_path},
            )
            return None

        pa_raw = _json.loads(storage.read(pa_path))
        page_analyses = [CompanyPageAnalysis.model_validate(p) for p in pa_raw]
        if not page_analyses:
            return None

        # Read discovered pages for additional metadata (h1, meta_description)
        dp_lookup: dict[str, DiscoveredPage] = {}
        dp_path = f"{ga_prefix}/site_discovery/discovered_pages.json"
        if storage.exists(dp_path):
            dp_raw = _json.loads(storage.read(dp_path))
            for dp_data in dp_raw:
                dp = DiscoveredPage.model_validate(dp_data)
                dp_lookup[dp.url] = dp

        # Build CrawledPageData DTOs
        crawled: list[CrawledPageData] = []
        for pa in page_analyses:
            if not pa.url:
                continue

            signals = pa.structural_signals
            dp = dp_lookup.get(pa.url)

            structural_signals_dict = None
            has_faq = False
            heading_count = 0
            word_count = pa.word_count

            if signals is not None:
                structural_signals_dict = signals.model_dump(
                    mode="json", exclude={"per_paragraph_word_counts"}
                )
                has_faq = signals.has_faq_section
                heading_count = signals.header_count
                word_count = signals.word_count or word_count

            crawled.append(
                CrawledPageData(
                    url=pa.url,
                    title=pa.title or (dp.title if dp else "") or "",
                    h1_text=(dp.h1 if dp else "") or "",
                    meta_description=(dp.meta_description if dp else "") or "",
                    content_preview="",
                    word_count=word_count,
                    has_faq_section=has_faq,
                    has_schema_markup=False,
                    heading_count=heading_count,
                    content_type_detected=_classify_content_type(pa.url),
                    structural_signals=structural_signals_dict,
                    sitemap_lastmod=(dp.last_modified if dp else None),
                )
            )

        if not crawled:
            return None

        async with session_factory() as session:
            repo = ContentInventoryRepository(session)
            upserted = await repo.bulk_upsert_from_crawl(
                company_id=company_id,
                effective_slug=effective_slug,
                ingestion_run_id=pipeline_run_id,
                pages=crawled,
                ingestion_source=ContentIngestionSource.gap_analysis_crawl,
                workspace_id=workspace_id,
            )
            await session.commit()

        logger.info(
            "content_inventory.gap_analysis_hydrated",
            extra={
                "company_id": str(company_id),
                "effective_slug": effective_slug,
                "upserted": upserted,
                "skipped": len(page_analyses) - len(crawled),
            },
        )
        return {"upserted": upserted, "skipped": len(page_analyses) - len(crawled)}

    except Exception:
        logger.warning(
            "content_inventory.gap_analysis_hydration_failed",
            extra={
                "company_id": str(company_id) if company_id else None,
                "effective_slug": effective_slug,
            },
            exc_info=True,
        )
        return None
