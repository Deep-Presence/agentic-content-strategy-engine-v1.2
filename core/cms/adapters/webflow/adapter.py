"""Webflow CMS adapter — Data API v2 (Site Token v1, OAuth-ready)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from core.cms.adapters.webflow.auth import resolve_webflow_access_token
from core.cms.adapters.webflow.client import WebflowClient, normalize_site_host
from core.cms.adapters.webflow.field_mapper import (
    build_field_data_for_create,
    build_field_data_for_update,
    parse_webflow_item,
)
from core.cms.exceptions import CMSAPIError, CMSNotFoundError
from core.cms.models import (
    CMSCategory,
    CMSConnectionConfig,
    CMSConnectionStatus,
    CMSMediaResult,
    CMSMediaUpload,
    CMSPost,
    CMSPostCreate,
    CMSPostStatus,
    CMSPostUpdate,
)
from core.cms.webflow_models import (
    WebflowCollectionConfig,
    WebflowProviderConfig,
    WebflowPublishMode,
)

logger = logging.getLogger(__name__)


class WebflowAdapter:
    """Concrete ``CMSAdapterProtocol`` implementation for Webflow CMS."""

    def __init__(
        self,
        config: CMSConnectionConfig,
        *,
        _transport: httpx.AsyncBaseTransport | None = None,
        _access_token: str | None = None,
    ) -> None:
        self.config = config
        self.base_url = str(config.site_url).rstrip("/")
        self._webflow_config = WebflowProviderConfig.from_provider_config(
            config.provider_config
        )
        token = _access_token or resolve_webflow_access_token(
            {
                "api_key": config.api_key,
                "access_token": config.extra.get("access_token", ""),
                "auth_type": config.extra.get("auth_type", ""),
            }
        )
        self._client = WebflowClient(token, transport=_transport)
        self._transport = _transport
        self._site_domains: list[str] = []

    # ── Connection ────────────────────────────────────────────────

    async def validate_connection(self) -> CMSConnectionStatus:
        try:
            auth_info = await self._client.get_authorized_by()
        except Exception as exc:
            return CMSConnectionStatus(
                connected=False,
                error=str(exc),
            )

        site = await self._resolve_site()
        if site is None:
            return CMSConnectionStatus(
                connected=False,
                user_display_name=str(auth_info.get("email", "")),
                error=(
                    "Could not resolve Webflow site — set site_id in provider_config "
                    "or provide a matching site_url."
                ),
            )

        site_name = str(site.get("displayName") or site.get("shortName") or "")
        site_url = self._site_public_url(site)
        self._cache_site_domains(site)

        capabilities = ["cms:read", "cms:write"]
        if self._webflow_config.enabled_collections():
            capabilities.append("collections:configured")

        return CMSConnectionStatus(
            connected=True,
            site_name=site_name,
            site_url=site_url or self.base_url,
            cms_version="webflow-v2",
            user_display_name=str(auth_info.get("email", "")),
            capabilities=capabilities,
        )

    async def _resolve_site(self) -> dict[str, Any] | None:
        if self._webflow_config.site_id:
            try:
                return await self._client.get_site(self._webflow_config.site_id)
            except CMSNotFoundError:
                return None

        sites = await self._client.list_sites()
        if not sites:
            return None

        target_host = normalize_site_host(self.base_url) if self.base_url else ""
        if target_host:
            for site in sites:
                if self._site_matches_host(site, target_host):
                    self._webflow_config.site_id = str(site.get("id", ""))
                    return site

        if len(sites) == 1:
            site = sites[0]
            self._webflow_config.site_id = str(site.get("id", ""))
            return site

        return None

    def _site_matches_host(self, site: dict[str, Any], target_host: str) -> bool:
        for domain in self._extract_domains(site):
            if domain == target_host or domain.endswith(f".{target_host}"):
                return True
            if target_host.endswith(domain):
                return True
        custom = str(site.get("customDomains") or "")
        preview = str(site.get("previewUrl") or site.get("defaultDomain") or "")
        return target_host in custom or target_host in preview

    @staticmethod
    def _extract_domains(site: dict[str, Any]) -> list[str]:
        domains: list[str] = []
        for key in ("customDomains", "defaultDomain", "previewUrl"):
            raw = site.get(key)
            if isinstance(raw, list):
                for entry in raw:
                    if isinstance(entry, dict):
                        url = entry.get("url") or entry.get("hostname") or ""
                    else:
                        url = str(entry)
                    host = normalize_site_host(str(url))
                    if host:
                        domains.append(host)
            elif raw:
                host = normalize_site_host(str(raw))
                if host:
                    domains.append(host)
        return domains

    def _cache_site_domains(self, site: dict[str, Any]) -> None:
        self._site_domains = self._extract_domains(site)

    @staticmethod
    def _site_public_url(site: dict[str, Any]) -> str:
        for key in ("previewUrl", "defaultDomain"):
            raw = site.get(key)
            if raw:
                url = str(raw)
                if not url.startswith("http"):
                    return f"https://{url}"
                return url
        return ""

    def _build_item_url(
        self,
        collection: WebflowCollectionConfig,
        slug: str,
    ) -> str:
        if not slug:
            return ""
        base = self.base_url.rstrip("/")
        if not base and self._site_domains:
            base = f"https://{self._site_domains[0]}"
        if not base:
            return ""
        coll_slug = collection.collection_slug.strip("/")
        if coll_slug:
            return f"{base}/{coll_slug}/{slug}"
        return f"{base}/{slug}"

    # ── Read Operations ───────────────────────────────────────────

    async def list_posts(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        status: str = "publish",
        after: datetime | None = None,
        modified_after: datetime | None = None,
    ) -> tuple[list[CMSPost], int]:
        if status != "publish":
            return [], 0

        collections = self._webflow_config.enabled_collections()
        if not collections:
            return [], 0

        # Aggregate first enabled collection page slice for protocol compatibility.
        all_posts: list[CMSPost] = []
        for collection in collections:
            offset = max(0, (page - 1) * per_page)
            raw_items, total = await self._client.list_live_items(
                collection.collection_id,
                offset=offset,
                limit=per_page,
            )
            for raw in raw_items:
                slug = str((raw.get("fieldData") or {}).get(
                    collection.field_mapping.slug_field, ""
                ))
                post = parse_webflow_item(
                    raw,
                    collection=collection,
                    item_url=self._build_item_url(collection, slug),
                )
                if after and post.published_at and post.published_at < after:
                    continue
                if modified_after and post.modified_at and post.modified_at < modified_after:
                    continue
                all_posts.append(post)
            if all_posts:
                return all_posts[:per_page], total

        return all_posts, len(all_posts)

    async def list_all_posts(
        self, status: str = "publish"
    ) -> tuple[list[CMSPost], bool]:
        if status != "publish":
            return [], False

        collections = self._webflow_config.enabled_collections()
        if not collections:
            return [], False

        all_posts: list[CMSPost] = []
        truncated = False
        for collection in collections:
            raw_items, coll_truncated = await self._client.list_all_live_items(
                collection.collection_id
            )
            truncated = truncated or coll_truncated
            for raw in raw_items:
                slug = str((raw.get("fieldData") or {}).get(
                    collection.field_mapping.slug_field, ""
                ))
                all_posts.append(
                    parse_webflow_item(
                        raw,
                        collection=collection,
                        item_url=self._build_item_url(collection, slug),
                    )
                )
        return all_posts, truncated

    async def get_post(self, post_id: int | str) -> CMSPost:
        item_id = str(post_id)
        collection_id = await self._resolve_collection_for_item(item_id)
        collection = self._webflow_config.collection_by_id(collection_id)
        if collection is None:
            raise CMSNotFoundError(f"Collection {collection_id} not configured")

        raw = await self._client.get_live_item(collection_id, item_id)
        slug = str((raw.get("fieldData") or {}).get(
            collection.field_mapping.slug_field, ""
        ))
        return parse_webflow_item(
            raw,
            collection=collection,
            item_url=self._build_item_url(collection, slug),
        )

    async def _resolve_collection_for_item(self, item_id: str) -> str:
        """Resolve which enabled collection owns a Webflow item.

        Single-collection sites use that collection directly. Multi-collection
        sites probe each enabled collection until a live item is found.
        """
        enabled = self._webflow_config.enabled_collections()
        if not enabled:
            raise CMSNotFoundError(
                f"Webflow item {item_id} not found — no collections configured"
            )
        if len(enabled) == 1:
            return enabled[0].collection_id

        for collection in enabled:
            try:
                await self._client.get_live_item(collection.collection_id, item_id)
                return collection.collection_id
            except CMSNotFoundError:
                continue

        raise CMSNotFoundError(
            f"Webflow item {item_id} not found in configured collections"
        )

    async def list_categories(self) -> list[CMSCategory]:
        seen: dict[str, CMSCategory] = {}
        for collection in self._webflow_config.enabled_collections():
            field_slug = collection.field_mapping.category_field
            if not field_slug:
                continue
            try:
                schema = await self._client.get_collection(collection.collection_id)
            except CMSAPIError:
                continue
            for field in schema.get("fields") or []:
                if not isinstance(field, dict):
                    continue
                if str(field.get("slug")) != field_slug:
                    continue
                validations = field.get("validations") or {}
                options = validations.get("options") or []
                for opt in options:
                    if not isinstance(opt, dict):
                        continue
                    name = str(opt.get("name") or "")
                    if not name:
                        continue
                    key = name.lower()
                    if key not in seen:
                        seen[key] = CMSCategory(
                            cms_id=str(opt.get("id") or name),
                            name=name,
                            slug=str(opt.get("slug") or name.lower().replace(" ", "-")),
                        )
        return list(seen.values())

    # ── Write Operations ──────────────────────────────────────────

    async def publish_post(self, post: CMSPostCreate) -> CMSPost:
        collection_id = self._webflow_config.resolve_publish_collection_id(
            post.collection_id
        )
        collection = self._webflow_config.collection_by_id(collection_id)
        if collection is None or not collection_id:
            raise CMSAPIError(
                "No Webflow collection configured for publish — "
                "set provider_config.collections"
            )

        field_data = build_field_data_for_create(post, collection.field_mapping)
        is_draft = post.status != CMSPostStatus.publish

        if (
            self._webflow_config.publish_mode == WebflowPublishMode.staged_then_publish
            and not is_draft
        ):
            raw = await self._client.create_staged_item(
                collection_id,
                field_data,
                is_draft=False,
            )
            item_id = str(raw.get("id", ""))
            if item_id:
                await self._client.publish_items(collection_id, [item_id])
        elif is_draft:
            raw = await self._client.create_staged_item(
                collection_id,
                field_data,
                is_draft=True,
            )
        else:
            raw = await self._client.create_live_item(
                collection_id,
                field_data,
                is_draft=False,
            )

        slug = post.slug or str((raw.get("fieldData") or {}).get(
            collection.field_mapping.slug_field, ""
        ))
        return parse_webflow_item(
            raw,
            collection=collection,
            item_url=self._build_item_url(collection, slug),
        )

    async def update_post(
        self, post_id: int | str, updates: CMSPostUpdate
    ) -> CMSPost:
        item_id = str(post_id)
        collection_id = updates.collection_id or await self._resolve_collection_for_item(
            item_id
        )
        collection = self._webflow_config.collection_by_id(collection_id)
        if collection is None or not collection_id:
            raise CMSNotFoundError(
                f"Cannot update Webflow item {item_id}: collection not configured"
            )

        field_data = build_field_data_for_update(updates, collection.field_mapping)
        if not field_data:
            return await self.get_post(item_id)

        raw = await self._client.update_live_item(collection_id, item_id, field_data)
        slug = str((raw.get("fieldData") or {}).get(
            collection.field_mapping.slug_field, ""
        ))
        return parse_webflow_item(
            raw,
            collection=collection,
            item_url=self._build_item_url(collection, slug),
        )

    # ── Media Operations ──────────────────────────────────────────

    async def upload_media(self, media: CMSMediaUpload) -> CMSMediaResult:
        """Upload an image to the Webflow site asset library."""
        site_id = self._webflow_config.site_id
        if not site_id:
            site = await self._resolve_site()
            if site:
                site_id = str(site.get("id", ""))
        if not site_id:
            raise CMSAPIError(
                "Webflow site_id is required for media upload — configure site first"
            )
        if not media.content_bytes:
            raise CMSAPIError("Webflow media upload requires content_bytes")

        filename = media.filename or "upload.png"
        uploaded = await self._client.upload_asset_bytes(
            site_id,
            file_name=filename,
            content_bytes=media.content_bytes,
            mime_type=media.mime_type or "image/png",
        )
        return CMSMediaResult(
            cms_id=str(uploaded.get("id", "")),
            url=str(uploaded.get("url", "")),
            filename=filename,
        )

    # ── Webflow-specific helpers (used by WF-2 configure API) ─────

    async def list_collections_for_site(self) -> list[dict[str, Any]]:
        site_id = self._webflow_config.site_id
        if not site_id:
            site = await self._resolve_site()
            if site:
                site_id = str(site.get("id", ""))
        if not site_id:
            return []
        return await self._client.list_collections(site_id)

    async def get_collection_schema(self, collection_id: str) -> dict[str, Any]:
        return await self._client.get_collection(collection_id)

    def export_provider_config(self) -> dict[str, Any]:
        """Return provider_config dict including any runtime-resolved site_id."""
        return self._webflow_config.export_provider_config()
