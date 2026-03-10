"""Tests for JsonAuthService — async wrapper around AuthStore.

Verifies:
- Protocol conformance (isinstance check)
- Behavior parity with direct AuthStore for key flows
- Async interface works correctly
"""
from __future__ import annotations

import pytest

from api.auth.store import AuthStore
from core.auth.json_service import JsonAuthService
from core.auth.service import AuthServiceProtocol
from core.models.organization import Product


@pytest.fixture
def auth_store(tmp_path):
    return AuthStore(tmp_path)


@pytest.fixture
def service(auth_store):
    return JsonAuthService(auth_store)


class TestProtocolConformance:
    def test_isinstance_check(self, service: JsonAuthService) -> None:
        assert isinstance(service, AuthServiceProtocol)


class TestRegistrationFlow:
    @pytest.mark.asyncio
    async def test_register_creates_company_and_user(
        self, service: JsonAuthService
    ) -> None:
        user, company = await service.register_user(
            first_name="Alice",
            last_name="Smith",
            email="alice@example.com",
            password="secure123",
            company_name="Acme Corp",
            company_domain="acme.com",
        )
        assert user.email == "alice@example.com"
        assert user.role == "superuser"
        assert company.slug == "acme-corp"
        assert company.domain == "acme.com"

    @pytest.mark.asyncio
    async def test_register_domain_taken(self, service: JsonAuthService) -> None:
        await service.register_user(
            first_name="A", last_name="B",
            email="a@acme.com", password="p",
            company_name="Acme", company_domain="acme.com",
        )
        with pytest.raises(ValueError, match="domain_taken"):
            await service.register_user(
                first_name="C", last_name="D",
                email="c@acme.com", password="p",
                company_name="Acme 2", company_domain="acme.com",
            )

    @pytest.mark.asyncio
    async def test_register_email_duplicate(self, service: JsonAuthService) -> None:
        await service.register_user(
            first_name="A", last_name="B",
            email="same@test.com", password="p",
            company_name="Co1", company_domain="co1.com",
        )
        with pytest.raises(ValueError, match="already exists"):
            await service.register_user(
                first_name="C", last_name="D",
                email="same@test.com", password="p",
                company_name="Co2", company_domain="co2.com",
            )


class TestLoginFlow:
    @pytest.mark.asyncio
    async def test_user_lookup_and_password_verify(
        self, service: JsonAuthService, auth_store: AuthStore
    ) -> None:
        await service.register_user(
            first_name="Bob", last_name="Jones",
            email="bob@beta.com", password="mypass",
            company_name="Beta", company_domain="beta.com",
        )
        user = await service.get_user_by_email("bob@beta.com")
        assert user is not None
        assert auth_store.verify_password("mypass", user["password_hash"])
        assert not auth_store.verify_password("wrong", user["password_hash"])


class TestInviteFlow:
    @pytest.mark.asyncio
    async def test_invite_create_and_redeem(
        self, service: JsonAuthService
    ) -> None:
        user, company = await service.register_user(
            first_name="Admin", last_name="User",
            email="admin@gamma.com", password="p",
            company_name="Gamma", company_domain="gamma.com",
        )
        code = await service.create_invite(company.slug, role="member")
        assert isinstance(code, str)
        assert len(code) == 16  # token_hex(8)

        new_user, same_company = await service.redeem_invite(
            code, "New", "Member", "new@gamma.com", "p2"
        )
        assert new_user.role == "member"
        assert new_user.company_id == company.id
        assert same_company.slug == company.slug

    @pytest.mark.asyncio
    async def test_invite_double_use(self, service: JsonAuthService) -> None:
        await service.register_user(
            first_name="A", last_name="B",
            email="a@delta.com", password="p",
            company_name="Delta", company_domain="delta.com",
        )
        code = await service.create_invite("delta", role="member")
        await service.redeem_invite(code, "C", "D", "c@delta.com", "p")
        with pytest.raises(ValueError, match="Invalid or expired"):
            await service.redeem_invite(code, "E", "F", "e@delta.com", "p")


class TestCompanyOps:
    @pytest.mark.asyncio
    async def test_get_company_by_slug(self, service: JsonAuthService) -> None:
        _, company = await service.register_user(
            first_name="A", last_name="B",
            email="a@test.com", password="p",
            company_name="Test Co", company_domain="test.com",
        )
        found = await service.get_company_by_slug(company.slug)
        assert found is not None
        assert found.slug == company.slug

    @pytest.mark.asyncio
    async def test_get_company_by_domain(self, service: JsonAuthService) -> None:
        await service.register_user(
            first_name="A", last_name="B",
            email="a@domain.com", password="p",
            company_name="Domain Co", company_domain="domain.com",
        )
        found = await service.get_company_by_domain("domain.com")
        assert found is not None
        assert found.domain == "domain.com"

    @pytest.mark.asyncio
    async def test_list_companies(self, service: JsonAuthService) -> None:
        assert await service.list_companies() == []
        await service.register_user(
            first_name="A", last_name="B",
            email="a@x.com", password="p",
            company_name="X", company_domain="x.com",
        )
        companies = await service.list_companies()
        assert len(companies) == 1


class TestProductOps:
    @pytest.mark.asyncio
    async def test_product_crud(self, service: JsonAuthService) -> None:
        _, company = await service.register_user(
            first_name="A", last_name="B",
            email="a@prod.com", password="p",
            company_name="ProdCo", company_domain="prod.com",
        )
        product = Product(
            company_id=company.id, slug="widget",
            name="Widget", domain="widget.prod.com",
        )
        added = await service.add_product(company.slug, product)
        assert added.slug == "widget"

        found = await service.get_product(company.slug, "widget")
        assert found is not None
        assert found.name == "Widget"

        updated = await service.update_product(
            company.slug, "widget", name="Widget Pro"
        )
        assert updated.name == "Widget Pro"

        removed = await service.remove_product(company.slug, "widget")
        assert removed is True
        assert await service.get_product(company.slug, "widget") is None


class TestTokenOps:
    def test_access_token_roundtrip(self, service: JsonAuthService) -> None:
        token = service.create_access_token("u1", "acme")
        payload = service.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == "u1"

    def test_stream_token_has_flag(self, service: JsonAuthService) -> None:
        token = service.create_stream_token("u2", "beta")
        payload = service.verify_token(token)
        assert payload is not None
        assert payload["stream_only"] is True


class TestPipelineDefaults:
    @pytest.mark.asyncio
    async def test_get_returns_empty_defaults(
        self, service: JsonAuthService
    ) -> None:
        defaults = await service.get_pipeline_defaults("nonexistent")
        assert defaults.platforms is None

    @pytest.mark.asyncio
    async def test_update_and_get(self, service: JsonAuthService) -> None:
        await service.register_user(
            first_name="A", last_name="B",
            email="a@pipe.com", password="p",
            company_name="PipeCo", company_domain="pipe.com",
        )
        updated = await service.update_pipeline_defaults(
            "pipeco", platforms=["openai", "claude"]
        )
        assert updated.platforms == ["openai", "claude"]
        fetched = await service.get_pipeline_defaults("pipeco")
        assert fetched.platforms == ["openai", "claude"]
