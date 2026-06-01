"""Test-only workspace service backed by AuthStore."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from core.auth.utils.domain import derive_slug
from core.models.organization import Company, UserProfile
from core.models.workspace import (
    Workspace,
    WorkspaceMemberSummary,
    WorkspaceMembership,
    WorkspaceProductSummary,
    WorkspaceProfile,
    WorkspaceResearchSummary,
    WorkspaceSummary,
)

if TYPE_CHECKING:
    from api.auth.store import AuthStore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _legacy_role(user_role: str) -> str:
    if user_role == "superuser":
        return "owner"
    if user_role == "viewer":
        return "viewer"
    return "member"


class TestWorkspaceService:
    """Async adapter that maps AuthStore companies to workspaces for API tests."""

    def __init__(self, store: AuthStore) -> None:
        self._store = store
        self._extra_memberships: Dict[str, Set[str]] = {}
        self._archived_slugs: Set[str] = set()
        self._membership_roles: Dict[str, Dict[str, str]] = {}

    def _get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get_user_by_id(user_id)

    def _company_for_slug(self, slug: str) -> Optional[Company]:
        return self._store.get_company_by_slug(slug)

    def _user_can_access(self, user_id: str, company: Company) -> bool:
        user = self._get_user(user_id)
        if user is None:
            return False
        if user.get("company_id") == company.id:
            return True
        return slug_in_extra(user_id, company.slug, self._extra_memberships)

    def _role_for_user(self, user_id: str, company: Company) -> str:
        override = self._membership_roles.get(user_id, {}).get(company.slug)
        if override:
            return override
        user = self._get_user(user_id)
        return _legacy_role(user.get("role", "member") if user else "member")

    def _workspace_from_company(self, company: Company, *, role: str) -> Workspace:
        return Workspace(
            id=company.id,
            company_id=company.id,
            slug=company.slug,
            name=company.name,
            primary_domain=company.domain,
            additional_domains=company.additional_domains,
            industry=company.industry,
            color="#5BA4C4",
            created_at=company.created_at,
            updated_at=company.updated_at,
        )

    async def list_workspaces_for_user(
        self, user_id: str, *, include_archived: bool = False
    ) -> List[WorkspaceSummary]:
        summaries: List[WorkspaceSummary] = []
        for company in self._store.list_companies():
            if not include_archived and company.slug in self._archived_slugs:
                continue
            if not self._user_can_access(user_id, company):
                continue
            role = self._role_for_user(user_id, company)
            summaries.append(
                WorkspaceSummary(
                    id=company.id,
                    slug=company.slug,
                    name=company.name,
                    primary_domain=company.domain,
                    role=role,
                    is_archived=company.slug in self._archived_slugs,
                )
            )
        return summaries

    async def get_workspace_by_slug(self, slug: str) -> Optional[Workspace]:
        company = self._company_for_slug(slug)
        if company is None:
            return None
        workspace = self._workspace_from_company(company, role="member")
        workspace.is_archived = slug in self._archived_slugs
        return workspace

    async def get_active_membership(
        self, workspace_slug: str, user_id: str
    ) -> Optional[WorkspaceMembership]:
        company = self._company_for_slug(workspace_slug)
        if company is None or not self._user_can_access(user_id, company):
            return None
        role = self._role_for_user(user_id, company)
        now = _utcnow()
        return WorkspaceMembership(
            id="test-membership",
            workspace_id=company.id,
            user_id=user_id,
            role=role,
            status="active",
            invited_at=None,
            joined_at=now,
            created_at=now,
            updated_at=now,
        )

    async def assert_workspace_access(
        self,
        workspace_slug: str,
        user: UserProfile,
        *,
        min_roles: Optional[tuple[str, ...]] = None,
    ) -> Tuple[Workspace, WorkspaceMembership]:
        company = self._company_for_slug(workspace_slug)
        if company is None:
            raise ValueError("workspace_not_found")
        if not self._user_can_access(user.id, company):
            raise ValueError("access_denied")
        membership = await self.get_active_membership(workspace_slug, user.id)
        assert membership is not None
        if min_roles and membership.role not in min_roles:
            raise ValueError("insufficient_role")
        return self._workspace_from_company(company, role=membership.role), membership

    async def ensure_workspace_for_company(
        self,
        company: Company,
        *,
        created_by_user_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        owner_role: str = "owner",
    ) -> Workspace:
        del created_by_user_id, owner_user_id, owner_role
        return self._workspace_from_company(company, role="owner")

    async def create_workspace(
        self,
        *,
        user: UserProfile,
        name: str,
        primary_domain: str,
        slug: Optional[str] = None,
        industry: Optional[str] = None,
        color: str = "#5BA4C4",
    ) -> Workspace:
        candidate = slug or derive_slug(name)
        company = await asyncio.to_thread(
            self._store.create_company,
            candidate,
            name,
            primary_domain,
        )
        self._extra_memberships.setdefault(user.id, set()).add(company.slug)
        self._membership_roles.setdefault(user.id, {})[company.slug] = "owner"
        workspace = self._workspace_from_company(company, role="owner")
        workspace.color = color
        workspace.industry = industry
        return workspace

    async def update_workspace(
        self, workspace_slug: str, user: UserProfile, **fields: Any
    ) -> Workspace:
        workspace, _membership = await self.assert_workspace_access(
            workspace_slug, user, min_roles=("owner", "admin")
        )
        company = self._company_for_slug(workspace_slug)
        assert company is not None
        updates = {k: v for k, v in fields.items() if v is not None}
        if "primary_domain" in updates:
            updates["domain"] = updates.pop("primary_domain")
        if updates:
            updated = await asyncio.to_thread(
                self._store.update_company, workspace_slug, **updates
            )
            return self._workspace_from_company(updated, role=_membership.role)
        return workspace

    async def archive_workspace(
        self, workspace_slug: str, user: UserProfile
    ) -> Workspace:
        workspace, _membership = await self.assert_workspace_access(
            workspace_slug, user, min_roles=("owner",)
        )
        self._archived_slugs.add(workspace_slug)
        workspace.is_archived = True
        return workspace

    async def list_members(
        self, workspace_slug: str, user: UserProfile
    ) -> List[WorkspaceMemberSummary]:
        await self.assert_workspace_access(workspace_slug, user)
        company = self._company_for_slug(workspace_slug)
        assert company is not None
        members = []
        for profile in self._store.list_users_for_company(company.id):
            members.append(
                WorkspaceMemberSummary(
                    user_id=profile.id,
                    email=profile.email,
                    first_name=profile.first_name,
                    last_name=profile.last_name,
                    role=_legacy_role(profile.role),
                    status="active",
                )
            )
        return members

    async def get_profile(
        self,
        workspace_slug: str,
        user: UserProfile,
        *,
        auth_service: Any = None,
        artifacts_root: Any = None,
        storage_backend: Any = None,
        task_store: Any = None,
    ) -> WorkspaceProfile:
        workspace, membership = await self.assert_workspace_access(
            workspace_slug, user
        )
        workspace.is_archived = workspace_slug in self._archived_slugs
        products: List[WorkspaceProductSummary] = []
        if auth_service is not None:
            company = await auth_service.get_company_by_slug(workspace_slug)
            if company and company.products:
                products = [
                    WorkspaceProductSummary(
                        slug=p.slug,
                        name=p.name,
                        domain=p.domain,
                        description=p.description,
                    )
                    for p in company.products
                ]

        research_summary = None
        has_research = False
        has_gap_analysis = False
        has_content = False
        latest_runs = {}
        running_tasks = []

        if artifacts_root is not None:
            from core.models.workspace import (
                WorkspaceLatestRunSummary,
                WorkspaceResearchSummary,
                WorkspaceRunningTaskSummary,
            )
            from core.services.company_profile_helpers import (
                build_research_summary,
                get_latest_runs,
                get_running_tasks,
                has_nested_artifacts,
            )

            research_raw = build_research_summary(
                artifacts_root, workspace_slug, backend=storage_backend
            )
            research_summary = WorkspaceResearchSummary(**research_raw)
            has_research = (
                research_summary.company_context_status != "none"
                or len(research_summary.personas) > 0
                or research_summary.style_guide_status != "none"
            )
            has_gap_analysis = has_nested_artifacts(
                artifacts_root, "gap_analysis", workspace_slug, backend=storage_backend
            )
            has_content = has_nested_artifacts(
                artifacts_root, "content", workspace_slug, backend=storage_backend
            )

        if task_store is not None:
            from core.models.workspace import (
                WorkspaceLatestRunSummary,
                WorkspaceRunningTaskSummary,
            )
            from core.services.company_profile_helpers import (
                get_latest_runs,
                get_running_tasks,
            )

            latest_runs = {
                key: WorkspaceLatestRunSummary(**value)
                for key, value in get_latest_runs(task_store, workspace_slug).items()
                if value is not None
            }
            running_tasks = [
                WorkspaceRunningTaskSummary(**item)
                for item in get_running_tasks(task_store, workspace_slug)
            ]

        return WorkspaceProfile(
            id=workspace.id,
            slug=workspace.slug,
            name=workspace.name,
            primary_domain=workspace.primary_domain,
            additional_domains=workspace.additional_domains,
            industry=workspace.industry,
            color=workspace.color,
            logo_url=workspace.logo_url,
            role=membership.role,
            is_archived=workspace.is_archived,
            products=products,
            has_research=has_research,
            has_gap_analysis=has_gap_analysis,
            has_content=has_content,
            research_summary=research_summary or WorkspaceResearchSummary(),
            latest_runs=latest_runs,
            running_tasks=running_tasks,
        )


def slug_in_extra(
    user_id: str, slug: str, extra_memberships: Dict[str, Set[str]]
) -> bool:
    return slug in extra_memberships.get(user_id, set())
