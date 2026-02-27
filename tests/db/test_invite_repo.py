"""Tests for InviteRepository — DB-only (auto-skip without TEST_DATABASE_URL)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from tests.db.conftest import pytestmark  # noqa: F401 (auto-skip marker)

from core.db.enums import UserRole
from core.db.models.organization import InviteModel, UserModel
from core.db.repositories.invite_repo import InviteRepository


@pytest_asyncio.fixture
async def invite_repo(db_session):
    return InviteRepository(db_session)


class TestInviteRepository:
    @pytest.mark.asyncio
    async def test_create_invite(self, invite_repo, sample_company, sample_user):
        invite = await invite_repo.create(
            company_id=sample_company.id,
            code=secrets.token_hex(8),
            role=UserRole.member,
            created_by=sample_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        assert invite.id is not None
        assert invite.code is not None
        assert invite.role == UserRole.member

    @pytest.mark.asyncio
    async def test_get_by_code(self, invite_repo, sample_company, sample_user):
        code = secrets.token_hex(8)
        await invite_repo.create(
            company_id=sample_company.id,
            code=code,
            role=UserRole.member,
            created_by=sample_user.id,
        )
        found = await invite_repo.get_by_code(code)
        assert found is not None
        assert found.code == code

    @pytest.mark.asyncio
    async def test_get_by_code_redeemed_returns_none(
        self, invite_repo, sample_company, sample_user, db_session
    ):
        code = secrets.token_hex(8)
        invite = await invite_repo.create(
            company_id=sample_company.id,
            code=code,
            role=UserRole.member,
            created_by=sample_user.id,
        )
        # Create a second user to redeem with
        redeemer = UserModel(
            company_id=sample_company.id,
            email="redeemer@test.com",
            password_hash="hash",
            role=UserRole.member,
        )
        db_session.add(redeemer)
        await db_session.flush()

        await invite_repo.mark_redeemed(invite.id, redeemer.id)
        found = await invite_repo.get_by_code(code)
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_code_expired_returns_none(
        self, invite_repo, sample_company, sample_user
    ):
        code = secrets.token_hex(8)
        await invite_repo.create(
            company_id=sample_company.id,
            code=code,
            role=UserRole.member,
            created_by=sample_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        found = await invite_repo.get_by_code(code)
        assert found is None

    @pytest.mark.asyncio
    async def test_mark_redeemed(
        self, invite_repo, sample_company, sample_user, db_session
    ):
        code = secrets.token_hex(8)
        invite = await invite_repo.create(
            company_id=sample_company.id,
            code=code,
            role=UserRole.member,
            created_by=sample_user.id,
        )
        redeemer = UserModel(
            company_id=sample_company.id,
            email="joiner@test.com",
            password_hash="hash",
            role=UserRole.member,
        )
        db_session.add(redeemer)
        await db_session.flush()

        result = await invite_repo.mark_redeemed(invite.id, redeemer.id)
        assert result is not None
        assert result.redeemed_by == redeemer.id
        assert result.redeemed_at is not None

    @pytest.mark.asyncio
    async def test_list_by_company(
        self, invite_repo, sample_company, sample_user
    ):
        for i in range(3):
            await invite_repo.create(
                company_id=sample_company.id,
                code=secrets.token_hex(8),
                role=UserRole.member,
                created_by=sample_user.id,
            )
        invites = await invite_repo.list_by_company(sample_company.id)
        assert len(invites) == 3

    @pytest.mark.asyncio
    async def test_get_by_code_no_expiration(
        self, invite_repo, sample_company, sample_user
    ):
        code = secrets.token_hex(8)
        await invite_repo.create(
            company_id=sample_company.id,
            code=code,
            role=UserRole.member,
            created_by=sample_user.id,
            # No expires_at → never expires
        )
        found = await invite_repo.get_by_code(code)
        assert found is not None
