"""Tests for AuthRepository."""
from __future__ import annotations

import os

import pytest

from core.db.enums import UserRole
from core.db.repositories.auth_repo import AuthRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


async def test_create_and_get_by_email(db_session, sample_company):
    """create() then get_by_email() returns the same user."""
    repo = AuthRepository(db_session)
    user = await repo.create(
        company_id=sample_company.id,
        email="auth-test@example.com",
        password_hash="argon2_hash_here",
        role=UserRole.member,
    )

    fetched = await repo.get_by_email("auth-test@example.com")
    assert fetched is not None
    assert fetched.id == user.id
    assert fetched.email == "auth-test@example.com"
    assert fetched.role == UserRole.member


async def test_list_by_company_filters_correctly(db_session):
    """list_by_company() returns only users belonging to that company."""
    from core.db.models.organization import CompanyModel

    repo = AuthRepository(db_session)

    co_a = CompanyModel(slug="co-a", name="Co A", domain="co-a.com")
    co_b = CompanyModel(slug="co-b", name="Co B", domain="co-b.com")
    db_session.add_all([co_a, co_b])
    await db_session.flush()

    user_a = await repo.create(
        company_id=co_a.id,
        email="user-a@co-a.com",
        password_hash="hash",
        role=UserRole.member,
    )
    user_b = await repo.create(
        company_id=co_b.id,
        email="user-b@co-b.com",
        password_hash="hash",
        role=UserRole.member,
    )

    co_a_users = await repo.list_by_company(co_a.id)
    co_a_ids = [u.id for u in co_a_users]

    assert user_a.id in co_a_ids
    assert user_b.id not in co_a_ids


async def test_count_superusers(db_session, sample_company):
    """count_superusers() counts active superusers in a company."""
    repo = AuthRepository(db_session)

    # sample_user (from conftest) is a superuser, but it's a separate fixture.
    # Create users explicitly for this test.
    await repo.create(
        company_id=sample_company.id,
        email="su1@test.com",
        password_hash="hash",
        role=UserRole.superuser,
    )
    await repo.create(
        company_id=sample_company.id,
        email="su2@test.com",
        password_hash="hash",
        role=UserRole.superuser,
    )
    await repo.create(
        company_id=sample_company.id,
        email="member1@test.com",
        password_hash="hash",
        role=UserRole.member,
    )
    # Inactive superuser should NOT be counted
    inactive_su = await repo.create(
        company_id=sample_company.id,
        email="su-inactive@test.com",
        password_hash="hash",
        role=UserRole.superuser,
        is_active=False,
    )

    count = await repo.count_superusers(sample_company.id)
    assert count == 2


async def test_deactivate_sets_is_active_false(db_session, sample_company):
    """deactivate() sets is_active=False and returns the updated user."""
    repo = AuthRepository(db_session)

    user = await repo.create(
        company_id=sample_company.id,
        email="deactivate-me@test.com",
        password_hash="hash",
        role=UserRole.member,
    )
    assert user.is_active is True

    deactivated = await repo.deactivate(user.id)
    assert deactivated is not None
    assert deactivated.is_active is False
