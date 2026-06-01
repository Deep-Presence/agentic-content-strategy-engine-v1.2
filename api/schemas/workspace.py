"""Workspace API request/response schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from core.models.workspace import (
    WorkspaceArtifactStatus,
    WorkspaceIntegrationsSummary,
    WorkspaceMemberSummary,
    WorkspaceProfile,
    WorkspaceSummary,
)


class WorkspaceListResponse(BaseModel):
    workspaces: List[WorkspaceSummary] = Field(default_factory=list)


class WorkspaceCreateRequest(BaseModel):
    name: str = ""
    primary_domain: str = ""
    slug: Optional[str] = None
    industry: Optional[str] = None
    color: str = "#5BA4C4"

    @model_validator(mode="after")
    def _require_identity(self) -> "WorkspaceCreateRequest":
        if not self.name.strip():
            raise ValueError("Workspace name is required")
        if not self.primary_domain.strip():
            raise ValueError("Primary domain is required")
        return self


class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = None
    primary_domain: Optional[str] = None
    additional_domains: Optional[List[str]] = None
    industry: Optional[str] = None
    color: Optional[str] = None
    logo_url: Optional[str] = None
    avatar_key: Optional[str] = None
    description: Optional[str] = None
    settings_json: Optional[Dict[str, Any]] = None


class WorkspaceDetailResponse(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    primary_domain: str = ""
    additional_domains: List[str] = Field(default_factory=list)
    industry: Optional[str] = None
    color: str = "#5BA4C4"
    logo_url: Optional[str] = None
    avatar_key: Optional[str] = None
    description: Optional[str] = None
    settings_json: Dict[str, Any] = Field(default_factory=dict)
    role: str = "member"
    is_archived: bool = False


class WorkspaceMembersResponse(BaseModel):
    members: List[WorkspaceMemberSummary] = Field(default_factory=list)
    total: int = 0


class WorkspaceMemberUpdateRequest(BaseModel):
    """Patch workspace membership role or status (owner/admin only)."""

    role: Optional[str] = None
    status: Optional[str] = None


class WorkspaceInviteRequest(BaseModel):
    role: str = "member"

    @model_validator(mode="after")
    def _validate_role(self) -> "WorkspaceInviteRequest":
        if self.role not in {"member", "viewer"}:
            raise ValueError("Invite role must be member or viewer")
        return self


class WorkspaceInviteResponse(BaseModel):
    invite_code: str = ""
    workspace_slug: str = ""
    role: str = "member"


class WorkspaceProfileResponse(WorkspaceProfile):
    """Alias response model for GET /workspaces/{slug}/profile."""

    pass
