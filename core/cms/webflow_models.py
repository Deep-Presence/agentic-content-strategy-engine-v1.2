"""Webflow-specific CMS configuration models.

Stored in ``cms_connections.provider_config`` JSONB (non-secret).
Secrets (site token or OAuth tokens) stay in ``encrypted_credentials``.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class WebflowAuthKind(str, Enum):
    """How the Webflow adapter authenticates API requests."""

    site_token = "site_token"
    oauth = "oauth"


class WebflowPublishMode(str, Enum):
    """Whether creates go live immediately or stay staged until publish."""

    live_direct = "live_direct"
    staged_then_publish = "staged_then_publish"


class WebflowFieldMapping(BaseModel):
    """Maps normalized CMS fields to Webflow collection field slugs."""

    title_field: str = "name"
    slug_field: str = "slug"
    body_field: str = ""
    excerpt_field: str = ""
    seo_title_field: str = ""
    seo_description_field: str = ""
    category_field: str = ""
    tags_field: str = ""
    featured_image_field: str = ""


class WebflowCollectionConfig(BaseModel):
    """One Webflow CMS collection wired for sync and/or publish."""

    collection_id: str = ""
    collection_slug: str = ""
    display_name: str = ""
    enabled: bool = True
    is_default_publish_target: bool = False
    field_mapping: WebflowFieldMapping = Field(default_factory=WebflowFieldMapping)


class WebflowProviderConfig(BaseModel):
    """Full provider_config payload for ``CMSProvider.webflow`` connections."""

    site_id: str = ""
    auth_kind: WebflowAuthKind = WebflowAuthKind.site_token
    collections: list[WebflowCollectionConfig] = Field(default_factory=list)
    publish_mode: WebflowPublishMode = WebflowPublishMode.live_direct
    default_collection_id: str = ""
    # Reserved for OAuth (WF-5): workspace id, authorized site ids, etc.
    oauth_metadata: dict[str, Any] = Field(default_factory=dict)

    def export_provider_config(self) -> dict[str, Any]:
        """Serialize for persistence in ``cms_connections.provider_config``."""
        return self.to_provider_config()

    @model_validator(mode="after")
    def _ensure_single_default_publish_target(self) -> WebflowProviderConfig:
        defaults = [
            c for c in self.collections if c.is_default_publish_target and c.enabled
        ]
        if len(defaults) > 1:
            raise ValueError("Only one collection may be the default publish target")
        return self

    def enabled_collections(self) -> list[WebflowCollectionConfig]:
        return [c for c in self.collections if c.enabled and c.collection_id]

    def resolve_publish_collection_id(self, explicit: str = "") -> str:
        if explicit:
            return explicit
        if self.default_collection_id:
            return self.default_collection_id
        for coll in self.collections:
            if coll.is_default_publish_target and coll.enabled and coll.collection_id:
                return coll.collection_id
        enabled = self.enabled_collections()
        if enabled:
            return enabled[0].collection_id
        return ""

    def collection_by_id(self, collection_id: str) -> WebflowCollectionConfig | None:
        for coll in self.collections:
            if coll.collection_id == collection_id:
                return coll
        return None

    @classmethod
    def from_provider_config(cls, data: dict[str, Any] | None) -> WebflowProviderConfig:
        if not data:
            return cls()
        return cls.model_validate(data)

    def to_provider_config(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
