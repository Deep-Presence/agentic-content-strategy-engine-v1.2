"""Workspace service protocol."""
from __future__ import annotations

from typing import Any, List, Optional, Protocol, Tuple, runtime_checkable

from core.models.organization import Company, UserProfile
from core.models.workspace import (
    Workspace,
    WorkspaceMemberSummary,
    WorkspaceMembership,
    WorkspaceProfile,
    WorkspaceSummary,
)


@runtime_checkable
class WorkspaceServiceProtocol(Protocol):
    """Async workspace tenant operations."""

    async def list_workspaces_for_user(
        self, user_id: str, *, include_archived: bool = False
    ) -> List[WorkspaceSummary]: ...

    async def get_workspace_by_slug(self, slug: str) -> Optional[Workspace]: ...

    async def get_active_membership(
        self, workspace_slug: str, user_id: str
    ) -> Optional[WorkspaceMembership]: ...

    async def assert_workspace_access(
        self,
        workspace_slug: str,
        user: UserProfile,
        *,
        min_roles: Optional[tuple[str, ...]] = None,
    ) -> Tuple[Workspace, WorkspaceMembership]: ...

    async def create_workspace(
        self,
        *,
        user: UserProfile,
        name: str,
        primary_domain: str,
        slug: Optional[str] = None,
        industry: Optional[str] = None,
        color: str = "#5BA4C4",
    ) -> Workspace: ...

    async def update_workspace(
        self, workspace_slug: str, user: UserProfile, **fields: Any
    ) -> Workspace: ...

    async def archive_workspace(
        self, workspace_slug: str, user: UserProfile
    ) -> Workspace: ...

    async def list_members(
        self, workspace_slug: str, user: UserProfile
    ) -> List[WorkspaceMemberSummary]: ...

    async def get_profile(
        self,
        workspace_slug: str,
        user: UserProfile,
        *,
        auth_service: Any = None,
        artifacts_root: Any = None,
        storage_backend: Any = None,
        task_store: Any = None,
    ) -> WorkspaceProfile: ...

    async def ensure_workspace_for_company(
        self,
        company: Company,
        *,
        created_by_user_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        owner_role: str = "owner",
    ) -> Workspace: ...
