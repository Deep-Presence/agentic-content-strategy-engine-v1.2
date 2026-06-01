"""Database-backed workspace tenant service."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from core.auth.utils.domain import derive_slug
from core.db.enums import MembershipStatus, UserRole, WorkspaceRole
from core.db.models.workspace import WorkspaceMembershipModel, WorkspaceModel
from core.db.repositories.auth_repo import AuthRepository
from core.db.repositories.company_repo import CompanyRepository
from core.db.repositories.workspace_repo import (
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from core.models.organization import Company, UserProfile
from core.models.workspace import (
    Workspace,
    WorkspaceMemberSummary,
    WorkspaceMembership,
    WorkspaceProductSummary,
    WorkspaceProfile,
    WorkspaceSummary,
)


_ADMIN_ROLES = frozenset({"owner", "admin"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _user_role_to_workspace_role(role: UserRole | str) -> WorkspaceRole:
    value = role.value if isinstance(role, UserRole) else str(role)
    if value == "superuser":
        return WorkspaceRole.owner
    if value == "viewer":
        return WorkspaceRole.viewer
    return WorkspaceRole.member


class WorkspaceService:
    """Workspace tenant operations backed by SQLAlchemy repositories."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        membership_repo: WorkspaceMembershipRepository,
        company_repo: CompanyRepository,
        auth_repo: AuthRepository,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._membership_repo = membership_repo
        self._company_repo = company_repo
        self._auth_repo = auth_repo

    @staticmethod
    def _orm_to_workspace(model: WorkspaceModel) -> Workspace:
        return Workspace(
            id=str(model.id),
            company_id=str(model.company_id),
            slug=model.slug,
            name=model.name,
            primary_domain=model.primary_domain,
            additional_domains=model.additional_domains or [],
            industry=model.industry,
            color=model.color or "#5BA4C4",
            logo_url=model.logo_url,
            avatar_key=model.avatar_key,
            description=model.description,
            settings_json=model.settings_json or {},
            created_by=str(model.created_by) if model.created_by else None,
            is_archived=model.is_archived,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _orm_to_membership(model: WorkspaceMembershipModel) -> WorkspaceMembership:
        return WorkspaceMembership(
            id=str(model.id),
            workspace_id=str(model.workspace_id),
            user_id=str(model.user_id),
            role=model.role.value,
            status=model.status.value,
            invited_at=model.invited_at,
            joined_at=model.joined_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _membership_role_for_user(
        self, workspace: WorkspaceModel, user_id: str
    ) -> str:
        uid = _uuid.UUID(user_id)
        for membership in workspace.memberships or []:
            if membership.user_id == uid and membership.status == MembershipStatus.active:
                return membership.role.value
        return "member"

    async def list_workspaces_for_user(
        self, user_id: str, *, include_archived: bool = False
    ) -> List[WorkspaceSummary]:
        rows = await self._workspace_repo.list_for_user(
            user_id, include_archived=include_archived
        )
        return [
            WorkspaceSummary(
                id=str(row.id),
                slug=row.slug,
                name=row.name,
                primary_domain=row.primary_domain,
                color=row.color or "#5BA4C4",
                logo_url=row.logo_url,
                role=self._membership_role_for_user(row, user_id),
                is_archived=row.is_archived,
            )
            for row in rows
        ]

    async def get_workspace_by_slug(self, slug: str) -> Optional[Workspace]:
        model = await self._workspace_repo.get_by_slug(slug)
        if model is None:
            return None
        return self._orm_to_workspace(model)

    async def get_active_membership(
        self, workspace_slug: str, user_id: str
    ) -> Optional[WorkspaceMembership]:
        workspace = await self._workspace_repo.get_by_slug(workspace_slug)
        if workspace is None:
            return None
        membership = await self._membership_repo.get_membership(workspace.id, user_id)
        if membership is None or membership.status != MembershipStatus.active:
            return None
        return self._orm_to_membership(membership)

    async def assert_workspace_access(
        self,
        workspace_slug: str,
        user: UserProfile,
        *,
        min_roles: Optional[tuple[str, ...]] = None,
    ) -> Tuple[Workspace, WorkspaceMembership]:
        workspace_model = await self._workspace_repo.get_by_slug(workspace_slug)
        if workspace_model is None:
            raise ValueError("workspace_not_found")

        membership_model = await self._membership_repo.get_membership(
            workspace_model.id, user.id
        )
        if membership_model is None or membership_model.status != MembershipStatus.active:
            # Legacy fallback during transition: single-company users table
            if str(user.company_id) == str(workspace_model.company_id):
                legacy_role = _user_role_to_workspace_role(user.role)
                if min_roles and legacy_role.value not in min_roles:
                    raise ValueError("insufficient_role")
                return (
                    self._orm_to_workspace(workspace_model),
                    WorkspaceMembership(
                        id="legacy",
                        workspace_id=str(workspace_model.id),
                        user_id=user.id,
                        role=legacy_role.value,
                        status=MembershipStatus.active.value,
                        invited_at=None,
                        joined_at=None,
                        created_at=_utcnow(),
                        updated_at=_utcnow(),
                    ),
                )
            raise ValueError("access_denied")

        membership = self._orm_to_membership(membership_model)
        if min_roles and membership.role not in min_roles:
            raise ValueError("insufficient_role")

        return self._orm_to_workspace(workspace_model), membership

    async def ensure_workspace_for_company(
        self,
        company: Company,
        *,
        created_by_user_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        owner_role: str = "owner",
    ) -> Workspace:
        existing = await self._workspace_repo.get_by_company_id(company.id)
        if existing is not None:
            return self._orm_to_workspace(existing)

        company_uuid = _uuid.UUID(company.id)
        workspace_model = await self._workspace_repo.create(
            id=company_uuid,
            company_id=company_uuid,
            slug=company.slug,
            name=company.name,
            primary_domain=company.domain,
            additional_domains=company.additional_domains or [],
            industry=company.industry,
            created_by=_uuid.UUID(created_by_user_id) if created_by_user_id else None,
        )
        if owner_user_id:
            await self._membership_repo.create(
                workspace_id=workspace_model.id,
                user_id=_uuid.UUID(owner_user_id),
                role=WorkspaceRole(owner_role),
                status=MembershipStatus.active,
                joined_at=_utcnow(),
            )
        return self._orm_to_workspace(workspace_model)

    async def ensure_workspace_membership(
        self,
        workspace_slug: str,
        user_id: str,
        *,
        role: str = "member",
    ) -> WorkspaceMembership:
        workspace_model = await self._workspace_repo.get_by_slug(workspace_slug)
        if workspace_model is None:
            raise ValueError("workspace_not_found")

        user_uuid = _uuid.UUID(user_id)
        membership = await self._membership_repo.get_membership(
            workspace_model.id,
            user_uuid,
        )
        if membership is not None:
            membership.role = WorkspaceRole(role)
            membership.status = MembershipStatus.active
            if membership.joined_at is None:
                membership.joined_at = _utcnow()
            await self._membership_repo._session.flush()
            return self._orm_to_membership(membership)

        created = await self._membership_repo.create(
            workspace_id=workspace_model.id,
            user_id=user_uuid,
            role=WorkspaceRole(role),
            status=MembershipStatus.active,
            joined_at=_utcnow(),
        )
        return self._orm_to_membership(created)

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
        base_slug = candidate
        counter = 1
        while await self._workspace_repo.slug_exists(candidate):
            candidate = f"{base_slug}-{counter}"
            counter += 1

        company_model = await self._company_repo.create(
            slug=candidate,
            name=name,
            domain=primary_domain,
            industry=industry,
        )
        workspace_model = await self._workspace_repo.create(
            id=company_model.id,
            company_id=company_model.id,
            slug=candidate,
            name=name,
            primary_domain=primary_domain,
            industry=industry,
            color=color,
            created_by=_uuid.UUID(user.id),
        )
        await self._membership_repo.create(
            workspace_id=workspace_model.id,
            user_id=_uuid.UUID(user.id),
            role=WorkspaceRole.owner,
            status=MembershipStatus.active,
            joined_at=_utcnow(),
        )
        return self._orm_to_workspace(workspace_model)

    async def update_workspace(
        self, workspace_slug: str, user: UserProfile, **fields: Any
    ) -> Workspace:
        workspace, _membership = await self.assert_workspace_access(
            workspace_slug, user, min_roles=tuple(_ADMIN_ROLES)
        )
        allowed = {
            "name",
            "primary_domain",
            "additional_domains",
            "industry",
            "color",
            "logo_url",
            "avatar_key",
            "description",
            "settings_json",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return workspace

        model = await self._workspace_repo.update(workspace.id, **updates)
        assert model is not None

        company_updates: dict[str, Any] = {}
        if "name" in updates:
            company_updates["name"] = updates["name"]
        if "primary_domain" in updates:
            company_updates["domain"] = updates["primary_domain"]
        if "additional_domains" in updates:
            company_updates["additional_domains"] = updates["additional_domains"]
        if "industry" in updates:
            company_updates["industry"] = updates["industry"]
        if company_updates:
            company = await self._company_repo.get_by_slug(workspace_slug)
            if company is not None:
                for key, value in company_updates.items():
                    setattr(company, key, value)
                await self._company_repo._session.flush()

        return self._orm_to_workspace(model)

    async def archive_workspace(
        self, workspace_slug: str, user: UserProfile
    ) -> Workspace:
        workspace, _membership = await self.assert_workspace_access(
            workspace_slug, user, min_roles=("owner",)
        )
        model = await self._workspace_repo.update(
            workspace.id, is_archived=True
        )
        assert model is not None
        company = await self._company_repo.get_by_slug(workspace_slug)
        if company is not None:
            company.is_archived = True
            await self._company_repo._session.flush()
        return self._orm_to_workspace(model)

    async def list_members(
        self, workspace_slug: str, user: UserProfile
    ) -> List[WorkspaceMemberSummary]:
        await self.assert_workspace_access(workspace_slug, user)
        workspace = await self._workspace_repo.get_by_slug(workspace_slug)
        assert workspace is not None
        memberships = await self._membership_repo.list_for_workspace(workspace.id)
        members: List[WorkspaceMemberSummary] = []
        for membership in memberships:
            user_model = await self._auth_repo.get_by_id(str(membership.user_id))
            if user_model is None:
                continue
            members.append(
                WorkspaceMemberSummary(
                    user_id=str(user_model.id),
                    email=user_model.email,
                    first_name=user_model.first_name,
                    last_name=user_model.last_name,
                    role=membership.role.value,
                    status=membership.status.value,
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
        from core.services.workspace_profile_service import WorkspaceProfileService

        profile_service = WorkspaceProfileService(self._workspace_repo._session)
        return await profile_service.get_profile(
            workspace_slug,
            workspace=workspace,
            membership=membership,
            auth_service=auth_service,
            artifacts_root=artifacts_root,
            storage_backend=storage_backend,
            task_store=task_store,
        )
