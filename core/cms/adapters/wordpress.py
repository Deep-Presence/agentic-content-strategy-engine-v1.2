"""WordPress REST API adapter.

Auth: Application Passwords (WP 5.6+).
The user provides their site URL + username + an application password.
We base64-encode ``username:app_password`` and send as Basic Auth.

WordPress REST API base: ``{site_url}/wp-json/wp/v2/``

Key endpoints used:
  GET  /posts          — list/filter posts (paginated, 100/page max)
  GET  /posts/{id}     — single post
  POST /posts          — create post
  POST /posts/{id}     — update post
  GET  /categories     — list categories
  POST /media          — upload image

Response headers:
  X-WP-Total           — total items matching query
  X-WP-TotalPages      — total pages

SEO plugin support:
  Yoast: yoast_head_json field (via ?_fields=yoast_head_json)
"""
from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

import httpx

from core.cms.exceptions import (
    CMSAPIError,
    CMSAuthError,
    CMSConnectionError,
    CMSNotFoundError,
)
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


class WordPressAdapter:
    """Concrete ``CMSAdapterProtocol`` implementation for WordPress."""

    def __init__(
        self,
        config: CMSConnectionConfig,
        *,
        _transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.base_url = str(config.site_url).rstrip("/")
        self.api_base = f"{self.base_url}/wp-json/wp/v2"

        # Basic Auth header from Application Password
        credentials = f"{config.username}:{config.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self._headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "User-Agent": "DeepPresence/1.0",
        }
        self._transport = _transport

    def _client(self) -> httpx.AsyncClient:
        """Build an async HTTP client (context-manager usage)."""
        kwargs: dict[str, Any] = {
            "headers": self._headers,
            "timeout": 30.0,
            "follow_redirects": True,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    # ── Connection ────────────────────────────────────────────────

    async def validate_connection(self) -> CMSConnectionStatus:
        """Test credentials: GET /wp-json then GET /users/me."""
        async with self._client() as client:
            # 1. Check REST API is accessible
            try:
                resp = await client.get(f"{self.base_url}/wp-json")
                resp.raise_for_status()
                site_info = resp.json()
            except httpx.ConnectError as e:
                raise CMSConnectionError(
                    f"Cannot reach {self.base_url}: {e}"
                ) from e
            except httpx.TimeoutException as e:
                raise CMSConnectionError(
                    f"Timeout connecting to {self.base_url}: {e}"
                ) from e
            except httpx.HTTPStatusError:
                return CMSConnectionStatus(
                    connected=False,
                    error=f"Site not reachable or REST API disabled: {resp.status_code}",
                )

            # 2. Verify credentials via /users/me
            try:
                me_resp = await client.get(
                    f"{self.api_base}/users/me", params={"context": "edit"}
                )
                me_resp.raise_for_status()
                me = me_resp.json()
            except httpx.HTTPStatusError:
                return CMSConnectionStatus(
                    connected=False,
                    site_name=site_info.get("name", ""),
                    error="Invalid credentials — check username and application password.",
                )

            return CMSConnectionStatus(
                connected=True,
                site_name=site_info.get("name", ""),
                site_url=site_info.get("url", self.base_url),
                cms_version=site_info.get("description", ""),
                user_display_name=me.get("name", ""),
                capabilities=list(me.get("capabilities", {}).keys()),
            )

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
        """Paginated post listing with optional date filters."""
        params: dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 100),
            "status": status,
            "orderby": "modified",
            "order": "desc",
            "_fields": (
                "id,title,slug,content,excerpt,status,link,"
                "date,modified,author,categories,tags,"
                "featured_media,yoast_head_json"
            ),
        }
        if after:
            params["after"] = after.isoformat()
        if modified_after:
            params["modified_after"] = modified_after.isoformat()

        async with self._client() as client:
            resp = await client.get(f"{self.api_base}/posts", params=params)
            if resp.status_code == 400:
                raise CMSAPIError(f"Bad request: {resp.text}")
            resp.raise_for_status()

            total = int(resp.headers.get("X-WP-Total", 0))
            posts = [self._parse_post(p) for p in resp.json()]
            return posts, total

    async def list_all_posts(self, status: str = "publish") -> list[CMSPost]:
        """Paginate through ALL posts (used during initial sync)."""
        all_posts: list[CMSPost] = []
        page = 1
        while True:
            posts, total = await self.list_posts(
                page=page, per_page=100, status=status
            )
            all_posts.extend(posts)
            if len(all_posts) >= total or not posts:
                break
            page += 1
        return all_posts

    async def get_post(self, post_id: int | str) -> CMSPost:
        """Fetch a single post by CMS-native ID."""
        async with self._client() as client:
            resp = await client.get(f"{self.api_base}/posts/{post_id}")
            if resp.status_code == 404:
                raise CMSNotFoundError(f"Post {post_id} not found")
            resp.raise_for_status()
            return self._parse_post(resp.json())

    async def list_categories(self) -> list[CMSCategory]:
        """Return all categories (paginated, WP caps at 100/page)."""
        categories: list[CMSCategory] = []
        page = 1
        async with self._client() as client:
            while True:
                resp = await client.get(
                    f"{self.api_base}/categories",
                    params={"page": page, "per_page": 100},
                )
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                for c in batch:
                    categories.append(
                        CMSCategory(
                            cms_id=str(c["id"]),
                            name=c["name"],
                            slug=c["slug"],
                            parent_id=str(c["parent"]) if c.get("parent") else None,
                            post_count=c.get("count", 0),
                        )
                    )
                total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1
        return categories

    # ── Write Operations ──────────────────────────────────────────

    async def publish_post(self, post: CMSPostCreate) -> CMSPost:
        """Create a new post on WordPress.

        Category resolution: names → WP category IDs (auto-creates missing).
        """
        category_ids = await self._resolve_category_ids(post.categories)

        payload: dict[str, Any] = {
            "title": post.title,
            "slug": post.slug,
            "content": post.content_html,
            "excerpt": post.excerpt,
            "status": post.status.value,
            "categories": category_ids,
            "tags": [],
        }
        if post.featured_image_id:
            payload["featured_media"] = int(post.featured_image_id)

        # Yoast SEO fields
        meta: dict[str, str] = {}
        if post.seo_title:
            meta["_yoast_wpseo_title"] = post.seo_title
        if post.seo_description:
            meta["_yoast_wpseo_metadesc"] = post.seo_description
        if meta:
            payload["meta"] = meta

        async with self._client() as client:
            resp = await client.post(f"{self.api_base}/posts", json=payload)
            if resp.status_code == 403:
                raise CMSAuthError("Insufficient permissions to create posts")
            resp.raise_for_status()
            return self._parse_post(resp.json())

    async def update_post(
        self, post_id: int | str, updates: CMSPostUpdate
    ) -> CMSPost:
        """Update an existing post. Only sends non-None fields."""
        payload: dict[str, Any] = {}
        if updates.title is not None:
            payload["title"] = updates.title
        if updates.content_html is not None:
            payload["content"] = updates.content_html
        if updates.excerpt is not None:
            payload["excerpt"] = updates.excerpt
        if updates.slug is not None:
            payload["slug"] = updates.slug

        meta: dict[str, str] = {}
        if updates.seo_title is not None:
            meta["_yoast_wpseo_title"] = updates.seo_title
        if updates.seo_description is not None:
            meta["_yoast_wpseo_metadesc"] = updates.seo_description
        if meta:
            payload["meta"] = meta

        if not payload:
            return await self.get_post(post_id)

        async with self._client() as client:
            resp = await client.post(
                f"{self.api_base}/posts/{post_id}", json=payload
            )
            if resp.status_code == 404:
                raise CMSNotFoundError(f"Post {post_id} not found")
            resp.raise_for_status()
            return self._parse_post(resp.json())

    # ── Media Operations ──────────────────────────────────────────

    async def upload_media(self, media: CMSMediaUpload) -> CMSMediaResult:
        """Upload an image to the WP media library."""
        headers = {**self._headers}
        headers["Content-Type"] = media.mime_type
        headers["Content-Disposition"] = (
            f'attachment; filename="{media.filename}"'
        )

        async with self._client() as client:
            resp = await client.post(
                f"{self.api_base}/media",
                content=media.content_bytes,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return CMSMediaResult(
                cms_id=str(data["id"]),
                url=data["source_url"],
                filename=media.filename,
            )

    # ── Internal Helpers ──────────────────────────────────────────

    def _parse_post(self, raw: dict[str, Any]) -> CMSPost:
        """Normalize a WP REST API post response into ``CMSPost``."""
        content_html = raw.get("content", {}).get("rendered", "")
        word_count = len(content_html.split()) if content_html else 0

        # Yoast SEO data if present
        yoast = raw.get("yoast_head_json", {}) or {}

        return CMSPost(
            cms_id=str(raw["id"]),
            title=raw.get("title", {}).get("rendered", ""),
            slug=raw.get("slug", ""),
            content_html=content_html,
            excerpt=raw.get("excerpt", {}).get("rendered", ""),
            status=CMSPostStatus(raw.get("status", "publish")),
            url=raw.get("link", ""),
            published_at=self._parse_dt(raw.get("date")),
            modified_at=self._parse_dt(raw.get("modified")),
            author=str(raw.get("author", "")),
            categories=[str(c) for c in raw.get("categories", [])],
            tags=[str(t) for t in raw.get("tags", [])],
            featured_image_url="",
            seo_title=yoast.get("title", ""),
            seo_description=yoast.get("og_description", ""),
            word_count=word_count,
            raw_metadata=raw,
        )

    def _parse_dt(self, dt_str: str | None) -> datetime | None:
        """Parse ISO 8601 datetime string, return None on failure."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None

    async def _resolve_category_ids(
        self, category_names: list[str]
    ) -> list[int]:
        """Map category names → WP category IDs. Create missing categories."""
        if not category_names:
            return []

        existing = await self.list_categories()
        name_to_id = {c.name.lower(): int(c.cms_id) for c in existing}

        ids: list[int] = []
        for name in category_names:
            if name.lower() in name_to_id:
                ids.append(name_to_id[name.lower()])
            else:
                async with self._client() as client:
                    resp = await client.post(
                        f"{self.api_base}/categories",
                        json={"name": name},
                    )
                    resp.raise_for_status()
                    new_id = resp.json()["id"]
                    ids.append(new_id)
                    name_to_id[name.lower()] = new_id
        return ids
