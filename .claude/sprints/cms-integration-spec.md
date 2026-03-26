# CMS Integration Architecture — Deep Presence

> **Module:** `core/cms/` (business logic) + `api/routers/cms.py` (API layer)
> **Purpose:** Read existing blog content from client CMS, publish new/refreshed content from Content Engine v1.3
> **Priority:** Demo-critical — closes the value loop from intelligence → content → publish
> **v1 Target CMS:** WordPress (via REST API + Application Passwords)

---

## 1. Design Principles

1. **Adapter pattern with Protocol contract** — follows existing `GapDataServiceProtocol` / `SiteAuditDataServiceProtocol` conventions. Every CMS is a concrete implementation of a single `CMSAdapterProtocol`. Adding Webflow or Strapi means adding one file, not changing any existing code.

2. **Read-first, write-second** — before publishing anything, Deep Presence must know what already exists on the client's site. The `sync_existing_content()` flow runs at CMS connection time and populates a local index. This prevents keyword cannibalization and feeds staleness detection.

3. **Single credential, full lifecycle** — the same auth credentials that let us publish also let us read. No separate API keys for read vs. write. The user connects once.

4. **Slug ownership by Deep Presence** — when we publish, the slug is deterministic from the Content Engine's title/keyword context. The user previews and can override, but the default slug is AEO-optimized.

5. **No CMS vendor lock-in in the data model** — the `cms_connections` and `cms_publish_records` tables store CMS-agnostic metadata. The adapter type is a string enum column, not a foreign key to a CMS-specific table.

6. **Platform detects, user approves** — staleness is surfaced automatically via the Recommended Actions component on the Home dashboard. The user never manually browses synced posts hunting for stale content. Deep Presence flags it (threshold: 30 days since last modification), presents it with context, and the user's only action is clicking "Refresh Content" to queue it into the Content Studio pipeline.

7. **Topic Discovery untouched, architecture-ready** — the CMS sync populates `cms_synced_posts` with existing titles, keywords, and categories. This data is available for future Topic Discovery cross-referencing (de-prioritizing already-covered topics, flagging cannibalization risk), but that integration is deferred. The `detected_primary_keyword` and `cannibalization_risk` columns are the extension points.

---

## 2. Adapter Protocol & Interface

### 2.1 Protocol Definition

**File:** `core/cms/protocols.py`

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable
from datetime import datetime

from core.cms.models import (
    CMSConnectionConfig,
    CMSPost,
    CMSPostCreate,
    CMSPostUpdate,
    CMSCategory,
    CMSConnectionStatus,
    CMSMediaUpload,
    CMSMediaResult,
)


@runtime_checkable
class CMSAdapterProtocol(Protocol):
    """
    Contract every CMS adapter must satisfy.
    
    Lifecycle:
        1. __init__(config: CMSConnectionConfig)
        2. validate_connection() — test credentials, return site metadata
        3. Read ops: list_posts(), get_post(), list_categories()
        4. Write ops: publish_post(), update_post()
        5. Media ops: upload_media() (for featured images)
    """

    # ── Connection ────────────────────────────────────────────────

    async def validate_connection(self) -> CMSConnectionStatus:
        """
        Test credentials against the CMS API.
        Returns site metadata (site name, URL, WP version, etc.) on success.
        Raises CMSAuthError on failure.
        """
        ...

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
        """
        Paginated listing of existing posts.
        Returns (posts, total_count).
        
        The `after` param filters by publish date.
        The `modified_after` param filters by last-modified date (staleness detection).
        """
        ...

    async def get_post(self, post_id: int | str) -> CMSPost:
        """Fetch a single post by CMS-native ID."""
        ...

    async def list_categories(self) -> list[CMSCategory]:
        """Return all categories/taxonomies from the CMS."""
        ...

    # ── Write Operations ──────────────────────────────────────────

    async def publish_post(self, post: CMSPostCreate) -> CMSPost:
        """
        Create and publish a new post on the CMS.
        Returns the created post with its CMS-native ID and permalink.
        """
        ...

    async def update_post(self, post_id: int | str, updates: CMSPostUpdate) -> CMSPost:
        """
        Update an existing post (for content refresh flows).
        Only sends changed fields.
        """
        ...

    # ── Media Operations ──────────────────────────────────────────

    async def upload_media(self, media: CMSMediaUpload) -> CMSMediaResult:
        """
        Upload an image to the CMS media library.
        Returns the media ID and URL for use as featured_image in posts.
        """
        ...
```

### 2.2 Domain Models

**File:** `core/cms/models.py`

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


# ── Enums ─────────────────────────────────────────────────────────

class CMSProvider(str, Enum):
    """Supported CMS platforms."""
    WORDPRESS = "wordpress"
    WEBFLOW = "webflow"       # Future
    STRAPI = "strapi"         # Future
    GHOST = "ghost"           # Future
    HUBSPOT = "hubspot"       # Future


class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISH = "publish"
    PENDING = "pending"
    PRIVATE = "private"


# ── Connection ────────────────────────────────────────────────────

class CMSConnectionConfig(BaseModel):
    """
    Credentials for connecting to a CMS.
    Provider-agnostic — each adapter interprets the fields it needs.
    """
    provider: CMSProvider
    site_url: HttpUrl                         # e.g. https://blog.ramp.com
    api_key: str = ""                         # Application Password (WP), API key (Webflow)
    username: str = ""                        # WP username (not needed for all providers)
    extra: dict[str, Any] = Field(default_factory=dict)  # Provider-specific overrides


class CMSConnectionStatus(BaseModel):
    """Result of validate_connection()."""
    connected: bool
    site_name: str = ""
    site_url: str = ""
    cms_version: str = ""                     # e.g. "6.7.1"
    user_display_name: str = ""               # Who the credentials belong to
    capabilities: list[str] = Field(default_factory=list)  # ["publish_posts", "upload_files", ...]
    error: str | None = None


# ── Posts ─────────────────────────────────────────────────────────

class CMSPost(BaseModel):
    """
    Normalized representation of a CMS post.
    Every adapter maps its native format into this shape.
    """
    cms_id: str                               # Native CMS ID (string for cross-CMS compat)
    title: str
    slug: str
    content_html: str                         # Full HTML body
    excerpt: str = ""
    status: PostStatus = PostStatus.PUBLISH
    url: str = ""                             # Permalink
    published_at: datetime | None = None
    modified_at: datetime | None = None
    author: str = ""
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    featured_image_url: str = ""
    seo_title: str = ""                       # From Yoast/RankMath if available
    seo_description: str = ""
    word_count: int = 0
    raw_metadata: dict[str, Any] = Field(default_factory=dict)  # Full CMS response for debugging


class CMSPostCreate(BaseModel):
    """Payload for publishing a new post."""
    title: str
    slug: str
    content_html: str
    excerpt: str = ""
    status: PostStatus = PostStatus.DRAFT     # Default to draft — user explicitly publishes
    categories: list[str] = Field(default_factory=list)   # Category names (adapter resolves to IDs)
    tags: list[str] = Field(default_factory=list)
    featured_image_id: str | None = None      # CMS media ID from upload_media()
    seo_title: str = ""
    seo_description: str = ""


class CMSPostUpdate(BaseModel):
    """Payload for updating an existing post (content refresh)."""
    title: str | None = None
    content_html: str | None = None
    excerpt: str | None = None
    slug: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None


# ── Categories ────────────────────────────────────────────────────

class CMSCategory(BaseModel):
    cms_id: str
    name: str
    slug: str
    parent_id: str | None = None
    post_count: int = 0


# ── Media ─────────────────────────────────────────────────────────

class CMSMediaUpload(BaseModel):
    filename: str
    content_bytes: bytes
    mime_type: str = "image/png"
    alt_text: str = ""


class CMSMediaResult(BaseModel):
    cms_id: str
    url: str
    filename: str
```

---

## 3. WordPress Adapter (v1 Implementation)

**File:** `core/cms/adapters/wordpress.py`

```python
"""
WordPress REST API adapter.

Auth: Application Passwords (WP 5.6+).
The user provides their site URL + a username + an application password.
We base64-encode "username:app_password" and send as Basic Auth.

WordPress REST API base: {site_url}/wp-json/wp/v2/

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
  Yoast: _yoast_wpseo_title, _yoast_wpseo_metadesc (via ?_fields=yoast_head_json)
  RankMath: rank_math_title, rank_math_description (via custom fields)
"""

import base64
from datetime import datetime
from typing import Any

import httpx

from core.cms.models import (
    CMSCategory,
    CMSConnectionConfig,
    CMSConnectionStatus,
    CMSMediaResult,
    CMSMediaUpload,
    CMSPost,
    CMSPostCreate,
    CMSPostUpdate,
    PostStatus,
)
from core.cms.exceptions import CMSAuthError, CMSAPIError, CMSNotFoundError


class WordPressAdapter:
    """Concrete CMSAdapterProtocol implementation for WordPress."""

    def __init__(self, config: CMSConnectionConfig) -> None:
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

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self._headers,
            timeout=30.0,
            follow_redirects=True,
        )

    # ── Connection ────────────────────────────────────────────

    async def validate_connection(self) -> CMSConnectionStatus:
        async with self._client() as client:
            # 1. Check if the REST API is accessible
            try:
                resp = await client.get(f"{self.base_url}/wp-json")
                resp.raise_for_status()
                site_info = resp.json()
            except httpx.HTTPStatusError as e:
                return CMSConnectionStatus(
                    connected=False,
                    error=f"Site not reachable or REST API disabled: {e.response.status_code}",
                )

            # 2. Verify credentials by hitting /users/me
            try:
                me_resp = await client.get(f"{self.api_base}/users/me?context=edit")
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

    # ── Read Operations ───────────────────────────────────────

    async def list_posts(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        status: str = "publish",
        after: datetime | None = None,
        modified_after: datetime | None = None,
    ) -> tuple[list[CMSPost], int]:
        params: dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 100),  # WP caps at 100
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
        """
        Convenience: paginate through ALL posts.
        Used during initial sync (connect flow).
        """
        all_posts: list[CMSPost] = []
        page = 1
        while True:
            posts, total = await self.list_posts(page=page, per_page=100, status=status)
            all_posts.extend(posts)
            if len(all_posts) >= total or not posts:
                break
            page += 1
        return all_posts

    async def get_post(self, post_id: int | str) -> CMSPost:
        async with self._client() as client:
            resp = await client.get(f"{self.api_base}/posts/{post_id}")
            if resp.status_code == 404:
                raise CMSNotFoundError(f"Post {post_id} not found")
            resp.raise_for_status()
            return self._parse_post(resp.json())

    async def list_categories(self) -> list[CMSCategory]:
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
                    categories.append(CMSCategory(
                        cms_id=str(c["id"]),
                        name=c["name"],
                        slug=c["slug"],
                        parent_id=str(c["parent"]) if c.get("parent") else None,
                        post_count=c.get("count", 0),
                    ))
                total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1
        return categories

    # ── Write Operations ──────────────────────────────────────

    async def publish_post(self, post: CMSPostCreate) -> CMSPost:
        """
        Create a new post on WordPress.
        
        Category resolution: post.categories contains category NAMES.
        We resolve them to WP category IDs, creating new categories if needed.
        """
        category_ids = await self._resolve_category_ids(post.categories)

        payload: dict[str, Any] = {
            "title": post.title,
            "slug": post.slug,
            "content": post.content_html,
            "excerpt": post.excerpt,
            "status": post.status.value,
            "categories": category_ids,
            "tags": [],  # Tag resolution is similar but deferred for v1
        }
        if post.featured_image_id:
            payload["featured_media"] = int(post.featured_image_id)

        # Yoast SEO fields (if Yoast is installed, these are custom meta)
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

    async def update_post(self, post_id: int | str, updates: CMSPostUpdate) -> CMSPost:
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
            resp = await client.post(f"{self.api_base}/posts/{post_id}", json=payload)
            if resp.status_code == 404:
                raise CMSNotFoundError(f"Post {post_id} not found")
            resp.raise_for_status()
            return self._parse_post(resp.json())

    # ── Media Operations ──────────────────────────────────────

    async def upload_media(self, media: CMSMediaUpload) -> CMSMediaResult:
        headers = {**self._headers}
        headers["Content-Type"] = media.mime_type
        headers["Content-Disposition"] = f'attachment; filename="{media.filename}"'

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

    # ── Internal Helpers ──────────────────────────────────────

    def _parse_post(self, raw: dict[str, Any]) -> CMSPost:
        """Normalize a WP REST API post response into CMSPost."""
        content_html = raw.get("content", {}).get("rendered", "")
        word_count = len(content_html.split()) if content_html else 0

        # Extract SEO data from Yoast if present
        yoast = raw.get("yoast_head_json", {}) or {}

        return CMSPost(
            cms_id=str(raw["id"]),
            title=raw.get("title", {}).get("rendered", ""),
            slug=raw.get("slug", ""),
            content_html=content_html,
            excerpt=raw.get("excerpt", {}).get("rendered", ""),
            status=PostStatus(raw.get("status", "publish")),
            url=raw.get("link", ""),
            published_at=self._parse_dt(raw.get("date")),
            modified_at=self._parse_dt(raw.get("modified")),
            author=str(raw.get("author", "")),
            categories=[str(c) for c in raw.get("categories", [])],
            tags=[str(t) for t in raw.get("tags", [])],
            featured_image_url="",  # Requires separate media lookup — deferred
            seo_title=yoast.get("title", ""),
            seo_description=yoast.get("og_description", ""),
            word_count=word_count,
            raw_metadata=raw,
        )

    def _parse_dt(self, dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None

    async def _resolve_category_ids(self, category_names: list[str]) -> list[int]:
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
                # Create the category
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
```

---

## 4. Adapter Factory

**File:** `core/cms/factory.py`

```python
"""
CMS adapter factory.

Usage:
    adapter = create_cms_adapter(config)
    status = await adapter.validate_connection()
"""

from core.cms.models import CMSConnectionConfig, CMSProvider
from core.cms.protocols import CMSAdapterProtocol
from core.cms.adapters.wordpress import WordPressAdapter


_ADAPTER_REGISTRY: dict[CMSProvider, type] = {
    CMSProvider.WORDPRESS: WordPressAdapter,
    # CMSProvider.WEBFLOW: WebflowAdapter,     # Future
    # CMSProvider.STRAPI: StrapiAdapter,        # Future
}


def create_cms_adapter(config: CMSConnectionConfig) -> CMSAdapterProtocol:
    """
    Instantiate the correct adapter based on provider type.
    
    Raises KeyError if the provider is not yet supported.
    """
    adapter_cls = _ADAPTER_REGISTRY.get(config.provider)
    if adapter_cls is None:
        supported = ", ".join(p.value for p in _ADAPTER_REGISTRY)
        raise ValueError(
            f"Unsupported CMS provider: {config.provider.value}. "
            f"Supported: {supported}"
        )
    return adapter_cls(config)
```

---

## 5. Exception Hierarchy

**File:** `core/cms/exceptions.py`

```python
class CMSError(Exception):
    """Base exception for all CMS operations."""


class CMSAuthError(CMSError):
    """Invalid or expired credentials."""


class CMSAPIError(CMSError):
    """CMS API returned an unexpected error."""


class CMSNotFoundError(CMSError):
    """Resource (post, category, media) not found."""


class CMSRateLimitError(CMSError):
    """CMS API rate limit hit."""


class CMSConnectionError(CMSError):
    """Cannot reach the CMS (DNS, timeout, etc.)."""
```

---

## 6. Database Layer — ORM Models

**File:** `core/db/models/cms.py`

```python
"""
CMS integration ORM models.
Alembic migration: 0006_cms_integration.py
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean,
    ForeignKey, Enum as SAEnum, Index, JSON,
)
from sqlalchemy.orm import relationship

from core.db.base import Base
from core.cms.models import CMSProvider, PostStatus


class CMSConnection(Base):
    """
    Stores a client company's CMS connection credentials.
    One company can have exactly one active CMS connection (for now).
    """
    __tablename__ = "cms_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_slug = Column(String(255), nullable=False, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)

    provider = Column(SAEnum(CMSProvider), nullable=False)
    site_url = Column(String(512), nullable=False)
    # Encrypted at rest — stored via Fernet symmetric encryption
    encrypted_credentials = Column(Text, nullable=False)

    site_name = Column(String(255), default="")
    cms_version = Column(String(50), default="")
    user_display_name = Column(String(255), default="")

    is_active = Column(Boolean, default=True)
    last_validated_at = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)     # Last time we pulled existing content

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    publish_records = relationship("CMSPublishRecord", back_populates="connection")
    synced_posts = relationship("CMSSyncedPost", back_populates="connection")

    __table_args__ = (
        Index("ix_cms_conn_tenant_slug", "tenant_id", "company_slug", unique=True),
    )


class CMSPublishRecord(Base):
    """
    Tracks each publish/update action from Deep Presence → CMS.
    Links a Content Engine brief to its CMS post.
    """
    __tablename__ = "cms_publish_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_id = Column(Integer, ForeignKey("cms_connections.id"), nullable=False)
    company_slug = Column(String(255), nullable=False, index=True)

    # Deep Presence side
    brief_id = Column(String(255), nullable=False)        # Content Engine brief ID
    content_engine_run_id = Column(String(255), default="")

    # CMS side
    cms_post_id = Column(String(50), nullable=False)       # ID in the CMS
    cms_post_url = Column(String(1024), default="")
    cms_post_slug = Column(String(512), default="")

    # Publish metadata
    action = Column(String(50), nullable=False)            # "create" | "update" | "refresh"
    status_at_publish = Column(SAEnum(PostStatus), default=PostStatus.DRAFT)
    published_at = Column(DateTime, default=datetime.utcnow)

    # Snapshot of what was sent (for audit trail)
    title_published = Column(String(512), default="")
    word_count = Column(Integer, default=0)

    connection = relationship("CMSConnection", back_populates="publish_records")

    __table_args__ = (
        Index("ix_publish_brief", "company_slug", "brief_id"),
    )


class CMSSyncedPost(Base):
    """
    Local index of existing posts on the client's CMS.
    Populated by the initial sync flow and refreshed periodically.
    
    This table enables:
    - Cannibalization check (does a post on this topic already exist?)
    - Staleness detection (was this post modified more than N days ago?)
    - Content refresh targeting (which existing posts should we update?)
    """
    __tablename__ = "cms_synced_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_id = Column(Integer, ForeignKey("cms_connections.id"), nullable=False)
    company_slug = Column(String(255), nullable=False, index=True)

    cms_post_id = Column(String(50), nullable=False)
    title = Column(String(512), nullable=False)
    slug = Column(String(512), nullable=False)
    url = Column(String(1024), default="")
    excerpt = Column(Text, default="")
    content_preview = Column(Text, default="")   # First ~500 chars of content (not full HTML)
    word_count = Column(Integer, default=0)

    published_at = Column(DateTime, nullable=True)
    modified_at = Column(DateTime, nullable=True)

    categories = Column(JSON, default=list)        # List of category names
    tags = Column(JSON, default=list)              # List of tag names
    seo_title = Column(String(512), default="")
    seo_description = Column(Text, default="")

    # Deep Presence analysis (populated post-sync)
    is_stale = Column(Boolean, default=False)               # modified_at older than 30-day threshold
    staleness_days = Column(Integer, default=0)
    detected_primary_keyword = Column(String(255), default="")  # Extracted by our NLP
    cannibalization_risk = Column(Boolean, default=False)        # Flagged by Topic Discovery (future)

    # Refresh tracking (Recommended Actions → Triage flow)
    queued_for_refresh = Column(Boolean, default=False)         # True once user clicks "Refresh Content"
    refresh_brief_id = Column(String(255), default="")          # Content Engine brief ID if queued
    refresh_queued_at = Column(DateTime, nullable=True)         # When user approved the refresh

    synced_at = Column(DateTime, default=datetime.utcnow)        # When we last pulled this

    connection = relationship("CMSConnection", back_populates="synced_posts")

    __table_args__ = (
        Index("ix_synced_post_cms_id", "connection_id", "cms_post_id", unique=True),
        Index("ix_synced_post_stale", "company_slug", "is_stale"),
    )
```

---

## 7. CMS Service Layer

**File:** `core/services/cms_service.py`

```python
"""
CMS service — orchestrates connection management, sync, and publish flows.

This is the layer that API routers call.
It coordinates between the adapter (CMS API calls), the database (persistence),
and the Content Engine artifacts (reading final.md for publish).
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.cms.factory import create_cms_adapter
from core.cms.models import (
    CMSConnectionConfig,
    CMSConnectionStatus,
    CMSPost,
    CMSPostCreate,
    CMSProvider,
    PostStatus,
)
from core.cms.protocols import CMSAdapterProtocol
from core.cms.exceptions import CMSError


class CMSService:
    """
    High-level CMS operations.
    
    Responsibilities:
    1. Connection lifecycle: connect, validate, store credentials
    2. Sync: pull existing posts into local index
    3. Publish: take a Content Engine brief and push to CMS
    4. Refresh: update an existing CMS post with new content
    """

    def __init__(
        self,
        *,
        artifacts_root: Path,
        # db_session and repositories injected via DI — placeholder signatures
        # cms_connection_repo: CMSConnectionRepository,
        # cms_publish_repo: CMSPublishRecordRepository,
        # cms_synced_repo: CMSSyncedPostRepository,
    ):
        self.artifacts_root = artifacts_root

    # ── Connect Flow ──────────────────────────────────────────

    async def connect(
        self,
        company_slug: str,
        tenant_id: str,
        provider: CMSProvider,
        site_url: str,
        username: str,
        api_key: str,
    ) -> CMSConnectionStatus:
        """
        1. Build config
        2. Validate credentials via adapter
        3. Persist connection (encrypted) to DB
        4. Trigger initial content sync
        """
        config = CMSConnectionConfig(
            provider=provider,
            site_url=site_url,
            username=username,
            api_key=api_key,
        )
        adapter = create_cms_adapter(config)
        status = await adapter.validate_connection()

        if not status.connected:
            return status

        # TODO: Encrypt credentials with Fernet, persist to cms_connections table
        # TODO: Trigger background sync task

        return status

    # ── Sync Flow ─────────────────────────────────────────────

    async def sync_existing_content(
        self,
        company_slug: str,
        adapter: CMSAdapterProtocol,
    ) -> dict[str, Any]:
        """
        Pull all published posts from the CMS and index them locally.
        
        Returns summary: {total_posts, new_posts, updated_posts, stale_count}
        """
        all_posts = await adapter.list_all_posts(status="publish")
        categories = await adapter.list_categories()

        # Build category ID → name lookup
        cat_map = {c.cms_id: c.name for c in categories}

        stale_threshold = datetime.utcnow() - timedelta(days=30)  # 1 month
        stale_count = 0

        for post in all_posts:
            is_stale = (
                post.modified_at is not None
                and post.modified_at < stale_threshold
            )
            if is_stale:
                stale_count += 1

            # Resolve category IDs to names
            cat_names = [cat_map.get(cid, f"unknown-{cid}") for cid in post.categories]

            # TODO: Upsert into cms_synced_posts table
            # - Match on (connection_id, cms_post_id)
            # - Update title, slug, url, modified_at, word_count, categories, etc.
            # - Set is_stale, staleness_days

        return {
            "total_posts": len(all_posts),
            "stale_count": stale_count,
            "categories": len(categories),
        }

    # ── Publish Flow ──────────────────────────────────────────

    async def publish_brief(
        self,
        company_slug: str,
        brief_id: str,
        adapter: CMSAdapterProtocol,
        *,
        target_status: PostStatus = PostStatus.DRAFT,
        category_names: list[str] | None = None,
        slug_override: str | None = None,
    ) -> CMSPost:
        """
        Publish a Content Engine brief to the connected CMS.
        
        1. Read final.md from the artifact directory
        2. Convert markdown to HTML (the CMS expects HTML)
        3. Extract title and slug from the content/blueprint
        4. Call adapter.publish_post()
        5. Record the publish action in cms_publish_records
        """
        # Locate the final content artifact
        content_dir = self.artifacts_root / company_slug / "content"
        brief_dir = content_dir / f"brief-{brief_id}"
        final_md_path = brief_dir / "final.md"

        if not final_md_path.exists():
            raise CMSError(f"No final.md found for brief {brief_id} at {final_md_path}")

        final_md = final_md_path.read_text(encoding="utf-8")

        # Extract title from first H1 line
        title = self._extract_title(final_md)

        # Generate slug from title (or use override)
        slug = slug_override or self._generate_slug(title)

        # Convert markdown → HTML for the CMS
        content_html = self._markdown_to_html(final_md)

        # Build the publish payload
        post_create = CMSPostCreate(
            title=title,
            slug=slug,
            content_html=content_html,
            status=target_status,
            categories=category_names or [],
        )

        # Publish via adapter
        published_post = await adapter.publish_post(post_create)

        # TODO: Record in cms_publish_records table
        # (connection_id, brief_id, cms_post_id, cms_post_url, action="create", ...)

        return published_post

    # ── Content Refresh Flow ──────────────────────────────────

    async def refresh_post(
        self,
        company_slug: str,
        cms_post_id: str,
        brief_id: str,
        adapter: CMSAdapterProtocol,
    ) -> CMSPost:
        """
        Update an existing CMS post with refreshed content from the Content Engine.
        Used when staleness detection flags a post for refresh.
        """
        content_dir = self.artifacts_root / company_slug / "content"
        brief_dir = content_dir / f"brief-{brief_id}"
        final_md_path = brief_dir / "final.md"

        if not final_md_path.exists():
            raise CMSError(f"No final.md for refresh brief {brief_id}")

        final_md = final_md_path.read_text(encoding="utf-8")
        content_html = self._markdown_to_html(final_md)
        title = self._extract_title(final_md)

        from core.cms.models import CMSPostUpdate
        updates = CMSPostUpdate(
            title=title,
            content_html=content_html,
        )

        updated_post = await adapter.update_post(cms_post_id, updates)

        # TODO: Record in cms_publish_records (action="refresh")

        return updated_post

    # ── Stale Content → Recommended Actions → Triage ──────────

    async def get_stale_actions(
        self,
        company_slug: str,
    ) -> list[dict]:
        """
        Return stale posts formatted as Recommended Action cards for the Home dashboard.
        
        Queries cms_synced_posts WHERE is_stale=True AND queued_for_refresh=False,
        ordered by staleness_days DESC.
        
        Each item includes:
        - title, url, cms_synced_post_id, staleness_days
        - description: "Last updated {N} days ago. Refreshing this content
          improves LLM presence and bot crawlability."
        """
        # TODO: Query cms_synced_posts with filters
        # Return list of StaleContentAction dicts
        pass

    async def queue_stale_for_refresh(
        self,
        company_slug: str,
        cms_synced_post_id: int,
    ) -> dict:
        """
        User clicked "Refresh Content" on a Recommended Actions card.
        
        1. Look up the stale post from cms_synced_posts
        2. Create a Content Engine brief stub:
           - topic = stale post's title / detected_primary_keyword
           - entry_mode = "cms_refresh"
           - cms_target_post_id = the WP/CMS post ID to update after approval
        3. The brief lands in Triage column of Content Studio Kanban
        4. Mark cms_synced_posts.queued_for_refresh = True
        5. Return { brief_id, title, status: "triage" }
        
        From here, the normal Content Studio flow takes over.
        When the user eventually approves the final content in the Approved column,
        the frontend calls POST /cms/refresh/{cms_post_id} to push it to the CMS.
        """
        # TODO: 
        # 1. Fetch synced post row
        # 2. Create brief stub via content engine API (similar to manual "Add to Content Cycle")
        #    - Set entry_mode="cms_refresh" so the pipeline knows this is a refresh, not net-new
        #    - Attach cms_target_post_id so the publish step knows which post to update
        # 3. Update cms_synced_posts SET queued_for_refresh=True, refresh_brief_id=brief_id
        # 4. Return StaleToTriageResponse
        pass

    # ── Helpers ────────────────────────────────────────────────

    def _extract_title(self, markdown: str) -> str:
        """Extract the first H1 from markdown content."""
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                return stripped.lstrip("# ").strip()
        return "Untitled"

    def _generate_slug(self, title: str) -> str:
        """Generate a URL-safe slug from a title."""
        slug = title.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        slug = slug.strip("-")
        return slug[:200]  # Cap length

    def _markdown_to_html(self, markdown: str) -> str:
        """
        Convert markdown to HTML for CMS publishing.
        
        Uses markdown library if available, otherwise a basic conversion.
        In production, consider using markdown2 or mistune for fidelity.
        """
        try:
            import markdown as md_lib
            return md_lib.markdown(
                markdown,
                extensions=["tables", "fenced_code", "toc", "attr_list"],
            )
        except ImportError:
            # Fallback: minimal conversion (paragraphs + headers)
            lines = markdown.splitlines()
            html_parts: list[str] = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("### "):
                    html_parts.append(f"<h3>{html.escape(stripped[4:])}</h3>")
                elif stripped.startswith("## "):
                    html_parts.append(f"<h2>{html.escape(stripped[3:])}</h2>")
                elif stripped.startswith("# "):
                    html_parts.append(f"<h1>{html.escape(stripped[2:])}</h1>")
                elif stripped:
                    html_parts.append(f"<p>{html.escape(stripped)}</p>")
            return "\n".join(html_parts)
```

---

## 8. API Router

**File:** `api/routers/cms.py`

```python
"""
CMS integration API endpoints.

Auth: All endpoints require authentication + tenant isolation.
Following patterns from: api/routers/gap_analysis.py, api/routers/research.py
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from typing import Any

from core.cms.models import CMSProvider, PostStatus


router = APIRouter(prefix="/api/v1/cms", tags=["cms"])


# ── Request/Response Schemas ──────────────────────────────────

class CMSConnectRequest(BaseModel):
    provider: CMSProvider
    site_url: HttpUrl
    username: str = ""
    api_key: str

class CMSConnectResponse(BaseModel):
    connected: bool
    site_name: str = ""
    site_url: str = ""
    cms_version: str = ""
    user_display_name: str = ""
    error: str | None = None

class CMSPublishRequest(BaseModel):
    brief_id: str
    status: PostStatus = PostStatus.DRAFT
    slug_override: str | None = None
    categories: list[str] = []

class CMSPublishResponse(BaseModel):
    cms_post_id: str
    url: str
    slug: str
    title: str
    status: str

class CMSSyncResponse(BaseModel):
    total_posts: int
    stale_count: int
    categories: int

class CMSSyncedPostSummary(BaseModel):
    cms_post_id: str
    title: str
    slug: str
    url: str
    word_count: int
    published_at: str | None = None
    modified_at: str | None = None
    is_stale: bool = False
    staleness_days: int = 0
    categories: list[str] = []

class CMSConnectionInfo(BaseModel):
    provider: str
    site_url: str
    site_name: str
    is_active: bool
    last_sync_at: str | None = None

class StaleContentAction(BaseModel):
    """A single stale content card for the Recommended Actions component."""
    cms_synced_post_id: int
    cms_post_id: str
    title: str
    url: str
    staleness_days: int
    description: str          # e.g. "Last updated 47 days ago. Refreshing improves LLM presence..."
    queued_for_refresh: bool = False  # True once user clicks "Refresh Content"

class StaleToTriageRequest(BaseModel):
    cms_synced_post_id: int

class StaleToTriageResponse(BaseModel):
    brief_id: str
    title: str
    status: str = "triage"    # The brief lands in Triage column


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/connect", response_model=CMSConnectResponse)
async def connect_cms(
    request: CMSConnectRequest,
    # auth: AuthUser = Depends(require_auth),
    # tenant: TenantContext = Depends(require_tenant),
):
    """
    Connect a CMS to the company's Deep Presence account.
    
    Validates credentials and stores the connection.
    Triggers a background sync of existing content.
    """
    # TODO: Wire to CMSService.connect()
    pass


@router.get("/connection", response_model=CMSConnectionInfo | None)
async def get_connection(
    # auth, tenant deps
):
    """Get the current CMS connection info for this company."""
    # TODO: Query cms_connections by tenant + company_slug
    pass


@router.delete("/connection")
async def disconnect_cms(
    # auth, tenant deps
):
    """Disconnect the CMS integration. Does NOT delete synced data."""
    # TODO: Set is_active=False on the connection
    pass


@router.post("/sync", response_model=CMSSyncResponse)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    # auth, tenant deps
):
    """
    Re-sync existing content from the CMS.
    Runs as a background task; returns immediately with an acknowledgment.
    """
    # TODO: Kick off background sync
    pass


@router.get("/synced-posts", response_model=list[CMSSyncedPostSummary])
async def list_synced_posts(
    stale_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    # auth, tenant deps
):
    """
    List the locally indexed posts from the connected CMS.
    Secondary informational view — primary stale action path is via /stale-actions.
    """
    # TODO: Query cms_synced_posts with filters
    pass


@router.get("/stale-actions", response_model=list[StaleContentAction])
async def get_stale_actions(
    # auth, tenant deps
):
    """
    Get stale content cards for the Home dashboard Recommended Actions component.
    
    Returns posts where is_stale=True and queued_for_refresh=False,
    ordered by staleness_days descending (most stale first).
    
    Each card includes the post title, URL, and a human-readable description
    explaining why the content needs refreshing.
    """
    # TODO: Query cms_synced_posts WHERE is_stale=True
    # Build description: f"Last updated {staleness_days} days ago. Refreshing this
    # content improves LLM presence and bot crawlability."
    pass


@router.post("/stale-to-triage", response_model=StaleToTriageResponse)
async def stale_to_triage(
    request: StaleToTriageRequest,
    # auth, tenant deps
):
    """
    User clicks "Refresh Content" on a stale content card in Recommended Actions.
    
    1. Reads the stale post's title, keyword, and cms_post_id from cms_synced_posts
    2. Creates a Content Engine brief stub with entry_mode="cms_refresh"
       and cms_target_post_id linking back to the CMS post to update
    3. The brief lands in the Triage column of Content Studio
    4. Marks the synced post as queued_for_refresh=True (so it greys out in Rec. Actions)
    
    From Triage, the normal Content Studio pipeline takes over.
    On final approval, the user triggers /cms/refresh/{cms_post_id} to push updates.
    """
    # TODO: Wire to CMSService.queue_stale_for_refresh()
    pass


@router.post("/publish", response_model=CMSPublishResponse)
async def publish_to_cms(
    request: CMSPublishRequest,
    # auth, tenant deps
):
    """
    Publish an approved Content Engine brief to the connected CMS.
    
    The brief must be in "approved" status (final.md exists).
    Default publishes as draft — user can set status to "publish" for immediate go-live.
    """
    # TODO: Wire to CMSService.publish_brief()
    pass


@router.post("/refresh/{cms_post_id}", response_model=CMSPublishResponse)
async def refresh_cms_post(
    cms_post_id: str,
    brief_id: str,
    # auth, tenant deps
):
    """
    Update an existing CMS post with refreshed content.
    Links a Content Engine refresh brief to the target post.
    """
    # TODO: Wire to CMSService.refresh_post()
    pass


@router.get("/publish-history", response_model=list[dict])
async def get_publish_history(
    limit: int = 50,
    # auth, tenant deps
):
    """
    List all publish/refresh actions for this company.
    Used for audit trail and the "Published" state in Content Studio.
    """
    # TODO: Query cms_publish_records ordered by published_at desc
    pass
```

---

## 9. Directory Layout

```
core/
├── cms/
│   ├── __init__.py
│   ├── protocols.py              # CMSAdapterProtocol
│   ├── models.py                 # Pydantic domain models (CMSPost, CMSPostCreate, etc.)
│   ├── exceptions.py             # CMSError hierarchy
│   ├── factory.py                # create_cms_adapter() registry
│   └── adapters/
│       ├── __init__.py
│       ├── wordpress.py          # WordPressAdapter (v1)
│       ├── webflow.py            # WebflowAdapter (future)
│       └── strapi.py             # StrapiAdapter (future)
├── services/
│   └── cms_service.py            # High-level orchestration
├── db/
│   ├── models/
│   │   └── cms.py                # ORM models (CMSConnection, CMSPublishRecord, CMSSyncedPost)
│   ├── repositories/
│   │   └── cms.py                # CMSConnectionRepository, CMSSyncedPostRepository (future)
│   └── migrations/
│       └── versions/
│           └── 0006_cms_integration.py   # Alembic migration

api/
├── routers/
│   └── cms.py                    # FastAPI endpoints
├── schemas/
│   └── cms.py                    # (optional: can live in the router file for v1)
└── dependencies.py               # + get_cms_service() factory function
```

---

## 10. Frontend Integration Points

### 10.1 CMS Settings Page

A new settings panel at `/settings/cms` where the user:
1. Selects provider (WordPress dropdown, others disabled/coming soon)
2. Pastes their site URL
3. Pastes their WordPress username
4. Pastes their Application Password
5. Clicks "Connect" → calls `POST /api/v1/cms/connect`
6. Sees success state with site name, user info, and sync progress

### 10.2 Content Studio — Publish Button

On tiles in the **Approved** column of the Kanban board:
- A "Publish to CMS" button appears (only if CMS is connected)
- Clicking opens a confirmation drawer showing:
  - Generated slug (editable)
  - Target status (Draft / Publish toggle)
  - Category selector (populated from CMS categories)
  - Preview of first ~200 chars
- "Confirm Publish" → calls `POST /api/v1/cms/publish`
- Tile badge updates to "Published" with the CMS permalink

### 10.3 Home Dashboard — Stale Content in Recommended Actions

The user does **not** manually browse synced posts looking for staleness. Deep Presence detects it and surfaces it.

On the Home page's existing **Recommended Actions** component, stale CMS posts appear as action cards:

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠  "How to Choose Expense Management Software" is stale       │
│                                                                 │
│  https://blog.ramp.com/expense-management-software              │
│  Last updated 47 days ago. Refreshing this content improves     │
│  LLM presence and bot crawlability.                             │
│                                                                 │
│                                          [ Refresh Content ]    │
└─────────────────────────────────────────────────────────────────┘
```

Each stale content card contains:
- The page title (heading from the CMS post)
- The page URL (permalink from the CMS)
- A short description: "Last updated {N} days ago. Refreshing this content improves LLM presence and bot crawlability."
- A **"Refresh Content"** button (primary action)

**When the user clicks "Refresh Content":**
1. Frontend calls `POST /api/v1/cms/stale-to-triage` with the `cms_synced_post_id`
2. Backend creates a Content Engine brief stub targeting the stale post's topic/keyword
3. The brief appears in the **Triage** column of Content Studio
4. The Recommended Actions card updates to "Queued for refresh" (muted state)
5. From Triage, the normal Content Studio flow takes over — user approves, brief generates, content produces, and on final approval the refreshed content gets pushed back to the CMS via `POST /api/v1/cms/refresh/{cms_post_id}`

The user's role is purely approval-based: Deep Presence detects, user approves, pipeline executes, CMS updates.

### 10.4 Synced Content View (Informational, secondary)

A secondary view at `/content-studio/synced` showing all imported CMS posts as a read-only table. This is for visibility, not action — the primary action path is Recommended Actions on Home.
- Table columns: Title, URL, word count, last modified, stale status
- No action buttons here (actions live in Recommended Actions)
- Useful for: "how many blog posts do we have?", "what's our publishing cadence?"

### 10.5 Topic Discovery — No Changes (Architecture-Ready)

Topic Discovery continues to show topics exactly as it does today. The CMS sync data (existing post titles, keywords, categories) is stored in `cms_synced_posts` and is **available** for future cross-referencing — e.g., de-prioritizing topics that already have published content, or flagging cannibalization risk — but this integration is deferred. The adapter pattern and the `cannibalization_risk` / `detected_primary_keyword` columns on `CMSSyncedPost` are the extension points when this becomes a priority.

---

## 11. Data Flow Diagrams

### 11.1 Connect + Sync Flow

```
User enters credentials
        │
        ▼
POST /api/v1/cms/connect
        │
        ├─→ CMSService.connect()
        │       ├─→ create_cms_adapter(config)
        │       ├─→ adapter.validate_connection()
        │       │       └─→ WP REST API: GET /wp-json + GET /users/me
        │       ├─→ Encrypt credentials → INSERT cms_connections
        │       └─→ Background: sync_existing_content()
        │               ├─→ adapter.list_all_posts()
        │               │       └─→ WP REST API: GET /posts?per_page=100&page=1,2,...
        │               ├─→ adapter.list_categories()
        │               │       └─→ WP REST API: GET /categories
        │               └─→ UPSERT cms_synced_posts (per post)
        │                       └─→ Flag is_stale where modified_at < threshold
        ▼
Response: { connected: true, site_name: "Ramp Blog", ... }
```

### 11.2 Publish Flow

```
User clicks "Publish to CMS" on Approved tile
        │
        ▼
POST /api/v1/cms/publish { brief_id: "xyz", status: "draft" }
        │
        ├─→ CMSService.publish_brief()
        │       ├─→ Read artifacts/{slug}/content/brief-xyz/final.md
        │       ├─→ Extract title → generate slug
        │       ├─→ Convert markdown → HTML
        │       ├─→ adapter.publish_post(CMSPostCreate)
        │       │       └─→ WP REST API: POST /posts { title, slug, content, status }
        │       ├─→ INSERT cms_publish_records (action="create")
        │       └─→ Return { cms_post_id, url, slug }
        ▼
Response: { cms_post_id: "1234", url: "https://blog.ramp.com/expense-management/", ... }
Frontend: Tile badge → "Published" with permalink
```

### 11.3 Stale Content → Refresh Flow

```
Background sync flags posts where modified_at < 30 days ago
        │
        ▼
Home Dashboard: Recommended Actions component
        │  Shows: title, URL, "Last updated N days ago..."
        │  Button: "Refresh Content"
        │
        ▼ (user clicks "Refresh Content")
POST /api/v1/cms/stale-to-triage { cms_synced_post_id: "42" }
        │
        ├─→ CMSService.queue_stale_for_refresh()
        │       ├─→ Read cms_synced_posts row (title, slug, keyword, cms_post_id)
        │       ├─→ Create Content Engine brief stub (entry_mode="cms_refresh")
        │       │       └─→ brief.cms_target_post_id = "1234" (the WP post to update)
        │       ├─→ Brief appears in Content Studio → Triage column
        │       └─→ Mark recommended action as "queued"
        │
        ▼ (normal Content Studio flow: Triage → Brief → Generating → Review → Approved)
        │
        ▼ (user approves final content)
POST /api/v1/cms/refresh/1234 { brief_id: "refresh-xyz" }
        │
        ├─→ CMSService.refresh_post()
        │       ├─→ Read artifacts/{slug}/content/brief-refresh-xyz/final.md
        │       ├─→ Convert markdown → HTML
        │       ├─→ adapter.update_post("1234", CMSPostUpdate)
        │       │       └─→ WP REST API: POST /posts/1234 { content, title }
        │       └─→ INSERT cms_publish_records (action="refresh")
        ▼
Response: updated post metadata
```

---

## 12. Adding a New CMS Provider (Extension Guide)

To add Webflow, Strapi, Ghost, or any other CMS:

1. **Create adapter file:** `core/cms/adapters/webflow.py`
   - Implement all methods from `CMSAdapterProtocol`
   - Map the provider's native API responses to `CMSPost`, `CMSCategory`, etc.
   - Handle provider-specific auth (Webflow uses Bearer token, Strapi uses JWT)

2. **Register in factory:** Add one line to `_ADAPTER_REGISTRY` in `core/cms/factory.py`

3. **Add enum value:** Add `WEBFLOW = "webflow"` to `CMSProvider` in `core/cms/models.py`

4. **Frontend:** Add the provider option to the CMS settings dropdown + any provider-specific credential fields

5. **Migration:** Alembic migration to add the new enum value to the `provider` column

**No changes needed to:** CMSService, API router, database models, publish flow, sync flow, or any other existing code. The adapter pattern encapsulates all provider differences.

---

## 13. Security Considerations

1. **Credential encryption:** CMS credentials (API keys, application passwords) must be encrypted at rest using Fernet symmetric encryption before storing in `cms_connections.encrypted_credentials`. The encryption key lives in environment variables, never in code.

2. **Credential scoping:** The WordPress Application Password should have the minimum required capabilities: `publish_posts`, `edit_posts`, `upload_files`, `read`. Admin-level credentials should be explicitly rejected during `validate_connection()`.

3. **Tenant isolation:** All CMS operations are scoped by `tenant_id` + `company_slug`. A user in Tenant A cannot access Tenant B's CMS connections. This follows the existing `require_tenant` dependency pattern.

4. **Rate limiting:** WordPress REST API has no built-in rate limiting, but hosting providers often do (Cloudflare, WP Engine). The adapter should handle 429 responses with exponential backoff.

5. **Content sanitization:** Content flowing from Deep Presence → CMS is trusted (we generated it). Content flowing from CMS → Deep Presence (during sync) should be treated as untrusted HTML — strip scripts, sanitize before storing/displaying.

---

## 14. Implementation Sequence (Effort Estimates)

| Step | Files | Status | Description |
|------|-------|--------|-------------|
| 1. Domain models + Protocol | `core/cms/models.py`, `protocols.py`, `exceptions.py` | **DONE** (2026-03-26) | 3 enums, 8 Pydantic models, CMSAdapterProtocol (7 methods), 6 exception classes. 32 tests. |
| 2. WordPress adapter | `core/cms/adapters/wordpress.py` | **DONE** (2026-03-26) | All 7 protocol methods + list_all_posts + _parse_post/_resolve_category_ids. httpx.MockTransport tests. 31 tests. |
| 3. Factory | `core/cms/factory.py` | **DONE** (2026-03-26) | Registry + kwargs forwarding (_transport for tests). 5 tests. |
| 4. CMS service | `core/services/cms_service.py` | **DONE** (2026-03-26) | 8 methods (connect, get_connection, disconnect, sync, publish, refresh, stale_actions, queue_stale). Fernet encryption, StorageBackend reads, MD→HTML. 13 tests. |
| 5. ORM + migration | `core/db/models/cms.py`, migration 0021 | **DONE** (2026-03-26) | 3 ORM models (UUID PKs, mapped_column), 3 repos, migration creates 3 tables + 3 enums. 12 tests (enum + import). |
| 6. API router | `api/routers/cms.py` + DI wiring | **DONE** (2026-03-26) | 11 endpoints (10 original + GET /categories per Codex F4). DI via get_cms_service() (DB-required, 503 fallback). Background sync via run_cms_sync_task() with own session. 3 Codex fixes: F2 tenant isolation, F4 categories, F8 reconnect UPDATE. 3 new CMSService methods. |
| 7. Tests | `tests/api/test_cms.py` | **DONE** (2026-03-26) | 49 API-level tests across 11 test classes. Auth/RBAC/tenant isolation/exception mapping coverage. Codex-reviewed (GPT-5.3-Codex, 10 findings). |
| 8. Frontend — CMS settings | Dashboard settings page | PENDING | Connect form + connection status display |
| 9. Frontend — publish button | Content Studio Kanban modification | PENDING | Publish drawer on Approved tiles |
| 10. Frontend — stale content in Recommended Actions | Home dashboard component | PENDING | Stale content cards + "Refresh Content" → Triage flow |
| 11. Frontend — synced posts (informational) | `/content-studio/synced` page | PENDING | Read-only table, no action buttons |

### Implementation Deviations from Original Spec (Approved 2026-03-26)

| # | Original Spec | Actual Implementation | Reason |
|---|---------------|----------------------|--------|
| D1 | Migration `0006` | **`0021`** | Latest migration was `0020_content_artifacts.py` |
| D2 | `Column()`, `Integer` PK | **`mapped_column()`, `UUIDPKMixin`** | Every other model uses modern style + UUID PKs |
| D3 | `Path.read_text()` in CMSService | **`StorageBackend.read()` via `asyncio.to_thread()`** | R2 migration (v20) requires all reads through StorageBackend |
| D4 | UPPERCASE enum values (`WORDPRESS`) | **Lowercase (`wordpress`)** | All enums in `core/db/enums.py` use lowercase |
| D5 | Enums in `core/cms/models.py` | **`core/db/enums.py`, re-exported** | Convention: all DB enums live in one file |
| D6 | `PostStatus` | **`CMSPostStatus`** | Avoids collision with `ContentPieceStatus` |
| D7 | `action: String(50)` | **`action: CMSPublishAction` typed enum** | Type safety |
| D8 | No encryption dependency | **`cryptography>=42.0`** | Required for Fernet credential encryption |
| D9 | `site_url: HttpUrl` | **`site_url: str`** | Pydantic v2 `HttpUrl` serializes to `Url` object, breaks concat |
| D10 | No `effective_slug` on publish record | **Added `effective_slug`** | Needed for storage path resolution |

### Test Summary (Steps 1-5)

- **93 total tests** across 7 test files
- **Zero regressions** on 5620 existing tests
- Test files: `test_exceptions.py` (8), `test_models.py` (21), `test_protocols.py` (3), `test_wordpress_adapter.py` (31), `test_factory.py` (5), `test_cms_enums.py` (12), `test_cms_service.py` (13)

### Test Summary (Steps 6-7)

- **49 new API tests** in `tests/api/test_cms.py` across 11 test classes
- **142 total CMS tests** (49 API + 93 core)
- **1258 API suite tests passed**, 3 pre-existing failures (not CMS-related)
- **Zero regressions** from CMS changes
- Codex-reviewed: GPT-5.3-Codex, 10 findings (4 fixed: F2 tenant isolation, F4 categories endpoint, F8 reconnect constraint, F9 additional test cases)

### Implementation Deviations — Steps 6-7 (Approved 2026-03-26)

| # | Original Spec | Actual Implementation | Reason |
|---|---------------|----------------------|--------|
| D11 | 10 endpoints | **11 endpoints** | Added `GET /categories` per Codex F4 (needed for publish UI) |
| D12 | `BackgroundTasks` for sync | **`asyncio.create_task` + `TaskStore`** | Follows codebase pattern; own DB session in runner |
| D13 | `cms_synced_post_id: int` | **`cms_synced_post_id: str`** | D2: UUIDPKMixin uses UUID, not Integer |
| D14 | Deactivate + insert on reconnect | **UPDATE existing row in-place** | Codex F8: preserves FK references, avoids unique constraint violation |
| D15 | No tenant check in queue_stale | **Added `company_slug` verification** | Codex F2: prevents cross-tenant access |

Steps 8–11 are frontend work that can run in parallel now that the API is stable.
