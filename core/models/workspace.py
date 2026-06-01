"""Pydantic models for workspace tenants and memberships."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


WorkspaceRoleLiteral = Literal["owner", "admin", "member", "viewer"]
MembershipStatusLiteral = Literal["active", "invited", "suspended"]


class WorkspaceSummary(BaseModel):
    """Lightweight workspace for list/selector views."""

    id: str
    slug: str
    name: str
    primary_domain: str = ""
    color: str = "#5BA4C4"
    logo_url: Optional[str] = None
    role: WorkspaceRoleLiteral = "member"
    is_archived: bool = False


class Workspace(BaseModel):
    """Full workspace metadata."""

    id: str
    company_id: str
    slug: str
    name: str
    primary_domain: str
    additional_domains: List[str] = Field(default_factory=list)
    industry: Optional[str] = None
    color: str = "#5BA4C4"
    logo_url: Optional[str] = None
    avatar_key: Optional[str] = None
    description: Optional[str] = None
    settings_json: Dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = None
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime


class WorkspaceMembership(BaseModel):
    """User membership in a workspace."""

    id: str
    workspace_id: str
    user_id: str
    role: WorkspaceRoleLiteral = "member"
    status: MembershipStatusLiteral = "active"
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberSummary(BaseModel):
    """Member row for workspace member listings."""

    user_id: str
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    role: WorkspaceRoleLiteral = "member"
    status: MembershipStatusLiteral = "active"


class WorkspaceIntegrationsSummary(BaseModel):
    """Connected integrations snapshot for workspace profile."""

    cms: Dict[str, Any] = Field(default_factory=lambda: {"connected": False})
    ga4: Dict[str, Any] = Field(default_factory=lambda: {"connected": False})


class WorkspaceArtifactStatus(BaseModel):
    """High-level pipeline/artifact readiness for dashboard shell."""

    knowledge_base: str = "missing"
    audience_personas: str = "missing"
    voice_style_guide: str = "missing"
    gap_analysis: str = "idle"
    topic_discovery: str = "idle"
    content_engine: str = "idle"


class WorkspaceProfile(BaseModel):
    """Broad workspace profile for selector + dashboard shell."""

    id: str
    slug: str
    name: str
    primary_domain: str
    additional_domains: List[str] = Field(default_factory=list)
    industry: Optional[str] = None
    color: str = "#5BA4C4"
    logo_url: Optional[str] = None
    role: WorkspaceRoleLiteral = "member"
    products: List[Dict[str, Any]] = Field(default_factory=list)
    integrations: WorkspaceIntegrationsSummary = Field(
        default_factory=WorkspaceIntegrationsSummary
    )
    artifact_status: WorkspaceArtifactStatus = Field(
        default_factory=WorkspaceArtifactStatus
    )
