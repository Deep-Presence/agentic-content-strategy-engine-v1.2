"""TDD tests for user registration with company deduplication.

Tests cover:
- Domain normalization (www stripping, subdomain extraction, root domain)
- Company deduplication by normalized domain
- First user gets superuser role, subsequent users get member
- Subdomain preservation in additional_domains
- Registration endpoint (POST /api/v1/auth/register)
- Duplicate email rejection
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.auth.store import AuthStore, normalize_domain


# ── Domain normalization ──────────────────────────────────────────


class TestNormalizeDomain:
    """Test the normalize_domain() utility function."""

    def test_plain_domain_unchanged(self) -> None:
        root, sub = normalize_domain("ramp.com")
        assert root == "ramp.com"
        assert sub is None

    def test_www_stripped(self) -> None:
        root, sub = normalize_domain("www.ramp.com")
        assert root == "ramp.com"
        assert sub is None  # www is not a meaningful subdomain

    def test_subdomain_extracted(self) -> None:
        root, sub = normalize_domain("app.ramp.com")
        assert root == "ramp.com"
        assert sub == "app.ramp.com"

    def test_deep_subdomain_extracted(self) -> None:
        root, sub = normalize_domain("dashboard.app.ramp.com")
        assert root == "ramp.com"
        assert sub == "dashboard.app.ramp.com"

    def test_uppercase_normalized(self) -> None:
        root, sub = normalize_domain("APP.Ramp.COM")
        assert root == "ramp.com"
        assert sub == "app.ramp.com"

    def test_trailing_slash_stripped(self) -> None:
        root, sub = normalize_domain("ramp.com/")
        assert root == "ramp.com"

    def test_https_prefix_stripped(self) -> None:
        root, sub = normalize_domain("https://ramp.com")
        assert root == "ramp.com"

    def test_http_prefix_stripped(self) -> None:
        root, sub = normalize_domain("http://www.ramp.com/path")
        assert root == "ramp.com"

    def test_co_uk_tld_preserved(self) -> None:
        """Multi-part TLDs like .co.uk should be handled correctly."""
        root, sub = normalize_domain("app.example.co.uk")
        assert root == "example.co.uk"
        assert sub == "app.example.co.uk"

    def test_io_tld(self) -> None:
        root, sub = normalize_domain("api.linear.app")
        assert root == "linear.app"
        assert sub == "api.linear.app"


# ── Company deduplication during registration ─────────────────────


class TestCompanyDeduplication:
    """Test that register_user correctly deduplicates companies by domain."""

    def test_first_user_creates_company_as_superuser(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        user, company = store.register_user(
            first_name="Aryan",
            last_name="Keshri",
            email="aryan@ramp.com",
            password="securepass",
            company_name="Ramp",
            company_domain="ramp.com",
        )

        assert user.role == "superuser"
        assert user.first_name == "Aryan"
        assert user.last_name == "Keshri"
        assert company.name == "Ramp"
        assert company.domain == "ramp.com"

    def test_second_user_joins_existing_company_as_member(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)

        user1, company1 = store.register_user(
            first_name="Aryan",
            last_name="Keshri",
            email="aryan@ramp.com",
            password="pass1",
            company_name="Ramp",
            company_domain="ramp.com",
        )

        user2, company2 = store.register_user(
            first_name="Jane",
            last_name="Doe",
            email="jane@ramp.com",
            password="pass2",
            company_name="Ramp",
            company_domain="ramp.com",
        )

        assert user1.role == "superuser"
        assert user2.role == "member"
        assert company1.id == company2.id  # Same company

    def test_subdomain_matches_existing_company(self, tmp_path: Path) -> None:
        """app.ramp.com should match an existing ramp.com company."""
        store = AuthStore(base_dir=tmp_path)

        _, c1 = store.register_user(
            first_name="A",
            last_name="K",
            email="a@ramp.com",
            password="p1",
            company_name="Ramp",
            company_domain="ramp.com",
        )

        _, c2 = store.register_user(
            first_name="B",
            last_name="L",
            email="b@ramp.com",
            password="p2",
            company_name="Ramp",
            company_domain="app.ramp.com",
        )

        assert c1.id == c2.id
        # The subdomain should be saved in additional_domains
        assert "app.ramp.com" in c2.additional_domains

    def test_www_matches_existing_company(self, tmp_path: Path) -> None:
        """www.ramp.com should match ramp.com (www stripped, not saved as subdomain)."""
        store = AuthStore(base_dir=tmp_path)

        _, c1 = store.register_user(
            first_name="A",
            last_name="K",
            email="a@ramp.com",
            password="p1",
            company_name="Ramp",
            company_domain="ramp.com",
        )

        _, c2 = store.register_user(
            first_name="B",
            last_name="L",
            email="b@ramp.com",
            password="p2",
            company_name="Ramp",
            company_domain="www.ramp.com",
        )

        assert c1.id == c2.id
        # www shouldn't be in additional_domains
        assert "www.ramp.com" not in c2.additional_domains

    def test_different_domain_creates_new_company(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)

        _, c1 = store.register_user(
            first_name="A",
            last_name="K",
            email="a@ramp.com",
            password="p1",
            company_name="Ramp",
            company_domain="ramp.com",
        )

        _, c2 = store.register_user(
            first_name="B",
            last_name="L",
            email="b@carta.com",
            password="p2",
            company_name="Carta",
            company_domain="carta.com",
        )

        assert c1.id != c2.id

    def test_duplicate_email_raises(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)

        store.register_user(
            first_name="Aryan",
            last_name="Keshri",
            email="aryan@ramp.com",
            password="p1",
            company_name="Ramp",
            company_domain="ramp.com",
        )

        with pytest.raises(ValueError, match="already exists"):
            store.register_user(
                first_name="Aryan",
                last_name="Keshri",
                email="aryan@ramp.com",
                password="p2",
                company_name="Ramp",
                company_domain="ramp.com",
            )

    def test_company_slug_derived_from_name(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        _, company = store.register_user(
            first_name="A",
            last_name="K",
            email="a@test.com",
            password="p1",
            company_name="Ramp Financial",
            company_domain="ramp.com",
        )

        assert company.slug == "ramp-financial"

    def test_registration_persists_to_disk(self, tmp_path: Path) -> None:
        store1 = AuthStore(base_dir=tmp_path)
        user, company = store1.register_user(
            first_name="Aryan",
            last_name="Keshri",
            email="aryan@ramp.com",
            password="pass",
            company_name="Ramp",
            company_domain="ramp.com",
        )

        # New store instance from same directory
        store2 = AuthStore(base_dir=tmp_path)
        found_company = store2.get_company_by_domain("ramp.com")
        assert found_company is not None
        assert found_company.id == company.id

        found_user = store2.get_user_by_email("aryan@ramp.com")
        assert found_user is not None
        assert found_user["first_name"] == "Aryan"


# ── UserProfile first_name / last_name ────────────────────────────


class TestUserProfileNames:
    """Test that UserProfile uses separate first_name and last_name fields."""

    def test_first_last_name_fields(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        user = store.create_user(
            company_id=company.id,
            email="test@ramp.com",
            first_name="John",
            last_name="Doe",
            password="pass",
        )

        assert user.first_name == "John"
        assert user.last_name == "Doe"

    def test_full_name_property(self, tmp_path: Path) -> None:
        store = AuthStore(base_dir=tmp_path)
        company = store.create_company(slug="ramp", name="Ramp", domain="ramp.com")

        user = store.create_user(
            company_id=company.id,
            email="test@ramp.com",
            first_name="John",
            last_name="Doe",
            password="pass",
        )

        assert user.full_name == "John Doe"


# ── Registration endpoint ─────────────────────────────────────────


class TestRegistrationEndpoint:
    """Test POST /api/v1/auth/register."""

    def test_register_new_user_and_company(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Aryan",
                "last_name": "Keshri",
                "email": "aryan@ramp.com",
                "password": "securepassword123",
                "company_name": "Ramp",
                "company_domain": "ramp.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["access_token"]
        assert data["user"]["first_name"] == "Aryan"
        assert data["user"]["last_name"] == "Keshri"
        assert data["user"]["email"] == "aryan@ramp.com"
        assert data["user"]["role"] == "superuser"
        assert data["company"]["name"] == "Ramp"
        assert data["company"]["domain"] == "ramp.com"

    def test_register_second_user_same_company(self, client: TestClient) -> None:
        # First user
        client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Aryan",
                "last_name": "Keshri",
                "email": "aryan@ramp.com",
                "password": "securepass1",
                "company_name": "Ramp",
                "company_domain": "ramp.com",
            },
        )

        # Second user, same company
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@ramp.com",
                "password": "securepass2",
                "company_name": "Ramp",
                "company_domain": "ramp.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["role"] == "member"

    def test_register_duplicate_email_409(self, client: TestClient) -> None:
        client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Aryan",
                "last_name": "Keshri",
                "email": "aryan@ramp.com",
                "password": "securepass1",
                "company_name": "Ramp",
                "company_domain": "ramp.com",
            },
        )

        resp = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Aryan",
                "last_name": "Keshri",
                "email": "aryan@ramp.com",
                "password": "securepass2",
                "company_name": "Ramp",
                "company_domain": "ramp.com",
            },
        )
        assert resp.status_code == 409

    def test_register_missing_required_fields(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "a@b.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 422

    def test_register_subdomain_joins_existing_company(self, client: TestClient) -> None:
        # First user creates company with ramp.com
        resp1 = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "A",
                "last_name": "K",
                "email": "a@ramp.com",
                "password": "password01",
                "company_name": "Ramp",
                "company_domain": "ramp.com",
            },
        )
        company_id_1 = resp1.json()["company"]["id"]

        # Second user provides app.ramp.com — should match
        resp2 = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "B",
                "last_name": "L",
                "email": "b@ramp.com",
                "password": "password02",
                "company_name": "Ramp",
                "company_domain": "app.ramp.com",
            },
        )
        assert resp2.status_code == 201
        company_id_2 = resp2.json()["company"]["id"]
        assert company_id_1 == company_id_2
