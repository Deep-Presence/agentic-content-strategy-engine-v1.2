"""CMS integration Pydantic domain models.

All models used by adapters, factory, and CMS service.
Enums are defined in ``core.db.enums`` (codebase convention) and re-exported here.
All fields have defaults for backward compatibility.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core.db.enums import CMSPostStatus, CMSProvider
from core.cms.webflow_models import (
    WebflowAuthKind,
    WebflowCollectionConfig,
    WebflowFieldMapping,
    WebflowProviderConfig,
    WebflowPublishMode,
)

# Re-export for convenience so adapter code can do:
#   from core.cms.models import CMSProvider, CMSPostStatus
__all__ = [
    "CMSCategory",
    "CMSConnectionConfig",
    "CMSConnectionStatus",
    "CMSMediaResult",
    "CMSMediaUpload",
    "CMSPost",
    "CMSPostCreate",
    "CMSPublishMetadata",
    "CMSPostStatus",
    "CMSPostUpdate",
    "CMSProvider",
    "WebflowAuthKind",
    "WebflowCollectionConfig",
    "WebflowFieldMapping",
    "WebflowProviderConfig",
    "WebflowPublishMode",
]


# ── Connection ────────────────────────────────────────────────────────


class CMSConnectionConfig(BaseModel):
    """Credentials for connecting to a CMS.

    Provider-agnostic — each adapter interprets the fields it needs.
    """

    provider: CMSProvider = CMSProvider.wordpress
    site_url: str = ""
    api_key: str = ""
    username: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)
    provider_config: dict[str, Any] = Field(default_factory=dict)


class CMSConnectionStatus(BaseModel):
    """Result of ``validate_connection()``."""

    connected: bool = False
    site_name: str = ""
    site_url: str = ""
    cms_version: str = ""
    user_display_name: str = ""
    capabilities: list[str] = Field(default_factory=list)
    error: str | None = None


# ── Posts ─────────────────────────────────────────────────────────────


class CMSPost(BaseModel):
    """Normalized representation of a CMS post.

    Every adapter maps its native format into this shape.
    """

    cms_id: str = ""
    title: str = ""
    slug: str = ""
    content_html: str = ""
    excerpt: str = ""
    status: CMSPostStatus = CMSPostStatus.publish
    url: str = ""
    published_at: datetime | None = None
    modified_at: datetime | None = None
    author: str = ""
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    featured_image_url: str = ""
    seo_title: str = ""
    seo_description: str = ""
    word_count: int = 0
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class CMSPostCreate(BaseModel):
    """Payload for publishing a new post."""

    title: str = ""
    slug: str = ""
    content_html: str = ""
    excerpt: str = ""
    status: CMSPostStatus = CMSPostStatus.draft
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    featured_image_id: str | None = None
    seo_title: str = ""
    seo_description: str = ""
    canonical_url: str = ""
    published_at: datetime | None = None
    author: str = ""
    schema_markup: bool = False
    collection_id: str = ""


class CMSPostUpdate(BaseModel):
    """Payload for updating an existing post (content refresh).

    Only non-None fields are sent to the CMS.
    """

    title: str | None = None
    content_html: str | None = None
    excerpt: str | None = None
    slug: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    canonical_url: str | None = None
    collection_id: str = ""


class CMSPublishMetadata(BaseModel):
    """Normalized SEO/publish metadata provided by the product UI."""

    slug: str = ""
    meta_title: str = ""
    meta_description: str = ""
    canonical_url: str = ""
    schema_markup: bool = False
    publish_date: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)


# ── Categories ────────────────────────────────────────────────────────


class CMSCategory(BaseModel):
    """A category/taxonomy from the CMS."""

    cms_id: str = ""
    name: str = ""
    slug: str = ""
    parent_id: str | None = None
    post_count: int = 0


# ── Media ─────────────────────────────────────────────────────────────


class CMSMediaUpload(BaseModel):
    """Payload for uploading an image to the CMS media library."""

    filename: str = ""
    content_bytes: bytes = b""
    mime_type: str = "image/png"
    alt_text: str = ""


class CMSMediaResult(BaseModel):
    """Result of a media upload."""

    cms_id: str = ""
    url: str = ""
    filename: str = ""
