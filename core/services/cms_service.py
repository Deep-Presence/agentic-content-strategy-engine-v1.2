"""CMS service — orchestrates connection management, sync, and publish flows.

This is the layer that API routers call.  It coordinates between the adapter
(CMS API calls), the database (persistence), and the Content Engine artifacts
(reading final.md for publish).

NOT a Protocol → JsonService → DbService pattern — this is a standalone
orchestrator (similar to DailyTrackerOrchestrator) that coordinates between
the CMS adapter, database repositories, and StorageBackend.
"""
from __future__ import annotations

import asyncio
import html as html_mod
import inspect
import json
import logging
import re
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from core.cms.adapters.webflow.adapter import WebflowAdapter
from core.cms.adapters.webflow.field_mapper import suggest_field_mapping
from core.cms.exceptions import CMSError
from core.cms.webflow_models import WebflowProviderConfig
from core.cms.factory import create_cms_adapter
from core.cms.models import (
    CMSConnectionConfig,
    CMSPost,
    CMSPostCreate,
    CMSPostUpdate,
    CMSPublishMetadata,
)
from core.cms.protocols import CMSAdapterProtocol
from core.db.enums import CMSPostStatus, CMSProvider, CMSPublishAction
from core.db.models.cms import CMSConnectionModel
from core.db.repositories.cms_repo import (
    CMSConnectionRepository,
    CMSPublishRecordRepository,
    CMSSyncedPostRepository,
)
from core.db.repositories.company_repo import CompanyRepository
from core.db.repositories.content_repo import ContentRepository
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)

STALE_THRESHOLD_DAYS = 30


class CMSService:
    """High-level CMS operations.

    Responsibilities:
    1. Connection lifecycle: connect, validate, store credentials
    2. Sync: pull existing posts into local index
    3. Publish: take a Content Engine brief and push to CMS
    4. Refresh: update an existing CMS post with new content
    """

    def __init__(
        self,
        *,
        connection_repo: CMSConnectionRepository,
        publish_repo: CMSPublishRecordRepository,
        synced_post_repo: CMSSyncedPostRepository,
        storage: StorageBackend,
        fernet_key: str,
        content_repo: ContentRepository | None = None,
        inventory_service: Any | None = None,
        company_repo: CompanyRepository | None = None,
        content_to_prompt_orchestrator: Any | None = None,
    ) -> None:
        self._connection_repo = connection_repo
        self._publish_repo = publish_repo
        self._synced_post_repo = synced_post_repo
        self._storage = storage
        self._fernet_key = fernet_key
        self._content_repo = content_repo
        self._inventory_service = inventory_service
        self._company_repo = company_repo
        self._content_to_prompt_orchestrator = content_to_prompt_orchestrator

    # ── Connect Flow ──────────────────────────────────────────────

    async def connect(
        self,
        company_id: str | _uuid.UUID,
        company_slug: str,
        tenant_id: str,
        provider: str,
        site_url: str,
        username: str,
        api_key: str,
        provider_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate credentials, encrypt, and persist the connection.

        Returns the CMSConnectionStatus dict.
        """
        cms_provider = CMSProvider(provider)
        resolved_config: dict[str, Any] = dict(provider_config or {})
        config = CMSConnectionConfig(
            provider=cms_provider,
            site_url=site_url,
            username=username,
            api_key=api_key,
            provider_config=resolved_config,
        )
        adapter = create_cms_adapter(config)
        status = await adapter.validate_connection()

        if not status.connected:
            return status.model_dump(mode="json")

        if cms_provider == CMSProvider.webflow:
            export = getattr(adapter, "export_provider_config", None)
            if callable(export):
                exported = export()
                if inspect.isawaitable(exported):
                    exported = await exported
                if isinstance(exported, dict):
                    resolved_config = exported

        encrypted = self._encrypt_credentials(
            username,
            api_key,
            provider=cms_provider,
        )

        # Upsert connection: update existing row in-place (preserves FK
        # references from publish_records and synced_posts) or create new.
        # Codex F8: deactivate+insert violates unique (company_id, tenant_id).
        existing = await self._connection_repo.get_by_company_slug(
            company_slug, tenant_id
        )
        if existing:
            existing.provider = cms_provider
            existing.site_url = site_url
            existing.encrypted_credentials = encrypted
            existing.provider_config = resolved_config or None
            existing.site_name = status.site_name
            existing.cms_version = status.cms_version
            existing.user_display_name = status.user_display_name
            existing.is_active = True
            existing.last_validated_at = datetime.now(timezone.utc)
            await self._connection_repo._session.flush()
        else:
            cid = (
                _uuid.UUID(str(company_id))
                if isinstance(company_id, str)
                else company_id
            )
            await self._connection_repo.create(
                company_id=cid,
                tenant_id=tenant_id,
                company_slug=company_slug,
                provider=cms_provider,
                site_url=site_url,
                encrypted_credentials=encrypted,
                provider_config=resolved_config or None,
                site_name=status.site_name,
                cms_version=status.cms_version,
                user_display_name=status.user_display_name,
                last_validated_at=datetime.now(timezone.utc),
            )

        return status.model_dump(mode="json")

    # ── Connection Info ───────────────────────────────────────────

    async def get_connection(
        self,
        company_slug: str,
        tenant_id: str,
    ) -> CMSConnectionModel | None:
        """Return the active CMS connection for a company, or None."""
        return await self._connection_repo.get_by_company_slug(
            company_slug, tenant_id
        )

    async def disconnect(
        self,
        company_slug: str,
        tenant_id: str,
    ) -> bool:
        """Soft-deactivate the CMS connection. Returns True if one existed."""
        conn = await self._connection_repo.get_by_company_slug(
            company_slug, tenant_id
        )
        if not conn:
            return False
        return await self._connection_repo.deactivate(conn.id)

    # ── Webflow configure (WF-2) ──────────────────────────────────

    def _require_webflow_adapter(
        self, connection: CMSConnectionModel
    ) -> WebflowAdapter:
        """Return a Webflow adapter for an active Webflow connection."""
        if CMSProvider(connection.provider.value) != CMSProvider.webflow:
            raise ValueError("CMS connection is not Webflow")
        adapter = self._reconstruct_adapter(connection)
        if not isinstance(adapter, WebflowAdapter):
            raise ValueError("Expected Webflow adapter for Webflow connection")
        return adapter

    async def list_webflow_collections(
        self,
        connection: CMSConnectionModel,
    ) -> list[dict[str, Any]]:
        """List CMS collections on the connected Webflow site."""
        adapter = self._require_webflow_adapter(connection)
        raw_collections = await adapter.list_collections_for_site()
        summaries: list[dict[str, Any]] = []
        for coll in raw_collections:
            if not isinstance(coll, dict):
                continue
            summaries.append(
                {
                    "collection_id": str(coll.get("id") or ""),
                    "collection_slug": str(coll.get("slug") or ""),
                    "display_name": str(
                        coll.get("displayName") or coll.get("slug") or ""
                    ),
                    "singular_name": str(coll.get("singularName") or ""),
                }
            )
        return summaries

    async def get_webflow_collection_fields(
        self,
        connection: CMSConnectionModel,
        collection_id: str,
    ) -> dict[str, Any]:
        """Return collection schema fields and a heuristic field mapping."""
        adapter = self._require_webflow_adapter(connection)
        schema = await adapter.get_collection_schema(collection_id)
        raw_fields = schema.get("fields") or []
        fields: list[dict[str, Any]] = []
        field_dicts: list[dict[str, Any]] = []
        for field in raw_fields:
            if not isinstance(field, dict):
                continue
            field_dicts.append(field)
            fields.append(
                {
                    "slug": str(field.get("slug") or ""),
                    "display_name": str(field.get("displayName") or ""),
                    "field_type": str(field.get("type") or ""),
                    "is_required": bool(field.get("isRequired", False)),
                }
            )
        suggested = suggest_field_mapping(field_dicts)
        return {
            "collection_id": collection_id,
            "fields": fields,
            "suggested_mapping": suggested.model_dump(mode="json"),
        }

    async def configure_webflow(
        self,
        company_slug: str,
        tenant_id: str,
        connection: CMSConnectionModel,
        *,
        configure_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate and persist Webflow ``provider_config`` on the connection."""
        existing = WebflowProviderConfig.from_provider_config(
            connection.provider_config
        )
        merged: dict[str, Any] = {
            **existing.to_provider_config(),
            **configure_payload,
        }
        if not merged.get("site_id") and existing.site_id:
            merged["site_id"] = existing.site_id

        validated = WebflowProviderConfig.model_validate(merged)
        if not validated.enabled_collections():
            raise ValueError("At least one enabled Webflow collection is required")

        adapter = self._require_webflow_adapter(connection)
        for coll in validated.enabled_collections():
            if not coll.field_mapping.body_field:
                raise ValueError(
                    f"Collection {coll.display_name or coll.collection_id} "
                    "requires a body_field mapping"
                )
            await adapter.get_collection_schema(coll.collection_id)

        provider_config = validated.to_provider_config()
        if validated.site_id and not provider_config.get("site_id"):
            provider_config["site_id"] = validated.site_id

        connection.provider_config = provider_config
        connection.last_validated_at = datetime.now(timezone.utc)
        await self._connection_repo._session.flush()

        return {
            "configured": True,
            "provider_config": provider_config,
        }

    async def update_provider_config(
        self,
        company_slug: str,
        tenant_id: str,
        provider_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge and persist provider_config for the active CMS connection."""
        conn = await self.get_connection(company_slug, tenant_id)
        if conn is None:
            raise CMSError("No active CMS connection for this company")

        if CMSProvider(conn.provider.value) == CMSProvider.webflow:
            return await self.configure_webflow(
                company_slug,
                tenant_id,
                conn,
                configure_payload=provider_config,
            )

        merged = {**(conn.provider_config or {}), **provider_config}
        conn.provider_config = merged
        await self._connection_repo._session.flush()
        return {"configured": True, "provider_config": merged}

    # ── Sync Flow ─────────────────────────────────────────────────

    async def sync_existing_content(
        self,
        company_slug: str,
        connection: CMSConnectionModel,
    ) -> dict[str, Any]:
        """Pull all published posts from CMS and upsert into synced_posts.

        Returns: ``{"synced": int, "stale": int, "categories": int}``
        """
        adapter = self._reconstruct_adapter(connection)
        all_posts, truncated = await adapter.list_all_posts(status="publish")
        categories = await adapter.list_categories()
        cat_map = {c.cms_id: c.name for c in categories}

        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(days=STALE_THRESHOLD_DAYS)
        stale_count = 0

        for post in all_posts:
            # Ensure timezone-aware comparison (CMS may return naive datetimes)
            mod_at = post.modified_at
            if mod_at is not None and mod_at.tzinfo is None:
                mod_at = mod_at.replace(tzinfo=timezone.utc)
            is_stale = (
                mod_at is not None and mod_at < stale_threshold
            )
            staleness_days = (
                (now - mod_at).days if mod_at else 0
            )
            if is_stale:
                stale_count += 1

            # Resolve category IDs to names
            cat_names = [
                cat_map.get(cid, f"unknown-{cid}") for cid in post.categories
            ]

            # Sanitize content_preview: strip HTML tags, first 500 chars
            preview = re.sub(r"<[^>]+>", "", post.content_html)[:500]

            await self._synced_post_repo.upsert_from_cms(
                connection_id=connection.id,
                company_slug=company_slug,
                cms_post_id=post.cms_id,
                title=post.title,
                slug=post.slug,
                url=post.url,
                excerpt=re.sub(r"<[^>]+>", "", post.excerpt)[:500],
                content_preview=preview,
                word_count=post.word_count,
                published_at=post.published_at,
                modified_at=post.modified_at,
                categories=cat_names,
                tags=post.tags,
                seo_title=post.seo_title,
                seo_description=post.seo_description,
                is_stale=is_stale,
                staleness_days=staleness_days,
            )

        # Hydrate content inventory (non-blocking, savepoint-isolated)
        new_page_ids: list[str] = []
        if self._inventory_service is not None:
            try:
                # Use a nested savepoint so DB errors don't poison the session
                async with self._synced_post_repo._session.begin_nested():
                    pairs, _new_ids = await self._inventory_service.ingest_from_cms_sync(
                        company_id=connection.company_id,
                        effective_slug=company_slug,
                        cms_posts=all_posts,
                    )
                    new_page_ids = [str(pid) for pid in _new_ids]
                    if pairs:
                        await self._synced_post_repo.batch_link_inventory_ids(
                            connection_id=connection.id,
                            pairs=pairs,
                        )
            except Exception:
                logger.warning(
                    "content_inventory.cms_sync_failed",
                    exc_info=True,
                )

        # Update connection sync metadata
        await self._connection_repo.update_sync_metadata(
            connection.id,
            last_sync_at=now,
            sync_post_count=len(all_posts),
        )

        return {
            "synced": len(all_posts),
            "stale": stale_count,
            "categories": len(categories),
            "truncated": truncated,
            "new_page_ids": new_page_ids,
        }

    # ── Publish Flow ──────────────────────────────────────────────

    async def publish_brief(
        self,
        company_slug: str,
        brief_id: str,
        connection: CMSConnectionModel,
        *,
        effective_slug: str,
        target_status: str = "draft",
        category_names: list[str] | None = None,
        slug_override: str | None = None,
        publish_metadata: CMSPublishMetadata | None = None,
        collection_id: str | None = None,
    ) -> CMSPost:
        """Read final.md from StorageBackend, convert to HTML, publish to CMS.

        Storage path: ``content/{effective_slug}/content/{brief_id}/final.md``
        """
        storage_path = (
            f"content/{effective_slug}/content/{brief_id}/final.md"
        )
        final_md = await asyncio.to_thread(self._storage.read, storage_path)
        if final_md is None:
            raise CMSError(
                f"No final.md found for brief {brief_id} at {storage_path}"
            )

        title = self._extract_title(final_md)
        normalized_publish_metadata = self._normalize_publish_metadata(
            publish_metadata,
            title=title,
        )
        requested_publish_at = self._parse_publish_date(
            normalized_publish_metadata.publish_date,
        )
        slug = (
            slug_override
            or normalized_publish_metadata.slug
            or self._generate_slug(title)
        )
        content_html = self._markdown_to_html(final_md)

        adapter = self._reconstruct_adapter(connection)
        post_create = CMSPostCreate(
            title=title,
            slug=slug,
            content_html=content_html,
            excerpt=normalized_publish_metadata.meta_description,
            status=CMSPostStatus(target_status),
            categories=category_names or [],
            tags=normalized_publish_metadata.tags,
            seo_title=normalized_publish_metadata.meta_title,
            seo_description=normalized_publish_metadata.meta_description,
            canonical_url=normalized_publish_metadata.canonical_url,
            published_at=requested_publish_at,
            author=normalized_publish_metadata.author,
            schema_markup=normalized_publish_metadata.schema_markup,
            collection_id=collection_id or "",
        )
        published_post = await adapter.publish_post(post_create)
        effective_published_at = (
            published_post.published_at
            or requested_publish_at
            or datetime.now(timezone.utc)
        )

        # Invalidate categories cache if publish may have created new categories
        if category_names:
            from core.services.cms_cache import invalidate_categories

            await asyncio.to_thread(invalidate_categories, connection.site_url)

        # Record in publish_records
        await self._publish_repo.create(
            connection_id=connection.id,
            company_slug=company_slug,
            brief_id=brief_id,
            effective_slug=effective_slug,
            cms_post_id=published_post.cms_id,
            cms_post_url=published_post.url,
            cms_post_slug=published_post.slug,
            action=CMSPublishAction.create,
            status_at_publish=CMSPostStatus(target_status),
            title_published=title,
            word_count=published_post.word_count,
        )

        # Persist publish metadata on the content piece (Kanban badge)
        if self._content_repo is not None:
            from core.db.enums import ContentPieceStatus

            piece = await self._content_repo.get_by_slug_and_brief_id(
                effective_slug, brief_id,
            )
            if piece:
                merged_results = dict(piece.evaluation_results or {})
                merged_results["publish_metadata"] = normalized_publish_metadata.model_dump(mode="json")
                await self._content_repo.update(
                    piece.id,
                    published_url=published_post.url,
                    published_at=effective_published_at,
                    status=ContentPieceStatus.published,
                    evaluation_results=merged_results,
                )

        inventory_item = None
        if self._inventory_service is not None and connection.company_id:
            try:
                inventory_item = await self._inventory_service.register_published_content(
                    company_id=connection.company_id,
                    effective_slug=effective_slug,
                    url=published_post.url,
                    title=title,
                    word_count=published_post.word_count,
                    content_text=final_md,
                    content_html=content_html,
                    published_at=effective_published_at,
                    h1_text=title,
                    meta_description=normalized_publish_metadata.meta_description,
                    categories=category_names or [],
                    tags=normalized_publish_metadata.tags,
                    seo_title=normalized_publish_metadata.meta_title,
                    seo_description=normalized_publish_metadata.meta_description,
                    has_schema_markup=normalized_publish_metadata.schema_markup,
                )
            except Exception:
                logger.warning(
                    "content_inventory.publish_register_failed",
                    exc_info=True,
                )

        if inventory_item is not None and connection.company_id:
            try:
                await self._auto_generate_prompts_for_published_page(
                    company_slug=company_slug,
                    company_uuid=connection.company_id,
                    inventory_id=inventory_item.id,
                )
            except Exception:
                logger.warning(
                    "cms.publish_auto_prompt_failed",
                    extra={
                        "company_slug": company_slug,
                        "inventory_id": str(inventory_item.id),
                    },
                    exc_info=True,
                )

        return published_post

    # ── Content Refresh Flow ──────────────────────────────────────

    async def refresh_post(
        self,
        company_slug: str,
        cms_post_id: str,
        brief_id: str,
        connection: CMSConnectionModel,
        *,
        effective_slug: str,
    ) -> CMSPost:
        """Update an existing CMS post with refreshed content."""
        storage_path = (
            f"content/{effective_slug}/content/{brief_id}/final.md"
        )
        final_md = await asyncio.to_thread(self._storage.read, storage_path)
        if final_md is None:
            raise CMSError(
                f"No final.md for refresh brief {brief_id} at {storage_path}"
            )

        content_html = self._markdown_to_html(final_md)
        title = self._extract_title(final_md)

        adapter = self._reconstruct_adapter(connection)
        updates = CMSPostUpdate(title=title, content_html=content_html)
        updated_post = await adapter.update_post(cms_post_id, updates)

        # Record in publish_records
        await self._publish_repo.create(
            connection_id=connection.id,
            company_slug=company_slug,
            brief_id=brief_id,
            effective_slug=effective_slug,
            cms_post_id=cms_post_id,
            cms_post_url=updated_post.url,
            cms_post_slug=updated_post.slug,
            action=CMSPublishAction.refresh,
            title_published=title,
            word_count=updated_post.word_count,
        )

        # Persist publish metadata on the content piece (Kanban badge)
        if self._content_repo is not None:
            from core.db.enums import ContentPieceStatus

            piece = await self._content_repo.get_by_slug_and_brief_id(
                effective_slug, brief_id,
            )
            if piece:
                await self._content_repo.update(
                    piece.id,
                    published_url=updated_post.url,
                    published_at=datetime.now(timezone.utc),
                    status=ContentPieceStatus.published,
                )

        return updated_post

    # ── Stale Content → Recommended Actions ───────────────────────

    async def get_stale_actions(
        self,
        company_slug: str,
    ) -> list[dict[str, Any]]:
        """Return stale posts as action cards for the Home dashboard.

        Caches the result in Redis (TTL 30min).
        """
        from core.services.cms_cache import get_cached_stale_actions, set_cached_stale_actions

        cached = await asyncio.to_thread(get_cached_stale_actions, company_slug)
        if cached is not None:
            return cached

        stale_posts = await self._synced_post_repo.get_stale(company_slug)
        actions: list[dict[str, Any]] = []
        for post in stale_posts:
            actions.append({
                "cms_synced_post_id": str(post.id),
                "cms_post_id": post.cms_post_id,
                "title": post.title,
                "url": post.url,
                "staleness_days": post.staleness_days,
                "description": (
                    f"Last updated {post.staleness_days} days ago. "
                    "Refreshing this content improves LLM presence "
                    "and bot crawlability."
                ),
                "queued_for_refresh": post.queued_for_refresh,
            })

        await asyncio.to_thread(set_cached_stale_actions, company_slug, actions)
        return actions

    async def queue_stale_for_refresh(
        self,
        company_slug: str,
        cms_synced_post_id: str,
    ) -> dict[str, Any]:
        """Mark a stale post as queued for content refresh and create a Triage tile.

        Creates a ``ContentPieceModel`` row with status=planned so the brief
        appears in the Content Studio Kanban Triage column.  Does NOT trigger
        any content-engine pipeline run.

        Returns ``{brief_id, title, status: "triage"}``.
        """
        from core.db.enums import ContentPieceStatus

        post = await self._synced_post_repo.get_by_id(cms_synced_post_id)
        if post is None or post.company_slug != company_slug:
            # Codex F2: verify tenant isolation — same error for not-found
            # and wrong-tenant to avoid information leakage.
            raise CMSError(f"Synced post {cms_synced_post_id} not found")

        brief_id = f"refresh-{_uuid.uuid4().hex[:8]}"
        await self._synced_post_repo.mark_queued_for_refresh(
            post.id, brief_id
        )

        # Create a Triage tile in Content Studio (DB row only, no pipeline)
        tile_created = True
        if self._content_repo is not None:
            try:
                await self._content_repo.create_piece(
                    effective_slug=company_slug,
                    brief_id=brief_id,
                    title=post.title or "",
                    cluster_name="",
                    content_type="long_blog",
                    status=ContentPieceStatus.planned,
                    word_count=0,
                )
            except Exception:
                tile_created = False
                logger.warning(
                    "queue_stale_for_refresh: failed to create triage tile "
                    "for %s/%s — queued in CMS but no Kanban tile",
                    company_slug, brief_id, exc_info=True,
                )

        return {
            "brief_id": brief_id,
            "title": post.title,
            "status": "triage",
            "warning": "" if tile_created else "Queued but triage tile could not be created",
        }

    # ── Read-Only Passthroughs (for API router) ────────────────────

    async def list_synced_posts(
        self,
        company_slug: str,
        *,
        stale_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        """Return synced posts for a company.

        Caches the result in Redis (TTL 10min), keyed by query params.
        """
        from core.services.cms_cache import (
            deserialize_synced_post,
            get_cached_synced_posts,
            serialize_synced_post,
            set_cached_synced_posts,
        )

        cached = await asyncio.to_thread(
            get_cached_synced_posts, company_slug, stale_only, limit, offset
        )
        if cached is not None:
            return [deserialize_synced_post(p) for p in cached]

        posts = list(
            await self._synced_post_repo.list_by_company(
                company_slug,
                stale_only=stale_only,
                limit=limit,
                offset=offset,
            )
        )

        serialized = [serialize_synced_post(p) for p in posts]
        await asyncio.to_thread(
            set_cached_synced_posts, company_slug, stale_only, limit, offset, serialized
        )
        return posts

    async def list_publish_history(
        self,
        company_slug: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list:
        """Return publish/refresh records for a company."""
        return list(
            await self._publish_repo.list_by_company(
                company_slug, limit=limit, offset=offset
            )
        )

    async def list_categories(
        self,
        connection: CMSConnectionModel,
    ) -> list:
        """Fetch categories from the connected CMS (Codex F4).

        Caches the result in Redis (TTL 1h) keyed by site_url.
        """
        from core.services.cms_cache import get_cached_categories, set_cached_categories

        cached = await asyncio.to_thread(get_cached_categories, connection.site_url)
        if cached is not None:
            from core.cms.models import CMSCategory

            return [CMSCategory(**c) for c in cached]

        adapter = self._reconstruct_adapter(connection)
        categories = await adapter.list_categories()

        serialized = [c.model_dump(mode="json") for c in categories]
        await asyncio.to_thread(set_cached_categories, connection.site_url, serialized)
        return categories

    # ── Private Helpers ───────────────────────────────────────────

    def _encrypt_credentials(
        self,
        username: str,
        api_key: str,
        *,
        provider: CMSProvider = CMSProvider.wordpress,
    ) -> str:
        """Encrypt CMS credentials using Fernet symmetric encryption."""
        from cryptography.fernet import Fernet

        from core.cms.adapters.webflow.auth import build_webflow_site_token_payload

        if provider == CMSProvider.webflow:
            payload: dict[str, Any] = build_webflow_site_token_payload(api_key=api_key)
        else:
            payload = {
                "username": username,
                "api_key": api_key,
                "auth_type": "application_password",
            }
        return Fernet(self._fernet_key.encode()).encrypt(
            json.dumps(payload).encode()
        ).decode()

    def _decrypt_credential_payload(self, encrypted: str) -> dict[str, Any]:
        """Decrypt CMS credential envelope."""
        from cryptography.fernet import Fernet

        decrypted = Fernet(self._fernet_key.encode()).decrypt(encrypted.encode())
        data = json.loads(decrypted)
        return data if isinstance(data, dict) else {}

    def _decrypt_credentials(self, encrypted: str) -> tuple[str, str]:
        """Decrypt CMS credentials. Returns ``(username, api_key)``."""
        data = self._decrypt_credential_payload(encrypted)
        username = str(data.get("username", ""))
        api_key = str(data.get("api_key", "") or data.get("access_token", ""))
        return username, api_key

    def _reconstruct_adapter(
        self, connection: CMSConnectionModel
    ) -> CMSAdapterProtocol:
        """Decrypt credentials and create a CMS adapter from a stored connection."""
        payload = self._decrypt_credential_payload(connection.encrypted_credentials)
        username = str(payload.get("username", ""))
        api_key = str(payload.get("api_key", "") or payload.get("access_token", ""))
        config = CMSConnectionConfig(
            provider=CMSProvider(connection.provider.value),
            site_url=connection.site_url,
            username=username,
            api_key=api_key,
            provider_config=connection.provider_config or {},
            extra={
                "auth_type": str(payload.get("auth_type", "")),
                "access_token": str(payload.get("access_token", "")),
            },
        )
        return create_cms_adapter(config)

    @staticmethod
    def _extract_title(markdown: str) -> str:
        """Extract the first H1 from markdown content."""
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                return stripped.lstrip("# ").strip()
        return "Untitled"

    @staticmethod
    def _generate_slug(title: str) -> str:
        """Generate a URL-safe slug from a title."""
        slug = title.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        slug = slug.strip("-")
        return slug[:200]

    @staticmethod
    def _normalize_publish_metadata(
        publish_metadata: CMSPublishMetadata | None,
        *,
        title: str,
    ) -> CMSPublishMetadata:
        if publish_metadata is None:
            return CMSPublishMetadata(
                slug=CMSService._generate_slug(title),
                meta_title=title,
            )
        return CMSPublishMetadata(
            slug=publish_metadata.slug or CMSService._generate_slug(title),
            meta_title=publish_metadata.meta_title or title,
            meta_description=publish_metadata.meta_description or "",
            canonical_url=publish_metadata.canonical_url or "",
            schema_markup=publish_metadata.schema_markup,
            publish_date=publish_metadata.publish_date or "",
            author=publish_metadata.author or "",
            tags=publish_metadata.tags or [],
        )

    @staticmethod
    def _parse_publish_date(publish_date: str) -> datetime | None:
        if not publish_date:
            return None
        try:
            return datetime.fromisoformat(f"{publish_date}T00:00:00+00:00")
        except ValueError:
            return None

    async def _auto_generate_prompts_for_published_page(
        self,
        *,
        company_slug: str,
        company_uuid: _uuid.UUID,
        inventory_id: _uuid.UUID,
    ) -> None:
        """Best-effort content-to-prompt generation for newly published pages."""
        if self._content_to_prompt_orchestrator is None:
            return

        brand_name = company_slug
        if self._company_repo is not None:
            company = await self._company_repo.get_by_slug(company_slug)
            resolved_name = getattr(company, "name", "") if company else ""
            if resolved_name:
                brand_name = resolved_name

        await self._content_to_prompt_orchestrator.run_for_pages(
            company_id=company_slug,
            company_uuid=company_uuid,
            page_ids=[inventory_id],
            brand_name=brand_name,
            k=6,
            auto_approve=True,
        )

    @staticmethod
    def _markdown_to_html(md_text: str) -> str:
        """Convert markdown to HTML for CMS publishing.

        Uses the ``markdown`` library with common extensions.
        """
        try:
            import markdown as md_lib

            return md_lib.markdown(
                md_text,
                extensions=["tables", "fenced_code", "toc", "attr_list"],
            )
        except ImportError:
            # Fallback: minimal conversion
            lines = md_text.splitlines()
            html_parts: list[str] = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("### "):
                    html_parts.append(
                        f"<h3>{html_mod.escape(stripped[4:])}</h3>"
                    )
                elif stripped.startswith("## "):
                    html_parts.append(
                        f"<h2>{html_mod.escape(stripped[3:])}</h2>"
                    )
                elif stripped.startswith("# "):
                    html_parts.append(
                        f"<h1>{html_mod.escape(stripped[2:])}</h1>"
                    )
                elif stripped:
                    html_parts.append(
                        f"<p>{html_mod.escape(stripped)}</p>"
                    )
            return "\n".join(html_parts)
