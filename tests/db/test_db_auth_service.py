"""Tests for DbAuthService — DB-only (auto-skip without TEST_DATABASE_URL)."""
from __future__ import annotations

import pytest
import pytest_asyncio

from tests.db.conftest import pytestmark  # noqa: F401 (auto-skip marker)

from core.auth.db_service import DbAuthService
from core.auth.service import AuthServiceProtocol
from core.auth.utils.passwords import verify_password
from core.auth.utils.tokens import get_secret_key
from core.db.repositories.auth_repo import AuthRepository
from core.db.repositories.company_repo import CompanyRepository
from core.db.repositories.invite_repo import InviteRepository
from core.db.repositories.pipeline_defaults_repo import PipelineDefaultsRepository
from core.db.repositories.product_repo import ProductRepository
from core.models.organization import Product


@pytest_asyncio.fixture
async def db_auth_service(db_session):
    return DbAuthService(
        company_repo=CompanyRepository(db_session),
        auth_repo=AuthRepository(db_session),
        invite_repo=InviteRepository(db_session),
        product_repo=ProductRepository(db_session),
        defaults_repo=PipelineDefaultsRepository(db_session),
        secret_key="test-secret-for-db-tests",
    )


class TestProtocolConformance:
    def test_isinstance_check(self, db_auth_service):
        assert isinstance(db_auth_service, AuthServiceProtocol)


class TestRegistration:
    @pytest.mark.asyncio
    async def test_register_happy_path(self, db_auth_service):
        user, company = await db_auth_service.register_user(
            first_name="Alice",
            last_name="Smith",
            email="alice@acme.com",
            password="secure123",
            company_name="Acme Corp",
            company_domain="acme.com",
        )
        assert user.email == "alice@acme.com"
        assert user.role == "superuser"
        assert company.slug == "acme-corp"
        assert company.domain == "acme.com"

    @pytest.mark.asyncio
    async def test_register_domain_taken(self, db_auth_service):
        await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="a@example.com", password="p",
            company_name="Example", company_domain="example.com",
        )
        with pytest.raises(ValueError, match="domain_taken"):
            await db_auth_service.register_user(
                first_name="C", last_name="D",
                email="c@example.com", password="p",
                company_name="Example 2", company_domain="example.com",
            )

    @pytest.mark.asyncio
    async def test_register_email_duplicate(self, db_auth_service):
        await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="dup@test.com", password="p",
            company_name="Co1", company_domain="co1.com",
        )
        with pytest.raises(ValueError, match="already exists"):
            await db_auth_service.register_user(
                first_name="C", last_name="D",
                email="dup@test.com", password="p",
                company_name="Co2", company_domain="co2.com",
            )

    @pytest.mark.asyncio
    async def test_register_slug_collision(self, db_auth_service):
        await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="a@same.com", password="p",
            company_name="Same Name", company_domain="same1.com",
        )
        _, company2 = await db_auth_service.register_user(
            first_name="C", last_name="D",
            email="c@same.com", password="p",
            company_name="Same Name", company_domain="same2.com",
        )
        assert company2.slug == "same-name-1"

    @pytest.mark.asyncio
    async def test_register_normalizes_domain(self, db_auth_service):
        user, company = await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="a@norm.com", password="p",
            company_name="Norm Co", company_domain="https://www.norm.com/about",
        )
        assert company.domain == "norm.com"


class TestLogin:
    @pytest.mark.asyncio
    async def test_user_lookup_and_verify(self, db_auth_service):
        await db_auth_service.register_user(
            first_name="Bob", last_name="J",
            email="bob@login.com", password="mypass",
            company_name="LoginCo", company_domain="login.com",
        )
        user = await db_auth_service.get_user_by_email("bob@login.com")
        assert user is not None
        assert verify_password("mypass", user["password_hash"])
        assert not verify_password("wrong", user["password_hash"])

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_auth_service):
        user, _ = await db_auth_service.register_user(
            first_name="Id", last_name="User",
            email="id@test.com", password="p",
            company_name="IdCo", company_domain="id.com",
        )
        found = await db_auth_service.get_user_by_id(user.id)
        assert found is not None
        assert found["email"] == "id@test.com"


class TestInviteFlow:
    @pytest.mark.asyncio
    async def test_create_and_redeem(self, db_auth_service):
        _, company = await db_auth_service.register_user(
            first_name="Admin", last_name="A",
            email="admin@inv.com", password="p",
            company_name="InvCo", company_domain="inv.com",
        )
        code = await db_auth_service.create_invite(company.slug, role="member")
        assert isinstance(code, str) and len(code) == 16

        new_user, same_company = await db_auth_service.redeem_invite(
            code, "New", "User", "new@inv.com", "p2"
        )
        assert new_user.role == "member"
        assert new_user.company_id == company.id

    @pytest.mark.asyncio
    async def test_double_use_prevention(self, db_auth_service):
        _, company = await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="a@dup.com", password="p",
            company_name="DupCo", company_domain="dup.com",
        )
        code = await db_auth_service.create_invite(company.slug)
        await db_auth_service.redeem_invite(code, "C", "D", "c@dup.com", "p")
        with pytest.raises(ValueError, match="Invalid or expired"):
            await db_auth_service.redeem_invite(code, "E", "F", "e@dup.com", "p")

    @pytest.mark.asyncio
    async def test_invalid_code(self, db_auth_service):
        with pytest.raises(ValueError, match="Invalid or expired"):
            await db_auth_service.redeem_invite("bad-code", "A", "B", "a@x.com", "p")


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_update_mutable_fields(self, db_auth_service):
        user, _ = await db_auth_service.register_user(
            first_name="Old", last_name="Name",
            email="upd@test.com", password="p",
            company_name="UpdCo", company_domain="upd.com",
        )
        updated = await db_auth_service.update_user(
            user.id, first_name="New", last_name="Updated"
        )
        assert updated.first_name == "New"
        assert updated.last_name == "Updated"

    @pytest.mark.asyncio
    async def test_self_deactivation_guard(self, db_auth_service):
        user, _ = await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="self@test.com", password="p",
            company_name="SelfCo", company_domain="self.com",
        )
        with pytest.raises(ValueError, match="Cannot deactivate your own"):
            await db_auth_service.update_user(
                user.id, requesting_user_id=user.id, is_active=False
            )

    @pytest.mark.asyncio
    async def test_last_superuser_guard(self, db_auth_service):
        user, _ = await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="last@test.com", password="p",
            company_name="LastCo", company_domain="last.com",
        )
        with pytest.raises(ValueError, match="Cannot demote the last superuser"):
            await db_auth_service.update_user(user.id, role="member")

    @pytest.mark.asyncio
    async def test_immutable_fields_ignored(self, db_auth_service):
        user, _ = await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="immut@test.com", password="p",
            company_name="ImmutCo", company_domain="immut.com",
        )
        updated = await db_auth_service.update_user(
            user.id, email="hacker@evil.com", first_name="Changed"
        )
        assert updated.email == "immut@test.com"  # email not changed
        assert updated.first_name == "Changed"  # first_name changed


class TestProductOps:
    @pytest.mark.asyncio
    async def test_product_crud(self, db_auth_service):
        _, company = await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="a@prod.com", password="p",
            company_name="ProdCo", company_domain="prod.com",
        )
        product = Product(
            company_id=company.id, slug="widget", name="Widget",
        )
        added = await db_auth_service.add_product(company.slug, product)
        assert added.slug == "widget"

        found = await db_auth_service.get_product(company.slug, "widget")
        assert found is not None
        assert found.name == "Widget"

        updated = await db_auth_service.update_product(
            company.slug, "widget", name="Widget Pro"
        )
        assert updated.name == "Widget Pro"

        removed = await db_auth_service.remove_product(company.slug, "widget")
        assert removed is True
        assert await db_auth_service.get_product(company.slug, "widget") is None


class TestPipelineDefaults:
    @pytest.mark.asyncio
    async def test_empty_defaults(self, db_auth_service):
        defaults = await db_auth_service.get_pipeline_defaults("nonexistent")
        assert defaults.platforms is None

    @pytest.mark.asyncio
    async def test_update_and_get(self, db_auth_service):
        _, company = await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="a@pipe.com", password="p",
            company_name="PipeCo", company_domain="pipe.com",
        )
        updated = await db_auth_service.update_pipeline_defaults(
            company.slug, platforms=["openai", "claude"]
        )
        assert updated.platforms == ["openai", "claude"]
        fetched = await db_auth_service.get_pipeline_defaults(company.slug)
        assert fetched.platforms == ["openai", "claude"]


class TestTokenOps:
    def test_access_token_roundtrip(self, db_auth_service):
        token = db_auth_service.create_access_token("u1", "acme")
        payload = db_auth_service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == "u1"

    def test_stream_token_has_flag(self, db_auth_service):
        token = db_auth_service.create_stream_token("u2", "beta")
        payload = db_auth_service.verify_token(token)
        assert payload is not None
        assert payload["stream_only"] is True


class TestCompanyOps:
    @pytest.mark.asyncio
    async def test_list_companies(self, db_auth_service):
        assert await db_auth_service.list_companies() == []
        await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="a@list.com", password="p",
            company_name="ListCo", company_domain="list.com",
        )
        companies = await db_auth_service.list_companies()
        assert len(companies) == 1

    @pytest.mark.asyncio
    async def test_update_company(self, db_auth_service):
        _, company = await db_auth_service.register_user(
            first_name="A", last_name="B",
            email="a@upd-co.com", password="p",
            company_name="UpdCo", company_domain="upd-co.com",
        )
        updated = await db_auth_service.update_company(
            company.slug, name="Updated Co"
        )
        assert updated.name == "Updated Co"
