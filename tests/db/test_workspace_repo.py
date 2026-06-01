"""Tests for workspace repositories."""
from __future__ import annotations

import pytest

from tests.db.conftest import pytestmark  # noqa: F401

from core.db.enums import MembershipStatus, UserRole, WorkspaceRole
from core.db.models.workspace import WorkspaceModel
from core.db.repositories.workspace_repo import (
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)


@pytest.mark.asyncio
async def test_create_workspace_and_membership(db_session, sample_company, sample_user):
    workspace_repo = WorkspaceRepository(db_session)
    membership_repo = WorkspaceMembershipRepository(db_session)

    workspace = await workspace_repo.create(
        id=sample_company.id,
        company_id=sample_company.id,
        slug=sample_company.slug,
        name=sample_company.name,
        primary_domain=sample_company.domain,
    )
    membership = await membership_repo.create(
        workspace_id=workspace.id,
        user_id=sample_user.id,
        role=WorkspaceRole.owner,
        status=MembershipStatus.active,
    )

    assert workspace.slug == "test-co"
    assert membership.role == WorkspaceRole.owner

    listed = await workspace_repo.list_for_user(sample_user.id)
    assert len(listed) == 1
    assert listed[0].id == workspace.id


@pytest.mark.asyncio
async def test_get_by_slug(db_session, sample_company):
    workspace_repo = WorkspaceRepository(db_session)
    await workspace_repo.create(
        id=sample_company.id,
        company_id=sample_company.id,
        slug="acme",
        name="Acme",
        primary_domain="acme.com",
    )
    found = await workspace_repo.get_by_slug("acme")
    assert found is not None
    assert found.name == "Acme"
