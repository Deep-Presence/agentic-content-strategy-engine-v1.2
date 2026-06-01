"""CMS integration request/response schemas.

All fields have defaults for backward compatibility (Pydantic v2 strict).
UUIDs are serialized as ``str`` (D2: UUIDPKMixin).
``site_url`` is ``str``, NOT ``HttpUrl`` (D9: Pydantic v2 HttpUrl serializes to Url object).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from api.schemas.content_data import ContentPublishMetadata


# ── Request Schemas ───────────────────────────────────────────────────


class CMSConnectRequest(BaseModel):
    """Credentials for connecting a CMS."""

    provider: str  # "wordpress", "webflow", etc.
    site_url: str  # NOT HttpUrl — D9
    username: str = ""
    api_key: str
    provider_config: dict[str, Any] | None = None


class CMSPublishRequest(BaseModel):
    """Publish a Content Engine brief to the connected CMS."""

    brief_id: str
    effective_slug: Optional[str] = None
    product_slug: Optional[str] = None
    status: str = "draft"  # "draft" | "publish"
    slug_override: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    publish_metadata: Optional[ContentPublishMetadata] = None
    collection_id: Optional[str] = None


class CMSRefreshRequest(BaseModel):
    """Refresh an existing CMS post with new content."""

    brief_id: str
    effective_slug: Optional[str] = None
    product_slug: Optional[str] = None


class CMSStaleToTriageRequest(BaseModel):
    """Queue a stale post for content refresh."""

    cms_synced_post_id: str  # UUID string (D2)


# ── Response Schemas ──────────────────────────────────────────────────


class CMSConnectResponse(BaseModel):
    """Result of CMS connection attempt."""

    connected: bool = False
    site_name: str = ""
    site_url: str = ""
    cms_version: str = ""
    user_display_name: str = ""
    error: Optional[str] = None
    sync_task_id: Optional[str] = None  # Set when auto-sync is triggered on first connect


class CMSConnectionInfoResponse(BaseModel):
    """Current CMS connection info for a company."""

    provider: str = ""
    site_url: str = ""
    site_name: str = ""
    cms_version: str = ""
    user_display_name: str = ""
    is_active: bool = False
    last_sync_at: Optional[datetime] = None
    sync_post_count: int = 0
    provider_config: dict[str, Any] = Field(default_factory=dict)


class CMSPublishResponse(BaseModel):
    """Result of publishing/refreshing a post to CMS."""

    cms_post_id: str = ""
    url: str = ""
    slug: str = ""
    title: str = ""
    status: str = ""
    word_count: int = 0


class CMSSyncedPostSummary(BaseModel):
    """Summary of a synced CMS post."""

    id: str = ""  # UUID string
    cms_post_id: str = ""
    title: str = ""
    slug: str = ""
    url: str = ""
    word_count: int = 0
    published_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    is_stale: bool = False
    staleness_days: int = 0
    categories: list[str] = Field(default_factory=list)
    queued_for_refresh: bool = False


class StaleContentAction(BaseModel):
    """A stale content card for the Home dashboard Recommended Actions."""

    cms_synced_post_id: str = ""  # UUID string
    cms_post_id: str = ""
    title: str = ""
    url: str = ""
    staleness_days: int = 0
    description: str = ""
    queued_for_refresh: bool = False


class StaleToTriageResponse(BaseModel):
    """Result of queuing a stale post for refresh."""

    brief_id: str = ""
    title: str = ""
    status: str = "triage"
    warning: str = ""  # Non-empty when triage tile creation failed


class CMSPublishHistoryItem(BaseModel):
    """A single publish/refresh record."""

    id: str = ""  # UUID string
    brief_id: str = ""
    effective_slug: str = ""
    cms_post_id: str = ""
    cms_post_url: str = ""
    cms_post_slug: str = ""
    action: str = ""  # "create" | "update" | "refresh"
    status_at_publish: str = ""
    published_at: Optional[datetime] = None
    title_published: str = ""
    word_count: int = 0


class CMSCategoryItem(BaseModel):
    """A CMS category (for publish UI category selector)."""

    cms_id: str = ""
    name: str = ""
    slug: str = ""
    parent_id: Optional[str] = None
    post_count: int = 0


# ── Webflow configure (WF-2) ──────────────────────────────────────────


class WebflowFieldMappingResponse(BaseModel):
    """Normalized ↔ Webflow field slug mapping for one collection."""

    title_field: str = "name"
    slug_field: str = "slug"
    body_field: str = ""
    excerpt_field: str = ""
    seo_title_field: str = ""
    seo_description_field: str = ""
    category_field: str = ""
    tags_field: str = ""
    featured_image_field: str = ""


class WebflowCollectionSummary(BaseModel):
    """Webflow CMS collection available on the connected site."""

    collection_id: str = ""
    collection_slug: str = ""
    display_name: str = ""
    singular_name: str = ""


class WebflowFieldSchemaItem(BaseModel):
    """One field from a Webflow collection schema."""

    slug: str = ""
    display_name: str = ""
    field_type: str = ""
    is_required: bool = False


class WebflowCollectionFieldsResponse(BaseModel):
    """Collection schema + heuristic mapping suggestion for the configure UI."""

    collection_id: str = ""
    fields: list[WebflowFieldSchemaItem] = Field(default_factory=list)
    suggested_mapping: WebflowFieldMappingResponse = Field(
        default_factory=WebflowFieldMappingResponse
    )


class WebflowCollectionConfigInput(BaseModel):
    """One collection entry in a configure request."""

    collection_id: str = ""
    collection_slug: str = ""
    display_name: str = ""
    enabled: bool = True
    is_default_publish_target: bool = False
    field_mapping: WebflowFieldMappingResponse = Field(
        default_factory=WebflowFieldMappingResponse
    )


class WebflowConfigureRequest(BaseModel):
    """Save Webflow multi-collection config after the connect wizard."""

    site_id: str = ""
    collections: list[WebflowCollectionConfigInput] = Field(default_factory=list)
    publish_mode: str = "live_direct"
    default_collection_id: str = ""
    trigger_sync: bool = True


class WebflowConfigureResponse(BaseModel):
    """Result of saving Webflow provider_config."""

    configured: bool = True
    provider_config: dict[str, Any] = Field(default_factory=dict)
    sync_task_id: Optional[str] = None
