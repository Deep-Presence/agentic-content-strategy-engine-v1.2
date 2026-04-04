"""Content Inventory service — orchestrates ingestion, embedding, and similarity.

Not a pipeline — a service that other pipelines call into.
Injected via FastAPI dependency (DB-only, no JSON fallback).
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime
from typing import Any

from core.content_inventory.models import (
    CannibalizationMatch,
    CrawledPageData,
    ExistingCoverageResult,
)
from core.content_inventory.url_utils import normalize_url
from core.db.enums import ContentIngestionSource
from core.db.repositories.content_inventory_repo import ContentInventoryRepository

_logger = logging.getLogger(__name__)

# Embedding text formula per design doc Section 10.1
_EMBED_TEMPLATE = "{title} | {h1_text} | {meta_description} | {content_preview}"
_EMBED_PREVIEW_LIMIT = 300


class ContentInventoryService:
    """Orchestrates content inventory operations.

    Not a pipeline — a service that other pipelines call into.
    """

    def __init__(
        self,
        *,
        inventory_repo: ContentInventoryRepository,
    ) -> None:
        self._repo = inventory_repo

    # ── Ingestion ─────────────────────────────────────────────────

    async def ingest_from_site_audit(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        pipeline_run_id: _uuid.UUID,
        discovery_output: Any,
        page_results: list[Any],
    ) -> dict[str, int]:
        """Extract page metadata from site audit results, bulk upsert.

        *discovery_output*: ``S1DiscoveryOutput`` (pages_with_html, sitemap_lastmod_map)
        *page_results*: list of ``PageAuditResult``

        Returns {"upserted": N, "skipped": N}
        """
        # Build a URL → PageAuditResult lookup
        result_map: dict[str, Any] = {}
        for pr in page_results:
            if pr.url:
                result_map[pr.url] = pr

        pages_with_html: list[tuple[str, str]] = getattr(
            discovery_output, "pages_with_html", []
        )
        sitemap_lastmod_map: dict[str, str] = getattr(
            discovery_output, "sitemap_lastmod_map", {}
        )

        crawled: list[CrawledPageData] = []
        skipped = 0

        for url, _html in pages_with_html:
            pr = result_map.get(url)
            if pr is None:
                skipped += 1
                continue

            # Detect FAQ section from AEO content patterns
            has_faq = False
            aeo = getattr(pr, "aeo", None)
            if aeo:
                patterns = getattr(aeo, "content_patterns", {})
                has_faq = patterns.get("faq_section", False)

            # Has schema markup
            schema_result = getattr(pr, "schema_result", None)
            has_schema = False
            if schema_result:
                schemas = getattr(schema_result, "schemas_found", [])
                has_schema = len(schemas) > 0

            # Content type heuristic from URL
            content_type = _classify_content_type(url)

            crawled.append(
                CrawledPageData(
                    url=url,
                    title=getattr(pr, "title", "") or "",
                    h1_text=getattr(pr, "h1_text", "") or "",
                    meta_description=getattr(pr, "meta_description", "") or "",
                    content_preview=(getattr(pr, "meta_description", "") or "")[:500],
                    word_count=getattr(pr, "word_count", 0) or 0,
                    has_faq_section=has_faq,
                    has_schema_markup=has_schema,
                    heading_count=len(getattr(pr, "headings", [])),
                    content_type_detected=content_type,
                    sitemap_lastmod=sitemap_lastmod_map.get(url),
                )
            )

        upserted = await self._repo.bulk_upsert_from_crawl(
            company_id=company_id,
            effective_slug=effective_slug,
            ingestion_run_id=pipeline_run_id,
            pages=crawled,
        )

        _logger.info(
            "content_inventory.site_audit_ingest",
            extra={
                "company_id": str(company_id),
                "upserted": upserted,
                "skipped": skipped,
            },
        )
        return {"upserted": upserted, "skipped": skipped}

    async def ingest_from_cms_sync(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        cms_posts: list[Any],
    ) -> list[tuple[_uuid.UUID, Any]]:
        """Upsert CMS posts into content_inventory.

        Returns list of (content_inventory_id, cms_post_identifier) pairs
        for the caller to link cms_synced_posts.content_inventory_id.
        """
        pairs: list[tuple[_uuid.UUID, Any]] = []

        for post in cms_posts:
            url = getattr(post, "url", "") or getattr(post, "link", "")
            title = getattr(post, "title", "") or ""
            if not url:
                continue

            model = await self._repo.upsert_page(
                company_id=company_id,
                effective_slug=effective_slug,
                url=url,
                title=title,
                ingestion_source=ContentIngestionSource.cms_sync,
                h1_text=getattr(post, "h1_text", "") or "",
                meta_description=getattr(post, "excerpt", "") or "",
                content_preview=getattr(post, "content_preview", "") or "",
                word_count=getattr(post, "word_count", 0) or 0,
                categories=getattr(post, "categories", None),
                tags=getattr(post, "tags", None),
                seo_title=getattr(post, "seo_title", "") or "",
                seo_description=getattr(post, "seo_description", "") or "",
                published_at=getattr(post, "published_at", None),
                content_modified_at=getattr(post, "modified_at", None),
            )
            post_id = getattr(post, "id", None) or getattr(post, "cms_post_id", None)
            pairs.append((model.id, post_id))

        _logger.info(
            "content_inventory.cms_sync_ingest",
            extra={"company_id": str(company_id), "count": len(pairs)},
        )
        return pairs

    async def ingest_from_csv(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        csv_rows: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Parse and upsert CSV rows. Returns {imported, skipped, errors}."""
        valid_pages: list[CrawledPageData] = []
        errors: list[str] = []
        skipped = 0

        for i, row in enumerate(csv_rows):
            url = (row.get("url") or "").strip()
            title = (row.get("title") or "").strip()

            if not url:
                errors.append(f"Row {i + 1}: missing url")
                skipped += 1
                continue
            if not title:
                title = url  # fallback

            word_count = 0
            wc_str = row.get("word_count", "")
            if wc_str:
                try:
                    word_count = int(wc_str)
                except ValueError:
                    pass

            published_at_str = row.get("published_at")

            valid_pages.append(
                CrawledPageData(
                    url=url,
                    title=title,
                    word_count=word_count,
                    sitemap_lastmod=published_at_str,
                )
            )

        # Use a run_id of None for CSV imports
        imported = 0
        if valid_pages:
            # Upsert one-by-one since we need csv_import source
            for page in valid_pages:
                published_at = None
                if page.sitemap_lastmod:
                    try:
                        published_at = datetime.fromisoformat(
                            page.sitemap_lastmod.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pass

                categories = None
                # Parse comma-separated categories from raw CSV
                # (sitemap_lastmod is repurposed; check original row)
                cat_idx = valid_pages.index(page)
                raw_cats = csv_rows[cat_idx + skipped - len(errors) if False else cat_idx].get("categories", "")
                if raw_cats:
                    categories = [c.strip() for c in raw_cats.split(",") if c.strip()]

                await self._repo.upsert_page(
                    company_id=company_id,
                    effective_slug=effective_slug,
                    url=page.url,
                    title=page.title,
                    ingestion_source=ContentIngestionSource.csv_import,
                    word_count=page.word_count,
                    published_at=published_at,
                    categories=categories,
                )
                imported += 1

        _logger.info(
            "content_inventory.csv_ingest",
            extra={
                "company_id": str(company_id),
                "imported": imported,
                "skipped": skipped,
            },
        )
        return {"imported": imported, "skipped": skipped, "errors": errors}

    async def register_published_content(
        self,
        company_id: _uuid.UUID,
        effective_slug: str,
        url: str,
        title: str,
        word_count: int,
        content_text: str,
    ) -> Any:
        """Register content published by Content Engine. Embeds inline."""
        model = await self._repo.upsert_page(
            company_id=company_id,
            effective_slug=effective_slug,
            url=url,
            title=title,
            ingestion_source=ContentIngestionSource.content_engine,
            word_count=word_count,
            content_preview=content_text[:500] if content_text else "",
        )

        # Generate embedding inline for Content Engine output
        if content_text:
            try:
                from core.shared_tools.async_embedding_client import async_embed_texts

                embed_text = _EMBED_TEMPLATE.format(
                    title=title,
                    h1_text="",
                    meta_description="",
                    content_preview=content_text[:_EMBED_PREVIEW_LIMIT],
                )
                embeddings = await async_embed_texts([embed_text])
                if embeddings and embeddings[0]:
                    await self._repo.update_embeddings_batch(
                        [(model.id, embeddings[0])]
                    )
            except Exception:
                _logger.warning(
                    "content_inventory.inline_embed_failed",
                    extra={"inventory_id": str(model.id)},
                    exc_info=True,
                )

        return model

    # ── Embedding ─────────────────────────────────────────────────

    async def generate_embeddings_for_company(
        self,
        company_id: _uuid.UUID,
        *,
        force: bool = False,
    ) -> int:
        """Generate embeddings for all inventory records missing them.

        If force=True, regenerates all embeddings (not implemented in Phase 1;
        currently only fills missing).
        Returns count of embeddings generated.
        """
        from core.shared_tools.async_embedding_client import async_embed_texts

        pages = await self._repo.get_pages_missing_embeddings(
            company_id, limit=1000
        )

        if not pages:
            return 0

        # Build embedding texts
        texts: list[str] = []
        page_ids: list[_uuid.UUID] = []
        for page in pages:
            embed_text = _EMBED_TEMPLATE.format(
                title=page.title or "",
                h1_text=page.h1_text or "",
                meta_description=page.meta_description or "",
                content_preview=(page.content_preview or "")[:_EMBED_PREVIEW_LIMIT],
            )
            texts.append(embed_text)
            page_ids.append(page.id)

        # Batch embed
        embeddings = await async_embed_texts(texts)

        # Build update pairs
        updates: list[tuple[_uuid.UUID, list[float]]] = []
        for pid, emb in zip(page_ids, embeddings):
            if emb:
                updates.append((pid, emb))

        count = await self._repo.update_embeddings_batch(updates)

        _logger.info(
            "content_inventory.embeddings_generated",
            extra={"company_id": str(company_id), "count": count},
        )
        return count

    # ── Similarity Queries (called by pipelines) ──────────────────

    async def check_cannibalization(
        self,
        company_id: _uuid.UUID,
        topic_text: str,
        *,
        threshold: float = 0.82,
    ) -> list[CannibalizationMatch]:
        """Check if a topic assignment overlaps with existing content.

        Returns list of matches with similarity scores and URLs.
        """
        from core.shared_tools.async_embedding_client import async_embed_texts

        embeddings = await async_embed_texts([topic_text])
        if not embeddings or not embeddings[0]:
            return []

        similar = await self._repo.find_similar(
            company_id, embeddings[0], threshold=threshold
        )

        return [
            CannibalizationMatch(
                inventory_id=str(model.id),
                url=model.url,
                title=model.title or "",
                similarity=sim,
                word_count=model.word_count or 0,
                content_preview=model.content_preview or "",
                content_type_detected=model.content_type_detected or "",
            )
            for model, sim in similar
        ]

    async def check_cannibalization_batch(
        self,
        company_id: _uuid.UUID,
        topics: list[str],
        *,
        threshold: float = 0.82,
    ) -> dict[str, list[CannibalizationMatch]]:
        """Batch cannibalization check for multiple topics.

        Embeds all topics in one call, then runs pgvector similarity.
        """
        if not topics:
            return {}

        from core.shared_tools.async_embedding_client import async_embed_texts

        embeddings = await async_embed_texts(topics)

        result: dict[str, list[CannibalizationMatch]] = {}
        for topic, emb in zip(topics, embeddings):
            if not emb:
                result[topic] = []
                continue

            similar = await self._repo.find_similar(
                company_id, emb, threshold=threshold
            )
            result[topic] = [
                CannibalizationMatch(
                    inventory_id=str(model.id),
                    url=model.url,
                    title=model.title or "",
                    similarity=sim,
                    word_count=model.word_count or 0,
                    content_preview=model.content_preview or "",
                    content_type_detected=model.content_type_detected or "",
                )
                for model, sim in similar
            ]

        return result

    async def find_existing_coverage(
        self,
        company_id: _uuid.UUID,
        query_text: str,
        *,
        threshold: float = 0.78,
        limit: int = 3,
    ) -> list[ExistingCoverageResult]:
        """Find existing content that covers a given query/topic.

        Used by Gap Analysis S2 to decide "optimize" vs "create".
        Used by Content Engine to inject existing content context into briefs.
        """
        from core.shared_tools.async_embedding_client import async_embed_texts

        embeddings = await async_embed_texts([query_text])
        if not embeddings or not embeddings[0]:
            return []

        similar = await self._repo.find_similar(
            company_id, embeddings[0], threshold=threshold, limit=limit
        )

        return [
            ExistingCoverageResult(
                inventory_id=str(model.id),
                url=model.url,
                title=model.title or "",
                similarity=sim,
                word_count=model.word_count or 0,
                content_preview=model.content_preview or "",
                categories=model.categories or [],
                content_modified_at=(
                    model.content_modified_at.isoformat()
                    if model.content_modified_at
                    else None
                ),
            )
            for model, sim in similar
        ]


def _classify_content_type(url: str) -> str:
    """Heuristic content type classification from URL patterns."""
    url_lower = url.lower()
    if "/blog/" in url_lower or "/posts/" in url_lower or "/article/" in url_lower:
        return "blog_post"
    if "/docs/" in url_lower or "/documentation/" in url_lower or "/help/" in url_lower:
        return "docs"
    if "/glossary/" in url_lower or "/terms/" in url_lower:
        return "glossary"
    if "/case-study/" in url_lower or "/case-studies/" in url_lower:
        return "case_study"
    if "/pricing" in url_lower:
        return "landing_page"
    if "/about" in url_lower or "/team" in url_lower:
        return "landing_page"
    return ""
