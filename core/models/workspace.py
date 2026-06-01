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


class WorkspaceProductSummary(BaseModel):
    """Product/project row within a workspace profile."""

    slug: str
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    has_research: bool = False
    has_gap_analysis: bool = False
    has_content: bool = False


class WorkspaceResearchSummary(BaseModel):
    """Research artifact snapshot for workspace profile."""

    company_context: Optional[str] = None
    company_context_status: str = "none"
    personas: List[str] = Field(default_factory=list)
    style_guide: Optional[str] = None
    style_guide_status: str = "none"


class WorkspaceLatestRunSummary(BaseModel):
    """Summary of the most recent pipeline run."""

    run_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    summary: Optional[Dict[str, Any]] = None


class WorkspaceRunningTaskSummary(BaseModel):
    """In-flight pipeline task for workspace profile."""

    task_id: str
    pipeline: str
    status: str
    created_at: datetime
    current_step: Optional[str] = None


class WorkspaceStatsSummary(BaseModel):
    """Aggregate counts for workspace dashboard shell."""

    content_inventory_count: int = 0
    tracked_prompts_active: int = 0
    tracked_prompts_total: int = 0
    knowledge_docs_count: int = 0


class WorkspaceTopicDiscoverySummary(BaseModel):
    """Topic discovery state for workspace profile."""

    status: str = "idle"
    assignment_count: int = 0
    latest_run_id: Optional[str] = None


class WorkspaceContentStudioSummary(BaseModel):
    """Content studio queue state for workspace profile."""

    queued: int = 0
    running: int = 0
    waiting_human: int = 0
    completed: int = 0
    failed: int = 0


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
    is_archived: bool = False
    products: List[WorkspaceProductSummary] = Field(default_factory=list)
    integrations: WorkspaceIntegrationsSummary = Field(
        default_factory=WorkspaceIntegrationsSummary
    )
    artifact_status: WorkspaceArtifactStatus = Field(
        default_factory=WorkspaceArtifactStatus
    )
    has_research: bool = False
    has_gap_analysis: bool = False
    has_content: bool = False
    research_summary: WorkspaceResearchSummary = Field(
        default_factory=WorkspaceResearchSummary
    )
    latest_runs: Dict[str, WorkspaceLatestRunSummary] = Field(default_factory=dict)
    running_tasks: List[WorkspaceRunningTaskSummary] = Field(default_factory=list)
    stats: WorkspaceStatsSummary = Field(default_factory=WorkspaceStatsSummary)
    topic_discovery: WorkspaceTopicDiscoverySummary = Field(
        default_factory=WorkspaceTopicDiscoverySummary
    )
    content_studio: WorkspaceContentStudioSummary = Field(
        default_factory=WorkspaceContentStudioSummary
    )
